"""Generate synthetic examples and an oracle using the unchanged freight engine."""
from __future__ import annotations
import argparse
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys

DEMO = Path(__file__).resolve().parents[1]
REPO = DEMO.parents[1]
sys.path.insert(0, str(REPO / "freight_packets"))
from freightpkt.models import Invoice, InvoiceLine, Load, RateCon, RateConStop, StopEvent, to_dict
from freightpkt.detention import evaluate_load
from freightpkt.invoice_match import match_invoices

CORE = {
    "freight_packets/freightpkt/models.py": "8a24ed2cca6f45aa8a47d793620b0e2e4d573ec92209954d3f3156795e3f0e05",
    "freight_packets/freightpkt/detention.py": "31ca31fd3210ff680bc83291916e39ea19b82580c3a090720556afd4ef0cd76b",
    "freight_packets/freightpkt/invoice_match.py": "37a9e0801de948c3b558ca7c9846b3d0eb76ec062703ee3e5132df273ff569ab",
}
BASELINE = "2f1e5f777197eedd69d51a4d81c0da744b65ad88"
CONTRACT = {
    "load_id": "DEMO-104", "invoice_no": "DEMO-INV-104",
    "ratecon_no": "DEMO-RC-104", "customer": "Example Distribution",
    "carrier": "Example Freight", "facility": "Sample receiving dock",
    "linehaul_cents": 145000, "fuel_cents": 24500, "lumper_cents": 15000,
    "warning": "synthetic rate confirmation marked incomplete",
}
BASE = {
    "appointment": "2026-09-07T09:00", "arrival": "2026-09-07T08:45",
    "departure": "2026-09-07T12:45", "free_minutes": 120,
    "increment_minutes": 15, "late_grace_minutes": 15,
    "detention_rate_cents": 7500, "detention_cap_cents": 30000,
    "linehaul_cents": 145000, "fuel_cents": 24500,
    "detention_cents": 15000, "lumper_cents": 15000, "tonu_cents": 0,
    "invoice_total_cents": None, "pod_received": True, "ratecon_complete": True,
}
def scenario(**changes):
    return dict(deepcopy(BASE), **changes)

PRESETS = [
    {"id": "long-dwell", "title": "Long dwell", "description": "An early arrival, a long stop and a detention line to review.", "scenario": scenario()},
    {"id": "within-free", "title": "Within free time", "description": "A clean single-stop example with no detention charge.", "scenario": scenario(arrival="2026-09-07T09:00", departure="2026-09-07T10:45", detention_cents=0)},
    {"id": "late-arrival", "title": "Late arrival", "description": "One minute past the grace period changes eligibility.", "scenario": scenario(arrival="2026-09-07T09:16", departure="2026-09-07T13:16")},
    {"id": "missing-exit", "title": "Missing departure", "description": "Incomplete tracking needs a person to resolve the gap.", "scenario": scenario(departure=None)},
]
def evaluate(s):
    c = CONTRACT
    appointment = datetime.fromisoformat(s["appointment"])
    load = Load(c["load_id"], c["customer"], c["carrier"], "", "", s["pod_received"],
                "scenario:ratecon", source_row="scenario:load", mode="brokered")
    rc = RateCon(
        c["load_id"], c["ratecon_no"], c["customer"], c["carrier"],
        c["linehaul_cents"], c["fuel_cents"], s["detention_rate_cents"],
        s["free_minutes"], s["increment_minutes"], s["detention_cap_cents"],
        s["late_grace_minutes"], accessorials_cents={"LUMPER": c["lumper_cents"]},
        stops=[RateConStop("delivery", c["facility"], appointment)], source="scenario:ratecon",
        parse_warnings=[] if s["ratecon_complete"] else [c["warning"]])
    events = [StopEvent(c["load_id"], c["facility"], event, datetime.fromisoformat(s[key]),
                       source_row="scenario:tracking", source_kind="tracking")
              for key, event in [("arrival", "entry"), ("departure", "exit")] if s[key] is not None]
    stop = evaluate_load(load, rc, events)[0]
    lines = [InvoiceLine(code, s[key]) for code, key in
             [("LINEHAUL", "linehaul_cents"), ("FUEL", "fuel_cents"),
              ("DETENTION", "detention_cents"), ("LUMPER", "lumper_cents")]]
    if s["tonu_cents"] > 0:
        lines.append(InvoiceLine("TONU", s["tonu_cents"]))
    line_sum = sum(line.amount_cents for line in lines)
    total = line_sum if s["invoice_total_cents"] is None else s["invoice_total_cents"]
    inv = Invoice(c["invoice_no"], c["load_id"], c["carrier"], "2026-09-07", total,
                  lines=lines, source_row="scenario:invoice")
    flags = match_invoices([inv], {load.load_id: load}, {load.load_id: rc},
                           {load.load_id: stop.amount_cents})
    return {"stop": to_dict(stop), "flags": [to_dict(f) for f in flags],
            "totals": {"line_sum_cents": line_sum, "invoice_total_cents": total,
                       "supported_detention_cents": stop.amount_cents}}

