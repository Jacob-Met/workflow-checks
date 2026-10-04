import json
import threading
import urllib.error
import urllib.request
from datetime import date, timedelta

import pytest

from ptauth.data import Auth, Patient, PayerRule, Visit
from ptauth.engine import build_ledger, build_worklist
from ptauth.report import run
from ptauth.synth import generate

AS_OF = date(2026, 9, 28)
RULE = PayerRule("P", "Plan (placeholder)", True, 3, 10, 5, None, True, ["Progress note", "POC"])
PAYERS = {"P": RULE, "SELF": PayerRule("SELF", "Self", False, 0, 0, 0, None, True)}
PATS = {"SYN-1": Patient("SYN-1", "Test A.", "Clinic", "P")}


def visits(dates, status_before=True, payer="P", vtype="treatment"):
    out = []
    for i, d in enumerate(dates):
        st = "completed" if d < AS_OF else "scheduled"
        out.append(Visit(f"V{i}", "SYN-1", d, "Clinic", "PT", payer, st, vtype))
    return out


def auth(n, start, end, no="A1", status="approved"):
    return Auth(no, "SYN-1", "P", n, start, end, status)


def days(*offsets):
    return [AS_OF + timedelta(days=o) for o in offsets]


def test_ledger_counts_used_and_scheduled():
    v = visits(days(-10, -7, -3, 2, 5))
    led, unc = build_ledger(v, [auth(12, AS_OF - timedelta(days=20), AS_OF + timedelta(days=40))], PAYERS, AS_OF)
    l = led["A1"]
    assert (len(l.used), len(l.scheduled), l.remaining, l.remaining_after_scheduled) == (3, 2, 9, 7)
    assert unc == []


def test_scheduled_past_visit_cap_is_uncovered():
    v = visits(days(-6, -3, 1, 4, 8))
    led, unc = build_ledger(v, [auth(4, AS_OF - timedelta(days=20), AS_OF + timedelta(days=40))], PAYERS, AS_OF)
    assert [x.visit_date for x in unc] == days(8)


def test_scheduled_after_end_date_is_uncovered_and_p1_within_week():
    v = visits(days(-5, 3, 6, 12))
    items, _, unc = build_worklist(v, [auth(20, AS_OF - timedelta(days=20), AS_OF + timedelta(days=4))],
                                   PAYERS, PATS, AS_OF)
    assert [x.visit_date for x in unc] == days(6, 12)
    [it] = items
    assert "UNCOVERED_VISIT" in it.reasons and "REAUTH_BY_DATE" in it.reasons and it.priority == "P1"


def test_reauth_by_visit_count_threshold():
    v = visits(days(-12, -9, -6, -3, 1))
    # 7 authorized, 4 used -> 3 left == threshold 3
    items, _, _ = build_worklist(v, [auth(7, AS_OF - timedelta(days=20), AS_OF + timedelta(days=60))],
                                 PAYERS, PATS, AS_OF)
    [it] = items
    assert it.reasons == ["REAUTH_BY_VISITS"] and it.visits_remaining == 3
    assert it.checklist == ["Progress note", "POC"]
    assert it.submit_by is not None


def test_no_flag_when_healthy():
    v = visits(days(-6, -3, 2))
    items, _, _ = build_worklist(v, [auth(20, AS_OF - timedelta(days=20), AS_OF + timedelta(days=60))],
                                 PAYERS, PATS, AS_OF)
    assert items == []


def test_successor_auth_suppresses_reauth_flag():
    v = visits(days(-6, -3, 2, 9))
    a1 = auth(20, AS_OF - timedelta(days=20), AS_OF + timedelta(days=5))
    a2 = auth(12, AS_OF + timedelta(days=6), AS_OF + timedelta(days=60), no="A2")
    items, _, unc = build_worklist(v, [a1, a2], PAYERS, PATS, AS_OF)
    assert items == [] and unc == []


def test_pending_successor_becomes_followup():
    v = visits(days(-3, 2, 9))
    a1 = auth(20, AS_OF - timedelta(days=20), AS_OF + timedelta(days=5))
    a2 = auth(12, AS_OF + timedelta(days=6), AS_OF + timedelta(days=60), no="A2", status="pending")
    items, _, _ = build_worklist(v, [a1, a2], PAYERS, PATS, AS_OF)
    assert any("PENDING_FOLLOWUP" in it.reasons for it in items)
    assert not any("UNCOVERED_VISIT" in it.reasons for it in items)


