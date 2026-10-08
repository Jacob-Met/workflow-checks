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

## Review the HTML report

Open `report.html` directly in a browser. The three summary cards jump to flags, unresolved
exceptions, and the payment-approval queue. Flags are grouped by property; select a property
heading (or focus it and press Enter or Space) to open or close its records. All start open.

Each record includes its account, bill or expected period, and source CSV rows. Payment records
also show the vendor, invoice, amount, due date and unchanged not-paid status, in the engine's
due-date order. Source rows count the CSV header as row 1. Use the companion CSV and audit
files when following up; closing a property only changes the view and does not save review
progress or approve anything. The report works offline with JavaScript disabled.

## Save a review worksheet

Use a CSV worksheet to assign follow-up and retain notes across reports. The HTML report
remains a view of the checker result; the worksheet is a separate, local record of human review.
It includes every flag and unresolved exception, with its account, finding code, description
and source CSV row pointers. It does not contain payment-approval controls.

```powershell
python -m uwatch run --data sample_data --out out
python -m uwatch review --data sample_data --report out/summary.json --out review-1.csv
```

Open `review-1.csv` in a CSV editor, or import all columns as text in a spreadsheet. Edit only
these first three columns on finding rows, then save as UTF-8 CSV:

| Column | Meaning |
|---|---|
| `review_status` | `open`, `in_progress`, or `reviewed`; new findings start `open` |
| `reviewer` | Person responsible for the review |
| `note` | Follow-up, supporting context, or review conclusion; quoted commas and line breaks are supported |

`in_progress` and `reviewed` require both a reviewer and a nonblank note. A `reviewed` row
records human work; it does not clear an engine flag, approve an invoice, or change payment
eligibility. You may reopen a row by setting its status to `open`. Keep every finding row,
protected column, and the final `manifest` row; row and column order may change. The manifest
lets the command detect accidentally deleted or duplicated rows and altered finding fields.
Checksums detect worksheet editing mistakes; they are not signatures or reviewer authentication.

After the next source export, regenerate its report and reconcile into a **new** worksheet:

```powershell
python -m uwatch run --data sample_data --out out
python -m uwatch review --data sample_data --report out/summary.json --previous review-1.csv --out review-2.csv
```

To check and save edited notes against the same export, use the second command without a new
`run`. Keep the previous file until you have inspected the new one. A successful command exits
with status 0 and reports current/historical row counts. An input or reconciliation error exits
with status 2 and leaves the requested output unpublished. An existing output, source file,
report file, prior worksheet, or symbolic-link destination is never replaced.

### Edit notes in the local review desk

Run `python -m uwatch review-desk --worksheet review-1.csv`, then open the printed
loopback URL on the same computer. Select a current finding and edit its status, reviewer
and note. **Download edited worksheet** keeps every finding and its protected evidence
in a new CSV, including rows outside the current filter and unchanged history. The selected
file is read-only; edits stay in the page until you download a copy.

Use the downloaded file as `--previous` in the existing review command when reconciling
a new export. Opening the desk does not recheck bills or reconcile a newer report.
See [Review desk](docs/review-desk.md) for the complete workflow and native checks.

### What carries forward

| `row_state` | How to use it |
|---|---|
| `current` | A finding in this report. Its annotation carries forward only while the finding and its source evidence match the previous current row. |
| `changed` | A previous finding whose evidence changed. Its original reviewer and note remain here; the current finding starts `open`. |
| `absent` | A previous finding not present in this report/window. This does not establish that it was resolved or paid. Its original review remains inspectable. |
| `manifest` | Worksheet integrity record. Keep it unchanged; it is not a finding. |

A finding identity includes its kind, account, bill or expected-period key, and code. Two
accounts sharing a bill ID do not share a review. A version binds the displayed finding to the
account's actual account, bill, and payment rows, plus the property's matching unit occupancy
rows where relevant. That includes historical bills used in rate calculations and payment IDs
that do not appear in report text. A source change can require a new review even when rounded
report text stays the same. Unchanged findings can keep their review across report dates.

Edits to another account's values leave an unchanged account's review intact. Source row
numbers are evidence: inserting or reordering rows can shift those pointers and conservatively
require renewed review. Historical rows never supply a current annotation, including when old
evidence disappears and later returns. History is retained in each successive worksheet.
Keep each source export with its report if you need to revisit the underlying historical rows;
the worksheet retains the finding text, row pointers and evidence identity, not every source value.

Before exporting, the command checks `summary.json` against the unchanged native checker on
a fixed snapshot of the supplied CSVs and the report's dates. Use reports made with the current
default rules. It rejects stale or altered report findings/queues, ambiguous duplicate account
or finding identities, malformed CSV/JSON, and invalid prior worksheets. Keep the source export
stable during review; an input change observed during reconciliation also refuses publication.
The command only reads source/report/previous files and publishes a complete new worksheet.
The checker, original report, audit log, and payment queue keep their existing semantics.

## Enter review notes from the terminal

Use the same saved worksheet without editing its protected columns:

```powershell
python -m uwatch worksheet list --worksheet review-1.csv
python -m uwatch worksheet annotate --worksheet review-1.csv --row-id ROW_ID_FROM_LIST --status in_progress --reviewer "Alex" --note "Asked the vendor to check this invoice." --out review-2.csv
```

Select an exact current row ID from the list and explicitly supply status, reviewer
and note. The command validates the whole worksheet, changes only those three
cells on the selected row, and publishes a new file. All other annotations,
history, protected values and original files are preserved. Listing supports
exact account/status filters, historical rows and JSON output.

These are annotations on the saved report, not a fresh check of source data.
Continue with the existing `review --previous review-2.csv` command when
reconciling against a new export. See [terminal worksheet controls](docs/worksheet-cli.md)
for complete examples, intentional clearing, literal notes and failure behavior.

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

Each `accounts.csv` account number must appear once. Surrounding whitespace
is trimmed before comparison; letter case remains significant. Repeated account
numbers are refused even when their property/vendor fields match. The error
identifies the repeated CSV row and its first declaration so you can correct
the export. This refusal preserves existing report and audit files.

Bill identifiers are scoped to `account_no`. Reusing a `bill_id` in another account
does not transfer a flag, exception, duplicate hold or historical-baseline exclusion
to that account. Within one account, repeated invoices or duplicate periods/amounts
still hold both copies for review.

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
