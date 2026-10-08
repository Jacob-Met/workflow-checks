"""Review custody controls through real native exports, reports and CLI calls."""
import csv
import hashlib
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from uwatch import engine, review  # noqa: E402

HEADERS = {
    "accounts.csv": "account_no,property,utility,vendor,scope,unit,cycle".split(","),
    "bills.csv": ("bill_id,account_no,vendor_invoice_no,period_start,period_end,usage,"
                  "usage_unit,amount,late_fee,prior_balance,due_date,received_date").split(","),
    "occupancy.csv": "property,unit,status,from,to".split(","),
    "payments.csv": "payment_id,account_no,vendor_invoice_no,amount,paid_date".split(","),
}
AS_OF, EVAL_FROM = date(2024, 2, 5), date(2024, 1, 1)


def write_csv(path, rows, columns=None):
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def bill(account, year, **changes):
    row = dict(zip(HEADERS["bills.csv"], [
        f"{account}-{year}", account, f"INV-{account}-{year}", f"{year}-01-01", f"{year}-01-31",
        "300", "kWh", "60", "5" if year == 2024 and account != "C" else "0", "0",
        "2024-03-01", "2024-02-01",
    ]))
    row.update(changes)
    return row


def prepare(tmp_path):
    data, out = tmp_path / "data", tmp_path / "report"
    data.mkdir()
    accounts = [dict(zip(HEADERS["accounts.csv"], [a, f"Property {a}", "electric", "Vendor",
                                                 "common", "", "irregular"])) for a in "ABC"]
    for name, rows in {
        "accounts.csv": accounts,
        "bills.csv": [bill(a, y) for a in "ABC" for y in (2023, 2024)],
        "occupancy.csv": [], "payments.csv": [],
    }.items():
        write_csv(data / name, rows, HEADERS[name])
    engine.run(data, out, AS_OF, eval_from=EVAL_FROM)
    first = tmp_path / "review-1.csv"
    review.reconcile(data, out / "summary.json", first)
    return data, out, first


def mark(path, account="A", status="reviewed", note="Checked against vendor statement."):
    rows = read_csv(path)
    for row in rows:
        if row["row_state"] == "current" and row["account_no"] == account:
            row.update(review_status=status, reviewer="AP reviewer", note=note)
    write_csv(path, rows)
    return rows


def current(path):
    return {r["account_no"]: r for r in read_csv(path) if r["row_state"] == "current"}


def snapshots(*directories):
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for directory in directories for p in directory.iterdir() if p.is_file()}


def cli(*args):
    return subprocess.run([sys.executable, "-B", "-m", "uwatch", *map(str, args)],
                          cwd=PACKAGE, capture_output=True, text=True)


def test_actual_cli_generate_run_review_edit_reconcile_keeps_queue_and_literal_notes(tmp_path):
    data, out = tmp_path / "synthetic", tmp_path / "out"
    generated = cli("generate", "--out", data, "--seed", 11)
    assert generated.returncode == 0, generated.stderr
    checked = cli("run", "--data", data, "--out", out)
    assert checked.returncode == 0, checked.stderr
    report = json.loads((out / "summary.json").read_text())
    assert report["payment_queue"] > 0
    before = snapshots(data, out)
    first, second = tmp_path / "review.csv", tmp_path / "review-next.csv"
    exported = cli("review", "--data", data, "--report", out / "summary.json", "--out", first)
    assert exported.returncode == 0, exported.stderr
    rows = read_csv(first)
    note = '  Owner: Zoë 李\nInvoice says "hold, reconcile"; =literal text  '
    rows[0].update(review_status="in_progress", reviewer="  Zoë 李  ", note=note)
    target_id = rows[0]["row_id"]
    # Column and row order may change during a legitimate edit.
    write_csv(first, list(reversed(rows)), list(reversed(review.COLUMNS)))
    prior_bytes = first.read_bytes()
    result = cli("review", "--data", data, "--report", out / "summary.json",
                 "--previous", first, "--out", second)
    assert result.returncode == 0, result.stderr
    assert "annotations do not change payment eligibility" in result.stdout
    kept = next(r for r in read_csv(second) if r["row_id"] == target_id)
    assert (kept["review_status"], kept["reviewer"], kept["note"]) == ("in_progress", "  Zoë 李  ", note)
    assert len([r for r in read_csv(second) if r["row_state"] == "current"]) == report["flags"] + report["exceptions"]
    assert first.read_bytes() == prior_bytes
    assert snapshots(data, out) == before


