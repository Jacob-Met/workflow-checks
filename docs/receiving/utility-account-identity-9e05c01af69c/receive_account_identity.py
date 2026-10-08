"""Independent native receiving for account-scoped Utility Watch bill identity."""
from __future__ import annotations
import calendar
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(sys.argv[1]).resolve()
EVIDENCE = ROOT / "independent-v1"
EVIDENCE.mkdir()
FIELDS = {
    "accounts.csv": ["account_no", "property", "utility", "vendor", "scope", "unit", "cycle"],
    "bills.csv": ["bill_id", "account_no", "vendor_invoice_no", "period_start", "period_end",
                  "usage", "usage_unit", "amount", "late_fee", "prior_balance", "due_date", "received_date"],
    "occupancy.csv": ["property", "unit", "status", "from", "to"],
    "payments.csv": ["payment_id", "account_no", "vendor_invoice_no", "amount", "paid_date"],
}
RUNS = []
RESULTS = []

def require(condition, message):
    if not condition:
        raise AssertionError(message)

def digest_files(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def account(name):
    return dict(zip(FIELDS["accounts.csv"], [name, "Fixture " + name, "electric", "Fixture vendor",
                                            "common", "", "monthly"]))

def bill(acct, key, year, month, *, usage=100, amount=100, late=0, invoice=None):
    last = calendar.monthrange(year, month)[1]
    start, end = f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last:02d}"
    return dict(zip(FIELDS["bills.csv"], [key, acct, invoice or acct + ":" + key, start, end,
        str(usage), "kWh", str(amount), str(late), "0", "2026-11-15", end]))

def fixture(name, accounts, bills):
    path = EVIDENCE / "inputs" / name
    path.mkdir(parents=True)
    rows = {"accounts.csv": accounts, "bills.csv": bills, "occupancy.csv": [], "payments.csv": []}
    for filename, fields in FIELDS.items():
        with (path / filename).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows[filename])
    dump(path / "expected.json", {"as_of": "2026-10-15", "eval_from": "2026-10-01",
                                 "fixture": "Independent receiving only; synthetic CSV records."})
    return path

def cli(variant, name, args, expected=0):
    cmd = [sys.executable, "-B", "-m", "uwatch", *map(str, args)]
    log = EVIDENCE / "commands" / variant / name
    log.mkdir(parents=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(ROOT / "tmp"))
    result = subprocess.run(cmd, cwd=ROOT / variant / "utility_watch", env=env,
                            capture_output=True, text=True, timeout=30)
    (log / "stdout.log").write_text(result.stdout, encoding="utf-8")
    (log / "stderr.log").write_text(result.stderr, encoding="utf-8")
    receipt = {"variant": variant, "name": name, "command": cmd, "cwd": str(ROOT / variant / "utility_watch"),
               "exit": result.returncode, "expected_exit": expected}
    dump(log / "command.json", receipt)
    RUNS.append(receipt)
    require(result.returncode == expected,
            f"{variant}/{name}: exit {result.returncode}, expected {expected}: {result.stderr}")
    return result

def run(variant, name, data):
    out = EVIDENCE / "reports" / variant / name
    cli(variant, name, ["run", "--data", data, "--out", out,
                       "--as-of", "2026-10-15", "--eval-from", "2026-10-01"])
    return json.loads((out / "summary.json").read_bytes()), out

def projection(report, acct):
    return {name: [row for row in report[name] if row["account_no"] == acct]
            for name in ("flags_detail", "exceptions_detail", "payment_queue_detail")}

def observe(variant, name, fn):
    try:
        detail = fn()
        result = {"variant": variant, "name": name, "passed": True, "detail": detail}
    except Exception as exc:
        result = {"variant": variant, "name": name, "passed": False,
                  "error": type(exc).__name__ + ": " + str(exc), "traceback": traceback.format_exc()}
    RESULTS.append(result)
    dump(EVIDENCE / "checks" / variant / (name + ".json"), result)
    return result

(ROOT / "tmp").mkdir(exist_ok=True)
sources_before = {v: digest_files(ROOT / v) for v in ("baseline", "candidate")}
base_bills = [bill("Target", "B-HISTORY", 2025, 10), bill("Target", "SHARED", 2026, 10)]
solo = fixture("queue-reference", [account("Target")], base_bills)
queue_cases = {}
for kind in ("flag", "exception", "unknown", "duplicate-first", "duplicate-second"):
    extra = [bill("Other", "A-HISTORY", 2025, 10)]
    accounts = [account("Target"), account("Other")]
    if kind == "flag":
        extra.append(bill("Other", "SHARED", 2026, 10, late=5))
    elif kind == "exception":
        extra.append(bill("Other", "SHARED", 2026, 10, usage=0))
    elif kind == "unknown":
        accounts = [account("Target")]
        extra = [bill("Unknown", "SHARED", 2026, 10)]
    else:
        first, second = ("SHARED", "A-DUPLICATE") if kind == "duplicate-first" else ("A-ORIGINAL", "SHARED")
        extra.extend([bill("Other", first, 2026, 10, invoice="Other:DUP"),
                      bill("Other", second, 2026, 10, invoice="Other:DUP")])
    queue_cases[kind] = fixture("queue-" + kind, accounts, base_bills + extra)

