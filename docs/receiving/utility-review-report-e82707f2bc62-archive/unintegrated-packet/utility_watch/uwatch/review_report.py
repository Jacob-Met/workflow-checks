"""Readable offline snapshots of validated review worksheets; no reconciliation."""
from __future__ import annotations

import csv
import hashlib
import html
import os
from pathlib import Path
import tempfile

from . import review
from .report import LABEL


STYLE = """
:root{color-scheme:light;font:15px/1.55 system-ui,Segoe UI,Arial,sans-serif;color:#243530;background:#f5f5ef}
*{box-sizing:border-box}body{margin:0 auto;max-width:1100px;padding:36px 24px 64px}
h1,h2,h3,p{margin:0}h1{font-size:2.45rem;line-height:1.1;letter-spacing:-.045em;margin:12px 0}
h2{font-size:1.45rem;letter-spacing:-.02em}h3{font-size:1.1rem;line-height:1.35}
a{color:#19644c;text-underline-offset:3px}button,input,select{font:inherit}button{cursor:pointer}
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid #19705b;outline-offset:3px}
.eyebrow{text-transform:uppercase;letter-spacing:.1em;font-size:.75rem;font-weight:750;color:#577064}
.intro{max-width:78ch;margin:14px 0 20px;color:#506057}.muted{color:#506057}.snapshot{overflow-wrap:anywhere}
.notice{border-left:4px solid #819c8c;background:#e8eee7;padding:12px 16px;margin:20px 0}
.counts{display:flex;flex-wrap:wrap;gap:12px 24px;margin:20px 0;padding:16px 0;border-top:1px solid #bbcbbf;border-bottom:1px solid #bbcbbf}
.counts strong{font-size:1.5rem;margin-right:5px}.counts span{white-space:nowrap}
.controls{padding:20px;background:#fff;border:1px solid #bbcbbf;border-radius:10px;margin:24px 0 14px}
.filters{display:grid;grid-template-columns:2fr repeat(3,1fr);gap:12px}label{font-size:.8rem;font-weight:650}
input,select{display:block;width:100%;margin-top:5px;padding:9px;border:1px solid #82988d;border-radius:5px;background:#fff;color:inherit;min-width:0}
.actions{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:16px}
button{padding:8px 14px;border:1px solid #19644c;border-radius:5px;background:#19644c;color:white;font-weight:600}
button.secondary{background:white;color:#19644c}.showing{font-size:.88rem;color:#506057;margin:8px 0 20px}
.section-heading{margin:30px 0 16px}.section-heading p{margin-top:5px;max-width:78ch;color:#506057}
.finding{border:1px solid #b8c8bc;border-radius:10px;margin:14px 0;background:white;overflow:hidden;break-inside:avoid}
.finding-header{padding:18px 20px 12px;background:#f0f4ec}.history .finding-header{background:#f3eee4}
.badges{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:9px}.badge{font-size:.72rem;font-weight:750;letter-spacing:.025em;padding:3px 7px;border-radius:4px;background:#dce8dd}
.history .badge{background:#e8dfce}.finding-content{padding:18px 20px}.finding dl{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px 20px;margin:0 0 18px}
dt{font-size:.73rem;text-transform:uppercase;letter-spacing:.025em;color:#52665b}dd{margin:3px 0 0;overflow-wrap:anywhere}
.literal{white-space:pre-wrap;overflow-wrap:anywhere}.annotation{border-left:3px solid #9ab9a6;background:#f4f7f1;padding:12px 15px;margin:14px 0}
.annotation p+p{margin-top:9px}.note-label{font-size:.76rem;font-weight:700;color:#52665b}.detail{margin:14px 0;overflow-wrap:anywhere}
.source{border-top:1px dashed #bdcbbf;padding-top:12px}.source h4{font-size:.8rem;margin:0 0 5px}.source ul{display:flex;flex-wrap:wrap;gap:6px 16px;list-style:none;margin:0;padding:0}
code{font-size:.84em;overflow-wrap:anywhere}details{margin-top:12px;font-size:.85rem}summary{cursor:pointer;color:#506057}
.identity{margin:8px 0 0!important;display:block!important}.identity div{margin:8px 0}
.empty{border:1px dashed #98ad9f;padding:20px;border-radius:8px;background:#fff}.no-matches{margin:24px 0}
footer{border-top:1px solid #bbcbbf;margin-top:32px;padding-top:18px;font-size:.83rem;color:#506057}
[hidden]{display:none!important}
@media(max-width:760px){body{padding:24px 16px 40px}.filters{grid-template-columns:1fr 1fr}.search-filter{grid-column:1/-1}.finding dl{grid-template-columns:1fr 1fr}}
@media(max-width:430px){h1{font-size:2rem}.filters{grid-template-columns:1fr}.search-filter{grid-column:auto}.finding dl{grid-template-columns:1fr}.actions{align-items:stretch;flex-direction:column}.finding-header,.finding-content{padding:16px}}
@media print{:root{background:white;font-size:10pt}body{max-width:none;padding:0}.controls{display:none!important}h1{font-size:24pt}.finding{box-shadow:none;border-radius:0}.finding-header{background:#f4f4f4}.finding-content{padding:12px}.finding details{display:none}footer{font-size:8pt}.counts{margin:10px 0;padding:10px 0}.section-heading{margin-top:20px}.notice{margin:12px 0}}
"""

