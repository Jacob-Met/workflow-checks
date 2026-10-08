"""Independent real CLI/worksheet receiving; synthetic fixtures, no browser claim."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser

import uwatch

SOURCE = Path(uwatch.__file__).resolve().parents[1]
ACCOUNT_COLUMNS = "account_no property utility vendor scope unit cycle".split()
BILL_COLUMNS = (
    "bill_id account_no vendor_invoice_no period_start period_end usage usage_unit "
    "amount late_fee prior_balance due_date received_date"
).split()
OCCUPANCY_COLUMNS = "property unit status from to".split()
PAYMENT_COLUMNS = "payment_id account_no vendor_invoice_no amount paid_date".split()
SCRIPT_LITERAL = '<script data-e827="literal">window.e827ReviewInjected = true</script>'
ACCOUNTS = ("account-East", "account-West", "account-Return")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path, columns, rows, *, bom=False):
    with path.open("w", encoding="utf-8-sig" if bom else "utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        return list(reader.fieldnames or []), list(reader)


def finding_rows(path):
    return [row for row in read_csv(path)[1] if row["row_state"] != "manifest"]


def identity(row):
    return row["account_no"], row["kind"], row["code"]


class ArticleText(HTMLParser):
    """Read semantic finding articles without evaluating JavaScript or CSS."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.articles = []
        self.script_text = []
        self.in_script = 0
        self.in_style = 0
        self.active = None
        self.attributes = []

    def handle_starttag(self, tag, attrs):
        self.attributes.extend(attrs)
        if tag == "script":
            self.in_script += 1
        elif tag == "style":
            self.in_style += 1
        elif tag == "article":
            if self.active is not None:
                raise AssertionError("nested finding articles are ambiguous")
            self.active = {"attrs": dict(attrs), "parts": []}
        elif tag == "br" and self.active is not None:
            self.active["parts"].append("\n")

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script -= 1
        elif tag == "style":
            self.in_style -= 1
        elif tag == "article" and self.active is not None:
            self.active["text"] = "".join(self.active.pop("parts"))
            self.articles.append(self.active)
            self.active = None

    def handle_data(self, data):
        if self.in_script:
            self.script_text.append(data)
        elif not self.in_style and self.active is not None:
            self.active["parts"].append(data)


