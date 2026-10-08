"""Refuse ambiguous account records before an existing Utility Watch report changes."""
from __future__ import annotations

import csv
from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from uwatch.engine import load, run

ACCOUNT_FIELDS = ["account_no", "property", "utility", "vendor", "scope", "unit", "cycle"]
BILL_FIELDS = ["bill_id", "account_no", "vendor_invoice_no", "period_start", "period_end",
               "usage", "usage_unit", "amount", "late_fee", "prior_balance", "due_date", "received_date"]
HEADERS = {"accounts": ACCOUNT_FIELDS, "bills": BILL_FIELDS,
           "occupancy": ["property", "unit", "status", "from", "to"],
           "payments": ["payment_id", "account_no", "vendor_invoice_no", "amount", "paid_date"]}
AS_OF = date(2024, 2, 1)
EVAL_FROM = date(2024, 1, 1)


def account(key="A1", property_name="Original property"):
    return dict(account_no=key, property=property_name, utility="electric", vendor="Original vendor",
                scope="common", unit="", cycle="irregular")


def bill(key="A1", year=2024):
    return dict(bill_id="SHARED-" + str(year), account_no=key,
                vendor_invoice_no="INVOICE-" + str(year), period_start=f"{year}-01-01",
                period_end=f"{year}-01-31", usage="310", usage_unit="kWh", amount="60",
                late_fee="", prior_balance="", due_date="2024-03-01", received_date=f"{year}-01-31")


def write_csv(path, fields, rows, encoding="utf-8"):
    with path.open("w", encoding=encoding, newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def fixture(root, accounts=None):
    data = root / "data"
    data.mkdir()
    supplied = accounts if accounts is not None else [account()]
    write_csv(data / "accounts.csv", ACCOUNT_FIELDS, supplied)
    keys = list(dict.fromkeys(row["account_no"].strip() for row in supplied if row["account_no"].strip()))
    write_csv(data / "bills.csv", BILL_FIELDS, [bill(k, y) for k in keys for y in (2023, 2024)])
    for name in ("occupancy", "payments"):
        write_csv(data / (name + ".csv"), HEADERS[name], [])
    return data


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def cli(data, out):
    return subprocess.run(
        [sys.executable, "-B", "-m", "uwatch", "run", "--data", str(data), "--out", str(out),
         "--as-of", AS_OF.isoformat(), "--eval-from", EVAL_FROM.isoformat()],
        cwd=PACKAGE, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        capture_output=True, text=True, timeout=15,
    )


class AccountIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="uwatch account identity ")
        self.root = Path(self.temporary.name)
        self.data = fixture(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def assert_duplicate(self, *, later=3, earlier=2):
        before = snapshot(self.data)
        with self.assertRaises(ValueError) as caught:
            load(self.data)
        message = str(caught.exception)
        self.assertIn("duplicate account_no", message)
        self.assertIn(f"accounts.csv:{later}", message)
        self.assertIn(f"accounts.csv:{earlier}", message)
        self.assertNotIn("Replacement property", message)
        self.assertEqual(snapshot(self.data), before)

    def test_cli_conflicting_duplicate_preserves_previous_outputs(self):
        output = self.root / "out"
        initial = cli(self.data, output)
        self.assertEqual(initial.returncode, 0, initial.stderr)
        before_output = snapshot(output)
        replacement = account(property_name="Replacement property")
        replacement["vendor"] = "Replacement vendor"
        write_csv(self.data / "accounts.csv", ACCOUNT_FIELDS, [account(), replacement])
        before_input = snapshot(self.data)
        repeated = cli(self.data, output)
        self.assertEqual(repeated.returncode, 2, repeated.stdout + repeated.stderr)
        self.assertIn("duplicate account_no", repeated.stderr)
        self.assertIn("accounts.csv:2", repeated.stderr)
        self.assertIn("accounts.csv:3", repeated.stderr)
        self.assertNotIn("report:", repeated.stdout)
        self.assertEqual(snapshot(output), before_output)
        self.assertEqual(snapshot(self.data), before_input)

    def test_identical_duplicate_is_still_ambiguous(self):
        write_csv(self.data / "accounts.csv", ACCOUNT_FIELDS, [account(), account()])
        self.assert_duplicate()

    def test_whitespace_normalized_duplicate_is_rejected(self):
        write_csv(self.data / "accounts.csv", ACCOUNT_FIELDS, [account(" A1 "), account("\tA1  ")])
        self.assert_duplicate()

    def test_bom_reordered_multiline_records_report_physical_rows(self):
        fields = list(reversed(ACCOUNT_FIELDS))
        write_csv(self.data / "accounts.csv", fields,
                  [account(property_name="Original\nproperty"), account(property_name="Replacement property")],
                  encoding="utf-8-sig")
        self.assert_duplicate(later=4, earlier=3)

    def test_blank_account_keeps_existing_required_error(self):
        for key in ("", " \t "):
            with self.subTest(key=repr(key)):
                write_csv(self.data / "accounts.csv", ACCOUNT_FIELDS, [account(), account(key)])
                before = snapshot(self.data)
                with self.assertRaisesRegex(ValueError, "account_no is blank"):
                    load(self.data)
                self.assertEqual(snapshot(self.data), before)

    def test_empty_rows_do_not_create_duplicate_accounts(self):
        empty = dict.fromkeys(ACCOUNT_FIELDS, "")
        write_csv(self.data / "accounts.csv", ACCOUNT_FIELDS, [empty, account(), empty])
        accounts, _, _, _ = load(self.data)
        self.assertEqual(list(accounts), ["A1"])
        self.assertEqual(accounts["A1"]["_row"], 3)

    def test_distinct_case_and_shared_bill_ids_keep_existing_behavior(self):
        other_root = self.root / "case"
        other_root.mkdir()
        data = fixture(other_root, [account("A1"), account("a1", "Other property")])
        original = snapshot(data)
        summary = run(data, other_root / "out", AS_OF, eval_from=EVAL_FROM)
        self.assertEqual(summary["accounts"], 2)
        self.assertEqual({(r["account_no"], r["bill_id"]) for r in summary["payment_queue_detail"]},
                         {("A1", "SHARED-2024"), ("a1", "SHARED-2024")})
        self.assertEqual(snapshot(data), original)

    def test_single_trimmed_account_retains_normalized_identity(self):
        write_csv(self.data / "accounts.csv", ACCOUNT_FIELDS, [account(" A1 ")])
        accounts, _, _, _ = load(self.data)
        self.assertEqual(list(accounts), ["A1"])
        self.assertEqual(accounts["A1"]["account_no"], "A1")

    def test_missing_column_keeps_reader_error(self):
        write_csv(self.data / "accounts.csv", ["property"], [{"property": "First"}, {"property": "Second"}])
        with self.assertRaisesRegex(ValueError, "missing required column"):
            load(self.data)


if __name__ == "__main__":
    unittest.main()
