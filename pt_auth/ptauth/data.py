"""Models + CSV loaders for the three inputs.

schedule.csv        visit_id, patient_id, visit_date, clinic, therapist, payer_id, status
                    status: completed | scheduled | cancelled | no_show
authorizations.csv  auth_no, patient_id, payer_id, visits_authorized, start_date, end_date, status
                    status: approved | pending | denied
payers.csv          payer_id, payer_name, requires_auth, reauth_visits_before, reauth_days_before,
                    turnaround_days, annual_visit_limit, counts_evals, checklist (pipe-separated)
patients.csv        patient_id, display_name, clinic, primary_payer   (synthetic only)

Loaders accept real-export quirks (BOM or cp1252 encoding, "Visit Date" style headers, blank or
comma-only rows, trailing commas, date+time values, common status synonyms) and raise InputError
naming the file and line for anything they cannot interpret, rather than guessing.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime, tzinfo
from pathlib import Path

# Time zone used to turn offset-bearing timestamps (e.g. "...T01:30:00Z") into a clinic calendar
# date. None = this machine's local time zone. Naive timestamps keep the date as written.
CLINIC_TZ: tzinfo | None = None


class InputError(ValueError):
    pass


@dataclass
class Visit:
    visit_id: str
    patient_id: str
    visit_date: date
    clinic: str
    therapist: str
    payer_id: str
    status: str
    visit_type: str = "treatment"   # eval | treatment | re-eval
    source_row: str = ""


@dataclass
class Auth:
    auth_no: str
    patient_id: str
    payer_id: str
    visits_authorized: int
    start: date
    end: date
    status: str
    source_row: str = ""

    def covers(self, d: date) -> bool:
        return self.start <= d <= self.end


@dataclass
class PayerRule:
    payer_id: str
    payer_name: str
    requires_auth: bool
    reauth_visits_before: int
    reauth_days_before: int
    turnaround_days: int
    annual_visit_limit: int | None
    counts_evals: bool
    checklist: list[str] = field(default_factory=list)


@dataclass
class Patient:
    patient_id: str
    display_name: str
    clinic: str
    primary_payer: str


_SLASH = re.compile(r"(\d{1,4})/(\d{1,2})/(\d{1,4})(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?)?")


def _d(s: str) -> date:
    s = s.strip()
    if not s:
        raise ValueError("date is blank")
    m = _SLASH.fullmatch(s)
    if m:
        a, b, c = m.group(1), m.group(2), m.group(3)
        if len(a) == 4:                       # YYYY/MM/DD
            y, mo, dd = int(a), int(b), int(c)
        elif len(c) in (2, 4):                # M/D/YYYY or M/D/YY (US exports)
            y, mo, dd = int(c) + (2000 if len(c) == 2 else 0), int(a), int(b)
        else:
            raise ValueError(f"unrecognized date {s!r}")
        try:
            return date(y, mo, dd)
        except ValueError:
            raise ValueError(f"invalid date {s!r} (expected month/day/year)") from None
    try:
        return date.fromisoformat(s)
    except ValueError:
        pass
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00") if s.endswith(("Z", "z")) else s)
    except ValueError:
        raise ValueError(f"unrecognized date {s!r} (use YYYY-MM-DD or M/D/YYYY)") from None
    if dt.tzinfo is not None:
        dt = dt.astimezone(CLINIC_TZ)
    return dt.date()


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _key(k: str) -> str:
    return re.sub(r"[\s\-]+", "_", k.strip().lower())


def _rows(path: Path):
    """Yields (file line number, getter, row) with normalized headers; skips all-blank rows."""
    name = Path(path).name
    reader = csv.DictReader(io.StringIO(_decode(Path(path).read_bytes()), newline=""))
    for r in reader:
        row = {_key(k): (v or "").strip() for k, v in r.items() if k is not None}
        if any(row.values()):
            yield reader.line_num, _getter(name, reader.line_num, row), row


def _getter(name: str, line: int, r: dict):
    def get(col: str, conv=lambda x: x):
        if col not in r:
            raise InputError(f"{name}: missing column {col!r}")
        try:
            return conv(r[col])
        except (ValueError, KeyError) as e:
            raise InputError(f"{name} line {line}: {col} {r[col]!r}: {e}") from None
    return get


def _id(s: str) -> str:
    s = " ".join(s.split()).upper()
    return (s.lstrip("0") or "0") if s.isdigit() else s


def _required(s: str) -> str:
    if not s:
        raise ValueError("is blank")
    return s


def _lookup(table: dict[str, str], what: str):
    def conv(s: str) -> str:
        k = " ".join(re.sub(r"[-_]", " ", s.lower()).split())
        if k not in table:
            raise ValueError(f"unrecognized {what}; expected one of {sorted(set(table.values()))}")
        return table[k]
    return conv


VISIT_STATUS = {
    **dict.fromkeys(["completed", "complete", "checked out", "checkedout", "arrived", "checked in",
                     "attended", "seen", "kept", "billed"], "completed"),
    **dict.fromkeys(["scheduled", "booked", "confirmed", "unconfirmed", "pending", "open"], "scheduled"),
    **dict.fromkeys(["cancelled", "canceled", "cancel", "cx", "late cancel", "late cancelled",
                     "late canceled", "late cancellation", "cancellation", "patient cancelled",
                     "patient canceled", "clinic cancelled", "clinic canceled", "rescheduled"], "cancelled"),
    **dict.fromkeys(["no show", "noshow", "ns", "dna", "did not attend"], "no_show"),
}
AUTH_STATUS = {
    **dict.fromkeys(["approved", "approve", "authorized", "active", "partially approved", "partial",
                     "expired"], "approved"),
    **dict.fromkeys(["pending", "submitted", "in review", "under review", "requested", "pended",
                     "in process"], "pending"),
    **dict.fromkeys(["denied", "rejected", "cancelled", "canceled", "void", "voided", "withdrawn"], "denied"),
}


def _visit_type(s: str) -> str:
    k = re.sub(r"[^a-z]", "", s.lower())
    if "eval" in k:
        return "re-eval" if k.startswith("re") or "reeval" in k else "eval"
    return "treatment"


def load_visits(path: Path) -> list[Visit]:
    name = Path(path).name
    out = []
    for i, f, r in _rows(path):
        out.append(Visit(f("visit_id", _required), f("patient_id", lambda s: _id(_required(s))),
                         f("visit_date", _d), r.get("clinic", ""), r.get("therapist", ""),
                         f("payer_id", lambda s: _id(_required(s))),
                         f("status", _lookup(VISIT_STATUS, "visit status")),
                         _visit_type(r.get("visit_type", "")), f"{name}:row{i}"))
    return out


def _count(s: str) -> int:
    if not s:
        raise ValueError("is blank; enter the number of visits the payer approved")
    n = float(s)
    if n != int(n) or n < 0:
        raise ValueError("must be a whole number >= 0")
    return int(n)


def load_auths(path: Path) -> list[Auth]:
    name = Path(path).name
    out = []
    for i, f, r in _rows(path):
        status = f("status", _lookup(AUTH_STATUS, "auth status")) if "status" in r else "approved"
        a = Auth(f("auth_no", lambda s: _required(s).upper()), f("patient_id", lambda s: _id(_required(s))),
                 f("payer_id", lambda s: _id(_required(s))), f("visits_authorized", _count),
                 f("start_date", _d), f("end_date", _d), status, f"{name}:row{i}")
        if a.end < a.start:
            raise InputError(f"{name} line {i}: end_date {a.end} is before start_date {a.start}")
        out.append(a)
    return out


def _b(s: str) -> bool:
    k = s.strip().lower()
    if k in ("y", "yes", "true", "1"):
        return True
    if k in ("n", "no", "false", "0"):
        return False
    raise ValueError("must be Y or N")


def _int0(s: str) -> int:
    return int(s) if s else 0


def load_payers(path: Path) -> dict[str, PayerRule]:
    out = {}
    for _, f, r in _rows(path):
        pid = f("payer_id", lambda s: _id(_required(s)))
        out[pid] = PayerRule(
            pid, r.get("payer_name") or pid, f("requires_auth", _b),
            f("reauth_visits_before", _int0), f("reauth_days_before", _int0), f("turnaround_days", _int0),
            f("annual_visit_limit", lambda s: int(s) if s else None) if "annual_visit_limit" in r else None,
            f("counts_evals", lambda s: _b(s) if s else True) if "counts_evals" in r else True,
            [c.strip() for c in r.get("checklist", "").split("|") if c.strip()])
    return out


def load_patients(path: Path) -> dict[str, Patient]:
    if not Path(path).exists():
        return {}
    out = {}
    for _, f, r in _rows(path):
        pid = f("patient_id", lambda s: _id(_required(s)))
        out[pid] = Patient(pid, r.get("display_name", ""), r.get("clinic", ""), _id(r.get("primary_payer", "")))
    return out