class ReviewReportReceiving(unittest.TestCase):
    def setUp(self):
        retained = os.environ.get("UWATCH_RECEIVING_OUTPUT")
        if retained:
            self.work = Path(retained) / self._testMethodName
            self.work.mkdir(parents=True, exist_ok=False)
        else:
            temporary = tempfile.TemporaryDirectory(prefix="uwatch-report-peer-")
            self.addCleanup(temporary.cleanup)
            self.work = Path(temporary.name)
        (self.work / "tmp").mkdir()
        self.protected = set()
        self.source_before = self.source_hashes()
        self.commands = 0

    def source_hashes(self):
        return {str(path.relative_to(SOURCE)): sha256(path)
                for path in sorted((SOURCE / "uwatch").glob("*.py"))}

    def tearDown(self):
        self.assertEqual(self.source_before, self.source_hashes(), "native source bytes changed")
        (self.work / "source-hashes.json").write_text(
            json.dumps(self.source_before, indent=2) + "\n", encoding="utf-8")

    def cli(self, *args):
        env = dict(os.environ)
        env.update(PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(self.work / "tmp"))
        command = [sys.executable, "-B", "-m", "uwatch", *(str(arg) for arg in args)]
        result = subprocess.run(command, cwd=SOURCE, env=env, capture_output=True,
                                text=True, encoding="utf-8", timeout=30, check=False)
        self.commands += 1
        record = {"sequence": self.commands, "argv": command, "cwd": str(SOURCE),
                  "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        with (self.work / "commands.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        return result

    def success(self, *args):
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return result

    def data(self, *, fees=(5, 7, 9), count=3):
        data = self.work / "data"
        data.mkdir()
        accounts, bills = [], []
        for index, account in enumerate(ACCOUNTS[:count]):
            accounts.append(dict(zip(ACCOUNT_COLUMNS, [account, 'North & West <Annex>', "water",
                "fixture-vendor", "unit", str(index + 1), "monthly"])))
            bills.append(dict(zip(BILL_COLUMNS, [
                "shared-bill-007" if index < 2 else "return-bill-009", account, f"vendor-{index + 1}",
                "2026-09-01", "2026-09-30", "12", "kgal", "40", str(fees[index]), "0",
                "2026-10-31", "2026-10-01"])))
        write_csv(data / "accounts.csv", ACCOUNT_COLUMNS, accounts)
        write_csv(data / "bills.csv", BILL_COLUMNS, bills)
        write_csv(data / "occupancy.csv", OCCUPANCY_COLUMNS, [])
        write_csv(data / "payments.csv", PAYMENT_COLUMNS, [])
        # Explicitly synthetic through the existing native marker convention.
        (data / "expected.json").write_text(
            '{"as_of":"2026-10-08","eval_from":"2026-09-01"}\n', encoding="utf-8")
        self.protected.update(data.iterdir())
        return data

    def native_review(self, data, stage, previous=None):
        report = self.work / f"report-{stage}"
        self.success("run", "--data", data, "--out", report,
                     "--as-of", "2026-10-08", "--eval-from", "2026-09-01")
        self.protected.update(report.iterdir())
        worksheet = self.work / f"review-{stage}.csv"
        args = ["review", "--data", data, "--report", report / "summary.json", "--out", worksheet]
        if previous:
            args.extend(["--previous", previous])
        self.success(*args)
        self.protected.add(worksheet)
        return worksheet

    def annotate(self, worksheet):
        columns, rows = read_csv(worksheet)
        for row in rows:
            if row["row_state"] != "manifest":
                row["review_status"] = "reviewed"
                row["reviewer"] = f'Zoë <{row["account_no"]}> & peer'
                row["note"] = (f'Original {row["account_no"]}/{row["kind"]}/{row["code"]}\n'
                               f'{SCRIPT_LITERAL}\n"quoted", A & B > C; =SUM(1,2)')
        write_csv(worksheet, columns, rows)

    def report(self, worksheet, destination):
        before = {str(path): sha256(path) for path in self.protected}
        result = self.cli("review-report", "--worksheet", worksheet, "--out", destination)
        self.assertEqual(before, {str(path): sha256(path) for path in self.protected},
                         "report changed source, native report, or saved worksheet")
        return result

    def assert_rendered(self, worksheet, destination):
        result = self.report(worksheet, destination)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertTrue(destination.is_file())
        parser = ArticleText()
        parser.feed(destination.read_text(encoding="utf-8"))
        parser.close()
        native = finding_rows(worksheet)
        self.assertEqual(len(parser.articles), len(native), "every finding appears exactly once")
        # Escaped text in inert data attributes is legitimate search metadata.
        self.assertFalse(any(key == "data-e827" and value == "literal"
                             for key, value in parser.attributes), "literal note became markup")
        self.assertFalse(any(key.casefold().startswith("on") and "e827ReviewInjected" in (value or "")
                             for key, value in parser.attributes), "literal note became an event handler")
        remaining = list(parser.articles)
        for row in native:
            tokens = [row[key] for key in ("account_no", "finding_key", "code", "property", "utility",
                      "detail", "reviewer", "note") if row[key]] + json.loads(row["evidence"])
            matches = []
            for article in remaining:
                words = article["text"].casefold().replace("_", " ")
                state = re.search(r"\b" + row["row_state"] + r"\b", words)
                status = re.search(r"\b" + row["review_status"].strip().replace("_", " ") + r"\b", words)
                if state and status and all(token in article["text"] for token in tokens):
                    matches.append(article)
            self.assertEqual(len(matches), 1, f"lost/merged/misassociated row: {identity(row)} {row['row_state']}")
            article = matches[0]
            self.assertNotIn("hidden", article["attrs"], "findings must be readable without JavaScript")
            self.assertNotRegex(article["attrs"].get("style", "").lower(), r"display\s*:\s*none")
            remaining.remove(article)
        self.assertFalse(remaining)
        (self.work / "rendered-receipt.json").write_text(json.dumps({
            "worksheet_sha256": sha256(worksheet), "html_sha256": sha256(destination),
            "native_rows": len(native), "semantic_articles": len(parser.articles),
            "states": {state: sum(row["row_state"] == state for row in native)
                       for state in ("current", "changed", "absent")},
            "browser_executed": False}, indent=2) + "\n", encoding="utf-8")

    def assert_refused(self, worksheet, destination):
        result = self.report(worksheet, destination)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn("invalid choice: 'review-report'", result.stderr,
                         "an absent command is not evidence of validation")

    def test_native_returned_evidence_keeps_account_and_historical_notes_separate(self):
        data = self.data()
        original_bills = (data / "bills.csv").read_bytes()
        first = self.native_review(data, "first")
        self.annotate(first)
        original = {identity(row): row for row in finding_rows(first)}
        self.assertEqual(len(original), 6)
        east = original[(ACCOUNTS[0], "flag", "LATE_FEE_OR_PAST_DUE")]
        west = original[(ACCOUNTS[1], "flag", "LATE_FEE_OR_PAST_DUE")]
        self.assertEqual(east["finding_key"], west["finding_key"])
        self.assertNotEqual(east["finding_id"], west["finding_id"])
        columns, bills = read_csv(data / "bills.csv")
        bills[0]["late_fee"], bills[2]["late_fee"] = "6", "0"
        write_csv(data / "bills.csv", columns, bills)
        second = self.native_review(data, "second", first)
        rows = finding_rows(second)
        self.assertEqual({state: sum(row["row_state"] == state for row in rows)
                          for state in ("current", "changed", "absent")},
                         {"current": 5, "changed": 3, "absent": 1})
        columns, annotated = read_csv(second)
        for row in annotated:
            if identity(row) == (ACCOUNTS[0], "flag", "LATE_FEE_OR_PAST_DUE") and row["row_state"] == "current":
                row.update(review_status="in_progress", reviewer="Second reviewer", note="Intermediate evidence only")
        write_csv(second, columns, annotated)
        (data / "bills.csv").write_bytes(original_bills)
        returned = self.native_review(data, "returned", second)
        rows = finding_rows(returned)
        self.assertEqual({state: sum(row["row_state"] == state for row in rows)
                          for state in ("current", "changed", "absent")},
                         {"current": 6, "changed": 6, "absent": 1})
        current = {identity(row): row for row in rows if row["row_state"] == "current"}
        for key, row in current.items():
            old = original[key]
            if key[0] == ACCOUNTS[1]:
                self.assertEqual([row[field] for field in ("row_id", "review_status", "reviewer", "note")],
                                 [old[field] for field in ("row_id", "review_status", "reviewer", "note")])
            else:
                self.assertEqual(row["evidence_version"], old["evidence_version"])
                self.assertNotEqual(row["row_id"], old["row_id"])
                self.assertEqual((row["review_status"], row["reviewer"], row["note"]), ("open", "", ""))
                historical = [saved for saved in rows if saved["row_id"] == old["row_id"]]
                self.assertEqual(len(historical), 1)
                self.assertEqual(historical[0]["note"], old["note"])
                self.assertIn(historical[0]["row_state"], ("changed", "absent"))
        self.assert_rendered(returned, self.work / "returned-review.html")

    def test_exception_only_bom_reordered_columns_keep_literal_annotations(self):
        data = self.data(fees=(0, 0), count=2)
        worksheet = self.native_review(data, "exceptions")
        self.annotate(worksheet)
        columns, rows = read_csv(worksheet)
        findings = [row for row in rows if row["row_state"] != "manifest"]
        self.assertEqual(len(findings), 2)
        self.assertTrue(all(row["kind"] == "exception" for row in findings))
        findings[0].update(review_status="  in_progress  ", reviewer='Review "lead"',
                           note=f'Line one\n{SCRIPT_LITERAL}\nLiteral &amp; entity stays literal')
        write_csv(worksheet, list(reversed(columns)), list(reversed(rows)), bom=True)
        self.assertTrue(worksheet.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assert_rendered(worksheet, self.work / "exception-review.html")

    def test_missing_integrity_manifest_refuses_new_output_and_preserves_input(self):
        data = self.data(fees=(0,), count=1)
        worksheet = self.native_review(data, "manifest")
        columns, rows = read_csv(worksheet)
        missing = self.work / "missing-manifest.csv"
        write_csv(missing, columns, [row for row in rows if row["row_state"] != "manifest"])
        self.protected.add(missing)
        destination = self.work / "refused.html"
        self.assert_refused(missing, destination)
        self.assertFalse(destination.exists())

    def test_hardlink_broken_symlink_and_unwritable_parent_are_preserved(self):
        data = self.data(fees=(0,), count=1)
        worksheet = self.native_review(data, "destinations")
        hardlink = self.work / "worksheet-hardlink.html"
        os.link(worksheet, hardlink)
        self.protected.add(hardlink)
        self.assert_refused(worksheet, hardlink)
        self.assertTrue(worksheet.samefile(hardlink))
        missing_target = self.work / "absent-target.html"
        link = self.work / "broken-report.html"
        link.symlink_to(missing_target)
        self.assert_refused(worksheet, link)
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.readlink(), missing_target)
        self.assertFalse(missing_target.exists())
        parent = self.work / "ordinary-file"
        parent.write_bytes(b"keep this exact destination parent\n")
        self.protected.add(parent)
        self.assert_refused(worksheet, parent / "report.html")
        self.assertEqual(parent.read_bytes(), b"keep this exact destination parent\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
