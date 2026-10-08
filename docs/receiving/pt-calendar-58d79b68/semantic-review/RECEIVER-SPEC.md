# Independent PT calendar semantics receiver

Reviewer: chatgpt:58d79b68c9e4:root. Source owner: product_work, workflow-checks issue 27. This review reads the author's frozen contract and source hash manifest before implementation or maintained tests. It does not edit source or receive the browser UI; mac_estate owns that independent browser lane.

Source offered for review: a68a667f3610153618c6cc8952c72abe980d89aa, exact native d75fb908a9893fd40b21112f62af16d32027bbe1, tree 94074bd3d39705fced23629038ab79057e943aff, parent 9e931fa9f42033bf2368f7149684fb5631345715. Formatter SHA256 89751f1de5548ced34a59c296d0edf1eda06a38bdb935be3e7c3c8b2ae5d55c0. The earlier author's blank-clinic negative remains historical; this review starts with its declared v2.

## Frozen expectations

1. A parsed calendar must contain exactly the selected eligible work items. Their DTSTART values must be the recorded submit_by dates, without a replacement from appointment/auth-end/as-of/current time. Each is a one-day DATE event. No time conversion, TZID on DATE, appointment, attendee, organizer, alarm or recurrence is introduced.
2. A leap day, both sides of a daylight-saving transition, a year boundary and different process time zones must retain the exact dates. Malformed nonempty dates must not become valid-looking events. Undated rows remain clearly excluded. Unknown or malformed status must not silently become eligible work.
3. Open/default-open and submitted items are eligible when dated. Approved and n/a items are excluded. Exclusion accounting must reconcile selected and eligible rows. Blank native clinic/name values must not invent an identity or make an otherwise supported report unusable.
4. UID values must remain stable across repeated exports, report ordering/subsetting, changed submit_by and changed export time for the same declared key/clinic/auth-end/zone identity. Different declared identity components must not collapse together. This verifies transformations instead of copying the hash implementation.
5. Export timestamp must represent the current UTC export, independent of report/as-of time. Calendar import/update/deduplication/cancellation behavior is outside this review.
6. Independently unfold and parse actual emitted bytes. Verify CRLF, valid UTF-8, physical lines no longer than 75 octets, and correct TEXT round-trip of comma, semicolon, backslash, newlines and multibyte characters at folding boundaries. An input containing apparent component/property lines must remain text and cannot create another event or active calendar property.
7. Relevant original work-item identity, recorded clinic-zone/status, source evidence, reasons and checklist content must survive as inspectable text. The source report/state objects and files remain unchanged. The calendar must not manufacture approval, certainty or a recalculated rule.
8. Actual saved-report CLI export must use the same semantics. A valid synthetic file creates a readable calendar; an existing destination must remain byte-identical, and invalid input must not produce a partial/misleading artifact. No report generation or staff-state write is accepted as part of export.
9. Snapshot binding is a comparison of observed content, not a file lock or authentication. A selected key absent from the observed report must refuse clearly. Extra unrelated projection fields must not change event meaning. Browser pending/late-response and current-filter behavior are accepted only by Mac's actual UI receiver.

The adapter may learn public function names and report field shape after this freeze. Fixtures and calendar parsing are independently authored from these expectations; no author test is used as an oracle. Consequential failures are preserved against the original source pins before any correction. A correction receives only the affected controls and necessary boundary checks.

## Primary format source

RFC 5545: https://www.rfc-editor.org/rfc/rfc5545.html, sections 3.1, 3.2.19, 3.3.4, 3.3.11, 3.6.1, 3.8.4.7 and 3.8.7.2. The primary body was retrieved 2026-10-08. It specifies CRLF content lines, octet-based folding, DATE semantics without TZID, TEXT escaping and UTC DTSTAMP. A DATE event without DTEND or DURATION lasts one day. No reference prose, example data or code is copied into fixtures.

No real patient data, external calendar import, payer/account action, new package, live service change or production source edit is part of this receiver.
