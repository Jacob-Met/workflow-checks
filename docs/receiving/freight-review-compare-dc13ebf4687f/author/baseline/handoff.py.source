"""Portable, read-only handoff for one generated freight packet and saved review."""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from html import escape


def _json_bytes(value) -> bytes:
    # Escaped JSON preserves every saved string, including a legacy surrogate.
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True,
                       allow_nan=False) + "\n").encode("utf-8")


def review_version(review) -> str:
    """Identity of the exact displayed native decision view, including history."""
    encoded = json.dumps(review, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def bundle_filename(load_id: str, evidence_version: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_-]+", "-", load_id).strip("-")[:64] or "load"
    return f"freight-review-{label}-{evidence_version[:12]}.zip"


def _text(value) -> str:
    text = str(value if value is not None else "").encode("utf-8", errors="backslashreplace").decode("utf-8")
    return escape(text, quote=True)


def _review_heading(review) -> str:
    if review is None:
        return "Not reviewed"
    state = review.get("review_state")
    if state == "cleared":
        return "Saved review cleared"
    if state == "current" and review.get("decision") in {"approve", "adjust", "reject"}:
        return "Current saved review: " + {"approve": "Approve", "adjust": "Needs adjust",
                                          "reject": "Reject"}[review["decision"]]
    return {"stale": "Previous review — review again",
            "unbound": "Previous review has no evidence binding — review again",
            "missing": "Previous review has no readable packet"}.get(
                state, "Unrecognized saved review — review again")


def _cover(load_id, evidence_version, saved_version, evidence, review) -> bytes:
    history = review.get("history", []) if review else []
    if not isinstance(history, list) or any(not isinstance(row, dict) for row in history):
        raise ValueError("saved review history is not a list of review records")
    details = ""
    if review:
        details = (f"<p>Recorded decision: <strong>{_text(review.get('decision'))}</strong>"
                   f"<br>Recorded at: {_text(review.get('at'))}</p>"
                   f"<h3>Saved note</h3><p class=\"note\">{_text(review.get('note')) or 'No saved note.'}</p>")
    previous = "".join(
        f"<li><strong>{_text(row.get('decision'))}</strong> · {_text(row.get('at'))}"
        f"<p class=\"note\">{_text(row.get('note'))}</p>"
        f"<small>Recorded evidence: {_text(row.get('evidence_version')) or 'Not recorded'}</small></li>"
        for row in reversed(history))
    section_counts = "".join(f"<li>{_text(name)}: {len(rows)} selected-load record(s)</li>"
                             for name, rows in evidence.items() if isinstance(rows, list))
    html = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Freight review handoff — {_text(load_id)}</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;max-width:850px;margin:2rem auto;padding:0 1rem;color:#1b1f24}}
h1{{font-size:1.7rem}}h2{{font-size:1.25rem}}.draft{{background:#fff4ce;border:1px solid #d8a800;padding:1rem}}
.note{{white-space:pre-wrap;overflow-wrap:anywhere}}code,small{{overflow-wrap:anywhere}}li{{margin:.6rem 0}}
@media print{{body{{margin:0}}a{{color:inherit}}}}
</style>
<h1>Freight review handoff</h1><h2>Load {_text(load_id)}</h2>
<p class="draft"><strong>Draft review.</strong> Nothing is sent, filed, invoiced or paid.
A reviewer decision is not a payment instruction.</p>
<h2>{_text(_review_heading(review))}</h2>
{details}
<p>The saved review and its history below are copied from the local review record.
An earlier or unbound review does not become approval of this packet.</p>
<h2>Open the evidence</h2>
<ul><li><a href="packet.html">Original generated packet</a></li>
<li><a href="evidence.json">Selected-load report records and original source references</a></li>
<li><a href="review.json">Exact saved review and history</a></li>
<li><a href="manifest.json">File sizes and SHA-256 checksums</a></li></ul>
<ul>{section_counts}</ul>
<details><summary>Snapshot identity</summary>
<p>Packet/report evidence: <code>{_text(evidence_version)}</code><br>
Saved review: <code>{_text(saved_version)}</code></p></details>
<h2>Previous saved reviews ({len(history)})</h2>
{('<ol>' + previous + '</ol>') if previous else '<p>No previous reviews are recorded.</p>'}
<p>Only this load is included. Original input files, other-load reports and the global audit log
are not included; the original file:row references remain in the copied evidence.</p>
<p>This is a snapshot. Later changes in the review app do not update this file.</p>
</html>
"""
    # A legacy surrogate is exact in JSON and visible as a backslash escape in HTML.
    return html.encode("utf-8")


def build_bundle(load_id: str, packet: bytes, evidence: dict, saved_review,
                 evidence_version: str, saved_version: str) -> bytes:
    """Serialize an already fenced snapshot without reading or writing source files."""
    canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != evidence_version:
        raise ValueError("packet/report snapshot does not match its evidence version")
    if evidence.get("packet_sha256") != hashlib.sha256(packet).hexdigest():
        raise ValueError("packet bytes do not match the selected evidence")
    if review_version(saved_review) != saved_version:
        raise ValueError("saved review does not match its version")
    members = {
        "index.html": _cover(load_id, evidence_version, saved_version, evidence, saved_review),
        "packet.html": packet,
        "evidence.json": _json_bytes(evidence),
        "review.json": _json_bytes({"schema": "freight-review-snapshot.v1", "load_id": load_id,
                                   "evidence_version": evidence_version, "review_version": saved_version,
                                   "review": saved_review}),
    }
    members["manifest.json"] = _json_bytes({
        "schema": "freight-review-bundle.v1", "load_id": load_id,
        "evidence_version": evidence_version, "review_version": saved_version,
        "files": [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                  for name, data in members.items()],
    })
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as archive:
        for name, data in members.items():
            item = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            archive.writestr(item, data)
    return result.getvalue()