history_bills = [bill("Middle", "H-PREVIOUS-YEAR", 2025, 10, usage=31)]
history_bills += [bill("Middle", f"H-{m}", 2026, m, usage=31) for m in range(5, 10)]
history_bills += [bill("Middle", "CURRENT", 2026, 10, usage=93, amount=600)]
history_solo = fixture("history-reference", [account("Middle")], history_bills)
history_cases = {}
for key in ("H-PREVIOUS-YEAR", "H-7"):
    for acct in ("Earlier", "Zlater"):
        extra = [bill(acct, "FIRST", 2024, 1, invoice="REPEAT"),
                 bill(acct, key, 2024, 1, invoice="REPEAT")]
        name = key + "-" + acct
        history_cases[name] = fixture("history-" + name, [account("Middle"), account(acct)], history_bills + extra)

punct_bills = [bill("North:West", "HISTORY", 2025, 10), bill("North:West", "bill", 2026, 10)]
punct_solo = fixture("punctuation-reference", [account("North:West")], punct_bills)
punct_combined = fixture("punctuation-combined", [account("North:West"), account("North")],
                        punct_bills + [bill("North", "HISTORY-OTHER", 2025, 10),
                                       bill("North", "West:bill", 2026, 10, late=5)])

reference_outputs = {}
queue_reports = {}
for variant in ("baseline", "candidate"):
    reference, reference_out = run(variant, "queue-reference", solo)
    require(len(reference["payment_queue_detail"]) == 1, "receiver's clean reference must be queued")
    reference_outputs[variant] = digest_files(reference_out)
    queue_reports[variant] = {}
    for name, data in queue_cases.items():
        def check_queue(name=name, data=data):
            actual, out = run(variant, "queue-" + name, data)
            queue_reports[variant][name] = (actual, out)
            actual_projection = projection(actual, "Target")
            expected_projection = projection(reference, "Target")
            dump(EVIDENCE / "comparisons" / variant / ("queue-" + name + ".json"),
                 {"expected": expected_projection, "actual": actual_projection,
                  "other_findings": [x for x in actual["flags_detail"] + actual["exceptions_detail"]
                                     if x["account_no"] != "Target"]})
            if name.startswith("duplicate-"):
                require(not any(x["account_no"] == "Other" for x in actual["payment_queue_detail"]),
                        "same-account duplicate copies must both remain held")
                require(any(x["account_no"] == "Other" and x["code"] == "DUPLICATE_BILL"
                            for x in actual["flags_detail"]), "native duplicate flag must remain")
            require(actual_projection == expected_projection, "unrelated account changed clean Target result")
            return {"target_queued": 1, "target_projection_equal": True, "source_output": str(out)}
        observe(variant, "queue-" + name, check_queue)

    history_reference, _ = run(variant, "history-reference", history_solo)
    require({x["code"] for x in history_reference["flags_detail"]} == {"USAGE_SPIKE", "RATE_CHANGE"},
            "receiver history reference must exercise both native rules")
    require(history_reference["naive_trailing3_hits"] == ["CURRENT"], "receiver needs native trailing-three hit")
    for name, data in history_cases.items():
        def check_history(name=name, data=data):
            actual, out = run(variant, "history-" + name, data)
            expected = {"account": projection(history_reference, "Middle"),
                        "naive": history_reference["naive_trailing3_hits"]}
            got = {"account": projection(actual, "Middle"), "naive": actual["naive_trailing3_hits"]}
            dump(EVIDENCE / "comparisons" / variant / ("history-" + name + ".json"),
                 {"expected": expected, "actual": got})
            require(got == expected, "other account's historical duplicate changed Middle baseline/rate/naive result")
            return {"projection_equal": True, "source_output": str(out)}
        observe(variant, "history-" + name, check_history)

    def check_punctuation():
        expected, _ = run(variant, "punctuation-reference", punct_solo)
        actual, _ = run(variant, "punctuation-combined", punct_combined)
        require(projection(actual, "North:West") == projection(expected, "North:West"),
                "account/bill separator collision changed a distinct compound identity")
        return {"distinct_pairs": [["North:West", "bill"], ["North", "West:bill"]], "target_queued": 1}
    observe(variant, "compound-identity-control", check_punctuation)

def read_sheet(path):
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)

