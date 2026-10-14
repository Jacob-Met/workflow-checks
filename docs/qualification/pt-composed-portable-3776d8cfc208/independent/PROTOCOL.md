# Independent PT composed workflow receiving

Frozen before exposure to the composed source. Root owns issue 116 and the
date/calendar composition; this receiver does not resolve that composition.
The component contract is `pt-composition-author/CONTRACT.md`. Its reviewed
inputs are date source `58305dd238db2b660bbfe6e0091f7d8806d9a74d` and calendar
source/evidence `370a0a24c5fef60d8b737e200a84bed03296799a`. The ten existing
Python-module identities are pinned in the receiver; only the resolved CLI
identity is supplied explicitly after source review.

## One bounded public workflow

Run the frozen receiver with Python `-B`, an exact source directory containing
`ptauth/`, the reviewed `--cli-git` pin and a previously nonexistent output
directory. It admits all ten source modules before execution. Five children
run with `-B`, source-root cwd, stdin DEVNULL and process-local UTF-8 strict
stdout policy, with inherited unbuffered mode removed. Each child has a fixed
15-second deadline, then kill and five-second reap. Retain every stream and
partial result; never repeat or extend a failed course automatically.

1. `generate`: six fictional patients, seed 53, explicit `--as-of 2026-10-14`,
   new owned data directory. Require exit 0, the six literal IDs SYN-1001
   through SYN-1006, and an explicit synthetic-data marker. No real input.
2. `run`: that generated data, new report directory, the same explicit date and
   `--clinic-timezone UTC`. Require exit 0, report date/time-zone and six-patient
   count, a nonempty worklist with at least one dated item, and literal
   patient/name/clinic association back to the generated CSV. The generated
   answer key is not an oracle for engine or clinical rules.
3. `calendar`: that existing report to a new Unicode filename. Require exit 0,
   a single complete JSON receipt with independently derived snapshot,
   selection/exclusion counts and output path. Every expected event is bound
   to a dated default-open report row, preserving report order, literal key,
   patient, payer, clinic, date, context, reasons and evidence. Check UID from
   its documented identity fields, UTF-8/CRLF/fold bounds and complete envelope.
4. `run --as-of not-a-date`: point at the existing report. Require exit 2, no
   traceback or success stdout, and the entire report tree's bytes and native
   mtimes unchanged, including audit data. Do not rerun a valid report.
5. `calendar` to another new filename with a real stdout pipe whose read end
   is closed before Popen. Require actual exit 2, complete retained calendar,
   created-file/receipt diagnostic and no ignored shutdown exception. Event
   values must equal the ordinary calendar apart from runtime DTSTAMP.

The generator does not create staff state. Require no `work_state.json` before
or after calendar receiving; treat absent state as the documented default-open
state and do not author artificial state into the actual generated report.
Calendar exclusion checks cover any undated rows actually in this fixed report;
this is not a repeat of the previous independent receipt matrix.

DTSTAMP is a runtime UTC export timestamp: check its syntax and bounded wall
interval for each child. The saved `generated_at` remains literal description
context. Never require the two to equal or differ, or freeze the current clock.

## Independence and custody

The receiver imports only Python standard-library modules. It never imports
the product, renderer or engine as an oracle. Its event checks decode the actual
wire format and compare explicit report/CSV values; no additional business-rule
implementation, clinical correctness or generated answer-key parity is claimed.

Watch all ten source modules plus receiver/protocol bytes and native integer
mtimes across the complete course. Snapshot generated inputs after generation
and require them unchanged afterward. Snapshot the complete report after its
single successful run and require it unchanged through both calendars and the
invalid-date refusal. Keep the ordinary output unchanged through later actions.
Record child PIDs, exits, deadlines, wall bounds and source/output identities in
the final receipt even on a failed assertion. No browser, installed service,
invitation, payer submission, source/ref mutation or deployment change.

The root's unchanged eleven-date/eight-receipt authored suites and the separate
calendar-only extracted package course are different receiving scopes; neither
is repeated here. Main integration remains held by the existing Pages/Actions
boundary. This course qualifies only the exact explicit source composition.
