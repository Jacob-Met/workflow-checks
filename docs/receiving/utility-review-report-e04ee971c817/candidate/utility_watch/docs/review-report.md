# Read and print saved Utility Watch reviews

`uwatch review-report` turns a saved review worksheet into one self-contained HTML file.
Open it in a browser to read or print the recorded findings, reviewer names, notes and evidence
without navigating the worksheet's protected CSV columns.

From the `utility_watch` directory:

```powershell
python -m uwatch review-report --worksheet "review-2.csv" --out "saved-review.html"
```

The input is the `uwatch-review-v1` worksheet created by the existing `uwatch review` command.
An edited worksheet can be viewed directly after it has been saved as UTF-8 CSV. The viewer
uses the same native worksheet validator as `uwatch review --previous`; it checks the manifest,
protected fields, statuses and required annotations before creating output. It accepts the
native UTF-8 BOM and row/column ordering rules.

## What the page shows

- **Current findings** show each saved status, reviewer and note, with counts for Open,
  In progress and Reviewed.
- **Prior findings** retain changed and absent rows separately. An earlier reviewed note
  does not appear as the current finding's annotation.
- Each finding includes its account, bill or expected-period key, code, description,
  property, utility, recorded report dates, source-row pointers and native identity fields.
- The header identifies the worksheet by filename and SHA256 of the exact bytes read.
  The page carries the native synthetic/client data label and remains readable without
  JavaScript, a server, a network connection or external assets.

Use the browser's Print action to print or save a PDF. The print styles retain the notes
and identifiers. Long notes and quoted line breaks remain readable; text from the worksheet
is escaped as text, including names or notes that resemble HTML.

## Saved review and current source

This page is a snapshot of the saved worksheet. Its dates are the recorded report dates,
not a new check time. The viewer does not load a source export, rerun the checker, reconcile
old notes, change a worksheet, write audit records or alter payment eligibility.

A Reviewed status records a person's follow-up. A changed row records earlier evidence;
an absent row was not present in the later report or evaluation window. Neither establishes
that a bill was resolved or paid. Reviewer names and notes are user-entered. The native
worksheet checksums detect editing mistakes; they are not signatures or authentication.

After the underlying export changes, use the existing commands to produce and reconcile
a new worksheet, then view that file:

```powershell
python -m uwatch run --data sample_data --out out
python -m uwatch review --data sample_data --report out/summary.json --previous review-2.csv --out review-3.csv
python -m uwatch review-report --worksheet review-3.csv --out review-3.html
```

Keep a source export with its report when you need to revisit the underlying historical
values. The HTML includes recorded row pointers and evidence identities, not those source
files. Finish saving the worksheet before exporting a view; the SHA256 identifies the
snapshot read by that command and does not promise that a later edit has been included.

## Output lifecycle

`--out` must be a new path in an existing directory. Existing regular files, directories,
symbolic links and the input worksheet cannot be replaced. Choose a new name when exporting
an updated view. The command does not create missing parent directories.

A successful command exits with status 0 and reports the current/prior counts, worksheet
SHA256 and output path. Invalid input or an output error exits with status 2 and does not
publish an incomplete HTML file. Publication follows the native review writer's approach:
write and close a temporary file in the output directory, then create the destination with
an exclusive hard link. A competing creator keeps its destination; unsupported hard links
cause an error. Cleanup failure may leave a uniquely named temporary file, but does not
remove an existing destination or turn a completed publication into a failure.

## Focused verification

The new consumer tests use Python's standard library and also run under the existing pytest
collection:

```powershell
python -m unittest discover -s tests -p test_review_report.py -v
```

They cover current/history attribution, multiline and HTML-like notes, native validation,
an empty worksheet, the actual CLI with producer/external-call tripwires, existing destinations
and controlled publication failures. The checker, original HTML report and reconciliation
rules remain unchanged.
