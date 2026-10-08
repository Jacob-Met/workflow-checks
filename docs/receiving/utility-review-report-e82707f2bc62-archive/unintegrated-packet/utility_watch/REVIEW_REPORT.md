# Read saved review notes as an offline report

After creating or reconciling a Utility Watch review worksheet, make a readable
copy for follow-up:

```sh
python -m uwatch review-report --worksheet review-2.csv --out review.html
```

Open `review.html` in an ordinary browser. It is one self-contained file with
no external assets, account access or network requests. The command needs only
the complete saved worksheet; the original source export and checker report are
not read again.

## Read the saved record

The report shows every finding's account, bill or expected-period key, code,
description, source row pointers, reviewer, note, review status and evidence
identity. Multiline notes and characters such as `<`, `&` and quotes remain
literal text. The top counts describe the complete worksheet.

Current and historical records remain distinct:

| Record set | Meaning in this report |
|---|---|
| Current | The finding was current in this worksheet's saved report. It may already have a saved review, or be open after evidence changed. |
| Changed | Earlier evidence has a newer finding in the reconciled worksheet. Its old annotation is retained as history. |
| Absent | The earlier finding was not present in the later report or review window. Its saved annotation remains history; absence does not establish resolution or payment. |

A `reviewed` annotation records human follow-up. It does not clear an engine
flag, approve an invoice, or change payment eligibility. This viewer cannot
authenticate who supplied a reviewer name and does not establish that the
original source exports are still current. Use the existing
`run` → `review --previous ...` workflow to refresh the worksheet against a
new export.

## Focus a handoff

With JavaScript enabled, the initial view shows current findings. Choose
current, historical or all saved records; narrow by review status or reviewer;
and search account, property, code, source pointer or saved note. Filters act
together. The visible-record count and filter description update while the
complete worksheet totals stay fixed. **Reset filters** restores the current
findings view.

**Print shown records** uses the browser's normal print dialog for the selected
view. The printed page retains the filter description, record identities,
saved notes and source rows. It excludes the editing controls. Printing and
filtering do not change the worksheet or save a new review.

When JavaScript is disabled, all current and historical records are readable
on the page. Use the browser's Find and Print commands. No report editor or
CSV import is required just to read the notes.

## Input and publication

The command accepts exactly the existing complete `uwatch-review-v1`
worksheet, including its final manifest row. It calls the same full worksheet
validator used by reconciliation. Missing or duplicate rows, altered protected
fields, malformed annotations, invalid evidence pointers and manifest
mismatches are errors. Reordered rows or columns and a UTF-8 BOM retain the
existing validator's behavior.

Successful output is a complete new HTML file; the command exits 0 and prints
current/historical counts and the output path. Existing files, the input
worksheet, symbolic-link destinations and aliases are never replaced.
Malformed input or publication failure exits 2. A complete temporary file is
linked to the new destination, so a competing writer cannot be overwritten.
No temporary document is presented as a completed report.

Keep the worksheet as the editable source. The report is a snapshot and does
not update when that worksheet changes. Its optional fingerprint identifies
the exact worksheet bytes used; it is a checksum, not a signature.

All qualification fixtures are fictional. The underlying program remains a
proof of concept; this view adds no deployment, patient-data, payment or
external-service capability.

## Browser receiving

The focused browser gate runs on the actual pull-request checkout and requires
an installed Chrome/Chromium plus Node's built-in WebSocket API (Node 22.4+).
It does not download a browser or substitute a simulated DOM:

```sh
node utility_watch/tests/review_report_browser.cjs /absolute/path/to/new-evidence-directory
```

`UWATCH_CHROME` can name an existing Chrome executable and `UWATCH_PYTHON` an
existing Python interpreter. Otherwise the test uses the installed commands.
The output directory must be empty. The test creates fictional inputs through
the real native CLI, opens the resulting HTML in a fresh browser profile, and
checks keyboard focus, combined filters, a narrow viewport, literal notes, the
JavaScript-disabled view, print media, and actual browser PDF generation.
Source, worksheet and report hashes are checked before and after receiving.
Raw errors, source identities, screenshots and the PDF are retained with the
receipt. A missing browser fails the gate; it is not a skipped test.

The dedicated workflow uses `ubuntu-24.04`. Its installed-software basis was
checked against the [pinned runner image description](https://github.com/actions/runner-images/blob/e7c7cb8f4227797c6404a4e98c2ad463c2f70f91/images/ubuntu/Ubuntu2404-Readme.md),
and the [Node WebSocket contract](https://github.com/nodejs/node/blob/v22.4.0/doc/api/globals.md#websocket).
Each run records its actual browser, Node, runner image, checkout and tree; those
runtime observations control acceptance.
