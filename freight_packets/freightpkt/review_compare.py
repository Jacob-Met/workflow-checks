"""Compare two retained native freight review bundles without changing either."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
from html import escape
import io
import json
from pathlib import Path
import re
import zipfile
import zlib

from .handoff import review_version

SECTIONS = ("stops", "flags", "fines", "settlements", "exceptions", "packets")
MEMBERS = ("index.html", "packet.html", "evidence.json", "review.json", "manifest.json")


class BundleError(ValueError):
    """A supplied copy is not a complete, internally bound native v1 bundle."""


@dataclass(frozen=True)
class ReviewCopy:
    source: str
    zip_bytes: int
    zip_sha256: str
    manifest: dict
    evidence: dict
    review: dict


def _require(condition, message):
    if not condition:
        raise BundleError(message)


def _fields(value, expected, label):
    _require(isinstance(value, dict) and set(value) == set(expected),
             f"{label} has unexpected or missing fields")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _token(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise BundleError("JSON object has a duplicate key")
        value[key] = item
    return value


def _constant(value):
    raise BundleError("JSON contains a nonfinite number")


def _json(raw, label):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                          parse_constant=_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise BundleError(f"{label} is not unambiguous UTF-8 JSON: {error}") from error


def decode_bundle(raw: bytes, source: str = "supplied copy") -> ReviewCopy:
    """Validate the native member/JSON/content bindings; never extract HTML."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            _require(len(names) == len(MEMBERS) and set(names) == set(MEMBERS),
                     "bundle must have exactly five unique native members")
            _require(not any(entry.is_dir() for entry in entries),
                     "bundle members must be files")
            files = {entry.filename: archive.read(entry) for entry in entries}
    except BundleError:
        raise
    except (OSError, ValueError, RuntimeError, EOFError, zipfile.BadZipFile,
            zlib.error) as error:
        raise BundleError(f"cannot read native ZIP members: {error}") from error

    manifest = _json(files["manifest.json"], "manifest.json")
    _fields(manifest, ("schema", "load_id", "evidence_version", "review_version", "files"),
            "manifest")
    _require(manifest["schema"] == "freight-review-bundle.v1", "unsupported bundle schema")
    lid = manifest["load_id"]
    _require(isinstance(lid, str) and bool(lid), "load_id must be a nonempty string")
    _require(_token(manifest["evidence_version"]) and _token(manifest["review_version"]),
             "manifest versions must be SHA-256 values")
    rows = manifest["files"]
    _require(isinstance(rows, list) and len(rows) == 4,
             "manifest must bind all four payload members")
    bound = set()
    for row in rows:
        _fields(row, ("path", "bytes", "sha256"), "manifest file record")
        name = row["path"]
        _require(isinstance(name, str) and name in MEMBERS[:-1] and name not in bound,
                 "manifest file paths must uniquely name the four payload members")
        bound.add(name)
        _require(type(row["bytes"]) is int and row["bytes"] >= 0 and _token(row["sha256"]),
                 "manifest file size/hash is invalid")
        _require(row["bytes"] == len(files[name]) and row["sha256"] == _sha(files[name]),
                 f"{name} does not match its manifest binding")

    evidence = _json(files["evidence.json"], "evidence.json")
    _fields(evidence, ("schema", "packet_sha256", *SECTIONS), "evidence")
    _require(evidence["schema"] == "freight-review.v1", "unsupported evidence schema")
    for section in SECTIONS:
        values = evidence[section]
        _require(isinstance(values, list) and all(
            isinstance(row, dict) and row.get("load_id") == lid for row in values),
            f"{section} must contain records for the selected load")
    _require(evidence["packet_sha256"] == _sha(files["packet.html"]),
             "packet.html does not match the evidence packet digest")

    review = _json(files["review.json"], "review.json")
    _fields(review, ("schema", "load_id", "evidence_version", "review_version", "review"),
            "review snapshot")
    _require(review["schema"] == "freight-review-snapshot.v1",
             "unsupported review snapshot schema")
    _require(all(review[key] == manifest[key]
                 for key in ("load_id", "evidence_version", "review_version")),
             "review snapshot identity differs from manifest")
    saved = review["review"]
    _require(saved is None or isinstance(saved, dict), "saved review must be an object or null")
    if saved is not None:
        history = saved.get("history", [])
        _require(isinstance(history, list) and all(isinstance(row, dict) for row in history),
                 "saved history must be a list of review records")
    try:
        encoded = json.dumps(evidence, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
        _require(_sha(encoded) == manifest["evidence_version"],
                 "evidence does not match its canonical version")
        _require(review_version(saved) == manifest["review_version"],
                 "saved review does not match its canonical version")
    except (ValueError, UnicodeError, RecursionError) as error:
        raise BundleError(f"invalid native content identity: {error}") from error
    return ReviewCopy(str(source), len(raw), _sha(raw), manifest, evidence, review)


def read_bundle(path: Path) -> ReviewCopy:
    """Read one supplied file once; the returned values are detached from it."""
    path = Path(path)
    return decode_bundle(path.read_bytes(), str(path))


def record_changes(rows_a, rows_b):
    """Compare canonical native JSON records, including duplicate occurrences."""
    def counts(rows):
        return Counter(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=True, allow_nan=False) for row in rows)
    a, b = counts(rows_a), counts(rows_b)
    def records(counter):
        return [{"record": json.loads(key), "count": counter[key]} for key in sorted(counter)]
    return {
        "a_count": sum(a.values()), "b_count": sum(b.values()),
        "unchanged": records(a & b), "only_a": records(a - b), "only_b": records(b - a),
    }


