# PT portable review — composed draft source

This separate portable source kit brings together the reviewed explicit-date
admission and calendar-receipt repairs. It includes the complete small PT runtime,
its local UI, existing fictional samples and two focused source tests. Earlier
date-only and calendar-only downloads remain available for their own pinned
versions; this package does not modify them or an installed application.

## Open the extracted component

Extract the entire ZIP into a new directory. Read the root `SOURCE_MANIFEST.json`
for the exact source identities, then open the extracted `pt_auth` folder. Keep
its `ptauth`, `sample_data` and `tests` subdirectories together. Runtime commands
below run from this `pt_auth` folder with an existing Python 3.10 or later.
The runtime uses Python's standard library. Nothing installs or starts itself.

The six bundled sample files are the unchanged repository samples: seed 21,
as-of 2026-09-28, `SYN-####` identifiers, fictional clinics and placeholder payer
rules. They are not real patient data or payer policy. Do not substitute clinical
records in this proof of concept. The package contains no generated report,
saved staff state, credentials or user data.

## Make a fresh review from the bundled fictional data

Choose a new report directory, then run:

```sh
python -B -m ptauth run --data sample_data --out review-20260928 --as-of 2026-09-28 --clinic-timezone UTC
```

`review-20260928` must be a new name for this walkthrough. The existing report
writer is not a universal create-only publisher; using a previously populated
report directory may replace report files. This kit does not change that
behavior. The source samples remain input files.

Named clinic zones use Python's `zoneinfo` and the machine's IANA time-zone data.
If `UTC` is unavailable on that Python installation, the command refuses it.
See the maintained `README.md` for the existing optional `tzdata` guidance;
no dependency or time-zone installation is included or automatic here. Omitting
the flag instead chooses the existing system-local behavior, which is a different
date interpretation and is not the fixed UTC example above.

Open the generated `digest.html` locally to inspect the saved review. The output
also contains the existing CSV/JSON/audit files described by `README.md`.
Counts and declarations are outputs of this synthetic model, not clinical
decisions. A package receiving record states which actual command and input
were exercised; copying the sources alone is not an application acceptance.

## Export a new submit-by calendar

From the same folder, point the calendar command to that saved report and a new
output file:

```sh
python -B -m ptauth calendar --report review-20260928 --output submit-by-20260928.ics
```

Use a new filename whose parent exists. The calendar command reads saved report
data; it does not run the report engine. Missing `work_state.json` follows the
existing empty-state behavior. Dated open/submitted work items are eligible;
undated items and staff states approved or n/a remain disclosed exclusions. No
event count is promised for a different report or filter. See
`CALENDAR_RECEIPTS.md` for exact options and receipt semantics, and the calendar
section of `README.md` for numeric input limits.

Status 0 means the new calendar and its newline-terminated JSON receipt were
delivered. The receipt uses JSON Unicode escapes; parse it to recover the actual
path and values. If status 2 reports receipt writing/flushing failure, a complete
calendar can remain. Inspect the diagnostic and destination before retrying;
partial stdout is not a success receipt. A failed stderr channel may be silent.
The reviewed module-entry cleanup does not qualify every interpreter or an
imported caller's stream lifecycle. External calendar import is a separate action.

## Other existing workflows and dates

The complete runtime also contains the existing local web UI. If you explicitly
want it, follow `README.md` and explicitly start it from this folder:

```sh
python -B -m ptauth serve --data sample_data --out review-20260928 --clinic-timezone UTC
```

It binds to the documented local address; opening or extracting this archive starts no server.
This kit's receiving record does not imply a new browser/UI course.

An explicit `--as-of` for `generate` or `run` must be a real calendar date. Blank
or invalid values refuse before reading inputs or writing outputs. Omitting the
option retains the existing default behavior. For example, to generate a separate
new six-patient fictional sample without replacing the bundled data:

```sh
python -B -m ptauth generate --out fictional-data-20261014 --patients 6 --seed 53 --as-of 2026-10-14
```

Choose that new directory name only if it does not already exist. This seed 53,
2026-10-14 example is distinct from the bundled seed 21, 2026-09-28 files. Use its
own new report directory if you later run it. The current `README.md`, `HARDENING.md` and `CSV_HEADERS.md` retain the maintained
input explanations; no source guide has been rewritten for this archive.

## Optional focused source tests

The package includes only the two repair-focused tests, not the complete
repository suite. With the required test tools already present, run from
`pt_auth`:

```sh
python -B -m unittest discover -s tests -p test_calendar_receipt_output.py -v
python -B -m pytest -q tests/test_cli_date_admission.py
```

The calendar tests use the standard library; the date-admission test requires
`pytest`. Tests create their own temporary data. They are optional source checks,
not steps required to open or use the portable runtime. Broader test commands in
the unchanged README refer to the full repository and are not this kit's inventory.

## Provenance and current integration boundary

The immutable source snapshot is reviewed composed commit
[`69f3c8e0577b579ee36256da0a075fccb201af8f`](https://github.com/Jacob-Met/workflow-checks/commit/69f3c8e0577b579ee36256da0a075fccb201af8f)
for [issue 116](https://github.com/Jacob-Met/workflow-checks/issues/116). It brings
the date-admission source from draft PR 107 together with the calendar-receipt
source and delivery history from draft PR 115. The per-file identities are in
`SOURCE_MANIFEST.json`; the composition does not claim that either earlier
portable artifact already contained both repairs.

This is reviewed draft source, not a main-branch merge or installed update.
The existing dynamic Pages/Actions main-integration hold remains. No repository
setting, workflow, deployment or installed helper was changed to make this kit.
Source integration and package receiving are separately recorded.

The archive has 28 members: 25 unchanged maintained source/sample/guide/license
files, this START note, `SOURCE_MANIFEST.json`, and the root `MANIFEST.json`.
The outer manifest records all 27 selected payload sizes and SHA-256 values;
the source manifest additionally binds the 25 maintained files to their exact
source paths and commits. These hashes establish file identity, not correctness
of a saved worklist, external payer rules or real-world use. Read the included
license and the source/receiving links before extending the prototype.
