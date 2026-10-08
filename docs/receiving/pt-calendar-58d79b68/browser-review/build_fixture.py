"""Build an independent synthetic PT calendar receiving fixture with the original engine."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--source", required=True, type=Path, help="exact baseline pt_auth directory")
ap.add_argument("--out", required=True, type=Path, help="new private fixture directory")
args = ap.parse_args()
source = args.source.resolve()
engine_hash = hashlib.sha256((source / "ptauth/engine.py").read_bytes()).hexdigest()
if engine_hash != "bfa7049e9b133d654ce947b135c17ac401bd7b1fcd76350bdb10de5b7a1ad1f7":
    raise RuntimeError("This fixture must be built by the pinned original engine")
sys.path.insert(0, str(source))
from ptauth.report import run

root = args.out.resolve()
root.mkdir()
data, out = root / "data", root / "out"
data.mkdir()
out.mkdir()

def write_csv(name, fields, rows):
    with (data / name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

shared = "Shared Léo <literal>, care;group 😀"
people = [
    ("PT1001", shared, "East"),
    ("PT1002", shared, "West"),
    ("PT1003", "Approved review", "East"),
    ("PT1004", "N/A review", "West"),
    ("PT1005", "Undated open", "East"),
    ("PT1006", "Undated submitted", "West"),
    ("PT1007", "Current note Ω", "East"),
]
write_csv("patients.csv", ["patient_id", "display_name", "clinic", "primary_payer"], [
    dict(patient_id=pid, display_name=name, clinic=clinic, primary_payer="PTEST")
    for pid, name, clinic in people
])
payer_name = "Payer Review, α; Plan " + "💠" * 25 + r"\literal"
checklist = r"Check dates, review; carefully|Verify \ records|Retain Ω evidence"
write_csv("payers.csv", ["payer_id", "payer_name", "requires_auth", "reauth_visits_before",
    "reauth_days_before", "turnaround_days", "annual_visit_limit", "counts_evals", "checklist"], [
    dict(payer_id="PTEST", payer_name=payer_name, requires_auth="Y",
         reauth_visits_before=2, reauth_days_before=14, turnaround_days=2,
         annual_visit_limit=100, counts_evals="Y", checklist=checklist)
])
auth_ends = {"PT1001": "2026-11-02", "PT1002": "2026-11-03", "PT1003": "2026-11-04",
             "PT1004": "2026-11-05", "PT1007": "2026-11-06"}
write_csv("authorizations.csv", ["auth_no", "patient_id", "payer_id", "visits_authorized",
    "start_date", "end_date", "status"], [
    dict(auth_no="AUTH-" + pid, patient_id=pid, payer_id="PTEST", visits_authorized=10,
         start_date="2026-10-01", end_date=end, status="approved")
    for pid, end in auth_ends.items()
])
write_csv("schedule.csv", ["visit_id", "patient_id", "visit_date", "clinic", "therapist",
    "payer_id", "status", "visit_type"], [
    dict(visit_id="VISIT-" + pid, patient_id=pid, visit_date="2026-11-01T01:30:00-07:00",
         clinic=clinic, therapist="SYNTHETIC", payer_id="PTEST", status="scheduled", visit_type="treatment")
    for pid, _, clinic in people
])
(data / "expected.json").write_text(json.dumps({"as_of": "2026-10-31", "synthetic": True}) + "\n",
                                   encoding="utf-8")
run(data, out, date(2026, 10, 31), run_by="independent_calendar_browser_fixture",
    clinic_timezone="America/Los_Angeles")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
expected_dates = {"PT1001": "2026-10-31", "PT1002": "2026-11-01", "PT1003": "2026-11-02",
                  "PT1004": "2026-11-03", "PT1005": None, "PT1006": None, "PT1007": "2026-11-04"}
if len(summary["worklist"]) != 7:
    raise AssertionError("Independent fixture did not produce exactly seven work items")
for row in summary["worklist"]:
    if row["submit_by"] != expected_dates[row["patient_id"]]:
        raise AssertionError("Original engine differed from the independently chosen date control")
states = {}
staff_states = {"PT1002": "submitted", "PT1003": "approved", "PT1004": "n/a", "PT1006": "submitted"}
for row in summary["worklist"]:
    if row["patient_id"] in staff_states:
        states[row["key"]] = {
            "state": staff_states[row["patient_id"]],
            "note": "Synthetic reviewed, waiting; Ω\\notes\nSecond line",
            "at": "2026-10-01T12:00:00+00:00",
        }
(out / "work_state.json").write_text(json.dumps(states, indent=2, ensure_ascii=False) + "\n",
                                    encoding="utf-8")
expected = []
for row in summary["worklist"]:
    staff_state = states.get(row["key"], {}).get("state", "open")
    expected.append({
        "key": row["key"], "patient_id": row["patient_id"], "patient_name": row["patient_name"],
        "payer_id": row["payer_id"], "payer_name": row["payer_name"], "auth_no": row["auth_no"],
        "clinic": row["clinic"], "auth_end": row["auth_end"], "submit_by": row["submit_by"],
        "staff_state": staff_state, "detail": row["detail"], "reasons": row["reasons"],
        "evidence": row["evidence"], "checklist": row["checklist"],
        "eligible": row["submit_by"] is not None and staff_state in ("open", "submitted"),
    })
if sum(row["eligible"] for row in expected) != 3:
    raise AssertionError("Fixture eligible subset differs from its declared three keys")
description = {
    "schema": "pt_calendar.independent_fixture.v1",
    "synthetic_only": True, "baseline_commit": "9e931fa9f42033bf2368f7149684fb5631345715",
    "baseline_engine_sha256": engine_hash, "as_of": summary["as_of"],
    "clinic_timezone": summary["clinic_timezone"], "rows": expected,
    "expected_all_state_counts": {"visible": 7, "eligible": 3, "undated": 2, "completed": 2},
    "expected_default_counts": {"visible": 5, "eligible": 3, "undated": 2, "completed": 0},
    "method": "Independent authored CSVs; exact original engine generates the saved report. Expected dates and staff subsets are explicit. No candidate formatter or author tests are imported.",
}
(root / "fixture-description.json").write_text(json.dumps(description, indent=2, ensure_ascii=False) + "\n",
                                             encoding="utf-8")
manifest = {"files": []}
for f in sorted(root.rglob("*")):
    if f.is_file():
        b = f.read_bytes()
        manifest["files"].append({"path": str(f.relative_to(root)), "bytes": len(b),
                                  "sha256": hashlib.sha256(b).hexdigest()})
(root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"fixture": str(root), "work_items": len(expected),
    "eligible_keys": [r["key"] for r in expected if r["eligible"]],
    "files": len(manifest["files"]), "expected": description["expected_all_state_counts"]}))
