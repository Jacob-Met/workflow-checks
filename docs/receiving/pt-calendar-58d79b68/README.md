# PT submit-by calendar receiving

This packet qualifies the PT calendar addition for [workflow-checks issue 27](https://github.com/Jacob-Met/workflow-checks/issues/27). The feature exports a reviewed local worklist selection as an iCalendar file and provides the same saved-report handoff through the CLI.

## Exact source

| Source stage | Pin |
| --- | --- |
| Original canonical parent | `9e931fa9f42033bf2368f7149684fb5631345715` |
| Native authored feature | `d75fb908a9893fd40b21112f62af16d32027bbe1` |
| Published source-only feature | `a68a667f3610153618c6cc8952c72abe980d89aa` |
| Exact native/published feature tree | `94074bd3d39705fced23629038ab79057e943aff` |
| Qualified composition's PT parent | `ea6ff4da45c038dd7440f83dc34d61ab245e1e52` |
| Final publication's canonical parent | `5a70e458ed455d47ef672ed9b5a614ec59812f0c` |
| Native current-parent composition | `33432db05b9def1a249650c79571402400c18d15` |
| Current composed source tree | `92f2df0d4bf1f6955f46449b04f2fb191e0bd2ea` |
| Formatter SHA-256 | `89751f1de5548ced34a59c296d0edf1eda06a38bdb935be3e7c3c8b2ae5d55c0` |

The original native and connector publication commits have different commit identities; their complete feature trees are identical. While evidence was being assembled, the earlier uncovered-visit workflow landed through PR 34. The final composition applies the original calendar patch onto that exact canonical PT parent and adapts only the existing authored-DOM test bootstrap to load the declared external calendar module. The formatter, calendar module, web module and calendar tests retain their exact historical blobs.

The independently received composition preserves all 626 unrelated leaves of its PT parent. The final publication also incorporates the later Utility worksheet merge; that later parent's entire pre-calendar PT subtree is identical, so the qualified PT source does not change. A separate reverse-index proof restores only the old test bootstrap, reverses the original calendar patch, and recovers the entire canonical parent tree exactly. This establishes preservation of the earlier owner's shared UI/CLI/README additions as well as its report, CSV and filters. Current source pins and receiving are in `current-source-receiving/`. The earlier `integration/runtime-composition.json` remains a historical preflight on the preceding Freight parent; it is superseded for final source by `current-source-receiving/source-freeze-v2.json`.

## User behavior

The calendar panel reviews the currently filtered worklist and offers an explicit local download. It includes only dated open/submitted items, preserves each existing `submit_by` date, and discloses undated and completed exclusions. Pending refreshes, edited as-of input, staff-state updates and filter changes retire an earlier selection. A changed reviewed report or state rejects the export; late responses cannot trigger an old download.

The CLI consumes an already saved report:

```sh
cd pt_auth
python3 -B -m ptauth calendar --report SAVED_REPORT_DIR --output NEW_FILE.ics
```

Optional `--priority`, exact `--clinic` (including an admitted empty clinic), and repeated `--key` arguments narrow the selection. Success writes a complete new file and one JSON result. Invalid input, an empty eligible selection or a pre-existing destination fails without replacing a file. The CLI does not run the engine or mutate saved report/state inputs.

Events are one-day all-day values. Stable UIDs identify the work item within its clinic, authorization-end and recorded-zone scope; `DTSTAMP` is actual UTC. The wire format escapes literal text, uses CRLF and folds UTF-8 lines without splitting code points. It does not assign appointment times or infer missing dates.

## Qualification

| Lane | Exact result | Evidence |
| --- | --- | --- |
| Native author | 19 additive standard-library tests; full PT 116 passed, one existing skipped, 45 subtests passed | `producer-v2/` |
| Source-stage hosted | Python 3.10 and 3.12 jobs passed on exact source-only head `a68a667f` | Producer archive; [run 37785036652](https://github.com/Jacob-Met/workflow-checks/actions/runs/37785036652) |
| Independent date/export receiving | 18 of 18 independent methods passed, no failures or skips | `semantic-review/` |
| Independent actual Mac browser receiving | Original run 15 of 16 groups passed; the corrected as-of group passed separately, without a product source change | `browser-review/` |
| Native current-parent seam | Calendar 19 methods and uncovered-visit 9 methods passed; the 7 inline groups belong to one of the latter methods | `current-source-receiving/` |
| Current-parent actual browser seam | 5/5 focused groups passed; 3 completed downloads (one full uncovered CSV and two calendars), zero exceptions | `composition-browser-review/` |
| Producer visual readback | Actual desktop keyboard-focus and 390 px captures inspected; readable panel, exclusions and focus state | `integration/producer-visual-readback.json` |

The browser receiver completed 11 real local `.ics` downloads across the two runs with no browser exceptions. Its synthetic fixture came through the unchanged original engine and used seven work items: three dated eligible, two undated and two completed. The receiver froze its independent controls before candidate implementation or author-test access. It checked selection and current-state boundaries, actual completed bytes, exclusions, delayed responses, keyboard use, narrow layout and source/input preservation.

The current-parent receiver executed the real newly composed App/Run/Chromium flow. It preserved the complete uncovered CSV while its view was filtered, kept staff work state independent from uncovered appointments, completed filtered and refreshed calendars with the new report fields, and observed real 409 refusal after report drift before a real Run recovered. All 118 executed PT source leaves remained byte/mode exact. The independent bootstrap source review is `integration/bootstrap-independent-review.json`; its scope remains separate from that actual browser evidence.

The final publication head's hosted gate is a later integration record. The earlier source-stage run qualifies its recorded source head only.

## Preserved failures and corrections

The producer's first draft rejected valid native blank clinic/name fields. The original report run without optional patient metadata, failing CLI result and six exact earlier source files remain in the producer archive. The qualified revision admits the original blank values, retains exact clinic filtering, and passes the same actual CLI route.

The browser's original sixteenth group expected a nonempty report after moving the as-of date to November 2. The unchanged engine correctly returned no work items because all synthetic appointments had passed. That original timeout, raw result and screenshot remain unchanged. The focused receiver correction requires the empty report to keep export disabled, then refreshes to October 30 and completes a download containing the independently expected three eligible events. The original result is still reported as 15/16; it has not been rewritten as a clean full run.

The newly landed uncovered-visit harness initially failed because it executed only the inline UI and omitted the declared external calendar module. All seven groups raised the missing-module ReferenceError. The preserved bootstrap adaptation loads the exact real module into its authored DOM environment and supplies the methods it needs. Every original test body and all helpers after the bootstrap remain byte-for-byte identical. The nine-method receiving then passed, including the same seven inline groups. There is no production fallback or relaxed assertion.

Both native devices encountered ENOSPC during evidence transport/publication preparation. Those failures did not change qualified product source. Relevant transfer and publication readbacks are retained separately from successful runtime receiving.

## Evidence custody

The producer archive contains 74 manifested files plus its manifest and later native receipt (76 files). The immutable producer manifest SHA-256 is `c617368ad4761333b9fcff883005e7bb372662380dea2c8ce4098999423df26e`; archive SHA-256 is `fa79ce904bd754815fef2e8dcf4b63e108cf0cc46ea63452cfebd83453366a69`.

The semantic receiver has 29 manifested files, its manifest and its later native receipt (31 files). Manifest SHA-256 is `bf8d65ea7bf2a3aa8a9b46850860fc2b77fe91626e518205d7cb8add72e6bb0d`. Its result is ConscienceLog sequence 4151 and its exact review claim completed at 4152.

The browser receiver contains 110 manifested files plus its manifest and later native receipt (112 files). Its manifest SHA-256 is `6da0e9179229ced9b4ce3b362ab1f755d8b754387260d9c99fccdade3b79b807`. Its result is ConscienceLog sequence 4160, event `cev_a7f33c29572a418eab3a58bc`; its exact review claim completed at 4161. The packet's own manifest, qualification, later receipt and transfer verification preserve the exact file counts and hashes.

The current-parent browser receiver contains 42 manifested files plus its manifest (43 files). Manifest SHA-256 is `2fe58c53ad26fd03efa6deb3a0cbfb560fe959aca58db5ee2e54c6b92de277ce`; its native result is sequence 4230, event `cev_7da8ac50ce2c43f0a0b117e2`. This is separate from the historical Mac packet and records the exact composed source.

Receiver directories are copied byte-for-byte for browsing. The adjacent archives also preserve their native UNIX mode bits: Git records file executability, but does not represent every original group-write permission. Copy/transfer receipts explain this distinction. Historical packet readmes and results retain their original stage boundaries instead of being rewritten by the implementation owner.

## Scope and integration boundary

The calendar contribution leaves the current canonical engine, eligibility, payer rules, report generation and staff-state writer unchanged. Earlier uncovered-visit issue 26 landed as PR 34 and its entire contribution is preserved. The calendar's additive UI/CLI/README hooks were disclosed before source publication, and the precise later test-bootstrap adaptation was disclosed in [the same owner thread](https://github.com/Jacob-Met/workflow-checks/issues/26#issuecomment-6062065947). Utility, Freight, shared CI and existing PT what-if paths remain outside this feature.

Qualification uses authored synthetic data. It covers the local application, saved-report CLI and downloaded wire format. It does not establish clinical correctness, calendar-client import/update/deduplication behavior, live administrative processing or deployment. The reviewed snapshot is an observed-content check, not a writer lock or authentication mechanism.
