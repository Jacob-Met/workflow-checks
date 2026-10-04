"""Deterministic rate-confirmation text parser.

Input is the text layer of a rate-con PDF (what pdftotext/pdfplumber yields).
Two common broker layouts are handled with regexes. Missing terms fall back
to conservative defaults *and* record a parse warning, which pushes the load
into the human exception queue instead of silently claiming money.
"""
from __future__ import annotations

import re
from pathlib import Path

from .ingest import dollars_to_cents, parse_time
from .models import RateCon, RateConStop

MONEY = r"\$?\s*([\d,]+(?:\.\d{2})?)"

_PATTERNS = {
    "load_id": [r"Load\s*(?:#|No\.?|Number)\s*:?\s*([A-Z0-9-]+)", r"Order\s*#\s*:?\s*([A-Z0-9-]+)"],
    "ratecon_no": [r"Rate\s*Con(?:firmation)?\s*(?:#|No\.?)\s*:?\s*([A-Z0-9-]+)", r"Confirmation\s*#\s*:?\s*([A-Z0-9-]+)"],
    "customer": [r"Shipper(?:/Customer)?\s*:\s*(.+)", r"Customer\s*:\s*(.+)"],
    "carrier": [r"Carrier\s*:\s*(.+)"],
    "linehaul": [r"Line\s*haul\s*:?\s*" + MONEY, r"Base\s*Rate\s*:?\s*" + MONEY],
    "fuel": [r"Fuel(?:\s*Surcharge)?\s*:?\s*" + MONEY, r"FSC\s*:?\s*" + MONEY],
    "det_rate": [r"Detention[^\n$]*?" + MONEY + r"\s*(?:/|per)\s*(?:hr|hour)",
                 r"" + MONEY + r"\s*(?:/|per)\s*(?:hr|hour)[^\n]*detention"],
    "free": [r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?)\s*free",
             r"free\s*time\s*(?:of|:)?\s*(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?)"],
    "increment": [r"(?:billed|billable|charged)\s*in\s*(\d+)\s*[- ]?min(?:ute)?\s*increments",
                  r"(\d+)\s*[- ]?min(?:ute)?\s*increments"],
    "cap": [r"(?:max(?:imum)?|cap(?:ped)?\s*at)\s*" + MONEY + r"\s*(?:per\s*stop|/stop)?"],
    "grace": [r"(\d+)\s*[- ]?min(?:ute)?s?\s*(?:late\s*)?grace"],
    "lumper": [r"Lumper\s*(?:fee|reimbursement)?\s*:?\s*" + MONEY],
}

_STOP_RE = re.compile(
    r"^(?:Stop\s*\d+\s*[-:]\s*)?(PICKUP|PU|DELIVERY|DEL|SHIPPER|CONSIGNEE)\s*[-:]\s*(.+?)\s*[|;]\s*"
    r"(?:Appt|Appointment)\s*:?\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


def _first(key: str, text: str):
    for pat in _PATTERNS[key]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m
    return None


def parse_ratecon_text(text: str, source: str = "") -> RateCon:
    warnings: list[str] = []

    def s(key, default=""):
        m = _first(key, text)
        if not m:
            warnings.append(f"missing {key}")
            return default
        return m.group(1).strip()

    def c(key, default=0, warn=True):
        m = _first(key, text)
        if not m:
            if warn:
                warnings.append(f"missing {key}")
            return default
        return dollars_to_cents(m.group(1))

    free_minutes = 120
    m = _first("free", text)
    if m:
        qty, unit = float(m.group(1)), m.group(2).lower()
        free_minutes = int(qty * 60) if unit.startswith("h") else int(qty)
    else:
        warnings.append("missing free time (defaulted to 120 min)")

    inc = _first("increment", text)
    grace = _first("grace", text)
    cap = _first("cap", text)
    accessorials = {}
    lumper = _first("lumper", text)
    if lumper:
        accessorials["LUMPER"] = dollars_to_cents(lumper.group(1))

    stops = []
    for sm in _STOP_RE.finditer(text):
        kind = "pickup" if sm.group(1).upper() in ("PICKUP", "PU", "SHIPPER") else "delivery"
        try:
            appt = parse_time(sm.group(3))
        except ValueError:
            warnings.append(f"unparseable appointment: {sm.group(3)!r}")
            continue
        stops.append(RateConStop(kind, sm.group(2).strip(), appt))
    if not stops:
        warnings.append("no stops found")

    return RateCon(
        load_id=s("load_id"),
        ratecon_no=s("ratecon_no"),
        customer=s("customer"),
        carrier=s("carrier"),
        linehaul_cents=c("linehaul"),
        fuel_cents=c("fuel", warn=False),
        detention_rate_cents=c("det_rate"),
        free_minutes=free_minutes,
        increment_minutes=int(inc.group(1)) if inc else 15,
        detention_cap_cents=dollars_to_cents(cap.group(1)) if cap else None,
        late_grace_minutes=int(grace.group(1)) if grace else 0,
        accessorials_cents=accessorials,
        stops=stops,
        source=source,
        parse_warnings=warnings,
    )


def load_ratecon(path: Path) -> RateCon:
    path = Path(path)
    return parse_ratecon_text(path.read_text(encoding="utf-8"), source=path.name)
