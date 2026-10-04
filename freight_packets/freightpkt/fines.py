"""Carrier fines matrix + settlement worksheet (brokered loads).

Brokers that run outside carriers typically publish a carrier fines schedule
(missing compliance photos, late POD, tracking not maintained, late
pickup/delivery) and give carriers a fixed dispute window. This module:

  * assesses fines ONLY from evidence on file (tracking stop events, the
    document log, the detention engine's late-arrival findings);
  * never guesses: if the evidence needed to judge a rule is missing
    (e.g. final departure unknown, so POD lateness can't be measured) the
    load goes to the exception queue instead of being fined;
  * tracks disputes against a dispute window (default 7 days from notice);
    a fine disputed inside the window is held, not deducted;
  * builds a settlement worksheet per carrier invoice: approved amount
    (capped at rate-con / telematics-supported values), fines deducted,
    net payable, and READY / HOLD for finance and factoring.

Inputs (all optional; no fines_schedule.csv = module is skipped):
  fines_schedule.csv   code,description,amount,applies_to
  documents.csv        load_id,doc_type,received_at      (POD, PICKUP_PHOTOS, DELIVERY_PHOTOS)
  disputes.csv         load_id,fine_code,received_at,reason
"""
from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .detention import StopResult
from .ingest import dollars_to_cents, parse_time
from .invoice_match import Flag
from .models import Invoice, Load, RateCon

POD_DEADLINE = timedelta(hours=48)
DISPUTE_WINDOW = timedelta(days=7)
PHOTO_RULES = {"MISSING_PICKUP_PHOTOS": "PICKUP_PHOTOS", "MISSING_DELIVERY_PHOTOS": "DELIVERY_PHOTOS"}


@dataclass
class Fine:
    load_id: str
    carrier: str
    code: str
    amount_cents: int
    detail: str
    notice_date: str = ""
    dispute_deadline: str = ""
    status: str = "assessed"      # assessed | disputed_in_window | dispute_late
    dispute_note: str = ""
    evidence: list[str] = field(default_factory=list)

    @property
    def fine_id(self) -> str:
        raw = f"{self.load_id}|{self.code}|{self.amount_cents}|{'|'.join(self.evidence)}"
        return "FINE-" + hashlib.sha256(raw.encode()).hexdigest()[:10].upper()

    @property
    def deducted_cents(self) -> int:
        return 0 if self.status == "disputed_in_window" else self.amount_cents


def load_schedule(path: Path) -> dict[str, dict]:
    out = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as fh:
        for i, r in enumerate(csv.DictReader(fh), start=2):
            out[r["code"].strip().upper()] = {
                "description": r.get("description", "").strip(),
                "amount_cents": dollars_to_cents(r["amount"]),
                "applies_to": (r.get("applies_to") or "brokered").strip().lower(),
                "source": f"{Path(path).name}:row{i}",
            }
    return out


def load_documents(path: Path) -> dict[str, dict[str, tuple[datetime, str]]]:
    """load_id -> doc_type -> (earliest received_at, evidence pointer)."""
    docs: dict[str, dict[str, tuple[datetime, str]]] = defaultdict(dict)
    p = Path(path)
    if not p.exists():
        return docs
    with p.open(newline="", encoding="utf-8-sig") as fh:
        for i, r in enumerate(csv.DictReader(fh), start=2):
            lid, typ = r["load_id"].strip(), r["doc_type"].strip().upper()
            at = parse_time(r["received_at"])
            cur = docs[lid].get(typ)
            if cur is None or at < cur[0]:
                docs[lid][typ] = (at, f"{p.name}:row{i}")
    return docs


def load_disputes(path: Path) -> dict[tuple[str, str], tuple[datetime, str, str]]:
    out = {}
    p = Path(path)
    if not p.exists():
        return out
    with p.open(newline="", encoding="utf-8-sig") as fh:
        for i, r in enumerate(csv.DictReader(fh), start=2):
            key = (r["load_id"].strip(), r["fine_code"].strip().upper())
            dispute = (parse_time(r["received_at"]), r.get("reason", "").strip(), f"{p.name}:row{i}")
            if key not in out or dispute[0] < out[key][0]:
                out[key] = dispute
    return out


