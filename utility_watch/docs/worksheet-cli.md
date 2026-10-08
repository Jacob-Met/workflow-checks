# Review worksheet notes from the terminal

The existing `review` command creates a CSV worksheet whose first three columns
hold human review status, reviewer and notes. `worksheet` provides terminal
controls for those same cells. It validates the complete saved worksheet with
the existing native validator and writes a separate worksheet that ordinary
`review --previous` can consume.

## List the saved findings

First generate the native report and worksheet as usual:

```sh
python -m uwatch run --data sample_data --out out
python -m uwatch review --data sample_data --report out/summary.json --out review-1.csv
python -m uwatch worksheet list --worksheet review-1.csv
```

Each finding shows its exact `row_id`, account, bill or expected-period key,
code, recorded evidence and existing annotation. Copy the complete row ID for
the finding you intend to annotate. Bill IDs alone are insufficient: two
accounts can have a bill with the same ID, and one finding can have several
historical evidence versions.

The default list includes current rows from **that saved worksheet**. It does
not check whether its report is the latest export. The report date, evaluation
window and synthetic/client-CSV marker stay visible. To inspect another view:

```sh
python -m uwatch worksheet list --worksheet review-1.csv --account SYN-7002 --status open
python -m uwatch worksheet list --worksheet review-1.csv --include-history
python -m uwatch worksheet list --worksheet review-1.csv --json
```

Account matching is exact. The status filter accepts `open`, `in_progress` or
`reviewed`. `--include-history` adds the native `changed` and `absent` rows;
absence from a report/window does not establish resolution or payment. Filters
apply only after the entire worksheet passes validation. An empty selection is
shown explicitly, with the complete current/historical counts retained.

`--json` writes every selected native row field plus the source worksheet's
SHA-256 and recorded report context. Text output quotes field values, displaying
newlines and terminal control characters as escapes. The saved note itself is
never rewritten for display.

## Enter a deliberate annotation

Replace `ROW_ID_FROM_LIST` with the full current row ID you just inspected:

```sh
python -m uwatch worksheet annotate --worksheet review-1.csv \
  --row-id ROW_ID_FROM_LIST --status in_progress \
  --reviewer "Alex" --note "Asked the vendor to check the duplicate invoice." \
  --out review-2.csv
```

All three annotation fields are required explicitly. `in_progress` and
`reviewed` need both a nonblank reviewer and a nonblank note, as in the existing
worksheet contract. Reviewer names, surrounding whitespace, Unicode, quoted
commas and multiline note contents are preserved. Use your shell's normal
quoting for these values.

To reopen the same finding and deliberately clear the two text fields:

```sh
python -m uwatch worksheet annotate --worksheet review-2.csv \
  --row-id ROW_ID_FROM_LIST --status open --reviewer= --note= \
  --out review-3.csv
```

Only the selected current row's `review_status`, `reviewer` and `note` change.
Every protected cell, the integrity manifest, all other annotations and every
historical row retain their original values. The output uses the existing
publisher's canonical UTF-8 CSV column order and line endings; input byte order,
BOM and CSV quoting need not be reproduced. The input file remains byte-exact.
Short IDs, finding IDs, bill IDs, missing IDs, the manifest and historical row
IDs cannot stand in for a current `row_id`.

An annotation records human work. It does not authenticate the named reviewer,
clear a flag, approve an invoice, issue payment or alter an engine decision.

## Continue through the existing source reconciliation

When a new source export is available, run the checker and reconcile the
annotated file through the original command:

```sh
python -m uwatch run --data sample_data --out out
python -m uwatch review --data sample_data --report out/summary.json \
  --previous review-2.csv --out review-next.csv
```

The original evidence rules decide which annotations remain current. Identical
current evidence can retain its row ID and notes. Changed or absent findings
keep their old annotations in history, and renewed current evidence starts
open. `worksheet annotate` never reconciles, reruns the checker or transfers a
historical note to a new evidence version. Reconcile first when you need to work
against a newer export.

## Errors and preservation

Successful commands exit 0. Invalid worksheets, invalid selections, missing
required notes and read/publication failures return the existing input-error
status 2. `--out` must be a new destination. An existing file or symbolic link
is refused; a competing writer creating that destination during publication
keeps its result. The unchanged native publisher writes and flushes a complete
temporary file before creating the new destination without replacement.

A worksheet byte change observed during annotation refuses publication. This
check is not a lock over other editors, proof of a latest source export or
protection against an adversarial concurrent path swap. Worksheet checksums
detect protected-field/row editing mistakes; they are not signatures. Keep the
original source exports, reports and prior worksheets according to the existing
review workflow.

## Native checks

From `utility_watch`, using only the Python standard library:

```sh
python -B tests/test_worksheet_cli.py
```

The suite executes the actual `uwatch` CLI, generator, checker, worksheet
validator and reconciler on disposable synthetic files. It covers explicit
annotations and clearing, literal notes, full-file validation before filtering,
exact account/row selection, changed-evidence history, unchanged protected cells
and inputs, and publication failures. Three controlled local faults exercise a
source edit during validation, a real raced destination and a flush failure.
There is no browser, real portfolio, external service or payment action.
