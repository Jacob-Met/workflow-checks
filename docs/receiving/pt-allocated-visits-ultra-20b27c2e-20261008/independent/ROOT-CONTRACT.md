# Independent PT allocated-visit receiving contract

Reviewer: ultra-20b27c2e-20261008 / root.
Claim: Jacob-Met/workflow-checks issue43.
Primary base: 0418e6308d886d0678ace759a9b984c1d06ac54d.
Primary tree: 92c62093a0bd4d86e8a518a50cb2869d809cbe63 (953 complete leaves).

This contract is frozen after direct primary data.py, engine.py, report.py, web.py, cli.py and UI inspection and public contract clarification, before reading any allocation candidate or authored tests. The native15-file baseline manifest is independently matched to primary Git objects before use. The independent fixture and probe must remain separate from the author's five-visit baseline.

## Receiver and authority

Use the actual project CSV loaders, current native engine, CLI/report writer and HTTP handler. All files and processes belong to /tmp/ultra-20b27c2e-root-pt-allocations on approved Mac device0e3d582f-e25b-44b2-8418-9639fc4e4e33. All people, clinics, payer records and visits are authored synthetic values. No provider, patient, account, installed service, clinical decision, staff-state mutation or calendar-client import is involved. No dependencies are installed. Check a measured native capacity floor before launch and close owned servers/browser profiles afterward.

The baseline establishes ordinary output positives and exact current ledger membership independently of the missing feature. Expected allocation rows are formed from each existing resolved AuthLedger's auth object and its used/scheduled Visit values, not by parsing the candidate or invoking a new projection helper. Selected simple assignment facts are also asserted manually so an empty or misconfigured oracle cannot pass. Raw source/CSV/output byte hashes are retained.

## Native consumer acceptance

1. Actual CLI on an authored mixed clinic succeeds and its existing summary counts, worklist, ledger, uncovered and status-review meanings match baseline. Existing worklist.csv, ledger.csv, uncovered_visits.csv and visit_status_review.csv bytes remain exact. Audit records retain original meanings after removal of only their recorded timestamp; generated_at is similarly excluded solely from baseline time comparison. Input bytes and all unowned native source bytes remain unchanged.

2. The serialized allocation_review contains exactly one detached row per membership of a visit in AuthLedger.used or AuthLedger.scheduled, with allocation=used or scheduled from membership, not from date inference. Rows preserve every settled public auth/Visit field: resolved auth label, patient/payer IDs, start/end, authorized count, auth source row; visit ID/date/status/type/patient/clinic/therapist/payer and visit source row; as_of and clinic_timezone context. Display names may supplement those identities. Source-row occurrence remains available for disambiguation.

3. Challenge completed-first and earliest-ending capacity, visits exactly on auth window boundaries, visits over capacity and outside windows, scheduled visits before as_of, completed visits after as_of, ignored cancelled/no-show, payer-exempt/no-auth and excluded evaluation records, pending/denied auths, and unknown payer with an actual approved allocation. No omitted record is invented in the projection. No projection action changes engine decisions.

4. Challenge duplicated visit IDs using the actual last-row behavior, overlapping amendments with last source row, separate periods with the same authorization number, repeated display names, same authorization text across patient/payer pairs, blank visit clinic and Unicode/punctuation/delimiter values. Expect the exact resolved auth occurrence and actual visit source row, not lookup by a display name or raw auth number alone.

5. Use an offset-bearing timestamp near midnight with an explicit named clinic time zone. The projection preserves the actual clinic date and recorded report zone. It must not introduce host-zone reinterpretation or reuse as_of to redefine allocation bucket.

6. allocated_visits.csv parses to the complete same semantic rows as summary, preserving quoting/newlines/Unicode and both source references. The printable digest contains every allocated row and its membership/provenance; it must not cap the list or reduce a filtered UI subset. Existing digest worklist/checklist/exception sections remain intact. Hostile authored text is escaped and cannot create script, event handlers, links or markup in the allocation section.

7. Older summary objects with missing/non-list allocation_review produce a visible unavailable message in digest/UI, not a false completed-empty claim. A valid empty list has an explicit completed empty state and a well-formed CSV header. The old input is not silently recalculated or repaired by inspection.

## Real browser acceptance

Use existing Chrome/Puppeteer with a fresh owned profile against a loopback server running actual ptauth.web.make_handler. Record served source bodies and hashes; allow only loopback application requests. Use the author's settled public control labels to locate controls, not internal candidate function names.

Open Auth ledger and the separate Allocated visits panel. Inspect exact rows and totals, keyboard-operated allocation/authorization-occurrence/visit-clinic filters, and a case-insensitive literal per-field query. A query containing regular-expression or HTML metacharacters stays literal; no false cross-field concatenation match. Authorization options with similar labels target the exact occurrence. Empty and no-match states differ, and clearing filters restores all rows.

Download the complete allocated CSV while a restrictive filter is active and compare actual saved bytes to the native written CSV. Open the actual printable digest and verify complete unfiltered rows. Preserve raw source and existing staff-state/audit bytes during read-only browsing/downloads. No approval/state or calendar export request is sent. Retain useful desktop/narrow screenshots; assert usable table scrolling and visible controls without claiming a real mobile device or screen-reader run.

Receive a same-origin older saved summary with the new field absent/non-list, and a valid empty projection, as explicit fixture variants. Existing worklist, ledger, uncovered, calendar and exports remain usable. Record page errors, denied network attempts and exact real download bytes. Do not turn setup failures into product failures.

## Failure and integration handling

Preserve the original baseline's missing-capability outcomes, source-bound candidate failures, fixture/setup errors and their repairs separately. Freeze expected values and native/browser probe source before reading candidate code or authored tests. Any probe correction must state the mistaken receiver assumption and leave original bytes/result intact. Repeat only the affected receiving boundary after a source change; current-source drift is qualified separately.

Root will publish qualified source through ordinary existing Python3.10/3.12 pytest gates, expected-head integration and full unowned-tree preservation. Source/runtime/browser qualification, merge, deployment and operational benefit are distinct states. This contract does not claim any result before execution.
