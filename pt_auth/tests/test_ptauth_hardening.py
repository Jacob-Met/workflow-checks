"""Adversarial tests for real-export edge cases. See pt_auth/HARDENING.md for the defect list."""
from dataclasses import asdict
from datetime import date, timedelta, timezone

import pytest

from ptauth import data
from ptauth.cli import main
from ptauth.data import Auth, PayerRule, Visit, load_auths, load_patients, load_payers, load_visits
from ptauth.engine import build_ledger, build_worklist
from ptauth.report import render_digest

AS_OF = date(2026, 9, 28)
RULE = PayerRule("P", "Plan (placeholder)", True, 3, 10, 5, None, True, ["Progress note"])
PAYERS = {"P": RULE}

SCHED_HDR = "visit_id,patient_id,visit_date,clinic,therapist,payer_id,status,visit_type\n"
AUTH_HDR = "auth_no,patient_id,payer_id,visits_authorized,start_date,end_date,status\n"
PAYER_HDR = ("payer_id,payer_name,requires_auth,reauth_visits_before,reauth_days_before,"
             "turnaround_days,annual_visit_limit,counts_evals,checklist\n")


def write(path, text, encoding="utf-8"):
    path.write_bytes(text.encode(encoding))
    return path


def d(offset):
    return AS_OF + timedelta(days=offset)


def v(vid, off, status=None, pid="SYN-1", payer="P", vtype="treatment"):
    return Visit(vid, pid, d(off), "C", "PT", payer, status or ("completed" if off < 0 else "scheduled"), vtype)


def a(no, n, start, end, status="approved", pid="SYN-1", payer="P"):
    return Auth(no, pid, payer, n, d(start), d(end), status)


def reasons_by_auth(items):
    return {it.auth_no: it.reasons for it in items}


# ---------------------------------------------------------------- CSV shape

def test_bom_header_is_read(tmp_path):
    p = write(tmp_path / "schedule.csv", SCHED_HDR + "V1,SYN-1,2026-09-20,C,PT,P,completed,treatment\n", "utf-8-sig")
    [x] = load_visits(p)
    assert x.visit_id == "V1"


def test_comma_only_trailing_rows_are_skipped(tmp_path):
    p = write(tmp_path / "schedule.csv", SCHED_HDR + "V1,SYN-1,2026-09-20,C,PT,P,completed,treatment\n"
              ",,,,,,,\n,,,,,,,\n")
    assert [x.visit_id for x in load_visits(p)] == ["V1"]


def test_source_row_points_at_file_line_after_blank_lines(tmp_path):
    p = write(tmp_path / "schedule.csv", SCHED_HDR + "V1,SYN-1,2026-09-20,C,PT,P,completed,treatment\n\n\n"
              "V2,SYN-1,2026-09-22,C,PT,P,completed,treatment\n")
    assert [x.source_row for x in load_visits(p)] == ["schedule.csv:row2", "schedule.csv:row5"]


def test_extra_trailing_field_does_not_crash(tmp_path):
    p = write(tmp_path / "schedule.csv", SCHED_HDR + "V1,SYN-1,2026-09-20,C,PT,P,completed,treatment,\n")
    [x] = load_visits(p)
    assert x.visit_type == "treatment"


def test_human_headers_are_accepted(tmp_path):
    p = write(tmp_path / "schedule.csv", "Visit ID,Patient ID,Visit Date,Clinic,Therapist,Payer ID,Status,Visit Type\n"
              "V1,SYN-1,2026-09-20,C,PT,P,completed,treatment\n")
    [x] = load_visits(p)
    assert (x.patient_id, x.visit_date) == ("SYN-1", date(2026, 9, 20))


def test_cp1252_export_loads(tmp_path):
    p = write(tmp_path / "patients.csv", "patient_id,display_name,clinic,primary_payer\nSYN-1,Test Jos\u00e9 A.,C,P\n",
              "cp1252")
    assert load_patients(p)["SYN-1"].display_name == "Test Jos\u00e9 A."


# ---------------------------------------------------------------- dates / time zones

