"""End-to-end run: ingest -> detention -> invoice match -> packets + reports.

Output directory layout:
  summary.json            machine-readable run result (also feeds the web UI)
  detention_claims.csv    one row per stop with billable detention
  invoice_flags.csv       invoice vs rate-con vs POD mismatches
  exceptions.csv          anything a human must look at before claiming
  packets/<LOAD>.html     draft detention/chargeback packet (print to PDF)
  audit.jsonl             append-only decision log with evidence pointers
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import ingest
from .detention import StopResult, evaluate_load
from .invoice_match import Flag, match_invoices
from .models import money, to_dict
from .packet import render_packet
from .packet_names import packet_filenames


def audit(out_dir: Path, action: str, **data) -> None:
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "action": action, **data}
    with (out_dir / "audit.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, default=str) + "\n")


def _find_telematics(data_dir: Path) -> list[Path]:
    return sorted([*data_dir.glob("telematics*.csv"), *data_dir.glob("telematics*.json")])


def run(data_dir: Path, out_dir: Path, run_by: str = "cli") -> dict:
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    (out_dir / "packets").mkdir(parents=True, exist_ok=True)

    events = []
    for p in _find_telematics(data_dir):
        events.extend(ingest.load_telematics(p))
    tracking_files = sorted(data_dir.glob("tracking*.csv"))
    for p in tracking_files:
        events.extend(ingest.load_tracking_stops(p))
    events.sort(key=lambda e: (e.asset, e.time))
    loads = {l.load_id: l for l in ingest.load_loads(data_dir / "loads.csv")}
    ratecons = {}
    from .ratecon import load_ratecon
    for l in loads.values():
        p = data_dir / "ratecons" / l.ratecon_file
        if l.ratecon_file and p.exists():
            rc = load_ratecon(p)
            if rc.load_id and rc.load_id != l.load_id:
                rc.parse_warnings.append(f"rate-con load # {rc.load_id} != TMS load {l.load_id}")
            ratecons[l.load_id] = rc
    invoices = ingest.load_invoices(data_dir / "carrier_invoices.csv") \
        if (data_dir / "carrier_invoices.csv").exists() else []

    audit(out_dir, "run_start", run_by=run_by, data_dir=str(data_dir),
          tracking_files=[p.name for p in tracking_files], n_events=len(events), n_loads=len(loads), n_ratecons=len(ratecons), n_invoices=len(invoices))

    stop_results: list[StopResult] = []
    exceptions = []
    for lid, load in loads.items():
        rc = ratecons.get(lid)
        if rc is None:
            exceptions.append({"load_id": lid, "stop": "", "reason": "no rate-con file found",
                               "evidence": load.source_row})
            continue
        for r in evaluate_load(load, rc, events):
            stop_results.append(r)
            if r.status == "exception":
                exceptions.append({"load_id": lid, "stop": r.stop_index,
                                   "reason": "; ".join(r.notes),
                                   "evidence": ";".join(x for x in (r.arrival_src, r.departure_src, rc.source) if x)})
            audit(out_dir, "stop_evaluated", load_id=lid, stop=r.stop_index, status=r.status,
                  billable_minutes=r.billable_minutes, amount_cents=r.amount_cents,
                  claim_id=r.claim_id if r.status == "detention" else None,
                  evidence=[r.arrival_src, r.departure_src, rc.source])

    supported = defaultdict(int)
    for r in stop_results:
        if r.status == "detention":
            supported[r.load_id] += r.amount_cents

    flags = match_invoices(invoices, loads, ratecons, supported)
    for f in flags:
        audit(out_dir, "invoice_flag", invoice_no=f.invoice_no, load_id=f.load_id,
              code=f.code, detail=f.detail, evidence=f.evidence)

    # Packets: one per load with billable detention or a late-arrival chargeback.
    by_load = defaultdict(list)
    for r in stop_results:
        by_load[r.load_id].append(r)
    packet_names = packet_filenames(
        lid for lid, rs in by_load.items()
        if any(r.status in ("detention", "late_arrival") for r in rs)
    )
    packets = []
    for lid, rs in by_load.items():
        if lid not in packet_names:
            continue
        load, rc = loads[lid], ratecons[lid]
        if load.mode == "brokered":
            assets = {load.load_id}
        elif load.mode == "asset":
            assets = {load.tractor, load.trailer} - {""}
        else:
            assets = {load.tractor, load.trailer, load.load_id} - {""}
        times = [t for r in rs for t in (r.arrival, r.departure) if t]
        lo, hi = min(times), max(times)
        timeline = [e for e in events if e.asset in assets and lo <= e.time <= hi]
        inv_flags = [f for f in flags if f.load_id == lid]
        html = render_packet(load, rc, rs, timeline, inv_flags,
                             synthetic=(data_dir / "README_SYNTHETIC.txt").exists())
        path = out_dir / "packets" / packet_names[lid]
        path.write_text(html, encoding="utf-8")
        total = sum(r.amount_cents for r in rs if r.status == "detention")
        packets.append({"load_id": lid, "file": f"packets/{packet_names[lid]}", "detention_cents": total,
                        "claim_ids": [r.claim_id for r in rs if r.status == "detention"],
                        "late_stops": [r.stop_index for r in rs if r.status == "late_arrival"]})
        audit(out_dir, "packet_drafted", load_id=lid, file=str(path.name), detention_cents=total,
              status="DRAFT_PENDING_APPROVAL")

    # Fines matrix + settlement worksheet (only when a fines schedule is supplied).
    fines, settlements = [], []
    sched_path = data_dir / "fines_schedule.csv"
    if sched_path.exists():
        from .fines import assess_fines, load_disputes, load_documents, load_schedule, settle
        docs_path = data_dir / "documents.csv"
        fines, fine_exc = assess_fines(loads, by_load, load_schedule(sched_path),
                                       load_documents(docs_path), load_disputes(data_dir / "disputes.csv"),
                                       invoices, docs_path.exists())
        exceptions.extend(fine_exc)
        for f in fines:
            audit(out_dir, "fine_assessed", fine_id=f.fine_id, load_id=f.load_id, code=f.code,
                  amount_cents=f.amount_cents, status=f.status, evidence=f.evidence)
        settlements = settle(invoices, loads, ratecons, supported, flags, fines, by_load)
        for st in settlements:
            audit(out_dir, "settlement_line", invoice_no=st.invoice_no, load_id=st.load_id,
                  approved_cents=st.approved_cents, fines_cents=st.fines_cents, net_cents=st.net_cents,
                  status=st.status, hold_reasons=st.hold_reasons)
        _write_csv(out_dir / "fines.csv",
                   ["fine_id", "load_id", "carrier", "code", "amount", "detail", "notice_date",
                    "dispute_deadline", "status", "dispute_note", "evidence"],
                   [[f.fine_id, f.load_id, f.carrier, f.code, money(f.amount_cents), f.detail, f.notice_date,
                     f.dispute_deadline, f.status, f.dispute_note, ";".join(f.evidence)] for f in fines])
        _write_csv(out_dir / "settlement.csv",
                   ["invoice_no", "load_id", "carrier", "invoiced", "approved", "fines", "net_payable",
                    "status", "hold_reasons", "notes", "evidence"],
                   [[s.invoice_no, s.load_id, s.carrier, money(s.invoiced_cents), money(s.approved_cents),
                     money(s.fines_cents), money(s.net_cents), s.status, ";".join(s.hold_reasons),
                     "; ".join(s.notes), ";".join(s.evidence)] for s in settlements])

    _write_csv(out_dir / "detention_claims.csv",
               ["claim_id", "load_id", "customer", "stop", "kind", "facility", "appointment", "arrival",
                "departure", "dwell_min", "free_min", "billable_min", "rate_per_hr", "amount", "capped",
                "arrival_evidence", "departure_evidence", "ratecon"],
               [[r.claim_id, r.load_id, loads[r.load_id].customer, r.stop_index, r.kind, r.facility,
                 r.appointment, r.arrival, r.departure, r.dwell_minutes, r.free_minutes,
                 r.billable_minutes, money(ratecons[r.load_id].detention_rate_cents),
                 money(r.amount_cents), r.capped, r.arrival_src, r.departure_src,
                 ratecons[r.load_id].source]
                for r in stop_results if r.status == "detention"])
    _write_csv(out_dir / "invoice_flags.csv",
               ["invoice_no", "load_id", "carrier", "flag", "detail", "invoiced", "expected",
                "variance", "evidence"],
               [[f.invoice_no, f.load_id, f.carrier, f.code, f.detail, money(f.invoiced_cents),
                 money(f.expected_cents), money(f.variance_cents), ";".join(f.evidence)]
                for f in flags])
    _write_csv(out_dir / "exceptions.csv", ["load_id", "stop", "reason", "evidence"],
               [[x["load_id"], x["stop"], x["reason"], x["evidence"]] for x in exceptions])

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_dir": str(data_dir),
        "counts": {"events": len(events), "loads": len(loads), "stops": len(stop_results),
                   "detention_stops": sum(r.status == "detention" for r in stop_results),
                   "late_arrivals": sum(r.status == "late_arrival" for r in stop_results),
                   "exceptions": len(exceptions), "invoices": len(invoices),
                   "invoice_flags": len(flags), "packets": len(packets),
                   "fines": len(fines), "settlement_ready": sum(s.status == "READY" for s in settlements),
                   "settlement_hold": sum(s.status == "HOLD" for s in settlements)},
        "fines_total_cents": sum(f.deducted_cents for f in fines),
        "net_payable_ready_cents": sum(s.net_cents for s in settlements if s.status == "READY"),
        "fines": [{**to_dict(f), "fine_id": f.fine_id, "deducted_cents": f.deducted_cents} for f in fines],
        "settlements": [to_dict(s) for s in settlements],
        "detention_total_cents": sum(supported.values()),
        "detention_total": money(sum(supported.values())),
        "stops": [{**to_dict(r), "claim_id": r.claim_id} for r in stop_results],
        "flags": [{**to_dict(f), "variance_cents": f.variance_cents} for f in flags],
        "exceptions": exceptions,
        "packets": packets,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    audit(out_dir, "run_end", detention_total_cents=summary["detention_total_cents"],
          n_flags=len(flags), n_exceptions=len(exceptions), n_packets=len(packets))
    return summary


def _write_csv(path: Path, header, rows) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
