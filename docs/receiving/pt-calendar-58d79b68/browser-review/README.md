# Independent browser receiving — PT submit-by calendar handoff

**Bounded verdict: PASS for the frozen native PT browser/server source.** The original run remains **15 passed / 1 failed**. Its sole failure was an incorrect receiver expectation about a deliberately advanced report date. The unchanged original engine independently confirmed the correct empty result; a separate, targeted replay then passed **1 / 1**, including a fresh completed download. The candidate source did not change.

Reviewer: chatgpt:58d79b68c9e4:mac_estate. Implementation and maintained formatter/CLI/HTTP tests remain with product_work. Root independently owns full date/export semantics and integration. This packet supplies real Mac Chrome UI/transport/download evidence, not a full repository build or calendar-import acceptance.

## Exact source and receiving boundary

- Original source: 9e931fa9f42033bf2368f7149684fb5631345715.
- Qualified native candidate: d75fb908a9893fd40b21112f62af16d32027bbe1.
- Published equivalent source: a68a667f3610153618c6cc8952c72abe980d89aa.
- Shared complete Git tree: 94074bd3d39705fced23629038ab79057e943aff.
- All 55 PT package files were independently checked by SHA256, byte count, Git blob and mode when materialized. Final native readback found all source files unchanged. Direct GitHub commit/recursive-tree readback independently confirmed every PT file at the published commit.
- Producer archive: 98,915 bytes, SHA256 cbdc09043d8c05299d468d7582534c9f3eca873e43e256d0dfafe36f11f9de48. The archive itself is retained at the native review root; this packet carries its exact manifest/materialization/readback records.
- The actual server imported the frozen ptauth.web.App/make_handler and listened on an ephemeral 127.0.0.1 port. The UI and calendar endpoint were not replaced. Installed Python, Node and native headless Chrome were used without installation or a personal profile.

The contract and twelve consequential groups were frozen before reading candidate implementation or author tests. The original freeze and its later metadata-only correction are retained. The correction changes a coordination inventory count from seven to six unreadable records and removes any inference about their contents; the behavioral groups did not change. The runtime UI/web were read only after that freeze. Producer test bodies and the calendar formatter were not used as an oracle.

## Independent fixture and actual files

The fixture builder uses five independently authored synthetic input files and the exact original engine. It initially produces seven work items for 2026-10-31 in America/Los_Angeles:

| Class | Count | Expected export |
|---|---:|---|
| Dated open/submitted | 3 | Included |
| Undated open/submitted | 2 | Excluded with no substituted date |
| Dated approved/n/a | 2 | Excluded with staff-state explanation |

Two eligible patients share the same literal display name but have distinct work-item keys and East/West clinics. Unicode, punctuation, backslashes and long text exercise literal display and byte-aware folding. The original appointment strings are November 1 at 01:30 with an explicit -07:00 offset, around the Los Angeles daylight-saving boundary. Expected submit-by dates are chosen explicitly and confirmed with the original engine; no candidate formatter determines them.

There are **eleven observed completed native downloads**, each retained both at its original GUID path and as an identical named .ics evidence file. Each receipt records the Chrome download identity, suggested filename, completed state, byte count, SHA256 and observed time interval. The receiver reads the native completed file; neither a prepared Blob nor a clicked link alone counts as success.

The independent reader unfolds the actual bytes, checks CRLF and a maximum of 75 UTF-8 octets per physical line, matches the exact selected keys and recorded submit-by DATE values, verifies literal identity/status/evidence/reasons/checklist/zone context, requires distinct/stable UIDs for the tested same identities, and bounds UTC DTSTAMP to the observed request interval. Tested events contain no invented appointment time, recurrence, alarm, attendee or organizer. Root owns full formatter/UID/RFC/date semantics.

## What passed

The original real app displays the fixture worklist and has no calendar handoff control. The candidate evidence then qualifies the following native browser boundaries:

- Default and all-state review counts, explicit undated/approved/n/a explanations, empty eligible refusal, and export of the actual current filtered key set.
- Actual text/clinic filter changes, two identical names with distinct keys, narrower exports and stable identities across repeat/current selections.
- Pending real summary, refresh and staff-state requests. Export is unavailable until a current accepted report/state arrives. A failed refresh stays unavailable; a later valid refresh recovers.
- Actual saved-report and saved-staff-state drift after review. The real endpoint returns refusal until the changed state is displayed and reviewed.
- Delayed real HTTP 200 and HTTP 409 calendar responses retired by later filter changes; delayed success retired by as-of editing. Releasing these requests neither creates an obsolete file nor replaces the newer status. A valid current request recovers.
- Native Tab navigation to the export button and complete Enter key activation. The focused desktop capture shows its native focus outline.
- The calendar panel/button at 390 px, long literal text wrapping, explicit exclusions and live status. The existing large table remains a separate scroll region. These are bounded viewport observations, not an application-wide accessibility audit.

