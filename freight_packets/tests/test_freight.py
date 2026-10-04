import csv
import json
import threading
import urllib.request
from datetime import datetime
from pathlib import Path

import pytest

from freightpkt.detention import evaluate_load
from freightpkt.ingest import load_telematics, parse_time
from freightpkt.models import Load, RateCon, RateConStop, StopEvent
from freightpkt.pipeline import run
from freightpkt.ratecon import parse_ratecon_text
from freightpkt.synth import generate


def rc(**kw):
    base = dict(load_id="L1", ratecon_no="R1", customer="C", carrier="X", linehaul_cents=100000,
                fuel_cents=20000, detention_rate_cents=6000, free_minutes=120, increment_minutes=15,
                detention_cap_cents=None, late_grace_minutes=30,
                stops=[RateConStop("pickup", "Acme DC", datetime(2026, 9, 1, 8, 0))])
    base.update(kw)
    return RateCon(**base)


LOAD = Load("L1", "C", "X", "T1", "TR1", True, "r.txt")


def ev(loc, kind, h, m):
    return StopEvent("T1", loc, kind, datetime(2026, 9, 1, h, m), source_row=f"t.csv:{h}{m}")


def test_detention_rounds_down_to_increment():
    # on time 08:00, leave 11:07 -> 187 on clock - 120 free = 67 -> 60 billable -> $60
    r = evaluate_load(LOAD, rc(), [ev("Acme DC", "entry", 7, 55), ev("Acme DC", "exit", 11, 7)])[0]
    assert r.status == "detention"
    assert r.over_free_minutes == 67 and r.billable_minutes == 60 and r.amount_cents == 6000


def test_early_arrival_clock_starts_at_appointment():
    r = evaluate_load(LOAD, rc(), [ev("Acme DC", "entry", 5, 0), ev("Acme DC", "exit", 10, 30)])[0]
    assert r.clock_start == datetime(2026, 9, 1, 8, 0)
    assert r.billable_minutes == 30 and r.amount_cents == 3000


def test_under_free_time_is_ok():
    r = evaluate_load(LOAD, rc(), [ev("Acme DC", "entry", 8, 0), ev("Acme DC", "exit", 9, 59)])[0]
    assert r.status == "ok" and r.amount_cents == 0


def test_late_arrival_forfeits_detention():
    r = evaluate_load(LOAD, rc(), [ev("Acme DC", "entry", 8, 45), ev("Acme DC", "exit", 14, 0)])[0]
    assert r.status == "late_arrival" and r.amount_cents == 0


def test_cap_applies():
    r = evaluate_load(LOAD, rc(detention_cap_cents=25000),
                      [ev("Acme DC", "entry", 8, 0), ev("Acme DC", "exit", 20, 0)])[0]
    assert r.amount_cents == 25000 and r.capped


def test_missing_exit_is_exception_not_claim():
    r = evaluate_load(LOAD, rc(), [ev("Acme DC", "entry", 8, 0)])[0]
    assert r.status == "exception" and r.amount_cents == 0


def test_other_geofence_ignored_and_fuzzy_facility_match():
    evs = [ev("Other Place", "entry", 7, 0), ev("Other Place", "exit", 7, 10),
           ev("ACME DC, Inc.", "entry", 8, 0), ev("ACME DC, Inc.", "exit", 11, 0)]
    r = evaluate_load(LOAD, rc(), evs)[0]
    assert r.arrival == datetime(2026, 9, 1, 8, 0) and r.amount_cents == 6000


def test_claim_id_is_idempotent():
    evs = [ev("Acme DC", "entry", 8, 0), ev("Acme DC", "exit", 11, 0)]
    a = evaluate_load(LOAD, rc(), evs)[0].claim_id
    b = evaluate_load(LOAD, rc(), evs)[0].claim_id
    assert a == b and a.startswith("DET-")


LAYOUT_B = """CARRIER LOAD CONFIRMATION
Confirmation # RC-9          Order # LD1
Shipper/Customer: Bluebonnet Grocers
Carrier: Caliche Carriers LLC
PU - Lone Star Foods DC; Appointment: 09/03/2026 08:00
DEL - Metroplex Retail DC; Appointment: 09/03/2026 18:30
Base Rate: 1,250.00
FSC: 275.00
Lumper reimbursement: $175.00
Free time of 180 minutes per stop. Detention pay $75.00 per hour thereafter,
30 min increments, maximum $500 per stop. 60 min late grace.
"""


def test_ratecon_parser_layout_b():
    r = parse_ratecon_text(LAYOUT_B, "x.txt")
    assert r.parse_warnings == []
    assert (r.load_id, r.ratecon_no) == ("LD1", "RC-9")
    assert r.linehaul_cents == 125000 and r.fuel_cents == 27500
    assert r.detention_rate_cents == 7500 and r.free_minutes == 180 and r.increment_minutes == 30
    assert r.detention_cap_cents == 50000 and r.late_grace_minutes == 60
    assert r.accessorials_cents == {"LUMPER": 17500}
    assert [s.kind for s in r.stops] == ["pickup", "delivery"]
    assert r.stops[1].appointment == datetime(2026, 9, 3, 18, 30)


