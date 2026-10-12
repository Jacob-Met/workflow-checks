"""A review reuses derived values only for its current, distinct bill records."""
from collections import Counter
from datetime import date
from pathlib import Path
import unittest
from unittest.mock import patch

from uwatch.engine import Bill, check, load


AS_OF = date(2026, 2, 1)
EVAL_FROM = date(2026, 1, 1)


def account():
    return {"account_no": "A", "property": "Fictional building", "utility": "electric",
            "vendor": "Fictional utility", "scope": "common", "unit": "",
            "cycle": "monthly", "_row": 2}


def bill(year, row, *, key="SHARED", unit="kWh"):
    return Bill(row, key, "A", f"INV-{row}", date(year, 1, 1), date(year, 1, 31),
                310, unit, 60, 0, 0, date(year, 2, 15), date(year, 1, 31))


class DerivedValueTests(unittest.TestCase):
    def test_shipped_sample_derives_each_known_record_once(self):
        data = Path(__file__).resolve().parents[1] / "sample_data"
        accounts, bills, occupancy, payments = load(data)
        calls = Counter()
        original = Bill.month.fget

        def observed(record):
            calls[id(record)] += 1
            return original(record)

        with patch.object(Bill, "month", property(observed)):
            flags, exceptions, queue, naive = check(
                accounts, bills, occupancy, payments, date(2026, 9, 28), date(2026, 3, 1))
        self.assertEqual(len(flags), 12)
        self.assertEqual(len(exceptions), 2)
        self.assertEqual(len(queue), 12)
        self.assertEqual(set(calls), {id(b) for b in bills if b.account_no in accounts})
        self.assertEqual(set(calls.values()), {1})

    def test_repeated_exported_id_does_not_merge_different_service_periods(self):
        history, current = bill(2025, 2), bill(2026, 3)
        flags, exceptions, queue, _ = check({"A": account()}, [current, history], [], [], AS_OF, EVAL_FROM)
        self.assertEqual((flags, exceptions), ([], []))
        self.assertEqual([(q["bill_id"], q["evidence"]) for q in queue], [("SHARED", "bills.csv:3")])

    def test_next_review_uses_edited_period_and_unit_without_stale_results(self):
        history, current = bill(2025, 2), bill(2026, 3)
        bills = [history, current]

        def review():
            return check({"A": account()}, bills, [], [], AS_OF, EVAL_FROM)

        self.assertEqual(len(review()[2]), 1)
        history.ps, history.pe = date(2025, 2, 1), date(2025, 2, 28)
        changed_period = review()
        self.assertEqual([e["reason"] for e in changed_period[1]], ["NO_BASELINE"])
        self.assertEqual(changed_period[2], [])
        history.ps, history.pe = date(2025, 1, 1), date(2025, 1, 31)
        current.unit = "kgal"
        changed_unit = review()
        self.assertEqual([e["reason"] for e in changed_unit[1]], ["USAGE_UNIT_CHANGED"])
        self.assertEqual(changed_unit[2], [])
        current.unit = "K W h"
        before = [vars(b).copy() for b in bills]
        recovered = review()
        self.assertEqual((recovered[0], recovered[1]), ([], []))
        self.assertEqual(len(recovered[2]), 1)
        self.assertEqual([vars(b) for b in bills], before)

    def test_unknown_account_remains_an_exception_without_deriving_its_month(self):
        class UnknownBill(Bill):
            @property
            def month(self):
                raise AssertionError("unknown-account service periods are not evaluated")

        unknown = UnknownBill(**vars(bill(2026, 2)))
        flags, exceptions, queue, naive = check({}, [unknown], [], [], AS_OF, EVAL_FROM)
        self.assertEqual((flags, queue, naive), ([], [], []))
        self.assertEqual(exceptions, [{"key": "SHARED", "account_no": "A",
                                     "reason": "UNKNOWN_ACCOUNT", "evidence": ["bills.csv:2"]}])


if __name__ == "__main__":
    unittest.main()
