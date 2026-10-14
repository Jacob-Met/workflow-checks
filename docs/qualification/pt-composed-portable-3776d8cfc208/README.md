# PT portable build: explicit dates and calendar receipts together

Issue [116](https://github.com/Jacob-Met/workflow-checks/issues/116) combines the
reviewed date-admission repair from draft PR107 and calendar-receipt repair from
draft PR115 in one opt-in source version. The full portable package is a separate
delivery step. Neither existing package nor either owner's branch is replaced.

## Source composition

Published source is [69f3c8e0](https://github.com/Jacob-Met/workflow-checks/commit/69f3c8e0577b579ee36256da0a075fccb201af8f)
on `root/pt-composed-portable-116-3776`, with tree
`3c2a77730ab23915fb5a33ae02b70497812da7c7`. It combines calendar
delivery parent `c95c3eaec22fd5bbafeb210a2ae99a470dc2e84a` and date repair parent
`58305dd238db2b660bbfe6e0091f7d8806d9a74d`, with common ancestor
`d2b583ae9350b30aec1453e93797dc231888417d`.

Only `pt_auth/ptauth/cli.py` had distinct concurrent edits. The resolved blob is
`8d6b43649bc6c142c28f71646485a31f6a6bbf55`: the date parent's exact four changed
lines applied to the calendar parent, retaining CRLF. Independently applying the
calendar parent's two changed regions to the date parent yields the same bytes;
reversing each contribution recovers the exact other parent. No report-engine,
calendar-renderer, input model, UI or business-rule changes were introduced.

Complete recursive trees were admitted by rehashing every directory with the
maintained `verify_tree_union.py` blob
`f6f3585033d393ce9f496336e4626db649f2711f`. Ordinary three-way leaf rules selected
every path except the separately reviewed CLI conflict. The received 1,611-leaf
tree preserves 1,581 calendar-parent leaves, changes only its README and CLI,
and adds the 28 unchanged date-test/evidence paths. The final calendar parent's
36 delivery additions are retained. All 17 runtime/UI/license/guide/test files
used in composition receiving match this tree exactly.

The initial frozen contract used calendar qualification parent `370a0a24`.
The later `c95c3eae` parent adds completed package-delivery records. Re-admitting
that complete parent changed the preserved evidence inventory and introduced no
new runtime conflict. The raw plan and received-tree record retain that step.

## Independent application workflow

One frozen receiver, `2ca8d584144fa7db5f2423a78c51517a507b1e18`, ran five public
CLI children against the composed source. Protocol
`96bd89e2e5bb8346878ecd045648cf10bbd26137` and receiver were frozen before candidate
exposure; full independent source review accepted the exact composition first.

All **68 assertions passed**. The children were fictional generation, report
creation, ordinary calendar export, invalid-date refusal and real closed-stdout
calendar export. Their exits were **0 / 0 / 0 / 2 / 2**, all reaped within their
bounds. Six generated patient IDs mapped through the report. Five worklist rows
yielded three dated calendar events and two explicit undated exclusions.

The receiver derived receipt and event expectations independently from the saved
report and CSV identities. It did not import product helpers or use the generated
`expected.json` as a business-rule oracle. Runtime `DTSTAMP` was checked against
the execution interval, independently of saved report generation time.

Invalid-date refusal preserved all seven report files. A real preclosed stdout
pipe retained a complete 4,823-byte calendar and returned status 2 without an
ignored shutdown exception. Twelve source/receiver/protocol records, all six
generated inputs, the complete saved report and ordinary calendar retained their
bytes and native modification times. Raw receipt:
`e05841cfb0312d2de2f55990327f4c11c9a09bb8`.

The 0.6971133-second observation is the executor-call wall time, not a performance
benchmark. Child PIDs 3–7 are scoped to that executor's namespace.

## Focused native tests

The exact two unchanged test modules ran once on the verified estate ThinkPad
(`d55b2499-5e82-4805-819a-d0d7ddea1efe`, `hamon-thinkpad`, account `jacob`).
The existing `/usr/bin/python3` 3.14.4 and pytest 9.0.2 were used without an
installation. Source admission bound exactly 17 files to manifest
`e7d2dfd71d9d899ec778e755854073dc152685c8`.

Frozen controller `70e1e1b7df489d531618390890fb17975c36c4a0` and protocol
`7a008247568434649badafca5f50a62696ddbccc` preceded source exposure. The single
command ran the 11 date-admission cases and eight calendar-receipt tests with
isolated Python, disabled pytest cache/plugin autoload, an owned temporary
directory and a 60-second process-group bound. Raw pytest output is:

```text
19 passed, 4 subtests passed in 1.53s
```

Child 612155 exited 0, was reaped and did not time out. All six controller
checks passed; the 19 source/controller/protocol records, separate manifest
and exact source inventory were unchanged. Child-controller elapsed time was
1.720098881 seconds; RDC call 612088 separately reported exit 0 and 1.82 seconds.
Raw native receipt: `7263f578848564b6864d94d0d6e9d302a3a13c75`.

An earlier staging wrapper's discretionary 1 GiB free-space guard refused
before creating a stage. Static fixture inspection established the small
six-patient scale; a 100 MiB staging guard admitted the available 555 MB. No
files were deleted, controller/test changed or test invocation repeated.
The pre-stage refusal remains in the outer observations. The exported core
retains 24 raw paths; a separate manifest records the full 152-path native
export, including temporary test fixtures. This is focused Linux receiving,
not a full repository suite or Windows result.

## Delivery and integration boundary

The independently received full portable kit will preserve the 25 maintained
runtime, UI, license, guide, focused-test and existing fictional-sample files,
with separate opening instructions and source/outer manifests. Actual download,
extraction and command receiving belong to its delivery record. A source-tree
hash alone is not package receiving.

This work publishes a separately named, skip-annotated opt-in branch. The
existing dynamic Pages/no-Actions main-integration hold remains. It does not
change repository settings, workflow definitions, main, draft PR107 or draft
PR115. No installed application, browser course, calendar-client import or
clinical validity is claimed by these composition checks.

## Evidence

- `author/`: frozen contract, byte-composition proof, complete-tree plan and
  received-tree record, exact native source manifest.
- `independent/`: frozen protocol/receiver, source verdict, raw five-child logs,
  fictional inputs/report/calendars and evidence manifest.
- `native/`: frozen bounded controller/protocol, exact two-module output,
  native source custody and execution/export observations.

The compact tree-plan record keeps all 30 source changes and the exact input
tree IDs. Complete Git inventories are recoverable through those immutable IDs;
unchanged repository-wide rows are not copied into the evidence packet. The
author scripts record the executed workspace paths and are historical
implementation evidence, not the portable package's opening commands.

Earlier date and calendar evidence remains at its original repository paths.
The composition adds a joint consumer result while retaining their separate
claims and limits.
