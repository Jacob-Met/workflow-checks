"""Assemble selected, already fenced per-load review handoffs without file writes."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from html import escape

from .handoff import _review_heading

MAX_BATCH_LOADS = 100
_FIELDS = {"load_id", "evidence_version", "review_version"}
_MEMBERS = ("index.html", "packet.html", "evidence.json", "review.json", "manifest.json")


def validate_selection(loads) -> list[dict]:
    """Keep exact displayed identities and order; never choose an ambiguous load."""
    if not isinstance(loads, list) or not 1 <= len(loads) <= MAX_BATCH_LOADS:
        raise ValueError(f"choose between 1 and {MAX_BATCH_LOADS} saved reviews")
    selected, seen = [], set()
    for row in loads:
        if not isinstance(row, dict) or set(row) != _FIELDS:
            raise ValueError("each selected load needs only load_id, evidence_version and review_version")
        load_id = row["load_id"]
        if not isinstance(load_id, str) or not load_id:
            raise ValueError("each selection must identify a current load")
        if load_id in seen:
            raise ValueError("a load may be selected only once")
        for key in ("evidence_version", "review_version"):
            value = row[key]
            if not isinstance(value, str) or len(value) != 64 or any(
                    c not in "0123456789abcdef" for c in value):
                raise ValueError("each selection needs its displayed evidence and saved review versions")
        seen.add(load_id)
        selected.append(dict(row))
    return selected


def _json(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
            + "\n").encode("utf-8")


def _text(value) -> str:
    return escape(str("" if value is None else value).encode(
        "utf-8", errors="backslashreplace").decode("utf-8"), quote=True)


def build_batch_bundle(bundles: list[tuple[dict, str, bytes]]) -> tuple[str, bytes]:
    """Preserve existing per-load ZIPs and members inside ordinal, collision-safe paths."""
    selection = validate_selection([row for row, _, _ in bundles])
    members, loads = {}, []
    for position, (expected, filename, raw) in enumerate(bundles, 1):
        directory = f"loads/{position:04d}/"
        # These archives come only from the existing native per-load exporter.
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = archive.namelist()
            if len(names) != len(_MEMBERS) or set(names) != set(_MEMBERS):
                raise ValueError("a saved review bundle has unexpected members")
            original = {name: archive.read(name) for name in _MEMBERS}
        saved = json.loads(original["review.json"])
        if any(saved.get(key) != expected[key] for key in _FIELDS):
            raise ValueError("a saved review bundle does not match the selected identity")
        review = saved.get("review")
        row = {
            **expected,
            "index_path": directory + "index.html",
            "bundle_path": directory + "review.zip",
            "bundle_filename": filename,
            "review_state": None if review is None else review.get("review_state"),
            "decision": None if review is None else review.get("decision"),
            "review_heading": _review_heading(review),
        }
        loads.append(row)
        for name, data in original.items():
            members[directory + name] = data
        members[row["bundle_path"]] = raw

    links = "".join(
        f'<li><h2>{number}. Load {_text(row["load_id"])}</h2>'
        f'<p>{_text(row["review_heading"])}</p>'
        f'<p><a href="{row["index_path"]}">Open saved review and packet</a> · '
        f'<a href="{row["bundle_path"]}" download="{_text(row["bundle_filename"])}">'
        f'Download this original review ZIP</a></p></li>'
        for number, row in enumerate(loads, 1))
    members["index.html"] = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Selected freight reviews ({len(loads)})</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;max-width:850px;margin:2rem auto;padding:0 1rem;color:#1b1f24}}
h1{{font-size:1.7rem}}h2{{font-size:1.15rem}}li{{margin:1.5rem 0;overflow-wrap:anywhere}}ul{{padding-left:1.3rem}}
.draft{{background:#fff4ce;border:1px solid #d8a800;padding:1rem}}
@media print{{body{{margin:0}}a{{color:inherit}}}}
</style>
<h1>Selected freight reviews ({len(loads)})</h1>
<p class="draft"><strong>Draft review snapshots.</strong> Nothing is sent, filed, invoiced or paid.
A saved reviewer decision is not a payment instruction.</p>
<p>These are the selected loads in the requested order. Each review keeps its original packet,
report records, saved note and history. Earlier or unbound approvals do not become current approvals.</p>
<ul>{links}</ul>
<p>Open each saved review to inspect its exact evidence and review identity. The original
single-load ZIP and its five member files are retained unchanged in that load's directory.</p>
<p><a href="manifest.json">Batch contents and SHA-256 checksums</a></p>
<p>Original input files, unselected loads and the global audit log are not included.
This is a snapshot; later app changes do not update these files.</p>
</html>
""".encode("utf-8")
    manifest = {"schema": "freight-review-batch.v1", "loads": loads,
                "files": [{"path": name, "bytes": len(data),
                           "sha256": hashlib.sha256(data).hexdigest()}
                          for name, data in members.items()]}
    members["manifest.json"] = _json(manifest)
    identity = hashlib.sha256(members["manifest.json"]).hexdigest()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in members.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return f"freight-review-batch-{len(selection)}-{identity[:12]}.zip", output.getvalue()
