"""Create and read back a deterministic, dependency-free static demo ZIP."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

DEMO = Path(__file__).resolve().parents[1]
SITE_FILES = ("app.mjs", "data.mjs", "index.html", "model.mjs", "scenario-record.mjs", "styles.css")
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True, help="New ZIP path")
parser.add_argument("--receipt", type=Path, required=True, help="New JSON receipt path")
args = parser.parse_args()
payloads = {"site/" + name: (DEMO / "site" / name).read_bytes() for name in SITE_FILES}
payloads["LICENSE"] = (DEMO.parents[1] / "LICENSE").read_bytes()
for name in ["serve.py", "install.py"]:
    payloads["tools/" + name] = (DEMO / "tools" / name).read_bytes()
payloads["README.txt"] = b"""FREIGHT WHAT-IF / WORKFLOW CHECKS

Synthetic freight reviewer demo. All scenarios are invented.
No third-party packages, external services or API keys are required.

RUN
1. Extract this ZIP into a new directory.
2. From that directory, run: python3 tools/serve.py
3. Open http://127.0.0.1:8765/
4. Press Ctrl-C in the terminal to stop the server.
   Use --port 8877 if 8765 is already occupied.

Use a local HTTP server; opening index.html directly as file:// will not
load JavaScript modules in browsers.

INSTALL / VERIFY / ROLLBACK (optional)
python3 tools/install.py install --target /your/new/freight-site
python3 tools/install.py verify --target /your/new/freight-site
python3 tools/serve.py --site /your/new/freight-site
Stop the server, then:
python3 tools/install.py rollback --target /your/new/freight-site

The installer creates a NEW target. It never overwrites an existing one.
Rollback refuses edited content, extra files or symlinks. Leave those intact
and review them yourself rather than deleting another person's work.

WHAT IT DOES
Four authored cases; editable timing, detention terms and invoice charges.
Findings include exact reasons and scenario evidence pointers.
Download records contain the loaded baseline, current inputs/results and
canonical rule source pins. Invalid inputs pause the review and download.
An evidence exception is shown as no automatic claim.

SCOPE
One brokered stop, one same-row arrival/departure pair, one known rate con,
one invoice. Civil minute times, USD integer cents. Not a live carrier tool,
payment approval or settlement engine. Duplicate invoices, missing rate
confirmations, multi-stop matching, fines and settlement are outside scope.
Edits remain in page memory and reset on refresh. Use Download record to save\nthem. Open saved record checks that existing v1 JSON and previews all sixteen\ninputs before explicit replacement. Cancel keeps the current draft. Records\nare limited to 1 MiB UTF-8 and must match this demo's pinned rules and preset;\nsaved calculations are checked against fresh results, not trusted as authority.

SOURCE AND VERIFICATION
https://github.com/Jacob-Met/workflow-checks/issues/17
Source, actual-Python parity oracle, browser receiving and install receipts:
demos/freight-whatif/ in the workflow-checks repository.
manifest.json pins every file in this archive and the canonical rule source.
"""
data = json.loads((DEMO / "site/data.mjs").read_text().split("export const data = ", 1)[1].removesuffix(";\n"))
manifest = {
    "schema": "workflow-checks.freight-whatif.bundle.v1",
    "provenance": data["provenance"],
    "files": {name: {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()} for name, payload in sorted(payloads.items())},
}
payloads["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
if not args.output.parent.is_dir():
    parser.error("--output parent must already exist")
with zipfile.ZipFile(args.output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for name, payload in sorted(payloads.items()):
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, payload)
with zipfile.ZipFile(args.output) as archive:
    assert sorted(archive.namelist()) == sorted(payloads)
    for name, payload in payloads.items():
        assert archive.read(name) == payload, name
receipt = {
    "schema": "workflow-checks.freight-whatif.bundle-receipt.v1",
    "archive_name": args.output.name, "bytes": args.output.stat().st_size,
    "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
    "entries": sorted(payloads), "all_archive_entries_read_back_exact": True,
    "manifest_sha256": hashlib.sha256(payloads["manifest.json"]).hexdigest(),
    "packager_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
with args.receipt.open("x") as stream:
    stream.write(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt))
