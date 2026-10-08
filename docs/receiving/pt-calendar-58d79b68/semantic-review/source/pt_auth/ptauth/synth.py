"""Synthetic data generator. ALL DATA IS FICTIONAL.

Patient ids are SYN-#### and display names are drawn from a small list of
obviously synthetic "Test" names so a screen recording can never be mistaken
for PHI. Payer names are generic placeholders, not real plans.

Also writes expected.json: an answer key of seeded conditions computed
independently from the engine, used by the tests.
"""
from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

FIRST = ["Alex", "Blair", "Casey", "Devon", "Emery", "Finley", "Gray", "Harper", "Indy", "Jordan",
         "Kai", "Logan", "Morgan", "Noel", "Oakley", "Parker", "Quinn", "Reese", "Sage", "Taylor"]
CLINICS = ["Clinic North (synthetic)", "Clinic West (synthetic)", "Clinic Lake (synthetic)"]
THERAPISTS = ["PT-A", "PT-B", "PT-C", "PT-D", "PTA-E"]

PAYERS = [
    # id, name, requires_auth, visits_before, days_before, turnaround, annual_limit, counts_evals, checklist
    ("PAY-COMM1", "Commercial Plan A (placeholder)", "Y", 3, 10, 5, "", "N",
     "Current plan of care signed by referring provider|Progress note within last 30 days|"
     "Objective measures (ROM, strength, functional score)|Updated goals|Payer portal request form"),
    ("PAY-COMM2", "Commercial Plan B (placeholder)", "Y", 2, 7, 3, 30, "Y",
     "Progress note|Functional outcome score (e.g., LEFS/ODI)|Visit history|Portal submission"),
    ("PAY-MA", "Medicare Advantage Plan (placeholder)", "Y", 4, 14, 7, "", "Y",
     "Plan of care certification|Progress report (every 10th visit)|Medical necessity statement|"
     "Functional limitation reporting|Utilization-management vendor form"),
    ("PAY-WC", "Workers Comp Carrier (placeholder)", "Y", 2, 7, 10, "", "Y",
     "Adjuster approval request|Work status report|Progress note|Physician referral / Rx"),
    ("PAY-SELF", "Self-pay / cash", "N", 0, 0, 0, "", "Y", ""),
]


