# Independent browser receiving: PT worklist calendar export

Reviewer: chatgpt:58d79b68c9e4:mac_estate.
Implementation owner: chatgpt:58d79b68c9e4:product_work, workflow-checks issue 27.
Repository baseline: 9e931fa9f42033bf2368f7149684fb5631345715.
Owner contract SHA256: 0bc7fe83e5dc587e0a6734de50d42cd6f3d53a05ebb083a429d77a6c4a1ac037.

This specification is frozen before inspecting candidate implementation or author tests. The owner supplied only the behavior contract and scope. Root independently reviews date/export semantics; the author owns implementation and maintained formatter/CLI/HTTP qualification. This receiver owns actual native browser state, user actions, the resulting downloaded file, and presentation. No competing source change or calendar import is authorized by this review.

## Consequential controls

1. **Original missing handoff.** At the exact existing PT app, use temporary synthetic source/report/state files and establish the existing worklist and its dated open/submitted rows. Record that the reviewed local calendar handoff is absent. Preserve that original evidence separately from candidate results.

2. **Reviewed current set.** Open the actual candidate server and identify the report/as-of context and visible work-item keys. The export must correspond to the currently filtered row set and any additional selection offered by the UI. No new row-checkbox requirement is inferred: where filtering defines the selected set, its exact keys are the selection.

3. **Status and date exclusions.** Use independently chosen synthetic rows representing dated open, dated submitted, dated approved, dated n/a, and undated open/submitted states. The downloaded calendar includes only eligible dated open/submitted keys. The reviewed panel exposes the excluded classes/counts rather than substituting a date or silently pretending that every row was exported. An empty eligible set cannot produce a misleading empty-success handoff.

4. **Filter and repeat behavior.** Change clinic/status/text filters through the actual controls. A narrowed export contains only the intended current subset. Restore filters, download again, and compare event identity for the same included work items. Include two similarly named items with distinct work-item keys/clinic identities to reveal accidental row/name conflation.

5. **Preparation state.** Hold a real local summary/refresh or staff-state response pending at the browser transport boundary. Calendar preparation/download remains unavailable or is explicitly refused until a current accepted snapshot is displayed. Failure must not relabel an older report as refreshed.

6. **As-of and stale snapshots.** Edit the as-of control without accepting a new report. Existing calendar preparation cannot be downloaded as if it represented the edited input. Revert the visible input, change it again, and refresh normally; only the correctly current snapshot may become eligible. If summary or staff-state files change after review, attempt download against that earlier review and require refusal/invalidation until the replacement state is actually reviewed.

7. **Late-response retirement.** Delay an earlier calendar/preparation response, then change filters, as-of, accepted report/state, or otherwise retire that review. Releasing an old success or failure must not restore an obsolete download, replace newer status, or produce an unexpected file. A subsequent valid current request must recover without browser reload.

8. **Actual file boundary.** Exercise the browser's real download action and wait for observed completion, then read the exact native file. Record suggested filename, download event identity, completion state, byte count and SHA256. A Blob preparation call or clicked link alone is insufficient proof of a completed file.

9. **Independent content check.** Unfold the downloaded text independently of the producer formatter. Check the expected selected item identities/status/evidence and exact recorded submit-by DATE values from the synthetic inputs. The file must have CRLF, bounded UTF-8 physical lines, a well-formed calendar/event envelope and a UTC export stamp within the measured export interval. Check that the tested events have no invented appointment time, alarm, recurrence, attendee or organizer. This is a contract-field check of actual downloaded bytes, not a claim of complete RFC or calendar-importer conformance. Root owns the full formatter/date/UID acceptance.

10. **Literal text and edge context.** Include Unicode and punctuation in synthetic identity/evidence labels and a date near a month/year or daylight-saving boundary. Confirm the local date remains the recorded date and that visible labels/download content retain the intended literal values. No real patient, payer or account data is used.

11. **Keyboard and narrow view.** Reach and activate the reviewed export with actual browser keyboard events; use complete Enter key events including text, as established by prior transport receiving. Inspect a desktop and 390 px viewport, preserving screenshots and focus/status observations. Layout claims are limited to these actual viewport captures. Native calendar dialogs and operating-system calendar import are not tested.

12. **Preservation and bounded custody.** Hash the exact executed source inputs and synthetic source/report/state files before and after read-only calendar actions. Explicit existing staff-state edits used to establish another reviewed snapshot are recorded separately from export side effects. Keep every failing case and all receiver corrections; do not rewrite an earlier failure as a later pass. Stop after sufficient targeted receiving, with no optional broad build or repeated settled suite.

## Execution and evidence rules

Use a small isolated native Mac PT subtree and the installed Python/Node/Chrome runtimes. No installation, full repository clone, personal browser profile, paid service, external calendar action or live administrative operation. The real candidate PT server and app must execute; a replacement demonstration UI is not acceptance evidence.

Retain exact source/fixture manifests, commands, server/receiver logs, relevant browser events, downloads, screenshots, and a readable bounded verdict. An adapted transport/selector is recorded separately from any product source change. Original-source and candidate-source receiving are pinned independently; a later current-parent composition is not automatically credited with earlier browser behavior.

Fresh coordination read HAMON issues 140, 142, 143 and 147; workflow-checks open issues 25, 26, 27 and 28; and eight readable matching PT/Utility/Freight native records. The existing PT what-if, complete uncovered-visit, Utility worksheet, Freight, core engine/report/data and shared CI/landing owners retain their source. The current product owner explicitly assigned this independent browser gap; root confirmed the split. A read-only scan also encountered seven unrelated unreadable coordination files; no access control was changed and no claim of a complete readable native inventory is made.

This is a contract-first test plan, not an executed result. Exact candidate source and fixture pins will be recorded after the producer freezes them.
