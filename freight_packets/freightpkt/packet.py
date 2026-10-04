"""Render a draft detention / chargeback packet as self-contained HTML.

The HTML has print CSS so "Print -> Save as PDF" produces a clean packet;
`pdf.py` can also do that headlessly with a locally installed Edge/Chrome.
"""
from __future__ import annotations

from html import escape
from datetime import datetime

from .detention import StopResult
from .invoice_match import Flag
from .models import Load, RateCon, StopEvent, money

CSS = """
body{font:14px/1.45 system-ui,Segoe UI,Arial,sans-serif;color:#1b1f24;max-width:900px;margin:24px auto;padding:0 16px}
h1{font-size:22px;margin:0}h2{font-size:16px;border-bottom:2px solid #1b1f24;padding-bottom:4px;margin-top:28px}
.banner{background:#fff4ce;border:1px solid #d8a800;padding:8px 12px;border-radius:6px;margin:12px 0;font-weight:600}
table{border-collapse:collapse;width:100%;margin:8px 0}th,td{border:1px solid #c9ced6;padding:5px 7px;text-align:left;vertical-align:top}
th{background:#eef1f5}td.num{text-align:right;font-variant-numeric:tabular-nums}
.meta td:first-child{width:200px;color:#555}.total{font-size:18px;font-weight:700}
.tag{display:inline-block;padding:1px 7px;border-radius:10px;font-size:12px;font-weight:600}
.detention{background:#dff5e1;color:#0c5a1a}.late_arrival{background:#fde2e1;color:#8a1111}
.ok{background:#eef1f5;color:#333}.exception{background:#fff4ce;color:#6b5200}
.bar{height:14px;background:#eef1f5;position:relative;border-radius:3px;overflow:hidden}
.bar span{position:absolute;top:0;bottom:0}.free{background:#9ec5fe}.over{background:#f28b82}
small{color:#666}.sig td{height:38px}
@media print{.banner{border-color:#000}a{color:inherit}body{margin:0}}
"""


