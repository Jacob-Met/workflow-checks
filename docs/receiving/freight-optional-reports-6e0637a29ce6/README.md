# Freight optional CSV refresh: source and receiving

Owner: the continuing four-worker HAMON team, `6e0637a29ce6 /
portfolio_engineer`. Independent consumer review: `research_delivery`.

## The observed inconsistency

At original main `86906f285cbef549b46677d9ad7c45d1ef4a9856`, two real CLI
runs using 24 synthetic loads and seed 7 both returned success. Between the
runs, the optional fines schedule was removed. The second summary correctly
reported no fines or settlements, while the existing download method still
returned the first run's 18 fine rows and 25 settlement rows byte for byte.
`original-witness.json` retains both CLI results and the exact stale CSVs.

The candidate moves the existing two CSV writes outside the optional schedule
branch. Their inputs remain the current `fines` and `settlements` lists, so a
successful run without the schedule produces normal headers and zero data
rows. All calculation expressions and serialized columns remain unchanged.
The production change is confined to `freightpkt/pipeline.py`; its original
CRLF format is retained. The exact inverse restores the original source.

Original pipeline SHA-256:
`e2c034fdc0032d47942a1e732c0737e603109678bac09ad17638c461ad23a8c9`.
Reviewed candidate SHA-256:
`c68d1ea8d853e9e0a05117e226e722663aac1f43ecd14db1f39c87e6a1dee627`.

## Maintained checks

The three new tests fail against the original and pass against the candidate.
They cover a fresh output directory without a schedule and actual CLI
remove/restore sequences for seed 7 with 24 loads and seed 99 with 40 loads.
The complete Freight suite passes **128 tests** on Python 3.12.14 with
pytest 8.3.5. The final three-test rerun and changed-test Ruff check pass after
test-only import formatting and an explicit `subprocess.run(check=False)`.
The original maintained test and its complete failed output remain retained.

`author-qualification.json` records these results, the initial formatting
diagnostics, the CRLF-aware whitespace check and exact inverse verification.
No dependency declaration or workflow was changed to obtain these results.

## Independent actual CLI and HTTP receiving

The reviewer froze the contract before inspecting the candidate and chose a
different fixture: 13 synthetic loads, seed 19. The original course passes
**17 of 23** checks; the candidate passes **23 of 23**.

The original serves four stale fine rows and 13 stale settlement rows after
schedule removal, and returns HTTP 404 for both downloads on a fresh run
without a schedule. The candidate serves exact 102-byte and 99-byte
header-only CSVs with HTTP 200 for fresh, reused and repeated no-schedule
runs. Scheduled output and normalized summary match the original exactly;
restoring the schedule restores those exact original CSVs.

The separate controls retain decision-file bytes with the expected stale
and current review views, append the audit without erasing its prefix, leave
HTTP reads free of audit writes, and preserve unrelated outputs, packet
bytes, a saved sentinel and all source-package bytes. The `independent/`
directory preserves the contract, receiver, complete original/candidate
receipts, stderr streams and explicit approval unchanged.

To run that receiver against this checkout, choose a new receiving directory:

```sh
python3 -I -B docs/receiving/freight-optional-reports-6e0637a29ce6/independent/review_freight_downloads.py.txt freight_packets /tmp/freight-optional-receiving
```

The script refuses an existing receiving directory. It uses local temporary
synthetic data, isolated CLI children and the existing localhost HTTP handler.
The `.py.txt` suffix keeps historical receiving code outside broad test/lint
discovery while preserving its exact bytes.

## Later parent and delivery boundaries

Current publication parent `df5f6fdd32ceb281212db626a200081aa78cdf51` adds
three separately reviewed Utility Watch files. Every Freight source/test file
and both workflow definitions are unchanged from the execution parent;
`current-parent-fit.json` records the exact comparison. Those incoming Utility
changes are preserved without attributing the earlier Freight tests to them.

This repair covers successful-run output consistency. It does not provide
transactional publication across all pipeline files, new payment or reviewer
authority, graphical browser receiving, hosted CI or installed deployment.
The separate CSV-admission, fine-rate, packet renderer and saved-review owners
retain their scopes. Source publication uses a skip-marked branch under the
user's no-Actions requirement; no workflow or Pages change accompanies it.