def test_ratecon_missing_terms_warns():
    r = parse_ratecon_text("Load #: X1\nLinehaul: $100.00\n")
    assert any("free time" in w for w in r.parse_warnings)
    assert any("det_rate" in w for w in r.parse_warnings)


def test_time_formats():
    assert parse_time("09/01/2026 07:05") == datetime(2026, 9, 1, 7, 5)
    assert parse_time("2026-09-01T07:05:00Z") == datetime(2026, 9, 1, 7, 5)


def test_telematics_csv_header_aliases(tmp_path):
    p = tmp_path / "telematics.csv"
    p.write_text("Asset,Geofence,Event Type,Timestamp\nT9,Yard,GeofenceEntry,2026-09-01 07:00\n", encoding="utf-8")
    [e] = load_telematics(p)
    assert (e.asset, e.location, e.event) == ("T9", "Yard", "entry")


@pytest.fixture(scope="module")
def e2e(tmp_path_factory):
    d = tmp_path_factory.mktemp("fr")
    expected = generate(d / "data", n_loads=30, seed=11)
    summary = run(d / "data", d / "out")
    return d, expected, summary


def test_e2e_detention_total_matches_answer_key(e2e):
    _, expected, s = e2e
    assert s["detention_total_cents"] == expected["detention_total_cents"]
    by_key = {f"{x['load_id']}#{x['stop_index']}": x for x in s["stops"]}
    for key, exp in expected["stops"].items():
        got = by_key[key]
        assert got["amount_cents"] == exp["amount_cents"], key
        want = {"late": "late_arrival"}.get(exp["status"], exp["status"])
        assert got["status"] == want, key


def test_e2e_every_seeded_invoice_defect_flagged(e2e):
    _, expected, s = e2e
    got = {(f["load_id"], f["code"]) for f in s["flags"]}
    for d in expected["invoice_defects"]:
        if d["code"] == "DUPLICATE_INVOICE":
            assert any(c == "DUPLICATE_INVOICE" for _, c in got)
        else:
            assert (d["load_id"], d["code"]) in got, d


def test_e2e_no_flags_on_clean_invoices(e2e):
    _, expected, s = e2e
    defect_loads = {d["load_id"] for d in expected["invoice_defects"]}
    # duplicate defect also touches the previous load
    dup_idx = [d["load_id"] for d in expected["invoice_defects"] if d["code"] == "DUPLICATE_INVOICE"]
    flagged = {f["load_id"] for f in s["flags"]}
    extra = flagged - defect_loads
    # the only allowed extra load is the one the duplicate invoice was re-submitted against
    assert len(extra) <= len(dup_idx)


def test_e2e_outputs_written(e2e):
    d, expected, s = e2e
    out = d / "out"
    for f in ("summary.json", "detention_claims.csv", "invoice_flags.csv", "exceptions.csv", "audit.jsonl"):
        assert (out / f).exists()
    rows = list(csv.DictReader((out / "detention_claims.csv").open(encoding="utf-8")))
    assert len(rows) == s["counts"]["detention_stops"]
    assert all(r["arrival_evidence"] and r["departure_evidence"] for r in rows)
    assert len(s["packets"]) >= 1
    html = (out / s["packets"][0]["file"]).read_text(encoding="utf-8")
    assert "DRAFT" in html and "SYNTHETIC" in html
    assert len(s["exceptions"]) == len(expected["exception_stops"])
    for line in (out / "audit.jsonl").read_text(encoding="utf-8").splitlines():
        json.loads(line)


def test_web_ui_serves(e2e, tmp_path):
    from http.server import ThreadingHTTPServer
    from freightpkt.web import App, make_handler
    d, _, _ = e2e
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(d / "data", d / "out")))
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        html = urllib.request.urlopen(base + "/").read().decode()
        assert "SYNTHETIC" in html and "http" not in html.split("<script>")[1].split("fetch")[0]
        s = json.loads(urllib.request.urlopen(base + "/api/summary").read())
        lid = s["packets"][0]["load_id"]
        req = urllib.request.Request(base + "/api/decision", method="POST",
                                     data=json.dumps({"load_id": lid, "decision": "approve"}).encode(),
                                     headers={"Content-Type": "application/json"})
        dec = json.loads(urllib.request.urlopen(req).read())
        assert dec[lid]["decision"] == "approve"
        assert urllib.request.urlopen(base + f"/out/packets/{lid}.html").status == 200
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base + "/out/../../etc/passwd")
    finally:
        srv.shutdown()
