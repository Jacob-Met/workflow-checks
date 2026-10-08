"""Create a real native worksheet and witness the absent HTML-view command."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

VIEW_TRIPWIRES = """import runpy, socket, subprocess, sys
import uwatch.engine as engine
import uwatch.review as review
import uwatch.synth as synth
def forbidden(*args, **kwargs):
    raise AssertionError('review-report attempted an engine, reconciliation, generator or external effect')
engine.run = engine.check = engine.load = forbidden
review.reconcile = forbidden
synth.generate = forbidden
socket.socket = forbidden
subprocess.Popen = forbidden
sys.argv = ['uwatch', *sys.argv[1:]]
runpy.run_module('uwatch', run_name='__main__')
"""

def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    package = args.package_root.resolve()
    evidence = args.evidence_root.resolve()
    if (evidence / "baseline-native.json").exists():
        raise SystemExit("refusing to replace a prior native baseline receipt")
    commands = []
    with tempfile.TemporaryDirectory(prefix="native-worksheet-baseline-", dir=evidence.parent) as td:
        fixture = Path(td)
        data, report = fixture / "data", fixture / "report"
        first, current = fixture / "review-1.csv", fixture / "review Zoë #%.csv"

        def cli(*argv, tripwires=False):
            command = [sys.executable, "-B"]
            command += ["-c", VIEW_TRIPWIRES] if tripwires else ["-m", "uwatch"]
            command += [str(x) for x in argv]
            proc = subprocess.run(command, cwd=package, capture_output=True, text=True, timeout=20)
            commands.append({"argv": [str(x) for x in argv], "tripwires": tripwires,
                             "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})
            return proc

        for argv in [
            ("generate", "--out", data, "--seed", "11", "--as-of", "2026-09-28"),
            ("run", "--data", data, "--out", report),
            ("review", "--data", data, "--report", report / "summary.json", "--out", first),
        ]:
            proc = cli(*argv)
            if proc.returncode:
                raise AssertionError(commands[-1])

        with first.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            headers, rows = reader.fieldnames, list(reader)
        previous = next(row for row in rows if row["finding_key"] == "B50087" and row["row_state"] == "current")
        previous["review_status"] = "reviewed"
        previous["reviewer"] = "Zoë 李 <AP>"
        previous["note"] = 'Vendor says "credit next month".\nRetain the hold; <script>must remain text</script>.'
        with first.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=headers, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

        bills = data / "bills.csv"
        with bills.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            bill_headers, bill_rows = reader.fieldnames, list(reader)
        bill = next(row for row in bill_rows if row["bill_id"] == "B50087")
        bill["late_fee"] = str(float(bill["late_fee"]) + 1)
        with bills.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=bill_headers, lineterminator="\n")
            writer.writeheader()
            writer.writerows(bill_rows)

        for argv in [
            ("run", "--data", data, "--out", report),
            ("review", "--data", data, "--report", report / "summary.json", "--previous", first, "--out", current),
        ]:
            proc = cli(*argv)
            if proc.returncode:
                raise AssertionError(commands[-1])
        with current.open(newline="", encoding="utf-8") as stream:
            result_rows = list(csv.DictReader(stream))
        findings = [row for row in result_rows if row["row_state"] != "manifest"]
        current_rows = [row for row in findings if row["row_state"] == "current"]
        history = [row for row in findings if row["row_state"] == "changed"]
        if len(current_rows) != 14 or len(history) != 1:
            raise AssertionError({"current": len(current_rows), "history": len(history)})
        old = history[0]
        new = next(row for row in current_rows if row["finding_id"] == old["finding_id"])
        if old["reviewer"] != previous["reviewer"] or old["note"] != previous["note"] or old["review_status"] != "reviewed":
            raise AssertionError("native historical annotation was not retained")
        if new["review_status"] != "open" or new["reviewer"] or new["note"]:
            raise AssertionError("native current evidence did not reopen")

        before = snapshot(fixture)
        output = fixture / "saved review.html"
        proc = cli("review-report", "--worksheet", current, "--out", output, tripwires=True)
        if proc.returncode != 2 or "invalid choice: 'review-report'" not in proc.stderr or proc.stdout or output.exists():
            raise AssertionError(commands[-1])
        if snapshot(fixture) != before:
            raise AssertionError("missing capability changed native files")

        raw = current.read_bytes()
        saved = evidence / "native-review-with-history.csv"
        with saved.open("xb") as stream:
            stream.write(raw)
        receipt = {
            "result": "MISSING_CAPABILITY_CONFIRMED",
            "method": "Actual current native package through six real Python CLI children: generate, run, review, edited-source run, reconcile and refused review-report. Last child traps engine/reconcile/generator/network/subprocess effects after native imports.",
            "python": sys.version,
            "package_root": str(package),
            "commands": commands,
            "actual_cli_children": len(commands),
            "native_counts": {"current": len(current_rows), "changed": len(history)},
            "historical_annotation": {key: old[key] for key in ("reviewer", "note", "review_status", "finding_id", "row_id")},
            "current_same_finding": {key: new[key] for key in ("reviewer", "note", "review_status", "finding_id", "row_id")},
            "all_existing_fixture_bytes_preserved_by_view": True,
            "fixture_before_sha256": before,
            "worksheet": {"artifact": saved.name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)},
            "limits": "Synthetic seed only. No real export, payment, service, provider, browser or production action. Temporary native data/report fixtures are removed after retaining their hashes and the exact worksheet.",
        }
        target = evidence / "baseline-native.json"
        with target.open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(json.dumps({"result": receipt["result"], "actual_cli_children": len(commands),
                          "native_counts": receipt["native_counts"], "worksheet": receipt["worksheet"],
                          "receipt": str(target)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