def assess_fines(loads: dict[str, Load], stops_by_load: dict[str, list[StopResult]],
                 schedule: dict[str, dict], docs, disputes, invoices: list[Invoice],
                 has_documents: bool) -> tuple[list[Fine], list[dict]]:
    fines: list[Fine] = []
    exceptions: list[dict] = []
    notice_by_load = {}
    for inv in invoices:
        notice_by_load.setdefault(inv.load_id, inv.invoice_date)

    for lid, load in loads.items():
        rs = stops_by_load.get(lid, [])
        if not rs:
            continue
        if load.mode != "brokered":
            continue  # own fleet: driver compliance is an internal matter, not a carrier fine

        def add(code, detail, evidence):
            rule = schedule.get(code)
            if rule is None or rule["applies_to"] not in ("brokered", "all"):
                return
            fines.append(Fine(lid, load.carrier, code, rule["amount_cents"], detail,
                              evidence=[e for e in evidence if e] + [rule["source"]]))

        # Service failures, from the detention engine's findings.
        for r in rs:
            if r.status == "late_arrival":
                code = "LATE_PICKUP" if r.kind == "pickup" else "LATE_DELIVERY"
                add(code, f"stop {r.stop_index} {r.facility}: appointment {r.appointment:%Y-%m-%d %H:%M}, "
                          f"arrived {r.arrival:%Y-%m-%d %H:%M}", [r.arrival_src])
            elif r.status == "exception" and r.arrival is not None and r.departure is None:
                add("TRACKING_GAP", f"stop {r.stop_index} {r.facility}: tracking shows arrival but no "
                                    f"departure (tracking not maintained)", [r.arrival_src])

        if not has_documents:
            continue
        ldocs = docs.get(lid, {})
        for code, typ in PHOTO_RULES.items():
            if typ not in ldocs:
                add(code, f"no {typ.replace('_', ' ').lower()} on file", [f"documents.csv (no {typ} row)"])

        final = rs[-1]
        pod = ldocs.get("POD")
        if pod is not None:
            if final.departure is None:
                exceptions.append({"load_id": lid, "stop": final.stop_index,
                                   "reason": "POD timeliness not measurable: final departure unknown",
                                   "evidence": pod[1]})
            elif pod[0] - final.departure > POD_DEADLINE:
                hrs = (pod[0] - final.departure).total_seconds() / 3600
                add("LATE_POD", f"POD received {pod[0]:%Y-%m-%d %H:%M}, {hrs:.0f}h after final departure "
                                f"(limit {POD_DEADLINE.total_seconds() / 3600:.0f}h)",
                    [pod[1], final.departure_src])

    for f in fines:
        notice = notice_by_load.get(f.load_id)
        if notice:
            nd = parse_time(notice)
            f.notice_date = nd.strftime("%Y-%m-%d")
            f.dispute_deadline = (nd + DISPUTE_WINDOW).strftime("%Y-%m-%d")
        d = disputes.get((f.load_id, f.code))
        if d is not None:
            at, reason, src = d
            f.evidence.append(src)
            if f.dispute_deadline and at.date() <= parse_time(f.dispute_deadline).date():
                f.status = "disputed_in_window"
                f.dispute_note = f"disputed {at:%Y-%m-%d} (inside window): {reason}; held pending review"
            else:
                f.status = "dispute_late"
                f.dispute_note = f"disputed {at:%Y-%m-%d} after window closed {f.dispute_deadline}: {reason}"
    fines.sort(key=lambda f: (f.load_id, f.code))
    return fines, exceptions


@dataclass
class Settlement:
    invoice_no: str
    load_id: str
    carrier: str
    invoiced_cents: int
    approved_cents: int
    fines_cents: int
    net_cents: int
    status: str                 # READY | HOLD
    hold_reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


def settle(invoices: list[Invoice], loads: dict[str, Load], ratecons: dict[str, RateCon],
           supported: dict[str, int], flags: list[Flag], fines: list[Fine],
           stops_by_load: dict[str, list[StopResult]]) -> list[Settlement]:
    dup = {(f.invoice_no, f.load_id) for f in flags if f.code == "DUPLICATE_INVOICE"}
    fines_by_load = defaultdict(list)
    for f in fines:
        fines_by_load[f.load_id].append(f)
    out = []
    for inv in invoices:
        load, rc = loads.get(inv.load_id), ratecons.get(inv.load_id)
        by_code = defaultdict(int)
        for ln in inv.lines:
            by_code[ln.code] += ln.amount_cents
        invoiced = sum(by_code.values())
        holds, notes = [], []
        approved = 0
        if rc is None:
            holds.append("NO_RATECON")
        elif rc.parse_warnings:
            holds.append("RATECON_PARSE_WARNING")
        else:
            approved += min(by_code.get("LINEHAUL", 0), rc.linehaul_cents)
            approved += min(by_code.get("FUEL", 0), rc.fuel_cents)
            approved += min(by_code.get("DETENTION", 0), supported.get(inv.load_id, 0))
            for code, amt in by_code.items():
                if code not in ("LINEHAUL", "FUEL", "DETENTION"):
                    approved += min(amt, rc.accessorials_cents.get(code, 0))
        if (inv.invoice_no, inv.load_id) in dup:
            holds.append("DUPLICATE_INVOICE")
            approved = 0
        if load is not None and not load.pod_received:
            holds.append("MISSING_POD")
        if by_code.get("DETENTION") and any(r.status == "exception" for r in stops_by_load.get(inv.load_id, [])):
            holds.append("DETENTION_PENDING_REVIEW")
        if inv.total_cents != invoiced:
            notes.append("header total differs from line sum; settled on lines")
        lf = [] if "DUPLICATE_INVOICE" in holds else fines_by_load.get(inv.load_id, [])
        fines_cents = sum(f.deducted_cents for f in lf)
        for f in lf:
            if f.status == "disputed_in_window":
                notes.append(f"{f.code} {f.fine_id} disputed in window: not deducted")
        if approved < invoiced and "DUPLICATE_INVOICE" not in holds:
            notes.append(f"short-pay vs invoice: see invoice flags")
        out.append(Settlement(inv.invoice_no, inv.load_id, inv.carrier, invoiced, approved, fines_cents,
                              approved - fines_cents, "HOLD" if holds else "READY", holds, notes,
                              [inv.source_row] + ([rc.source] if rc else [])))
    out.sort(key=lambda s: (s.load_id, s.invoice_no))
    return out
