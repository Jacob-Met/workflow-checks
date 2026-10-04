"""Match rate-con stops to geofence events and compute detention.

Rules (configurable per customer in a real pilot; these are common defaults):
  * Arrival = first geofence ENTRY for the load's tractor at the stop's
    facility inside [appt - 12h, appt + 24h], after the previous stop's exit.
  * Free-time clock starts at max(arrival, appointment): early arrival does
    not earn detention.
  * Arrival later than appointment + grace forfeits detention and is flagged
    as a late arrival (possible late-fee chargeback / service failure).
  * Billable = (exit - clock_start - free), rounded DOWN to the increment.
  * Amount = billable_hours * hourly rate, capped per stop if the rate-con
    states a cap.
Anything ambiguous (no entry, no exit, rate-con parse warnings) becomes an
exception for a human, never a claim.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .models import Load, RateCon, StopEvent

WINDOW_BEFORE = timedelta(hours=12)
WINDOW_AFTER = timedelta(hours=24)


def norm_name(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\b(inc|llc|co|corp|dc|the)\b\.?", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def facility_match(a: str, b: str) -> bool:
    na, nb = norm_name(a), norm_name(b)
    return bool(na) and bool(nb) and (na == nb or na in nb or nb in na)


@dataclass
class StopResult:
    load_id: str
    stop_index: int
    kind: str
    facility: str
    appointment: datetime
    arrival: datetime | None = None
    departure: datetime | None = None
    arrival_src: str = ""
    departure_src: str = ""
    dwell_minutes: int | None = None
    clock_start: datetime | None = None
    free_minutes: int = 0
    over_free_minutes: int = 0
    billable_minutes: int = 0
    amount_cents: int = 0
    capped: bool = False
    status: str = "ok"          # ok | detention | late_arrival | exception
    notes: list[str] = field(default_factory=list)

    @property
    def claim_id(self) -> str:
        """Idempotency key: same evidence -> same claim id, so reruns never
        create duplicate packets."""
        raw = f"{self.load_id}|{self.stop_index}|{self.arrival}|{self.departure}|{self.amount_cents}"
        return "DET-" + hashlib.sha256(raw.encode()).hexdigest()[:10].upper()


def evaluate_load(load: Load, rc: RateCon, events: list[StopEvent]) -> list[StopResult]:
    # Own-fleet ELD events are keyed by tractor/trailer; stop-level tracking
    # exports (brokered loads) are keyed by the load number.
    if load.mode == "brokered":
        assets = {load.load_id}
    elif load.mode == "asset":
        assets = {a for a in (load.tractor, load.trailer) if a}
    else:
        assets = {a for a in (load.tractor, load.trailer, load.load_id) if a}
    mine = sorted((e for e in events if e.asset in assets), key=lambda e: e.time)
    results = []
    cursor = datetime.min
    for idx, stop in enumerate(rc.stops, start=1):
        r = StopResult(load.load_id, idx, stop.kind, stop.facility, stop.appointment,
                       free_minutes=rc.free_minutes)
        lo, hi = stop.appointment - WINDOW_BEFORE, stop.appointment + WINDOW_AFTER
        entry = next((e for e in mine if e.event == "entry" and e.time > cursor
                      and lo <= e.time <= hi and facility_match(e.location, stop.facility)), None)
        if entry is None:
            r.status = "exception"
            r.notes.append("no geofence entry found for this stop in the appointment window")
            results.append(r)
            continue
        r.arrival, r.arrival_src = entry.time, entry.source_row
        # The next event at this facility must be an exit within 24h; otherwise
        # the export has a gap and a human must look.
        exit_ = next((e for e in mine if e.asset == entry.asset and e.time > entry.time
                      and facility_match(e.location, stop.facility)
                      and (entry.source_kind != "tracking" or
                           (e.source_kind == "tracking" and e.source_row == entry.source_row))), None)
        if exit_ is not None and (exit_.event != "exit" or exit_.time - entry.time > WINDOW_AFTER):
            exit_ = None
        if exit_ is None:
            r.status = "exception"
            r.notes.append("geofence entry has no matching exit (export gap or still on site)")
            results.append(r)
            continue
        r.departure, r.departure_src = exit_.time, exit_.source_row
        cursor = exit_.time
        r.dwell_minutes = int((exit_.time - entry.time).total_seconds() // 60)

        late_by = (entry.time - stop.appointment).total_seconds() / 60
        if late_by > rc.late_grace_minutes:
            r.status = "late_arrival"
            r.notes.append(f"arrived {int(late_by)} min after appointment "
                           f"(grace {rc.late_grace_minutes} min): detention forfeited")
            if rc.parse_warnings:
                r.status = "exception"
                r.notes.append("rate-con parse warnings: " + "; ".join(rc.parse_warnings))
            results.append(r)
            continue

        r.clock_start = max(entry.time, stop.appointment)
        if entry.time < stop.appointment:
            r.notes.append(f"arrived {int(-late_by)} min early; free-time clock starts at appointment")
        on_clock = int((exit_.time - r.clock_start).total_seconds() // 60)
        r.over_free_minutes = max(0, on_clock - rc.free_minutes)
        inc = max(1, rc.increment_minutes)
        r.billable_minutes = (r.over_free_minutes // inc) * inc
        # Round half cents up using integer arithmetic; Python's round uses
        # banker's rounding and float arithmetic can distort monetary ties.
        amount = (rc.detention_rate_cents * r.billable_minutes + 30) // 60
        if rc.detention_cap_cents is not None and amount > rc.detention_cap_cents:
            amount, r.capped = rc.detention_cap_cents, True
            r.notes.append("capped at rate-con per-stop maximum")
        r.amount_cents = amount
        if amount > 0:
            r.status = "detention"
        if rc.parse_warnings:
            r.status = "exception"
            r.billable_minutes = 0
            r.amount_cents = 0
            r.capped = False
            r.notes.append("rate-con parse warnings: " + "; ".join(rc.parse_warnings))
        results.append(r)
    return results
