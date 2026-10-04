"""Plain dataclasses shared by the pipeline. Money is kept in integer cents."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class StopEvent:
    """One geofence entry/exit, normalized from a Samsara-like export."""
    asset: str            # tractor or trailer id
    location: str         # geofence / address name
    event: str            # "entry" | "exit"
    time: datetime
    driver: str = ""
    lat: float | None = None
    lon: float | None = None
    source_row: str = ""  # pointer back to the raw export (file:row)
    source_kind: str = "geofence"  # tracking rows pair arrival/departure on the same row


@dataclass
class RateConStop:
    kind: str             # "pickup" | "delivery"
    facility: str
    appointment: datetime


@dataclass
class RateCon:
    load_id: str
    ratecon_no: str
    customer: str
    carrier: str
    linehaul_cents: int
    fuel_cents: int
    detention_rate_cents: int      # per hour
    free_minutes: int              # free time per stop
    increment_minutes: int         # billing increment (round down)
    detention_cap_cents: int | None
    late_grace_minutes: int        # arrival grace after appointment
    accessorials_cents: dict[str, int] = field(default_factory=dict)  # e.g. lumper
    stops: list[RateConStop] = field(default_factory=list)
    source: str = ""
    parse_warnings: list[str] = field(default_factory=list)


@dataclass
class Load:
    load_id: str
    customer: str
    carrier: str
    tractor: str
    trailer: str
    pod_received: bool
    ratecon_file: str
    source_row: str = ""
    mode: str = ""        # "asset" (own fleet) | "brokered" (outside carrier) | "" unknown


@dataclass
class InvoiceLine:
    code: str             # LINEHAUL | FUEL | DETENTION | LUMPER | TONU | ...
    amount_cents: int


@dataclass
class Invoice:
    invoice_no: str
    load_id: str
    carrier: str
    invoice_date: str
    total_cents: int
    lines: list[InvoiceLine] = field(default_factory=list)
    source_row: str = ""


def to_dict(obj):
    """dataclass -> JSON-friendly dict (datetimes as ISO strings)."""
    def conv(v):
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, dict):
            return {k: conv(x) for k, x in v.items()}
        if isinstance(v, list):
            return [conv(x) for x in v]
        return v
    return conv(asdict(obj))


def money(cents: int | None) -> str:
    if cents is None:
        return "-"
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents // 100:,}.{cents % 100:02d}"
