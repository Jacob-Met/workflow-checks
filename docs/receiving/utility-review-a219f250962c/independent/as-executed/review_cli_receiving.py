"""Independent actual-CLI receiving controls; synthetic CSV inputs, no source edits."""
from __future__ import annotations

import calendar
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


SOURCE = Path(os.environ.get("UWATCH_REVIEW_SOURCE", "/dev/shm/utility-review-a219f250962c/utility_watch")).resolve()
REPO = SOURCE.parent
ROOT = Path(__file__).resolve().parent
RUN = ROOT / ("run-" + str(time.time_ns()))
RUN.mkdir()
EXECUTIONS = []
HEADERS = {
    "accounts.csv": "account_no property utility vendor scope unit cycle".split(),
    "bills.csv": "bill_id account_no vendor_invoice_no period_start period_end usage usage_unit amount late_fee prior_balance due_date received_date".split(),
    "occupancy.csv": "property unit status from to".split(),
    "payments.csv": "payment_id account_no vendor_invoice_no amount paid_date".split(),
}
REPORTS = ("summary.json", "flags.csv", "exceptions.csv", "payment_queue.csv", "report.html", "audit.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames), list(reader)


def write_rows(path, columns, records):
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)


def bill(account, year, month, amount=100.0):
    key = f"{account}-{year}-{month:02d}"
    return dict(zip(HEADERS["bills.csv"], (
        key, account, "INV-" + key, f"{year}-{month:02d}-01",
        f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]}",
        "100.0", "kWh", str(amount), "0", "0", "2026-10-30", "2026-10-01",
    )))


