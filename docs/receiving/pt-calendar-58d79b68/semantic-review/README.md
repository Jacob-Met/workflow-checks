# Independent PT calendar date and export receiving

## Verdict

**Qualified for the exact v2 formatter and saved-report CLI below.** Eighteen independently authored native test methods pass with no failures or skips. The review did not find a blocking date, identity, text-format or output-preservation defect.

Reviewer: chatgpt:58d79b68c9e4:root. Author: product_work, [workflow-checks #27](https://github.com/Jacob-Met/workflow-checks/issues/27). Native review claim 4142 uses claim:pt-calendar-semantic-review-58d79b68c9e4. Source/UI integration and publication remain with the author; mac_estate receives actual browser behavior separately.

## Exact source and independence

Public source a68a667f3610153618c6cc8952c72abe980d89aa exactly matches native d75fb908a9893fd40b21112f62af16d32027bbe1, tree 94074bd3d39705fced23629038ab79057e943aff, parent 9e931fa9f42033bf2368f7149684fb5631345715. The formatter SHA256 is 89751f1de5548ced34a59c296d0edf1eda06a38bdb935be3e7c3c8b2ae5d55c0.

The reviewer read the frozen author contract and primary RFC 5545 body, then wrote its own receiving specification before reading implementation. Spec SHA256 4386db6a20665cdcfc90b4d9365f1ca29bf722b44b4ea1c1f5d8ee35176da66d; author contract SHA256 0bc7fe83e5dc587e0a6734de50d42cd6f3d53a05ebb083a429d77a6c4a1ac037. Eleven runtime files were copied directly from the frozen Git commit and checked against the author's manifest. No author test was read or copied.

The adapter subsequently learned public function names and the native report field shape. Its synthetic fixtures, byte-level calendar parser, identity transformations and saved-file controls were authored independently. Test SHA256 ae92c57d11337a794149e1bacdbb15ec2966d1427aab99f45d6f0dbfb99ae261. Source hashes remain unchanged before and after execution.

## What the controls establish

| Boundary | Observed result |
| --- | --- |
| Selection and staff state | Dated default-open and submitted rows export. Approved, n/a and undated rows remain explicitly excluded. Five selected rows produce two events and three excluded rows; overlapping exclusion reasons are counted without inventing extra rows. |
| Recorded dates | Leap day, both US daylight-saving boundaries, year boundary and years 0001/9999 retain exact DATE values under three different process-zone settings. No appointment/auth-end/as-of date substitutes for an absent submit-by date. |
| Calendar semantics | Events use DATE without TZID, DTEND or DURATION, and are transparent to availability. No alarm, recurrence, organizer, attendee or extra event is introduced. |
| Timestamp | An aware offset time crosses the UTC year boundary correctly. A default export timestamp falls between independent before/after UTC observations and differs from the report's old recorded generation time. Naive injected export time is refused. |
| Identity | UIDs stay stable across ordering, selected subsets, changed submit-by date, report generation/as-of and export time. Changing the declared key, clinic, authorization-end period or zone produces distinct identities. |
| Literal content | Unicode, delimiter characters, backslashes and apparent component/property text survive independent unfolding/unescaping. Every physical line is valid UTF-8 and at most 75 octets. The injected-looking text remains one event's description. |
| Evidence and mutable inputs | Recorded identity, clinic zone, staff notes/time, reasons, details, checklist and source evidence remain inspectable. Original report objects are unchanged; later caller edits do not change a prepared plan. Blank native clinic/name/auth fields remain supported. |
| Refusal | Malformed dates, unknown staff states, inconsistent/duplicate identities, unknown/duplicate selected keys, duplicate JSON fields, nonfinite JSON and incomplete UTF-8 refuse clearly. |
| Actual CLI and files | An actual saved-report invocation applies selected clinic/priority filters, creates a parseable calendar and preserves all saved input hashes. It does not create the absent work_state.json. Invalid input creates no output. An existing output and a destination created during the final-link race remain exact. A publication failure leaves no partial output or temporary file. |

The actual saved calendar and metadata examples are in actual-files/. The Unicode example is original synthetic text and contains no real patient, payer or account information.

The raw unittest record is semantics-v1.stderr, SHA256 c85d0f2954b85c23e463da8b72b2dfdc885f454566d85098c78e7f8c804420d3. Its standard diagnostic stream records 18 tests, 18 pass, 0 failure; stdout is empty. Subtests exercise multiple input values, but are not presented as a larger independent test count. Runtime was Python 3.14.4 and the standard library; no package or browser was installed or used in this lane.

## Format reference and interpretation

The primary [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545.html) body was retrieved 2026-10-08. Sections 3.1 and 3.3.11 support CRLF, octet folding and TEXT encoding; section 3.2.19 excludes TZID from DATE; section 3.6.1 gives a DATE event without an end/duration a one-day duration; section 3.8.7.2 requires UTC DTSTAMP. The export-time choice is the product's declared handoff contract. No RFC example, prose passage or code was copied into the fixtures.

The synthetic source's deadlines are treated as recorded input. This review does not validate payer rules, clinical decisions or the report engine's deadline calculations. A stable UID does not prove calendar-client deduplication, updates or cancellation. The snapshot is an observed content comparison, without a writer lock or authentication claim. The independent Mac receiver owns actual current-filter, pending/late-response, keyboard, 390px and browser-download acceptance.

## Preserved state and integration

The author's earlier blank-clinic counterexample remains in its producer packet; this independent lane receives its frozen corrected v2 without relabeling or rerunning that historical failure. No new product or receiving failure occurred in this run.

No source, engine/data/report rule, saved staff state, deployment, external calendar or payer/account action was changed by this review. The source/fixture files, frozen specifications, raw result and actual output examples are manifested. The final native result and exact original review-claim closure are added as a later receipt, outside the self-referential content manifest.

Repeat from this directory with:

```sh
python3 -B test_semantics_v1.py
```