def annotate(source, target, text):
    fields, rows = read_sheet(source)
    current = [x for x in rows if x["row_state"] == "current"]
    require(len(current) == 1 and current[0]["account_no"] == "Other", "expected one independent flagged account")
    current[0].update(review_status="reviewed", reviewer="Independent receiver", note=text)
    with target.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return current[0]

def migration():
    data = queue_cases["flag"]
    old_report = queue_reports["baseline"]["flag"][1]
    new_report = queue_reports["candidate"]["flag"][1]
    work = EVIDENCE / "migration"
    work.mkdir()
    old_sheet, annotated = work / "old.csv", work / "old-annotated.csv"
    cli("baseline", "review-old", ["review", "--data", data, "--report", old_report / "summary.json", "--out", old_sheet])
    original = annotate(old_sheet, annotated, "Original code and exact original source were reviewed.")
    watched = {"data": digest_files(data), "old_report": digest_files(old_report),
               "new_report": digest_files(new_report), "previous": hashlib.sha256(annotated.read_bytes()).hexdigest()}
    rejected = work / "must-not-exist.csv"
    failure = cli("candidate", "review-stale-report",
        ["review", "--data", data, "--report", old_report / "summary.json", "--previous", annotated, "--out", rejected],
        expected=2)
    require(not rejected.exists(), "stale report must not publish a worksheet")
    require("regenerate" in failure.stderr and "payment_queue" in failure.stderr, "refusal must identify changed native report")
    fresh = work / "fresh.csv"
    cli("candidate", "review-new", ["review", "--data", data, "--report", new_report / "summary.json",
                                  "--previous", annotated, "--out", fresh])
    _, rows = read_sheet(fresh)
    current = [x for x in rows if x["row_state"] == "current"]
    history = [x for x in rows if x["row_state"] == "changed"]
    require(len(current) == 1 and current[0]["review_status"] == "open" and not current[0]["note"],
            "changed engine evidence must receive a fresh open finding")
    require(len(history) == 1 and history[0]["row_id"] == original["row_id"]
            and history[0]["note"] == original["note"] and history[0]["review_status"] == "reviewed",
            "old annotation must remain exact changed history")
    final_annotated = work / "current-annotated.csv"
    selected = annotate(fresh, final_annotated, "Reviewed after the account identity correction.")
    final = work / "retained.csv"
    cli("candidate", "review-same-source", ["review", "--data", data, "--report", new_report / "summary.json",
        "--previous", final_annotated, "--out", final])
    _, again = read_sheet(final)
    now = [x for x in again if x["row_state"] == "current"]
    require(len(now) == 1 and now[0] == selected, "same-source current annotation must be retained exactly")
    after = {"data": digest_files(data), "old_report": digest_files(old_report),
             "new_report": digest_files(new_report), "previous": hashlib.sha256(annotated.read_bytes()).hexdigest()}
    require(watched == after, "review operations changed inputs, reports or prior worksheet")
    return {"stale_report_exit": 2, "stale_output_absent": True, "changed_history_retained": True,
            "current_note_retained": True, "source_report_previous_unchanged": True,
            "current_payment_queue": queue_reports["candidate"]["flag"][0]["payment_queue_detail"]}
observe("candidate", "existing-review-migration-and-retention", migration)
sources_after = {v: digest_files(ROOT / v) for v in ("baseline", "candidate")}
require(sources_before == sources_after, "receiving mutated source files")
require(reference_outputs["baseline"] == reference_outputs["candidate"], "all six clean reference output bytes must agree")
summary = {
    "schema": "utility-account-identity-independent.v1", "python": sys.version,
    "carrier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "baseline_engine_sha256": sources_before["baseline"]["utility_watch/uwatch/engine.py"],
    "candidate_engine_sha256": sources_before["candidate"]["utility_watch/uwatch/engine.py"],
    "sources_unchanged": True, "source_files": sources_before,
    "clean_reference_all_six_outputs_equal": True,
    "results": RESULTS, "native_cli_invocations": RUNS,
    "counts": {v: {"passed": sum(x["passed"] for x in RESULTS if x["variant"] == v),
                   "failed": sum(not x["passed"] for x in RESULTS if x["variant"] == v)}
               for v in ("baseline", "candidate")},
    "limits": ["Independently authored synthetic four-CSV fixtures and marker, using native CLI/report/review.",
               "No customer files, payments, external service or app deployment.",
               "Candidate runtime context uses baseline files plus the exact frozen candidate engine.",
               "Original code failures are retained, not treated as a harness success."]
}
dump(EVIDENCE / "result.json", summary)
print(json.dumps({k: summary[k] for k in ("counts", "candidate_engine_sha256", "sources_unchanged",
                                         "clean_reference_all_six_outputs_equal")}))
sys.exit(0 if summary["counts"]["candidate"]["failed"] == 0 else 1)
