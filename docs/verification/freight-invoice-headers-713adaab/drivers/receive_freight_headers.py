"""Native Windows receiving of the frozen freight header consistency candidate."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
import traceback

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def hashes(root):
    return {path.relative_to(root).as_posix(): sha(path)
            for path in sorted(root.rglob("*")) if path.is_file()}

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qa-root", required=True)
    args = ap.parse_args()
    root = Path(args.qa_root).resolve()
    expected_parent = (Path(os.environ["LOCALAPPDATA"]) / "Temp").resolve()
    require(sys.platform == "win32" and platform.node().upper() == "DESKTOP-LA7CMTA",
            "wrong receiving host")
    require(sys.version_info[:2] == (3, 11), "wrong receiving Python")
    require(root.parent == expected_parent and root.name.startswith("hamon-freight-headers-713adaab-"),
            "wrong private receiving namespace")
    evidence = root / "evidence"
    evidence.mkdir(exist_ok=True)
    with (evidence / "receiving-started.json").open("x", encoding="utf-8") as f:
        json.dump({"started_utc": utc(), "namespace": str(root)}, f)
    source = root / "source"
    inputs = root / "input"
    manifest = json.loads((root / "source-manifest.json").read_text(encoding="utf-8"))
    source_before, inputs_before = hashes(source), hashes(inputs)
    expected = {row["path"]: row["sha256"] for row in manifest["files"]}
    require(source_before == expected, "source manifest mismatch")
    report = {
        "schema": "hamon.freight-invoice-header-windows-receiving.v1",
        "started_utc": utc(), "namespace": str(root), "host": platform.node(),
        "platform": platform.platform(), "python": sys.version,
        "executable": sys.executable, "runner_optimization": sys.flags.optimize,
        "source_manifest_sha256": sha(root / "source-manifest.json"),
        "source_sha256": sha(source / "freight_packets/freightpkt/ingest.py"),
        "test_sha256": sha(source / "freight_packets/tests/test_invoice_header_consistency.py"),
        "upstream_source_commit": manifest["upstream_source_commit"],
        "source_before": source_before, "input_before": inputs_before, "cases": [],
        "qualification": "in_progress", "live_service_or_data_changed": False,
    }
    output = root / "reports"
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME"):
        environment.pop(key, None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    prior_outputs = None
    variants = [
        ("coherent", None), ("carrier-first-A", "carrier"),
        ("carrier-first-B", "carrier"), ("date-first-01", "invoice_date"),
        ("date-first-10", "invoice_date"), ("total-first-1100", "invoice_total"),
        ("total-first-999", "invoice_total"),
    ]
    try:
        for name, conflict in variants:
            data = inputs / name / "data"
            command = [sys.executable, "-B", "-m", "freightpkt", "run",
                       "--data", str(data), "--out", str(output)]
            started = utc()
            result = subprocess.run(command, cwd=source / "freight_packets",
                                    env=environment, capture_output=True, timeout=45)
            case_dir = evidence / name
            case_dir.mkdir()
            (case_dir / "stdout.txt").write_bytes(result.stdout)
            (case_dir / "stderr.txt").write_bytes(result.stderr)
            record = {"name": name, "started_utc": started, "finished_utc": utc(),
                      "argv": command, "cwd": str(source / "freight_packets"),
                      "returncode": result.returncode,
                      "expected_returncode": 0 if conflict is None else 1,
                      "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                      "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
                      "output_hashes": hashes(output) if output.exists() else {},
                      "inputs_unchanged": hashes(inputs) == inputs_before}
            report["cases"].append(record)
            (case_dir / "process.json").write_text(
                json.dumps(record, indent=2) + "\n", encoding="utf-8")
            require(record["inputs_unchanged"], "fixture inputs changed")
            if conflict is None:
                require(result.returncode == 0, "coherent input failed")
                summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
                settlement = summary["settlements"][0]
                require((settlement["status"], settlement["carrier"],
                         settlement["approved_cents"], settlement["fines_cents"],
                         settlement["net_cents"]) ==
                        ("READY", "Fictional Carrier A", 110000, 10000, 100000),
                        "coherent settlement differs from original fixture")
                require(summary["flags"] == [], "coherent input gained flags")
                prior_outputs = hashes(output)
                require("audit.jsonl" in prior_outputs and "settlement.csv" in prior_outputs,
                        "missing original reports")
                report["coherent_settlement"] = settlement
                report["coherent_fines"] = summary["fines"]
                report["original_output_hashes"] = prior_outputs
            else:
                text = result.stderr.decode("utf-8", errors="strict")
                require(result.returncode == 1, "ambiguous invoice was not refused")
                require("conflicting invoice header" in text and conflict in text,
                        "missing conflicting-field diagnostic")
                require("carrier_invoices.csv:row2" in text and
                        "carrier_invoices.csv:row3" in text, "missing source records")
                require(hashes(output) == prior_outputs, "refusal changed previous reports")
                record["previous_outputs_unchanged"] = True
                (case_dir / "process.json").write_text(
                    json.dumps(record, indent=2) + "\n", encoding="utf-8")
        report["source_after"] = hashes(source)
        report["input_after"] = hashes(inputs)
        require(report["source_after"] == source_before, "candidate source changed")
        require(report["input_after"] == inputs_before, "fixture source changed")
        require(len(report["cases"]) == 7, "incomplete case sequence")
        report["qualification"] = "passed"
        report["source_unchanged"] = True
        report["input_unchanged"] = True
        report["all_six_refusals_preserve_reports"] = True
        code = 0
    except Exception as error:
        report["qualification"] = "failed"
        report["error"] = {"type": type(error).__name__, "message": str(error),
                           "traceback": traceback.format_exc()}
        code = 1
    report["finished_utc"] = utc()
    report["qualification_exit_code"] = code
    (evidence / "receiving-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"qualification": report["qualification"], "case_count": len(report["cases"]),
                      "native_process_exits": [c["returncode"] for c in report["cases"]],
                      "report_sha256": sha(evidence / "receiving-report.json"),
                      "source_sha256": report["source_sha256"],
                      "qualification_exit_code": code}, indent=2))
    return code

if __name__ == "__main__":
    raise SystemExit(main())
