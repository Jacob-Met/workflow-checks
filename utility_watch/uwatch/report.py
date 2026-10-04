"""Static weekly exception report (single HTML file, no CDN, no scripts)."""
from __future__ import annotations

import html
from pathlib import Path

LABEL = {
    "USAGE_SPIKE": "Usage spike vs same month last year",
    "RATE_CHANGE": "Effective rate jumped",
    "DUPLICATE_BILL": "Duplicate bill (hold)",
    "LATE_FEE_OR_PAST_DUE": "Late fee / past-due balance",
    "MISSING_BILL": "Expected bill missing",
    "PERIOD_OVERLAP": "Service periods overlap",
    "PAYMENT_MISMATCH": "Payment does not match bill",
    "UNPAID_PAST_DUE": "Unpaid and past due",
    "VACANT_UNIT_USAGE": "Usage on a vacant unit",
}


def write_html(path: Path, s: dict, queue: list) -> None:
    e = html.escape
    rows = []
    for f in sorted(s["flags_detail"], key=lambda x: (x["property"], x["code"])):
        rows.append(f"<tr><td>{e(f['property'])}</td><td>{e(f['utility'])}</td><td>{e(f['account_no'])}</td>"
                    f"<td><b>{e(LABEL.get(f['code'], f['code']))}</b><br><small>{e(f['code'])}</small></td>"
                    f"<td>{e(f['detail'])}</td><td><small>{e(' '.join(f['evidence']))}</small></td></tr>")
    exc = "".join(f"<tr><td>{e(x['key'])}</td><td>{e(x['account_no'])}</td><td>{e(x['reason'])}</td>"
                  f"<td>{e(x.get('detail', ''))}</td></tr>" for x in s["exceptions_detail"])
    q = "".join(f"<tr><td>{e(x['due_date'])}</td><td>{e(str(x['property']))}</td><td>{e(str(x['utility']))}</td>"
                f"<td>{e(x['invoice'])}</td><td style='text-align:right'>${x['amount_due']:,.2f}</td></tr>" for x in queue)
    cards = "".join(f"<div class=c><b>{v}</b><br>{e(LABEL.get(k, k))}</div>" for k, v in sorted(s["by_code"].items()))
    synthetic = s.get("data_mode", "synthetic") == "synthetic"
    title_suffix = " (SYNTHETIC)" if synthetic else ""
    warning = ("<b>SYNTHETIC DATA.</b> Fictional properties and placeholder vendors."
               if synthetic else "<b>REVIEW ONLY.</b> This report does not approve or issue payments.")
    doc = f"""<!doctype html><meta charset=utf-8><title>Utility bill exceptions{title_suffix}</title>
<style>body{{font:14px system-ui,sans-serif;margin:24px;max-width:1100px}}table{{border-collapse:collapse;width:100%;margin:8px 0 24px}}
td,th{{border:1px solid #ccc;padding:4px 6px;vertical-align:top}}th{{background:#f3f3f3;text-align:left}}
.c{{display:inline-block;border:1px solid #bbb;border-radius:6px;padding:8px 12px;margin:4px;min-width:120px}}
.warn{{background:#fff3cd;padding:8px;border:1px solid #e0c36b}}</style>
<p class=warn>{warning} Nothing is paid, disputed or sent; every item is for a person to review.</p>
<h1>Utility bill exceptions, week of {e(s['as_of'])}</h1>
<p>{s['accounts']} accounts, {s['bills']} bills on file; checked service months from {e(s['eval_from'])}.
{s['flags']} flags, {s['exceptions']} items the rules could not judge, {s['payment_queue']} clean bills
(${s['payment_queue_total']:,.2f}) queued for payment approval.</p>
<div>{cards}</div>
<h2>Flags</h2><table><tr><th>Property</th><th>Utility</th><th>Account</th><th>Flag</th><th>Why</th><th>Evidence</th></tr>
{''.join(rows)}</table>
<h2>Could not judge (exception queue)</h2><table><tr><th>Bill</th><th>Account</th><th>Reason</th><th>Detail</th></tr>{exc}</table>
<h2>Clean bills queued for payment approval (not paid)</h2>
<table><tr><th>Due</th><th>Property</th><th>Utility</th><th>Invoice</th><th>Amount</th></tr>{q}</table>
<p><small>Baseline: same service month last year (usage per day), so summer electric and winter gas are not
flagged just for being seasonal. A naive trailing-3-month rule would have flagged {len(s['naive_trailing3_hits'])}
bills that this report does not.</small></p>"""
    Path(path).write_text(doc, encoding="utf-8")
