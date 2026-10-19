# PT calendar-only kit — independent extracted receiving

Frozen before package/START_HERE exposure from continuity's inventory and the
reviewed draft source `1bd30de4cecff7ee7564dccadf53561f3e21c284` in
`Jacob-Met/workflow-checks`. This is one ordinary extracted-package invocation,
not a repetition of the original five-process receipt-failure matrix.

## Delivered boundary

Admit the one actual Drive-downloaded ZIP by explicit full byte count, SHA-256
and Git blob supplied after packaging. Open a fresh exclusive local receiving
directory. Require exactly these eight regular file members, no duplicates,
absolute/traversal/backslash names, directories, symlinks or encrypted members:

- `MANIFEST.json`
- `pt_auth/START_HERE.md`
- `pt_auth/SOURCE_MANIFEST.json`
- `pt_auth/CALENDAR_RECEIPTS.md`
- `pt_auth/ptauth/__init__.py`
- `pt_auth/ptauth/__main__.py`
- `pt_auth/ptauth/cli.py`
- `pt_auth/ptauth/worklist_calendar.py`

Bound ZIP to 1 MiB and the sum of uncompressed members to 2 MiB. Read all
members before extraction; retain exact bytes without newline conversion.
Root MANIFEST schema is `hamon.delivery-zip/1`, exact keys schema/files, seven
sorted records with full archive-relative path/bytes/sha256 and no selfhash.
Nested SOURCE_MANIFEST schema is `pt.calendar-receipts.source/1`, exact keys
schema/source_commit/publication_status/files/scope, draft pin above and
publication_status `reviewed-draft-not-main`. Its six file records use paths
relative to pt_auth and contain path/bytes/sha256/git_blob/origin. Five reviewed
source records additionally contain the same source_commit and their full
repository path. START_HERE is a delivery-note record without source lineage.
Both manifests must bind every actual payload byte and size. Independently
require these five source Git identities, not just manifest agreement:

| Relative path below pt_auth | Git blob |
| --- | --- |
| ptauth/__init__.py | a6f4545ac17e2578317ef694f7bb548489f6c71c |
| ptauth/__main__.py | 07cf8abb5a559054d4487c65a3f9f7c992067cf5 |
| ptauth/cli.py | b1b7a60de7b470ea59de6313bfcde336f1c5dfe1 |
| ptauth/worklist_calendar.py | e125f9ed77343fcc3d82e6d6f25a7296b0463aa7 |
| CALENDAR_RECEIPTS.md | a4a55efba02796069bbd974ab2d9de3060da5428 |

Review START_HERE and relative local links after exposure. Instructions must
identify Python 3.10+ and this calendar-only scope, exact draft rather than
main/installed availability, a saved report directory with summary.json and
work_state.json, new output paths, and the distinction between receipt failure
and an already-created calendar. The maintained full source guide may mention
unbundled tests explicitly; those are not package commands or missing runtime
dependencies. No package builder, tests, dependencies, server or installation
is run here.

## Frozen original fictional input and output oracle

Copy the existing independently received two-file report unchanged into the
new receiver-owned saved-report directory. This receiver has read the exact
existing report and literal previous output before package exposure:

| Oracle file | Git blob |
| --- | --- |
| summary.json | a78876985055972f122725366a19ba8c9735ee1d |
| work_state.json | 091cf6cf96601fd5988e2f78dc119844a97343d0 |
| prior-calendar.ics | e6c6dd73e470ab29d8f6baa9c8d032e4f41fae8e |
| prior-receipt.json | ae5ca5f2557d7505045ac71c23ddb85f33b9f9ee |

Expected: selected2, events1, undated1 and completed_state1. The sole event is
submitted fictional SYN-009, all-day 20261020, with unchanged Unicode,
escaping, folded CRLF wire text and literal UID. Approved undated SYN-010 is
excluded with exactly [undated, completed_state]. Receipt snapshot remains
7267b18939113f65ab61aea9970138c78f57ebadf00961d9a1322a1aed55b3a1,
as_of2026-10-14 and clinic_timezone Europe/Paris. Only receipt output path
differs intentionally.

The unchanged renderer uses current UTC time for DTSTAMP, not saved
generated_at. Require one valid UTC DTSTAMP and bound it to the ordinary
invocation's UTC interval, allowing whole-second rounding. Replace only that
single line with a fixed marker in both prior and new bytes for full-wire
equality; every other byte must match. Preserve new unnormalized ICS bytes,
hash and stamp. No clock mock or source modification.

## One actual command and custody

Use a Python3.10+ local Linux runtime and record its executable/version/platform.
From extracted `pt_auth`, run exactly one ordinary child command:

```text
python -B -m ptauth calendar --report ABS_NEW_SAVED_REPORT --output ABS_NEW_calendar-雪.ics
```

Remove inherited PYTHONPATH/PYTHONHOME, disable user-site imports, and retain
UTF-8 stdout/stderr as raw bytes. The extracted cwd contains the admitted
regular package; all four runtime modules are independently pinned above.
No imported helper is used to generate the expected receipt/calendar. Bound
the child to30seconds; on timeout terminate only its owned POSIX process group,
wait/reap with a10second bound and retain all partial files/streams. Never
replay automatically. Require exit0, reaped/no timeout, empty stderr and one
ASCII JSON stdout object+LF. Compare its parsed value against the frozen
prior receipt after replacing only the known output path. Inspect the complete
ICS against the frozen wire oracle and timestamp rule.

Watch raw archive, this receiver, protocol, all four original oracle inputs,
all eight extracted members and both copied report inputs before/after with
bytes/Git/SHA and native nanosecond mtime. Retain exact record arrays. Require
the package tree remains exactly its original eight members, no __pycache__,
and the copied report directory remains only its two unchanged files. The new
calendar is the sole deliberate application output. Save raw streams, command,
PID/return/timeout/reaped facts, calendar identity and a controlled receiving
JSON. This does not validate an external calendar app, real records, receipt
failure modes, other subcommands, Windows behavior or installation.
