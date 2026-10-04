"""Run the tracker and write outputs.

  worklist.csv          the daily worklist (one row per patient/payer/auth item)
  ledger.csv            every auth: authorized / used / scheduled / remaining / days left
  digest.html           printable daily digest (worklist + re-auth checklists)
  summary.json          everything, for the web UI
  audit.jsonl           append-only log of each run and reviewer action
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

from . import data
from .engine import build_worklist

BANNER = ("SYNTHETIC DATA - NOT REAL PATIENTS. Proof of concept; payer rules are placeholders. "
          "Nothing is submitted to any payer.")


def _j(o):
    if isinstance(o, date):
        return o.isoformat()
    raise TypeError(type(o))


def audit(out_dir: Path, action: str, **kw):
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "action": action, **kw}
    with (Path(out_dir) / "audit.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, default=_j) + "\n")


def run(data_dir: Path, out_dir: Path, as_of: date | None = None, run_by: str = "cli") -> dict:
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if as_of is None:
        exp = data_dir / "expected.json"
        as_of = date.fromisoformat(json.loads(exp.read_text())["as_of"]) if exp.exists() else date.today()
    visits = data.load_visits(data_dir / "schedule.csv")
    auths = data.load_auths(data_dir / "authorizations.csv")
    payers = data.load_payers(data_dir / "payers.csv")
    patients = data.load_patients(data_dir / "patients.csv")
    items, ledgers, uncovered = build_worklist(visits, auths, payers, patients, as_of)

    ledger_rows = []
    for led in sorted(ledgers.values(), key=lambda l: (l.auth.patient_id, l.auth.start)):
        a = led.auth
        ledger_rows.append({
            "auth_no": a.auth_no, "patient_id": a.patient_id,
            "patient_name": patients[a.patient_id].display_name if a.patient_id in patients else "",
            "payer_id": a.payer_id, "start": a.start, "end": a.end,
            "authorized": a.visits_authorized, "used": len(led.used), "scheduled": len(led.scheduled),
            "remaining": led.remaining, "remaining_after_scheduled": led.remaining_after_scheduled,
            "days_left": (a.end - as_of).days, "status": "expired" if a.end < as_of else "active"})

    wl = []
    for it in items:
        d = asdict(it)
        d["key"] = it.key
        wl.append(d)

    with (out_dir / "worklist.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["priority", "patient_id", "patient_name", "clinic", "payer", "auth_no", "reasons",
                    "visits_used", "visits_authorized", "visits_remaining", "scheduled_in_window",
                    "auth_end", "days_left", "next_visit", "submit_by", "detail", "evidence"])
        for it in items:
            w.writerow([it.priority, it.patient_id, it.patient_name, it.clinic, it.payer_name, it.auth_no,
                        "|".join(it.reasons), it.visits_used, it.visits_authorized, it.visits_remaining,
                        it.scheduled_in_window, it.auth_end, it.days_left, it.next_visit, it.submit_by,
                        " / ".join(it.detail), ";".join(it.evidence)])
    with (out_dir / "ledger.csv").open("w", newline="", encoding="utf-8") as fh:
        if ledger_rows:
            w = csv.DictWriter(fh, fieldnames=list(ledger_rows[0].keys()))
            w.writeheader()
            w.writerows(ledger_rows)

    counts = {"patients": len(patients), "visits": len(visits), "auths": len(auths),
              "worklist": len(items), "p1": sum(i.priority == "P1" for i in items),
              "p2": sum(i.priority == "P2" for i in items), "p3": sum(i.priority == "P3" for i in items),
              "uncovered_scheduled": sum(1 for v in uncovered if v.status == "scheduled" and v.visit_date >= as_of),
              "unauthorized_done": sum(1 for v in uncovered if v.status == "completed")}
    summary = {"banner": BANNER, "as_of": as_of, "generated_at": datetime.now().isoformat(timespec="seconds"),
               "counts": counts, "worklist": wl, "ledger": ledger_rows,
               "uncovered": [{"visit_id": v.visit_id, "patient_id": v.patient_id, "date": v.visit_date,
                              "status": v.status, "payer_id": v.payer_id} for v in uncovered]}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=_j), encoding="utf-8")
    (out_dir / "digest.html").write_text(render_digest(summary), encoding="utf-8")
    audit(out_dir, "run", run_by=run_by, as_of=as_of, **counts)
    return summary


def render_digest(s: dict) -> str:
    e = escape
    rows = "".join(
        f"<tr class='{x['priority']}'><td><b>{x['priority']}</b></td><td>{e(x['patient_name'])}<br><small>{e(x['patient_id'])}</small></td>"
        f"<td>{e(x['clinic'])}</td><td>{e(x['payer_name'])}<br><small>{e(x['auth_no'])}</small></td>"
        f"<td>{'<br>'.join(e(r) for r in x['reasons'])}</td>"
        f"<td>{x['visits_used'] if x['visits_used'] is not None else '-'} / {x['visits_authorized'] if x['visits_authorized'] is not None else '-'}</td>"
        f"<td>{x['auth_end'] or '-'}<br><small>{'' if x['days_left'] is None else str(x['days_left']) + ' d'}</small></td>"
        f"<td>{x['next_visit'] or '-'}</td><td>{x['submit_by'] or '-'}</td>"
        f"<td><small>{'<br>'.join(e(d) for d in x['detail'])}</small></td></tr>" for x in s["worklist"])
    checklists = "".join(
        f"<div class='ck'><b>{e(x['patient_name'])}</b> &middot; {e(x['payer_name'])} &middot; {e(x['auth_no'])}"
        f"<ul>{''.join('<li>&#9744; ' + e(c) + '</li>' for c in x['checklist'])}</ul></div>"
        for x in s["worklist"] if x["checklist"] and set(x["reasons"]) & {"REAUTH_BY_VISITS", "REAUTH_BY_DATE", "UNCOVERED_VISIT"})
    c = s["counts"]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Auth worklist {s['as_of']}</title>
<style>body{{font:13px/1.4 system-ui,Segoe UI,Arial,sans-serif;margin:20px;color:#1b1f24}}
.banner{{background:#fde2e1;border:1px solid #c0392b;padding:8px 12px;font-weight:700;border-radius:6px}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccd;padding:4px 6px;vertical-align:top;text-align:left}}
th{{background:#eef1f5}}tr.P1 td:first-child{{background:#fde2e1}}tr.P2 td:first-child{{background:#fff4ce}}
small{{color:#666}}.ck{{border:1px solid #ccd;border-radius:6px;padding:6px 10px;margin:6px 0;break-inside:avoid}}
.ck ul{{margin:4px 0;padding-left:18px;list-style:none}}</style></head><body>
<div class="banner">{e(s['banner'])}</div>
<h1>Daily authorization worklist &mdash; {s['as_of']}</h1>
<p>{c['p1']} act-today (P1) &middot; {c['p2']} this week (P2) &middot; {c['p3']} heads-up (P3) &middot;
{c['uncovered_scheduled']} scheduled visits outside an approved auth &middot; {c['unauthorized_done']} completed visits without auth</p>
<table><tr><th>Pri</th><th>Patient</th><th>Clinic</th><th>Payer / auth</th><th>Reason</th><th>Used / auth'd</th>
<th>Auth end</th><th>Next visit</th><th>Submit by</th><th>Detail</th></tr>{rows}</table>
<h2>Re-auth packet checklists (pre-filled from payer rules table)</h2>{checklists or '<p>None.</p>'}
</body></html>"""
