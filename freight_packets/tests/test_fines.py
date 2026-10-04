"""Fines matrix, tracking-export ingest and settlement worksheet."""
import json
from datetime import datetime

import pytest

from freightpkt.detention import evaluate_load
from freightpkt.fines import Fine, assess_fines, settle
from freightpkt.ingest import load_tracking_stops
from freightpkt.models import Invoice, InvoiceLine, Load, RateCon, RateConStop
from freightpkt.pipeline import run
from freightpkt.synth import generate

SCHED = {c: {"amount_cents": a, "applies_to": "brokered", "source": f"s:{c}", "description": ""}
         for c, a in (("LATE_POD", 10000), ("MISSING_PICKUP_PHOTOS", 5000),
                      ("MISSING_DELIVERY_PHOTOS", 5000), ("TRACKING_GAP", 15000),
                      ("LATE_PICKUP", 10000), ("LATE_DELIVERY", 15000))}


def _rc():
    return RateCon("B1", "R1", "C", "X", 100000, 20000, 6000, 120, 15, None, 30,
                   stops=[RateConStop("pickup", "Acme DC", datetime(2026, 9, 1, 8, 0)),
                          RateConStop("delivery", "Zed Whse", datetime(2026, 9, 1, 18, 0))])


def _track(tmp_path, rows):
    p = tmp_path / "tracking_stops.csv"
    p.write_text("Load Number,Stop Sequence,Stop Name,Actual Arrival,Actual Departure\n"
                 + "\n".join(rows) + "\n", encoding="utf-8")
    return load_tracking_stops(p)


def test_tracking_export_drives_detention_by_load_number(tmp_path):
    evs = _track(tmp_path, ["B1,1,ACME DC Inc.,2026-09-01 07:50,2026-09-01 11:07",
                            "B1,2,Zed Whse,2026-09-01 17:40,2026-09-01 19:00"])
    load = Load("B1", "C", "Outside Carrier LLC", "", "", True, "r.txt", mode="brokered")
    r1, r2 = evaluate_load(load, _rc(), evs)
    assert r1.status == "detention" and r1.amount_cents == 6000
    assert r1.arrival_src == "tracking_stops.csv:row2" and r2.status == "ok"


def test_blank_departure_is_exception_and_tracking_gap_fine(tmp_path):
    evs = _track(tmp_path, ["B1,1,Acme DC,2026-09-01 07:50,2026-09-01 09:00",
                            "B1,2,Zed Whse,2026-09-01 17:40,"])
    load = Load("B1", "C", "X", "", "", True, "r.txt", mode="brokered")
    rs = evaluate_load(load, _rc(), evs)
    assert rs[1].status == "exception"
    docs = {"B1": {"PICKUP_PHOTOS": (datetime(2026, 9, 1, 9), "d:2"),
                   "DELIVERY_PHOTOS": (datetime(2026, 9, 1, 19), "d:3"),
                   "POD": (datetime(2026, 9, 2, 9), "d:4")}}
    fines, exc = assess_fines({"B1": load}, {"B1": rs}, SCHED, docs, {}, [], True)
    assert [f.code for f in fines] == ["TRACKING_GAP"]
    # POD lateness can't be measured without a final departure: exception, not a fine
    assert exc and "POD timeliness" in exc[0]["reason"]


def _clean_stops(tmp_path):
    evs = _track(tmp_path, ["B1,1,Acme DC,2026-09-01 07:50,2026-09-01 09:00",
                            "B1,2,Zed Whse,2026-09-01 17:40,2026-09-01 19:00"])
    load = Load("B1", "C", "X", "", "", True, "r.txt", mode="brokered")
    return load, evaluate_load(load, _rc(), evs)


