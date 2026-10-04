"""Regression cases from real-world freight export edge conditions."""
from datetime import datetime

import pytest

from freightpkt.detention import evaluate_load
from freightpkt.fines import assess_fines, load_disputes, settle
from freightpkt.ingest import load_loads, load_tracking_stops, parse_time
from freightpkt.invoice_match import match_invoices
from freightpkt.models import Invoice, InvoiceLine, Load, RateCon, RateConStop, StopEvent
from freightpkt.packet import render_packet
from freightpkt.ratecon import parse_ratecon_text


def load_and_ratecon(*, appointment=None, **changes):
    load = Load("B1", "C", "Carrier", "", "", True, "r.txt", mode="brokered")
    values = dict(load_id="B1", ratecon_no="R1", customer="C", carrier="Carrier",
                  linehaul_cents=100000, fuel_cents=0, detention_rate_cents=6000,
                  free_minutes=0, increment_minutes=15, detention_cap_cents=None,
                  late_grace_minutes=30,
                  stops=[RateConStop("delivery", "Depot", appointment or datetime(2026, 9, 1, 8))])
    values.update(changes)
    return load, RateCon(**values)


def test_dst_fallback_stop_uses_elapsed_time_across_offset_change():
    appointment = parse_time("2026-11-01T01:30:00-07:00")
    load, rc = load_and_ratecon(appointment=appointment)
    events = [StopEvent("B1", "Depot", "entry", parse_time("2026-11-01T01:30:00-07:00")),
              StopEvent("B1", "Depot", "exit", parse_time("2026-11-01T01:15:00-08:00"))]
    [stop] = evaluate_load(load, rc, events)
    assert stop.dwell_minutes == 45
    assert (stop.status, stop.billable_minutes, stop.amount_cents) == ("detention", 45, 4500)


def test_midnight_appointment_matches_next_day_departure():
    load, rc = load_and_ratecon(appointment=datetime(2026, 9, 1, 23, 45))
    events = [StopEvent("B1", "Depot", "entry", datetime(2026, 9, 1, 23, 30)),
              StopEvent("B1", "Depot", "exit", datetime(2026, 9, 2, 0, 45))]
    [stop] = evaluate_load(load, rc, events)
    assert (stop.status, stop.billable_minutes) == ("detention", 60)


def test_missing_arrival_and_departure_before_arrival_are_exceptions(tmp_path):
    path = tmp_path / "tracking_stops.csv"
    path.write_text("Load Number,Stop Name,Actual Arrival,Actual Departure\n"
                    "B1,Depot,,2026-09-01 09:00\n", encoding="utf-8")
    load, rc = load_and_ratecon()
    [stop] = evaluate_load(load, rc, load_tracking_stops(path))
    assert stop.status == "exception" and stop.amount_cents == 0
    path.write_text("Load Number,Stop Name,Actual Arrival,Actual Departure\n"
                    "B1,Depot,2026-09-01 08:00,2026-09-01 07:59\n", encoding="utf-8")
    [stop] = evaluate_load(load, rc, load_tracking_stops(path))
    assert stop.status == "exception" and stop.amount_cents == 0


def test_orphan_tracking_departure_cannot_close_different_row(tmp_path):
    path = tmp_path / "tracking_stops.csv"
    path.write_text("Load Number,Stop Name,Actual Arrival,Actual Departure\n"
                    "B1,Depot,2026-09-01 08:00,\n"
                    "B1,Depot,,2026-09-01 10:00\n", encoding="utf-8")
    load, rc = load_and_ratecon()
    [stop] = evaluate_load(load, rc, load_tracking_stops(path))
    assert stop.status == "exception" and stop.amount_cents == 0


def test_brokered_load_ignores_tractor_geofence_from_other_load():
    load, rc = load_and_ratecon()
    load.tractor = "T1"
    events = [StopEvent("T1", "Depot", "entry", datetime(2026, 9, 1, 8)),
              StopEvent("T1", "Depot", "exit", datetime(2026, 9, 1, 10))]
    [stop] = evaluate_load(load, rc, events)
    assert stop.status == "exception" and stop.amount_cents == 0


def test_asset_arrival_cannot_be_closed_by_trailer_exit():
    load, rc = load_and_ratecon()
    load.mode, load.tractor, load.trailer = "asset", "T1", "TR1"
    events = [StopEvent("T1", "Depot", "entry", datetime(2026, 9, 1, 8)),
              StopEvent("TR1", "Depot", "exit", datetime(2026, 9, 1, 10))]
    [stop] = evaluate_load(load, rc, events)
    assert stop.status == "exception" and stop.amount_cents == 0


def test_ratecon_in_other_detention_unit_requires_review():
    text = ("Load #: B1\nRate Con #: R1\nCustomer: C\nCarrier: Carrier\n"
            "Linehaul: $1000.00\nDetention: $100.00/day after 2 hours free\n"
            "DELIVERY: Depot | Appt: 2026-09-01 08:00\n")
    rc = parse_ratecon_text(text)
    assert "missing det_rate" in rc.parse_warnings
    load, _ = load_and_ratecon()
    [stop] = evaluate_load(load, rc, [StopEvent("B1", "Depot", "entry", datetime(2026, 9, 1, 8)),
                                      StopEvent("B1", "Depot", "exit", datetime(2026, 9, 1, 12))])
    assert stop.status == "exception" and stop.amount_cents == 0


