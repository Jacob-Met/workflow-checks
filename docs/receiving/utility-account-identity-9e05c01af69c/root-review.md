# Independent Utility Watch account identity receiving

## Decision

Accept the frozen candidate engine `ff0dc3a473235c55639e4373e3b5a4c786a0cd9ae7badd2be9113f39a4efd3d0` for the scoped account-and-bill identity correction.

The unchanged ten-case native carrier records **3 passes and 7 failures on the original engine**, then **10 passes on the candidate**. One additional migration/retention scenario exercises the existing review CLI across original and corrected reports and passes, giving **11 candidate scenarios accepted**. These are scenario counts from **30 actual CLI processes**, separately attributed from the producer's maintained tests.

The source parent is workflow-checks commit `65461ca8f6bd636cd85c0086210ccb1e6837fbee`, tree `24e0514dcb28c545dc8414090a5147db79d6ddac`. Later freight integration leaves Utility source intact. This receiving does not adopt an unmerged duplicate-header PR24.

## Source and carrier

- Original engine SHA-256: `48c968584d0494ee5fb0538fc7d4c685c2cc3128a45c33f57c2079234cdb7775`.
- Accepted engine SHA-256: `ff0dc3a473235c55639e4373e3b5a4c786a0cd9ae7badd2be9113f39a4efd3d0`.
- Unchanged independent carrier SHA-256: `bf8f2f8268a7323f215fedb918d699506c809b2e4f8af6622d90932e84577246`.
- Structured result SHA-256: `eab29947d3a63f3b2a8fa30a6da0185f26e6251107885b90c87ab6e7a1f36cd1`.
- Runtime: the existing Mac Python **3.13.7**, using native `python -B -m uwatch run` and `review`.
- Native directory: `/Users/me/hamon-receiving-9e05c01af69c/utility-account-identity-root-v1`.

The receiver checked all 12 intake source records by SHA-256, Git blob and byte size. Its candidate context is the exact original 11-file package/test/documentation snapshot with only the frozen candidate engine substituted. The producer's added test and documentation changes are not an oracle or part of this runtime-context claim. The complete baseline and candidate context hashes remain unchanged after execution.

Root reviewed the production diff: only `check()`'s internal duplicate, hold, flagged and exception memberships change to account/bill tuples. Loader, CSV admission, native financial/rate/usage rules, report serialization, review implementation and public schema remain unchanged.

## Native observations

All input records are independently authored synthetic fixtures: four native CSV inputs plus an explicit synthetic marker. The receiver derives its expected per-account result by running the unchanged native system with that account alone, then appending another account's records without shifting the protected account's source-row positions.

Five cases prove that a separate account's late-fee flag, zero-usage exception, unknown-account exception, or either member of a duplicate pair cannot remove the protected clean bill from the approval queue. Both duplicate copies on their own account remain held, and the native duplicate flag remains present. All five cases fail on the original source and pass on the candidate.

Four historical cases append a duplicate ID that collides with another account's prior-year or trailing-three history. They preserve the protected account's usage-spike, effective-rate and naive-comparison observations. On the original source, an account sorted earlier contaminates the later account: two cases fail. The same fixtures with the unrelated account sorted later pass, preserving the original order-dependent counterexample. All four pass after the correction.

The compound-identity control distinguishes account `North:West` / bill `bill` from account `North` / bill `West:bill`. Both original and candidate pass; this prevents a delimiter-joined replacement from being mistaken for a distinct native tuple.

The clean single-account reference produces **all six output files byte for byte identically** across original and candidate source.

## Existing review workflow

The eleventh candidate scenario uses the genuine existing review CLI:

1. Generate and annotate the original source's worksheet.
2. Present that old report to the corrected checker. It returns exit 2 with the changed `payment_queue` reason and regeneration guidance; no worksheet is created.
3. Use the corrected native report with the prior annotated worksheet. The old note remains exact as changed history, and current evidence starts as an open review.
4. Annotate that current finding and reconcile again against the same corrected source/report. The full current row, including its row identity and note, is retained exactly.

The review operations leave input files, original/current reports and the prior worksheet unchanged. This matches the pre-existing engine-source-hash binding. A checker-source change does not silently transfer an old annotation to new evidence.

## Evidence and replay

`independent-v1/result.json` records every scenario, source pin, actual command and count. Original failing comparisons and tracebacks, all native inputs, all six reports per run, command stdout/stderr, and review worksheets remain intact. `receiver-v1.log` and its launch receipt report the process outcome. No expectation or carrier change was made after this run.

For replay, use a new empty directory containing copied `baseline/`, `candidate/` and `receive_account_identity.py`, then run `python3 -B receive_account_identity.py /absolute/new-root`. The carrier creates its own `independent-v1/` and refuses to overwrite an existing receiving history.

This is source and native CLI/report/review qualification using synthetic records. It does not exercise customer files, payments, external services, browser rendering, deployment or a second writer. Hosted gates and current full-tree integration remain root's separate publication checks.
