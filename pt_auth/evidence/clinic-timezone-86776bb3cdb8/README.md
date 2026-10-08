# Clinic calendar dates that travel with the export

## Result

The qualified source is `5222ac0e38d2b48631c527770afa3d6d951e0a6a`, based on
`58d18344b1ba81e704a22096d05ead2f5d5cdddd` in
[Jacob-Met/workflow-checks](https://github.com/Jacob-Met/workflow-checks).
The complete PT suite passes **88 tests**, including 14 independently authored
receiving cases and an actual Chromium UI/digest check. The repository's other
configured groups pass 41 freight tests and 34 utility tests on their unchanged
source. This directory is an evidence-only addition after source qualification.

The first source accepted by the independent receiver was
`2946f7754c921a9e670ba48d325d634665f50e94`. The next commit adds only the
receiver's checked test file; all five product files are unchanged. The final
combined run therefore qualifies the maintained 88-test collection at its
exact source commit. `source-receipt.json` contains the nine changed source,
test and existing documentation file hashes, Git blob IDs, and runtime data.

## The observed need

The project's existing `pt_auth/HARDENING.md` explicitly recorded the missing
clinic-timezone option. Offset-bearing appointment and authorization timestamps
were converted using the machine's local zone, with no CLI selection or report
provenance.

The original CLI was run twice against the same four authored synthetic CSVs.
A visit at `2026-09-29T01:30:00Z` and an authorization ending September 28
produce these results for the same explicit September 27 as-of date:

| Machine timezone | Uncovered scheduled visits | Visits scheduled in the authorization | Worklist |
| --- | ---: | ---: | --- |
| UTC | 1 | 0 | One P1 item |
| America/Los_Angeles | 0 | 1 | Empty |

Neither original report records its date-conversion zone.
`baseline-host-drift.json` preserves the actual CLI commands, exit status,
output and counts; `authored-input/` retains the exact CSVs. These are
software counterexamples, not observations of clinic activity.

The receiver separately reproduced a stale cached interpretation through the
actual `serve` CLI: a report produced under UTC and then served under a Pacific
host setting continued to report one uncovered visit. Its meaningful baseline
negative control fails on the wrong coverage count, without using a missing
new argument. The before/after evidence is retained under `receiving/`.

## Behavior and decisions

Both `run` and `serve` now accept `--clinic-timezone IANA_ZONE`. One resolved
`ZoneInfo` is passed to both timestamp-bearing loaders in each report. The
choice applies before calendar dates are extracted, so visits and authorization
windows use the same clinic day. The implementation does not change process
timezone state or the existing module default.

Historical daylight-saving rules apply to aware instants. Written dates and
timestamps without offsets retain their written calendar date. An explicit
as-of date or a sample's `expected.json` date also retains its meaning; when
neither exists, fallback "today" comes from the selected zone. One zone applies
to the input batch.

The chosen zone appears in CLI output, the browser, the printable digest,
`summary.json`, and run audit events. A cached report for a different or
unrecorded zone is rebuilt for its previously selected as-of date. A matching
named-zone cache can be reused across host changes. With no option, conversion
continues to use system-local time; that mode refreshes cached output once when
the server starts because a generic local label cannot establish host identity.
Later reads reuse the refreshed report without appending another run event.

Invalid or unavailable zones fail before creating output directories, generating
synthetic inputs, binding a server port, or replacing report/audit bytes. The
message identifies the requested zone and explains the optional `tzdata`
database source. Original payer/priority/coverage algorithms, synthetic
generation rules, CSV export columns, and the other two programs are unchanged.

## Qualification

| Check | Source | Result | Evidence |
| --- | --- | --- | --- |
| Existing PT suite before changes | Base `58d1834` | 55 passed | Recorded in `source-receipt.json` |
| Exact final 19 author controls on original source | Base `58d1834` | 19 failed | `baseline-author-tests.log` |
| PT suite with first complete feature, including actual browser | `2946f77` | 74 passed | `candidate-tests.log` |
| Independent actual serve cache-move negative control | Base `58d1834` | 1 failed, 13 deselected | `receiving/baseline-cache-control.log` and receipt |
| Independent CLI/HTTP/date controls | `2946f77` | 14 passed | `receiving/candidate-independent.log` and receipt |
| Final PT suite, including both authors' controls and actual browser | `5222ac0` | 88 passed in 4.13 seconds | `final-tests.log` |
| Existing freight and utility groups | Unchanged subtrees at `2946f77` and `5222ac0` | 41 passed / 34 passed | `other-project-gates.json` |
| Severe-error Ruff subset (`E9,F63,F7,F82`) | `5222ac0` | Passed | `severe-lint.log` |

The 19 author failures show that the new option and API were unavailable on
main. Its optional browser test therefore fails before browser startup; that
row is not a claim of a baseline browser run. The concrete old CLI and actual
server coverage failures above establish the user-facing need.

The final browser control uses a fresh Chromium context and permits only its
disposable loopback server. It verifies the visible Pacific zone, zero uncovered
visits, one scheduled visit in the authorization, a rerun for September 28, and
the printable digest's matching zone. Its actual output records Chromium
153.0.8010.0 and no unhandled requests. No existing browser profile or server
was used.

Independent receiving adds real CLI/server subprocesses, spring/autumn midnight
and repeated-hour expectations, Kathmandu's 45-minute offset, inclusive
authorization end dates, timezone cache refresh and reuse, invalid-zone priority
over an occupied port, real missing-database child processes, and actual
fallback-today checks at UTC-12 and UTC+14. Only the host-local cache-move case
skips on platforms without `time.tzset`; it executed in this qualification.

`receiving/REVIEW.md` documents the receiver's source acceptance and bounds.
`receiving/file-hashes.json` preserves the original packet hashes. The retained
test snapshot has a `.py.txt` suffix to keep it outside pytest collection;
`receiving/artifact-paths.json` records that filename mapping. Its bytes match
the maintained `pt_auth/tests/test_receiving_timezone.py` exactly. Raw logs
retain their original whitespace. Existing CRLF source formatting is preserved.

## Reproduce

Use Python 3.10+ and pytest. The recorded native run used Python 3.12.14,
pytest 9.1.1, Playwright 1.63.0, Node 24.19.0, and system IANA data 2025b.
The receipt pins the used timezone rule files. Named-zone results depend on the
installed rule data; this contribution does not certify identity across future
rule-database revisions.

From the repository root:

```sh
PTAUTH_TEST_CHROME=/absolute/path/to/chromium python -B -m pytest -q -s pt_auth
git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --check
```

The optional browser control also needs Playwright in the test environment.
Without `PTAUTH_TEST_CHROME` it skips explicitly. The project's configured CI
runs pytest separately in `freight_packets`, `pt_auth`, and `utility_watch`.
For an independent comparison checkout, set `PT_RECEIVING_SOURCE` to that
repository root when executing `test_receiving_timezone.py`.

Primary behavior references are the project's pinned original hardening note
and Python's [zoneinfo documentation](https://docs.python.org/3/library/zoneinfo.html).
All inputs are authored synthetic records with placeholder payer rules. The
checks establish software date conversion and report behavior; no real patient,
clinic, payer, production deployment, or clinical accuracy was evaluated.