def test_duplicate_load_number_is_rejected_with_both_source_rows(tmp_path):
    path = tmp_path / "loads.csv"
    path.write_text("load_id,customer,carrier,tractor,pod_received,ratecon_file\n"
                    "B1,C,First,T1,y,r1.txt\nB1,C,Second,T2,y,r2.txt\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"duplicate load_id B1.*row2.*row3"):
        load_loads(path)


def test_ratecon_warning_never_exposes_provisional_claim_amount():
    load, rc = load_and_ratecon(parse_warnings=["missing free time"])
    events = [StopEvent("B1", "Depot", "entry", datetime(2026, 9, 1, 8)),
              StopEvent("B1", "Depot", "exit", datetime(2026, 9, 1, 9))]
    [stop] = evaluate_load(load, rc, events)
    assert (stop.status, stop.billable_minutes, stop.amount_cents) == ("exception", 0, 0)


def test_detention_fractional_cent_rounds_half_up():
    load, rc = load_and_ratecon(detention_rate_cents=7501)
    events = [StopEvent("B1", "Depot", "entry", datetime(2026, 9, 1, 8)),
              StopEvent("B1", "Depot", "exit", datetime(2026, 9, 1, 8, 30))]
    [stop] = evaluate_load(load, rc, events)
    assert stop.amount_cents == 3751


def test_earliest_dispute_within_inclusive_seventh_day_wins(tmp_path):
    path = tmp_path / "disputes.csv"
    path.write_text("load_id,fine_code,received_at,reason\n"
                    "B1,LATE_DELIVERY,2026-09-11 23:59,on time\n"
                    "B1,LATE_DELIVERY,2026-09-12 00:00,follow up\n", encoding="utf-8")
    load, rc = load_and_ratecon()
    rs = evaluate_load(load, rc, [StopEvent("B1", "Depot", "entry", datetime(2026, 9, 1, 9)),
                                  StopEvent("B1", "Depot", "exit", datetime(2026, 9, 1, 10))])
    schedule = {"LATE_DELIVERY": {"amount_cents": 10000, "applies_to": "brokered", "source": "s:2"}}
    inv = Invoice("I1", "B1", "Carrier", "2026-09-04", 100000,
                  [InvoiceLine("LINEHAUL", 100000)])
    fines, _ = assess_fines({"B1": load}, {"B1": rs}, schedule, {}, load_disputes(path), [inv], False)
    assert fines[0].status == "disputed_in_window"
    assert fines[0].deducted_cents == 0


def test_pod_at_exactly_48_hours_is_not_late():
    load, rc = load_and_ratecon()
    rs = evaluate_load(load, rc, [StopEvent("B1", "Depot", "entry", datetime(2026, 9, 1, 8)),
                                  StopEvent("B1", "Depot", "exit", datetime(2026, 9, 1, 9))])
    schedule = {"LATE_POD": {"amount_cents": 10000, "applies_to": "brokered", "source": "s:2"}}
    docs = {"B1": {"POD": (datetime(2026, 9, 3, 9), "d:2")}}
    fines, exc = assess_fines({"B1": load}, {"B1": rs}, schedule, docs, {}, [], True)
    assert fines == [] and exc == []


def test_all_copies_of_duplicate_invoice_are_held():
    a, rc_a = load_and_ratecon()
    b, rc_b = load_and_ratecon()
    b.load_id = rc_b.load_id = "B2"
    invoices = [Invoice("I1", "B1", "Carrier", "2026-09-04", 100000,
                        [InvoiceLine("LINEHAUL", 100000)]),
                Invoice("I1", "B2", "Carrier", "2026-09-04", 100000,
                        [InvoiceLine("LINEHAUL", 100000)])]
    loads, rcs = {"B1": a, "B2": b}, {"B1": rc_a, "B2": rc_b}
    flags = match_invoices(invoices, loads, rcs, {})
    rows = settle(invoices, loads, rcs, {}, flags, [], {})
    assert len([f for f in flags if f.code == "DUPLICATE_INVOICE"]) == 2
    assert all(s.status == "HOLD" and "DUPLICATE_INVOICE" in s.hold_reasons for s in rows)


def test_partial_ratecon_parse_holds_settlement():
    load, rc = load_and_ratecon(parse_warnings=["missing det_rate"])
    invoice = Invoice("I1", "B1", "Carrier", "2026-09-04", 100000,
                      [InvoiceLine("LINEHAUL", 100000)])
    [row] = settle([invoice], {"B1": load}, {"B1": rc}, {}, [], [], {})
    assert row.status == "HOLD" and "RATECON_PARSE_WARNING" in row.hold_reasons
    assert row.approved_cents == 0


def test_packet_for_real_input_does_not_label_it_synthetic():
    load, rc = load_and_ratecon()
    html = render_packet(load, rc, [], [], [], synthetic=False)
    assert "SYNTHETIC" not in html
    assert "DRAFT" in html
