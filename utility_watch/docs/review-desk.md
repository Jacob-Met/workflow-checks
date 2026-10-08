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

The desk does not read source exports or rerun the checker. Its current label
means current in the selected saved worksheet.

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
127.0.0.1. It uses an in-memory session token and exact snapshot/row identities
for downloads. There are no arbitrary-path, upload, payment or source-edit
routes. Another local program running as the same user is outside this
isolation boundary.

Worksheets are limited to 8 MiB and annotation requests to 4 MiB. The existing
native CSV parser's cell and schema limits still apply. Checksums detect editing
mistakes; a modified worksheet can be resealed by someone with the source and
is not a signed evidence record.

## Native checks

From utility_watch:

    python -m pytest -q tests/test_review_desk.py
    node tests/review_desk_browser.mjs

The optional browser consumer requires Node 22+ and an already installed
Chromium. Set BROWSER_BIN and, for a snap-packaged browser,
REVIEW_DESK_PROFILE_ROOT to an owned directory Chromium can read and write.
The browser check uses a fictional native worksheet, an exclusive profile and
actual CSV downloads. Its output directory is printed and retained for review.
It never opens an installed browser profile or a real source export.