@pytest.mark.parametrize("raw", ["2026-09-28", "9/28/2026", "09/28/26", "9/28/2026 10:00 AM", "09/28/2026 14:30",
                                 "9/28/2026 2:30:00 PM", "2026-09-28T09:15:00", "2026-09-28 09:15", "2026/09/28"])
def test_common_export_date_formats_parse(raw):
    assert data._d(raw) == date(2026, 9, 28)


def test_aware_timestamp_uses_clinic_local_date(monkeypatch):
    monkeypatch.setattr(data, "CLINIC_TZ", timezone(timedelta(hours=-7)), raising=False)
    assert data._d("2026-09-29T01:30:00Z") == date(2026, 9, 28)        # 6:30 PM Pacific
    assert data._d("2026-09-28T18:30:00-07:00") == date(2026, 9, 28)


def test_day_first_date_is_rejected_with_file_and_line(tmp_path):
    p = write(tmp_path / "schedule.csv", SCHED_HDR + "V1,SYN-1,28/09/2026,C,PT,P,completed,treatment\n")
    with pytest.raises(ValueError, match=r"schedule\.csv line 2.*visit_date"):
        load_visits(p)


def test_leap_day_auth_end_is_inclusive():
    assert data._d("2/29/2028") == date(2028, 2, 29)
    leap = date(2028, 2, 29)
    visits = [Visit("V1", "SYN-1", leap, "C", "PT", "P", "scheduled"),
              Visit("V2", "SYN-1", leap + timedelta(days=1), "C", "PT", "P", "scheduled")]
    auths = [Auth("A1", "SYN-1", "P", 10, date(2028, 1, 1), leap, "approved")]
    led, unc = build_ledger(visits, auths, PAYERS, date(2028, 2, 20))
    assert len(led["A1"].scheduled) == 1 and [x.visit_id for x in unc] == ["V2"]


# ---------------------------------------------------------------- visit status / type

def test_visit_status_synonyms_are_normalized(tmp_path):
    rows = ["V1,SYN-1,2026-09-20,C,PT,P,Checked Out,Treatment", "V2,SYN-1,2026-09-21,C,PT,P,No Show,Treatment",
            "V3,SYN-1,2026-09-22,C,PT,P,Canceled,Treatment", "V4,SYN-1,2026-09-23,C,PT,P,Late Cancel,Treatment",
            "V5,SYN-1,2026-09-24,C,PT,P,Arrived,Treatment", "V6,SYN-1,2026-10-01,C,PT,P,Confirmed,Treatment"]
    vs = load_visits(write(tmp_path / "schedule.csv", SCHED_HDR + "\n".join(rows) + "\n"))
    assert [x.status for x in vs] == ["completed", "no_show", "cancelled", "cancelled", "completed", "scheduled"]
    led, _ = build_ledger(vs, [a("A1", 10, -30, 30)], PAYERS, AS_OF)
    assert (len(led["A1"].used), len(led["A1"].scheduled)) == (2, 1)


def test_unknown_visit_status_is_rejected_not_dropped(tmp_path):
    p = write(tmp_path / "schedule.csv", SCHED_HDR + "V1,SYN-1,2026-09-20,C,PT,P,Complet,treatment\n")
    with pytest.raises(ValueError, match=r"line 2.*status"):
        load_visits(p)


def test_cancelled_and_no_show_never_consume_auth():
    vs = [v("V1", -5), v("V2", -4, "cancelled"), v("V3", -3, "no_show"), v("V4", 2, "cancelled")]
    led, unc = build_ledger(vs, [a("A1", 1, -30, 30)], PAYERS, AS_OF)
    assert (len(led["A1"].used), len(led["A1"].scheduled), unc) == (1, 0, [])


def test_visit_type_synonyms_are_normalized(tmp_path):
    rows = ["V1,SYN-1,2026-09-20,C,PT,P,completed,Initial Evaluation",
            "V2,SYN-1,2026-09-21,C,PT,P,completed,Re-Evaluation", "V3,SYN-1,2026-09-22,C,PT,P,completed,Tx"]
    vs = load_visits(write(tmp_path / "schedule.csv", SCHED_HDR + "\n".join(rows) + "\n"))
    assert [x.visit_type for x in vs] == ["eval", "re-eval", "treatment"]


