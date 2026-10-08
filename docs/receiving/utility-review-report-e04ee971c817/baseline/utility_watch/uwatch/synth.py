"""Synthetic multifamily utility-bill generator. ALL DATA IS FICTIONAL.

Properties are "(synthetic)", vendors are placeholders ("Metro Power Co (placeholder)"),
account numbers start with SYN-. Seeded anomalies are recorded in expected.json, an
answer key computed from the seeding decisions, NOT from the engine.

Bills follow a seasonal curve so a competent same-month-last-year baseline is needed:
naive month-over-month comparison would flag every summer electric bill (a decoy the
tests check stays unflagged).
"""
from __future__ import annotations

import csv
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

PROPS = ["Cypress Court (synthetic)", "Bayou Flats (synthetic)", "Gaylord Ridge (synthetic)"]
VENDORS = {
    "electric": ("Metro Power Co (placeholder)", "kWh", 0.13, 18),
    "gas": ("Gulf Gas Utility (placeholder)", "therm", 1.10, 21),
    "water": ("City Water Dept (placeholder)", "kgal", 11.5, 20),
    "trash": ("Haul-Rite Waste (placeholder)", "pull", 95.0, 25),
}
# seasonal multipliers by month (1..12); electric peaks in summer, gas in winter
SEASON = {
    "electric": [0.85, 0.8, 0.85, 0.95, 1.1, 1.6, 1.9, 1.9, 1.5, 1.1, 0.9, 0.9],
    "gas": [1.6, 1.5, 1.2, 0.9, 0.7, 0.6, 0.55, 0.55, 0.6, 0.8, 1.1, 1.5],
    "water": [0.9, 0.9, 0.95, 1.0, 1.05, 1.15, 1.2, 1.2, 1.1, 1.0, 0.95, 0.9],
    "trash": [1.0] * 12,
}
DAILY_BASE = {"electric": 900.0, "gas": 45.0, "water": 9.0, "trash": 0.4}  # per common meter
UNIT_DAILY = {"electric": 14.0, "water": 0.12}  # vacant-unit house meters, when occupied-equivalent


def _month_starts(first: date, n: int):
    y, m = first.year, first.month
    for _ in range(n):
        yield date(y, m, 1)
        m += 1
        if m == 13:
            y, m = y + 1, 1


def _month_end(d: date) -> date:
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return nxt - timedelta(days=1)