SCRIPT = """
(() => {
  const controls = document.getElementById('controls');
  const search = document.getElementById('search');
  const state = document.getElementById('state');
  const status = document.getElementById('status');
  const reviewer = document.getElementById('reviewer');
  const articles = Array.from(document.querySelectorAll('article[data-state]'));
  const sections = Array.from(document.querySelectorAll('section[data-records]'));
  function update() {
    const query = search.value.trim().toLocaleLowerCase();
    let count = 0;
    for (const article of articles) {
      const isCurrent = article.dataset.state === 'current';
      const stateMatches = state.value === 'all' || (state.value === 'current' ? isCurrent : !isCurrent);
      const matches = stateMatches && (status.value === 'all' || article.dataset.status === status.value)
        && (reviewer.value === 'all' || article.dataset.reviewer === reviewer.value)
        && (!query || article.dataset.search.toLocaleLowerCase().includes(query));
      article.hidden = !matches;
      if (matches) count += 1;
    }
    for (const section of sections) {
      const records = Array.from(section.querySelectorAll('article'));
      section.hidden = records.length ? records.every(article => article.hidden) : state.value !== 'all';
    }
    const labels = [state.options[state.selectedIndex].text, status.options[status.selectedIndex].text,
      reviewer.options[reviewer.selectedIndex].text];
    if (query) labels.push('Search: ' + search.value.trim());
    document.getElementById('showing').textContent = 'Showing ' + count + ' of ' + articles.length
      + ' saved finding records · ' + labels.join(' · ');
    document.getElementById('no-matches').hidden = count !== 0;
  }
  controls.hidden = false;
  for (const field of [search, state, status, reviewer]) field.addEventListener('input', update);
  document.getElementById('reset').addEventListener('click', () => {
    search.value = ''; state.value = 'current'; status.value = 'all'; reviewer.value = 'all'; update();
  });
  document.getElementById('print').addEventListener('click', () => window.print());
  update();
})();
"""


def _text(value) -> str:
    return html.escape(str(value), quote=True)


def _record(row: dict, reviewer_token: str) -> str:
    status = row["review_status"].replace("_", " ")
    fields = (("Account", row["account_no"]), ("Bill / expected period", row["finding_key"]),
              ("Property", row["property"]), ("Utility", row["utility"]),
              ("Finding kind", row["kind"]), ("Record report date", row["as_of"]))
    identity = "".join(f'<div><dt>{_text(key)}</dt><dd>{_text(value)}</dd></div>' for key, value in fields)
    pointers = review._read_json(row["evidence"].encode("utf-8"))
    evidence = "".join(f"<li><code>{_text(value)}</code></li>" for value in pointers)
    search = "\n".join(row[key] for key in (*review.OBSERVED, *review.EDITABLE))
    reviewer = _text(row["reviewer"]) if row["reviewer"] else "Unassigned"
    note = _text(row["note"]) if row["note"] else "No saved note."
    return f"""<article class="finding" data-state="{_text(row['row_state'])}"
data-status="{_text(row['review_status'])}" data-reviewer="{reviewer_token}" data-search="{_text(search)}">
<header class="finding-header"><div class="badges"><span class="badge">{_text(row['row_state'].title())}</span>
<span class="badge">Review: {_text(status)}</span></div>
<h3>{_text(LABEL.get(row['code'], row['code']))}</h3><code>{_text(row['code'])}</code></header>
<div class="finding-content"><dl>{identity}</dl><p class="detail">{_text(row['detail'])}</p>
<div class="annotation"><p><span class="note-label">Reviewer</span><br><span class="literal">{reviewer}</span></p>
<p><span class="note-label">Saved note</span><br><span class="literal">{note}</span></p></div>
<div class="source"><h4>Source CSV rows</h4><ul>{evidence}</ul></div>
<details><summary>Saved finding identity</summary><dl class="identity">
<div><dt>Finding</dt><dd><code>{_text(row['finding_id'])}</code></dd></div>
<div><dt>Evidence version</dt><dd><code>{_text(row['evidence_version'])}</code></dd></div>
<div><dt>Worksheet row</dt><dd><code>{_text(row['row_id'])}</code></dd></div></dl></details></div></article>"""