def _t(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "-"


def _hm(minutes: int | None) -> str:
    if minutes is None:
        return "-"
    return f"{minutes // 60}h {minutes % 60:02d}m"


def render_packet(load: Load, rc: RateCon, stops: list[StopResult],
                  timeline: list[StopEvent], flags: list[Flag], synthetic: bool = False) -> str:
    det = [s for s in stops if s.status == "detention"]
    late = [s for s in stops if s.status == "late_arrival"]
    total = sum(s.amount_cents for s in det)
    e = escape

    rows = []
    for s in stops:
        bar = ""
        if s.dwell_minutes and s.clock_start and s.arrival:
            span = max(s.dwell_minutes, 1)
            pre = (s.clock_start - s.arrival).total_seconds() / 60
            free_w = min(s.free_minutes, span - pre)
            over_w = max(0, span - pre - free_w)
            bar = (f'<div class="bar" title="grey: before appointment, blue: free time, red: over free">'
                   f'<span class="free" style="left:{pre / span * 100:.1f}%;width:{max(free_w, 0) / span * 100:.1f}%"></span>'
                   f'<span class="over" style="left:{(pre + free_w) / span * 100:.1f}%;width:{over_w / span * 100:.1f}%"></span></div>')
        rows.append(
            f"<tr><td>{s.stop_index}</td><td>{e(s.kind)}<br><b>{e(s.facility)}</b></td>"
            f"<td>{_t(s.appointment)}</td><td>{_t(s.arrival)}<br><small>{e(s.arrival_src)}</small></td>"
            f"<td>{_t(s.departure)}<br><small>{e(s.departure_src)}</small></td>"
            f"<td class=num>{_hm(s.dwell_minutes)}{bar}</td><td class=num>{_hm(s.billable_minutes)}</td>"
            f"<td class=num>{money(s.amount_cents)}</td>"
            f"<td><span class='tag {s.status}'>{e(s.status.replace('_', ' '))}</span>"
            f"{''.join('<br><small>' + e(n) + '</small>' for n in s.notes)}</td></tr>")

    tl = "".join(
        f"<tr><td>{_t(ev.time)}</td><td>{e(ev.asset)}</td><td>{e(ev.driver)}</td><td>{e(ev.location)}</td>"
        f"<td>{e(ev.event)}</td><td><small>{'' if ev.lat is None else f'{ev.lat:.4f}, {ev.lon:.4f}'}</small></td>"
        f"<td><small>{e(ev.source_row)}</small></td></tr>" for ev in timeline)

    calc = "".join(
        f"<li>Stop {s.stop_index} ({e(s.facility)}): clock start {_t(s.clock_start)} "
        f"&rarr; departure {_t(s.departure)} = {_hm(s.over_free_minutes + s.free_minutes)} on clock; "
        f"minus {_hm(s.free_minutes)} free = {_hm(s.over_free_minutes)}; rounded down to "
        f"{rc.increment_minutes}-min increments = {_hm(s.billable_minutes)} &times; "
        f"{money(rc.detention_rate_cents)}/hr = <b>{money(s.amount_cents)}</b>"
        f"{' (capped)' if s.capped else ''} <small>[{s.claim_id}]</small></li>" for s in det)

    late_html = ""
    if late:
        late_html = ("<h2>Service failure / late arrival (chargeback candidate)</h2><ul>" + "".join(
            f"<li>Stop {s.stop_index} {e(s.facility)}: appointment {_t(s.appointment)}, geofence entry "
            f"{_t(s.arrival)} &mdash; {e('; '.join(s.notes))}</li>" for s in late)
            + "</ul><p><small>Apply the customer/carrier late-fee schedule here after human review; the PoC does "
              "not assume a fee amount.</small></p>")

    flag_html = ""
    if flags:
        flag_html = ("<h2>Carrier invoice check</h2><table><tr><th>Invoice</th><th>Flag</th><th>Detail</th>"
                     "<th>Variance</th></tr>" + "".join(
                         f"<tr><td>{e(f.invoice_no)}</td><td>{e(f.code)}</td><td>{e(f.detail)}</td>"
                         f"<td class=num>{money(f.variance_cents)}</td></tr>" for f in flags) + "</table>")

    terms = (f"Free time {_hm(rc.free_minutes)} per stop; detention {money(rc.detention_rate_cents)}/hr, "
             f"billed in {rc.increment_minutes}-min increments"
             + (f", max {money(rc.detention_cap_cents)} per stop" if rc.detention_cap_cents else "")
             + (f"; arrival grace {rc.late_grace_minutes} min" if rc.late_grace_minutes else ""))

    provenance = (" Generated by a proof of concept from SYNTHETIC sample data."
                  if synthetic else " Generated from supplied input files.")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Detention packet {e(load.load_id)}</title><style>{CSS}</style></head><body>
<div class="banner">DRAFT &mdash; pending human approval.{provenance} Not sent, not filed.</div>
<h1>Detention / accessorial claim &mdash; Load {e(load.load_id)}</h1>
<table class="meta">
<tr><td>Bill to (customer)</td><td>{e(rc.customer or load.customer)}</td></tr>
<tr><td>Carrier</td><td>{e(load.carrier)}</td></tr>
<tr><td>Rate confirmation</td><td>{e(rc.ratecon_no)} <small>({e(rc.source)})</small></td></tr>
<tr><td>Equipment</td><td>Tractor {e(load.tractor)}{' / Trailer ' + e(load.trailer) if load.trailer else ''}</td></tr>
<tr><td>Rate-con detention terms</td><td>{e(terms)}</td></tr>
<tr><td>Amount claimed</td><td class="total">{money(total)}</td></tr>
</table>
<h2>Stops</h2>
<table><tr><th>#</th><th>Stop</th><th>Appointment</th><th>Geofence in</th><th>Geofence out</th>
<th>Dwell</th><th>Billable</th><th>Amount</th><th>Status</th></tr>{''.join(rows)}</table>
<h2>Calculation</h2><ul>{calc or '<li>No billable detention.</li>'}</ul>
{late_html}
<h2>Evidence timeline (telematics geofence events)</h2>
<table><tr><th>Time</th><th>Asset</th><th>Driver</th><th>Geofence</th><th>Event</th><th>Lat/Lon</th><th>Source</th></tr>{tl}</table>
{flag_html}
<h2>Approval</h2>
<table class="sig"><tr><th>Reviewed by</th><th>Date</th><th>Decision</th></tr><tr><td></td><td></td><td>&#9744; Approve &nbsp; &#9744; Adjust &nbsp; &#9744; Reject</td></tr></table>
<p><small>Times with an explicit offset are shown in UTC; timezone-less times are shown as exported. Evidence pointers reference the source export file and row.</small></p>
</body></html>"""