def test_changed_source_without_regenerated_report_refuses_before_output(tmp_path):
    data, out, first = prepare(tmp_path)
    bills = read_csv(data / "bills.csv")
    bills[1]["late_fee"] = "8"
    write_csv(data / "bills.csv", bills)
    before = snapshots(data, out, tmp_path)
    destination = tmp_path / "must-not-exist" / "review.csv"
    result = cli("review", "--data", data, "--report", out / "summary.json",
                 "--previous", first, "--out", destination)
    assert result.returncode == 2
    assert "report does not match" in result.stderr
    assert not destination.parent.exists()
    assert snapshots(data, out, tmp_path) == before


def test_changed_missing_and_returning_facts_never_resurrect_notes(tmp_path):
    data, out, first = prepare(tmp_path)
    mark(first)
    mark(first, "B", note="Unrelated account already checked.")
    original = current(first)
    bills = read_csv(data / "bills.csv")
    bills[1]["late_fee"] = "8"
    write_csv(data / "bills.csv", bills)
    engine.run(data, out, AS_OF, eval_from=EVAL_FROM)
    changed = tmp_path / "changed.csv"
    review.reconcile(data, out / "summary.json", changed, first)
    rows = read_csv(changed)
    prior = next(r for r in rows if r["row_id"] == original["A"]["row_id"])
    assert (prior["row_state"], prior["review_status"], prior["note"]) == (
        "changed", "reviewed", "Checked against vendor statement.")
    assert current(changed)["A"]["review_status"] == "open"
    assert current(changed)["B"]["row_id"] == original["B"]["row_id"]
    assert current(changed)["B"]["review_status"] == "reviewed"
    mark(changed, note="Rechecked the new eight-dollar fee.")
    newer_id = current(changed)["A"]["row_id"]
    bills[1]["late_fee"] = "0"
    write_csv(data / "bills.csv", bills)
    engine.run(data, out, AS_OF, eval_from=EVAL_FROM)
    absent = tmp_path / "absent.csv"
    review.reconcile(data, out / "summary.json", absent, changed)
    assert "A" not in current(absent)
    assert next(r for r in read_csv(absent) if r["row_id"] == newer_id)["row_state"] == "absent"
    bills[1]["late_fee"] = "5"
    write_csv(data / "bills.csv", bills)
    engine.run(data, out, AS_OF, eval_from=EVAL_FROM)
    returned = tmp_path / "returned.csv"
    review.reconcile(data, out / "summary.json", returned, absent)
    new = current(returned)["A"]
    assert new["evidence_version"] == original["A"]["evidence_version"]
    assert new["row_id"] not in (original["A"]["row_id"], newer_id)
    assert (new["review_status"], new["note"]) == ("open", "")
    assert len([r for r in read_csv(returned) if r["account_no"] == "A"]) == 3


def test_changed_input_below_visible_rounding_still_invalidates_review(tmp_path):
    data, out, first = prepare(tmp_path)
    mark(first)
    original = current(first)["A"]
    bills = read_csv(data / "bills.csv")
    bills[1]["late_fee"] = "5.00001"
    write_csv(data / "bills.csv", bills)
    # Native summary is genuinely unchanged at its displayed precision.
    old_report = (out / "summary.json").read_bytes()
    engine.run(data, out, AS_OF, eval_from=EVAL_FROM)
    assert (out / "summary.json").read_bytes() == old_report
    next_path = tmp_path / "precision.csv"
    review.reconcile(data, out / "summary.json", next_path, first)
    new = current(next_path)["A"]
    assert new["detail"] == original["detail"]
    assert new["evidence_version"] != original["evidence_version"]
    assert new["review_status"] == "open"
    assert next(r for r in read_csv(next_path) if r["row_id"] == original["row_id"])["note"] == original["note"]


