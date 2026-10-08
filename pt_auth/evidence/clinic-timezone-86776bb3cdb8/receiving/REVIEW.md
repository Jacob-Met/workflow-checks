# Independent receiving: PT clinic timezone

**Accepted source:** `2946f7754c921a9e670ba48d325d634665f50e94`.
**Base and checked live main:** `58d18344b1ba81e704a22096d05ead2f5d5cdddd`.

The candidate resolves the documented missing clinic-timezone option and passes
the independent native controls described below. No remaining actionable defect
was found in the inspected changes. The author may add the checked independent
test and qualification records without changing the five qualified product files.

## Demonstrated baseline behavior

An authored synthetic UTC visit at `2026-09-29T01:30:00Z` has a one-day,
date-only authorization for September 28. The actual original CLI, with the same
explicit September 27 as-of date and no timezone option, reported one uncovered
visit and one P1 item under a UTC host setting. Under a Pacific host setting it
reported zero uncovered visits and zero P1 items. Neither summary identified the
date-conversion timezone. `baseline-host-drift.json` retains the runtime,
source identity, CLI output, counts, ledger and uncovered rows from both runs.

A separate actual serve-CLI control reproduced a consequential cache problem:
an output produced on the UTC host and then served on a Pacific host continued
to show the UTC interpretation. The final independent test fails on main at the
wrong uncovered count (`1` instead of `0`), not at an unrecognized new argument.
The baseline process exited 1 with one failed and 13 deselected tests.

## Receiving feedback incorporated before the first freeze

Initial source review identified two startup paths that direct `App` tests could
miss: regenerating a cached report must retain its previously selected as-of
date, and a generic host-local label cannot establish equivalence across hosts.
The author incorporated the agreed policy before freezing the source: preserve
the reviewed date when rebuilding; refresh local-mode cache once per App
startup; thereafter reuse it. Matching named-zone caches remain reusable across
host changes. The native serve controls verify this implemented behavior.

## Independent native results

The final `test_receiving_timezone.py` passed **14 tests in 1.57 seconds** on
Python 3.12.14. These tests launch the actual `python -m ptauth run` and
`python -m ptauth serve` entry points in child processes and make real loopback
HTTP requests. They do not replace the application entry points or date loaders.

The controls cover:

- Sixteen independently authored date expectations around spring and autumn
  Pacific transitions, including midnight on each side of a transition,
  repeated fall-back hours, and naive/date-only values. Each synthetic visit
  has its own one-day date-only authorization, so coverage checks the resulting
  date against an input oracle. The corpus passes on UTC and UTC+14 hosts.
- Kathmandu's 45-minute offset at the exact second before and at midnight,
  under UTC and Pacific host settings.
- Aware authorization endpoints converted into the same clinic day as visits:
  the end day remains inclusive, while the following written date is uncovered.
- Actual server startup with a different named zone, missing provenance, and
  a host-local cache moved to another host setting. All retain the reviewed
  as-of date, recalculate coverage once and reuse subsequent reads. HTTP rerun
  and digest retrieval retain the server-selected zone.
- Reuse of a matching named-zone cache after a host change, without an extra
  audit event.
- Invalid-zone refusal before absent input/output directories are created and
  before attempting to bind an already occupied port.
- Real unavailable-database refusal for both CLI modes. Child processes run
  with `-S` and an empty `PYTHONTZPATH`, disabling site-package fallback and
  system timezone search; no missing-zone function is mocked.
- Actual fallback-today reports at UTC-12 and UTC+14, checked against independent
  UTC arithmetic and bounded for a possible midnight crossing during execution.

Only the host-local cache-move case skips on platforms without `time.tzset`;
the named-zone controls remain collected. The test locates the repository root
correctly when copied unchanged to `pt_auth/tests/test_receiving_timezone.py`.
An optional `PT_RECEIVING_SOURCE` environment variable selects an isolated
checkout for comparative receiving runs.

## Source review and preservation

All 132 tracked source entries in the candidate match their frozen Git blob IDs
and executable modes after testing, and the receiver checkout remains clean.
The eight changed paths are the five CLI/data/report/web/UI files, two existing
documents and the author's new tests. The core rule engine, synthetic generator
and other product directories are unchanged. `source-preservation.json` records
the changed paths and exact hashes of the five product files.

Named-zone resolution precedes input/output side effects. One resolved zone is
passed to both timestamp-bearing loaders; existing naive/date-only handling and
the legacy module default remain available. The new keyword-only arguments
preserve existing call shapes. Summary, audit, CLI and HTML provenance agree;
the HTML paths escape the label or set it as text. Core coverage and priority
rules are not changed by this contribution.

Python's primary [zoneinfo documentation](https://docs.python.org/3/library/zoneinfo.html)
describes IANA transitions and system/`tzdata` lookup. The
[datetime documentation](https://docs.python.org/3/library/datetime.html#datetime.datetime.astimezone)
describes conversion of aware instants. The tests retain explicit expected
calendar dates rather than deriving their authorization oracle through the
candidate's conversion function.

This receiver ran the focused independent suite and its meaningful baseline
negative control. The author's inherited-suite and Chromium qualification are
separate evidence. All records and HTTP servers used authored synthetic data;
no real clinic service was contacted.

## Evidence

The candidate and baseline logs have adjacent `-receipt.json` files containing
the actual commands, source selections, exit statuses, timing and SHA256 values.
`candidate-source-manifest.json` pins the complete candidate tree and the final
independent test. `baseline-host-drift-inputs/` retains the four original CSV
inputs. `file-hashes.json` pins the receiving packet's files.