def _text(value):
    # Native saved reviews may contain a legacy surrogate. Show its escape literally.
    return escape(str(value).encode("utf-8", errors="backslashreplace").decode("utf-8"),
                  quote=True)


def _display(value):
    return _text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                            allow_nan=False))


def _count(records):
    return sum(item["count"] for item in records)


def _group(title, records):
    body = "".join(
        f'<li><p>Occurrences: <strong>{item["count"]}</strong></p>'
        f'<pre>{_display(item["record"])}</pre></li>' for item in records)
    return f"<h3>{title} ({_count(records)} occurrences)</h3>" + (
        f'<ol class="records">{body}</ol>' if records else "<p>None.</p>")


CSS = """
body{font:16px/1.5 system-ui,sans-serif;color:#1b1f24;max-width:1100px;margin:2rem auto;padding:0 1rem}
h1{font-size:1.8rem}h2{margin-top:2rem}h3{font-size:1.05rem}.notice{background:#fff4ce;padding:1rem}
table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border:1px solid #bbc3ce;padding:.5rem;text-align:left;vertical-align:top}
th{background:#eef1f5}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7fa;padding:.8rem;font-size:.85rem}
code,td{overflow-wrap:anywhere}.records{padding-left:1.5rem}.records li{break-inside:avoid}
.copies{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}nav a{display:inline-block;padding:.45rem}
a:focus-visible{outline:3px solid #245fa3;outline-offset:2px}
@media(max-width:650px){.copies{grid-template-columns:1fr}body{padding:0 .6rem}th,td{padding:.3rem;font-size:.85rem}}
@media print{body{max-width:none;margin:0;font-size:10pt}nav{display:none}pre{background:white}h2,h3{break-after:avoid}.copies{display:block}}
"""


def render_comparison(a: ReviewCopy, b: ReviewCopy) -> str:
    """Render a complete static comparison of two validated same-load copies."""
    _require(a.manifest["load_id"] == b.manifest["load_id"],
             "copies have different load IDs; no comparison was written")
    changes = {name: record_changes(a.evidence[name], b.evidence[name]) for name in SECTIONS}
    overview = "".join(
        f'<tr><th><a href="#{name}">{name}</a></th><td>{row["a_count"]}</td>'
        f'<td>{row["b_count"]}</td><td>{_count(row["unchanged"])}</td>'
        f'<td>{_count(row["only_a"])}</td><td>{_count(row["only_b"])}</td></tr>'
        for name, row in changes.items())
    sections = "".join(
        f'<section id="{name}"><h2>{name}</h2>'
        + _group("Only in Copy A", row["only_a"])
        + _group("Only in Copy B", row["only_b"])
        + _group("Unchanged", row["unchanged"]) + "</section>"
        for name, row in changes.items())
    identities = [
        ("Source path", a.source, b.source),
        ("ZIP bytes", a.zip_bytes, b.zip_bytes),
        ("ZIP SHA-256", a.zip_sha256, b.zip_sha256),
        ("Packet SHA-256", a.evidence["packet_sha256"], b.evidence["packet_sha256"]),
        ("Evidence version", a.manifest["evidence_version"], b.manifest["evidence_version"]),
        ("Saved review version", a.manifest["review_version"], b.manifest["review_version"]),
    ]
    identity_rows = "".join(
        f"<tr><th>{name}</th><td>{_text(va)}</td><td>{_text(vb)}</td></tr>"
        for name, va, vb in identities)
    files_a = {row["path"]: row for row in a.manifest["files"]}
    files_b = {row["path"]: row for row in b.manifest["files"]}
    member_rows = "".join(
        f'<tr><th>{name}</th><td>{files_a[name]["bytes"]} bytes<br>'
        f'<code>{files_a[name]["sha256"]}</code></td>'
        f'<td>{files_b[name]["bytes"]} bytes<br><code>{files_b[name]["sha256"]}</code></td>'
        f'<td>{"Same bytes" if files_a[name]["sha256"] == files_b[name]["sha256"] else "Changed bytes"}</td></tr>'
        for name in MEMBERS[:-1])
    reviews = []
    for label, copy in (("Copy A", a), ("Copy B", b)):
        saved = copy.review["review"]
        if saved is None:
            heading = "<p>No saved review is recorded in this copy.</p>"
        else:
            state = _display(saved["review_state"]) if "review_state" in saved else "Not recorded"
            decision = _display(saved["decision"]) if "decision" in saved else "Not recorded"
            heading = f"<p>Recorded state: <code>{state}</code><br>Recorded decision: <code>{decision}</code></p>"
        reviews.append(f"<article><h3>{label}</h3>{heading}<pre>{_display(saved)}</pre></article>")
    same_review = a.manifest["review_version"] == b.manifest["review_version"]
    same_evidence = a.manifest["evidence_version"] == b.manifest["evidence_version"]
    nav = "".join(f'<a href="#{name}">{name}</a>' for name in SECTIONS)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Saved freight review comparison — {_text(a.manifest["load_id"])}</title><style>{CSS}</style></head>
