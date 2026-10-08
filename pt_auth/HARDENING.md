# Hardening review: pt_auth (2026-09-29)

Goal: trustworthy enough for a front-desk person to run on a real weekly schedule export.
All tests referenced below are in `tests/test_hardening.py` unless noted. Run `python -m pytest -q pt_auth`.

## README promises vs. code

| # | README promise | Before | Now |
|---|---|---|---|
| 1 | Ingests `schedule.csv`, `authorizations.csv`, `payers.csv`, `patients.csv` | Only exact machine-style files: crashed on comma-only rows, trailing commas, "Visit Date" headers, cp1252 files, date+time values | Yes. Tolerant loaders, and anything uninterpretable stops the run with `file line N: column 'value': reason` |
| 2 | Each **non-cancelled** visit is assigned to the approved auth covering its date with capacity | Only statuses spelled exactly `completed`/`scheduled` counted; "Checked Out", "Arrived" etc. were **silently dropped** (visits used undercounted) | Yes. Status synonyms normalized; unknown statuses rejected |
| 3 | Completed visits assigned first, then scheduled in date order | Yes | Yes |
| 4 | Visits used / scheduled / remaining / remaining after scheduled / days left | A visit appearing twice (appended weekly exports) was **counted twice** | Yes. Deduped by `visit_id`, last row wins |
| 5 | Visits used vs. authorized per auth | Two rows with the same `auth_no` shared one ledger: a renewal that reused the number merged both periods' visits into one capacity | Yes. Overlapping same-number rows = amendment (last row wins); separate windows = separate periods |
| 6 | Expiry dates: visits after end date are uncovered; auth covers its end date | Yes (inclusive end; auth ending today is still live) | Yes, now with regression tests |
| 7 | `UNCOVERED_VISIT` by date **or** count; P1 within 7 days else P2 | Yes | Yes |
| 8 | `UNAUTHORIZED_DONE` P1 | Yes | Yes |
| 9 | `REAUTH_BY_VISITS` / `REAUTH_BY_DATE` when threshold reached **and visits continue** | `REAUTH_BY_VISITS` fired with no future visits (discharged patients) | Yes, both require continuing visits |
| 10 | Re-auth lead time: submit-by = min(auth end, exhausting visit) - turnaround; P1 once passed | Yes | Yes |
| 11 | Auths with a successor (approved/pending) are not re-flagged | An **older, longer** overlapping auth counted as a "successor" and suppressed the current auth's re-auth alert | Yes. A successor must start no earlier and end later |
| 12 | `PENDING_FOLLOWUP` P2; P1 within 2 days | Yes | Yes |
| 13 | `ANNUAL_LIMIT` P3; P2 if scheduled exceeds cap | Yes (calendar year; "near" = within 3 visits) | Yes. See open items |
| 14 | Payer-specific rules table drives everything | A blank `requires_auth` cell meant "no auth required" (payer silently never flagged); blank `counts_evals` meant "evals don't count"; a payer id missing from `payers.csv` skipped all re-auth checks silently; `pay-comm1` vs `PAY-COMM1` never matched | Yes. Blank `requires_auth` rejected; blank `counts_evals` = Y (conservative); new `UNKNOWN_PAYER` (P2) item; ids normalized |
| 15 | Self-pay and no-auth payers never flagged | Yes for auth rules. `ANNUAL_LIMIT` can still fire if such a payer has a cap | Unchanged, by design; README wording clarified |
| 16 | Evals excluded when payer says so | Only the exact string `eval`; "Initial Evaluation" counted as a treatment | Yes. Visit-type synonyms normalized |
| 17 | Outputs: worklist.csv, ledger.csv, digest.html, summary.json, audit.jsonl | Digest showed `0 / -` for a zero-visit auth | Yes |
| 18 | Evidence points to source rows | Row numbers drifted after blank lines in the file | Yes. Real file line numbers |
| 19 | Answer-key verification (seed 5 in tests; seeds 1, 2, 3, 99, 1234 manually) | Pass | Pass (re-checked all six after the changes; sample-data worklist is identical) |

## Defects found (each has a test that failed before the fix)

