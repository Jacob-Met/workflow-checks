# Utility Watch editable review desk — native receiving

The desk opens one saved native review worksheet on a loopback URL. A reviewer
can edit current status, reviewer and note, filter the list, inspect history and
download a complete validated CSV. The selected worksheet is never written.
The existing review command remains the reconciliation authority.

## Source pins

| Role | Commit | Tree |
| --- | --- | --- |
| Original baseline | `9e931fa9f42033bf2368f7149684fb5631345715` | `0b0c903801f432968e9cdfb1f1fa134cecc37217` |
| Authored product and actual browser source | `fa057a67c428fb6ccd1517e7f9eb51d946ab12d6` | `9124788f2224f99f153642754c6dc832ed4762c2` |
| Receiving public main | `5a70e458ed455d47ef672ed9b5a614ec59812f0c` | `86f234b92173176c7f3c8ae4e1e4d5d3c41d36fd` |
| Qualified current composition | `65c306d1138d57ceb0fbcb7829addbd36da832d8` | `12266e043adaeb99d49c42a5191dfdf5efdbe92b` |

Scope reservation: [workflow-checks issue 31](https://github.com/Jacob-Met/workflow-checks/issues/31).
The native composition is a normal merge of the authored product and the
receiving main. The four desk runtime files, guide and three authored test files
are byte-identical between those product commits. README and CLI are additive
unions; their inherited CRLF convention is preserved. All 709 other current
base leaves remain exact. The native worksheet validator stays at blob
`2475217ce9c073c39756f9fa3926342cd83f7254`.

The printable report, account-scoped checker correction, independent worksheet
terminal controls, source-evidence commands, PT, Freight, existing reports,
shared CI and deployed routes retain their owners. No public deployment or real
utility account action was performed for this desk.

## Actual qualification

| Gate | Exact scope and result |
| --- | --- |
| Original baseline | 81 existing tests pass; the proposed CLI command is absent and exits 2 without output. |
| Authored native tests | Nine groups pass. The complete original-base package passes 90 tests with an owned temporary directory. |
| Authored actual browser | Nine groups pass on native Chromium 153.0.8010.47 and Node 22.22.1. Real pointer/keyboard edits and four real CSV downloads; one actual native review reconciliation. |
| Independent actual consumer | Six groups pass on the authored product, using a separately produced original-native worksheet and original validator. Two real downloaded files and one actual original-native reconciliation; unchanged independent packet is adjacent. |
| Current composition | 24 affected engine, printable-report and desk tests plus 16 subtests pass. Four additional groups exercise five actual CLI children and real loopback HTTP. No browser repetition is attributed to this composition. |

The browser controls cover distinct accounts sharing a finding key, literal
markup, Unicode and multiline notes, hidden edited rows in a complete export,
non-open review validation, real selected-file drift returning 409, correction
and retry, immutable historical/protected/manifest cells, an empty worksheet and
narrow layouts. Authored desktop and 320-pixel screenshots and independent
390-pixel screenshots were inspected. Product pages issued no external requests
and raised no JavaScript exceptions in the passing browser runs.

The changed engine bytes are part of the native evidence identity. The current
composition control starts from the genuine earlier browser download, reruns the
current native report and review commands, and observes three fresh open current
rows plus five historical rows. Every earlier note remains in history.
A new explicit current-origin annotation then survives a real HTTP desk download
and current native reconciliation; the preserved printable command displays it.
The receiving does not force old-engine annotations onto new evidence.

## Retained failures and limits

The lossless raw packet keeps the original results alongside corrections:

- The first authored transport assertion expected a full oversized upload to
  finish before a 413 response. The server closed an unread oversized body
  early. The test now distinguishes the observed broken pipe/reset transport
  from a tiny-body, oversized-header request that receives 413; valid retry
  still succeeds. No product code changed for that correction.
- The first full candidate run reports 76 failures, one pass and 13 setup errors
  caused by native temporary storage quota exhaustion. It is not a passing
  suite. The later owned-temporary-directory run records all 90 passes.
- The first Chromium attempt times out at Page.enable with zero product groups.
  A separately received renderer precondition and the exact native launch
  envelope permit the later real product run. Both originals remain.
- One empty temporary receipt records an interrupted ENOSPC write. The original
  default Git whitespace warning is retained; scoped cr-at-eol checks pass on
  the inherited CRLF files after byte-preservation checks.
- The independent first consumer reached five groups but assumed a second
  download would get another filesystem name. Immediate archival of each real
  fixed-name download corrected only that receiver. Its original red result
  and both exact files remain in the unchanged independent packet.

No shared cache, quota, permissions, installed browser profile or service was
changed. Only owned temporary directories and source worktrees were used. The
passing browser's fixture, profile, temporary files, downloads and evidence all
used an owned path accepted by the installed Chromium policy.

The original native source repository is shallow at the recorded baseline. Its
older parent `65461ca8f6bd636cd85c0086210ccb1e6837fbee` is not present. This packet
qualifies complete source trees and recorded commits, without claiming a full
earlier ancestry. Portable complete-tree snapshot commits, when supplied, are
explicitly separate roots; public integration uses the existing upstream base.

All inputs are fictional. Review states are human annotations, not approval,
payment, resolution, authentication or fresh checker outcomes. The server does
not save edit state. The UI reports a download request, not filesystem save
completion. Observed source-byte checks are not an editor lock.

## Files and replay

`SOURCE.json` binds both product versions, preserved upstream leaves, raw
receipts and the unchanged independent publication. The raw container preserves
every listed file as exact bytes, including native outputs, fictional CSVs,
screenshots, prior script versions, source hashes and original failures.

Decode to a new owned directory with the existing native receiving decoder:

```sh
python3 -B unpack-receiving.py RAW_EVIDENCE.json.gz.b64 RAW_EVIDENCE_MANIFEST.json /path/to/new-owned-directory
```

Run the authored commands from `utility_watch` on the source pin being checked:

```sh
python3 -B -m pytest -q -p no:cacheprovider tests/test_review_desk.py
node tests/review_desk_browser.mjs
```

The optional browser runner requires Node 22+ and an installed Chromium.
Set `BROWSER_BIN`, `REVIEW_DESK_PROFILE_ROOT` and `TMPDIR` to explicit owned
locations that the installed browser can use. Original and corrected launch
envelopes are in the raw evidence. `receive-current-composition.py` records the
bounded current CLI/HTTP identity and printable handoff; its original invocation
and input paths are retained. The independent packet carries its own replay
instructions and remains attributed to the authored source.