class ActualCLIReceiving(unittest.TestCase):
    def setUp(self):
        self.case = RUN / self._testMethodName
        self.case.mkdir()
        self.data = self.case / "data"
        self.data.mkdir()
        self.report = self.case / "report"
        self.serial = 0
        accounts = [dict(zip(HEADERS["accounts.csv"], (a, "Independent Terrace", "electric", "Fictional vendor", "common", "", "monthly")))
                    for a in ("RATE-A", "CLEAN-B", "MISSING-C", "EXCEPT-D")]
        bills = ([bill("RATE-A", 2025, 9)] + [bill("RATE-A", 2026, m) for m in range(3, 9)] +
                 [bill("RATE-A", 2026, 9, 150.0), bill("CLEAN-B", 2025, 9), bill("CLEAN-B", 2026, 9),
                  bill("MISSING-C", 2026, 7), bill("EXCEPT-D", 2026, 9)])
        for name, values in (("accounts.csv", accounts), ("bills.csv", bills), ("occupancy.csv", []), ("payments.csv", [])):
            write_rows(self.data / name, HEADERS[name], values)
        self.native_run()

    def command(self, *args, source=SOURCE):
        env = dict(os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(self.case))
        result = subprocess.run([sys.executable, "-B", "-m", "uwatch", *map(str, args)],
                                cwd=source, env=env, capture_output=True, text=True, timeout=15)
        EXECUTIONS.append({"case": self._testMethodName, "arguments": list(map(str, args)), "source": str(source),
                           "exit": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        return result

    def native_run(self, out=None, source=SOURCE):
        result = self.command("run", "--data", self.data, "--out", out or self.report,
                              "--as-of", "2026-10-08", "--eval-from", "2026-09-01", source=source)
        self.assertEqual(result.returncode, 0, result.stderr)

    def protected(self):
        paths = list(self.data.iterdir()) + list(self.report.iterdir())
        return {str(p): p.read_bytes() for p in paths if p.is_file()}

    def review(self, previous=None, out=None, report=None, expected=0):
        self.serial += 1
        out = out or self.case / f"review-{self.serial}.csv"
        arguments = ["review", "--data", self.data, "--report", report or self.report / "summary.json", "--out", out]
        if previous is not None:
            arguments += ["--previous", previous]
        before = self.protected()
        prior = previous.read_bytes() if previous is not None else None
        result = self.command(*arguments)
        self.assertEqual(result.returncode, expected, result.stderr)
        self.assertEqual(before, self.protected(), "review modified source or native reports/queues")
        if previous is not None:
            self.assertEqual(previous.read_bytes(), prior, "previous annotation file changed")
        return out

    def current(self, path, account="RATE-A", code="RATE_CHANGE"):
        selected = [r for r in rows(path)[1] if r["row_state"] == "current" and r["account_no"] == account and r["code"] == code]
        self.assertEqual(len(selected), 1)
        return selected[0]

    def annotate(self, path, account="RATE-A", code="RATE_CHANGE", note="Independent reviewer checked this exact evidence."):
        columns, values = rows(path)
        for row in values:
            if row["row_state"] == "current" and row["account_no"] == account and row["code"] == code:
                row.update(review_status="reviewed", reviewer="  Independent reviewer  ", note=note)
        write_rows(path, columns, values)

    def amount(self, account, year, month, amount):
        columns, values = rows(self.data / "bills.csv")
        matches = [r for r in values if r["bill_id"] == f"{account}-{year}-{month:02d}"]
        self.assertEqual(len(matches), 1)
        matches[0]["amount"] = str(amount)
        write_rows(self.data / "bills.csv", columns, values)

    def test_fresh_findings_and_unchanged_native_queue(self):
        output = self.review()
        findings = [r for r in rows(output)[1] if r["row_state"] == "current"]
        self.assertEqual({(r["account_no"], r["kind"], r["code"]) for r in findings},
                         {("RATE-A", "flag", "RATE_CHANGE"), ("MISSING-C", "flag", "MISSING_BILL"), ("EXCEPT-D", "exception", "NO_BASELINE")})
        self.assertTrue(all((r["review_status"], r["reviewer"], r["note"]) == ("open", "", "") for r in findings))
        queue = rows(self.report / "payment_queue.csv")[1]
        self.assertEqual([r["account_no"] for r in queue], ["CLEAN-B"])
        self.assertEqual(queue[0]["status"], "QUEUED_FOR_APPROVAL (not paid)")

    def test_multiline_unicode_notes_and_column_row_reorder(self):
        first = self.review()
        note = '  First line, "quoted".\r\nSecond line: café e\u0301 / 東京 / 😀\t  '
        self.annotate(first, note=note)
        self.annotate(first, "EXCEPT-D", "NO_BASELINE", "Separate exception annotation")
        before = self.current(first)
        columns, values = rows(first)
        write_rows(first, list(reversed(columns)), list(reversed(values)))
        second = self.review(first)
        after = self.current(second)
        for key in ("note", "reviewer", "review_status", "row_id", "finding_id", "evidence_version"):
            self.assertEqual(after[key], before[key])
        self.assertEqual(after["note"], note)
        self.assertEqual(self.current(second, "EXCEPT-D", "NO_BASELINE")["note"], "Separate exception annotation")

    def test_unrounded_current_and_historical_facts_invalidate_note(self):
        for year, month, value in ((2026, 9, 150.001), (2026, 3, 100.001)):
            with self.subTest(year=year, month=month):
                self.amount("RATE-A", 2026, 9, 150.0)
                self.amount("RATE-A", 2026, 3, 100.0)
                self.native_run()
                before_report = (self.report / "summary.json").read_bytes()
                old = self.review()
                self.annotate(old)
                old_row = self.current(old)
                self.amount("RATE-A", year, month, value)
                # Actual report is byte-identical despite the changed underlying fact.
                fresh_report = self.case / f"rounded-{month}"
                self.native_run(out=fresh_report)
                self.assertEqual((fresh_report / "summary.json").read_bytes(), before_report)
                new = self.review(old)
                new_row = self.current(new)
                self.assertEqual(new_row["detail"], old_row["detail"])
                self.assertNotEqual(new_row["evidence_version"], old_row["evidence_version"])
                self.assertEqual((new_row["review_status"], new_row["note"]), ("open", ""))
                historic = [r for r in rows(new)[1] if r["row_id"] == old_row["row_id"]]
                self.assertEqual([(r["row_state"], r["note"]) for r in historic], [("changed", old_row["note"])])

    def test_other_account_change_preserves_exact_account_note(self):
        old = self.review()
        self.annotate(old)
        old_row = self.current(old)
        self.amount("CLEAN-B", 2026, 9, 101.0)
        self.native_run()
        new = self.review(old)
        after = self.current(new)
        for key in ("note", "review_status", "row_id", "evidence_version"):
            self.assertEqual(after[key], old_row[key])
        self.assertEqual(rows(self.report / "payment_queue.csv")[1][0]["amount_due"], "101.0")

    def test_changed_absent_and_returning_evidence_never_resurrects_review(self):
        old = self.review()
        self.annotate(old, note="Review of original rate")
        original = self.current(old)
        self.amount("RATE-A", 2026, 9, 160.0)
        self.native_run()
        changed = self.review(old)
        self.annotate(changed, note="Review of changed rate")
        changed_row = self.current(changed)
        self.amount("RATE-A", 2026, 9, 100.0)
        self.native_run()
        absent = self.review(changed)
        self.assertFalse(any(r["account_no"] == "RATE-A" and r["row_state"] == "current" for r in rows(absent)[1]))
        self.amount("RATE-A", 2026, 9, 150.0)
        self.native_run()
        returned = self.review(absent)
        current = self.current(returned)
        self.assertEqual(current["evidence_version"], original["evidence_version"])
        self.assertEqual((current["review_status"], current["reviewer"], current["note"]), ("open", "", ""))
        self.assertNotIn(current["row_id"], (original["row_id"], changed_row["row_id"]))
        history = {r["row_id"]: r for r in rows(returned)[1] if r["row_state"] in ("changed", "absent")}
        self.assertEqual((history[original["row_id"]]["row_state"], history[original["row_id"]]["note"]), ("changed", original["note"]))
        self.assertEqual((history[changed_row["row_id"]]["row_state"], history[changed_row["row_id"]]["note"]), ("absent", changed_row["note"]))

    def test_stale_or_malformed_report_refuses_before_publication(self):
        original = (self.report / "summary.json").read_bytes()
        self.amount("RATE-A", 2026, 9, 200.0)
        self.assertFalse(self.review(expected=2).exists())
        self.amount("RATE-A", 2026, 9, 150.0)
        parsed = json.loads(original)
        variants = []
        for field, value in (("payment_queue", True), ("bills", 12.0), ("flags", 999), ("flags_detail", [])):
            doc = dict(parsed); doc[field] = value
            variants.append(json.dumps(doc))
        variants += [original.decode().replace('"flags": 2', '"flags": 2, "flags": 2', 1),
                     original.decode()[:-1] + ', "invalid": NaN}', '{"as_of":"invalid"}']
        for n, text in enumerate(variants):
            with self.subTest(report=n):
                path = self.case / f"invalid-{n}.json"
                path.write_text(text)
                self.assertFalse(self.review(report=path, expected=2).exists())

    def test_annotation_integrity_and_status_refusals(self):
        old = self.review()
        columns, original = rows(old)
        changes = ("protected", "missing_row", "duplicate_row", "missing_manifest", "bad_status", "no_reviewer", "no_note")
        for change in changes:
            with self.subTest(change=change):
                values = [dict(row) for row in original]
                finding = next(r for r in values if r["row_state"] == "current")
                if change == "protected": finding["detail"] += " altered"
                elif change == "missing_row": values.remove(finding)
                elif change == "duplicate_row": values.append(dict(finding))
                elif change == "missing_manifest": values = [r for r in values if r["row_state"] != "manifest"]
                elif change == "bad_status": finding["review_status"] = "paid"
                elif change == "no_reviewer": finding.update(review_status="reviewed", note="Checked", reviewer=" ")
                elif change == "no_note": finding.update(review_status="in_progress", reviewer="Reviewer", note="\r\n")
                altered = self.case / f"{change}.csv"
                write_rows(altered, columns, values)
                self.assertFalse(self.review(altered, expected=2).exists())

    def test_source_ambiguity_and_csv_corruption_refuse(self):
        path = self.data / "accounts.csv"
        original = path.read_bytes()
        columns, records = rows(path)
        variants = [original + original.splitlines(keepends=True)[1],
                    original.replace(b"account_no,", b"account_no,account_no,", 1),
                    original + b'"unfinished quote\n']
        for n, content in enumerate(variants):
            with self.subTest(source=n):
                path.write_bytes(content)
                self.assertFalse(self.review(expected=2).exists())
        path.write_bytes(original)

    def test_existing_reserved_and_symlink_outputs_remain_untouched(self):
        previous = self.review()
        destinations = [self.data / name for name in HEADERS] + [self.data / "expected.json"] + [self.report / name for name in REPORTS] + [previous]
        for out in destinations:
            with self.subTest(out=str(out)):
                existed = out.exists()
                content = out.read_bytes() if existed else None
                self.review(previous, out=out, expected=2)
                self.assertEqual(out.exists(), existed)
                if existed: self.assertEqual(out.read_bytes(), content)
        existing = self.case / "owned-by-another-review.csv"
        existing.write_bytes(b"Existing review must survive\n")
        self.review(previous, out=existing, expected=2)
        self.assertEqual(existing.read_bytes(), b"Existing review must survive\n")
        link = self.case / "dangling-review.csv"
        link.symlink_to("absent-target.csv")
        self.review(previous, out=link, expected=2)
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), "absent-target.csv")
        self.assertFalse((self.case / "absent-target.csv").exists())

    def test_actual_run_cli_remains_identical_to_original_native_source(self):
        baseline = self.case / "baseline" / "utility_watch"
        package = baseline / "uwatch"
        package.mkdir(parents=True)
        manifest = json.loads(Path("/dev/shm/utility-review-a219f250962c-base.json").read_text())
        native = {item["path"]: item for item in manifest["files"]}
        for name in ("__init__.py", "__main__.py", "cli.py", "engine.py", "report.py", "synth.py"):
            relative = "utility_watch/uwatch/" + name
            content = subprocess.check_output(["git", "show", "906f1e058e41bee015a58466d5eee9f14ed71394:" + relative], cwd=REPO)
            self.assertEqual(hashlib.sha256(content).hexdigest(), native[relative]["sha256"])
            (package / name).write_bytes(content)
            if name != "cli.py":
                self.assertEqual((SOURCE / "uwatch" / name).read_bytes(), content)
        old_report = self.case / "original-native-report"
        self.native_run(out=old_report, source=baseline)
        for name in REPORTS:
            self.assertEqual((old_report / name).read_bytes(), (self.report / name).read_bytes(), name)


if __name__ == "__main__":
    source_before = {str(p.relative_to(SOURCE)): sha(p) for p in (SOURCE / "uwatch").glob("*.py")}
    git_before = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ActualCLIReceiving)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    source_after = {str(p.relative_to(SOURCE)): sha(p) for p in (SOURCE / "uwatch").glob("*.py")}
    receipt = {"source": str(SOURCE), "commit_at_start": git_before,
               "commit_at_end": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
               "source_sha256": source_before, "source_unchanged_during_review": source_before == source_after,
               "synthetic_inputs_only": True, "actual_cli_invocations": len(EXECUTIONS), "tests": result.testsRun,
               "failures": len(result.failures), "errors": len(result.errors), "successful": result.wasSuccessful(),
               "executions": EXECUTIONS}
    (RUN / "receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    print("RECEIPT", RUN / "receipt.json")
    sys.exit(0 if result.wasSuccessful() and source_before == source_after else 1)
