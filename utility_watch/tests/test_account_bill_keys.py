"""Account-local exported bill IDs must not transfer decisions between accounts."""
from datetime import date
import unittest

from uwatch.engine import Bill, check


AS_OF = date(2024, 2, 1)
EVAL_FROM = date(2024, 1, 1)


def account(key):
    return {"account_no": key, "property": "Fictional " + key, "utility": "electric",
            "vendor": "Fictional vendor", "scope": "common", "unit": "", "cycle": "monthly", "_row": 2}


def bill(key, acct, year, *, month=1, invoice=None, usage=300, amount=60, late_fee=0):
    return Bill(2, key, acct, invoice or f"INV-{acct}-{year}-{month}",
                date(year, month, 1), date(year, month, 28), usage, "kWh", amount,
                late_fee, 0, date(year, min(month + 1, 12), 15), date(year, month, 28))


def receive(accounts, bills, payments=()):
    for line, item in enumerate(bills, 2):
        item.row = line
    return check({key: account(key) for key in accounts}, bills, [], payments, AS_OF, EVAL_FROM)


def queue_keys(result):
    return {(row["account_no"], row["bill_id"]) for row in result[2]}


def finding_keys(result):
    return {(row.account_no, row.key, row.code) for row in result[0]}


class AccountBillKeyTests(unittest.TestCase):
    def test_flag_does_not_hold_same_id_on_another_account(self):
        for other in ("A", "Z"):
            with self.subTest(other_account=other):
                bills = [bill("OTHER-BASE", other, 2023), bill("B-BASE", "B", 2023),
                         bill("SHARED", other, 2024, late_fee=5), bill("SHARED", "B", 2024)]
                result = receive([other, "B"], bills)
                self.assertEqual(queue_keys(result), {("B", "SHARED")})
                self.assertEqual(finding_keys(result), {(other, "SHARED", "LATE_FEE_OR_PAST_DUE")})
                self.assertEqual(result[0][0].evidence, ["bills.csv:4"])

    def test_exception_does_not_hold_same_id_on_a_known_account(self):
        result = receive(["B"], [bill("B-BASE", "B", 2023),
                         bill("SHARED", "UNKNOWN", 2024), bill("SHARED", "B", 2024)])
        self.assertEqual(queue_keys(result), {("B", "SHARED")})
        self.assertEqual([(x["account_no"], x["key"], x["reason"], x["evidence"]) for x in result[1]],
                         [("UNKNOWN", "SHARED", "UNKNOWN_ACCOUNT", ["bills.csv:3"])])

    def test_duplicate_pair_stays_held_without_holding_other_account(self):
        for other in ("A", "Z"):
            for shared_member in ("first", "later"):
                with self.subTest(other_account=other, shared_member=shared_member):
                    first = "SHARED" if shared_member == "first" else "OTHER-FIRST"
                    later = "SHARED" if shared_member == "later" else "OTHER-LATER"
                    bills = [bill("OTHER-BASE", other, 2023), bill("B-BASE", "B", 2023),
                             bill(first, other, 2024, invoice="DUPLICATE"),
                             bill(later, other, 2024, invoice="DUPLICATE"), bill("SHARED", "B", 2024)]
                    result = receive([other, "B"], bills)
                    self.assertEqual(queue_keys(result), {("B", "SHARED")})
                    duplicate = [f for f in result[0] if f.code == "DUPLICATE_BILL"]
                    self.assertEqual([(f.account_no, f.key, f.evidence) for f in duplicate],
                                     [(other, later, ["bills.csv:5", "bills.csv:4"])])

    def test_other_account_duplicate_does_not_erase_prior_year_baseline(self):
        for other in ("A", "Z"):
            with self.subTest(other_account=other):
                bills = [bill("OTHER-BASE", other, 2023), bill("SHARED-HISTORY", "B", 2023),
                         bill("OTHER-FIRST", other, 2024, invoice="DUPLICATE"),
                         bill("SHARED-HISTORY", other, 2024, invoice="DUPLICATE"), bill("CURRENT", "B", 2024)]
                result = receive([other, "B"], bills)
                self.assertEqual(queue_keys(result), {("B", "CURRENT")})
                self.assertFalse([x for x in result[1] if x["account_no"] == "B"])

    def test_other_account_duplicate_does_not_erase_rate_history(self):
        history = [bill("B-BASE", "B", 2023)] + [
            bill("SHARED-HISTORY" if month == 8 else f"B-{month}", "B", 2023, month=month)
            for month in range(8, 13)]
        bills = [bill("A-BASE", "A", 2023), *history,
                 bill("A-FIRST", "A", 2024, invoice="DUPLICATE"),
                 bill("SHARED-HISTORY", "A", 2024, invoice="DUPLICATE"),
                 bill("B-CURRENT", "B", 2024, amount=120)]
        result = receive(["A", "B"], bills)
        self.assertIn(("B", "B-CURRENT", "RATE_CHANGE"), finding_keys(result))
        self.assertNotIn(("B", "B-CURRENT"), queue_keys(result))
        self.assertFalse([x for x in result[1] if x["account_no"] == "B"])

    def test_other_account_duplicate_does_not_erase_trailing_usage_history(self):
        history = [bill("B-BASE", "B", 2023, usage=900)] + [
            bill("SHARED-HISTORY" if month == 10 else f"B-{month}", "B", 2023, month=month, usage=100)
            for month in range(10, 13)]
        bills = [bill("A-BASE", "A", 2023), *history,
                 bill("A-FIRST", "A", 2024, invoice="DUPLICATE"),
                 bill("SHARED-HISTORY", "A", 2024, invoice="DUPLICATE"),
                 bill("B-CURRENT", "B", 2024, usage=900)]
        result = receive(["A", "B"], bills)
        self.assertEqual(result[3], ["B-CURRENT"])
        self.assertEqual(queue_keys(result), {("B", "B-CURRENT")})

    def test_two_clean_accounts_can_share_a_bill_id(self):
        bills = [bill("A-BASE", "A", 2023), bill("B-BASE", "B", 2023),
                 bill("SHARED", "A", 2024), bill("SHARED", "B", 2024)]
        result = receive(["A", "B"], bills)
        self.assertEqual(queue_keys(result), {("A", "SHARED"), ("B", "SHARED")})
        self.assertEqual(result[0:2], ([], []))

    def test_payments_keep_existing_account_and_invoice_identity(self):
        bills = [bill("A-BASE", "A", 2023), bill("B-BASE", "B", 2023),
                 bill("SHARED", "A", 2024, invoice="SAME-INVOICE"),
                 bill("SHARED", "B", 2024, invoice="SAME-INVOICE")]
        payments = [("A", "SAME-INVOICE", 60, AS_OF, 2)]
        result = receive(["A", "B"], bills, payments)
        self.assertEqual(queue_keys(result), {("B", "SHARED")})
        self.assertEqual(result[0:2], ([], []))


if __name__ == "__main__":
    unittest.main(verbosity=2)