# ---------------------------------------------------------------- patient / payer id mismatches

def test_ids_are_normalized_across_files(tmp_path):
    sched = write(tmp_path / "schedule.csv", SCHED_HDR + "V1, syn-1001 ,2026-09-20,C,PT,pay-comm1,completed,treatment\n"
                  "V2,1234,2026-09-21,C,PT,PAY-COMM1,completed,treatment\n")
    auths = write(tmp_path / "authorizations.csv", AUTH_HDR + "A1,SYN-1001,PAY-COMM1,10,2026-09-01,2026-10-31,approved\n"
                  "A2,001234,Pay-Comm1,10,2026-09-01,2026-10-31,approved\n")
    payers = write(tmp_path / "payers.csv", PAYER_HDR + "PAY-COMM1,Plan,Y,3,10,5,,Y,Note\n")
    led, unc = build_ledger(load_visits(sched), load_auths(auths), load_payers(payers), AS_OF)
    assert unc == [] and len(led["A1"].used) == 1 and len(led["A2"].used) == 1


# ---------------------------------------------------------------- auth / payer rows

def test_blank_visits_authorized_is_rejected(tmp_path):
    p = write(tmp_path / "authorizations.csv", AUTH_HDR + "A1,SYN-1,P,,2026-09-01,2026-10-31,approved\n")
    with pytest.raises(ValueError, match=r"line 2.*visits_authorized"):
        load_auths(p)


def test_auth_end_before_start_is_rejected(tmp_path):
    p = write(tmp_path / "authorizations.csv", AUTH_HDR + "A1,SYN-1,P,12,2026-10-31,2026-09-01,approved\n")
    with pytest.raises(ValueError, match=r"line 2.*end_date"):
        load_auths(p)


def test_auth_status_synonyms_and_blank_status(tmp_path):
    p = write(tmp_path / "authorizations.csv", AUTH_HDR + "A1,SYN-1,P,12,2026-09-01,2026-10-31,Approved\n"
              "A2,SYN-1,P,12,2026-11-01,2026-12-31,Submitted\nA3,SYN-1,P,12,2026-11-01,2026-12-31,In Review\n"
              "A4,SYN-1,P,12,2026-11-01,2026-12-31,Denied\n")
    assert [x.status for x in load_auths(p)] == ["approved", "pending", "pending", "denied"]
    blank = write(tmp_path / "blank.csv", AUTH_HDR + "A1,SYN-1,P,12,2026-09-01,2026-10-31,\n")
    with pytest.raises(ValueError, match=r"line 2.*status"):
        load_auths(blank)


def test_payer_flags_fail_safe(tmp_path):
    ok = write(tmp_path / "payers.csv", PAYER_HDR + "P,Plan,Yes,3,10,5,,,Note\n")
    assert load_payers(ok)["P"].counts_evals is True
    blank = write(tmp_path / "blank.csv", PAYER_HDR + "P,Plan,,3,10,5,,Y,Note\n")
    with pytest.raises(ValueError, match=r"line 2.*requires_auth"):
        load_payers(blank)


# ---------------------------------------------------------------- engine rules

def test_duplicate_visit_rows_from_appended_exports_count_once():
    vs = [v("V1", -5, "scheduled"), v("V2", -3), v("V1", -5, "completed")]
    led, unc = build_ledger(vs, [a("A1", 10, -30, 30)], PAYERS, AS_OF)
    assert (len(led["A1"].used), len(led["A1"].scheduled), unc) == (2, 0, [])


def test_renewal_reusing_auth_number_keeps_separate_periods():
    old = [v(f"O{i}", -100 + i * 3) for i in range(10)]          # inside the first period
    new = [v(f"N{i}", -20 + i * 3) for i in range(6)]            # inside the renewal
    auths = [a("A1", 12, -110, -50), a("A1", 12, -49, 40)]
    items, led, unc = build_worklist(old + new, auths, PAYERS, {}, AS_OF)
    assert unc == []
    assert sorted((len(x.used), x.auth.visits_authorized) for x in led.values()) == [(6, 12), (10, 12)]