def generate(out_dir: Path, n_patients: int = 40, seed: int = 21, as_of: date = date(2026, 9, 28)) -> dict:
    rng = random.Random(seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    patients, auths, visits = [], [], []
    expected = {"as_of": as_of.isoformat(), "uncovered_scheduled": [], "unauthorized_done": [],
                "reauth_due": [], "pending_followup": [], "pending_visits": [], "clean": []}
    vid = 1000
    payer_ids = [p[0] for p in PAYERS]
    weights = [30, 20, 25, 15, 10]
    rules = {p[0]: p for p in PAYERS}

    for i in range(n_patients):
        pid = f"SYN-{1001 + i}"
        name = f"Test {rng.choice(FIRST)} {chr(65 + i % 26)}."
        clinic = rng.choice(CLINICS)
        payer = rng.choices(payer_ids, weights)[0]
        patients.append([pid, name, clinic, payer])
        rule = rules[payer]
        n_auth = rng.choice([8, 10, 12, 12, 20])
        start = as_of - timedelta(days=rng.randint(10, 55))
        end = start + timedelta(days=rng.choice([45, 60, 90]))
        auth_no = f"AUTH-{70000 + i * 3}"
        kinds = ["clean", "near_visits", "near_date", "uncovered", "expired_done", "pending", "has_successor"]
        scenario = rng.choices(kinds, [30, 18, 12, 14, 6, 10, 10])[0]
        if i < len(kinds):  # guarantee every scenario appears at least once
            scenario = kinds[i]
            if payer == "PAY-SELF":
                payer = "PAY-MA"
                patients[-1][3] = payer
                rule = rules[payer]
        if payer == "PAY-SELF":
            scenario = "self"

        # visit cadence 2x/week from start
        d = start
        dates = []
        while d <= as_of + timedelta(days=28):
            dates.append(d)
            d += timedelta(days=rng.choice([2, 3, 4]))
        completed = [x for x in dates if x < as_of]
        future = [x for x in dates if x >= as_of]

        if scenario == "clean":
            n_auth = max(n_auth, len(completed) + len(future) + rule[3] + 2)
            end = max(end, dates[-1] + timedelta(days=rule[4] + 5))
        elif scenario == "near_visits":
            n_auth = len(completed) + rng.randint(0, rule[3])
            end = max(end, as_of + timedelta(days=60))
            # keep scheduled visits inside the date window; some will exceed count -> uncovered too
        elif scenario == "near_date":
            n_auth = len(completed) + len(future) + 10
            end = as_of + timedelta(days=rng.randint(1, max(1, rule[4] - 1)))
        elif scenario == "uncovered":
            n_auth = len(completed) + len(future) + 10
            end = as_of + timedelta(days=rng.randint(3, 9))
        elif scenario == "expired_done":
            end = as_of - timedelta(days=6)
            n_auth = 40
        elif scenario in ("pending", "has_successor"):
            end = as_of + timedelta(days=rng.randint(2, 6))
            n_auth = len(completed) + len(future) + 10
        if scenario != "self":
            auths.append([auth_no, pid, payer, n_auth, start.isoformat(), end.isoformat(), "approved"])
        if scenario in ("pending", "has_successor"):
            s2 = end + timedelta(days=1)
            auths.append([f"AUTH-{70000 + i * 3 + 1}", pid, payer, 12, s2.isoformat(),
                          (s2 + timedelta(days=60)).isoformat(),
                          "pending" if scenario == "pending" else "approved"])

        for j, x in enumerate(dates):
            vid += 1
            status = "completed" if x < as_of else "scheduled"
            if status == "completed" and rng.random() < 0.06:
                status = rng.choice(["cancelled", "no_show"])
            vtype = "eval" if j == 0 else ("re-eval" if j % 10 == 0 else "treatment")
            visits.append([f"V{vid}", pid, x.isoformat(), clinic, rng.choice(THERAPISTS), payer, status, vtype])

        # --- answer key, computed from the seeded parameters (not the engine) ---
        if scenario == "self":
            continue
        counted_done = [v for v in visits if v[1] == pid and v[6] == "completed"
                        and not (v[7] == "eval" and rule[7] == "N")]
        counted_future = [v for v in visits if v[1] == pid and v[6] == "scheduled"
                          and not (v[7] == "eval" and rule[7] == "N")]
        cap_left = n_auth - len([v for v in counted_done if date.fromisoformat(v[2]) <= end])
        outside_date = [v[0] for v in counted_future if date.fromisoformat(v[2]) > end]
        inside = [v for v in counted_future if date.fromisoformat(v[2]) <= end]
        over_count = [v[0] for v in inside[max(cap_left, 0):]]
        done_outside = [v[0] for v in counted_done if date.fromisoformat(v[2]) > end]
        if scenario == "pending":
            expected["pending_followup"].append(pid)
            expected.setdefault("pending_visits", []).extend(outside_date)
        elif scenario == "has_successor":
            pass  # successor approved -> future visits covered by it, no re-auth flag
        else:
            expected["uncovered_scheduled"] += outside_date + over_count
            expected["unauthorized_done"] += done_outside
            remaining = n_auth - len(counted_done)
            days_left = (end - as_of).days
            if end >= as_of and (remaining <= rule[3] or (days_left <= rule[4] and counted_future)):
                expected["reauth_due"].append(pid)
            if scenario == "clean":
                expected["clean"].append(pid)

    def w(name, header, rows):
        with (out_dir / name).open("w", newline="", encoding="utf-8") as fh:
            wr = csv.writer(fh)
            wr.writerow(header)
            wr.writerows(rows)

    w("patients.csv", ["patient_id", "display_name", "clinic", "primary_payer"], patients)
    w("authorizations.csv", ["auth_no", "patient_id", "payer_id", "visits_authorized", "start_date",
                             "end_date", "status"], auths)
    w("schedule.csv", ["visit_id", "patient_id", "visit_date", "clinic", "therapist", "payer_id",
                       "status", "visit_type"], visits)
    w("payers.csv", ["payer_id", "payer_name", "requires_auth", "reauth_visits_before",
                     "reauth_days_before", "turnaround_days", "annual_visit_limit", "counts_evals",
                     "checklist"], PAYERS)
    (out_dir / "expected.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    (out_dir / "README_SYNTHETIC.txt").write_text(
        "SYNTHETIC DATA - NOT REAL PATIENTS. Every patient id (SYN-####), name ('Test ...'),\n"
        "clinic, payer and authorization number in this folder is fictional, generated by\n"
        f"ptauth.synth (seed={seed}, as_of={as_of}). Payer rules are placeholders, not real plan policy.\n",
        encoding="utf-8")
    return expected
