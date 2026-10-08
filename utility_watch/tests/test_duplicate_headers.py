"""Refuse ambiguous utility exports before replacing a previous review."""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from uwatch.engine import _rows


HEADERS = {
    "accounts": "account_no,property,utility,vendor,scope,unit,cycle".split(","),
    "bills": ("bill_id,account_no,vendor_invoice_no,period_start,period_end,usage,"
              "usage_unit,amount,late_fee,prior_balance,due_date,received_date").split(","),
    "occupancy": "property,unit,status,from,to".split(","),
    "payments": "payment_id,account_no,vendor_invoice_no,amount,paid_date".split(","),
}


def write_data(data):
    data.mkdir()
    records = {
        "accounts": [["SYN-A", "Synthetic One", "electric", "Fictional Power", "common", "", "monthly"]],
        "bills": [
            ["SYN-BASE", "SYN-A", "SYN-OLD", "2023-01-01", "2023-01-31", "300", "kWh",
             "60", "0", "0", "2023-03-01", "2023-02-01"],
            ["SYN-B", "SYN-A", "SYN-NEW", "2024-01-01", "2024-01-31", "300", "kWh",
             "60", "0", "0", "2024-04-01", "2024-02-01"],
        ],
        "occupancy": [],
        "payments": [],
    }
    for name, rows in records.items():
        with (data / (name + ".csv")).open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(HEADERS[name])
            writer.writerows(rows)


def run_cli(data, out):
    return subprocess.run(
        [sys.executable, "-m", "uwatch", "run", "--data", str(data), "--out", str(out),
         "--as-of", "2024-03-15", "--eval-from", "2024-01-01"],
        cwd=APP, capture_output=True, text=True, check=False,
    )


def files_in(directory):
    return {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}


class DuplicateHeaders(unittest.TestCase):
    def test_duplicate_required_names_refuse_even_without_records(self):
        with tempfile.TemporaryDirectory() as td:
            for name, headers in HEADERS.items():
                with self.subTest(table=name):
                    p = Path(td) / (name + ".csv")
                    p.write_text(",".join(headers + [headers[0]]) + "\n", encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "duplicate CSV column"):
                        list(_rows(p, headers))

    def test_duplicate_unused_and_empty_names_refuse(self):
        with tempfile.TemporaryDirectory() as td:
            for headers in ("id,note,note", "id,,", "id,note,other,note"):
                with self.subTest(headers=headers):
                    p = Path(td) / "authored.csv"
                    p.write_text(headers + "\n", encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "duplicate CSV column"):
                        list(_rows(p, ["id"]))

    def test_conflicting_amount_cells_are_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bills.csv"
            p.write_text("bill_id,amount,amount\nSYN-B,12.50,99.00\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "bills.csv.*duplicate CSV column") as error:
                list(_rows(p, ["bill_id", "amount"]))
            self.assertNotIn("12.50", str(error.exception))
            self.assertNotIn("99.00", str(error.exception))

    def test_each_cli_table_refuses_and_preserves_previous_review(self):
        for name, duplicate in (("accounts", "property"), ("bills", "amount"),
                                ("occupancy", "status"), ("payments", "amount")):
            with self.subTest(table=name), tempfile.TemporaryDirectory() as td:
                data, out = Path(td) / "authored input", Path(td) / "old review"
                write_data(data)
                initial = run_cli(data, out)
                self.assertEqual(initial.returncode, 0, initial.stderr)
                summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
                self.assertEqual([(q["bill_id"], q["amount_due"])
                                  for q in summary["payment_queue_detail"]], [("SYN-B", 60.0)])
                previous = files_in(out)
                path = data / (name + ".csv")
                with path.open(newline="", encoding="utf-8") as f:
                    rows = list(csv.reader(f))
                column = rows[0].index(duplicate)
                for row in rows:
                    row.append(row[column])
                if name == "bills":
                    rows[-1][-1] = "99.00"
                with path.open("w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerows(rows)
                inputs = files_in(data)
                result = run_cli(data, out)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn(name + ".csv", result.stderr)
                self.assertIn("duplicate CSV column", result.stderr)
                self.assertNotIn("queued for approval", result.stdout)
                self.assertEqual(files_in(out), previous)
                self.assertEqual(files_in(data), inputs)

    def test_bom_reordered_unique_extra_and_multiline_values_are_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "authored.csv"
            p.write_bytes(b'\xef\xbb\xbfextra,amount,id,Amount\r\n"a, b\r\nc", 12.50 , SYN-B ,unused\r\n')
            self.assertEqual(list(_rows(p, ["id", "amount"])), [
                (3, {"extra": "a, b\r\nc", "amount": "12.50", "id": "SYN-B", "Amount": "unused"})
            ])

    def test_missing_required_column_keeps_precedence(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "authored.csv"
            p.write_text("id,id\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing required column.*amount"):
                list(_rows(p, ["id", "amount"]))

    def test_unique_header_extra_cells_and_blank_rows_keep_existing_behavior(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "authored.csv"
            p.write_text("id,amount\n,\nSYN-B,12.50\n", encoding="utf-8")
            self.assertEqual(list(_rows(p, ["id", "amount"])), [(3, {"id": "SYN-B", "amount": "12.50"})])
            p.write_text("id,amount\nSYN-B,12.50,99.00\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "authored.csv:2: too many CSV columns"):
                list(_rows(p, ["id", "amount"]))


if __name__ == "__main__":
    unittest.main()
