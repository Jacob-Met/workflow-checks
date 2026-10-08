# Utility bill exception checker (PoC)

> **The bundled sample data is synthetic.** Fictional properties, placeholder vendors, invented account numbers. The checker can also read a client CSV export as described below. Nothing is paid, disputed or sent. Every flag is for a person to review.

Built for multifamily operators who pay utility bills across a portfolio and staff a person to catch problems by hand. That job typically means verifying charges against prior billing periods, flagging unusual spikes, duplicate charges or billing errors, paying on time to avoid late fees, monitoring consumption trends, and handling service transfers at move-in and move-out.

## What it checks (deterministic rules, no model calls)

| Code | What it catches | Baseline / rule |
|---|---|---|
| `USAGE_SPIKE` | Usage per day well above normal | Same service month **last year** (so summer electric and winter gas are not flagged just for being seasonal); default ratio > 1.5 |
| `RATE_CHANGE` | Effective $/unit jumped | Account's trailing-12-month median; ignored on bills under $100 |
| `DUPLICATE_BILL` | Same invoice number, or same period and amount, received twice | Held; never goes to the payment queue |
| `PERIOD_OVERLAP` | Service period overlaps the previous bill | Days possibly billed twice are stated |
| `MISSING_BILL` | Expected monthly bill never arrived | Checked for every completed service month in the window after an account's first exported bill |
| `LATE_FEE_OR_PAST_DUE` | Late fee or carried balance on the bill | Any non-zero amount |
| `PAYMENT_MISMATCH` | Paid amount differs from the bill, or paid twice | $1 tolerance |
| `UNPAID_PAST_DUE` | No payment on file after the due date | |
| `VACANT_UNIT_USAGE` | A vacant unit's house meter is using real water/power (leak, running equipment) | Joined to an occupancy export; standby ceiling per utility |

Anything the rules cannot judge (a new account with no same-month history, a unit bill for a unit not marked vacant, an unknown account) goes to the **exception queue**, not to a guess. Clean bills that are not yet paid go to a **payment-approval queue**, sorted by due date. Nothing is paid.

Outputs: `flags.csv`, `exceptions.csv`, `payment_queue.csv`, `report.html` (single self-contained file), `summary.json`, and an append-only `audit.jsonl` with a file:row evidence pointer for every decision.

## Run it

```powershell
cd utility_watch
python -m uwatch generate --out sample_data --seed 11   # synthetic portfolio + answer key
python -m uwatch run --data sample_data --out out       # flags, exceptions, payment queue, report
python -m pytest -q
```

Python 3.10+ standard library only; `pytest` for tests.

## Run a client CSV export

No install or programming is needed. Put these four CSV files in one folder, open PowerShell in `utility_watch`, and run:

```powershell
python -m uwatch run --data "C:\Exports\utility-bills" --out "C:\Exports\utility-review" --as-of 2026-09-29 --eval-from 2026-03-01
```

Open `utility-review\report.html` in a browser. Also review `flags.csv`, `exceptions.csv`, and `payment_queue.csv`. The command only reads the input folder and writes reports to the output folder; it cannot issue payments.

Required columns (column order does not matter):

| File | Columns |
|---|---|
| `accounts.csv` | `account_no, property, utility, vendor, scope, unit, cycle` |
| `bills.csv` | `bill_id, account_no, vendor_invoice_no, period_start, period_end, usage, usage_unit, amount, late_fee, prior_balance, due_date, received_date` |
| `occupancy.csv` | `property, unit, status, from, to` |
| `payments.csv` | `payment_id, account_no, vendor_invoice_no, amount, paid_date` |

Use `common` or `unit` for account `scope`, `monthly` for a monthly `cycle`, and `vacant` for vacancy rows. Files may have a UTF-8 BOM and blank rows. Dates may be `YYYY-MM-DD`, `M/D/YYYY`, or `M/D/YY`. Numeric fields may contain commas, a dollar sign, or accounting negatives such as `(25.00)` when the CSV value is properly quoted. `late_fee` and `prior_balance` may be blank; other bill fields are required. Blank occupancy `from`/`to` dates mean open-ended.

All imported bill and payment numbers must be finite. `NaN`, positive or negative infinity,
and values that overflow the numeric parser (such as `1e309`) are input errors. The command
exits with status 2 and identifies the CSV file, row and field so you can correct the export.
Rejected input leaves the previous reports and audit file unchanged; those files still describe
the earlier successful run, so use the new command's exit status before treating them as current.

`--as-of` defaults to today. `--eval-from` defaults to about six months before the review date. Use the first day of a month for `--eval-from`. Service periods crossing month boundaries are assigned to the month containing the most service days (ties use the ending month).

Keep `expected.json` out of a client-data folder: that file marks generated sample data and supplies its fixed test dates.

## Verification

The generator writes `expected.json` from its own seeding decisions, not from the engine. Tests assert:
- the set of (bill, flag code) pairs **equals** the answer key exactly (seeds 11, 3, 99, 2026; also checked by hand on 1, 2, 7, 1234: 12/12 seeded anomalies, 0 extra flags on every seed);
- **seasonal decoys** (summer electric peaks) are not flagged, while a naive "vs trailing 3 months" rule would have flagged 2 to 5 of them per seed;
- accounts without a same-month baseline go to exceptions and are never flagged;
- the payment queue contains only clean, unpaid bills;
- every flag has an evidence pointer and an audit line; reruns are stable; lowering a seeded spike below threshold removes its flag.

## What this is not

- Not a bill-pay or bill-and-collect service (Conservice, Zego and others sell that). This is a check layer that works on the exports an AP team already has.
- Thresholds are defaults, not tuned on any real portfolio. A pilot measures precision on the client's own history and reports it.
- No PDF bill parsing in this PoC; it reads a bills CSV. A pilot starts from whatever export or portal download the client already uses.
