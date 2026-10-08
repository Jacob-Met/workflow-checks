"""Reproduce the real offline CLI receiving sequence; writes receipts only to --out."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True, type=Path, help="utility_watch directory")
    parser.add_argument("--out", required=True, type=Path, help="new receipt directory")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    commands = []

    def call(*arguments, expected=0):
        result = subprocess.run([sys.executable, "-B", "-m", "uwatch", *map(str, arguments)],
                                cwd=args.package, capture_output=True, text=True)
        commands.append({"argv": list(map(str, arguments)), "exit": result.returncode,
                         "stdout": result.stdout, "stderr": result.stderr})
        assert result.returncode == expected, commands[-1]

    def rows(path):
        with path.open(encoding="utf-8", newline="") as source:
            return list(csv.DictReader(source))

    def write(path, records):
        with path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)

    def snapshot(*directories):
        return {f"{d.name}/{p.name}": hashlib.sha256(p.read_bytes()).hexdigest()
                for d in directories for p in d.iterdir() if p.is_file()}

    with tempfile.TemporaryDirectory(prefix="uwatch-cli-receiving-") as name:
        working = Path(name)
        data, report = working / "data", working / "report"
        call("generate", "--out", data, "--seed", 11)
        call("run", "--data", data, "--out", report)
        summary = json.loads((report / "summary.json").read_text())
        assert summary["payment_queue"] > 0
        before = snapshot(data, report)
        first, kept = args.out / "review-1.csv", args.out / "review-2.csv"
        call("review", "--data", data, "--report", report / "summary.json", "--out", first)
        records = rows(first)
        target = next(r for r in records if r["code"] == "LATE_FEE_OR_PAST_DUE")
        target.update(review_status="reviewed", reviewer="Zoë 李",
                      note='Statement reviewed.\nVendor says "credit next month"; keep the hold.')
        reviewed = dict(target)
        write(first, records)
        first_bytes = first.read_bytes()
        call("review", "--data", data, "--report", report / "summary.json",
             "--previous", first, "--out", kept)
        retained = next(r for r in rows(kept) if r["row_id"] == reviewed["row_id"])
        assert retained == reviewed
        assert first.read_bytes() == first_bytes
        assert snapshot(data, report) == before
        bills = rows(data / "bills.csv")
        source_bill = next(r for r in bills if r["bill_id"] == reviewed["finding_key"]
                           and r["account_no"] == reviewed["account_no"])
        source_bill["late_fee"] = str(float(source_bill["late_fee"]) + 1)
        write(data / "bills.csv", bills)
        refused = args.out / "must-not-publish.csv"
        stale_before = snapshot(data, report)
        call("review", "--data", data, "--report", report / "summary.json",
             "--previous", kept, "--out", refused, expected=2)
        assert not refused.exists()
        assert snapshot(data, report) == stale_before
        call("run", "--data", data, "--out", report)
        changed = args.out / "review-3.csv"
        regenerated = snapshot(data, report)
        call("review", "--data", data, "--report", report / "summary.json",
             "--previous", kept, "--out", changed)
        reconciled = rows(changed)
        historical = next(r for r in reconciled if r["row_id"] == reviewed["row_id"])
        fresh = next(r for r in reconciled if r["row_state"] == "current"
                     and r["finding_id"] == reviewed["finding_id"])
        assert (historical["row_state"], historical["review_status"], historical["note"]) == (
            "changed", "reviewed", reviewed["note"])
        assert fresh["review_status"] == "open" and fresh["note"] == ""
        assert fresh["evidence_version"] != reviewed["evidence_version"]
        assert snapshot(data, report) == regenerated
        result = {
            "schema": "uwatch-cli-receiving-v1", "result": "PASS", "seed": 11,
            "python": sys.version.split()[0], "commands": commands,
            "native_summary": {k: summary[k] for k in ("data_mode", "flags", "exceptions", "payment_queue", "payment_queue_total")},
            "initial_source_and_report_sha256": before,
            "review_only_file_bytes_unchanged": True,
            "stale_report_exit": 2, "stale_output_absent": True,
            "annotation_before": reviewed, "annotation_unchanged": retained,
            "changed_historical": historical, "changed_current": fresh,
            "source_files": {str(p.relative_to(args.package)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (args.package / "uwatch").glob("*.py")},
            "external_calls": "none; native Python CLI, synthetic input only",
        }
        (args.out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"result": "PASS", "commands": len(commands), "receipt": str(args.out / "result.json")}))


if __name__ == "__main__":
    main()