def test_late_pod_and_missing_photo_fines_with_dispute_window(tmp_path):
    load, rs = _clean_stops(tmp_path)
    docs = {"B1": {"PICKUP_PHOTOS": (datetime(2026, 9, 1, 9), "d:2"),
                   "POD": (datetime(2026, 9, 3, 20), "d:4")}}   # 49h after 19:00 departure
    inv = Invoice("I1", "B1", "X", "2026-09-04", 120000,
                  [InvoiceLine("LINEHAUL", 100000), InvoiceLine("FUEL", 20000)], "inv:2")
    disputes = {("B1", "LATE_POD"): (datetime(2026, 9, 11, 10), "receiver late", "disp:2"),
                ("B1", "MISSING_DELIVERY_PHOTOS"): (datetime(2026, 9, 12, 9), "uploaded late", "disp:3")}
    fines, _ = assess_fines({"B1": load}, {"B1": rs}, SCHED, docs, disputes, [inv], True)
    by = {f.code: f for f in fines}
    assert set(by) == {"LATE_POD", "MISSING_DELIVERY_PHOTOS"}
    assert by["LATE_POD"].dispute_deadline == "2026-09-11"
    assert by["LATE_POD"].status == "disputed_in_window" and by["LATE_POD"].deducted_cents == 0
    assert by["MISSING_DELIVERY_PHOTOS"].status == "dispute_late"
    assert by["MISSING_DELIVERY_PHOTOS"].deducted_cents == 5000
    [st] = settle([inv], {"B1": load}, {"B1": _rc()}, {}, [], fines, {"B1": rs})
    assert (st.approved_cents, st.fines_cents, st.net_cents, st.status) == (120000, 5000, 115000, "READY")


def test_asset_loads_are_not_fined(tmp_path):
    load, rs = _clean_stops(tmp_path)
    load.mode = "asset"
    fines, _ = assess_fines({"B1": load}, {"B1": rs}, SCHED, {}, {}, [], True)
    assert fines == []


def test_settlement_caps_at_ratecon_and_holds_missing_pod(tmp_path):
    load, rs = _clean_stops(tmp_path)
    load.pod_received = False
    inv = Invoice("I1", "B1", "X", "2026-09-04", 150000,
                  [InvoiceLine("LINEHAUL", 110000), InvoiceLine("FUEL", 20000),
                   InvoiceLine("DETENTION", 20000)], "inv:2")
    [st] = settle([inv], {"B1": load}, {"B1": _rc()}, {"B1": 0}, [], [], {"B1": rs})
    assert st.approved_cents == 120000 and st.status == "HOLD" and st.hold_reasons == ["MISSING_POD"]


@pytest.mark.parametrize("seed,n", [(3, 40), (7, 24), (99, 40)])
def test_e2e_fines_and_holds_match_answer_key(tmp_path, seed, n):
    e = generate(tmp_path / "data", n, seed)
    s = run(tmp_path / "data", tmp_path / "out")
    got = {(f["load_id"], f["code"], f["amount_cents"], f["status"]) for f in s["fines"]}
    assert got == {(f["load_id"], f["code"], f["amount_cents"], f["status"]) for f in e["fines"]}
    holds = {(x["invoice_no"], x["load_id"], r) for x in s["settlements"] for r in x["hold_reasons"]}
    assert holds == {(h["invoice_no"], h["load_id"], h["reason"]) for h in e["settlement_holds"]}
    pod_exc = sorted(x["load_id"] for x in s["exceptions"] if "POD timeliness" in x["reason"])
    assert pod_exc == sorted(e["fine_exceptions"])
    assert s["detention_total_cents"] == e["detention_total_cents"]
    for f in ("fines.csv", "settlement.csv"):
        assert (tmp_path / "out" / f).exists()
    assert any(json.loads(l)["action"] == "settlement_line"
               for l in (tmp_path / "out" / "audit.jsonl").read_text(encoding="utf-8").splitlines())


def test_no_schedule_means_no_fines(tmp_path):
    generate(tmp_path / "data", 12, 5)
    (tmp_path / "data" / "fines_schedule.csv").unlink()
    s = run(tmp_path / "data", tmp_path / "out")
    assert s["fines"] == [] and s["settlements"] == []
