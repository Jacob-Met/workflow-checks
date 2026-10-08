"""Read real cited CSV records without changing native findings or source custody."""
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from uwatch import engine, evidence, review  # noqa: E402

HEADERS = {
    "accounts.csv": "account_no,property,utility,vendor,scope,unit,cycle".split(","),
    "bills.csv": ("bill_id,account_no,vendor_invoice_no,period_start,period_end,usage,"
                  "usage_unit,amount,late_fee,prior_balance,due_date,received_date,memo").split(","),
    "occupancy.csv": "property,unit,status,from,to".split(","),
    "payments.csv": "payment_id,account_no,vendor_invoice_no,amount,paid_date".split(","),
}


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="uwatch-evidence-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = self.root / "data"
        self.report_dir = self.root / "report"
        self.data.mkdir()
        self.accounts = [
            dict(zip(HEADERS["accounts.csv"],
                     [key, prop, "water", "Fictional vendor", "common", "", "irregular"]))
            for key, prop in (("A", "Maple, West\r\nWing α"), ("B", "Birch"))
        ]
        self.bills = [
            dict(zip(HEADERS["bills.csv"], [
                key, account, invoice, f"{year}-08-01", f"{year}-08-31", usage, "kgal",
                amount, "0", "0", due, "2026-09-01", memo,
            ])) for key, account, invoice, year, usage, amount, due, memo in (
                ("A-BASE", "A", "old", 2025, "31", "62", "2025-09-20", ""),
                ("SHARED", "A", "current, α", 2026, "93", "186", "2026-09-20",
                 '  =SUM(1,2)\r\nInvoice says "inspect"\nend  '),
                ("SHARED", "B", "other", 2026, "31", "62", "2026-10-20", "other account"),
            )
        ]
        for name, rows in {
            "accounts.csv": self.accounts, "bills.csv": self.bills,
            "occupancy.csv": [], "payments.csv": [
                dict(zip(HEADERS["payments.csv"], ["PAY-OLD", "A", "old", "62", "2025-09-15"]))
            ],
        }.items():
            self.write_csv(name, rows)
        self.regenerate()

    def write_csv(self, name, rows):
        with (self.data / name).open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=HEADERS[name], lineterminator="\r\n")
            writer.writeheader()
            writer.writerows(rows)

    def regenerate(self, as_of=date(2026, 9, 28)):
        self.summary = engine.run(self.data, self.report_dir, as_of, eval_from=date(2026, 8, 1))
        self.report = self.report_dir / "summary.json"

    def inputs(self):
        return {str(path): path.read_bytes() for directory in (self.data, self.report_dir)
                for path in directory.iterdir() if path.is_file()}

    def emit(self, name="evidence.json", **selector):
        chosen = {"kind": "flag", "account": "A", "key": "SHARED", "code": "USAGE_SPIKE"}
        chosen.update(selector)
        return evidence.write_evidence(self.data, self.report, self.root / name, **chosen)

    def assert_no_output(self, name="evidence.json"):
        self.assertFalse((self.root / name).exists())
        self.assertEqual(list(self.root.glob(".uwatch-evidence-*")), [])

    def cli(self, *extra):
        return subprocess.run([
            sys.executable, "-B", "-m", "uwatch", "evidence",
            "--data", str(self.data), "--report", str(self.report),
            "--kind", "flag", "--account", "A", "--key", "SHARED", "--code", "USAGE_SPIKE",
            "--out", str(self.root / "evidence.json"), *extra,
        ], cwd=PACKAGE, capture_output=True, text=True)

    def test_actual_cli_preserves_bom_multiline_cells_pointer_order_and_all_inputs(self):
        before = self.inputs()
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("2 source records", result.stdout)
        document = json.loads((self.root / "evidence.json").read_bytes())
        self.assertEqual(document["schema"], "uwatch-evidence-v1")
        self.assertEqual(document["finding"]["evidence"], ["bills.csv:5", "bills.csv:2"])
        self.assertEqual([r["record_end_line"] for r in document["records"]], [5, 2])
        self.assertEqual(document["records"][0]["columns"], HEADERS["bills.csv"])
        self.assertEqual(document["records"][0]["fields"], self.bills[1])
        self.assertEqual(document["records"][1]["fields"], self.bills[0])
        self.assertEqual(document["review"], {
            "as_of": "2026-09-28", "eval_from": "2026-08-01", "data_mode": "client_csv",
        })
        self.assertEqual(self.inputs(), before)
        for item in document["source"]["inputs"]:
            path = self.data / item["file"]
            if item["present"]:
                self.assertEqual(item["sha256"], hashlib.sha256(before[str(path)]).hexdigest())
                self.assertEqual(item["bytes"], len(before[str(path)]))
            else:
                self.assertEqual(item, {
                    "file": "expected.json", "present": False, "bytes": None, "sha256": None,
                })
        self.assertEqual(document["source"]["report"]["sha256"],
                         hashlib.sha256(before[str(self.report)]).hexdigest())
        self.assertNotIn(str(self.root), (self.root / "evidence.json").read_text())

    def test_same_key_on_other_account_and_multiple_codes_choose_only_exact_finding(self):
        selected = self.emit(kind="exception", account="B", code="NO_BASELINE")
        self.assertEqual(selected["finding"]["account_no"], "B")
        self.assertEqual(selected["records"][0]["fields"], self.bills[2])
        self.assertEqual(selected["finding"]["evidence"], ["bills.csv:6"])
        other = self.emit("unpaid.json", code="UNPAID_PAST_DUE")
        self.assertEqual(len(other["records"]), 1)
        self.assertEqual(other["finding"]["code"], "UNPAID_PAST_DUE")

    def test_missing_bill_resolves_complete_multiline_account_record(self):
        self.accounts[0]["cycle"] = "monthly"
        self.write_csv("accounts.csv", self.accounts)
        self.regenerate(date(2026, 10, 28))
        selected = self.emit(key="A:2026-09-01", code="MISSING_BILL")
        self.assertEqual(selected["finding"]["evidence"], ["accounts.csv:3"])
        self.assertEqual(selected["records"][0]["fields"], self.accounts[0])
        self.assertEqual(selected["records"][0]["record_end_line"], 3)

    def test_repeated_pointer_order_and_inside_record_pointer_refusal(self):
        raw = {name: (self.data / name).read_bytes() for name in HEADERS}
        records = evidence._records(["bills.csv:5", "bills.csv:2", "bills.csv:5"], raw)
        self.assertEqual([r["fields"]["bill_id"] for r in records], ["SHARED", "A-BASE", "SHARED"])
        for pointers in ([], ["bills.csv:3"], ["bills.csv:999"], ["../bills.csv:5"],
                         ["bills.csv:05"], ["unknown.csv:2"], [None]):
            with self.subTest(pointers=pointers), self.assertRaises(ValueError):
                evidence._records(pointers, raw)

    def test_unknown_selector_refuses_without_source_or_output_changes(self):
        before = self.inputs()
        for choice in ({"kind": "exception"}, {"account": "B"}, {"key": "shared"}, {"code": "RATE_CHANGE"}):
            with self.subTest(choice=choice), self.assertRaisesRegex(ValueError, "expected one exact"):
                self.emit(**choice)
        self.assert_no_output()
        self.assertEqual(self.inputs(), before)

    def test_stale_report_refuses_before_output(self):
        self.bills[1]["usage"] = "125"
        self.write_csv("bills.csv", self.bills)
        before = self.inputs()
        result = self.cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn("report does not match", result.stderr)
        self.assert_no_output()
        self.assertEqual(self.inputs(), before)

    def test_tampered_and_duplicate_key_report_refuse(self):
        original = self.report.read_bytes()
        for raw in (original.replace(b'"flags": 2', b'"flags": 99'),
                    b'{"as_of":"2026-09-28","as_of":"2026-09-28"}'):
            with self.subTest(raw=raw[:50]):
                self.assertNotEqual(raw, original)
                self.report.write_bytes(raw)
                before = self.inputs()
                with self.assertRaises(ValueError):
                    self.emit()
                self.assert_no_output()
                self.assertEqual(self.inputs(), before)

    def test_malformed_and_duplicate_header_csv_refuse(self):
        path = self.data / "bills.csv"
        original = path.read_bytes()
        for raw in (original + b'"unclosed quote',
                    original.replace(b"bill_id,account_no,", b"bill_id,bill_id,")):
            with self.subTest(raw=raw[-30:]):
                path.write_bytes(raw)
                before = self.inputs()
                with self.assertRaises(ValueError):
                    self.emit()
                self.assert_no_output()
                self.assertEqual(self.inputs(), before)

    def test_synthetic_marker_is_bound_and_mode_is_explicit(self):
        marker = self.data / "expected.json"
        marker.write_text('{"as_of":"2026-09-28","eval_from":"2026-08-01"}', encoding="utf-8")
        self.regenerate()
        selected = self.emit()
        self.assertEqual(selected["review"]["data_mode"], "synthetic")
        item = selected["source"]["inputs"][-1]
        self.assertTrue(item["present"])
        self.assertEqual(item["sha256"], hashlib.sha256(marker.read_bytes()).hexdigest())

    def test_same_admitted_bytes_are_reproducible(self):
        self.emit("first.json")
        self.emit("second.json")
        self.assertEqual((self.root / "first.json").read_bytes(), (self.root / "second.json").read_bytes())

    def test_existing_source_report_symlink_and_hardlink_destinations_preserved(self):
        neighbor = self.root / "neighbor.json"
        neighbor.write_bytes(b"authored neighbor")
        symlink = self.root / "linked.json"
        symlink.symlink_to(neighbor)
        hardlink = self.root / "hardlink.json"
        os.link(self.data / "bills.csv", hardlink)
        dangling = self.root / "dangling.json"
        dangling.symlink_to(self.root / "absent")
        before = self.inputs()
        for target in (neighbor, symlink, hardlink, dangling, self.report,
                       self.data / "bills.csv", self.data / "expected.json",
                       self.report_dir / "payment_queue.csv"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                evidence.write_evidence(self.data, self.report, target, kind="flag",
                                        account="A", key="SHARED", code="USAGE_SPIKE")
        self.assertEqual(neighbor.read_bytes(), b"authored neighbor")
        self.assertTrue(symlink.is_symlink())
        self.assertTrue(dangling.is_symlink())
        self.assertEqual(self.inputs(), before)

    def test_missing_parent_is_not_created(self):
        with self.assertRaises(FileNotFoundError):
            self.emit("missing/evidence.json")
        self.assertFalse((self.root / "missing").exists())

    def test_input_symbolic_link_and_nonregular_file_refused(self):
        path = self.data / "bills.csv"
        stored = self.root / "stored-bills.csv"
        path.rename(stored)
        original = stored.read_bytes()
        path.symlink_to(stored)
        with self.assertRaisesRegex(ValueError, "regular file"):
            self.emit()
        self.assertTrue(path.is_symlink())
        self.assertEqual(stored.read_bytes(), original)
        path.unlink()
        if hasattr(os, "mkfifo"):
            os.mkfifo(path)
            with self.assertRaisesRegex(ValueError, "regular file"):
                self.emit()
        self.assert_no_output()

    def test_missing_input_refused_without_output(self):
        (self.data / "payments.csv").unlink()
        with self.assertRaises(FileNotFoundError):
            self.emit()
        self.assert_no_output()

    def test_input_change_after_validation_is_preserved_and_refused(self):
        original_current = review._current
        path = self.data / "bills.csv"
        new = path.read_bytes() + b"\r\n"
        def change(*args):
            result = original_current(*args)
            path.write_bytes(new)
            return result
        with patch.object(review, "_current", side_effect=change):
            with self.assertRaisesRegex(ValueError, "input changed"):
                self.emit()
        self.assertEqual(path.read_bytes(), new)
        self.assert_no_output()

    def test_same_bytes_replacement_is_refused_by_file_identity(self):
        original_current = review._current
        path = self.data / "payments.csv"
        raw = path.read_bytes()
        def change(*args):
            result = original_current(*args)
            replacement = self.root / "replacement.csv"
            replacement.write_bytes(raw)
            replacement.replace(path)
            return result
        with patch.object(review, "_current", side_effect=change):
            with self.assertRaisesRegex(ValueError, "input changed"):
                self.emit()
        self.assertEqual(path.read_bytes(), raw)
        self.assert_no_output()

    def test_same_bytes_replacement_directory_is_refused(self):
        original_current = review._current
        original = self.inputs()
        moved = self.root / "moved-data"
        def change(*args):
            result = original_current(*args)
            self.data.rename(moved)
            shutil.copytree(moved, self.data)
            return result
        with patch.object(review, "_current", side_effect=change):
            with self.assertRaisesRegex(ValueError, "directory changed"):
                self.emit()
        self.assertEqual(self.inputs(), original)
        self.assert_no_output()

    def test_marker_created_during_validation_refuses(self):
        original_current = review._current
        marker = self.data / "expected.json"
        def change(*args):
            result = original_current(*args)
            marker.write_bytes(b"{}")
            return result
        with patch.object(review, "_current", side_effect=change):
            with self.assertRaisesRegex(ValueError, "input changed"):
                self.emit()
        self.assertEqual(marker.read_bytes(), b"{}")
        self.assert_no_output()

    def test_change_after_staging_before_publication_refuses(self):
        actual_sync = os.fsync
        path = self.data / "payments.csv"
        changed = path.read_bytes() + b"\r\n"
        def stage(fd):
            actual_sync(fd)
            path.write_bytes(changed)
        with patch.object(evidence.os, "fsync", side_effect=stage):
            with self.assertRaisesRegex(ValueError, "input changed"):
                self.emit()
        self.assertEqual(path.read_bytes(), changed)
        self.assert_no_output()

    def test_failed_flush_does_not_publish_partial_json(self):
        before = self.inputs()
        with patch.object(evidence.os, "fsync", side_effect=OSError("injected sync failure")):
            with self.assertRaisesRegex(OSError, "sync failure"):
                self.emit()
        self.assert_no_output()
        self.assertEqual(self.inputs(), before)

    def test_raced_destination_is_preserved(self):
        actual_link = os.link
        target = self.root / "evidence.json"
        before = self.inputs()
        def race(source, destination):
            Path(destination).write_bytes(b"another writer owns this")
            return actual_link(source, destination)
        with patch.object(evidence.os, "link", side_effect=race):
            with self.assertRaises(FileExistsError):
                self.emit()
        self.assertEqual(target.read_bytes(), b"another writer owns this")
        self.assertEqual(list(self.root.glob(".uwatch-evidence-*")), [])
        self.assertEqual(self.inputs(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