def cases():
    out = []
    def add(name, **changes):
        s = scenario(**changes)
        out.append({"id": name, "scenario": s, "expected": evaluate(s)})
    for preset in PRESETS:
        s = preset["scenario"]
        out.append({"id": "preset-" + preset["id"], "scenario": s, "expected": evaluate(s)})
    appt = datetime.fromisoformat(BASE["appointment"])
    for offset in [-721, -720, -1, 0, 15, 16, 1440, 1441]:
        for dwell in [-1, 0, 1, 119, 120, 134, 135, 1440, 1441]:
            a = appt + timedelta(minutes=offset)
            d = a + timedelta(minutes=dwell)
            add(f"window-{offset}-dwell-{dwell}", arrival=a.isoformat(timespec="minutes"),
                departure=d.isoformat(timespec="minutes"))
    for free in [0, 119, 120, 121, 1440]:
        for increment in [1, 15, 30, 60, 1440]:
            add(f"free-{free}-increment-{increment}", free_minutes=free, increment_minutes=increment)
    for rate in [0, 1, 29, 30, 31, 75, 7500, 100000]:
        for cap in [None, 0, 1, 10000, 100000000]:
            add(f"rate-{rate}-cap-{cap}", detention_rate_cents=rate, detention_cap_cents=cap,
                free_minutes=0, arrival=BASE["appointment"], departure="2026-09-07T09:01", increment_minutes=1)
    add("no-entry", arrival=None)
    add("no-events", arrival=None, departure=None)
    add("incomplete-ratecon", ratecon_complete=False)
    add("incomplete-late", ratecon_complete=False, arrival="2026-09-07T09:16")
    add("incomplete-capped", ratecon_complete=False, detention_cap_cents=1)
    add("exact-grace-and-cap", arrival="2026-09-07T09:15", departure="2026-09-07T13:15", detention_cap_cents=15000)
    add("maximum-grace", arrival="2026-09-08T09:00", departure="2026-09-08T13:00", late_grace_minutes=1440)
    for field in ["linehaul_cents", "fuel_cents", "detention_cents", "lumper_cents", "tonu_cents", "invoice_total_cents"]:
        for amount in [0, 1, 13125, 15001, 100000000]:
            add(f"invoice-{field}-{amount}", **{field: amount})
    add("missing-pod", pod_received=False)
    add("many-findings", linehaul_cents=145001, fuel_cents=24501, detention_cents=20000,
        lumper_cents=15001, tonu_cents=25000, pod_received=False, invoice_total_cents=1)
    for stamp in ["1900-01-01T00:00", "2000-02-29T23:00", "2026-03-08T01:30", "2026-11-01T01:30", "2100-12-31T00:00"]:
        a = datetime.fromisoformat(stamp)
        add("civil-" + stamp, appointment=stamp, arrival=stamp,
            departure=(a + timedelta(hours=4)).isoformat(timespec="minutes"))
    return out

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Compare generated bytes; do not write")
    args = parser.parse_args()
    pins = {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in CORE}
    if pins != CORE:
        raise SystemExit("Freight source changed: explicitly review and refresh the oracle before building")
    provenance = {"baseline_commit": BASELINE, "source_sha256": pins,
                  "oracle": "freightpkt.detention.evaluate_load + freightpkt.invoice_match.match_invoices",
                  "scope": "One authored brokered stop, one tracking pair, one known rate confirmation and one invoice. Civil minute times; USD integer cents."}
    data = {"contract": CONTRACT, "presets": PRESETS, "provenance": provenance}
    fixtures = {"schema": "freight-whatif.oracle.v1", "provenance": provenance, "cases": cases()}
    outputs = {
        DEMO / "site/data.mjs": "// Generated by tools/build_fixtures.py from authored synthetic scenarios.\nexport const data = " + json.dumps(data, indent=2) + ";\n",
        DEMO / "tests/oracle.json": json.dumps(fixtures, indent=2) + "\n",
    }
    for path, text in outputs.items():
        payload = text.encode()
        if args.check:
            if not path.is_file() or path.read_bytes() != payload:
                raise SystemExit(f"Generated bytes differ: {path}")
        else:
            path.write_bytes(payload)
    assert {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in CORE} == CORE
    print(json.dumps({"cases": len(fixtures["cases"]), "check_only": args.check, "core_unchanged": True,
                      "generated_sha256": {str(p.relative_to(DEMO)): hashlib.sha256(t.encode()).hexdigest() for p,t in outputs.items()},
                      "python": sys.version.split()[0]}))
if __name__ == "__main__":
    main()
