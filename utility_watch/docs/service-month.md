# Utility bill service-month calculation

Utility Watch assigns each inclusive billing period to the calendar month with
the most service days. Equal counts choose the latest month. For an ordinary
two-month cycle this is the ending month; if a longer period ties among several
full interior months, the latest of those interior months wins.

The calculation now inspects the two partial endpoints and at most the latest
two full interior months. Every consecutive pair of Gregorian months contains a
31-day month, so these candidates retain the latest possible full-month maximum.
The work is bounded even for long periods. A period entirely within one month
returns that month directly. It never constructs the following month or adds a
day to the final endpoint, so December 9999 works within Python's date range.

`Bill` remains mutable and `month` is recomputed on every access. Updating a
period does not leave a stale cached service month. Reversed periods raise
`ValueError`; CSV loading already rejects those periods before the property is
used. Existing billing, comparison, payment-queue and report rules are unchanged.

## Use

No new option or dependency is needed. From `utility_watch/`:

```sh
python -m uwatch run --data sample_data --out out --as-of 2026-09-28
```

Open `out/report.html` or read the usual CSV and JSON outputs. Sample data is
fictional. The command creates an advisory payment queue; it does not pay bills.

## Verification, 2026-10-12

Receiving base: `ec92e0b071d8cef9c314cece9bff6dbbe9a3382d`.
The existing engine edit is limited to a standard-library `calendar` import and
`Bill.month`. Every other engine byte, including CRLF line endings, is preserved.
The candidate engine's SHA-256 is
`a4d3f60bbfb5911a4d4710e3bb15247c8513f255abb65b5505005d2546f3c7b5`.
Coordination and delivery: [issue 96](https://github.com/Jacob-Met/workflow-checks/issues/96).

The receiving base incorporates the separate per-review metadata cache described
in [check performance](check-performance.md). That complete change and its four
files are preserved. This contribution changes the underlying property only;
the checker continues to derive each known bill's month once per review.

- The complete composed Utility Watch suite passes: **172 tests and 3,472 subtests** on
  Python 3.12.14 with pytest 9.1.1.
- The seven added regression methods also pass under `python -O -m unittest`.
  An independent daily-count oracle covers ordinary cycles, every calendar
  month across leap-century controls, 500 seeded longer periods, endpoint and
  interior ties, supported date limits and mutation. The actual CLI accepts a
  fictional final-day bill and produces the six normal outputs.
- The original source fails the date-limit controls, including actual CLI status
  2 for a valid December 9999 bill. Ordinary control cases pass. A preliminary
  test-fixture overflow was fixed before the corrected original and candidate
  comparison; both original logs are retained in the delivery evidence.
- A separate reviewer accepted the exact candidate and **37 additional
  full-month-enumeration cases**, including random multi-millennial periods and
  `date.max`, and reviewed the first 28 complete CLI receipts. The property's
  reviewed bytes remain exact after composition with the later metadata cache.

The timing comparison used byte-identical fictional exports, seven interleaved
original/candidate runs per size, and separate empty output directories. Timings
include Python startup, CSV input, all billing checks and all six output writes.

| Fictional export | Original median | Candidate median | Observed ratio |
| --- | ---: | ---: | ---: |
| 31 accounts, 274 bills | 89.74 ms | 89.37 ms | 1.00x |
| 310 accounts, 2,740 bills | 177.25 ms | 192.95 ms | 0.92x |

All 28 runs exited successfully. For each size, the six final files matched byte
for byte across every original and candidate run; all four input CSVs remained
unchanged. These current-base measurements do not demonstrate an overall CLI
speedup; the larger candidate median was slower in this run. The independent
cache has already removed most repeated month computation. The benefit here is
bounded property work and recovery of valid date-limit inputs. Other date
arithmetic retains its existing contracts.

An earlier 28-run comparison against pre-cache base
`66030b1f930906d0b42fa46fc0a74c06678ec964` measured 100.64 to 85.47 ms for
274 bills and 366.12 to 270.91 ms for 2,740 bills, with exact six-file parity.
Those timings, the earlier 168-test suite and all original receipts are retained
as historical qualification; they are not attributed to this receiving base.

To rerun the regression and maintained suite from `utility_watch/`:

```sh
python -m unittest discover -s tests -p test_service_month.py -v
python -O -m unittest discover -s tests -p test_service_month.py -v
python -m pytest -q
```

GitHub Actions were intentionally skipped for this contribution to preserve the
user's standing execution constraint. Local test and independent receiving
results are the qualification evidence for this increment.
