# Utility Watch review worksheet receiving

This is the native, offline review workflow for Utility Watch in `Jacob-Met/workflow-checks`.
It lets an AP reviewer assign and annotate actual flags/exceptions, reconcile those annotations
against a later source export, and inspect changed or disappeared evidence without changing a
bill's eligibility. It introduces no service, payment action, browser code, or package dependency.

## Source boundary

Canonical starting commit: `2f1e5f777197eedd69d51a4d81c0da744b65ad88`, full repository tree
`86e6201872d2f2400537b84a50f026a1335a8c3d`. The working repository is a **17-file scoped
materialization**, recorded in `baseline-source.json`, not a full repository clone. Its local
baseline is `906f1e058e41bee015a58466d5eee9f14ed71394`, tree
`b4ee68267915149ea6ee5dab0d3469e1afc6db03`. Publish an additive overlay on the fresh canonical
full tree; do not replace other repository paths with this scoped tree.

Production changes are the new `utility_watch/uwatch/review.py`, an additive parser/dispatch seam
in `utility_watch/uwatch/cli.py`, and user instructions in `utility_watch/README.md`. New tests
live in `utility_watch/tests/test_review.py`. The engine, report renderer, generator, existing
tests, sample exports, and all other owner paths remain unchanged.

The narrow external-contribution record is
`/srv/hamon-estate/coord/estate-a219f250962c/utility-review-coordination.json`, SHA256
`32cee49ae41a53f4780159fefc03b1b4c570ec6765a8c9a61ba9ac497031184a`. Current owner reads found
separate work in `demos/utility-whatif/`, `demos/freight-whatif/`, `demos/ptauth-whatif/`, and
CI workflows; none is included in this change. This contribution does not claim resident Za
or native goal ownership.

## Contract

The command reads a native `summary.json` and its four source CSVs. It validates the report's
dates, mode, findings, exceptions, counts, queue records/total, and naive comparison output
against the unchanged checker on a fixed snapshot. Review uses current default rules.
Duplicate account identities and duplicate current finding identities refuse as ambiguous.

The worksheet's only editable columns are `review_status`, `reviewer`, and `note`. Status is
`open`, `in_progress`, or `reviewed`; a non-open status requires a reviewer and note. Logical
identity includes kind, account, finding key and code. Evidence versions include displayed
facts, complete account/bill/payment source rows, matching unit occupancy, row numbers, native
engine identity, rules, and data mode. A small source change still invalidates a review when
the report's rounded text happens to stay unchanged. A value change on another account leaves
unmoved evidence intact; source row moves conservatively invalidate affected row pointers.

Only the prior **current** row can supply an annotation. Exact evidence retains that row's ID
and literal annotation. Changed evidence becomes a historical `changed` row and a fresh open
current row. A finding absent from the new report/window becomes historical `absent`, which
does not imply resolution or payment. A returned historical version starts open. All history
is retained; it never resurrects a review. A protected checksum plus one manifest catches
accidental changed, missing, added, or duplicate rows; it is not an authentication mechanism.

CSV and JSON are validated before output creation, including malformed CSV shape, duplicate
headers/JSON keys, nonfinite numeric JSON, invalid statuses and altered protected fields.
Observed source/report/previous-file changes during reconciliation refuse. Publication uses
a completed, flushed temporary file and an atomic no-overwrite link to a new destination.
Existing output and input files remain intact, including when another writer wins the path.
This is not a locking protocol for a source export being continuously rewritten: use a stable
export. No review status is read by the existing engine or payment queue.

## Retained before/after evidence

* `baseline-native.log` and `baseline-result.json`: all 45 existing tests pass on the canonical
  source materialization; actual `python -m uwatch review --help` refuses the missing command
  with exit 2. This is the pre-feature control, not a simulated failure.
* `candidate-native.log` and `candidate-result.json`: all 81 tests pass (45 inherited and 36
  new review controls). The result pins four changed source/doc/test hashes and verifies eight
  protected native source/test files byte-for-byte against the baseline.
* `verify_cli.py` and `cli-roundtrip/`: seven actual native CLI commands using generated seed
  11. Generation and report run succeed; review export, literal Unicode/multiline annotation,
  and unchanged reconciliation succeed; a changed source with the old report refuses with
  exit 2 and no output; regenerated source/report reconciles into fresh open evidence plus the
  original reviewed historical row. All source/report/audit/queue files are byte-identical
  across each review-only operation. Three complete review CSVs and a JSON receipt remain.

The new native controls also exercise sub-display-precision source changes, payment identifiers
omitted by the native loader, changed-to-absent-to-returned evidence, unaffected account review,
multiple codes and shared bill IDs, unknown accounts, missing monthly bills, altered/malformed
previous worksheets and summaries, empty reports, source/output collisions, concurrent input
edits, simulated write/fsync failure, path publication races, and a post-publication cleanup failure.

## Reproduce

From the repository root, with Python 3.10+ and the project's existing pytest environment:

```sh
python -B -m pytest -p no:cacheprovider -q utility_watch/tests
python -B docs/receiving/utility-review-a219f250962c/verify_cli.py \
  --package "$PWD/utility_watch" --out /path/to/new-receipts
```

The receiving script requires a new receipt directory and uses temporary synthetic source
files. Set `TMPDIR` to a location with space when necessary. It never contacts a provider.
Independent receiving is tracked separately from these authored receipts.

## Independent disposition

Independent receiving **accepts** source `e2e91f12bc69690b1ea63f4cc68a9784110cc9a0`, scoped
tree `7a10a9bc24c12f59b8a9431202406ee27a08c042`. The exact 13-file packet is preserved under
`independent/` without edits. It reports 13 behavioral groups, 89 actual CLI commands, and
eight controlled foreign-writer/I/O cases with zero failures or errors. Two additional
commands qualify only the portable replay option; the original as-executed scripts remain.

The independent review verifies all 15 untouched native leaves, source/report agreement,
rounded-text hidden-history changes, exact annotations, history nonresurrection, malformed
inputs, protected destinations, concurrent input mutation, and atomic publication failure
boundaries. Its declared limits agree with the product README. The full disposition is
`independent/REVIEW.md`; detailed arguments and observations are retained in its JSON receipts.

Independent manifest SHA256: `471cc7fe6da6274a10ebab411da39954c727646b28459c628666471dc15e5d45`.
The production module, CLI, authored tests and product README remain byte-identical to the
accepted source. This later commit adds only the frozen review packet and this receiving note;
identical source behavior was not unnecessarily rerun. Canonical full-tree publication and
hosted CI remain separate gates.