def test_payment_identifier_omitted_by_loader_is_still_review_evidence(tmp_path):
    data, out, first = prepare(tmp_path)
    payments = [dict(zip(HEADERS["payments.csv"], ["PAY-1", "A", "UNMATCHED", "10", "2024-02-01"]))]
    write_csv(data / "payments.csv", payments)
    engine.run(data, out, AS_OF, eval_from=EVAL_FROM)
    start = tmp_path / "payments-1.csv"
    review.reconcile(data, out / "summary.json", start, first)
    mark(start)
    old_report = (out / "summary.json").read_bytes()
    payments[0]["payment_id"] = "PAY-CORRECTED"
    write_csv(data / "payments.csv", payments)
    engine.run(data, out, AS_OF, eval_from=EVAL_FROM)
    assert (out / "summary.json").read_bytes() == old_report
    end = tmp_path / "payments-2.csv"
    review.reconcile(data, out / "summary.json", end, start)
    assert current(end)["A"]["review_status"] == "open"
    assert current(end)["A"]["evidence_version"] != current(start)["A"]["evidence_version"]


def test_same_bill_key_across_accounts_and_multiple_codes_stay_distinct(tmp_path):
    data, out, first = prepare(tmp_path)
    bills = read_csv(data / "bills.csv")
    for row in bills:
        if row["period_start"] == "2024-01-01" and row["account_no"] in "AB":
            row["bill_id"] = "SAME-ID"
            row["usage"] = "900"
    write_csv(data / "bills.csv", bills)
    engine.run(data, out, AS_OF, eval_from=EVAL_FROM)
    target = tmp_path / "identities.csv"
    review.reconcile(data, out / "summary.json", target, first)
    rows = [r for r in read_csv(target) if r["row_state"] == "current"]
    assert len(rows) == 4
    assert len({r["finding_id"] for r in rows}) == 4
    assert {r["code"] for r in rows} == {"USAGE_SPIKE", "LATE_FEE_OR_PAST_DUE"}
    assert {r["account_no"] for r in rows} == {"A", "B"}


def test_unknown_accounts_and_missing_periods_have_inspectable_source_keys(tmp_path):
    data, out, first = prepare(tmp_path)
    accounts = read_csv(data / "accounts.csv")
    accounts[0]["cycle"] = "monthly"
    write_csv(data / "accounts.csv", accounts)
    bills = read_csv(data / "bills.csv") + [bill("UNKNOWN", 2024)]
    write_csv(data / "bills.csv", bills)
    engine.run(data, out, date(2024, 3, 5), eval_from=EVAL_FROM)
    target = tmp_path / "exceptions.csv"
    review.reconcile(data, out / "summary.json", target, first)
    rows = read_csv(target)
    unknown = next(r for r in rows if r["code"] == "UNKNOWN_ACCOUNT")
    missing = next(r for r in rows if r["code"] == "MISSING_BILL")
    assert (unknown["kind"], unknown["account_no"], unknown["detail"]) == ("exception", "UNKNOWN", "")
    assert json.loads(unknown["evidence"]) == ["bills.csv:8"]
    assert missing["finding_key"] == "A:2024-02-01"
    assert json.loads(missing["evidence"]) == ["accounts.csv:2"]


