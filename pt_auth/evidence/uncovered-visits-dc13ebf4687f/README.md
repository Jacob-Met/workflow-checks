# Complete uncovered-appointment review and export

This packet binds the seven-path PT contribution at local candidate **9676a5a20f3adab0ccf46e31e3052de04f50d267** to its authored qualification, independent receiving review, and source-distribution check. It supports [workflow-checks issue 26](https://github.com/Jacob-Met/workflow-checks/issues/26).

## Existing workflow made complete

The daily worklist groups appointments by patient, payer, and authorization. Its brief descriptions name at most four upcoming uncovered visits in a group. Staff need a complete appointment-level view to locate the remaining source rows and export them for review.

The new **Uncovered visits** tab, printable section, and **uncovered_visits.csv** expose every appointment already counted as an uncovered upcoming scheduled visit or a recorded completed visit. Filters use recorded status, actual visit clinic, and literal patient/visit/payer text. The download explicitly includes the complete review regardless of active UI filters. A missing field in an older saved report asks for Run worklist; an explicit empty array truthfully reports zero.

Allocation, attendance interpretation, timezone conversion, payer rules, and staff work states retain their existing behavior. Past dates still marked scheduled stay in the separate Visit status review. No new authorization decision or live clinical integration is claimed.

## Evidence and limits

| Evidence | Qualified result | Boundary |
| --- | --- | --- |
| [Author qualification](author/AUTHOR.md) | Nine focused Python methods pass normally and with optimization; the exact inline-UI child has seven passing cases. Original source failures remain available. The shipped 842-visit input yields all 196 eligible rows, including 110 IDs omitted from the prior digest. | Authored and shipped synthetic inputs; no inherited full-suite or graphical-browser claim. |
| [Independent receiving](independent/REVIEW.md) | A different 14-visit fixture produces all nine eligible rows with exact source fields. Three actual CLI calls preserve previous outputs. Four real local App instances serve pinned UI/report bytes; the exact inline programs exercise filters, full CSV retrieval, and the actual legacy Run handler through an authored DOM boundary. | Native DOM/layout, keyboard navigation, and browser-initiated download remain unqualified because temporary storage was insufficient. The prepared browser harness was never executed. |
| [Source distribution](distribution/REVIEW.md) | Existing source-checkout run/serve and generic output routes include the new module, adjacent UI, and CSV. Six unchanged metadata files bind the documented entrypoints and CI discovery. | No package install, hosted CI result, public sample rebuild, or deployment is inferred. PT CI does not pin Node; the optional child declares a skip when Node is absent. |

All old summary fields except timestamps and the additive fields, three previous CSV streams, printable sections, rendered work/status/ledger sections, and staff-state bytes remain equivalent in the recorded comparisons. The independent baseline omits its fifth and sixth upcoming appointments; the candidate includes both. The independent retained failure is a reviewer DOM-fixture defect encountered while loading the baseline, with its raw failure and corrected program both preserved.

## Source and receiving custody

The source candidate was reconstructed from upstream **9e931fa9f42033bf2368f7149684fb5631345715**, tree **0b0c903801f432968e9cdfb1f1fa134cecc37217**. Local partial-checkout commits are not upstream ancestry.

At assembly, main had advanced through the unrelated Utility-account PR #29 to **a5fd61b0c361c8a9b8a6737b33ecc9efab46e0ad**, tree **5ac515d24c722128f04b7ae343fb7c3e369a06c9**. All 15 existing PT input pins and all six distribution metadata pins still matched. The four modified-source preimages remain exact; the three new source/test paths and this evidence prefix remained absent. The assembly changes no accepted source bytes and preserves that unrelated work.

The [COPYMANIFEST](COPYMANIFEST.json) records the exact repository destination, frozen local origin, size, SHA-256, and Git blob for each contribution. Assembly references existing frozen bytes directly; it does not duplicate the source checkout. [PUBLICATION-ALLOWLIST.txt](PUBLICATION-ALLOWLIST.txt) enumerates all repository paths in this increment, including the real source paths and carriers. The copy manifest excludes its own digest to avoid a self-reference; its exact pin is carried by the external publication-files mapping and handoff.

The author, independent, and distribution directories retain their original relative layouts and carrier conventions. Authored staff-state files, duplicate generated reports, temporary profiles, and unallowlisted scratch files are excluded. Review programs and receipts record historical local paths and one-shot authored fixtures; they do not create a new portable product command. Root owns publication, hosted CI review, and merge.
