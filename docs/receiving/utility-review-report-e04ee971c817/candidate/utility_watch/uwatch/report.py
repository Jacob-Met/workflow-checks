"""Static weekly exception report (single HTML file, no CDN, no scripts)."""
from __future__ import annotations

import html
from itertools import groupby
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

STYLE = """
:root{color-scheme:light;font:15px/1.5 system-ui,Segoe UI,Arial,sans-serif;color:#1b2d37;background:#f4f6f7}
*{box-sizing:border-box}body{max-width:1120px;margin:0 auto;padding:32px 24px 48px}
a{color:#125c83;text-underline-offset:3px}a:hover{text-decoration-thickness:2px}
a:focus-visible,summary:focus-visible{outline:3px solid #125c83;outline-offset:5px;border-radius:3px}
h1{font-size:2.2rem;line-height:1.15;letter-spacing:-.035em;margin:12px 0}h2{font-size:1.6rem;margin:0}
h3,p{margin:0 0 10px}h3{font-size:1.1rem}small,.muted{color:#52636d}
code{font-size:.88em;overflow-wrap:anywhere}section,details{scroll-margin-top:20px}
.eyebrow{text-transform:uppercase;font-size:.78rem;font-weight:750;letter-spacing:.1em;color:#52636d}
.notice{background:#fff5d7;border:1px solid #d2b258;padding:12px 16px;border-radius:8px;margin-bottom:24px}
.summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:24px 0 16px}
.summary a{display:block;border:1px solid #c1d0d7;border-radius:10px;padding:18px;background:white;text-decoration:none}
.summary strong{font-size:2rem;display:block;line-height:1.2;color:#1b2d37}.summary span{display:block}
.summary .amount{font-size:.88rem;margin-top:6px;color:#52636d}.summary a:hover{border-color:#125c83}
.section-head{display:flex;align-items:baseline;justify-content:space-between;gap:16px;margin:36px 0 10px}
.section-head>a{font-size:.9rem;white-space:nowrap}.intro{max-width:78ch}
.codes,.property-index,.evidence{display:flex;flex-wrap:wrap;gap:8px 16px;padding:0;list-style:none}
.codes{margin:18px 0}.codes li{background:#e5ecef;border-radius:6px;padding:4px 8px;font-size:.85rem}
.property-index{margin:14px 0 20px}.property-index li{min-width:0;max-width:100%}
.property-index a{font-size:.9rem;overflow-wrap:anywhere}
.property{border:1px solid #c1d0d7;border-radius:10px;background:white;margin-bottom:14px;overflow:hidden}
.property summary{cursor:pointer;padding:16px 20px;background:#eaf0f3;font-weight:700;overflow-wrap:anywhere}
.property summary .count{font-size:.85rem;font-weight:500;margin-left:10px;color:#405663}
.records,.queue{list-style:none;padding:0;margin:0}.record{padding:20px;border-bottom:1px solid #d7e0e4;background:white}
.record:last-child{border-bottom:0}.record p{overflow-wrap:anywhere}.record .reason{display:block;margin-bottom:10px}
.identity{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px 24px;margin:14px 0}
.identity div{min-width:0}dt{font-size:.76rem;color:#52636d;text-transform:uppercase;letter-spacing:.03em}
dd{margin:2px 0 0;overflow-wrap:anywhere}.evidence-block{border-top:1px dashed #c1d0d7;padding-top:12px;margin-top:14px}
.evidence-title{font-size:.8rem;font-weight:700;color:#405663}.evidence{margin:4px 0 0;font-size:.9rem}
.queue>.record,.exception-list>.record{border:1px solid #c1d0d7;border-radius:10px;margin-top:12px}
.payment-head{display:flex;justify-content:space-between;gap:20px;align-items:baseline}
.payment-head h3{font-size:1rem;font-weight:600}.payment-head strong{font-size:1.4rem;white-space:nowrap}
.status{background:#edf4ee;color:#2d573b;border-radius:4px;padding:4px 8px;display:inline-block;font-size:.85rem}
.empty{padding:20px;border:1px dashed #a8bbc5;border-radius:10px;background:white}
footer{border-top:1px solid #c1d0d7;margin-top:36px;padding-top:18px;font-size:.85rem;color:#52636d}
@media(max-width:640px){body{padding:20px 14px 32px}h1{font-size:1.85rem}.summary{gap:8px}
.summary a{padding:12px 10px}.summary strong{font-size:1.7rem}.summary span{font-size:.86rem}
.summary .amount{font-size:.76rem}.identity{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 16px}
.property summary,.record{padding:16px}.section-head{align-items:flex-start}h2{font-size:1.35rem}}
@media(max-width:360px){.summary{grid-template-columns:1fr}.summary strong{display:inline;margin-right:8px}
.summary span{display:inline}.summary .amount{display:block}.payment-head{flex-wrap:wrap;gap:4px}}
@media print{:root{background:white;font-size:10pt}body{max-width:none;padding:0}.notice{margin-bottom:12px}
a{color:inherit;text-decoration:none}.summary,.property-index,.section-head>a{display:none}
.property{overflow:visible}.property::details-content{content-visibility:visible;display:block;height:auto}
.property:not([open])>.records{display:block!important}.property summary{list-style:none;padding:10px}
.record{padding:12px;break-inside:avoid}.section-head{margin-top:24px}.evidence-block{padding-top:6px}
.identity{margin:8px 0}.status{background:none;border:1px solid #aaa}}
"""


