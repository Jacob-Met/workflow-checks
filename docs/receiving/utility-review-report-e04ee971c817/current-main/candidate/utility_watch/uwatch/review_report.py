"""Read-only HTML snapshots of native Utility Watch review worksheets."""
from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import tempfile
from collections import Counter
from pathlib import Path

from .report import LABEL
from .review import STATUSES, _csv, _previous

_STATUS = {"open": "Open", "in_progress": "In progress", "reviewed": "Reviewed"}
_STATE = {
    "current": "Current finding",
    "changed": "Prior finding: evidence changed",
    "absent": "Prior finding: absent from the later report",
}
_STYLE = """
:root{color-scheme:light;font:16px/1.5 system-ui,sans-serif;color:#152b36;background:#f4f6f7}
body{margin:0 auto;max-width:1040px;padding:28px}
h1{font-size:2rem;line-height:1.15;margin:.2em 0}
h2{margin:1.8em 0 .6em}h3{font-size:1.1rem;margin:.2em 0 .8em}
a{color:#155c75}nav{display:flex;gap:20px;margin:18px 0}
.snapshot{padding:14px 18px;background:#e5eef1;border-left:4px solid #34778b}
.counts{font-weight:600}.finding{margin:16px 0;padding:20px;border:1px solid #bfccd2;
border-radius:8px;background:white}
.state{font-size:.85rem;font-weight:700;color:#415865;margin:0 0 6px}
dl{display:grid;grid-template-columns:minmax(125px,1fr) minmax(0,4fr);gap:5px 16px;margin:12px 0}
dt{font-weight:600}dd{margin:0;min-width:0;overflow-wrap:anywhere}
.multiline{white-space:pre-wrap}.identities{font-size:.72rem;color:#475c67}
.identities dd,code{font-family:ui-monospace,monospace;overflow-wrap:anywhere}
ul{padding-left:24px}.source{font-size:.85rem;overflow-wrap:anywhere}
.empty{padding:16px;border:1px dashed #93a6b0}footer{margin-top:28px;font-size:.85rem}
@media(max-width:600px){body{padding:14px}.finding{padding:14px}dl{grid-template-columns:1fr;gap:2px}
dd{margin-bottom:8px}.identities{font-size:.7rem}}
@media print{:root{background:white;color:black;font-size:10pt}body{max-width:none;padding:0}
nav{display:none}a{color:inherit}.finding{border-radius:0;margin:10pt 0;padding:10pt}
h2,h3,.state,dt{break-after:avoid}dd,.multiline{overflow:visible}.identities{font-size:7pt}
.snapshot{background:white;border:1px solid #777}}
"""


def _text(value: str) -> str:
    # Character references retain a quoted CSV carriage return in the parsed HTML text.
    return html.escape(value, quote=True).replace("\r", "&#13;")


def _fields(fields: list[tuple[str, str]], css: str = "") -> str:
    return f'<dl class="{css}">' + "".join(
        f"<dt>{_text(label)}</dt><dd>{_text(value)}</dd>" for label, value in fields
    ) + "</dl>"


def _record(row: dict) -> str:
    title = LABEL.get(row["code"], row["code"]) if row["kind"] == "flag" else row["code"]
    context = _fields([
        ("Account", row["account_no"]), ("Bill or period", row["finding_key"]),
        ("Property", row["property"] or "Not recorded"), ("Utility", row["utility"] or "Not recorded"),
        ("Kind / code", f'{row["kind"]} / {row["code"]}'),
        ("Report as of", row["as_of"]), ("Evaluation from", row["eval_from"]),
        ("Data mode", row["data_mode"]),
    ])
    review = (
        "<dl><dt>Review status</dt>"
        f'<dd>{_STATUS[row["review_status"]]}</dd><dt>Reviewer</dt>'
        f'<dd class="multiline">{_text(row["reviewer"]) if row["reviewer"] else "Unassigned"}</dd>'
        f'<dt>Note</dt><dd class="multiline">{_text(row["note"]) if row["note"] else "No note recorded"}</dd></dl>'
    )
    evidence = "".join(f"<li><code>{_text(value)}</code></li>" for value in json.loads(row["evidence"]))
    identities = _fields([
        ("Worksheet row ID", row["row_id"]), ("Finding ID", row["finding_id"]),
        ("Evidence version", row["evidence_version"]), ("Protected record SHA256", row["record_sha256"]),
    ], "identities")
    return (
        f'<article class="finding" id="row-{row["row_id"]}" data-row-state="{row["row_state"]}">'
        f'<p class="state">{_STATE[row["row_state"]]}</p><h3>{_text(title)}</h3>'
        + context + f'<p class="multiline">{_text(row["detail"])}</p>' + review
        + "<h4>Recorded source rows</h4><ul>" + evidence + "</ul>" + identities + "</article>"
    )