def _document(rows: list[dict], manifest: dict, name: str, digest: str) -> str:
    current = [row for row in rows if row["row_state"] == "current"]
    history = [row for row in rows if row["row_state"] != "current"]
    reviewers = sorted({row["reviewer"] for row in rows if row["reviewer"].strip()}, key=lambda value: (value.casefold(), value))
    tokens = {value: str(index) for index, value in enumerate(reviewers, 1)}
    options = "".join(f'<option value="{tokens[value]}">Assigned: {_text(value)}</option>' for value in reviewers)
    statuses = {value: sum(row["review_status"] == value for row in current) for value in review.STATUSES}

    def cards(records):
        return "".join(_record(row, tokens.get(row["reviewer"], "0")) for row in records)

    current_html = cards(current) or '<p class="empty">This worksheet has no current findings.</p>'
    history_html = cards(history) or '<p class="empty">This worksheet has no historical findings.</p>'
    mode = "SYNTHETIC DATA" if manifest["data_mode"] == "synthetic" else "Saved CSV review"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Utility Watch — saved review notes</title><style>{STYLE}</style></head><body>
<header><p class="eyebrow">Utility Watch · {_text(mode)}</p><h1>Review handoff</h1>
<p class="snapshot">Saved worksheet <b>{_text(name)}</b> · Report as of <b>{_text(manifest['as_of'])}</b></p>
<p class="intro">Read the follow-up assignments, notes and history already saved in this worksheet.
Current means current in its saved report. Reconcile a new source export to refresh those findings.</p>
<p class="notice">A reviewed annotation records human follow-up. This view does not clear findings,
approve invoices or issue payments. Changed and absent records retain earlier work; absence does not establish resolution.</p>
<div class="counts"><span><strong>{len(current)}</strong> current findings</span>
<span><strong>{statuses['open']}</strong> open</span><span><strong>{statuses['in_progress']}</strong> in progress</span>
<span><strong>{statuses['reviewed']}</strong> reviewed</span><span><strong>{len(history)}</strong> historical records</span></div></header>
<div class="controls" id="controls" hidden><div class="filters">
<label class="search-filter" for="search">Search findings and notes<input id="search" type="search" placeholder="Account, property, note, source row…"></label>
<label for="state">Record set<select id="state"><option value="current">Current findings</option><option value="history">Historical records</option><option value="all">All saved records</option></select></label>
<label for="status">Review status<select id="status"><option value="all">All review statuses</option><option value="open">Open</option><option value="in_progress">In progress</option><option value="reviewed">Reviewed</option></select></label>
<label for="reviewer">Reviewer<select id="reviewer"><option value="all">All reviewers</option><option value="0">Unassigned</option>{options}</select></label></div>
<div class="actions"><button class="secondary" id="reset" type="button">Reset filters</button><button id="print" type="button">Print shown records</button></div></div>
<p class="showing" id="showing" role="status">Showing all {len(rows)} saved finding records, including history.</p>
<noscript><p class="muted">All records are shown below. Use your browser’s Find and Print commands.</p></noscript>
<main><p class="empty no-matches" id="no-matches" hidden>No saved records match these filters.</p>
<section id="current" data-records="current" aria-labelledby="current-title"><div class="section-heading"><h2 id="current-title">Current in this worksheet</h2>
<p>These annotations apply to the evidence retained by this saved report. Totals above describe the complete worksheet.</p></div>{current_html}</section>
<section class="history" id="history" data-records="history" aria-labelledby="history-title"><div class="section-heading"><h2 id="history-title">Historical review records</h2>
<p>Changed findings have newer evidence. Absent findings were not in the later report or window. These annotations are historical.</p></div>{history_html}</section></main>
<footer><p>Worksheet format: {_text(review.SCHEMA)} · Checked service months from {_text(manifest['eval_from'])}.</p>
<p>This is a snapshot of the validated worksheet. It does not reopen or verify the original CSV exports and cannot authenticate a reviewer.</p>
<details><summary>Worksheet fingerprint</summary><p><code>{digest}</code></p></details></footer>
<script>{SCRIPT}</script></body></html>"""


def _publish(path: Path, document: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".uwatch-review-report-", suffix=".html", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as target:
            target.write(document)
            target.flush()
            os.fsync(target.fileno())
        os.link(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass


def render_report(worksheet: Path, out: Path) -> dict:
    """Validate the complete existing worksheet and publish one new HTML snapshot."""
    worksheet, out = Path(worksheet), Path(out)
    if out.is_symlink():
        raise ValueError("--out must name a new report, not a symbolic link")
    worksheet, out = worksheet.resolve(), out.resolve()
    if out == worksheet or out.exists():
        raise ValueError("--out must name a new report; the worksheet and existing files cannot be replaced")
    raw = worksheet.read_bytes()
    try:
        rows = review._previous(raw)
        _, incoming = review._csv(raw, "worksheet")
    except csv.Error as exc:
        raise ValueError(f"malformed worksheet CSV: {exc}") from exc
    manifest = next(row for _, row in incoming if row["row_state"] == "manifest")
    digest = hashlib.sha256(raw).hexdigest()
    document = _document(rows, manifest, worksheet.name, digest)
    if worksheet.read_bytes() != raw:
        raise ValueError("worksheet changed while building the report; inspect it and run again")
    _publish(out, document)
    current = sum(row["row_state"] == "current" for row in rows)
    return {"current": current, "history": len(rows) - current, "report": str(out), "worksheet_sha256": digest}