Loaders (`ptauth/data.py`)
- `test_comma_only_trailing_rows_are_skipped`: Excel's `,,,,,,,` trailing rows crashed the run.
- `test_source_row_points_at_file_line_after_blank_lines`: evidence row numbers were wrong after blank lines.
- `test_extra_trailing_field_does_not_crash`: a trailing comma on a row crashed (`None` header key).
- `test_human_headers_are_accepted`: "Visit Date" style headers raised `KeyError`.
- `test_cp1252_export_loads`: Excel "CSV" (cp1252) with an accented name crashed.
- `test_common_export_date_formats_parse[...]` (6 failing cases): `9/28/2026 10:00 AM`, `09/28/2026 14:30`, `9/28/2026 2:30:00 PM`, `2026-09-28T09:15:00`, `2026-09-28 09:15` and `2026/09/28` crashed or misparsed.
- `test_aware_timestamp_uses_clinic_local_date`: UTC `...Z` timestamps crashed; they now convert to the clinic's local date (`data.CLINIC_TZ`, default = this machine's zone), so a 6:30 PM visit is not moved to the next day.
- `test_day_first_date_is_rejected_with_file_and_line`: `28/09/2026` gave a bare "month must be in 1..12" with no file/line.
- `test_visit_status_synonyms_are_normalized`, `test_unknown_visit_status_is_rejected_not_dropped`: non-exact statuses were silently ignored.
- `test_visit_type_synonyms_are_normalized`: "Initial Evaluation" / "Re-Evaluation" were not recognized.
- `test_ids_are_normalized_across_files`: case/whitespace/leading-zero id differences between files made covered visits look uncovered.
- `test_blank_visits_authorized_is_rejected`: blank count silently became 0 authorized visits.
- `test_auth_end_before_start_is_rejected`: swapped dates were accepted.
- `test_auth_status_synonyms_and_blank_status`: "Submitted"/"In Review" were ignored (not treated as pending); a blank status was silently treated as **approved**.
- `test_payer_flags_fail_safe`: blank payer flags defaulted to the unsafe side.

Engine (`ptauth/engine.py`)
- `test_duplicate_visit_rows_from_appended_exports_count_once`
- `test_renewal_reusing_auth_number_keeps_separate_periods`
- `test_older_longer_auth_does_not_suppress_reauth_of_current_auth`
- `test_reauth_by_visits_requires_continuing_visits`
- `test_unknown_payer_is_flagged_not_silently_skipped`

Output / CLI
- `test_digest_shows_zero_visits_authorized` (`ptauth/report.py`)
- `test_cli_reports_bad_input_without_traceback`: bad input now prints `ERROR: schedule.csv line 2: ...` and exits 2 instead of a traceback. The web UI's `/api/run` returns the same message as a 400.

Guard tests that already passed (kept as regressions): BOM header, ISO / `M/D/YYYY` / `M/D/YY` dates, leap day (`2/29/2028` end date inclusive), cancelled/no-show never consume an auth, zero-visit auth leaves every visit uncovered at P1, visit on the auth end date is covered and the next day is not, an auth ending today is still live, amended auth row supersedes the earlier one.

## Still open (not fixed; decide with the clinic)

- **Stale "scheduled" rows in the past** (never checked out or cancelled) still consume auth capacity, but they are not surfaced. They could be undocumented or unbilled visits and deserve their own worklist code.
- **Duplicate auth numbers** are resolved by a heuristic (overlapping = amendment, later row wins). Nothing tells staff this happened; a "data warnings" panel in the digest/UI would help.
- **Day-first dates** (`DD/MM/YYYY`) are rejected, not auto-detected. This is deliberate, because detection is ambiguous.
- **Numeric ids** drop leading zeros (`001234` = `1234`) to survive Excel. That would merge two genuinely different patients whose ids differ only by leading zeros.
- **ANNUAL_LIMIT** uses the calendar year (no plan/benefit-year option), counts evals even when `counts_evals = N`, includes stale scheduled rows, and can fire for no-auth payers that have a cap.
- **Payer threshold cells** (`reauth_visits_before`, `reauth_days_before`, `turnaround_days`) still default to 0 when blank.
- **Name mismatches** cannot be detected: the schedule has no name column, and duplicate `patient_id` rows in `patients.csv` resolve last-wins.
- A patient whose insurance changed mid-episode is correctly shown as uncovered, but the tool doesn't hint that it's a payer mismatch.
- The status/synonym lists are generic. Map the clinic's EMR vocabulary (WebPT, Raintree, etc.) on the first real de-identified export.
- The original review ran on Python 3.14. The 2026-10-08 clinic-timezone contribution also runs the inherited PT suite on Python 3.12; the configured CI matrix covers 3.10 and 3.12.

## Clinic timezone selection (2026-10-08)

The same authored UTC appointment is uncovered on a UTC host and covered on
a Pacific host when the authorization ends on the prior calendar day. This
reproduced through the real CLI on source
`58d18344b1ba81e704a22096d05ead2f5d5cdddd`; neither report identified its zone.

Named-zone selection now binds visit and authorization timestamp conversion
to one per-run `ZoneInfo`, without changing the process or module default.
The selected zone supplies fallback "today" and is recorded in the summary,
audit, CLI, browser, and printable digest. Cached summaries for another or
unrecorded zone are rebuilt for their same as-of date. Host-local mode
refreshes once at server startup because its label alone cannot establish
which host interpreted the input.

`tests/test_clinic_timezone.py` covers host-independent named-zone decisions,
historical offsets, date-only/naive compatibility, separate concurrent runs,
invalid-zone refusal before output changes or startup, and actual local HTTP
and optional Chromium consumption. These are synthetic software controls;
they do not establish a real clinic's rules or accuracy.
