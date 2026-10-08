"""Build the static fixture and independent browser-rule oracle from uwatch."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "utility_watch"))
from uwatch.engine import DEFAULT_RULES, check, load  # noqa: E402

SOURCE_COMMIT = "26d6bb87ee3269930db4ab5885cde2b74e93bf7e"
FOCUSED_FLAGS = {"USAGE_SPIKE", "RATE_CHANGE"}
FOCUSED_EXCEPTIONS = {"NO_BASELINE", "USAGE_UNIT_CHANGED", "ZERO_USAGE", "NEGATIVE_USAGE", "CREDIT_OR_NEGATIVE_BILL"}


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def generate():
    data = ROOT / "utility_watch" / "sample_data"
    accounts, bills, occupancy, payments = load(data)
    meta = json.loads((data / "expected.json").read_text())
    review_date = date.fromisoformat(meta["as_of"])
    eval_from = date.fromisoformat(meta["eval_from"])
    target = next(b for b in bills if b.bill_id == "B50032")
    history = [b for b in bills if b.account_no == target.account_no]
    paths = ["utility_watch/uwatch/engine.py"] + ["utility_watch/sample_data/" + name for name in ["accounts.csv", "bills.csv", "occupancy.csv", "payments.csv", "expected.json"]]
    blobs = {}
    for path in paths:
        raw = (ROOT / path).read_bytes()
        blobs[path] = {"gitBlob": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(), "sha256": hashlib.sha256(raw).hexdigest()}
    fixture = {
        "schema": "utility-watch.whatif-fixture.v1", "version": 1, "synthetic": True,
        "notice": "Invented sample account. Usage and rate checks only; no bill approval, payment or real-world accuracy claim.",
        "source": {"repository": "Jacob-Met/workflow-checks", "commit": SOURCE_COMMIT, "files": blobs},
        "account": accounts[target.account_no], "selectedBill": target.bill_id,
        "asOf": review_date.isoformat(), "evalFrom": eval_from.isoformat(), "rules": DEFAULT_RULES,
        "bills": [{key: value.isoformat() if isinstance(value, date) else value for key, value in asdict(b).items()} for b in history],
    }
    original = {"usage": target.usage, "amount": target.amount, "ps": target.ps.isoformat(), "pe": target.pe.isoformat()}
    prior = next(b for b in history if b.month == date(target.month.year - 1, target.month.month, 1))
    threshold = prior.per_day * target.days * DEFAULT_RULES["spike_ratio"]
    cases = [("as-received", original)]
    def add(name, **changes):
        cases.append((name, {**original, **changes}))
    for label, delta in [("below", -0.01), ("at", 0), ("above", 0.01)]:
        add("usage-threshold-" + label, usage=threshold + delta)
    historical_rates = [b.amount / b.usage for b in history if b.usage > 0 and b.amount > 0 and b.unit == target.unit and target.month > b.month >= date(target.month.year - 1, target.month.month, 1)]
    rate_boundary_usage = 1000 / (median(historical_rates) * DEFAULT_RULES["rate_ratio"])
    for label, delta in [("above-rate", -0.0001), ("at-rate", 0), ("below-rate", 0.0001)]:
        add("rate-threshold-" + label, usage=rate_boundary_usage + delta, amount=1000)
    for usage in [0, -1, 0.01, 100, 1480.65, 5000, 1000000]:
        for amount in [0, -1, 99.99, 100, 1320, 1320.01, 3058.42]:
            add(f"usage-{usage}-amount-{amount}", usage=usage, amount=amount)
    for ps, pe in [("2026-04-01", "2026-04-01"), ("2026-04-01", "2026-04-30"), ("2026-04-16", "2026-05-15"), ("2026-03-31", "2026-04-30"), ("2026-04-30", "2026-05-01"), ("2026-02-01", "2026-03-01"), ("2024-02-01", "2024-02-29"), ("2026-08-01", "2026-08-31"), ("2027-04-01", "2027-04-30"), ("2026-01-01", "2026-04-15")]:
        for usage in [0, 1480.65, 3000]:
            add(f"period-{ps}-{pe}-usage-{usage}", ps=ps, pe=pe, usage=usage)
    for other in history:
        if other.bill_id != target.bill_id and other.month >= eval_from:
            add("duplicate-period-" + other.bill_id, ps=other.ps.isoformat(), pe=other.pe.isoformat(), amount=other.amount)
    records = []
    for name, inputs in cases:
        altered = replace(target, ps=date.fromisoformat(inputs["ps"]), pe=date.fromisoformat(inputs["pe"]), usage=inputs["usage"], amount=inputs["amount"])
        changed = [altered if b.bill_id == target.bill_id else b for b in bills]
        flags, exceptions, _, _ = check(accounts, changed, occupancy, payments, review_date, eval_from)
        relevant_flags = [f for f in flags if f.key == target.bill_id]
        records.append({"name": name, "input": inputs, "expected": {
            "flags": [{"code": f.code, "evidence": f.evidence} for f in relevant_flags if f.code in FOCUSED_FLAGS],
            "exceptions": [{"reason": e["reason"], "evidence": e["evidence"]} for e in exceptions if e["key"] == target.bill_id and e["reason"] in FOCUSED_EXCEPTIONS],
            "duplicate": any(f.code == "DUPLICATE_BILL" for f in relevant_flags),
            "inEvaluation": altered.month >= eval_from,
            "days": altered.days, "serviceMonth": altered.month.isoformat(), "perDay": altered.per_day,
        }})
    oracle = {"schema": "utility-watch.whatif-oracle.v1", "source": fixture["source"], "cases": records}
    return fixture, oracle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Refuse stale fixture/oracle files without rewriting them")
    args = parser.parse_args()
    fixture, oracle = generate()
    for name, value in [("fixture.json", fixture), ("tests/parity.json", oracle)]:
        path = HERE / name
        raw = encoded(value)
        if args.check:
            if not path.exists() or path.read_bytes() != raw:
                raise SystemExit("Generated source is stale: " + str(path))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    print(json.dumps({"fixture": fixture["selectedBill"], "accountBills": len(fixture["bills"]), "actualPythonOracleCases": len(oracle["cases"]), "mode": "checked" if args.check else "generated", "engineBlob": fixture["source"]["files"]["utility_watch/uwatch/engine.py"]["gitBlob"]}))


if __name__ == "__main__":
    main()