def _text(value) -> str:
    return html.escape("" if value is None else str(value))


def _identity(fields: list[tuple[str, object]]) -> str:
    return '<dl class="identity">' + "".join(
        f"<div><dt>{_text(label)}</dt><dd>{_text(value)}</dd></div>"
        for label, value in fields
    ) + "</dl>"


def _evidence(pointers: list[str] | str) -> str:
    if isinstance(pointers, str):
        pointers = [pointers] if pointers else []
    rows = "".join(f"<li><code>{_text(pointer)}</code></li>" for pointer in pointers)
    content = f'<ul class="evidence">{rows}</ul>' if rows else '<p class="muted">No source row supplied.</p>'
    return '<div class="evidence-block"><span class="evidence-title">Source rows</span>' + content + "</div>"


def write_html(path: Path, s: dict, queue: list) -> None:
    flags = sorted(s["flags_detail"], key=lambda x: (x["property"], x["code"], x["key"]))
    properties, property_links = [], []
    for index, (name, items) in enumerate(groupby(flags, key=lambda x: x["property"]), 1):
        items = list(items)
        property_id = f"property-{index}"
        property_links.append(f'<li><a href="#{property_id}">{_text(name)} ({len(items)})</a></li>')
        rows = []
        for flag in items:
            identity = _identity([
                ("Utility", flag["utility"]), ("Account", flag["account_no"]),
                ("Bill / expected period", flag["key"]),
            ])
            rows.append(
                f'<li class="record"><h3>{_text(LABEL.get(flag["code"], flag["code"]))}</h3>'
                f'<code class="reason">{_text(flag["code"])}</code>{identity}'
                f'<p>{_text(flag["detail"])}</p>{_evidence(flag["evidence"])}</li>'
            )
        count = f'{len(items)} flag' + ("s" if len(items) != 1 else "")
        properties.append(
            f'<details class="property" id="{property_id}" open><summary>{_text(name)}'
            f'<span class="count">{count}</span></summary><ul class="records">{"".join(rows)}</ul></details>'
        )
    exception_rows = []
    for item in s["exceptions_detail"]:
        identity = _identity([("Bill / expected period", item["key"]), ("Account", item["account_no"])])
        exception_rows.append(
            f'<li class="record"><h3><code>{_text(item["reason"])}</code></h3>{identity}'
            f'<p>{_text(item.get("detail", ""))}</p>{_evidence(item["evidence"])}</li>'
        )
    payment_rows = []
    # Keep the engine's global due-date order, including its stable ordering of ties.
    for item in queue:
        identity = _identity([
            ("Property", item["property"]), ("Utility", item["utility"]), ("Vendor", item["vendor"]),
            ("Account", item["account_no"]), ("Bill", item["bill_id"]), ("Invoice", item["invoice"]),
        ])
        payment_rows.append(
            f'<li class="record"><div class="payment-head"><h3>Due {_text(item["due_date"])}</h3>'
            f'<strong>${item["amount_due"]:,.2f}</strong></div>{identity}'
            f'<code class="status">{_text(item["status"])}</code>{_evidence(item["evidence"])}</li>'
        )
    cards = "".join(
        f"<li><b>{_text(count)}</b> {_text(LABEL.get(code, code))}</li>"
        for code, count in sorted(s["by_code"].items())
    )
    synthetic = s.get("data_mode", "synthetic") == "synthetic"
    title_suffix = " (SYNTHETIC)" if synthetic else ""
    warning = ("<b>SYNTHETIC DATA.</b> Fictional properties and placeholder vendors."
               if synthetic else "<b>REVIEW ONLY.</b> This report does not approve or issue payments.")
    flag_content = (f'<nav aria-label="Properties with flags"><ul class="property-index">'
                    f'{"".join(property_links)}</ul></nav>{"".join(properties)}' if properties
                    else '<p class="empty">No flags in this review window.</p>')
    exception_content = (f'<ul class="records exception-list">{"".join(exception_rows)}</ul>' if exception_rows
                         else '<p class="empty">No items in the exception queue.</p>')
    payment_content = (f'<ol class="queue">{"".join(payment_rows)}</ol>' if payment_rows
                       else '<p class="empty">No clean, unpaid bills queued for approval.</p>')
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Utility bill exceptions{title_suffix}</title><style>{STYLE}</style></head>
<body><header id="report-top">
<p class="notice">{warning} Nothing is paid, disputed or sent; every item is for a person to review.</p>
<p class="eyebrow">Utility Watch · Weekly review</p>
<h1>Utility bill exceptions</h1>
<p>Week of <b>{_text(s['as_of'])}</b> · {_text(s['accounts'])} accounts · {_text(s['bills'])} bills on file</p>
<p class="muted">Checked service months from {_text(s['eval_from'])}.</p>
<nav class="summary" aria-label="Review queues">
<a href="#flags"><strong>{_text(s['flags'])}</strong><span>Flags to review</span></a>
<a href="#exceptions"><strong>{_text(s['exceptions'])}</strong><span>Could not judge</span></a>
<a href="#payment-queue"><strong>{_text(s['payment_queue'])}</strong><span>Queued for approval</span>
<span class="amount">${s['payment_queue_total']:,.2f} · not paid</span></a></nav>
</header><main>
<section id="flags" aria-labelledby="flags-heading"><div class="section-head">
<h2 id="flags-heading">Flags to review</h2><a href="#report-top">Back to top</a></div>
<p class="intro">Review each reason and its source rows. Open or close a property to focus the list;
all properties start open. A bill can have more than one flag.</p>
<ul class="codes" aria-label="Flag counts by reason">{cards}</ul>{flag_content}</section>
<section id="exceptions" aria-labelledby="exceptions-heading"><div class="section-head">
<h2 id="exceptions-heading">Could not judge</h2><a href="#report-top">Back to top</a></div>
<p class="intro">These items need a person to resolve missing information or another exception.
They are held out of the payment queue. Match the account and bill or expected period to the source rows.</p>
{exception_content}</section>
<section id="payment-queue" aria-labelledby="payment-heading"><div class="section-head">
<h2 id="payment-heading">Queued for payment approval</h2><a href="#report-top">Back to top</a></div>
<p class="intro">{_text(s['payment_queue'])} clean, unpaid bills · <b>${s['payment_queue_total']:,.2f}</b> total.
Listed by due date, earliest first. Review the account, invoice and source row before approving in your payment system.
Nothing here is approved or paid.</p>{payment_content}</section>
</main><footer><p>Source rows refer to the input CSV files, with the header counted as row 1.
The companion CSV files and audit.jsonl contain the same decisions. This report does not save review progress.</p>
<p>Baseline: same service month last year (usage per day), so summer electric and winter gas are not
flagged just for being seasonal. A naive trailing-3-month rule would have flagged {_text(len(s['naive_trailing3_hits']))}
bills that this report does not.</p></footer></body></html>"""
    Path(path).write_text(doc, encoding="utf-8")