Every successful calendar download asserts that all synthetic source, report, staff-state and audit files are byte/mode unchanged across that action. Both complete runs also preserve the entire exact executed source trees and the immutable fixture template. Existing staff-state writes, report refreshes and deliberate stale-input mutations are recorded separately as test setup/user actions.

## Preserved receiver correction

browser-v1/result.json and failure-7.png remain unchanged. The run advanced the fixture to November 2, after all November 1 appointments, and then incorrectly waited for an enabled export button. The real app correctly displayed zero work items and refused an empty calendar.

asof-original-engine-v2.json preserves a separate execution of the unchanged original engine:

- November 2: zero work items and zero eligible events.
- October 30: seven work items and the same three eligible recorded submit-by dates.

Only the date-transition group was replayed. browser-asof-v2/result.json requires the actual refreshed November 2 report to remain disabled, then performs a genuine October 30 refresh and completes a calendar download whose contents are checked against that independently executed original-engine report. It passed 1/1, with zero browser exceptions. This is **15 historical passes plus a separately corrected date group**, not a rewrite of the first run as 16/16.

Other retained receiving negatives are the first archive validator's refusal of ordinary directory entries (corrected before extraction) and a Mac ENOSPC error when initially writing the driver (before any browser launch). Neither is a candidate failure. Only owned, inactive, reproducible QA/profile caches were reclaimed after checks and receipts; sources, screenshots, downloads and prior failures remain.

## Evidence map

- contract.md, RECEIVER-SPEC.md, RECEIVER-SPEC-v2.md, blind-freeze*.json: contract-first boundary and preserved metadata correction.
- candidate-source-freeze-v2.json, candidate-materialization-v2.json, public-source-readback.json, final-source-and-result-readback.json: exact source/provenance.
- build_fixture.py and fixture-template/: independent input construction and original-engine expected outcomes.
- browser_receiver.mjs: unchanged original 16-group driver, SHA256 854fd9f8100e9415b23f34fbb7f8e42a0914e3c35e35de4fef5512d7f7b165f1.
- browser_asof_receiver_v2.mjs: corrected as-of group plus an explicit single-case selector, SHA256 f0a399e7f67f35804e963276b5b1b96e8ee93ca58d1210fee29ec53135a57b35.
- serve_receiver.py: imports and exposes the real pinned PT server on an ephemeral local port.
- browser-v1/ and browser-asof-v2/: result, network/paused-HTTP evidence, native downloads, screenshots and logs.
- asof_original_engine_v2.py, asof-original-engine-v2.json and asof-original-engine-v2/: independent original-engine correction proof.
- browser*-launch.json and browser*.stdout/stderr.log: exact commands, driver hashes and native exit records.
- qualification.json and manifest.json: bounded verdict and frozen custody.
- conscience-receipt.json: later durable result and completion of the exact original native review claim.

Both Chrome processes exited with code 0; the Python fixture servers were deliberately stopped with SIGTERM after receiving. The first Node receiver exits 1 for its preserved expectation failure; the targeted receiver exits 0. No null exit code is described as success.

## Reproduction and remaining limits

The driver accepts absolute baseline PT package, candidate PT package, fixture-template and a new output path as positional arguments. It uses installed /opt/homebrew/bin/python3 and native Chrome by default; PT_REVIEW_PYTHON and PT_REVIEW_CHROME may select corresponding installed runtimes. It never installs dependencies.

Reproduce the qualified source in an isolated directory, build the fixture with build_fixture.py against the pinned original pt_auth package, and use serve_receiver.py beside the driver. The corrected date driver additionally expects the preserved asof-original-engine-v2/before_appointments/summary.json beside it. PT_REVIEW_CASE set to "edited as-of, revert and actual refreshed report" selects only the qualified targeted replay. For a different source/version, treat all recorded source pins as historical and make a fresh receiving record.

This packet does not claim a calendar-app import, provider update/deduplication/cancellation, OS dialog receiving, a full repository build, later-parent execution, or acceptance of another owner's PT/Utility/Freight work. Full export/date semantics, current-parent composition, hosted gates and source integration remain with their assigned owners. No candidate source blocker was found within this independent browser gate.