@pytest.mark.parametrize("mutation", [
    "status", "reviewer", "note", "protected", "delete", "duplicate", "manifest", "manifest-note",
    "extra-header", "duplicate-header", "missing-header", "malformed-csv",
])
def test_malformed_prior_refuses_without_replacing_any_input(tmp_path, mutation):
    data, out, first = prepare(tmp_path)
    rows = mark(first)
    columns = list(review.COLUMNS)
    if mutation == "status":
        rows[0]["review_status"] = "paid"
    elif mutation in ("reviewer", "note"):
        rows[0][mutation] = "   "
    elif mutation == "protected":
        rows[0]["detail"] = "Changed protected evidence"
    elif mutation == "delete":
        rows.pop(0)
    elif mutation == "duplicate":
        rows.insert(0, dict(rows[0]))
    elif mutation == "manifest":
        rows.pop()
    elif mutation == "manifest-note":
        rows[-1]["note"] = "Edited manifest"
    elif mutation == "extra-header":
        columns.append("extra")
    elif mutation == "duplicate-header":
        columns.append("note")
    elif mutation == "missing-header":
        columns.remove("note")
        rows = [{k: v for k, v in r.items() if k != "note"} for r in rows]
    write_csv(first, rows, columns)
    if mutation == "malformed-csv":
        first.write_text(first.read_text() + '"unclosed quote', encoding="utf-8")
    before = snapshots(data, out, tmp_path)
    target = tmp_path / "refused.csv"
    with pytest.raises(ValueError):
        review.reconcile(data, out / "summary.json", target, first)
    assert not target.exists()
    assert snapshots(data, out, tmp_path) == before


@pytest.mark.parametrize("mutation", ["duplicate-account", "duplicate-finding", "duplicate-header", "short-row"])
def test_ambiguous_source_refuses_after_native_report_generation(tmp_path, mutation):
    data, out, first = prepare(tmp_path)
    if mutation == "duplicate-account":
        rows = read_csv(data / "accounts.csv")
        write_csv(data / "accounts.csv", rows + [rows[0]])
    elif mutation == "duplicate-finding":
        rows = read_csv(data / "bills.csv")
        # Two unknown-account rows emit the same exception identity in the unchanged engine.
        rows += [bill("UNKNOWN", 2024), bill("UNKNOWN", 2024)]
        write_csv(data / "bills.csv", rows)
    elif mutation == "duplicate-header":
        rows = read_csv(data / "accounts.csv")
        write_csv(data / "accounts.csv", rows, HEADERS["accounts.csv"] + ["unit"])
    else:
        raw = (data / "accounts.csv").read_text()
        (data / "accounts.csv").write_text(raw.replace("common,,irregular", "common", 1))
    if mutation == "duplicate-account":
        before = snapshots(data, out, tmp_path)
        with pytest.raises(ValueError, match="duplicate account_no"):
            engine.run(data, out, AS_OF, eval_from=EVAL_FROM)
        assert snapshots(data, out, tmp_path) == before
    else:
        engine.run(data, out, AS_OF, eval_from=EVAL_FROM)
    before = snapshots(data, out, tmp_path)
    with pytest.raises(ValueError):
        review.reconcile(data, out / "summary.json", tmp_path / "ambiguous.csv", first)
    assert snapshots(data, out, tmp_path) == before


@pytest.mark.parametrize("mutation", ["count", "queue", "flag", "date", "duplicate-key", "nonfinite", "overflow"])
def test_stale_or_malformed_summary_is_not_accepted(tmp_path, mutation):
    data, out, first = prepare(tmp_path)
    report_path = out / "summary.json"
    report = json.loads(report_path.read_text())
    if mutation == "count":
        report["accounts"] = True
    elif mutation == "queue":
        report["payment_queue_detail"][0]["amount_due"] = 0
    elif mutation == "flag":
        report["flags_detail"][0]["evidence"] = ["bills.csv:99"]
    elif mutation == "date":
        report["as_of"] = "2024-2-5"
    report_path.write_text(json.dumps(report))
    if mutation == "duplicate-key":
        report_path.write_text(report_path.read_text().replace('"accounts": 3', '"accounts": 3, "accounts": 3'))
    elif mutation == "nonfinite":
        report_path.write_text(report_path.read_text().replace('"accounts": 3', '"accounts": NaN'))
    elif mutation == "overflow":
        report_path.write_text(report_path.read_text().replace('"accounts": 3', '"accounts": 1e309'))
    before = snapshots(data, out, tmp_path)
    with pytest.raises(ValueError):
        review.reconcile(data, report_path, tmp_path / "invalid-report.csv", first)
    assert snapshots(data, out, tmp_path) == before


