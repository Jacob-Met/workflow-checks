"""Deterministic utility-bill checks. No model calls, no network.

Every flag carries a reason code, a plain-language detail and an evidence pointer
(file:row). Anything the rules cannot judge goes to the exception queue instead of
being guessed. Nothing is paid: the payment queue is a list for a human to approve.
"""
from __future__ import annotations

import csv
import json
import statistics
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from pathlib import Path

DEFAULT_RULES = {
    "spike_ratio": 1.5,            # usage/day vs same month last year
    "rate_ratio": 1.2,             # $/unit vs account's trailing-12 median
    "rate_min_amount": 100.0,      # ignore rate check on tiny bills (fixed charges dominate)
    "vacant_standby_per_day": {"water": 0.05, "electric": 5.0},  # kgal/day, kWh/day
    "payment_tolerance": 1.00,     # dollars
    "naive_trailing3_ratio": 1.5,  # used only to report what a naive rule would do
}


@dataclass
class Bill:
    row: int
    bill_id: str
    account_no: str
    invoice: str
    ps: date
    pe: date
    usage: float
    unit: str
    amount: float
    late_fee: float
    prior_balance: float
    due: date
    received: date

    @property
    def days(self) -> int:
        return (self.pe - self.ps).days + 1

    @property
    def per_day(self) -> float:
        return self.usage / self.days if self.days else 0.0

    @property
    def month(self) -> date:
        """Service month containing the most days in this bill's period.

        Utility cycles often cross calendar boundaries. Assigning every bill to
        its end month makes a Jan 1-Feb 1 bill look like a February bill and can
        create a false January missing-bill alert.
        """
        end_month = date(self.pe.year, self.pe.month, 1)
        month = date(self.ps.year, self.ps.month, 1)
        candidates = []
        while month <= end_month:
            next_month = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
            days = (min(self.pe + timedelta(days=1), next_month) - max(self.ps, month)).days
            candidates.append((days, month == end_month, month))
            month = next_month
        return max(candidates)[2]


@dataclass
class Flag:
    key: str
    account_no: str
    property: str
    utility: str
    code: str
    detail: str
    evidence: list = field(default_factory=list)


def _d(s: str) -> date:
    value = s.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unsupported date {s!r}; use YYYY-MM-DD or MM/DD/YYYY")


def _number(s: str, *, blank: float | None = None) -> float:
    value = s.strip()
    if not value:
        if blank is not None:
            return blank
        raise ValueError("number is blank")
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1]
    value = value.replace("$", "").replace(",", "").strip()
    result = float(value)
    return -abs(result) if negative else result


def _rows(path: Path, required: list[str]):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        missing = [name for name in required if name not in headers]
        if missing:
            raise ValueError(f"{path.name}: missing required column(s): {', '.join(missing)}")
        for raw in reader:
            row_number = reader.line_num
            if None in raw:
                raise ValueError(f"{path.name}:{row_number}: too many CSV columns; quote values containing commas")
            row = {key: (value or "").strip() for key, value in raw.items()}
            if not any(row.values()):
                continue
            yield row_number, row


def _unit_key(unit: str) -> str:
    return "".join(c for c in unit.casefold() if c.isalnum())


def load(data: Path):
    data = Path(data)
    account_fields = ["account_no", "property", "utility", "vendor", "scope", "unit", "cycle"]
    accounts = {}
    for i, r in _rows(data / "accounts.csv", account_fields):
        if not r["account_no"]:
            raise ValueError(f"accounts.csv:{i}: account_no is blank")
        r["utility"] = r["utility"].casefold()
        r["scope"] = r["scope"].casefold()
        r["cycle"] = r["cycle"].casefold()
        r["_row"] = i
        accounts[r["account_no"]] = r
    bills = []
    bill_fields = ["bill_id", "account_no", "vendor_invoice_no", "period_start", "period_end", "usage",
                   "usage_unit", "amount", "late_fee", "prior_balance", "due_date", "received_date"]
    for i, r in _rows(data / "bills.csv", bill_fields):
        try:
            bill = Bill(i, r["bill_id"], r["account_no"], r["vendor_invoice_no"], _d(r["period_start"]),
                        _d(r["period_end"]), _number(r["usage"]), r["usage_unit"], _number(r["amount"]),
                        _number(r["late_fee"], blank=0), _number(r["prior_balance"], blank=0),
                        _d(r["due_date"]), _d(r["received_date"]))
        except ValueError as exc:
            raise ValueError(f"bills.csv:{i}: {exc}") from exc
        if not bill.bill_id or not bill.account_no:
            raise ValueError(f"bills.csv:{i}: bill_id and account_no are required")
        if bill.pe < bill.ps:
            raise ValueError(f"bills.csv:{i}: period_end is before period_start")
        bills.append(bill)
    occ = []
    for i, r in _rows(data / "occupancy.csv", ["property", "unit", "status", "from", "to"]):
        try:
            start = _d(r["from"]) if r["from"] else date.min
            end = _d(r["to"]) if r["to"] else date.max
        except ValueError as exc:
            raise ValueError(f"occupancy.csv:{i}: {exc}") from exc
        if end < start:
            raise ValueError(f"occupancy.csv:{i}: to is before from")
        occ.append((r["property"], r["unit"], r["status"].casefold(), start, end, i))
    pays = []
    for i, r in _rows(data / "payments.csv",
                      ["payment_id", "account_no", "vendor_invoice_no", "amount", "paid_date"]):
        try:
            pays.append((r["account_no"], r["vendor_invoice_no"], _number(r["amount"]),
                         _d(r["paid_date"]), i))
        except ValueError as exc:
            raise ValueError(f"payments.csv:{i}: {exc}") from exc
    return accounts, bills, occ, pays


