"""Visit-status reconciliation uses the real CSV, report and CLI boundaries."""
import csv
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from ptauth.report import run


AS_OF = date(2026, 10, 8)
HEADERS = {
    "patients.csv": ["patient_id", "display_name", "clinic", "primary_payer"],
    "payers.csv": ["payer_id", "payer_name", "requires_auth", "reauth_visits_before",
                   "reauth_days_before", "turnaround_days", "annual_visit_limit",
                   "counts_evals", "checklist"],
    "authorizations.csv": ["auth_no", "patient_id", "payer_id", "visits_authorized",
                           "start_date", "end_date", "status"],
    "schedule.csv": ["visit_id", "patient_id", "visit_date", "clinic", "therapist",
                     "payer_id", "status", "visit_type"],
}


def write_rows(data, name, rows):
    with (data / name).open("w", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerows([HEADERS[name], *rows])


def visit(vid, day, status="scheduled", patient="SYN-1", payer="P", kind="treatment"):
    return [vid, patient, day, "Visit clinic (synthetic)", "Test PT", payer, status, kind]


@pytest.fixture
def clinic(tmp_path):
    data, out = tmp_path / "data", tmp_path / "out"
    data.mkdir()
    write_rows(data, "patients.csv", [["SYN-1", "Test Reconciliation", "Home clinic", "P"]])
    write_rows(data, "payers.csv", [["P", "Plan (placeholder)", "Y", 0, 0, 0, "", "Y", ""]])
    write_rows(data, "authorizations.csv", [
        ["A1", "SYN-1", "P", 10, "2026-09-01", "2026-11-30", "approved"],
    ])
    write_rows(data, "schedule.csv", [
        visit("V-PAST-COVERED", "2026-09-20"),
        visit("V-PAST-UNCOVERED", "2026-08-20"),
        visit("V-FUTURE", "2026-10-10"),
    ])
    return data, out


def test_past_appointments_have_source_and_actual_reservation_without_changing_accounting(clinic):
    data, out = clinic
    s = run(data, out, AS_OF)
    rows = s["visit_status_review"]
    assert [r["visit_id"] for r in rows] == ["V-PAST-UNCOVERED", "V-PAST-COVERED"]
    assert [r["days_since"] for r in rows] == [49, 18]
    assert [r["auth_no"] for r in rows] == ["", "A1"]
    assert [r["evidence"] for r in rows] == ["schedule.csv:row3", "schedule.csv:row2"]
    assert rows[0]["capacity_note"] == "No approved authorization visit allocated"
    assert rows[1]["capacity_note"] == "Reserves one authorized visit"
    assert rows[1]["patient_name"] == "Test Reconciliation"
    assert rows[1]["clinic"] == "Visit clinic (synthetic)"
    assert s["counts"]["past_scheduled"] == 2
    assert s["counts"]["uncovered_scheduled"] == s["counts"]["unauthorized_done"] == 0
    [ledger] = s["ledger"]
    assert (ledger["used"], ledger["scheduled"], ledger["remaining_after_scheduled"]) == (0, 2, 8)
    assert s["worklist"] == [], "past status review must not create an empty authorization item"


def test_status_review_uses_last_export_row_and_as_of_boundary(clinic):
    data, out = clinic
    write_rows(data, "schedule.csv", [
        visit("V-CORRECTED", "2026-10-01"),
        visit("V-CORRECTED", "2026-10-01", "completed"),
        visit("V-CANCELLED", "2026-10-02", "cancelled"),
        visit("V-NO-SHOW", "2026-10-03", "no_show"),
        visit("V-TODAY", "2026-10-08"),
        visit("V-YESTERDAY", "2026-10-07", "booked"),
    ])
    today = run(data, out, AS_OF)
    assert [r["visit_id"] for r in today["visit_status_review"]] == ["V-YESTERDAY"]
    tomorrow = run(data, out, date(2026, 10, 9))
    assert [r["visit_id"] for r in tomorrow["visit_status_review"]] == ["V-YESTERDAY", "V-TODAY"]
    assert tomorrow["counts"]["past_scheduled"] == 2
    assert today["ledger"] == [dict(tomorrow["ledger"][0], days_left=today["ledger"][0]["days_left"])]
    assert tomorrow["ledger"][0]["used"] == 1


def test_status_review_distinguishes_exempt_and_unallocated_appointments(clinic):
    data, out = clinic
    write_rows(data, "payers.csv", [
        ["P", "Plan (placeholder)", "Y", 0, 0, 0, "", "N", ""],
        ["SELF", "Self (placeholder)", "N", 0, 0, 0, "", "Y", ""],
    ])
    write_rows(data, "schedule.csv", [
        visit("V-SELF", "2026-10-01", payer="SELF"),
        visit("V-EVAL", "2026-10-02", kind="Initial Evaluation"),
        visit("V-UNKNOWN", "2026-10-03", patient="SYN-MISSING", payer="UNKNOWN"),
    ])
    s = run(data, out, AS_OF)
    rows = s["visit_status_review"]
    assert [r["capacity_note"] for r in rows] == [
        "Payer does not require authorization", "Evaluation excluded by payer rule",
        "No approved authorization visit allocated",
    ]
    assert all(r["auth_no"] == "" for r in rows)
    assert rows[-1]["patient_name"] == "SYN-MISSING" and rows[-1]["payer_name"] == "UNKNOWN"
    assert s["worklist"] == []
    assert s["ledger"][0]["scheduled"] == 0


def test_review_reports_actual_period_when_authorization_number_is_reused(clinic):
    data, out = clinic
    write_rows(data, "authorizations.csv", [
        ["A1", "SYN-1", "P", 10, "2026-08-01", "2026-08-31", "approved"],
        ["A1", "SYN-1", "P", 10, "2026-09-01", "2026-11-30", "approved"],
    ])
    s = run(data, out, AS_OF)
    assert [r["auth_no"] for r in s["visit_status_review"]] == [
        "A1 (2026-08-01..2026-08-31)", "A1 (2026-09-01..2026-11-30)",
    ]
    assert [r["scheduled"] for r in s["ledger"]] == [1, 2]


def test_corrected_export_clears_review_and_releases_only_cancelled_reservation(clinic):
    data, out = clinic
    first = run(data, out, AS_OF)
    assert first["counts"]["past_scheduled"] == 2
    with (data / "schedule.csv").open("a", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerows([
            visit("V-PAST-COVERED", "2026-09-20", "cancelled"),
            visit("V-PAST-UNCOVERED", "2026-08-20", "completed"),
        ])
    corrected = run(data, out, AS_OF)
    assert corrected["visit_status_review"] == [] and corrected["counts"]["past_scheduled"] == 0
    assert corrected["ledger"][0]["scheduled"] == 1
    assert corrected["ledger"][0]["remaining_after_scheduled"] == 9
    assert corrected["counts"]["unauthorized_done"] == 1
    assert corrected["worklist"][0]["reasons"] == ["UNAUTHORIZED_DONE"]
    with (out / "visit_status_review.csv").open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        assert "evidence" in reader.fieldnames and list(reader) == []
    assert "No past appointments remain marked scheduled." in (out / "digest.html").read_text()


def test_real_cli_exports_complete_status_evidence_and_prints_count(clinic):
    data, out = clinic
    result = subprocess.run(
        [sys.executable, "-m", "ptauth", "run", "--data", str(data), "--out", str(out), "--as-of", AS_OF.isoformat()],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "2 past scheduled visits need status review" in result.stdout
    s = json.loads((out / "summary.json").read_text())
    with (out / "visit_status_review.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert [r["visit_id"] for r in rows] == [r["visit_id"] for r in s["visit_status_review"]]
    assert rows[0]["evidence"] == "schedule.csv:row3"
    digest = (out / "digest.html").read_text()
    assert all(r["visit_id"] in digest and r["evidence"] in digest for r in rows)
    assert "SYNTHETIC DATA" in digest


def test_digest_escapes_status_review_context_without_losing_csv_text(clinic):
    data, out = clinic
    name = 'Test <script>unsafe()</script> & "literal"'
    write_rows(data, "patients.csv", [["SYN-1", name, "Home clinic", "P"]])
    run(data, out, AS_OF)
    digest = (out / "digest.html").read_text()
    assert "&lt;script&gt;unsafe()&lt;/script&gt;" in digest and "<script>unsafe()" not in digest
    with (out / "visit_status_review.csv").open(newline="", encoding="utf-8") as stream:
        assert all(r["patient_name"] == name for r in csv.DictReader(stream))
