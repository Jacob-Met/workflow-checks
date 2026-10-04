"""Synthetic sample-data generator (seeded, deterministic).

Writes a data dir with: telematics.csv (Samsara-like geofence export),
telematics_extra.json (Samsara-API-like JSON), loads.csv, ratecons/*.txt,
carrier_invoices.csv and expected.json (answer key: seeded detention per stop
and seeded invoice defects, computed independently of the pipeline).
All companies, drivers and units are fictional.
"""
from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

FACILITIES = [
    ("Lone Star Foods DC", 29.4889, -98.3987), ("Alamo Paper Converting", 29.3668, -98.5361),
    ("Hill Country Beverage", 29.6011, -98.2821), ("Gulf Coast Cold Storage", 29.7550, -95.3240),
    ("Brazos Building Supply", 30.6280, -96.3344), ("Rio Grande Produce Co", 26.2034, -98.2300),
    ("Permian Pipe & Valve", 31.9973, -102.0779), ("Metroplex Retail DC", 32.8998, -97.0403),
]
CUSTOMERS = ["Bluebonnet Grocers", "Texan Home Supply", "Mesquite Beverage Dist."]
CARRIERS = ["Blue Mesa Transport (asset)", "Caliche Carriers LLC", "Pecos Freightways Inc"]
DRIVERS = ["D. Ramirez", "K. Nguyen", "T. Walker", "M. Flores", "J. Okafor", "S. Patel"]

# Two broker layouts to exercise the regex parser.
LAYOUT_A = """RATE CONFIRMATION
Rate Con #: {rc}
Load #: {load}
Customer: {customer}
Carrier: {carrier}

Stop 1 - PICKUP: {f1} | Appt: {a1}
Stop 2 - DELIVERY: {f2} | Appt: {a2}

CHARGES
Linehaul: ${lh}
Fuel Surcharge: ${fuel}
{lumper}
ACCESSORIAL TERMS
Detention: ${rate}/hr after {free_h} hours free at each stop, billed in {inc}-minute increments{cap}.
Late arrival: {grace}-minute grace period after appointment; later arrivals forfeit detention.
"""

LAYOUT_B = """CARRIER LOAD CONFIRMATION
Confirmation # {rc}          Order # {load}
Shipper/Customer: {customer}
Carrier: {carrier}
PU - {f1}; Appointment: {a1}
DEL - {f2}; Appointment: {a2}
Base Rate: {lh}
FSC: {fuel}
{lumper}
Free time of {free_m} minutes per stop. Detention pay ${rate} per hour thereafter,
{inc} min increments{cap}. {grace} min late grace.
"""


def _fmt_a(dt):  # layout A: ISO-ish
    return dt.strftime("%Y-%m-%d %H:%M")


def _fmt_b(dt):  # layout B: US style
    return dt.strftime("%m/%d/%Y %H:%M")


