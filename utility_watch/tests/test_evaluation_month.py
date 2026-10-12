"""Exercise evaluation-month admission through the actual CLI and public engine."""
import copy
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from uwatch.engine import check, load, run  # noqa: E402


def write_data(data):
    data.mkdir()
    tables = {
        "accounts": [
            ["account_no", "property", "utility", "vendor", "scope", "unit", "cycle"],
            ["A1", "Synthetic Court", "electric", "Fictional Power", "common", "", "monthly"],
        ],
        "bills": [
            ["bill_id", "account_no", "vendor_invoice_no", "period_start", "period_end", "usage",
             "usage_unit", "amount", "late_fee", "prior_balance", "due_date", "received_date"],
            ["BASE", "A1", "INV-BASE", "2023-01-01", "2023-01-31", "300", "kWh", "60",
             "0", "0", "2023-03-01", "2023-02-01"],
            ["B1", "A1", "INV-B1", "2024-01-01", "2024-01-31", "300", "kWh", "60",
             "0", "0", "2024-04-01", "2024-02-01"],
        ],
        "occupancy": [["property", "unit", "status", "from", "to"]],
        "payments": [["payment_id", "account_no", "vendor_invoice_no", "amount", "paid_date"]],
    }
    for name, rows in tables.items():
        with (data / f"{name}.csv").open("w", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerows(rows)


def snapshot(path):
    return {p.relative_to(path).as_posix(): p.read_bytes()
            for p in path.rglob("*") if p.is_file()}


class EvaluationMonthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "input"
        self.out = self.root / "review"
        write_data(self.data)

    def command(self, out=None, eval_from="2024-01-01"):
        args = [sys.executable, "-m", "uwatch", "run", "--data", str(self.data),
                "--out", str(out or self.out), "--as-of", "2024-03-15"]
        if eval_from is not None:
            args.extend(["--eval-from", eval_from])
        return subprocess.run(args, cwd=APP, capture_output=True, text=True, timeout=15)

    def assert_refused(self, result):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("eval_from", result.stderr)
        self.assertIn("first day of a month", result.stderr)
        self.assertIn("YYYY-MM-01", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_cli_refuses_non_month_starts_and_preserves_prior_report_and_inputs(self):
        valid = self.command()
        self.assertEqual(valid.returncode, 0, valid.stderr)
        prior, source = snapshot(self.out), snapshot(self.data)
        for value in ("2024-01-02", "2024-01-31", "2024-02-29", "2024-12-31"):
            with self.subTest(value=value):
                self.assert_refused(self.command(eval_from=value))
                self.assertEqual(snapshot(self.out), prior)
                self.assertEqual(snapshot(self.data), source)

    def test_cli_refuses_before_creating_a_new_output_directory(self):
        target = self.root / "new-parent" / "review"
        self.assert_refused(self.command(target, "2024-01-02"))
        self.assertFalse(target.parent.exists())

    def test_run_refuses_non_month_start_before_reading_csv_or_creating_output(self):
        missing_data = self.root / "missing-input"
        target = self.root / "new-parent" / "review"
        with self.assertRaisesRegex(ValueError, "first day of a month"):
            run(missing_data, target, date(2024, 3, 15), eval_from=date(2024, 1, 2))
        self.assertFalse(target.parent.exists())
        self.assertFalse(missing_data.exists())

    def test_check_refuses_non_month_start_without_mutating_loaded_data(self):
        inputs = load(self.data)
        prior = copy.deepcopy(inputs)
        with self.assertRaisesRegex(ValueError, "first day of a month"):
            check(*inputs, as_of=date(2024, 3, 15), eval_from=date(2024, 1, 2))
        self.assertEqual(inputs, prior)

    def test_all_twelve_month_starts_remain_valid_for_direct_checks(self):
        for month in range(1, 13):
            with self.subTest(month=month):
                self.assertEqual(check({}, [], [], [], date(2024, 12, 31), date(2024, month, 1)),
                                 ([], [], [], []))

    def test_first_of_month_keeps_expected_bill_and_missing_month(self):
        result = self.command()
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((self.out / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["eval_from"], "2024-01-01")
        self.assertEqual([(q["bill_id"], q["amount_due"]) for q in summary["payment_queue_detail"]],
                         [("B1", 60.0)])
        self.assertEqual([(f["key"], f["code"]) for f in summary["flags_detail"]],
                         [("A1:2024-02-01", "MISSING_BILL")])
        self.assertEqual(set(snapshot(self.out)), {"flags.csv", "exceptions.csv", "payment_queue.csv",
                                                   "audit.jsonl", "summary.json", "report.html"})

    def test_invalid_effective_synthetic_metadata_is_refused_without_output(self):
        (self.data / "expected.json").write_text(
            json.dumps({"as_of": "2024-03-15", "eval_from": "2024-01-02"}), encoding="utf-8")
        source = snapshot(self.data)
        self.assert_refused(self.command(eval_from=None))
        self.assertFalse(self.out.exists())
        self.assertEqual(snapshot(self.data), source)

    def test_valid_explicit_date_still_overrides_invalid_metadata_date(self):
        (self.data / "expected.json").write_text(
            json.dumps({"as_of": "2024-03-15", "eval_from": "2024-01-02"}), encoding="utf-8")
        result = self.command()
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((self.out / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["eval_from"], "2024-01-01")
        self.assertEqual(summary["payment_queue_total"], 60.0)

    def test_valid_metadata_and_explicit_month_produce_identical_outputs(self):
        (self.data / "expected.json").write_text(
            json.dumps({"as_of": "2024-03-15", "eval_from": "2024-01-01"}), encoding="utf-8")
        explicit = self.command()
        automatic_out = self.root / "automatic"
        automatic = self.command(automatic_out, eval_from=None)
        self.assertEqual(explicit.returncode, 0, explicit.stderr)
        self.assertEqual(automatic.returncode, 0, automatic.stderr)
        self.assertEqual(snapshot(self.out), snapshot(automatic_out))

    def test_default_evaluation_window_remains_six_months_earlier(self):
        result = self.command(eval_from=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((self.out / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["eval_from"], "2023-09-01")


if __name__ == "__main__":
    unittest.main()
