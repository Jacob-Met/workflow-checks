"""Visit/auth ledger and worklist rules.

Ledger: each non-cancelled visit is assigned to the approved auth for the same
patient+payer whose window covers the visit date and that still has capacity
(earliest-ending first). Completed visits consume first, then scheduled ones in
date order, so "remaining after scheduled" shows when an auth will run out.

Worklist reason codes (P1 = act today, P2 = act this week, P3 = heads-up):
  UNCOVERED_VISIT       scheduled visit with no approved auth that covers it   P1 if within 7 days else P2
  UNAUTHORIZED_DONE     completed visit with no auth (billing/denial risk)     P1
  REAUTH_BY_VISITS      remaining visits <= payer threshold, visits continue   P2 (P1 if submit-by passed)
  REAUTH_BY_DATE        days to auth end <= payer threshold, visits continue   P2 (P1 if submit-by passed)
  PENDING_FOLLOWUP      pending auth covers upcoming visits                    P2
  ANNUAL_LIMIT          calendar-year visits near payer annual cap             P3 (P2 if scheduled visits exceed it)
  UNKNOWN_PAYER         payer id missing from payers.csv; rules not checked    P2
An auth whose successor (approved or pending, starting no earlier and ending
later) already exists is not re-flagged for REAUTH_* — that work is in progress.

Input clean-up: a visit_id that appears more than once (appended weekly exports)
counts once, using its last row. Rows sharing an auth_no for the same
patient/payer with overlapping windows are amendments: the last row wins. The
same auth_no over separate windows is kept as separate periods, labeled
"<auth_no> (<start>..<end>)".
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, timedelta

from .data import Auth, Patient, PayerRule, Visit

ACTIVE = ("completed", "scheduled")


def _dedupe_visits(visits: list[Visit]) -> list[Visit]:
    last = {v.visit_id: v for v in visits if v.visit_id}
    return [v for v in visits if not v.visit_id or last[v.visit_id] is v]


def _resolve_auths(auths: list[Auth]) -> list[Auth]:
    out: list[Auth] = []
    for a in auths:
        i = next((i for i, b in enumerate(out) if b.auth_no == a.auth_no and b.patient_id == a.patient_id
                  and b.payer_id == a.payer_id and b.start <= a.end and a.start <= b.end), None)
        if i is None:
            out.append(a)
        else:
            out[i] = a
    dup = Counter(a.auth_no for a in out)
    seen: set[str] = set()
    for i, a in enumerate(out):
        if dup[a.auth_no] > 1:
            label = f"{a.auth_no} ({a.start}..{a.end})"
            while label in seen:
                label += "*"
            out[i] = replace(a, auth_no=label)
        seen.add(out[i].auth_no)
    return out


@dataclass
class AuthLedger:
    auth: Auth
    used: list[Visit] = field(default_factory=list)
    scheduled: list[Visit] = field(default_factory=list)

    @property
    def remaining(self) -> int:
        return self.auth.visits_authorized - len(self.used)

    @property
    def remaining_after_scheduled(self) -> int:
        return self.remaining - len(self.scheduled)


@dataclass
class WorkItem:
    patient_id: str
    patient_name: str
    clinic: str
    payer_id: str
    payer_name: str
    auth_no: str
    priority: str
    reasons: list[str]
    detail: list[str]
    visits_used: int | None = None
    visits_authorized: int | None = None
    visits_remaining: int | None = None
    scheduled_in_window: int | None = None
    auth_end: date | None = None
    days_left: int | None = None
    next_visit: date | None = None
    submit_by: date | None = None
    checklist: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.patient_id}|{self.payer_id}|{self.auth_no}"


@dataclass
class VisitStatusItem:
    visit_id: str
    patient_id: str
    patient_name: str
    clinic: str
    payer_id: str
    payer_name: str
    visit_date: date
    days_since: int
    visit_type: str
    auth_no: str
    capacity_note: str
    evidence: str


def _counts(v: Visit, rule: PayerRule | None) -> bool:
    return not (v.visit_type == "eval" and rule is not None and not rule.counts_evals)


def build_ledger(visits: list[Visit], auths: list[Auth], payers: dict[str, PayerRule], as_of: date):
    """Returns (ledgers by auth_no, uncovered visits list)."""
    visits, auths = _dedupe_visits(visits), _resolve_auths(auths)
    approved = defaultdict(list)
    for a in auths:
        if a.status == "approved":
            approved[(a.patient_id, a.payer_id)].append(a)
    for lst in approved.values():
        lst.sort(key=lambda a: (a.end, a.start))
    ledgers = {a.auth_no: AuthLedger(a) for lst in approved.values() for a in lst}
    uncovered: list[Visit] = []

    active = sorted((v for v in visits if v.status in ACTIVE),
                    key=lambda v: (v.status != "completed", v.visit_date, v.visit_id))
    for v in active:
        rule = payers.get(v.payer_id)
        if rule is not None and not rule.requires_auth:
            continue
        if not _counts(v, rule):
            continue
        is_done = v.status == "completed"
        home = None
        for a in approved.get((v.patient_id, v.payer_id), []):
            led = ledgers[a.auth_no]
            if a.covers(v.visit_date) and led.remaining_after_scheduled > 0:
                home = led
                break
        if home is None:
            uncovered.append(v)
        elif is_done:
            home.used.append(v)
        else:
            home.scheduled.append(v)
    return ledgers, uncovered


def build_visit_status_review(visits: list[Visit], ledgers: dict[str, AuthLedger],
                              payers: dict[str, PayerRule], patients: dict[str, Patient],
                              as_of: date) -> list[VisitStatusItem]:
    """Project past scheduled CSV visits and their actual existing ledger allocation.

    CSV visit IDs are required; the same last-row rule used by the ledger applies.
    This review never changes a visit status or an authorization reservation.
    """
    reserved = {v.visit_id: led.auth.auth_no for led in ledgers.values() for v in led.scheduled}
    rows = []
    for v in sorted(_dedupe_visits(visits), key=lambda v: (v.visit_date, v.patient_id, v.visit_id)):
        if v.status != "scheduled" or v.visit_date >= as_of:
            continue
        patient, rule = patients.get(v.patient_id), payers.get(v.payer_id)
        auth_no = reserved.get(v.visit_id, "")
        if auth_no:
            note = "Reserves one authorized visit"
        elif rule is not None and not rule.requires_auth:
            note = "Payer does not require authorization"
        elif not _counts(v, rule):
            note = "Evaluation excluded by payer rule"
        else:
            note = "No approved authorization visit allocated"
        rows.append(VisitStatusItem(
            v.visit_id, v.patient_id, patient.display_name if patient else v.patient_id,
            v.clinic or (patient.clinic if patient else ""), v.payer_id,
            rule.payer_name if rule else v.payer_id, v.visit_date, (as_of - v.visit_date).days,
            v.visit_type, auth_no, note, v.source_row))
    return rows


PRIO_ORDER = {"P1": 0, "P2": 1, "P3": 2}


def build_worklist(visits: list[Visit], auths: list[Auth], payers: dict[str, PayerRule],
                   patients: dict[str, Patient], as_of: date):
    visits, auths = _dedupe_visits(visits), _resolve_auths(auths)
    ledgers, uncovered = build_ledger(visits, auths, payers, as_of)
    items: dict[str, WorkItem] = {}

    def item(pid, payer_id, auth_no="") -> WorkItem:
        key = f"{pid}|{payer_id}|{auth_no}"
        if key not in items:
            p = patients.get(pid)
            rule = payers.get(payer_id)
            items[key] = WorkItem(pid, p.display_name if p else pid, p.clinic if p else "",
                                  payer_id, rule.payer_name if rule else payer_id, auth_no,
                                  "P3", [], [], checklist=list(rule.checklist) if rule else [])
        return items[key]

    def bump(it: WorkItem, prio: str):
        if PRIO_ORDER[prio] < PRIO_ORDER[it.priority]:
            it.priority = prio

    # successors: an approved/pending auth that starts no earlier and ends later than this one
    # (an older, longer auth is not a renewal, even if its end date is later)
    by_pp = defaultdict(list)
    for a in auths:
        if a.status in ("approved", "pending"):
            by_pp[(a.patient_id, a.payer_id)].append(a)

    def has_successor(a: Auth) -> Auth | None:
        return next((b for b in by_pp[(a.patient_id, a.payer_id)]
                     if b.auth_no != a.auth_no and b.start >= a.start and b.end > a.end), None)

    future = defaultdict(list)
    for v in visits:
        if v.status == "scheduled" and v.visit_date >= as_of:
            future[(v.patient_id, v.payer_id)].append(v)

    # 1) uncovered visits
    unc_by_item: dict[str, list[Visit]] = {}
    for v in uncovered:
        pending = next((a for a in auths if a.status == "pending" and a.patient_id == v.patient_id
                        and a.payer_id == v.payer_id and a.covers(v.visit_date)), None)
        # attach to the pending auth, else the patient's most recent approved auth,
        # so one patient/payer shows up as one work item
        latest = max((a for a in auths if a.status == "approved" and a.patient_id == v.patient_id
                      and a.payer_id == v.payer_id), key=lambda a: a.end, default=None)
        anchor = pending or latest
        it = item(v.patient_id, v.payer_id, anchor.auth_no if anchor else "")
        it.evidence.append(v.source_row)
        if v.status == "completed":
            if "UNAUTHORIZED_DONE" not in it.reasons:
                it.reasons.append("UNAUTHORIZED_DONE")
            it.detail.append(f"completed visit {v.visit_date} ({v.visit_id}) had no covering approved auth")
            bump(it, "P1")
            continue
        if v.visit_date < as_of:
            continue  # stale scheduled row in the past; not actionable
        code = "PENDING_FOLLOWUP" if pending else "UNCOVERED_VISIT"
        if code not in it.reasons:
            it.reasons.append(code)
        if pending:
            it.detail.append(f"visit {v.visit_date} relies on PENDING auth {pending.auth_no}; follow up with payer")
            bump(it, "P1" if (v.visit_date - as_of).days <= 2 else "P2")
        else:
            unc_by_item.setdefault(it.key, []).append(v)
            bump(it, "P1" if (v.visit_date - as_of).days <= 7 else "P2")
        it.next_visit = min(filter(None, [it.next_visit, v.visit_date]))
    for key, vs in unc_by_item.items():
        vs.sort(key=lambda x: x.visit_date)
        ids = ", ".join(x.visit_id for x in vs[:4]) + (" ..." if len(vs) > 4 else "")
        items[key].detail.insert(0, f"{len(vs)} scheduled visit(s) outside any approved auth, "
                                    f"first {vs[0].visit_date} ({ids})")

    # 2) re-auth thresholds per live auth
    for led in ledgers.values():
        a = led.auth
        rule = payers.get(a.payer_id)
        if rule is None or a.end < as_of or a.start > as_of + timedelta(days=30):
            continue
        succ = has_successor(a)
        days_left = (a.end - as_of).days
        continuing = [v for v in future[(a.patient_id, a.payer_id)] if v.visit_date >= as_of]
        reasons, detail = [], []
        if led.remaining <= rule.reauth_visits_before and continuing:
            reasons.append("REAUTH_BY_VISITS")
            detail.append(f"{led.remaining} of {a.visits_authorized} visits left "
                          f"(payer threshold {rule.reauth_visits_before})")
        if days_left <= rule.reauth_days_before and continuing:
            reasons.append("REAUTH_BY_DATE")
            detail.append(f"auth ends {a.end} ({days_left} days); "
                          f"{len(continuing)} visit(s) still scheduled")
        if led.remaining_after_scheduled < 0:
            detail.append(f"scheduled visits exceed remaining by {-led.remaining_after_scheduled}")
        if not reasons or succ is not None:
            continue
        it = item(a.patient_id, a.payer_id, a.auth_no)
        it.reasons += [r for r in reasons if r not in it.reasons]
        it.detail += detail
        it.evidence.append(a.source_row)
        # submit-by = the earlier of (auth end - turnaround) and (date of the visit that exhausts it - turnaround)
        exhaust = led.scheduled[led.remaining - 1].visit_date if 0 < led.remaining <= len(led.scheduled) else None
        cutoffs = [a.end] + ([exhaust] if exhaust else [])
        it.submit_by = min(cutoffs) - timedelta(days=rule.turnaround_days)
        bump(it, "P1" if it.submit_by <= as_of or led.remaining <= 0 else "P2")

    # 2b) payers missing from the rules table: re-auth thresholds above could not be checked
    unknown = {(v.patient_id, v.payer_id) for v in visits
               if v.payer_id not in payers and v.status == "scheduled" and v.visit_date >= as_of}
    unknown |= {(a.patient_id, a.payer_id) for a in auths
                if a.payer_id not in payers and a.status in ("approved", "pending") and a.end >= as_of}
    for pid, payer_id in sorted(unknown):
        anchor = max((a for a in auths if a.status == "approved" and a.patient_id == pid
                      and a.payer_id == payer_id), key=lambda a: a.end, default=None)
        it = item(pid, payer_id, anchor.auth_no if anchor else "")
        it.reasons.append("UNKNOWN_PAYER")
        it.detail.append(f"payer {payer_id} is not in payers.csv; add its rules - "
                         f"re-auth thresholds and turnaround were not checked")
        bump(it, "P2")

    # 3) populate ledger numbers on every item that references an auth
    for it in items.values():
        led = ledgers.get(it.auth_no)
        if led:
            a = led.auth
            it.visits_used, it.visits_authorized = len(led.used), a.visits_authorized
            it.visits_remaining, it.scheduled_in_window = led.remaining, len(led.scheduled)
            it.auth_end, it.days_left = a.end, (a.end - as_of).days
        nxt = sorted(v.visit_date for v in future[(it.patient_id, it.payer_id)])
        it.next_visit = nxt[0] if nxt else it.next_visit

    # 4) annual visit limits (calendar year)
    year = defaultdict(lambda: [0, 0])
    for v in visits:
        if v.visit_date.year == as_of.year and v.status in ACTIVE:
            year[(v.patient_id, v.payer_id)][0 if v.status == "completed" else 1] += 1
    for (pid, payer_id), (done, sched) in year.items():
        rule = payers.get(payer_id)
        if not rule or not rule.annual_visit_limit:
            continue
        lim = rule.annual_visit_limit
        if done + sched > lim or lim - done <= 3:
            existing = [x for x in items.values() if x.patient_id == pid and x.payer_id == payer_id]
            it = existing[0] if existing else item(pid, payer_id)
            it.reasons.append("ANNUAL_LIMIT")
            it.detail.append(f"{done} visits used of {lim}/yr payer limit; {sched} more scheduled")
            bump(it, "P2" if done + sched > lim else "P3")

    # Past scheduled rows may anchor annual-limit alerts; keep that context until
    # all rules finish, then omit any placeholders that still have no reason.
    out = sorted((it for it in items.values() if it.reasons),
                 key=lambda x: (PRIO_ORDER[x.priority], x.submit_by or date.max,
                                x.next_visit or date.max, x.patient_id))
    return out, ledgers, uncovered
