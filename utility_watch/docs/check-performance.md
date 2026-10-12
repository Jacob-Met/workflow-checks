# Measuring Utility Watch checks

The checker derives each known bill's service month once per call. It also
normalizes usage-unit names once per non-unit-account bill and computes each
evaluated bill's comparison-window boundaries once. These values are discarded
after the call. Editing a bill's period or unit before another call is therefore
reflected in that next review.

Derived values use object identity, because exported bill IDs can repeat across
accounts and across distinct records. Historical comparisons keep their original
iteration order and apply the existing duplicate exclusions as those exclusions
are discovered. The change does not alter billing rules, findings, evidence,
payment-queue eligibility or the advisory approval gate.

## Run an equivalent benchmark

With Python 3.10+ and no third-party dependencies, run from `utility_watch`:

```sh
python tools/benchmark_checks.py --data sample_data --as-of 2026-09-28 --eval-from 2026-03-01 --repeats 5
```

The JSON output separates the already-loaded `check()` median from the full
`python -m uwatch run` median. The latter includes a fresh Python process, CSV
loading, checking and writing all reports. Every command writes to a new private
temporary directory that is removed when the measurement ends. Existing reports
are not used as destinations. The tool verifies unchanged input hashes and
identical result/output hashes across repeats. To compare source revisions, use
the same benchmark script, Python executable, inputs, dates and repeat count in
separate checkouts, and run them sequentially.

`check_peak_allocated_bytes` is a separate `tracemalloc` measurement with inputs
already loaded; tracing is disabled during timings. It includes checker output
allocations, not the full process memory. The derived-value dictionaries use
additional memory proportional to the number of loaded bills. Historical scans
are still performed; this change reduces repeated computation rather than
changing which records are compared.

## Qualification on 2026-10-12

Baseline: `66030b1f930906d0b42fa46fc0a74c06678ec964`. Measurements used CPython
3.12.14 on a Linux cloud workspace. The larger portfolio consists of 30 copies of
the shipped synthetic sample with distinct account/property identities; bill and
invoice IDs deliberately remain local to each account. It is not client data.

| Input | Samples | Checker before → after | Full CLI before → after | Checker peak allocations before → after |
|---|---:|---:|---:|---:|
| Shipped sample: 31 accounts, 274 bills | 5 | 20.35 → 2.11 ms | 102.68 → 66.27 ms | 46,143 → 72,943 bytes |
| Synthetic portfolio: 930 accounts, 8,220 bills | 7 | 677.18 → 94.20 ms | 1,105.68 → 403.13 ms | 2,191,297 → 3,011,968 bytes |

These are measured local medians, not latency promises. Service-month
calculations on the shipped sample fell from 12,830 to 274. The full command
improved by 1.55× and 2.74× for these two inputs respectively; CSV parsing,
report output and process startup remain part of its cost.

Forty actual baseline/candidate CLI invocations, including genuine `python -O`
runs, covered the shipped sample, three other generated seeds, a 120-month
history, the larger portfolio, nonfinite usage/payment amounts, malformed dates
and reversed periods. Successes produced the same six output files byte for
byte. Refusals retained exit status 2 and identical diagnostics while preserving
all six prior report/audit files and every input file. The candidate suite passed
165 tests and 81 subtests in both normal and optimized Python.

The focused regression file also exercises repeated exported IDs, period/unit
edits between calls, recovery after those edits, input-object preservation and
unknown-account handling. Run it independently with:

```sh
python -m unittest discover -s tests -p test_check_derived_values.py -v
```

Independent team review compared 80 further varied corpora against the original
checker, then reviewed the same mutable objects again. Shifted periods, usage
units and values, amounts, unknown accounts, repeated IDs, thresholds, date
windows and input ordering retained exact flag, exception, queue and naive-hit
results without mutating input objects. All 80 initial and 80 repeated comparisons
passed. The independent result digest was
`7a75c47fc7e6006dcd6d3d9773b6f48db3e370a5a2c41812ac6855e40446e64a`;
the approved checker SHA-256 was
`31d8c0f3162af10baa22a3b7fe24fe0635b3de11048cbad42a119c3542690767`.
