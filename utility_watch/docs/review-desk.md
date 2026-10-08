# Utility Watch review desk

The desk edits the current findings in one saved review worksheet. It uses the
existing Python validator and produces the same CSV format as the native review
command. Python 3.10 or later and a browser are sufficient; there is no install,
provider connection or new Python dependency.

## Open a saved worksheet

From the utility_watch directory:

    python -m uwatch review-desk --worksheet review-1.csv

Open the printed http://127.0.0.1 address on that computer. The default chooses an
available port; --port 8767 requests a particular port. Stop the command with
Ctrl+C when finished. The command admits the worksheet before starting its
listener. A malformed or unsupported worksheet exits with status 2.

If you have no worksheet yet, create the ordinary report and worksheet first:

    python -m uwatch run --data sample_data --out out
    python -m uwatch review --data sample_data --report out/summary.json --out review-1.csv

## Record the follow-up

Select a current finding by its account, bill or expected period, and finding
code. The original description, dates and source-row evidence remain visible.
Search can match those fields, the property, utility, reviewer or note; the status
filter uses the in-page review values.

Edit only the review status, reviewer and note. In progress and reviewed require
both a nonblank reviewer and a note. If a selected record leaves the current
filter, its editor remains open so you can finish the same record. Reset this
row's edits restores that row to its selected-file values.

Historical changed and absent findings remain read-only. Changed retains an older
version of a finding; absent only means it was not present in that saved report.
Neither means resolved or paid. Reviewer names and checksums do not authenticate
anyone. A human review never changes a checker flag or payment eligibility.

## Inspect the source records

To connect the matching export and its native report when starting the desk:

    python -m uwatch review-desk --worksheet review-1.csv --data sample_data --report out/summary.json

Supply both optional arguments together. The ordinary worksheet-only command
still works; its source inspection button explains how to connect an export.

Select a current finding and choose **Inspect source records**. The desk calls
the existing native evidence command's producer. It checks the configured
report against a fixed captured export, then verifies the complete finding
identity, evidence version, source pointers and report dates against the saved
worksheet. The selected worksheet must remain unchanged during the request.

The resulting record cards show every CSV column in header order. Values remain
literal text, including whitespace, line breaks, Unicode and formula-like cells.
**Download evidence JSON** requests a download named utility-source-evidence.json
with the exact bytes emitted by the native producer. It includes the finding,
physical record-ending line pointers, source/report hashes and checker identity.
The displayed records and download describe that checked snapshot; use Inspect
again to recheck. Neither action changes your note, status, filters or worksheet.

Moving to another finding clears the prior result/download. A late response
cannot replace records under a new selection. Historical rows cannot be matched
to a newer source using this action. A different source context, report date,
changed worksheet or native validation failure refuses inspection and keeps
in-page notes. Use the existing reconciliation command below when the export has
changed; inspected records do not supply a current review or clear a finding.

Source evidence is limited to 8 MiB as one complete response; it is never
truncated. For a larger response, use the existing [source evidence command](source-evidence.md).
The native writer retains its existing observed-change checks; this interface
does not claim an atomic filesystem snapshot across all source files.

## Keep a new CSV

Download edited worksheet validates all submitted annotations with the native
worksheet validator, then requests a browser download named
utility-review-edited.csv. Choose a new destination and keep the actual CSV
before closing the page. The page reports a download request; it cannot verify
the browser's save destination or completion.

Every original finding, historical row, protected value and integrity manifest
is included. Filtering never limits the download. CSV column order and line
endings may be normalized; cell values remain the selected snapshot plus the
explicit current-row edits. Unicode, quotes, commas and multiline notes are
supported. Import all columns as text if later opening the CSV in a spreadsheet.

The program never writes the selected worksheet. Edits live in the browser and
are not automatically saved on the server or in browser storage. A failed or
refused download retains the fields for correction or retry. If the selected
worksheet changes or becomes unreadable on disk, the desk refuses further
downloads rather than applying edits to a different snapshot. Keep any in-page
notes you need before restarting the command with the intended file.

## Reconcile the next export

Opening the desk does not read source exports or rerun the checker. The optional
Inspect source records action uses the native evidence producer to validate the
configured source/report for one saved finding. Its current label still means
current in the selected saved worksheet; inspection does not reconcile it.

After generating a report from the next export, pass your downloaded worksheet
to the existing native reconciliation command:

    python -m uwatch review --data sample_data --report out/summary.json --previous utility-review-edited.csv --out review-next.csv

That command decides which exact-evidence annotations remain current, which
become changed or absent history, and which current findings start open. Keep
the original worksheets and their source/report exports as needed.

The separately provided read-only worksheet report is a print/review consumer;
this editor does not replace its output or command.

## Local interface boundaries

The desk serves only its own fixed assets and the selected worksheet on
127.0.0.1. Optional inspection reads only the explicitly configured source/report.
It uses an in-memory session token and exact snapshot/row identities for downloads
and source inspection. There are no arbitrary-path, upload, payment or source-edit
routes. Another local program running as the same user is outside this
isolation boundary.

Worksheets are limited to 8 MiB and annotation requests to 4 MiB. The existing
native CSV parser's cell and schema limits still apply. Checksums detect editing
mistakes; a modified worksheet can be resealed by someone with the source and
is not a signed evidence record.

## Native checks

From utility_watch:

    python -m pytest -q tests/test_review_desk.py tests/test_review_evidence.py
    node tests/review_desk_browser.mjs

The optional browser consumer requires Node 22+ and an already installed
Chromium. Set BROWSER_BIN and, for a snap-packaged browser,
REVIEW_DESK_PROFILE_ROOT to an owned directory Chromium can read and write.
The browser check uses a fictional native worksheet, an exclusive profile and
actual CSV and source-evidence JSON downloads, including exact native producer
bytes, literal source fields, selection interleaving and changed-source refusal.
Its output directory is printed and retained for review.
It never opens an installed browser profile or a real source export.
