# Native Utility worksheet list and annotation receiving

This change makes the existing review worksheet usable from the terminal. A reviewer can list the saved findings, select an exact current row ID, and write a deliberate status, reviewer and note to a separate worksheet. The existing `review --previous` command continues to own evidence reconciliation.

## Source and ownership

The original baseline is [`9e931fa9`](https://github.com/Jacob-Met/workflow-checks/commit/9e931fa9f42033bf2368f7149684fb5631345715), tree `0b0c903801f432968e9cdfb1f1fa134cecc37217`. After the account-identity owner merged [PR29](https://github.com/Jacob-Met/workflow-checks/pull/29), this candidate was composed on [`a5fd61b0`](https://github.com/Jacob-Met/workflow-checks/commit/a5fd61b0c361c8a9b8a6737b33ecc9efab46e0ad), tree `5ac515d24c722128f04b7ae343fb7c3e369a06c9`.

The product scope is five files:

- `utility_watch/uwatch/worksheet.py`: native list and explicit annotation commands.
- `utility_watch/uwatch/cli.py`: four additive registration/dispatch lines.
- `utility_watch/tests/test_worksheet_cli.py`: actual CLI receiving and bounded publication faults.
- `utility_watch/docs/worksheet-cli.md`: complete use and preservation contract.
- `utility_watch/README.md`: one added workflow section, composed with PR29's exact current README.

The native validator, integrity manifest, reconciler and publisher remain the original `review.py` blob `2475217ce9c073c39756f9fa3926342cd83f7254`. Current engine blob `b764a1f45ba718b31f7841e2c2f61d16a7fef5e9`, its account-key test and HARDENING notes remain exact parent content. Removing the added README section restores the current parent's complete README. All 18 selected inherited files match the current tree.

The [scope claim](https://github.com/Jacob-Met/workflow-checks/issues/21#issuecomment-6061094462) was posted by root while source implementation was already underway under standing direction and the serialized coordination write was queued. The packet preserves that chronology. The printable `review-report` consumer has its earlier central claim by `estate-accel-e04ee971c817` and a current project claim in [#30](https://github.com/Jacob-Met/workflow-checks/issues/30) by `estate-e82707f2bc62`. [#31](https://github.com/Jacob-Met/workflow-checks/issues/31) owns the local browser notes desk, and [#32](https://github.com/Jacob-Met/workflow-checks/issues/32) owns source-evidence inspection. These separate interfaces keep their own files and additive CLI/README seams. Original worksheet reconciliation, engine rules, report generation, demos and CI remain with their existing owners.

Fresh publication input is `5b12dcd4c3a2c09d6602b2313e2bb556ac5997f7`, tree `e16dd0815e252c7e1715545999918f303bc823af`. Its 214 intervening changed leaves belong to Freight and its evidence; every Utility source input remains exact, so unchanged runtime checks were not repeated.

## Use

From `utility_watch`, after creating a native report and worksheet:

```sh
python -m uwatch worksheet list --worksheet review-1.csv
python -m uwatch worksheet list --worksheet review-1.csv --include-history --json
python -m uwatch worksheet annotate --worksheet review-1.csv \
  --row-id FULL_CURRENT_ROW_ID --status in_progress \
  --reviewer "Alex" --note "Asked the vendor to check this invoice." \
  --out review-2.csv
```

All three annotation values are explicit; `in_progress` and `reviewed` require nonblank reviewer and note. Reopening and deliberately clearing values uses `--status open --reviewer= --note=`. Only those three cells on one current row change. Protected cells, the manifest, history, other reviewers' cells and prior input bytes remain exact. Literal Unicode, commas, surrounding whitespace and multiline notes are retained. The output uses the native publisher's canonical CSV encoding.

List filtering happens after whole-file validation. “Current” means current within the recorded worksheet; the report date and synthetic/client marker remain visible. Exact account matching and full row IDs keep accounts and evidence versions distinct. A historical row, finding ID, bill ID or partial ID cannot select a current row.

## Executed qualification

| Phase | Source | Observed result |
|---|---|---|
| Missing workflow | Original `9e931fa9` | Real generate, run and review succeeded; actual `worksheet list` exited 2 as an unknown command, with empty stdout and every existing synthetic file preserved. |
| Original author checks | Four authored executable/test files plus original README | 14 unittest methods, 43 actual native CLI children, zero failures/errors/skips. |
| Current author checks | Exact PR29 engine and current README composition | Same unchanged 14 methods and 43 native CLI children passed; every used source file stayed unchanged. |
| Independent original receiver | Original engine | 14 real CLI children and 16 explicit absent-to-returned lifecycle checks passed. |
| Independent current receiver | Current PR29 engine | Only that focused receiver repeated; 14 real CLI children and 16 checks passed with no mocks or author-suite invocation. |

The author suite covers full validation before filters, annotation into native reconciliation, explicit clearing, raw notes and other-reviewer preservation, same bill ID in two accounts, changed-evidence history, invalid/historical selection refusal, existing and raced output refusal, and source changes during annotation. Three trusted local faults exercise native input revalidation, `os.link` collision and `fsync` failure; they do not substitute a model implementation.

The independent receiver proves that identical evidence returning after absence gets a fresh open row. The old historical ID refuses; a new explicit annotation survives native `review --previous`. Every historical/protected/manifest/other-reviewer cell and prior input byte remains exact. Its complete 68-file packet is retained unchanged under `independent/`, including its separately pinned original run.

## Evidence and replay

`manifest.json` binds all product and receiving files except itself by bytes, Git blob, SHA-256, mode and type. `shared-file-integration.patch` contains only the two existing-file seams; the three new files live in their native package locations. `results.json` points to the original and current receipts. `author/baseline/` retains the actual missing-command input, report, worksheet and command output. The original author README, which was the only authored file recomposed after PR29, is retained separately.

The exact executed baseline driver is frozen in `author/capture_baseline.py`. Its local layout assumes a fresh sibling `base/utility_watch`, `tmp` and `evidence/baseline`; it is an execution artifact rather than a path-independent runner. The source pins and command arguments in its receipt support reconstruction in an isolated checkout.

To receive the current candidate using the installed Python standard library:

```sh
cd utility_watch
python -B tests/test_worksheet_cli.py
```

The independent harness is portable with explicit package and new-output arguments:

```sh
python -B docs/receiving/utility-worksheet-61749b/independent/review_absent_returned.py \
  --package utility_watch --out NEW_EMPTY_RECEIVING_DIRECTORY
```

The current-source capture initially lost its observable child result when shared storage filled during log persistence. That attempt is not counted. The subsequent complete passing output and source-stability result were emitted before receipt persistence; the exact log was recovered from that output and verified against its recorded SHA-256 after space became available. `author/current-capture-limitation.json` records this distinction.

## Boundaries

Execution used installed Python 3.12 and disposable synthetic local data. There is no full-project pytest result, optimized-mode result, browser result, real portfolio or financial action claim. Hosted gates remain separately observable after publication.

An annotation records human work; it does not authenticate the reviewer, establish current export completeness, clear a flag, approve an invoice or issue payment. Source-byte rechecking is not an editor lock or adversarial path-swap guarantee. The existing publisher refuses overwriting a raced destination. Worksheet seals are unchanged integrity checks, not signatures. No alternate release, deployment or account operation is introduced.
