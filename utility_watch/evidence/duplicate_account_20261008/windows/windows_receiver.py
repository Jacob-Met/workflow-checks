"""Independent, frozen native Windows receiving for duplicate account identities."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import os
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPORTS = ("summary.json", "flags.csv", "exceptions.csv", "payment_queue.csv", "report.html", "audit.jsonl")
ACCOUNT_FIELDS = ("account_no", "property", "utility", "vendor", "scope", "unit", "cycle")
BILL_FIELDS = ("bill_id", "account_no", "vendor_invoice_no", "period_start", "period_end", "usage", "usage_unit", "amount", "late_fee", "prior_balance", "due_date", "received_date")
AS_OF, EVAL_FROM = "2026-02-10", "2026-01-01"

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def csv_bytes(headers, rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")

def account(number, prop):
    return (number, prop, "water", "Municipal water", "common", "kgal", "monthly")

def dataset(account_rows, account_numbers=("A001",), account_bytes=None):
    bills = []
    for n in account_numbers:
        bills.append(("history-" + n, n, "prior-" + n, "2025-01-01", "2025-01-31", "40", "kgal", "25", "0", "0", "2025-02-15", "2025-02-01"))
        bills.append(("shared-bill", n, "new-" + n, "2026-01-01", "2026-01-31", "40", "kgal", "25", "0", "0", "2026-02-15", "2026-02-01"))
    return {
        "accounts.csv": account_bytes if account_bytes is not None else csv_bytes(ACCOUNT_FIELDS, account_rows),
        "bills.csv": csv_bytes(BILL_FIELDS, bills),
        "occupancy.csv": csv_bytes(("property", "unit", "status", "from", "to"), []),
        "payments.csv": csv_bytes(("payment_id", "account_no", "vendor_invoice_no", "amount", "paid_date"), []),
    }

def cases():
    first = account("A001", "Original property")
    multiline = csv_bytes(ACCOUNT_FIELDS, [account(" \tA001 ", "North\r\nWing")])
    multiline += b"\r\n"
    multiline += csv_bytes(ACCOUNT_FIELDS, [account("A001\t ", "Replacement\r\nWing")]).split(b"\r\n", 1)[1]
    return {
        "valid": {"files": dataset([first]), "expected": "valid"},
        "shared_bill_id": {"files": dataset([first, account("B001", "Other property")], ("A001", "B001")), "expected": "valid", "queue_accounts": ["A001", "B001"]},
        "case_distinct": {"files": dataset([first, account("a001", "Case distinct property")], ("A001", "a001")), "expected": "valid", "queue_accounts": ["A001", "a001"]},
        "duplicate_exact": {"files": dataset([first, first]), "expected": "duplicate", "rows": [2, 3]},
        "duplicate_conflict": {"files": dataset([first, account("A001", "Replacement property")]), "expected": "duplicate", "rows": [2, 3]},
        "duplicate_reverse": {"files": dataset([account("A001", "Replacement property"), first]), "expected": "duplicate", "rows": [2, 3]},
        "duplicate_whitespace": {"files": dataset([account(" \tA001 ", "Original property"), account("A001\t ", "Replacement property")]), "expected": "duplicate", "rows": [2, 3]},
        "duplicate_multiline": {"files": dataset([], account_bytes=multiline), "expected": "duplicate", "rows": [3, 6]},
        "blank_account": {"files": dataset([account(" \t ", "Original property")]), "expected": "blank"},
    }

def source_checkout(lane):
    inputs = json.loads((ROOT / "inputs.json").read_text(encoding="utf-8"))
    source = ROOT / lane / "source"
    pins = {}
    for name, item in inputs["source"].items():
        raw = item["content"].encode("utf-8")
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        if blob != item["git_blob_sha"]:
            raise AssertionError("source blob mismatch: " + name)
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        pins[name] = {"git_blob_sha": blob, "sha256": sha(raw)}
    if lane == "candidate":
        patch = json.loads((ROOT / "candidate.json").read_text(encoding="utf-8"))
        if patch["base"] != inputs["base"]:
            raise AssertionError("candidate wrong base")
        name = "utility_watch/uwatch/engine.py"
        raw = patch["content"].encode("utf-8")
        if sha(raw) != patch["sha256"]:
            raise AssertionError("candidate hash mismatch")
        (source / name).write_bytes(raw)
        pins[name] = {"sha256": sha(raw)}
    return source, pins

def cli(source, work, args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source / "utility_watch")
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run([sys.executable, "-m", "uwatch", *args], cwd=work, env=env, capture_output=True, timeout=30)
    return {"rc": p.returncode, "stdout": p.stdout.decode("utf-8"), "stderr": p.stderr.decode("utf-8"),
            "stdout_sha256": sha(p.stdout), "stderr_sha256": sha(p.stderr)}

def file_hashes(root):
    return {str(p.relative_to(root)): sha(p.read_bytes()) for p in sorted(root.rglob("*")) if p.is_file()} if root.exists() else {}

def main():
    lane = sys.argv[1]
    assert lane in ("baseline", "candidate")
    if (ROOT / lane).exists():
        raise AssertionError("immutable receiving lane already exists: " + lane)
    source, pins = source_checkout(lane)
    evidence = {"base": "125339ec63eeb7c4989c9b240c01202555dce573", "lane": lane,
                "utc": datetime.now(timezone.utc).isoformat(), "system": platform.platform(),
                "python": sys.version, "executable": sys.executable,
                "receiver_sha256": sha(Path(__file__).read_bytes()), "source_pins": pins,
                "cases": {}, "checks": []}
    def check(name, condition):
        evidence["checks"].append({"name": name, "passed": bool(condition)})
    fixture_pins = {}
    for name, case in cases().items():
        work = ROOT / lane / "cases" / name
        data = work / "data"
        data.mkdir(parents=True)
        for filename, raw in case["files"].items():
            (data / filename).write_bytes(raw)
        fixture_pins[name] = file_hashes(data)
        out = work / "out"
        before = {}
        if case["expected"] == "duplicate":
            out.mkdir()
            for filename in REPORTS:
                (out / filename).write_bytes(("existing report sentinel: " + filename + "\r\n").encode("utf-8"))
            (out / "unrelated.txt").write_bytes(b"keep me\r\n")
            before = file_hashes(out)
        observed = cli(source, work, ["run", "--data", "data", "--out", "out", "--as-of", AS_OF, "--eval-from", EVAL_FROM])
        observed.update(input_sha256=fixture_pins[name], report_before=before, report_after=file_hashes(out))
        check(name + ": source bytes unchanged", file_hashes(data) == fixture_pins[name])
        if case["expected"] == "valid":
            check(name + ": CLI success", observed["rc"] == 0)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            observed["queue_properties"] = [q["property"] for q in summary["payment_queue_detail"]]
            observed["queue_accounts"] = [q["account_no"] for q in summary["payment_queue_detail"]]
            check(name + ": exact report closure", set(observed["report_after"]) == set(REPORTS))
            if case.get("queue_accounts"):
                check(name + ": account-scoped shared bill remains payable", sorted(observed["queue_accounts"]) == case["queue_accounts"])
        elif case["expected"] == "duplicate":
            first, later = case["rows"]
            check(name + ": CLI input refusal", observed["rc"] == 2 and observed["stdout"] == "")
            check(name + ": both physical rows", ("accounts.csv:" + str(first)) in observed["stderr"] and ("accounts.csv:" + str(later)) in observed["stderr"])
            check(name + ": duplicate diagnostic", "duplicate" in observed["stderr"].lower() and "account_no" in observed["stderr"])
            check(name + ": no report writes", observed["report_after"] == before)
            check(name + ": metadata absent from diagnostic", all(x not in observed["stderr"] for x in ("Original property", "Replacement property", "North", "Wing")))
            fresh = cli(source, work, ["run", "--data", "data", "--out", "fresh", "--as-of", AS_OF, "--eval-from", EVAL_FROM])
            observed["fresh"] = {**fresh, "report_files": file_hashes(work / "fresh")}
            check(name + ": fresh output has no report files", fresh["rc"] == 2 and not observed["fresh"]["report_files"])
            if observed["rc"] == 0:
                summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
                observed["silently_selected_properties"] = [q["property"] for q in summary["payment_queue_detail"]]
        else:
            check(name + ": blank-account diagnostic unchanged", observed["rc"] == 2 and observed["stderr"] == "uwatch: input error: accounts.csv:2: account_no is blank\r\n")
        evidence["cases"][name] = observed
    review_work = ROOT / lane / "cases" / "duplicate_conflict"
    review_report = ROOT / lane / "cases" / "valid" / "out" / "summary.json"
    review_before = file_hashes(review_work)
    reviewed = cli(source, review_work, ["review", "--data", "data", "--report", str(review_report), "--out", "review.csv"])
    check("review: existing duplicate refusal", reviewed["rc"] == 2 and "duplicate account identity is ambiguous for review" in reviewed["stderr"])
    check("review: no writes", not (review_work / "review.csv").exists() and file_hashes(review_work) == review_before)
    evidence["review"] = reviewed
    evidence["fixture_pins"] = fixture_pins
    if lane == "candidate":
        baseline = json.loads((ROOT / "baseline-receipt.json").read_text(encoding="utf-8"))
        check("receiving script frozen before candidate", evidence["receiver_sha256"] == baseline["receiver_sha256"])
        check("all fixture bytes frozen before candidate", fixture_pins == baseline["fixture_pins"])
        for name in ("valid", "shared_bill_id", "case_distinct"):
            before = baseline["cases"][name]
            after = evidence["cases"][name]
            check(name + ": all six native report bytes identical", before["report_after"] == after["report_after"])
            check(name + ": CLI stdout/stderr bytes identical", before["stdout_sha256"] == after["stdout_sha256"] and before["stderr_sha256"] == after["stderr_sha256"])
        check("review: native duplicate refusal unchanged", baseline["review"]["rc"] == reviewed["rc"] and baseline["review"]["stderr_sha256"] == reviewed["stderr_sha256"])
    failed = [c["name"] for c in evidence["checks"] if not c["passed"]]
    evidence["failed_checks"] = failed
    evidence["check_count"] = len(evidence["checks"])
    receipt = ROOT / (lane + "-receipt.json")
    receipt.write_text(json.dumps(evidence, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps({"lane": lane, "receipt": str(receipt), "receipt_sha256": sha(receipt.read_bytes()),
                      "engine_sha256": pins["utility_watch/uwatch/engine.py"]["sha256"],
                      "receiver_sha256": evidence["receiver_sha256"], "check_count": len(evidence["checks"]),
                      "failed_checks": failed, "cases": {k: {"rc": v["rc"], "stderr": v["stderr"],
                      "selected": v.get("silently_selected_properties")} for k,v in evidence["cases"].items()}}))
    return 1 if lane == "candidate" and failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