def render_html(raw: bytes, worksheet_name: str) -> tuple[str, dict]:
    """Validate the existing worksheet format and render the exact saved snapshot."""
    try:
        rows = _previous(raw)
        # The native validator has already checked the unique, complete manifest.
        manifest = next(row for _, row in _csv(raw, "worksheet")[1] if row["row_state"] == "manifest")
    except csv.Error as exc:
        raise ValueError(f"malformed CSV: {exc}") from exc

    current = [row for row in rows if row["row_state"] == "current"]
    history = [row for row in rows if row["row_state"] != "current"]
    statuses = Counter(row["review_status"] for row in current)
    digest = hashlib.sha256(raw).hexdigest()
    counts = " · ".join(f"{_STATUS[status]}: {statuses[status]}" for status in STATUSES)
    current_html = "".join(_record(row) for row in current) or '<p class="empty">No current findings in this worksheet.</p>'
    history_html = "".join(_record(row) for row in history) or '<p class="empty">No prior findings retained in this worksheet.</p>'
    mode = "SYNTHETIC DATA" if manifest["data_mode"] == "synthetic" else "SAVED REVIEW"
    document = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Utility Watch saved review</title><style>' + _STYLE + '</style></head><body>'
        '<header><p>UTILITY WATCH</p><h1>Saved review worksheet</h1>'
        f'<p>Report as of {_text(manifest["as_of"])} · Evaluation from {_text(manifest["eval_from"])}</p>'
        f'<div class="snapshot"><b>{mode} · Read-only snapshot</b>'
        '<p>This view records the saved worksheet. It does not recheck the source export or establish '
        'that these findings are still current. Reviewer names and notes are user-entered; '
        'worksheet checksums are integrity checks, not signatures.</p></div>'
        f'<p class="source">Worksheet: {_text(worksheet_name)}<br>Worksheet SHA256: <code>{digest}</code></p>'
        '<nav aria-label="Review sections"><a href="#current">Current findings</a>'
        '<a href="#history">Prior findings</a></nav></header><main>'
        f'<section id="current" aria-labelledby="current-heading"><h2 id="current-heading">Current findings ({len(current)})</h2>'
        f'<p class="counts">{counts}</p>' + current_html + '</section>'
        f'<section id="history" aria-labelledby="history-heading"><h2 id="history-heading">Prior findings ({len(history)})</h2>'
        '<p>Changed rows retain the review of earlier evidence. Absent rows were not present in the later '
        'report or evaluation window; absence does not establish resolution or payment. '
        'Prior annotations do not apply to a current finding.</p>' + history_html + '</section></main>'
        '<footer>A Reviewed status records human follow-up. It does not clear a checker flag, approve an '
        'invoice or change payment eligibility. Keep the worksheet and its source exports for further review.</footer>'
        '</body></html>\n'
    )
    return document, {"current": len(current), "history": len(history),
                      "statuses": {status: statuses[status] for status in STATUSES},
                      "worksheet_sha256": digest, "data_mode": manifest["data_mode"]}


def export_html(worksheet: Path, out: Path) -> dict:
    """Publish one complete new HTML file without replacing any existing destination."""
    worksheet, out = Path(worksheet), Path(out)
    if not worksheet.is_file():
        raise ValueError("--worksheet must name an existing saved worksheet file")
    document, result = render_html(worksheet.read_bytes(), worksheet.name)
    if out.is_symlink() or out.exists():
        raise ValueError("--out must name a new HTML file; existing destinations cannot be replaced")

    # Match the native review writer's complete-new-file publication contract.
    fd, temporary = tempfile.mkstemp(prefix=".uwatch-review-report-", suffix=".html", dir=out.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as target:
            target.write(document)
            target.flush()
            os.fsync(target.fileno())
        os.link(temporary, out)
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass
    return result
