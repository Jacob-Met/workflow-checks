import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uwatch.engine import check, load, run  # noqa: E402
from uwatch.cli import main  # noqa: E402
from uwatch.synth import generate  # noqa: E402


ACCOUNT_HEADER = ["account_no", "property", "utility", "vendor", "scope", "unit", "cycle"]
BILL_HEADER = ["bill_id", "account_no", "vendor_invoice_no", "period_start", "period_end", "usage",
               "usage_unit", "amount", "late_fee", "prior_balance", "due_date", "received_date"]
OCCUPANCY_HEADER = ["property", "unit", "status", "from", "to"]
PAYMENT_HEADER = ["payment_id", "account_no", "vendor_invoice_no", "amount", "paid_date"]


def _write_csv(path, header, rows, encoding="utf-8"):
    with open(path, "w", newline="", encoding=encoding) as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)


def _data(tmp_path, bills, accounts=None, occupancy=None, payments=None):
    d = tmp_path / "client_data"
    d.mkdir()
    accounts = accounts or [{
        "account_no": "A1", "property": "One", "utility": "electric", "vendor": "Power",
        "scope": "common", "unit": "", "cycle": "monthly",
    }]
    _write_csv(d / "accounts.csv", ACCOUNT_HEADER, accounts)
    _write_csv(d / "bills.csv", BILL_HEADER, bills)
    _write_csv(d / "occupancy.csv", OCCUPANCY_HEADER, occupancy or [])
    _write_csv(d / "payments.csv", PAYMENT_HEADER, payments or [])
    return d


def _bill(bill_id, ps, pe, *, invoice=None, usage="300", unit="kWh", amount="60",
          late_fee="", prior_balance="", due="2024-04-01", received="2024-03-01",
          account="A1"):
    return {
        "bill_id": bill_id, "account_no": account, "vendor_invoice_no": invoice or f"INV-{bill_id}",
        "period_start": ps, "period_end": pe, "usage": usage, "usage_unit": unit, "amount": amount,
        "late_fee": late_fee, "prior_balance": prior_balance, "due_date": due,
        "received_date": received,
    }


def _check(d, as_of=date(2024, 3, 15), eval_from=date(2024, 1, 1)):
    return check(*load(d), as_of=as_of, eval_from=eval_from)


def _run(tmp_path, seed):
    d, o = tmp_path / f"d{seed}", tmp_path / f"o{seed}"
    exp = generate(d, seed=seed)
    s = run(d, o)
    got = {(f["key"], f["code"]) for f in s["flags_detail"]}
    return exp, s, got, d, o


@pytest.mark.parametrize("seed", [11, 3, 99, 2026])
def test_flags_equal_answer_key(tmp_path, seed):
    exp, s, got, _, _ = _run(tmp_path, seed)
    assert got == {tuple(x) for x in exp["flags"]}


@pytest.mark.parametrize("seed", [11, 7])
def test_seasonal_peaks_not_flagged_but_naive_rule_would(tmp_path, seed):
    exp, s, got, _, _ = _run(tmp_path, seed)
    flagged = {k for k, _ in got}
    assert not flagged & set(exp["decoys"])
    assert set(s["naive_trailing3_hits"]) & set(exp["decoys"]), "decoy set should trip the naive rule"


def test_every_anomaly_class_present(tmp_path):
    exp, s, got, _, _ = _run(tmp_path, 11)
    codes = {c for _, c in got}
    assert codes == {"USAGE_SPIKE", "RATE_CHANGE", "DUPLICATE_BILL", "LATE_FEE_OR_PAST_DUE", "MISSING_BILL",
                     "PERIOD_OVERLAP", "PAYMENT_MISMATCH", "UNPAID_PAST_DUE", "VACANT_UNIT_USAGE"}


def test_no_baseline_goes_to_exceptions_not_flags(tmp_path):
    exp, s, got, _, _ = _run(tmp_path, 11)
    exc = {x["key"] for x in s["exceptions_detail"] if x["reason"] == "NO_BASELINE"}
    assert exc == set(exp["insufficient_history"])
    assert not {k for k, _ in got} & exc


def test_payment_queue_is_clean_and_unpaid(tmp_path):
    exp, s, got, d, o = _run(tmp_path, 11)
    flagged = {k for k, _ in got}
    with open(o / "payment_queue.csv", encoding="utf-8") as f:
        q = list(csv.DictReader(f))
    assert q and all(r["bill_id"] not in flagged for r in q)
    assert all("not paid" in r["status"] for r in q)
    with open(d / "payments.csv", encoding="utf-8") as f:
        paid_inv = {(r["account_no"], r["vendor_invoice_no"]) for r in csv.DictReader(f)}
    assert all((r["account_no"], r["invoice"]) not in paid_inv for r in q)


