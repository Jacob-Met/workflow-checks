"""Compare the frozen 150 cases with the actual pinned Python and browser rules.

This is the existing independent receiving oracle made repository-relative.
It does not implement payer policy or generate new cases. No third-party
package, network call, source edit, temporary corpus or browser is required.
"""
from __future__ import annotations

import argparse
import dataclasses
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PIN = json.loads((HERE / "pins.json").read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def evaluate(inp):
    # The unchanged thin dataclass/date serializer used by receiving. The
    # imported build_worklist function remains the sole rule implementation.
    def make(cls, row, dates=()):
        d = dict(row)
        for field in dates:
            d[field] = date.fromisoformat(d[field])
        return cls(**d)
    visits = [make(Visit, v, ("visit_date",)) for v in inp["visits"]]
    auths = [make(Auth, a, ("start", "end")) for a in inp["auths"]]
    payers = {k: make(PayerRule, p) for k, p in inp["payers"].items()}
    patients = {k: make(Patient, p) for k, p in inp["patients"].items()}
    items, ledgers, uncovered = build_worklist(visits, auths, payers, patients,
                                              date.fromisoformat(inp["as_of"]))
    output = dict(items=[dict(dataclasses.asdict(i), key=i.key) for i in items],
                  ledgers={k: dict(auth=dataclasses.asdict(l.auth),
                                   used=[dataclasses.asdict(v) for v in l.used],
                                   scheduled=[dataclasses.asdict(v) for v in l.scheduled],
                                   remaining=l.remaining,
                                   remaining_after_scheduled=l.remaining_after_scheduled)
                           for k, l in ledgers.items()},
                  uncovered=[dataclasses.asdict(v) for v in uncovered])
    return json.loads(json.dumps(output, default=lambda x: x.isoformat()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default="node", help="Node.js executable (default: node on PATH)")
    args = parser.parse_args()
    for spec in PIN["python_inputs"]:
        raw = (REPO / spec["path"]).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == spec["sha256"],
                f"Pinned source changed: {spec['path']}. Reconcile and qualify before updating the pin.")
        require(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == spec["git_blob"],
                f"Git blob mismatch: {spec['path']}")
    sys.path.insert(0, str(REPO / "pt_auth"))
    global Auth, Patient, PayerRule, Visit, build_worklist
    from ptauth.data import Auth, Patient, PayerRule, Visit
    from ptauth.engine import build_worklist

    corpus = (HERE / PIN["corpus"]["path"]).read_bytes()
    require(hashlib.sha256(corpus).hexdigest() == PIN["corpus"]["sha256"], "Frozen receiving corpus changed")
    rows = [json.loads(line) for line in corpus.splitlines()]
    require(len(rows) == PIN["corpus"]["cases"], "Receiving case count changed")
    require(len({row["id"] for row in rows}) == len(rows), "Duplicate receiving case ID")
    for row in rows:
        before = json.dumps(row["input"], sort_keys=True)
        native = evaluate(row["input"])
        require(json.dumps(row["input"], sort_keys=True) == before, row["id"] + ": Python input changed")
        require(native == row["expected"], row["id"] + ": current Python result differs from recorded native output")
        row["expected"] = native

    payload = dict(cases=rows, native_cases=len(rows), matched_recorded_expected=len(rows),
                   python_source_commit=PIN["python_source_commit"], corpus_sha256=PIN["corpus"]["sha256"])
    result = subprocess.run([args.node, str(HERE / "parity.mjs")],
                            input=json.dumps(payload, separators=(",", ":")),
                            text=True, capture_output=True, cwd=REPO)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(f"Parity check failed: {error}", file=sys.stderr)
        raise SystemExit(2)
