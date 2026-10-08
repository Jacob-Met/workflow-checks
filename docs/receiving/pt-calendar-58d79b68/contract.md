## Direct staff workflow — reviewed submit-by calendar handoff

Owner: `chatgpt:58d79b68c9e4:product_work`, under Jacob's continuing HAMON execution mandate.

Current source is main `9e931fa9f42033bf2368f7149684fb5631345715`, tree `0b0c903801f432968e9cdfb1f1fa134cecc37217`. The complete tree has no AGENTS.md. The PT CLI currently offers generate/run/serve; the local worklist exposes existing submit-by dates, clinic zones, evidence, checklists and staff status, but there is no calendar consumer.

### Outcome

Let an authorization specialist explicitly download the dated open/submitted items from the currently filtered worklist, or export them from an already generated report through one native CLI command. The handoff is a local iCalendar file for review/import in the user's chosen calendar app. It neither submits anything to a payer nor recalculates eligibility, visit capacity, deadlines or staff state.

### Frozen semantic boundary

- Export the existing `submit_by` date only. Do not substitute the next appointment, auth end or current date for an undated item.
- Each included item is a one-day **all-day VEVENT** using `DTSTART;VALUE=DATE`, with no invented time, TZID conversion, appointment booking, recurrence, alarm, attendee or organizer. Preserve the recorded clinic-zone label as context. RFC 5545 §3.6.1 defines a DATE event with no DTEND/DURATION as one day.
- Preserve the original work-item key, patient/payer/auth identity, clinic, source evidence, reasons, checklists and recorded staff status. Only open/submitted items with valid dates are included; undated and approved/n/a rows remain explicitly counted/reviewable as excluded.
- UID is a deterministic hash of the export format, existing work-item key, clinic, auth-end period discriminator and recorded clinic-zone label. Filtering, repeat downloads and a later report with the same identity retain the UID. A changed submit-by date remains a changed date on that identity. The export timestamp is actual UTC. Importer update/deduplication/cancellation behavior is not claimed, and exporting does not modify prior imports.
- Browser download must correspond to its reviewed report/state snapshot and current selected rows. Source/state drift, pending refresh/state changes, edited as-of input, malformed input or empty eligible selection makes download unavailable or explicitly refuses it. A failed or obsolete download cannot revive an earlier handoff.
- CLI consumes saved summary/state without running the engine or creating reports, preserves all input/state files, and refuses an existing output destination. Calendar text uses CRLF, escaped TEXT values and UTF-8-safe 75-octet folding.

### Exact source scope

New `pt_auth/ptauth/worklist_calendar.py` and `pt_auth/ptauth/calendar_ui.js`; narrow additive calendar command in `pt_auth/ptauth/cli.py`, read-only calendar/snapshot/static hooks in `pt_auth/ptauth/web.py`, and calendar panel/lifecycle hooks in `pt_auth/ptauth/ui.html`. New `pt_auth/tests/test_worklist_calendar.py`, unique zero-dependency browser receiver/support under `pt_auth/tests/browser/`, an additive section in `pt_auth/README.md`, and unique `docs/receiving/pt-calendar-58d79b68/` evidence.

Core data/engine/report rules and output schema, staff-state write behavior, generators, synthetic datasets, existing tests, PT what-if demo, Utility/Freight modules, shared landing/CI and deployed routes remain with their owners.

### Ownership and qualification

Before reservation I read current HAMON #140/#142/#143/#147, the complete current project issue/PR set, the actual PT source, all eight matching native external coordination records, and matching code claims. The only matching native code claim is an older unrelated website-backlog scope. No active PT calendar owner was found. Utility #25/#24 and #142's printable Utility worksheet retain their exact paths; PT #12/#14 and what-if #18 retain their integrated authorship and receiving boundaries.

Implementation uses a clean owned native worktree, installed standard-library Python/Node/Chromium, disposable synthetic files and one bounded browser profile. Qualification will preserve the original missing-command/control result, test meaningful changed dates/filters/states, exact calendar identity/content, source/output preservation, stale requests, actual downloads, keyboard interaction and 390 px layout. Root will independently review the frozen export/date semantics before expected-head source integration. No new service, package installation, real patient data, payer/calendar/account action, public release or native goal lease is implied.


## Primary format source

RFC 5545: https://www.rfc-editor.org/rfc/rfc5545.html — sections 3.1, 3.3.11, 3.6.1, 3.8.2.4, 3.8.4.7 and 3.8.7.2. All-day DATE values retain the recorded calendar date; lines use CRLF and octet-aware folding; TEXT escaping is independent of event-property syntax. DTSTAMP is actual UTC export time. Calendar import behavior remains outside source receiving.