<body><h1>Saved freight review comparison</h1><h2>Load {_text(a.manifest["load_id"])}</h2>
<p class="notice">Copy A and Copy B are the supplied order, not an inferred chronology.
Recorded review state belongs to each retained copy; this report establishes no current approval.
Nothing is sent, filed, invoiced or paid.</p>
<p>Evidence identity: <strong>{"same" if same_evidence else "different"}</strong>.
Saved review identity: <strong>{"same" if same_review else "different"}</strong>.</p>
<p>Records are compared by their complete native JSON values. Equal duplicates retain occurrence counts.
Rows are not paired by stop number, invoice, position or guessed identity.</p>
<nav aria-label="Comparison sections"><a href="#identities">Copy identities</a><a href="#reviews">Saved reviews</a>{nav}</nav>
<h2>Record counts</h2><table><thead><tr><th>Section</th><th>Copy A</th><th>Copy B</th><th>Unchanged</th><th>Only A</th><th>Only B</th></tr></thead>
<tbody>{overview}</tbody></table>
<section id="reviews"><h2>Saved review and history</h2><p>Complete recorded values are shown below.
A recorded approval in one copy does not approve changed evidence in the other.</p>
<div class="copies">{''.join(reviews)}</div></section>
{sections}
<section id="identities"><h2>Copy identities</h2><table><thead><tr><th>Identity</th><th>Copy A</th><th>Copy B</th></tr></thead>
<tbody>{identity_rows}</tbody></table>
<h3>Exact payload member bindings</h3><p>ZIP container or cover bytes can differ even when evidence and saved review identities are the same.</p>
<table><thead><tr><th>Member</th><th>Copy A</th><th>Copy B</th><th>Comparison</th></tr></thead><tbody>{member_rows}</tbody></table>
<p>Both manifests and their canonical content bindings were checked. These checks establish internal consistency,
not authenticated authorship or freshness. The original ZIP inputs remain the source copies.</p></section>
<p>No supplied packet or cover HTML is embedded or executed. Original input files and any changes made after
these snapshots are outside this comparison. Use the browser's Print command to print the complete report.</p>
</body></html>
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare two retained native freight review ZIPs.")
    parser.add_argument("copy_a", type=Path, help="first supplied copy (not necessarily earlier)")
    parser.add_argument("copy_b", type=Path, help="second supplied copy (not necessarily later)")
    parser.add_argument("--out", required=True, type=Path, help="new comparison HTML file; must not exist")
    args = parser.parse_args(argv)
    try:
        a, b = read_bundle(args.copy_a), read_bundle(args.copy_b)
        report = render_comparison(a, b).encode("utf-8")
        # Validation and complete rendering precede exclusive creation. A later I/O
        # failure can leave a partial new file; never replace it on a later invocation.
        with args.out.open("xb") as target:
            target.write(report)
    except (BundleError, OSError) as error:
        parser.exit(2, f"review comparison: {error}\n")
    print(f"Comparison written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