def test_every_flag_has_evidence_pointer_and_audit(tmp_path):
    exp, s, got, d, o = _run(tmp_path, 11)
    assert all(f["evidence"] for f in s["flags_detail"])
    assert all(any(re.fullmatch(r".+\.csv:\d+", item) for item in f["evidence"])
               for f in s["flags_detail"])
    lines = (o / "audit.jsonl").read_text().splitlines()
    assert len(lines) == len(s["flags_detail"]) + len(s["exceptions_detail"]) + len(s["payment_queue_detail"])
    queued = [json.loads(line) for line in lines if json.loads(line)["decision"] == "payment_queue"]
    assert queued and all(re.fullmatch(r"bills\.csv:\d+", item["evidence"]) for item in queued)


def test_rerun_is_stable(tmp_path):
    exp, s1, got1, d, o = _run(tmp_path, 3)
    s2 = run(d, o)
    assert {(f["key"], f["code"]) for f in s2["flags_detail"]} == got1


def test_changed_input_spike_below_threshold_not_flagged(tmp_path):
    exp, s, got, d, o = _run(tmp_path, 11)
    spikes = [k for k, c in got if c == "USAGE_SPIKE"]
    rows = list(csv.DictReader(open(d / "bills.csv", encoding="utf-8")))
    for r in rows:
        if r["bill_id"] == spikes[0]:
            r["usage"] = str(round(float(r["usage"]) / 1.9, 2))
            r["amount"] = str(round(float(r["amount"]) / 1.9, 2))
    with open(d / "bills.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    s2 = run(d, tmp_path / "o2")
    assert (spikes[0], "USAGE_SPIKE") not in {(f["key"], f["code"]) for f in s2["flags_detail"]}


def test_report_is_self_contained(tmp_path):
    exp, s, got, d, o = _run(tmp_path, 11)
    h = (o / "report.html").read_text()
    assert "SYNTHETIC DATA" in h
    assert "<script" not in h and "http://" not in h and "https://" not in h


def test_utf8_bom_in_csv_headers_is_accepted(tmp_path):
    d = _data(tmp_path, [_bill("B1", "2024-01-01", "2024-01-31")])
    rows = list(csv.DictReader(open(d / "accounts.csv", encoding="utf-8")))
    _write_csv(d / "accounts.csv", ACCOUNT_HEADER, rows, encoding="utf-8-sig")
    accounts, bills, _, _ = load(d)
    assert set(accounts) == {"A1"}
    assert bills[0].account_no == "A1"


def test_export_formatted_numbers_are_accepted(tmp_path):
    d = _data(tmp_path, [_bill("B1", "2024-01-01", "2024-01-31", usage="1,234.50",
                               amount="$1,234.50", prior_balance="(25.00)")])
    _, bills, _, _ = load(d)
    assert bills[0].usage == 1234.50
    assert bills[0].amount == 1234.50
    assert bills[0].prior_balance == -25.0


def test_blank_export_rows_are_ignored_without_losing_evidence_line_numbers(tmp_path):
    d = _data(tmp_path, [_bill("B1", "2024-01-01", "2024-01-31")])
    with open(d / "bills.csv", "a", encoding="utf-8") as f:
        f.write(",,,,,,,,,,,\n\n")
    _, bills, _, _ = load(d)
    assert [(b.bill_id, b.row) for b in bills] == [("B1", 2)]


def test_common_us_export_dates_are_accepted(tmp_path):
    d = _data(tmp_path, [_bill("B1", "1/1/2024", "01/31/2024", due="3/31/2024",
                               received="2/5/2024")])
    _, bills, _, _ = load(d)
    assert bills[0].ps == date(2024, 1, 1)
    assert bills[0].due == date(2024, 3, 31)


def test_blank_invoice_numbers_do_not_make_unrelated_bills_duplicates(tmp_path):
    bills = [
        _bill("B1", "2023-01-01", "2023-01-31", invoice=""),
        _bill("B2", "2024-01-01", "2024-01-31", invoice="", amount="65"),
    ]
    for b in bills:
        b["vendor_invoice_no"] = ""
    flags, exceptions, queue, _ = _check(_data(tmp_path, bills))
    assert not [f for f in flags if f.code == "DUPLICATE_BILL"]
    assert {e["key"] for e in exceptions if e["reason"] == "MISSING_INVOICE"} == {"B2"}
    assert not queue


def test_duplicate_period_and_amount_with_different_ids_is_held(tmp_path):
    bills = [
        _bill("B1", "2024-01-01", "2024-01-31", invoice="INV-1"),
        _bill("B2", "2024-01-01", "2024-01-31", invoice="INV-2"),
    ]
    flags, _, queue, _ = _check(_data(tmp_path, bills))
    assert {(f.key, f.code) for f in flags if f.code == "DUPLICATE_BILL"} == {
        ("B2", "DUPLICATE_BILL")
    }
    assert all(q["bill_id"] != "B2" for q in queue)


def test_both_bills_in_a_duplicate_pair_are_withheld_from_payment_queue(tmp_path):
    bills = [
        _bill("BASE", "2023-01-01", "2023-01-31"),
        _bill("B1", "2024-01-01", "2024-01-31", invoice="INV-DUP", amount="65"),
        _bill("B2", "2024-01-01", "2024-01-31", invoice="INV-DUP", amount="65"),
    ]
    _, _, queue, _ = _check(_data(tmp_path, bills))
    assert not {"B1", "B2"} & {q["bill_id"] for q in queue}


def test_nested_periods_do_not_hide_a_later_overlap(tmp_path):
    bills = [
        _bill("B1", "2023-01-01", "2023-01-31"),
        _bill("B2", "2023-01-10", "2023-01-20", amount="61"),
        _bill("B3", "2023-01-25", "2023-02-10", amount="62"),
    ]
    flags, _, _, _ = _check(_data(tmp_path, bills), eval_from=date(2023, 1, 1))
    overlaps = {f.key for f in flags if f.code == "PERIOD_OVERLAP"}
    assert overlaps == {"B2", "B3"}


def test_service_month_uses_most_of_cross_boundary_period(tmp_path):
    bills = [
        _bill("B1", "2023-01-01", "2023-02-01", usage="320"),
        _bill("B2", "2024-01-01", "2024-02-01", usage="320"),
    ]
    flags, _, _, _ = _check(_data(tmp_path, bills))
    assert not [f for f in flags if f.code == "USAGE_SPIKE"]
    assert "A1:2024-01-01" not in {f.key for f in flags if f.code == "MISSING_BILL"}


def test_leap_year_baseline_compares_daily_usage(tmp_path):
    bills = [
        _bill("B1", "2023-02-01", "2023-02-28", usage="280"),
        _bill("B2", "2024-02-01", "2024-02-29", usage="290"),
    ]
    flags, _, _, _ = _check(_data(tmp_path, bills), eval_from=date(2024, 2, 1))
    assert not [f for f in flags if f.code == "USAGE_SPIKE"]


def test_zero_usage_baseline_does_not_create_infinite_spike(tmp_path):
    bills = [
        _bill("B1", "2023-01-01", "2023-01-31", usage="0", amount="25"),
        _bill("B2", "2024-01-01", "2024-01-31", usage="0", amount="25"),
    ]
    flags, exceptions, queue, _ = _check(_data(tmp_path, bills))
    assert not [f for f in flags if f.code == "USAGE_SPIKE"]
    assert {e["key"] for e in exceptions if e["reason"] == "ZERO_USAGE"} == {"B2"}
    assert not queue


def test_credit_bill_is_an_exception_and_never_queued_for_payment(tmp_path):
    bills = [_bill("B1", "2024-01-01", "2024-01-31", amount="-42.50")]
    _, exceptions, queue, _ = _check(_data(tmp_path, bills))
    assert {e["key"] for e in exceptions if e["reason"] == "CREDIT_OR_NEGATIVE_BILL"} == {"B1"}
    assert not queue


def test_zero_net_amount_due_is_not_treated_as_payable(tmp_path):
    bills = [_bill("B1", "2024-01-01", "2024-01-31", amount="50", prior_balance="-50")]
    _, exceptions, queue, _ = _check(_data(tmp_path, bills))
    assert {e["key"] for e in exceptions if e["reason"] == "CREDIT_OR_NEGATIVE_BILL"} == {"B1"}
    assert not queue


def test_negative_carried_balance_is_still_disclosed(tmp_path):
    bills = [_bill("B1", "2024-01-01", "2024-01-31", prior_balance="-10")]
    flags, _, _, _ = _check(_data(tmp_path, bills))
    assert ("B1", "LATE_FEE_OR_PAST_DUE") in {(f.key, f.code) for f in flags}


def test_exception_bill_is_not_also_put_in_payment_queue(tmp_path):
    bills = [_bill("B1", "2024-01-01", "2024-01-31")]
    _, exceptions, queue, _ = _check(_data(tmp_path, bills))
    assert {e["reason"] for e in exceptions} >= {"NO_BASELINE"}
    assert not queue


def test_unknown_account_does_not_crash_or_enter_payment_workflow(tmp_path):
    bills = [_bill("B1", "2024-01-01", "2024-01-31", account="UNKNOWN",
                   due="2024-02-15")]
    flags, exceptions, queue, _ = _check(_data(tmp_path, bills))
    assert not flags
    assert {e["reason"] for e in exceptions} == {"UNKNOWN_ACCOUNT"}
    assert not queue


def test_future_dated_payment_does_not_hide_a_past_due_bill(tmp_path):
    bills = [_bill("B1", "2024-01-01", "2024-01-31", due="2024-02-15")]
    payments = [{"payment_id": "P1", "account_no": "A1", "vendor_invoice_no": "INV-B1",
                 "amount": "60", "paid_date": "2024-03-20"}]
    flags, _, _, _ = _check(_data(tmp_path, bills, payments=payments), as_of=date(2024, 3, 15))
    assert ("B1", "UNPAID_PAST_DUE") in {(f.key, f.code) for f in flags}


def test_usage_unit_change_is_not_compared_as_if_units_match(tmp_path):
    bills = [
        _bill("B1", "2023-01-01", "2023-01-31", usage="31000", unit="kWh", amount="3100"),
        _bill("B2", "2024-01-01", "2024-01-31", usage="31", unit="MWh", amount="3100"),
    ]
    flags, exceptions, queue, _ = _check(_data(tmp_path, bills))
    assert not [f for f in flags if f.code in {"USAGE_SPIKE", "RATE_CHANGE"}]
    assert {e["key"] for e in exceptions if e["reason"] == "USAGE_UNIT_CHANGED"} == {"B2"}
    assert not queue


def test_partial_vacancy_does_not_label_whole_bill_as_vacant(tmp_path):
    accounts = [{
        "account_no": "A1", "property": "One", "utility": "water", "vendor": "Water",
        "scope": "unit", "unit": "101", "cycle": "monthly",
    }]
    bills = [_bill("B1", "2024-01-01", "2024-01-31", usage="100", unit="kgal")]
    occupancy = [{"property": "One", "unit": "101", "status": "vacant",
                  "from": "2024-01-15", "to": "2024-01-15"}]
    flags, exceptions, queue, _ = _check(_data(tmp_path, bills, accounts, occupancy))
    assert not [f for f in flags if f.code == "VACANT_UNIT_USAGE"]
    assert {e["key"] for e in exceptions if e["reason"] == "PARTIAL_VACANCY"} == {"B1"}
    assert not queue


def test_vacant_unit_without_a_standby_threshold_is_an_exception(tmp_path):
    accounts = [{
        "account_no": "A1", "property": "One", "utility": "gas", "vendor": "Gas",
        "scope": "unit", "unit": "101", "cycle": "monthly",
    }]
    bills = [_bill("B1", "2024-01-01", "2024-01-31", usage="10", unit="therm")]
    occupancy = [{"property": "One", "unit": "101", "status": "vacant",
                  "from": "2024-01-01", "to": "2024-01-31"}]
    _, exceptions, queue, _ = _check(_data(tmp_path, bills, accounts, occupancy))
    assert {e["key"] for e in exceptions if e["reason"] == "NO_STANDBY_THRESHOLD"} == {"B1"}
    assert not queue


def test_client_cli_supports_explicit_window_and_is_not_labeled_synthetic(tmp_path, capsys):
    d = _data(tmp_path, [_bill("B1", "2024-01-01", "2024-01-31")])
    out = tmp_path / "out"
    result = main(["run", "--data", str(d), "--out", str(out), "--as-of", "2024-03-15",
                   "--eval-from", "2024-01-01"])
    assert result == 0
    assert "[SYNTHETIC]" not in capsys.readouterr().out
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["eval_from"] == "2024-01-01"
    assert summary["data_mode"] == "client_csv"
    report = (out / "report.html").read_text(encoding="utf-8")
    assert "REVIEW ONLY" in report
    assert "SYNTHETIC DATA" not in report