def test_completed_visit_without_auth_is_p1():
    v = visits(days(-3))
    items, _, _ = build_worklist(v, [], PAYERS, PATS, AS_OF)
    assert items[0].reasons == ["UNAUTHORIZED_DONE"] and items[0].priority == "P1"


def test_self_pay_never_flagged():
    v = visits(days(-3, 4), payer="SELF")
    items, _, unc = build_worklist(v, [], PAYERS, PATS, AS_OF)
    assert items == [] and unc == []


def test_evals_excluded_when_payer_says_so():
    rule = PayerRule("P", "Plan", True, 1, 0, 0, None, False)
    v = visits(days(-9), vtype="eval") + [Visit("X", "SYN-1", AS_OF - timedelta(days=4), "C", "PT", "P", "completed")]
    led, _ = build_ledger(v, [auth(5, AS_OF - timedelta(days=20), AS_OF + timedelta(days=60))], {"P": rule}, AS_OF)
    assert len(led["A1"].used) == 1


def test_annual_limit_flag():
    rule = PayerRule("P", "Plan", True, 0, 0, 0, 5, True)
    v = visits(days(-12, -9, -6, -3, 3, 6))
    items, _, _ = build_worklist(v, [auth(50, AS_OF - timedelta(days=20), AS_OF + timedelta(days=60))],
                                 {"P": rule}, PATS, AS_OF)
    assert "ANNUAL_LIMIT" in items[0].reasons and items[0].priority == "P2"


@pytest.fixture(scope="module")
def e2e(tmp_path_factory):
    d = tmp_path_factory.mktemp("pt")
    exp = generate(d / "data", n_patients=60, seed=5)
    s = run(d / "data", d / "out")
    return d, exp, s


def test_e2e_zero_uncovered_visits_missed(e2e):
    _, exp, s = e2e
    got = {u["visit_id"] for u in s["uncovered"] if u["status"] == "scheduled"}
    assert got == set(exp["uncovered_scheduled"]) | set(exp["pending_visits"])
    flagged_patients = {w["patient_id"] for w in s["worklist"]}
    uncovered_patients = {u["patient_id"] for u in s["uncovered"] if str(u["date"]) >= exp["as_of"]}
    assert uncovered_patients <= flagged_patients  # every uncovered visit reaches the worklist


def test_e2e_reauth_matches_manual_audit(e2e):
    _, exp, s = e2e
    got = {w["patient_id"] for w in s["worklist"] if {"REAUTH_BY_VISITS", "REAUTH_BY_DATE"} & set(w["reasons"])}
    assert got == set(exp["reauth_due"])


def test_e2e_unauthorized_done_and_pending(e2e):
    _, exp, s = e2e
    assert {u["visit_id"] for u in s["uncovered"] if u["status"] == "completed"} == set(exp["unauthorized_done"])
    pend = {w["patient_id"] for w in s["worklist"] if "PENDING_FOLLOWUP" in w["reasons"]}
    assert set(exp["pending_followup"]) <= pend


def test_e2e_clean_patients_not_flagged(e2e):
    _, exp, s = e2e
    assert not ({w["patient_id"] for w in s["worklist"]} & set(exp["clean"]))


def test_e2e_outputs_are_labeled_synthetic(e2e):
    d, _, _ = e2e
    assert "SYNTHETIC DATA" in (d / "out" / "digest.html").read_text(encoding="utf-8")
    assert "SYNTHETIC" in (d / "data" / "README_SYNTHETIC.txt").read_text(encoding="utf-8")
    names = (d / "data" / "patients.csv").read_text(encoding="utf-8").splitlines()[1:]
    assert all(",Test " in n and n.startswith("SYN-") for n in names)


def test_web_ui(e2e):
    from http.server import ThreadingHTTPServer
    from ptauth.web import App, make_handler
    d, _, _ = e2e
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(d / "data", d / "out")))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        html = urllib.request.urlopen(base + "/").read().decode()
        assert "SYNTHETIC DATA" in html and "cdn" not in html.lower()
        s = json.loads(urllib.request.urlopen(base + "/api/summary").read())
        key = s["worklist"][0]["key"]
        req = urllib.request.Request(base + "/api/state", method="POST",
                                     data=json.dumps({"key": key, "state": "submitted"}).encode())
        assert json.loads(urllib.request.urlopen(req).read())[key]["state"] == "submitted"
        req = urllib.request.Request(base + "/api/run", method="POST",
                                     data=json.dumps({"as_of": "2026-10-05"}).encode())
        assert json.loads(urllib.request.urlopen(req).read())["as_of"] == "2026-10-05"
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base + "/out/../../secret")
    finally:
        srv.shutdown()
