"""Ingest telematics exports, load records, rate confirmations and invoices.

Telematics: accepts either
  * a Samsara-style geofence CSV export
    (Vehicle Name, Driver Name, Address Name, Event, Time, Latitude, Longitude)
  * a Samsara-API-like JSON shape
    {"data": [{"vehicle": {"name": ..}, "address": {"name": ..},
               "eventType": "GeofenceEntry"|"GeofenceExit", "time": ..}]}

Rate confirmations: plain text as extracted from the PDF (pdftotext / pdfplumber).
Two broker layouts are supported by regex; anything not found becomes a
parse warning that routes the load to the human exception queue.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .models import Invoice, InvoiceLine, Load, RateCon, RateConStop, StopEvent

TIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%y %H:%M",
)


def parse_time(raw: str) -> datetime:
    """Return UTC without tzinfo for offset timestamps; leave local-only inputs naive.

    A timezone-less export must use one consistent clock across its inputs.
    Offsets on every timestamp are required when a stop may cross a DST change.
    """
    s = raw.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
    except ValueError:
        pass
    for fmt in TIME_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            continue
    raise ValueError(f"unrecognized timestamp: {raw!r}")


def _norm_event(raw: str) -> str:
    r = raw.strip().lower().replace(" ", "")
    if r in ("entry", "enter", "geofenceentry", "arrived", "arrival", "in"):
        return "entry"
    if r in ("exit", "geofenceexit", "departed", "departure", "out"):
        return "exit"
    raise ValueError(f"unrecognized event type: {raw!r}")


# Header aliases so slightly different export templates still load.
_CSV_ALIASES = {
    "asset": ("vehicle name", "vehicle", "asset", "asset name", "trailer", "unit"),
    "driver": ("driver name", "driver"),
    "location": ("address name", "geofence", "location", "address"),
    "event": ("event", "event type", "type"),
    "time": ("time", "timestamp", "event time", "time (local)"),
    "lat": ("latitude", "lat"),
    "lon": ("longitude", "lon", "lng"),
}


def _resolve_headers(fieldnames: list[str]) -> dict[str, str]:
    lower = {f.strip().lower(): f for f in fieldnames}
    out = {}
    for key, aliases in _CSV_ALIASES.items():
        for a in aliases:
            if a in lower:
                out[key] = lower[a]
                break
    missing = {"asset", "location", "event", "time"} - out.keys()
    if missing:
        raise ValueError(f"telematics CSV missing columns: {sorted(missing)}")
    return out


def load_telematics(path: Path) -> list[StopEvent]:
    path = Path(path)
    events: list[StopEvent] = []
    if path.suffix.lower() == ".json":
        doc = json.loads(path.read_text(encoding="utf-8"))
        rows = doc.get("data", doc) if isinstance(doc, dict) else doc
        for i, r in enumerate(rows):
            veh = r.get("vehicle") or r.get("asset") or {}
            addr = r.get("address") or r.get("geofence") or {}
            loc = addr.get("name") or addr.get("formattedAddress")
            events.append(StopEvent(
                asset=veh.get("name", ""),
                driver=(r.get("driver") or {}).get("name", ""),
                location=loc or "",
                event=_norm_event(r.get("eventType", "")),
                time=parse_time(r.get("time") or r.get("eventTime")),
                lat=(r.get("location") or {}).get("latitude"),
                lon=(r.get("location") or {}).get("longitude"),
                source_row=f"{path.name}#data[{i}]",
            ))
    else:
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            h = _resolve_headers(reader.fieldnames or [])
            for i, r in enumerate(reader, start=2):
                events.append(StopEvent(
                    asset=r[h["asset"]].strip(),
                    driver=r.get(h.get("driver", ""), "").strip() if "driver" in h else "",
                    location=r[h["location"]].strip(),
                    event=_norm_event(r[h["event"]]),
                    time=parse_time(r[h["time"]]),
                    lat=float(r[h["lat"]]) if "lat" in h and r[h["lat"]] else None,
                    lon=float(r[h["lon"]]) if "lon" in h and r[h["lon"]] else None,
                    source_row=f"{path.name}:row{i}",
                ))
    events.sort(key=lambda e: (e.asset, e.time))
    return events


def load_loads(path: Path) -> list[Load]:
    path = Path(path)
    out = []
    seen: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for i, r in enumerate(csv.DictReader(fh), start=2):
            lid = r["load_id"].strip()
            source = f"{path.name}:row{i}"
            if lid in seen:
                raise ValueError(f"duplicate load_id {lid!s}: {seen[lid]} and {source}")
            seen[lid] = source
            out.append(Load(
                load_id=lid,
                customer=r["customer"].strip(),
                carrier=r["carrier"].strip(),
                tractor=r["tractor"].strip(),
                trailer=r.get("trailer", "").strip(),
                pod_received=r.get("pod_received", "").strip().lower() in ("y", "yes", "true", "1"),
                ratecon_file=r.get("ratecon_file", "").strip(),
                source_row=source,
                mode=(r.get("mode") or "").strip().lower(),
            ))
    return out


# Stop-level tracking export (FourKites-style visibility platform). Column names
# vary by account/report template, so aliases are resolved like the geofence CSV.
# NOTE: the aliases are generic guesses, not FourKites' documented schema; a real
# pilot confirms them against the client's own export.
_TRACK_ALIASES = {
    "load": ("load number", "load #", "load id", "load", "shipment id", "reference number",
             "bill of lading", "order number"),
    "stop": ("stop name", "location name", "stop location", "facility", "facility name", "location"),
    "seq": ("stop sequence", "stop #", "stop number", "sequence"),
    "arrival": ("actual arrival", "actual arrival time", "arrival time", "arrived at", "arrival"),
    "departure": ("actual departure", "actual departure time", "departure time", "departed at",
                  "departure"),
    "carrier": ("carrier", "carrier name"),
    "device": ("tracking method", "tracking source", "device", "source"),
}


def load_tracking_stops(path: Path) -> list[StopEvent]:
    """Stop-level tracking export -> entry/exit StopEvents keyed by LOAD number.

    One row per load stop with actual arrival/departure. Blank arrival = the
    platform never saw the truck there (no event); blank departure = entry only
    (the detention engine then routes the stop to the exception queue).
    """
    path = Path(path)
    events: list[StopEvent] = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        lower = {f.strip().lower(): f for f in (reader.fieldnames or [])}
        h = {}
        for key, aliases in _TRACK_ALIASES.items():
            for a in aliases:
                if a in lower:
                    h[key] = lower[a]
                    break
        missing = {"load", "stop", "arrival"} - h.keys()
        if missing:
            raise ValueError(f"tracking export missing columns: {sorted(missing)}")
        for i, r in enumerate(reader, start=2):
            load = r[h["load"]].strip()
            stop = r[h["stop"]].strip()
            src = f"{path.name}:row{i}"
            for kind, col in (("entry", "arrival"), ("exit", "departure")):
                raw = (r.get(h[col], "") if col in h else "").strip()
                if raw:
                    events.append(StopEvent(asset=load, location=stop, event=kind,
                                            time=parse_time(raw), source_row=src,
                                            source_kind="tracking"))
    events.sort(key=lambda e: (e.asset, e.time))
    return events


def dollars_to_cents(raw: str) -> int:
    s = raw.replace("$", "").replace(",", "").strip()
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    cents = round(float(s) * 100)
    return -cents if neg else cents


def load_invoices(path: Path) -> list[Invoice]:
    """Group invoice lines by invoice_no+load_id, requiring consistent headers.

    Duplicate invoice numbers on different loads remain separate for matching.
    Repeated headers use the existing string trimming and monetary parsing.
    """
    path = Path(path)
    grouped: dict[tuple[str, str], Invoice] = {}
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for i, r in enumerate(csv.DictReader(fh), start=2):
            key = (r["invoice_no"].strip(), r["load_id"].strip())
            carrier = r["carrier"].strip()
            invoice_date = r["invoice_date"].strip()
            total_cents = dollars_to_cents(r["invoice_total"])
            source_row = f"{path.name}:row{i}"
            inv = grouped.get(key)
            if inv is None:
                inv = Invoice(
                    invoice_no=key[0], load_id=key[1],
                    carrier=carrier,
                    invoice_date=invoice_date,
                    total_cents=total_cents,
                    source_row=source_row,
                )
                grouped[key] = inv
            else:
                conflicts = [
                    name for name, first, current in (
                        ("carrier", inv.carrier, carrier),
                        ("invoice_date", inv.invoice_date, invoice_date),
                        ("invoice_total", inv.total_cents, total_cents),
                    ) if first != current
                ]
                if conflicts:
                    raise ValueError(
                        f"conflicting invoice header {', '.join(conflicts)} "
                        f"for invoice {key[0]!r} on load {key[1]!r}: "
                        f"{inv.source_row} and {source_row}"
                    )
            inv.lines.append(InvoiceLine(r["line_code"].strip().upper(),
                                         dollars_to_cents(r["line_amount"])))
    return list(grouped.values())