def test_amended_auth_row_supersedes_earlier_version():
    vs = [v(f"V{i}", -28 + i * 2) for i in range(14)]
    led, unc = build_ledger(vs, [a("A1", 12, -30, 30), a("A1", 20, -30, 60)], PAYERS, AS_OF)
    assert unc == [] and list(led) == ["A1"] and led["A1"].remaining == 6 and led["A1"].auth.end == d(60)


def test_older_longer_auth_does_not_suppress_reauth_of_current_auth():
    old = [v(f"O{i}", -200 + i * 5) for i in range(10)]
    cur = [v(f"C{i}", -18 + i * 3) for i in range(6)] + [v("F1", 2), v("F2", 5)]
    auths = [a("OLD", 10, -210, 100), a("NEW", 8, -20, 40)]
    items, led, _ = build_worklist(old + cur, auths, PAYERS, {}, AS_OF)
    assert led["NEW"].remaining == 2
    assert "REAUTH_BY_VISITS" in reasons_by_auth(items).get("NEW", [])


def test_reauth_by_visits_requires_continuing_visits():
    vs = [v(f"V{i}", -15 + i * 3) for i in range(5)]                 # discharged: nothing scheduled
    items, _, _ = build_worklist(vs, [a("A1", 7, -20, 60)], PAYERS, {}, AS_OF)
    assert items == []


def test_unknown_payer_is_flagged_not_silently_skipped():
    vs = [v("V1", -3, payer="Q"), v("V2", 2, payer="Q")]
    items, _, _ = build_worklist(vs, [a("A1", 3, -20, 5, payer="Q")], PAYERS, {}, AS_OF)
    assert any("UNKNOWN_PAYER" in it.reasons for it in items)


def test_zero_visit_auth_leaves_every_visit_uncovered():
    items, led, unc = build_worklist([v("V1", 1), v("V2", 3)], [a("A1", 0, -5, 30)], PAYERS, {}, AS_OF)
    assert [x.visit_id for x in unc] == ["V1", "V2"]
    [it] = items
    assert it.priority == "P1" and it.visits_authorized == 0 and "UNCOVERED_VISIT" in it.reasons


def test_digest_shows_zero_visits_authorized():
    items, _, _ = build_worklist([v("V1", 1)], [a("A1", 0, -5, 30)], PAYERS, {}, AS_OF)
    s = {"banner": "SYNTHETIC", "as_of": AS_OF, "worklist": [asdict(i) for i in items],
         "counts": {"p1": 1, "p2": 0, "p3": 0, "uncovered_scheduled": 1, "unauthorized_done": 0}}
    assert "0 / 0" in render_digest(s)


def test_visit_on_auth_end_date_is_covered_and_next_day_is_not():
    led, unc = build_ledger([v("V1", 3), v("V2", 4)], [a("A1", 10, -20, 3)], PAYERS, AS_OF)
    assert [x.visit_id for x in led["A1"].scheduled] == ["V1"] and [x.visit_id for x in unc] == ["V2"]


def test_auth_ending_today_is_still_live():
    items, _, unc = build_worklist([v("V1", -2), v("V2", 0)], [a("A1", 10, -20, 0)], PAYERS, {}, AS_OF)
    [it] = items
    assert unc == [] and it.days_left == 0 and "REAUTH_BY_DATE" in it.reasons


# ---------------------------------------------------------------- CLI

def test_cli_reports_bad_input_without_traceback(tmp_path, capsys):
    dd = tmp_path / "data"
    dd.mkdir()
    write(dd / "schedule.csv", SCHED_HDR + "V1,SYN-1,28/09/2026,C,PT,P,completed,treatment\n")
    write(dd / "authorizations.csv", AUTH_HDR)
    write(dd / "payers.csv", PAYER_HDR + "P,Plan,Y,3,10,5,,Y,Note\n")
    rc = main(["run", "--data", str(dd), "--out", str(tmp_path / "out"), "--as-of", "2026-09-28"])
    err = capsys.readouterr().err
    assert rc == 2 and "schedule.csv line 2" in err and "Traceback" not in err