def _prev_month(m: date) -> date:
    return date(m.year - (m.month == 1), (m.month - 2) % 12 + 1, 1)


def check(accounts, bills, occ, pays, as_of: date, eval_from: date, rules=None):
    rules = {**DEFAULT_RULES, **(rules or {})}
    flags, exceptions, naive_hits = [], [], []
    by_acct: dict[str, list[Bill]] = {}
    for b in sorted(bills, key=lambda x: (x.account_no, x.ps, x.received)):
        by_acct.setdefault(b.account_no, []).append(b)
    last_full = date(as_of.year, as_of.month, 1) - timedelta(days=1)
    dup_ids = set()
    duplicate_hold_ids = set()

    def flag(b_or_key, acct, code, detail, ev):
        a = accounts[acct]
        key = b_or_key.bill_id if isinstance(b_or_key, Bill) else b_or_key
        flags.append(Flag(key, acct, a["property"], a["utility"], code, detail, ev))

    def add_exception(b: Bill, reason: str, detail: str):
        exceptions.append({"key": b.bill_id, "account_no": b.account_no, "reason": reason,
                           "detail": detail, "evidence": [f"bills.csv:{b.row}"]})

    for acct, bl in by_acct.items():
        a = accounts.get(acct)
        if a is None:
            for b in bl:
                exceptions.append({"key": b.bill_id, "account_no": acct, "reason": "UNKNOWN_ACCOUNT",
                                   "evidence": [f"bills.csv:{b.row}"]})
            continue
        util, scope = a["utility"], a["scope"]
        seen_invoice = {}
        seen_period = {}
        overlap_anchor = None
        for b in bl:
            in_eval = b.month >= eval_from
            # duplicates: same invoice number, or same period + amount
            period_key = (b.ps, b.pe, round(b.amount, 2))
            first_by_invoice = seen_invoice.get(b.invoice) if b.invoice else None
            first_by_period = seen_period.get(period_key)
            first = first_by_invoice or first_by_period
            if first is not None:
                dup_ids.add(b.bill_id)
                duplicate_hold_ids.update((first.bill_id, b.bill_id))
                if in_eval:
                    flag(b, acct, "DUPLICATE_BILL",
                         f"same {'invoice number' if first_by_invoice else 'period and amount'} as {first.bill_id}"
                         f" ({first.invoice}); hold, do not pay twice",
                         [f"bills.csv:{b.row}", f"bills.csv:{first.row}"])
                continue
            if b.invoice:
                seen_invoice[b.invoice] = b
            seen_period[period_key] = b
            if in_eval and overlap_anchor is not None and b.ps <= overlap_anchor.pe:
                flag(b, acct, "PERIOD_OVERLAP",
                     f"service period {b.ps}..{b.pe} overlaps prior bill {overlap_anchor.bill_id}"
                     f" ({overlap_anchor.ps}..{overlap_anchor.pe});"
                     f" {(min(overlap_anchor.pe, b.pe) - b.ps).days + 1} days may be billed twice",
                     [f"bills.csv:{b.row}", f"bills.csv:{overlap_anchor.row}"])
            if overlap_anchor is None or b.pe > overlap_anchor.pe:
                overlap_anchor = b
            if not in_eval:
                continue
            if not b.invoice:
                add_exception(b, "MISSING_INVOICE",
                              "vendor invoice number is blank; payment matching is unsafe")
            owed = round(b.amount + b.late_fee + b.prior_balance, 2)
            if b.amount < 0 or owed <= 0:
                add_exception(b, "CREDIT_OR_NEGATIVE_BILL",
                              f"bill amount ${b.amount:,.2f}, net amount due ${owed:,.2f};"
                              " review as a credit or zero balance")
            if b.usage < 0:
                add_exception(b, "NEGATIVE_USAGE",
                              f"usage is {b.usage:,.2f} {b.unit}; review meter adjustment or correction")
            elif b.usage == 0:
                add_exception(b, "ZERO_USAGE",
                              "zero usage cannot support usage-rate comparisons; review fixed/minimum charges")
            if b.late_fee != 0 or b.prior_balance != 0:
                flag(b, acct, "LATE_FEE_OR_PAST_DUE",
                     f"late fee ${b.late_fee:,.2f}, prior balance ${b.prior_balance:,.2f} on the bill",
                     [f"bills.csv:{b.row}"])
            if scope == "unit":
                lim = rules["vacant_standby_per_day"].get(util)
                vac = [o for o in occ if o[0] == a["property"] and o[1] == a["unit"] and o[2] == "vacant"
                       and o[3] <= b.pe and o[4] >= b.ps]
                full_vac = [o for o in vac if o[3] <= b.ps and o[4] >= b.pe]
                if full_vac:
                    if lim is None:
                        add_exception(b, "NO_STANDBY_THRESHOLD",
                                      f"no vacant-unit standby ceiling is configured for utility {util}")
                    elif b.per_day > lim:
                        flag(b, acct, "VACANT_UNIT_USAGE",
                             f"unit {a['unit']} vacant; {b.per_day:.3f} {b.unit}/day vs standby ceiling {lim}"
                             f" (possible leak or running equipment)",
                             [f"bills.csv:{b.row}", f"occupancy.csv:{full_vac[0][5]}"])
                elif vac and not full_vac:
                    add_exception(b, "PARTIAL_VACANCY",
                                  "vacancy covers only part of the service period; usage cannot be attributed safely")
                elif not vac:
                    add_exception(b, "UNIT_BILL_NOT_VACANT",
                                  "house-meter bill for a unit not marked vacant")
                continue
            # same month last year baseline
            ly_all = [x for x in bl if x.month == date(b.month.year - 1, b.month.month, 1)
                      and x.bill_id not in dup_ids]
            ly = [x for x in ly_all if _unit_key(x.unit) == _unit_key(b.unit)]
            if ly_all and not ly:
                add_exception(b, "USAGE_UNIT_CHANGED",
                              f"usage unit changed from {ly_all[0].unit or '(blank)'} to {b.unit or '(blank)'};"
                              " usage and rate were not compared")
            elif not ly:
                add_exception(b, "NO_BASELINE", "no same-month bill last year; usage not judged")
            else:
                base = ly[0].per_day
                ratio = b.per_day / base if base else None
                if (ratio is not None and ratio > rules["spike_ratio"]) or (base == 0 and b.per_day > 0):
                    comparison = f"x{ratio:.2f}" if ratio is not None else "prior-year baseline was zero"
                    flag(b, acct, "USAGE_SPIKE",
                         f"{b.per_day:,.1f} {b.unit}/day vs {base:,.1f} same month last year ({comparison})",
                         [f"bills.csv:{b.row}", f"bills.csv:{ly[0].row}"])
            # naive comparison, reported only
            tr = [x for x in bl if x.bill_id not in dup_ids and _unit_key(x.unit) == _unit_key(b.unit)
                  and _prev_month(b.month) >= x.month >= _prev_month(_prev_month(_prev_month(b.month)))]
            if len(tr) == 3:
                avg = sum(x.per_day for x in tr) / 3
                if avg and b.per_day / avg > rules["naive_trailing3_ratio"]:
                    naive_hits.append(b.bill_id)
            # effective rate vs trailing-12 median
            if b.amount >= rules["rate_min_amount"] and b.usage > 0:
                hist = [x.amount / x.usage for x in bl if x.usage > 0 and x.amount > 0
                        and x.bill_id not in dup_ids
                        and _unit_key(x.unit) == _unit_key(b.unit)
                        and b.month > x.month >= date(b.month.year - 1, b.month.month, 1)]
                if len(hist) >= 6:
                    med = statistics.median(hist)
                    r = (b.amount / b.usage) / med
                    if r > rules["rate_ratio"]:
                        flag(b, acct, "RATE_CHANGE",
                             f"${b.amount / b.usage:.4f}/{b.unit} vs trailing median ${med:.4f} (x{r:.2f});"
                             f" check tariff/rate plan",
                             [f"bills.csv:{b.row}"])
        # missing months (common accounts, monthly cycle, from first bill to last full month)
        if scope == "common" and a.get("cycle", "monthly") == "monthly" and bl:
            have = {x.month for x in bl}
            m = max(bl[0].month, eval_from)
            while m <= date(last_full.year, last_full.month, 1):
                if m not in have:
                    flag(f"{acct}:{m.isoformat()}", acct, "MISSING_BILL",
                         f"no bill for service month {m:%Y-%m}; check vendor portal / mail before a late fee lands",
                         [f"accounts.csv:{a['_row']}"])
                m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)

    # payments
    paid: dict[tuple, list] = {}
    for acct, inv, amt, pdate, row in pays:
        if pdate <= as_of:
            paid.setdefault((acct, inv), []).append((amt, pdate, row))
    queue = []
    flagged = {f.key for f in flags}
    excepted = {e["key"] for e in exceptions}
    for b in bills:
        if b.bill_id in duplicate_hold_ids or b.account_no not in accounts or b.month < eval_from:
            continue
        owed = round(b.amount + b.late_fee + b.prior_balance, 2)
        if not b.invoice or b.amount < 0 or owed <= 0:
            continue
        p = paid.get((b.account_no, b.invoice), [])
        if p:
            total = round(sum(x[0] for x in p), 2)
            if len(p) > 1 or abs(total - owed) > rules["payment_tolerance"]:
                flag(b, b.account_no, "PAYMENT_MISMATCH",
                     f"owed ${owed:,.2f}; {len(p)} payment(s) totalling ${total:,.2f}",
                     [f"bills.csv:{b.row}"] + [f"payments.csv:{x[2]}" for x in p])
        elif not p:
            if b.due < as_of:
                flag(b, b.account_no, "UNPAID_PAST_DUE", f"due {b.due}, no payment on file",
                     [f"bills.csv:{b.row}"])
            elif b.bill_id not in flagged and b.bill_id not in excepted:
                a = accounts.get(b.account_no, {})
                queue.append({"bill_id": b.bill_id, "account_no": b.account_no, "property": a.get("property"),
                              "utility": a.get("utility"), "vendor": a.get("vendor"), "invoice": b.invoice,
                              "amount_due": owed, "due_date": b.due.isoformat(),
                              "status": "QUEUED_FOR_APPROVAL (not paid)",
                              "evidence": f"bills.csv:{b.row}"})
    queue.sort(key=lambda x: x["due_date"])
    return flags, exceptions, queue, naive_hits


