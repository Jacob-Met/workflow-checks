# Independent Utility Watch review CLI receiving

**Disposition: ACCEPT** commit `e2e91f12bc69690b1ea63f4cc68a9784110cc9a0`, tree
`7a10a9bc24c12f59b8a9431202406ee27a08c042`. No source or behavioral blocker remains in
this review's boundary. This is independent source/CLI receiving, not activation,
client-data validation, or payment approval.

## Source boundary

Production changes are the new `utility_watch/uwatch/review.py` and the additive review
parser/dispatch in `utility_watch/uwatch/cli.py`. The native checker, renderer, generator,
existing tests and sample data remain byte-identical to baseline. The complete change set
contains 15 authorized paths including instructions, authored tests and receiving records.
`source-scope-result.json` lists every changed path and all 15 unchanged native leaves.

The baseline is a 17-file materialization of canonical workflow-checks commit
`2f1e5f777197eedd69d51a4d81c0da744b65ad88`, tree
`86e6201872d2f2400537b84a50f026a1335a8c3d`. It is not a complete repository. Its local
baseline commit is `906f1e058e41bee015a58466d5eee9f14ed71394`. Receiving must add the
intended leaves to a reconciled full canonical tree; it must not replace that tree with this
scoped materialization. Fresh canonical composition remains a separate receiving check.

| Production file | SHA256 |
|---|---|
| `utility_watch/uwatch/review.py` | `f9f730ca45140436704d9823eafcfb58fb3922c5d0bf93a21a63f31347c947de` |
| `utility_watch/uwatch/cli.py` | `0f8e6947baaadccc86c1f7d8cd0dd542b88d81b9b1990cc3aab7cbfcf3beb08d` |

Source hashes and the Git pin stayed unchanged during receiving. The user README and
receiving README were read as the behavior contract. Both correctly qualify historical
source custody, stable exports and nonauthentication of checksums.

## Independent evidence

The first run contains **10 groups / 66 actual CLI invocations**, with no failures or errors.
The publication run contains **3 groups / 23 actual CLI invocations**, including eight
deterministic foreign-writer/I/O cases, with no failures or errors. These 13 groups and
89 commands use independently specified synthetic CSV facts and actual `uwatch` dispatch.
They do not call providers or reuse the author's assertions.

The initial fixture has four fictional accounts, twelve bills, two expected flags, one expected
exception and one payment-queue row. The independent controls establish:

- Fresh worksheets contain exactly the expected flags/exceptions and start open. Original
  and candidate native CLIs emit byte-identical summary, flags, exceptions, payment queue,
  HTML and audit files for the same source.
- Literal annotations survive exact evidence, including multiline CRLF, quotes, commas,
  Unicode, tabs, surrounding whitespace and row/column reorder. Another account's changed
  value does not reset the unchanged account's review.
- Changes below displayed rate precision, including a historical bill omitted from the
  visible finding, reset the current annotation even when `summary.json` remains byte-identical.
  The old reviewed row and its exact note remain as history.
- Changed, absent and returned evidence never resurrects an older annotation. Returning
  original evidence receives a new open current row while the prior review stays inspectable.
- Stale or altered reports, numeric type substitutions, invalid dates, duplicate JSON keys,
  nonfinite JSON, ambiguous accounts, malformed CSV, invalid statuses, missing/duplicate rows
  and altered protected finding fields refuse with exit 2 and no new output.
- Existing source/report/previous paths, unrelated existing destinations and symlinks remain
  intact. Ordinary review calls leave source bytes and all original native outputs unchanged.

The publication run retains the actual checker, reconciliation and OS link. It injects only
a synthetic foreign writer or an explicit I/O failure at a named seam. Source, report and
expected-marker changes after the real checker returns, plus a prior-worksheet change after
real reconciliation, are observed and refuse publication. A competing file or symlink wins
the output path without replacement. Fsync failure leaves no published output. A failure to
remove a temporary name after successful publication still reports success for the complete
worksheet; a subsequent ordinary CLI accepts it. All other inputs remain unchanged.

## Qualifications

Use a stable export. The command detects changes it observes during reconciliation; it does
not lock multiple files against continuously running writers. Output publication uses a
complete, flushed temporary file and a real no-overwrite link. Review status never clears an
engine flag, authorizes an invoice or changes queue eligibility. Checksums catch editing
mistakes, not reviewer identity or malicious resigning.

A worksheet retains historical finding text, row pointers, evidence identity and annotations.
Keep the underlying export to recover historical source values. Source row moves can
conservatively require renewed review. All data here is synthetic. Existing business rules
and a full live-client workflow were not audited by this narrow feature review. The author's
81-test result is separate; this packet reports independent controls.

## Replay

The scripts in `as-executed/` are exactly those used for the two main receipts. The top-level
replay script differs only by making the baseline Git ref and manifest location configurable.
The affected original-versus-candidate comparison was rerun alone: one passing group and two
additional actual CLI invocations, recorded in `portability-result.json`. No other assertion
or implementation changed for that adjustment.

From a full repository containing the canonical baseline and accepted feature source, run
these commands using a writable copy of this packet. The source variable points to the package
directory containing `uwatch`, not the repository root. Scripts create new synthetic receipt
directories beside themselves and do not edit the implementation.

```sh
export UWATCH_REVIEW_SOURCE=/absolute/path/to/workflow-checks/utility_watch
export UWATCH_REVIEW_BASE_REF=2f1e5f777197eedd69d51a4d81c0da744b65ad88
export UWATCH_REVIEW_BASE_MANIFEST=/absolute/path/to/independent-review/baseline-source.json
export PYTHONDONTWRITEBYTECODE=1
python -B /absolute/path/to/independent-review/review_cli_receiving.py
python -B /absolute/path/to/independent-review/review_publication_receiving.py
```

For the original local materialization, use baseline ref
`906f1e058e41bee015a58466d5eee9f14ed71394`. Set `TMPDIR` to a writable location with space
when needed. The receipts include actual arguments, exit values, stdout/stderr and controlled
injection events. Raw synthetic run directories were removed only after these complete
receipts were copied and byte-verified; the scripts reproduce their inputs. No live client
data or credentials are included.
