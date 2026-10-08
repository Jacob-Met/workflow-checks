# Complete uncovered-visit review

This is the author qualification for [workflow-checks issue #26](https://github.com/Jacob-Met/workflow-checks/issues/26), contributed by `estate-accel-dc13ebf4687f`. It extends the existing PT authorization tracker with complete appointment inspection, filtering, CSV export and printable detail.

## Operator benefit and observed comparison

The original worklist already counted uncovered visits and grouped authorization work by patient/payer. Its scheduled-visit detail abbreviated a group after four visit IDs. An authorization specialist therefore had to return to the source schedule to identify the remaining appointments. The new view exposes every appointment represented by the existing scheduled/completed uncovered counts, together with its source row.

| Identical synthetic input | Existing eligible visits | IDs absent from the original printable digest | New review, CSV and printable rows |
| --- | ---: | ---: | ---: |
| Authored 13-visit mixed-status fixture | 6 scheduled + 2 completed | 2 | 8 |
| Unchanged shipped 842-visit sample | 194 scheduled + 2 completed | 110 | 196 |

The authored omission was `V-UPCOMING-5` and `V-UPCOMING-6`. The shipped example includes patient `SYN-1024` / payer `PAY-WC`, whose nine scheduled uncovered appointments were abbreviated after the first four. `baseline/` preserves the original observations; `qualification/preservation.json` binds the new results to the original summary and output hashes. The small before/after reports in `example-before/` and `example-after/` are entirely synthetic.

## Exact source boundary

The canonical source observation is `Jacob-Met/workflow-checks` main `9e931fa9f42033bf2368f7149684fb5631345715`. The lead separately confirmed its tree as `0b0c903801f432968e9cdfb1f1fa134cecc37217`. `source-preconditions.json` is an excerpt of the retained original connector tree response, not a fresh current-main read. It records the four existing-file preimages and the absence of the three new paths.

The local partial baseline is `d67c6087ab5fae717be2eec08f131d2c80b539f6`; the frozen local candidate is `9676a5a20f3adab0ccf46e31e3052de04f50d267`. These commits describe an exact sparse reconstruction, not upstream ancestry. `candidate-manifest.json` records all seven changed/additive paths and their raw-byte Git/SHA-256 identities. `candidate.patch` contains that exact change. Existing CRLF bytes are preserved.

The implementation adds `ptauth/uncovered.py`, integrates its projection into `report.py`, prints the new CSV path in the existing CLI, and adds the **Uncovered visits** tab to the existing UI. The other source additions are the two focused tests and README documentation. The engine, loader, web handler, generator, existing tests and five captured sample inputs are unchanged. The new projection consumes the existing `build_worklist` unmatched visits and uses precisely the original count predicates: every recorded `completed` visit, and `scheduled` visits on or after the report's clinic-calendar as-of date. A future-dated completed row retains its recorded status. Past scheduled appointments stay in the prior status-review feature.

Each row retains visit ID/date/status, patient ID/name, actual visit clinic, therapist, payer ID/name, whether payer rules are present, visit type and normalized source-row reference. Missing clinic/name/rules stay explicitly missing. The view does not substitute a patient's home clinic or primary payer for the visit's values.

## User workflow

Run the existing worklist command, then select **Uncovered visits**. Filter by recorded status or actual visit clinic, including an explicitly unrecorded clinic. Search is a case-insensitive literal substring across visit ID, patient ID/name and payer ID/name. Every matching row remains available with a shown/total count. Work-item staff state and the existing worklist filters do not remove review rows.

**Download all uncovered visits CSV** always exports the complete report review, independent of the UI filters. The CSV has a header even when empty, and normal CSV quoting retains commas, quotes, newlines and Unicode. The printable digest includes the complete review before the unchanged past-scheduled status section. HTML text and option values are escaped. An older saved summary without the new field asks for a worklist rerun instead of reporting a false zero or offering an unavailable export.

## Qualification

| Check | Original source | Frozen candidate |
| --- | --- | --- |
| Nine focused Python methods | 3 failures + 6 errors exposing the missing feature | 9 pass normally; 9 pass under `-O`; zero skips |
| Seven exact-inline UI cases, identical authored summary | 7 failures | 7 pass; zero skips |
| Authored and shipped output preservation | Retained original outputs | All inherited summary fields equal except `generated_at`; original three CSV files byte-identical; all original printable sections byte-identical after removal of the new section |

Python was 3.12.14; Node was v24.19.0. The Python entry also runs the seven-case Node test when Node is available. These counts are nested coverage and should not be added together as independent Python methods. The baseline failures and final normal/optimized logs are retained in `qualification/`.

The focused checks cover exact eligible membership, source detail, unknown/missing records, future-recorded completion, latest-row corrections, empty/legacy states, clinic timezone boundaries, literal HTML/CSV text, all filters, unfiltered export and staff-state independence. One test uses the existing real HTTP application on an ephemeral loopback port with only authored inputs and state. Another executes the actual CLI child; optimized parents pass optimization to that child. The inline UI checks execute the production script with explicit DOM and API boundaries. They do not claim browser layout or accessibility receiving. Independent receiving evidence is separate.

The portable source test entry, from `pt_auth/`, is:

```sh
python -B -m unittest discover -s tests -p test_uncovered_review.py -v
```

No pytest installation, full inherited suite, real patient data, provider call, account access, native estate connection or deployment was used. All 11 untouched captured source/sample paths and all inputs remained identical across the author checks.

## Evidence layout and limits

`PUBLICATION-ALLOWLIST.txt` and `PUBLICATION-MANIFEST.json` bind this compact author packet. They exclude Git metadata, caches, disposable test state, the old provisional scope draft and large duplicate shipped outputs. The latter were removed only after their full hashes and the preservation result were recorded; `qualification/generated-output-cleanup.json` records that capacity cleanup. The original shipped source and original observation are retained outside this compact packet and identified by `baseline-manifest.json`.

The exact historical author programs are preserved as inert `.source` files under `historical/`. Their original paths and retained-output assumptions are historical: they are not a portable extraction replay. Use the committed tests above in a checkout containing the seven changed paths. The publication receiver must compare the existing-file preimages with its current branch and preserve any newer owner contributions. This packet provides source qualification, not a runtime adoption claim.
