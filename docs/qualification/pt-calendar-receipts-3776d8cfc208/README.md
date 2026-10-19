# Calendar receipt delivery after publication

The repaired command preserves a completed calendar when its separate JSON
receipt cannot be delivered. It writes ASCII-compatible JSON, flushes stdout
before returning success, and returns a handled error with an accurate
created-file diagnostic if the receipt write or flush fails. The direct module
entry points suppress a failed stdout shutdown retry after returned status 2.
Imported `main(argv)` retains the caller's stdout and bytecode policy.

The maintained [usage guide](../../../pt_auth/CALENDAR_RECEIPTS.md) explains
statuses, retained output, Unicode JSON escapes and retry decisions.

## Source and existing ownership

The final reviewed source snapshot is
`1bd30de4cecff7ee7564dccadf53561f3e21c284`, based on main
`5b7ece2ff6fadf1c3a194e9ca292f660787a2cd9` via first source snapshot
`f05e64c9b0719ec969c1657fcdfffbd731319787`.

| Maintained path | Final Git blob |
| --- | --- |
| `pt_auth/ptauth/cli.py` | `b1b7a60de7b470ea59de6313bfcde336f1c5dfe1` |
| `pt_auth/ptauth/__main__.py` | `07cf8abb5a559054d4487c65a3f9f7c992067cf5` |
| `pt_auth/tests/test_calendar_receipt_output.py` | `3264d6566e4ce482b47e05b5161a4a35bc74df56` |
| `pt_auth/CALENDAR_RECEIPTS.md` | `a4a55efba02796069bbd974ab2d9de3060da5428` |

The product changes two existing files and adds one focused test and one guide.
All 1,478 unrelated main leaves and modes are preserved. Original CRLF bytes
outside the two CLI edit spans and the entry import/call remain exact. The date
owner's two `--as-of` declarations and two date conversion lines are unchanged.
The existing README, initializer, calendar renderer and publisher, engine,
services, dependencies, workflows and deployment settings are unchanged.

Issue [114](https://github.com/Jacob-Met/workflow-checks/issues/114) owns this
increment. Main integration remains held by the existing dynamic Pages/Actions
boundary recorded in [issue 106](https://github.com/Jacob-Met/workflow-checks/issues/106).
This is reviewed draft source. An opt-in calendar-only package is a separate
delivery; no merged-main, installed or real-record adoption is claimed here.

## Original actual-process witness

Before editing source, the [frozen original protocol](author/ORIGINAL_PROTOCOL.md)
and [observer](author/observe_original.py) exercised four actual processes on
an independently authored two-row fictional saved report. The canonical
UTF-8 invocation returned 0. Canonical restrictive `ascii:strict` output
returned 1 with `UnicodeEncodeError`. Canonical and direct-module invocations
with real preclosed UTF-8 stdout pipes returned 120 with a shutdown
`BrokenPipeError`.

All four had already created complete calendars. The observer independently
checked CRLF, UTF-8 folding, a single event and its literal date. All eight
watched source/input/observer/protocol byte and native mtime records remained
exact. The observer returned 0 after its expected-behavior observations; that
does not convert the three failed calendar process exits into successes.
The [raw observation](author/original-course/observation.json), process streams,
created calendars and original source bodies remain retained without replay.

## Eight original-first authored methods

The [contract](author/CONTRACT.md) was frozen before candidate implementation.
The exact maintained test body ran once against original source and once
against the candidate. Original execution ran eight methods in 0.965 seconds
and reported five subtest/method failures and two errors. Its closed-pipe
regression cases use restrictive ASCII, so they returned 1 at Unicode encoding
before reaching pipe delivery; those observations differ from the separate
original UTF-8 witness's status 120 and remain separately attributed.

The unchanged eight-method suite passed against the candidate in 0.926 seconds,
with no skips. It covers decoded Unicode receipt values, actual restrictive
streams on both entry points, real preclosed pipes, complete calendar output,
occupied-destination and unmatched-selection refusals, and imported write,
flush and diagnostic failures. Imported controls establish handler return and
caller stream ownership. They do not qualify every interpreter shutdown
channel or a native Windows terminal.

The [raw candidate log](author/regression-candidate.stderr),
[original log](author/regression-original.stderr) and
[author freeze](author/author-control-freeze.json) retain exact outcomes. The
test runner's timings describe these control invocations, not performance.
One subsequent guide-only clarification narrowed the diagnostic-failure claim
to the tested handler/stdout scope. Its [exact amendment](author/guide-clarification.json)
retains the prior guide body; no source, test or functional course changed.

## Independent public CLI receiving

A second worker froze [its protocol](independent/PROTOCOL.md) and executable
receiver before candidate exposure. The final receiver
`bccc907cc1476c35bccd24d4cfb5bcf595f55d82` includes three reviewed preparation
corrections: pin the initializer, close stdin, and remove inherited unbuffered
mode. These preceded its only candidate invocation and did not change expected
receipts or calendar values.

The receiver authored a different fictional two-row report, including a
submitted dated item and an undated approved item. It independently derived
the complete expected receipt, snapshot and event UID, and checked actual
calendar wire bytes. Exactly five real command processes passed **57/57
checks**:

| Actual invocation | Exit | Observed result |
| --- | ---: | --- |
| Canonical module, UTF-8 stdout | 0 | Exact decoded JSON and complete calendar |
| Direct CLI module, ASCII stdout | 0 | ASCII JSON with exact decoded Unicode values and complete calendar |
| Canonical module, preclosed ASCII stdout | 2 | Complete retained calendar, ASCII created-file/receipt diagnostic, no traceback or ignored shutdown exception |
| Direct CLI module, preclosed ASCII stdout | 2 | Same retained-file and handled-error behavior |
| Canonical module, occupied Unicode output path, ASCII stdout | 2 | No success receipt; existing file bytes and native mtime preserved |

All five children completed under their ten-second bounds and were reaped.
All eight watched source/input/receiver/protocol files retained exact bytes and
native mtimes. No calendar temporary files remained. The receiver's outer
invocation returned 0 over 0.587481662 seconds; individual child intervals are
separately recorded in the [raw receipt](independent/received-course/receiving.json).
The [independent manifest](independent/native-manifest.json) maps the exact
retained input, output, stream and receiving files.

Root and the second worker reviewed the complete source, entry, tests and
guide. This receiving scope uses local Python processes, authored saved JSON,
and real filesystem/pipe behavior. It does not run the report engine, open a
calendar application, send an invitation, change a deployed service, validate
clinical rules or establish a native Windows output channel.
