"""Independent day-count oracle and actual CLI service-month receiving."""
import collections
import json
import random
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uwatch.engine import Bill


def bill(start, end):
    return Bill(2, "B-MONTH", "A-MONTH", "INV-MONTH", start, end,
                60.0, "kWh", 60.0, 0.0, 0.0, date(2026, 11, 1),
                date(2026, 10, 1))


def counted_month(start, end):
    """Count each actual civil day; no month-step or month-length shortcut."""
    counts = collections.Counter()
    for ordinal in range(start.toordinal(), end.toordinal() + 1):
        day = date.fromordinal(ordinal)
        counts[date(day.year, day.month, 1)] += 1
    return max(counts, key=lambda month: (counts[month], month))


class ServiceMonthTests(unittest.TestCase):
    def test_all_days_in_a_month_including_date_limits(self):
        for start, end, expected in [
            (date.min, date.min, date(1, 1, 1)),
            (date(2024, 2, 1), date(2024, 2, 29), date(2024, 2, 1)),
            (date(9999, 12, 1), date.max, date(9999, 12, 1)),
            (date.max, date.max, date(9999, 12, 1)),
        ]:
            with self.subTest(start=start, end=end):
                self.assertEqual(bill(start, end).month, expected)

    def test_endpoint_and_interior_ties_keep_latest_month(self):
        for start, end, expected in [
            (date(2026, 1, 17), date(2026, 2, 15), date(2026, 2, 1)),
            (date(2026, 1, 16), date(2026, 2, 15), date(2026, 1, 1)),
            (date(2026, 1, 1), date(2026, 3, 30), date(2026, 1, 1)),
            (date(2026, 1, 2), date(2026, 3, 30), date(2026, 3, 1)),
            (date(2026, 1, 1), date(2026, 4, 1), date(2026, 3, 1)),
            (date(2026, 1, 1), date(2026, 5, 31), date(2026, 5, 1)),
            (date(2025, 12, 1), date(2026, 3, 1), date(2026, 1, 1)),
        ]:
            with self.subTest(start=start, end=end):
                self.assertEqual(bill(start, end).month, expected)
                self.assertEqual(expected, counted_month(start, end))

    def test_day_oracle_across_every_month_and_leap_centuries(self):
        for year in (1, 4, 100, 400, 1900, 2000, 2024, 2100, 2400, 9998):
            for month in range(1, 13):
                for start_day in (1, 15, 28):
                    start = date(year, month, start_day)
                    for duration in (1, 14, 29, 30, 31, 60, 92, 370):
                        end = date.fromordinal(min(start.toordinal() + duration - 1,
                                                   date.max.toordinal()))
                        with self.subTest(start=start, end=end):
                            self.assertEqual(bill(start, end).month,
                                             counted_month(start, end))

    def test_day_oracle_on_seeded_longer_periods(self):
        randomizer = random.Random(830526)
        for _ in range(500):
            start = date.fromordinal(randomizer.randint(1, date.max.toordinal() - 1500))
            end = start + timedelta(days=randomizer.randrange(1500))
            with self.subTest(start=start, end=end):
                self.assertEqual(bill(start, end).month, counted_month(start, end))

    def test_full_supported_range_and_final_partial_month(self):
        self.assertEqual(bill(date.min, date.max).month, date(9999, 12, 1))
        self.assertEqual(bill(date.min, date(9999, 12, 30)).month, date(9999, 10, 1))
        self.assertEqual(bill(date.min, date(9999, 3, 1)).month, date(9999, 1, 1))

    def test_recomputed_after_mutation_and_reversed_period_refused(self):
        current = bill(date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(current.month, date(2026, 1, 1))
        current.pe = date(2026, 3, 31)
        self.assertEqual(current.month, date(2026, 3, 1))
        current.ps = date(2026, 4, 1)
        with self.assertRaises(ValueError):
            _ = current.month

    def test_actual_cli_accepts_final_supported_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data, output = root / "input", root / "output"
            data.mkdir()
            files = {
                "accounts.csv": "account_no,property,utility,vendor,scope,unit,cycle\n"
                                "A-MONTH,Fictional House,electric,Fictional Vendor,common,,monthly\n",
                "bills.csv": "bill_id,account_no,vendor_invoice_no,period_start,period_end,usage,usage_unit,amount,late_fee,prior_balance,due_date,received_date\n"
                             "B-MONTH,A-MONTH,INV-MONTH,9999-12-01,9999-12-31,60,kWh,60,0,0,9999-12-31,9999-12-31\n",
                "occupancy.csv": "property,unit,status,from,to\n",
                "payments.csv": "payment_id,account_no,vendor_invoice_no,amount,paid_date\n",
            }
            for name, content in files.items():
                (data / name).write_text(content, encoding="utf-8")
            before = {name: (data / name).read_bytes() for name in files}
            result = subprocess.run(
                [sys.executable, "-m", "uwatch", "run", "--data", str(data),
                 "--out", str(output), "--as-of", "2026-10-12",
                 "--eval-from", "2026-01-01"],
                cwd=Path(__file__).resolve().parents[1], capture_output=True,
                text=True, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["bills"], 1)
            self.assertEqual(summary["payment_queue"], 0)
            self.assertEqual(summary["exceptions_detail"][0]["reason"], "NO_BASELINE")
            self.assertEqual({name: (data / name).read_bytes() for name in files}, before)
            self.assertEqual({p.name for p in output.iterdir()},
                             {"flags.csv", "exceptions.csv", "payment_queue.csv",
                              "audit.jsonl", "summary.json", "report.html"})


if __name__ == "__main__":
    unittest.main()