def test_empty_current_set_has_a_manifest_and_preserves_absent_history(tmp_path):
    data, out, first = prepare(tmp_path)
    mark(first)
    engine.run(data, out, AS_OF, eval_from=date(2024, 2, 1))
    empty = tmp_path / "empty.csv"
    result = review.reconcile(data, out / "summary.json", empty)
    assert (result["current"], result["history"]) == (0, 0)
    assert [r["row_state"] for r in read_csv(empty)] == ["manifest"]
    again = tmp_path / "empty-again.csv"
    assert review.reconcile(data, out / "summary.json", again, empty)["current"] == 0
    history = tmp_path / "history-only.csv"
    result = review.reconcile(data, out / "summary.json", history, first)
    assert (result["current"], result["history"]) == (0, 2)
    assert next(r for r in read_csv(history) if r["account_no"] == "A")["review_status"] == "reviewed"
    assert all(r["row_state"] == "absent" for r in read_csv(history)[:-1])


def test_output_input_and_symbolic_link_collisions_refuse(tmp_path):
    data, out, first = prepare(tmp_path)
    arbitrary = tmp_path / "existing.txt"
    arbitrary.write_text("preserve")
    dangling = tmp_path / "dangling.csv"
    dangling.symlink_to(tmp_path / "not-created.csv")
    before = snapshots(data, out, tmp_path)
    for target in (first, arbitrary, data / "bills.csv", out / "summary.json", out / "payment_queue.csv", dangling):
        with pytest.raises(ValueError):
            review.reconcile(data, out / "summary.json", target, first)
    assert not (tmp_path / "not-created.csv").exists()
    assert snapshots(data, out, tmp_path) == before


def test_observed_concurrent_input_edit_refuses_before_publication(tmp_path, monkeypatch):
    data, out, first = prepare(tmp_path)
    original = review._combine
    def edit_after_read(current_rows, prior):
        rows = original(current_rows, prior)
        with (data / "bills.csv").open("a") as target:
            target.write("\n")
        return rows
    monkeypatch.setattr(review, "_combine", edit_after_read)
    target = tmp_path / "concurrent.csv"
    with pytest.raises(ValueError, match="input changed during review"):
        review.reconcile(data, out / "summary.json", target, first)
    assert not target.exists()


@pytest.mark.parametrize("failure", ["fsync", "race", "cleanup"])
def test_atomic_publication_handles_write_failure_race_and_post_publish_cleanup(tmp_path, monkeypatch, failure):
    data, out, first = prepare(tmp_path)
    target = tmp_path / "atomic.csv"
    before = snapshots(data, out)
    original_link, original_unlink = os.link, os.unlink
    temporary_names = []
    if failure == "fsync":
        def fail_fsync(_fd):
            raise OSError("simulated full disk")
        monkeypatch.setattr(review.os, "fsync", fail_fsync)
    elif failure == "race":
        def raced_link(source, destination):
            target.write_text("another writer won")
            return original_link(source, destination)
        monkeypatch.setattr(review.os, "link", raced_link)
    else:
        def fail_cleanup(name, *args, **kwargs):
            if Path(name).name.startswith(".uwatch-review-"):
                temporary_names.append(name)
                raise OSError("simulated cleanup denial")
            return original_unlink(name, *args, **kwargs)
        monkeypatch.setattr(review.os, "unlink", fail_cleanup)
    if failure == "cleanup":
        assert review.reconcile(data, out / "summary.json", target, first)["current"] == 2
        assert len(read_csv(target)) == 3
        for name in temporary_names:
            original_unlink(name)
    else:
        with pytest.raises(OSError):
            review.reconcile(data, out / "summary.json", target, first)
        if failure == "race":
            assert target.read_text() == "another writer won"
        else:
            assert not target.exists()
    assert snapshots(data, out) == before
