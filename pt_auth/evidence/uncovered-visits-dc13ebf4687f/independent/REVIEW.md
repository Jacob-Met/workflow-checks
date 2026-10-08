# PT uncovered-visit review: independent acceptance

**Accepted at candidate 9676a5a20f3adab0ccf46e31e3052de04f50d267 for source, CLI/report, and exact-inline UI receiving through the real local App.** No source correction is requested. Graphical layout, native keyboard navigation, and a browser-initiated download remain unqualified because sufficient temporary space was unavailable.

The source belongs to Jacob-Met/workflow-checks issue [26](https://github.com/Jacob-Met/workflow-checks/issues/26), based on upstream 9e931fa9f42033bf2368f7149684fb5631345715 and tree 0b0c903801f432968e9cdfb1f1fa134cecc37217. The local baseline is an exact partial reconstruction, not upstream Git ancestry. Fifteen existing inputs match that upstream tree; all three new source/test paths were absent. The seven changed paths match the author's frozen manifest. Allocation, data loading, timezone handling, staff state, web code, and supplied sample files remain unchanged.

## Independent receiving result

The authored example has 14 appointments: seven upcoming scheduled visits, two recorded completed visits, one separate past-scheduled visit, and covered/no-auth/cancelled/no-show controls. One completed visit has a future recorded date; the unchanged engine counts it as completed. A timestamp crossing midnight becomes the prior UTC clinic date and stays solely in status review. An approved staff item hides its grouped work item by default.

The baseline digest and all-staff-state worklist omit the fifth and sixth appointments of one patient's scheduled group. The candidate exposes all nine eligible appointments, even while a worklist filter shows zero work items.

- Three actual CLI invocations verified every field of all nine rows, including the actual visit clinic, blank names and clinic, an unknown visit payer despite a known primary payer, Unicode, literal HTML, commas, quotes, and an embedded CSV newline. Physical source-row evidence correctly starts at row 3 after that newline.
- All previous summary fields and counts match after excluding only the clock timestamp and new fields. The three old CSV byte streams, existing printable sections, and staff-state bytes are preserved. The original raw uncovered array still contains its separate tenth past-scheduled row.
- Four ephemeral instances of the unchanged real App served pinned baseline/candidate UI bytes and authored reports. The exact inline programs ran against an explicitly authored DOM boundary. Existing cards, worklist, status review, ledger markup, and export actions match the baseline.
- Status, actual-clinic, literal case-insensitive search, and combined filters returned the expected visit sets. Blank clinic is distinguishable from all clinics. Unknown payer context remains unavailable. Regex punctuation has no special search meaning.
- With one appointment shown, an actual HTTP GET to the emitted download link returned the exact complete nine-row CSV. Its text explicitly says that UI filters do not restrict the export.
- A matching-zone legacy summary did not silently rerun on GET. It offered a rerun message and withheld the new export. Invoking the actual existing Run handler performed the sole permitted POST, created all nine review rows and the complete CSV, and preserved staff state. An explicit empty review instead showed zero and offered a valid header-only CSV.

The successful comparison made ten local HTTP requests, including exactly one authored legacy POST to /api/run. There were no external, state-edit, or generator attempts, and all fixture servers closed. No inherited suite was rerun.

## Boundaries and retained failure

The inline harness models element values, option parsing, class toggles, and event handlers. It does not establish native DOM parsing, graphical layout, keyboard behavior, physical-device behavior, or clinical correctness. The existing allocation results define eligibility throughout this review.

The prepared review_ui.cjs browser program was syntax checked but never executed. Observed free temporary space fell to 200,704 bytes, with zero free bytes on the root filesystem; a later check still had only 6,676,480 bytes on shared memory. The 96 MiB browser launch gate was not met. Its presence in this packet is preparation evidence only.

The initial inline reviewer stopped during the baseline after four custody checks. Static inspection found that its element allowlist omitted the baseline small element with ID shown. Its final POST-count assertion also overwrote the primary exception; the preserved raw receipt therefore contains that secondary assertion. Both the rejected program and receipt are retained under rejected-harnesses. The corrected reviewer accepts existing elements carrying IDs, preserves primary errors, and passed the complete comparison. No candidate source was changed.

These are historical review programs with explicit local roots and one-shot authored outputs. They are not new portable product commands. The legacy fixture was advanced by the successful review and needs a fresh authored baseline before a later browser rehearsal.

See [review-receipt.json](review-receipt.json) for exact bindings, [report-receipt.json](report-receipt.json) and [inline-receipt.json](inline-receipt.json) for raw checks, and [PUBLICATION-MANIFEST.json](PUBLICATION-MANIFEST.json) for the allowlisted packet. The manifest binds every published file except itself; its own pin is supplied in the handoff.