def generate(out_dir: Path, seed: int = 11, as_of: date = date(2026, 9, 28), months: int = 18) -> dict:
    rng = random.Random(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    last_full = date(as_of.year, as_of.month, 1) - timedelta(days=1)  # end of previous month
    # first bill month = `months` months back from the last full month
    y, m = last_full.year, last_full.month - months + 1
    while m <= 0:
        y, m = y - 1, m + 12
    first = date(y, m, 1)
    eval_from = date(last_full.year, last_full.month, 1)
    for _ in range(5):  # evaluation window = last 6 bill months
        eval_from = date(eval_from.year - (eval_from.month == 1), (eval_from.month - 2) % 12 + 1, 1)

    accounts, bills, occupancy, payments = [], [], [], []
    expected = {"as_of": as_of.isoformat(), "eval_from": eval_from.isoformat(), "flags": [],
                "decoys": [], "insufficient_history": []}
    bid = 50000
    acct_n = 0

    # unit house meters (vacant units the property pays for)
    unit_meters = []
    for p_i, prop in enumerate(PROPS):
        for u in range(3):
            unit = f"{100 + p_i * 100 + u + 1}"
            unit_meters.append((prop, unit))
    # occupancy: each unit has a vacancy stretch somewhere in the window
    vac = {}
    for prop, unit in unit_meters:
        start = first + timedelta(days=rng.randint(60, 360))
        end = start + timedelta(days=rng.choice([45, 60, 90]))
        vac[(prop, unit)] = (start, end)
        occupancy.append([prop, unit, "vacant", start.isoformat(), end.isoformat()])

    def add_bill(acct, util, ps, pe, usage, amount, late_fee=0.0, prior=0.0, inv=None, received=None, paid=None):
        nonlocal bid
        bid += 1
        vendor, unit, rate, due_days = VENDORS[util]
        inv = inv or f"{vendor.split()[0].upper()[:4]}-{bid}"
        received = received or pe + timedelta(days=rng.randint(3, 8))
        due = received + timedelta(days=due_days + 12)
        row = {"bill_id": f"B{bid}", "account_no": acct, "vendor_invoice_no": inv,
               "period_start": ps.isoformat(), "period_end": pe.isoformat(), "usage": round(usage, 2),
               "usage_unit": unit, "amount": round(amount, 2), "late_fee": round(late_fee, 2),
               "prior_balance": round(prior, 2), "due_date": due.isoformat(), "received_date": received.isoformat()}
        bills.append(row)
        pay_day = paid if paid is not None else (due - timedelta(days=rng.randint(1, 6)))
        if pe >= last_full - timedelta(days=1) and paid is None:
            pay_day = None  # latest month: received, not yet paid -> payment approval queue
        if pay_day and pay_day <= as_of:
            payments.append({"payment_id": f"P{bid}", "account_no": acct, "vendor_invoice_no": inv,
                             "amount": round(amount + late_fee + prior, 2), "paid_date": pay_day.isoformat()})
        return row

    # --- common-area accounts
    plan = []  # (acct, util, prop)
    for prop in PROPS:
        for util in ("electric", "gas", "water", "trash"):
            acct_n += 1
            acct = f"SYN-{7000 + acct_n}"
            vendor = VENDORS[util][0]
            accounts.append([acct, prop, util, vendor, "common", "", "monthly"])
            plan.append((acct, util, prop))
    # one account opened recently -> insufficient history (exception, not a flag)
    acct_n += 1
    new_acct = f"SYN-{7000 + acct_n}"
    accounts.append([new_acct, PROPS[2], "electric", VENDORS["electric"][0], "common", "", "monthly"])
    for prop, unit in unit_meters:
        for util in ("electric", "water"):
            acct_n += 1
            acct = f"SYN-{7000 + acct_n}"
            accounts.append([acct, prop, util, VENDORS[util][0], "unit", unit, "monthly"])
            plan.append((acct, util, (prop, unit)))

    # decide seeded anomalies on common accounts (eval window only)
    eval_months = list(_month_starts(eval_from, 6))
    common = [p for p in plan if isinstance(p[2], str)]
    rng.shuffle(common)
    seeds = {}
    # each anomaly class gets its own account; spikes only on metered (non-trash) utilities
    kinds = ["spike", "spike", "rate", "duplicate", "late", "missing", "overlap", "pay_short", "pay_double", "unpaid"]
    pool = list(common)
    for kind in kinds:
        cand = [c for c in pool if not (kind == "spike" and c[1] == "trash")]
        pick = cand[0]
        pool.remove(pick)
        month = eval_months[-2] if kind == "unpaid" else rng.choice(eval_months[1:5])
        seeds[pick[0]] = (kind, month)
    # vacancy with a leak: force one unit's vacancy to overlap the evaluation window
    leak_unit = unit_meters[rng.randrange(len(unit_meters))]
    vs = eval_months[2] + timedelta(days=4)
    vac[leak_unit] = (vs, vs + timedelta(days=75))
    for row in occupancy:
        if (row[0], row[1]) == leak_unit:
            row[3], row[4] = vac[leak_unit][0].isoformat(), vac[leak_unit][1].isoformat()
    expected["leak_unit"] = list(leak_unit)

    for acct, util, owner in plan:
        is_unit = not isinstance(owner, str)
        base = (UNIT_DAILY[util] if is_unit else DAILY_BASE[util] * rng.uniform(0.7, 1.3))
        rate = VENDORS[util][2] * rng.uniform(0.95, 1.05)
        kind, kmonth = seeds.get(acct, (None, None))
        for ms in _month_starts(first, months):
            ps, pe = ms, _month_end(ms)
            ndays = (pe - ps).days + 1
            season = SEASON[util][ms.month - 1]
            noise = rng.uniform(0.95, 1.05)
            if is_unit:
                vs, ve = vac[owner]
                vac_days = max(0, (min(pe, ve) - max(ps, vs)).days + 1)
                if vac_days == 0:
                    continue  # tenant-paid while occupied: no house-meter bill
                daily = UNIT_DAILY[util] * 0.08 * noise  # vacant: near-zero standby
                usage = daily * vac_days
                leak = (util == "water" and owner == leak_unit and ms >= eval_from and vac_days >= 20)
                if leak:
                    usage = UNIT_DAILY[util] * 3.0 * vac_days  # running toilet / leak in a vacant unit
                row = add_bill(acct, util, max(ps, vs), min(pe, ve), usage, usage * rate + 8.0)
                if leak:
                    expected["flags"].append([row["bill_id"], "VACANT_UNIT_USAGE"])
                continue
            usage = base * season * noise * ndays
            amount = usage * rate + 25.0
            if ms == kmonth and kind:
                if kind == "spike":
                    usage *= 1.9
                    amount = usage * rate + 25.0
                    row = add_bill(acct, util, ps, pe, usage, amount)
                    expected["flags"].append([row["bill_id"], "USAGE_SPIKE"])
                    continue
                if kind == "rate":
                    amount = usage * rate * 1.35 + 25.0
                    row = add_bill(acct, util, ps, pe, usage, amount)
                    expected["flags"].append([row["bill_id"], "RATE_CHANGE"])
                    continue
                if kind == "duplicate":
                    row = add_bill(acct, util, ps, pe, usage, amount)
                    dup = add_bill(acct, util, ps, pe, usage, amount, inv=row["vendor_invoice_no"],
                                   received=date.fromisoformat(row["received_date"]) + timedelta(days=6),
                                   paid=False)  # duplicate is caught before payment
                    expected["flags"].append([dup["bill_id"], "DUPLICATE_BILL"])
                    continue
                if kind == "late":
                    row = add_bill(acct, util, ps, pe, usage, amount, late_fee=round(amount * 0.05, 2),
                                   prior=round(amount * 0.9, 2))
                    expected["flags"].append([row["bill_id"], "LATE_FEE_OR_PAST_DUE"])
                    continue
                if kind == "missing":
                    expected["flags"].append([acct + ":" + ps.isoformat(), "MISSING_BILL"])
                    continue
                if kind == "overlap":
                    row = add_bill(acct, util, ps - timedelta(days=9), pe, usage * (ndays + 9) / ndays,
                                   (usage * (ndays + 9) / ndays) * rate + 25.0)
                    expected["flags"].append([row["bill_id"], "PERIOD_OVERLAP"])
                    continue
                if kind == "unpaid":
                    row = add_bill(acct, util, ps, pe, usage, amount, paid=False)
                    expected["flags"].append([row["bill_id"], "UNPAID_PAST_DUE"])
                    continue
                if kind == "pay_short":
                    row = add_bill(acct, util, ps, pe, usage, amount, paid=pe + timedelta(days=12))
                    payments[-1]["amount"] = round(payments[-1]["amount"] - 150.0, 2)
                    expected["flags"].append([row["bill_id"], "PAYMENT_MISMATCH"])
                    continue
                if kind == "pay_double":
                    row = add_bill(acct, util, ps, pe, usage, amount, paid=pe + timedelta(days=12))
                    p = dict(payments[-1])
                    p["payment_id"] += "b"
                    p["paid_date"] = (date.fromisoformat(p["paid_date"]) + timedelta(days=4)).isoformat()
                    payments.append(p)
                    expected["flags"].append([row["bill_id"], "PAYMENT_MISMATCH"])
                    continue
            row = add_bill(acct, util, ps, pe, usage, amount)
            if util == "electric" and ms >= eval_from and ms.month in (6, 7, 8):
                expected["decoys"].append(row["bill_id"])  # seasonal peak: must NOT flag

    # recent account with 2 months of history -> exception queue, no flag
    for ms in list(_month_starts(first, months))[-2:]:
        pe = _month_end(ms)
        row = add_bill(new_acct, "electric", ms, pe, 800 * 30, 800 * 30 * 0.13 + 25)
        if ms >= eval_from:
            expected["insufficient_history"].append(row["bill_id"])

    # one received-but-unpaid bill due soon (payment queue ordering), no flag
    expected["flags"].sort()

    def wcsv(name, header, rows):
        with open(out / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            for r in rows:
                w.writerow([r[h] for h in header] if isinstance(r, dict) else r)

    wcsv("accounts.csv", ["account_no", "property", "utility", "vendor", "scope", "unit", "cycle"], accounts)
    wcsv("bills.csv", list(bills[0].keys()), bills)
    wcsv("occupancy.csv", ["property", "unit", "status", "from", "to"], occupancy)
    wcsv("payments.csv", ["payment_id", "account_no", "vendor_invoice_no", "amount", "paid_date"], payments)
    (out / "expected.json").write_text(json.dumps(expected, indent=1))
    (out / "README_SYNTHETIC.txt").write_text(
        "SYNTHETIC DATA ONLY. Fictional properties, placeholder vendors, invented accounts.\n"
        "expected.json is the answer key written by the generator from its seeding decisions.\n")
    return expected