def run(data: Path, out: Path, as_of: date | None = None, rules=None,
        eval_from: date | None = None) -> dict:
    data, out = Path(data), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    is_synthetic = (data / "expected.json").exists()
    meta = json.loads((data / "expected.json").read_text(encoding="utf-8")) if is_synthetic else {}
    as_of = as_of or (_d(meta["as_of"]) if meta.get("as_of") else date.today())
    eval_from = eval_from or (_d(meta["eval_from"]) if meta.get("eval_from") else
                              date(as_of.year - (as_of.month <= 6), (as_of.month - 7) % 12 + 1, 1))
    accounts, bills, occ, pays = load(data)
    flags, exceptions, queue, naive = check(accounts, bills, occ, pays, as_of, eval_from, rules)
    with open(out / "flags.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["key", "property", "utility", "account_no", "code", "detail", "evidence"])
        for x in sorted(flags, key=lambda x: (x.property, x.code, x.key)):
            w.writerow([x.key, x.property, x.utility, x.account_no, x.code, x.detail, " ".join(x.evidence)])
    with open(out / "exceptions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["key", "account_no", "reason", "detail", "evidence"])
        for e in exceptions:
            w.writerow([e["key"], e["account_no"], e["reason"], e.get("detail", ""), " ".join(e["evidence"])])
    with open(out / "payment_queue.csv", "w", newline="", encoding="utf-8") as f:
        queue_fields = ["bill_id", "account_no", "property", "utility", "vendor", "invoice",
                        "amount_due", "due_date", "status", "evidence"]
        w = csv.DictWriter(f, fieldnames=queue_fields)
        w.writeheader()
        w.writerows(queue)
    with open(out / "audit.jsonl", "a", encoding="utf-8") as f:
        for x in flags:
            f.write(json.dumps({"as_of": as_of.isoformat(), "decision": "flag", **asdict(x)}) + "\n")
        for e in exceptions:
            f.write(json.dumps({"as_of": as_of.isoformat(), "decision": "exception", **e}) + "\n")
        for q in queue:
            f.write(json.dumps({"as_of": as_of.isoformat(), "decision": "payment_queue", **q}) + "\n")
    counts = {}
    for x in flags:
        counts[x.code] = counts.get(x.code, 0) + 1
    summary = {"as_of": as_of.isoformat(), "eval_from": eval_from.isoformat(),
               "data_mode": "synthetic" if is_synthetic else "client_csv", "accounts": len(accounts),
               "bills": len(bills), "flags": len(flags), "by_code": counts, "exceptions": len(exceptions),
               "payment_queue": len(queue), "payment_queue_total": round(sum(q["amount_due"] for q in queue), 2),
               "naive_trailing3_hits": naive,
               "flags_detail": [asdict(x) for x in flags], "exceptions_detail": exceptions,
               "payment_queue_detail": queue}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    from .report import write_html
    write_html(out / "report.html", summary, queue)
    return summary
