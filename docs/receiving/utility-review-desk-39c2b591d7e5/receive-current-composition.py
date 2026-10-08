"""Current-main CLI/identity composition control; disposable fictional data only."""
from __future__ import annotations
import csv
import hashlib
import html
import io
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
import urllib.request

from uwatch import review

ROOT = Path(sys.argv[1])
OLD = Path(sys.argv[2])
ROOT.mkdir()
COMMANDS = []
CHECKS = []
SERVER = None
SERVER_LOG = ROOT / "desk-stdout.txt"
SERVER_ERROR = ROOT / "desk-stderr.txt"

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def pin_tree(root):
    return {str(p.relative_to(root)): sha(p.read_bytes())
            for p in sorted(root.rglob("*")) if p.is_file()}

def run(args):
    cmd = [sys.executable, "-B", "-m", "uwatch", *args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    COMMANDS.append({"argv": cmd, "status": result.returncode,
                     "stdout": result.stdout, "stderr": result.stderr})
    if result.returncode:
        raise AssertionError(json.dumps(COMMANDS[-1]))
    return result

def rows(raw):
    review._previous(raw)
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline="")))

def mark(name, **detail):
    CHECKS.append({"name": name, **detail})

failure = None
try:
    fixture = json.loads((OLD / "fixture" / "fixture.json").read_text())
    old_download = OLD / "downloads" / "01-filtered-edits.csv"
    original_inputs = pin_tree(OLD / "fixture")
    old_raw = old_download.read_bytes()
    old_rows = rows(old_raw)
    old_current = {r["finding_id"]: r for r in old_rows if r["row_state"] == "current"}
    report = ROOT / "current-report"
    run(["run", "--data", fixture["data"], "--out", str(report),
         "--as-of", "2024-02-05", "--eval-from", "2024-01-01"])
    selected = ROOT / "current-origin.csv"
    run(["review", "--data", fixture["data"], "--report", str(report / "summary.json"),
         "--previous", str(old_download), "--out", str(selected)])
    selected_raw = selected.read_bytes()
    selected_rows = rows(selected_raw)
    now = {r["finding_id"]: r for r in selected_rows if r["row_state"] == "current"}
    history = {r["row_id"]: r for r in selected_rows
               if r["row_state"] in ("changed", "absent")}
    assert set(now) == set(old_current)
    for identity, row in now.items():
        prior = old_current[identity]
        assert {k: row[k] for k in review.OBSERVED} == {k: prior[k] for k in review.OBSERVED}
        assert row["evidence_version"] != prior["evidence_version"]
        assert row["row_id"] != prior["row_id"]
        assert (row["review_status"], row["reviewer"], row["note"]) == ("open", "", "")
    for prior in old_rows:
        if prior["row_state"] == "manifest":
            continue
        old_history = history[prior["row_id"]]
        if prior["row_state"] == "current":
            assert old_history["row_state"] == "changed"
            assert {k: v for k, v in old_history.items() if k not in ("row_state", "record_sha256")} == {
                k: v for k, v in prior.items() if k not in ("row_state", "record_sha256")}
        else:
            assert old_history == prior
    mark("current engine identity reopens exact displayed findings and preserves old downloaded annotations as history",
         current=len(now), history=len(history), old_download_sha256=sha(old_raw))

    stdout = SERVER_LOG.open("w")
    stderr = SERVER_ERROR.open("w")
    server_args = [sys.executable, "-B", "-m", "uwatch", "review-desk",
                   "--worksheet", str(selected), "--port", "0"]
    SERVER = subprocess.Popen(server_args, stdout=stdout, stderr=stderr, text=True)
    deadline = time.monotonic() + 10
    origin = None
    while time.monotonic() < deadline:
        lines = SERVER_LOG.read_text().splitlines()
        if lines and lines[0].startswith("Utility Watch review desk: "):
            origin = lines[0].split(": ", 1)[1]
            break
        if SERVER.poll() is not None:
            raise AssertionError("current CLI desk exited: " + SERVER_ERROR.read_text())
        time.sleep(0.02)
    assert origin is not None
    with urllib.request.urlopen(origin + "/api/worksheet", timeout=5) as response:
        view = json.load(response)
    assert view["snapshot"] == sha(selected_raw)
    assert view["rows"] == [r for r in selected_rows if r["row_state"] != "manifest"]
    edit_row = next(r for r in now.values() if r["account_no"] == "A")
    edit = {"row_id": edit_row["row_id"], "review_status": "reviewed",
            "reviewer": "New engine reviewer",
            "note": "Explicit current-engine review. Preserve prior notes as history."}
    request = urllib.request.Request(
        origin + "/api/download",
        data=json.dumps({"snapshot": view["snapshot"], "changes": [edit]}).encode(),
        headers={"Content-Type": "application/json", "X-Review-Token": view["token"], "Origin": origin})
    with urllib.request.urlopen(request, timeout=5) as response:
        assert response.status == 200
        assert response.headers["Content-Disposition"] == 'attachment; filename="utility-review-edited.csv"'
        downloaded = response.read()
    expected = [dict(r) for r in selected_rows]
    for row in expected:
        if row["row_id"] == edit["row_id"]:
            row.update({k: edit[k] for k in review.EDITABLE})
    assert rows(downloaded) == expected
    assert selected.read_bytes() == selected_raw
    edited = ROOT / "current-desk-download.csv"
    edited.write_bytes(downloaded)
    mark("merged current CLI serves and downloads a complete current-engine worksheet through real HTTP",
         download_sha256=sha(downloaded), rows=len(expected))
    SERVER.send_signal(signal.SIGINT)
    assert SERVER.wait(timeout=10) == 0
    stdout.close()
    stderr.close()
    COMMANDS.append({"argv": server_args, "status": SERVER.returncode,
                     "stdout": SERVER_LOG.read_text(), "stderr": SERVER_ERROR.read_text()})
    assert SERVER_ERROR.read_text() == ""

    reconciled = ROOT / "current-reconciled.csv"
    run(["review", "--data", fixture["data"], "--report", str(report / "summary.json"),
         "--previous", str(edited), "--out", str(reconciled)])
    assert rows(reconciled.read_bytes()) == expected
    mark("current native reconciliation retains only the explicit new-origin annotation",
         reconciled_sha256=sha(reconciled.read_bytes()))

    printable = ROOT / "current-review.html"
    run(["review-report", "--worksheet", str(edited), "--out", str(printable)])
    document = printable.read_text()
    assert html.escape(edit["reviewer"]) in document
    assert html.escape(edit["note"]) in document
    assert "Léa 李" in document
    assert all(p["stderr"] == "" for p in COMMANDS)
    assert pin_tree(OLD / "fixture") == original_inputs
    assert old_download.read_bytes() == old_raw
    assert selected.read_bytes() == selected_raw
    mark("preserved printable report consumes the desk download; all original source and selected bytes remain exact",
         html_sha256=sha(printable.read_bytes()))
except Exception as exc:
    import traceback
    failure = {"message": str(exc), "traceback": traceback.format_exc()}
finally:
    if SERVER is not None and SERVER.poll() is None:
        SERVER.send_signal(signal.SIGINT)
        try:
            SERVER.wait(timeout=5)
        except subprocess.TimeoutExpired:
            SERVER.kill()
            SERVER.wait(timeout=5)
    receipt = {"checks": CHECKS, "failure": failure, "commands": COMMANDS,
               "source_base": "5a70e458ed455d47ef672ed9b5a614ec59812f0c",
               "candidate_tree": "12266e043adaeb99d49c42a5191dfdf5efdbe92b",
               "original_product": "fa057a67c428fb6ccd1517e7f9eb51d946ab12d6",
               "engine_sha256": sha(Path(review.engine.__file__).read_bytes()),
               "validator_sha256": sha(Path(review.__file__).read_bytes()),
               "scope": "Actual CLI/HTTP/current-origin/print composition only; no new browser/UI qualification."}
    (ROOT / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=True, indent=2) + "\n")
    print(json.dumps({"root": str(ROOT), "checks": len(CHECKS), "cli_children": len(COMMANDS), "failure": failure}))
if failure:
    raise SystemExit(1)