def expected_detention_cents(appt, arrive, depart, free_min, inc, rate_cents, cap_cents, grace):
    """Independent 'human' calculation used for the answer key."""
    if (arrive - appt).total_seconds() / 60 > grace:
        return 0, "late"
    start = appt if arrive < appt else arrive
    over = int((depart - start).total_seconds() // 60) - free_min
    if over <= 0:
        return 0, "ok"
    billable = over - over % inc
    amt = rate_cents * billable // 60 if (rate_cents * billable) % 60 == 0 else round(rate_cents * billable / 60)
    if cap_cents and amt > cap_cents:
        amt = cap_cents
    return amt, ("detention" if amt else "ok")


# Stop scenarios: (name, arrival offset from appt in min, dwell minutes)
SCENARIOS = [
    ("quick", (-20, 10), (45, 110)),
    ("quick", (-10, 5), (60, 115)),
    ("detention", (-10, 20), (170, 330)),
    ("early_detention", (-150, -60), (260, 420)),
    ("late", (75, 140), (150, 300)),
    ("capped", (-5, 10), (700, 800)),
    ("missing_exit", (-10, 10), (200, 300)),
]
WEIGHTS = [30, 20, 22, 8, 7, 3, 3]

# Illustrative carrier fines schedule (amounts are placeholders; a pilot uses the
# client's own matrix). applies_to=brokered: outside carriers only.
FINES_SCHEDULE = [
    ("MISSING_PICKUP_PHOTOS", "Required pickup compliance photos not uploaded", 5000),
    ("MISSING_DELIVERY_PHOTOS", "Required delivery compliance photos not uploaded", 5000),
    ("LATE_POD", "POD not received within 48h of final departure", 10000),
    ("TRACKING_GAP", "Tracking not maintained through the stop (arrival without departure)", 15000),
    ("LATE_PICKUP", "Arrived at pickup after appointment + grace", 10000),
    ("LATE_DELIVERY", "Arrived at delivery after appointment + grace", 15000),
]
FINE_AMT = {c: a for c, _, a in FINES_SCHEDULE}

INVOICE_DEFECTS = ["LINEHAUL_MISMATCH", "FUEL_MISMATCH", "DETENTION_UNSUPPORTED",
                   "ACCESSORIAL_NOT_ON_RATECON", "ACCESSORIAL_OVER_RATECON",
                   "TOTAL_MISMATCH", "DUPLICATE_INVOICE", "MISSING_POD"]


def _terms(rng):
    return {
        "rate": rng.choice([5000, 6000, 7500]),        # cents/hr
        "free": rng.choice([120, 120, 180]),           # minutes
        "inc": rng.choice([15, 15, 30]),
        "cap": rng.choice([None, None, 50000]),        # cents per stop
        "grace": rng.choice([30, 60]),
        "lumper": rng.choice([None, None, 17500]),
    }


def _ratecon_text(layout, rc_no, load_id, customer, carrier, stops, lh, fuel, t):
    fmt = _fmt_a if layout == "A" else _fmt_b
    cap = f", maximum ${t['cap'] // 100} per stop" if t["cap"] else ""
    lumper = f"Lumper reimbursement: ${t['lumper'] / 100:.2f}" if t["lumper"] else ""
    tpl = LAYOUT_A if layout == "A" else LAYOUT_B
    return tpl.format(
        rc=rc_no, load=load_id, customer=customer, carrier=carrier,
        f1=stops[0][0], a1=fmt(stops[0][1]), f2=stops[1][0], a2=fmt(stops[1][1]),
        lh=f"{lh / 100:,.2f}", fuel=f"{fuel / 100:,.2f}", lumper=lumper,
        rate=f"{t['rate'] / 100:.2f}", free_h=f"{t['free'] / 60:g}", free_m=t["free"],
        inc=t["inc"], cap=cap, grace=t["grace"])


def generate(out_dir: Path, n_loads: int = 24, seed: int = 7,
             start: datetime = datetime(2026, 9, 1, 6, 0)) -> dict:
    rng = random.Random(seed)
    rng2 = random.Random(seed * 7919 + 1)  # fines/docs only: keeps detention data stable per seed
    out_dir = Path(out_dir)
    (out_dir / "ratecons").mkdir(parents=True, exist_ok=True)
    csv_events, json_events, loads, invoice_rows = [], [], [], []
    tracking_rows, doc_rows, dispute_rows = [], [], []
    expected = {"stops": {}, "detention_total_cents": 0, "invoice_defects": [],
                "late_stops": [], "exception_stops": [], "fines": [], "fine_exceptions": [],
                "settlement_holds": []}

    for i in range(n_loads):
        load_id = f"LD{260900 + i * 7}"
        rc_no = f"RC-{48000 + i}"
        customer = rng.choice(CUSTOMERS)
        carrier = CARRIERS[i % len(CARRIERS)]
        tractor, trailer = f"T{410 + i % 9}", f"TR53-{5100 + i}"
        driver = rng.choice(DRIVERS)
        f1, f2 = rng.sample(FACILITIES, 2)
        appt1 = start + timedelta(days=i // 2, hours=rng.choice([0, 1, 2, 3, 6, 8]))
        appt2 = appt1 + timedelta(hours=rng.choice([8, 10, 14, 20]))
        t = _terms(rng)
        layout = "A" if i % 2 == 0 else "B"
        lh = rng.randrange(900, 3200) * 100
        fuel = round(lh * rng.choice([0.18, 0.22, 0.25]))

        brokered = carrier != CARRIERS[0]
        cursor = appt1 - timedelta(hours=14)
        det_total = 0
        stop_log = []  # (kind, scenario status, arrive, depart or None)
        for s_idx, (fac, appt) in enumerate(((f1, appt1), (f2, appt2)), start=1):
            name, (a_lo, a_hi), (d_lo, d_hi) = rng.choices(SCENARIOS, WEIGHTS)[0]
            if name == "capped" and not t["cap"]:
                name, (a_lo, a_hi), (d_lo, d_hi) = SCENARIOS[2]
            arrive = appt + timedelta(minutes=rng.randint(a_lo, a_hi))
            arrive = max(arrive, cursor + timedelta(minutes=30))
            depart = arrive + timedelta(minutes=rng.randint(d_lo, d_hi))
            key = f"{load_id}#{s_idx}"
            # a noise event: truck passes through a different geofence en route
            kind = "pickup" if s_idx == 1 else "delivery"
            if s_idx == 2 and rng.random() < 0.5:
                other = rng.choice([f for f in FACILITIES if f not in (f1, f2)])
                tp = arrive - timedelta(hours=3)
                if not brokered:  # stop-level tracking exports have no pass-through geofences
                    for ev, tt in (("Entry", tp), ("Exit", tp + timedelta(minutes=12))):
                        csv_events.append([tractor, driver, other[0], ev, tt, other[1], other[2]])
            if name == "missing_exit":
                if brokered:
                    tracking_rows.append([load_id, carrier, s_idx, fac[0], kind.upper(), appt, arrive, None])
                else:
                    csv_events.append([tractor, driver, fac[0], "Entry", arrive, fac[1], fac[2]])
                stop_log.append((kind, "exception", arrive, None))
                expected["exception_stops"].append(key)
                expected["stops"][key] = {"status": "exception", "amount_cents": 0}
                cursor = depart
                continue
            amt, status = expected_detention_cents(appt, arrive, depart, t["free"], t["inc"],
                                                   t["rate"], t["cap"], t["grace"])
            expected["stops"][key] = {"status": status, "amount_cents": amt}
            if status == "late":
                expected["late_stops"].append(key)
            det_total += amt
            stop_log.append((kind, status, arrive, depart))
            # ~1/4 of events go to the JSON (API-shaped) export to prove both paths
            target = json_events if rng.random() < 0.25 else csv_events
            if brokered:
                tracking_rows.append([load_id, carrier, s_idx, fac[0], kind.upper(), appt, arrive, depart])
            else:
                for ev, tt in (("Entry", arrive), ("Exit", depart)):
                    target.append([tractor, driver, fac[0], ev, tt, fac[1], fac[2]])
            cursor = depart
        expected["detention_total_cents"] += det_total

        text = _ratecon_text(layout, rc_no, load_id, customer, carrier,
                             [(f1[0], appt1), (f2[0], appt2)], lh, fuel, t)
        (out_dir / "ratecons" / f"{rc_no}.txt").write_text(text, encoding="utf-8")

        # Carrier invoice (clean unless a defect is seeded).
        defect = INVOICE_DEFECTS[i // 3] if i % 3 == 1 and i // 3 < len(INVOICE_DEFECTS) else None
        pod = defect != "MISSING_POD"
        loads.append([load_id, customer, carrier, tractor, trailer, "Y" if pod else "N", f"{rc_no}.txt",
                      "brokered" if brokered else "asset"])
        lines = {"LINEHAUL": lh, "FUEL": fuel}
        if det_total:
            lines["DETENTION"] = det_total
        if t["lumper"]:
            lines["LUMPER"] = t["lumper"]
        inv_no = f"{carrier.split()[0][:3].upper()}-{7100 + i}"
        header_delta = 0
        if defect == "LINEHAUL_MISMATCH":
            lines["LINEHAUL"] += 15000
        elif defect == "FUEL_MISMATCH":
            lines["FUEL"] += 4275
        elif defect == "DETENTION_UNSUPPORTED":
            lines["DETENTION"] = det_total + 12500
        elif defect == "ACCESSORIAL_NOT_ON_RATECON":
            lines["TONU"] = 25000
        elif defect == "ACCESSORIAL_OVER_RATECON":
            if not t["lumper"]:
                t["lumper"] = 17500  # ensure the rate-con carries a lumper term
                text = _ratecon_text(layout, rc_no, load_id, customer, carrier,
                                     [(f1[0], appt1), (f2[0], appt2)], lh, fuel, t)
                (out_dir / "ratecons" / f"{rc_no}.txt").write_text(text, encoding="utf-8")
            lines["LUMPER"] = t["lumper"] + 8000
        elif defect == "TOTAL_MISMATCH":
            header_delta = 10000
        total = sum(lines.values()) + header_delta
        inv_date = (appt2 + timedelta(days=2)).strftime("%Y-%m-%d")
        for code, amt in lines.items():
            invoice_rows.append([inv_no, load_id, carrier, inv_date, f"{total / 100:.2f}", code, f"{amt / 100:.2f}"])
        if defect:
            expected["invoice_defects"].append({"load_id": load_id, "code": defect})
        if defect == "DUPLICATE_INVOICE":
            # the same invoice number re-submitted against the previous load
            prev = loads[-2][0]
            for code, amt in lines.items():
                invoice_rows.append([inv_no, prev, carrier, inv_date, f"{total / 100:.2f}", code, f"{amt / 100:.2f}"])
            expected["settlement_holds"].append({"invoice_no": inv_no, "load_id": prev,
                                                 "reason": "DUPLICATE_INVOICE"})
            expected["settlement_holds"].append({"invoice_no": inv_no, "load_id": load_id,
                                                 "reason": "DUPLICATE_INVOICE"})
        if defect == "MISSING_POD":
            expected["settlement_holds"].append({"invoice_no": inv_no, "load_id": load_id, "reason": "MISSING_POD"})
        if "DETENTION" in lines and any(s[1] == "exception" for s in stop_log):
            expected["settlement_holds"].append({"invoice_no": inv_no, "load_id": load_id,
                                                 "reason": "DETENTION_PENDING_REVIEW"})

        # Documents (POD + compliance photos) and the fines they imply, computed
        # here from the seeded facts, independently of freightpkt.fines.
        final_kind, final_status, _, final_depart = stop_log[-1]
        load_fines = []
        for s_idx, (kind, status, _, _) in enumerate(stop_log, start=1):
            if status == "late":
                load_fines.append("LATE_PICKUP" if kind == "pickup" else "LATE_DELIVERY")
            elif status == "exception":
                load_fines.append("TRACKING_GAP")
        for typ, code in (("PICKUP_PHOTOS", "MISSING_PICKUP_PHOTOS"), ("DELIVERY_PHOTOS", "MISSING_DELIVERY_PHOTOS")):
            if rng2.random() < 0.8:
                doc_rows.append([load_id, typ, stop_log[0 if typ.startswith("PICKUP") else -1][2]
                                 + timedelta(minutes=rng2.randint(5, 90))])
            else:
                load_fines.append(code)
        if pod:
            lag_h = rng2.choice([3, 8, 20, 30, 40, 60, 90])
            base = final_depart or stop_log[-1][2]
            doc_rows.append([load_id, "POD", base + timedelta(hours=lag_h)])
            if final_depart is None:
                expected["fine_exceptions"].append(load_id)
            elif lag_h > 48:
                load_fines.append("LATE_POD")
        if brokered:
            for code in load_fines:
                status = "assessed"
                if rng2.random() < 0.3:
                    days = rng2.choice([2, 5, 9])
                    got = datetime.strptime(inv_date, "%Y-%m-%d") + timedelta(days=days, hours=10)
                    dispute_rows.append([load_id, code, got, rng2.choice(
                        ["photos uploaded to wrong load", "receiver delayed check-in", "ELD outage"])])
                    status = "disputed_in_window" if days <= 7 else "dispute_late"
                expected["fines"].append({"load_id": load_id, "code": code, "amount_cents": FINE_AMT[code],
                                          "status": status})
        elif final_depart is None and pod:
            expected["fine_exceptions"].remove(load_id)  # own fleet: fines module skips asset loads

    csv_events.sort(key=lambda r: r[4])
    with (out_dir / "telematics.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Vehicle Name", "Driver Name", "Address Name", "Event", "Time", "Latitude", "Longitude"])
        for r in csv_events:
            w.writerow([r[0], r[1], r[2], r[3], r[4].strftime("%m/%d/%Y %H:%M"), r[5], r[6]])
    json_doc = {"data": [
        {"vehicle": {"name": r[0]}, "driver": {"name": r[1]}, "address": {"name": r[2]},
         "eventType": "Geofence" + r[3], "time": r[4].strftime("%Y-%m-%dT%H:%M:%S") + "Z",
         "location": {"latitude": r[5], "longitude": r[6]}}
        for r in sorted(json_events, key=lambda r: r[4])],
        "pagination": {"hasNextPage": False}}
    (out_dir / "telematics_extra.json").write_text(json.dumps(json_doc, indent=2), encoding="utf-8")
    fmt = lambda d: "" if d is None else d.strftime("%Y-%m-%d %H:%M")
    with (out_dir / "tracking_stops.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Load Number", "Carrier", "Stop Sequence", "Stop Name", "Stop Type",
                    "Scheduled Appointment", "Actual Arrival", "Actual Departure", "Tracking Method"])
        for r in tracking_rows:
            w.writerow([r[0], r[1], r[2], r[3], r[4], fmt(r[5]), fmt(r[6]), fmt(r[7]), "ELD integration"])
    with (out_dir / "fines_schedule.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["code", "description", "amount", "applies_to"])
        for c, d, a in FINES_SCHEDULE:
            w.writerow([c, d, f"{a / 100:.2f}", "brokered"])
    with (out_dir / "documents.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["load_id", "doc_type", "received_at"])
        for r in doc_rows:
            w.writerow([r[0], r[1], fmt(r[2])])
    with (out_dir / "disputes.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["load_id", "fine_code", "received_at", "reason"])
        for r in dispute_rows:
            w.writerow([r[0], r[1], fmt(r[2]), r[3]])
    with (out_dir / "loads.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["load_id", "customer", "carrier", "tractor", "trailer", "pod_received", "ratecon_file", "mode"])
        w.writerows(loads)
    with (out_dir / "carrier_invoices.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["invoice_no", "load_id", "carrier", "invoice_date", "invoice_total", "line_code", "line_amount"])
        w.writerows(invoice_rows)
    (out_dir / "expected.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    (out_dir / "README_SYNTHETIC.txt").write_text(
        "SYNTHETIC DATA. All companies, facilities, drivers, units and amounts are fictional,\n"
        f"generated by freightpkt.synth (seed={seed}). expected.json is the answer key.\n", encoding="utf-8")
    return expected
