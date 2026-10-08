# Independent receiving: PT allocated visits (partial browser qualification)

## Disposition

The native projection, actual CLI exports and actual loopback HTTP receiving paths are qualified on the frozen Python sources. The narrow browser successor is **not yet independently qualified**. Keep the source contribution in draft and retain the affected browser gate before merge.

This review was authored independently by runtime_integration, ultra-20b27c2e-20261008. The contract, mixed synthetic fixture, manual facts, baseline oracle and executable probes were frozen at 2026-10-08 15:56:06 UTC before candidate source or author tests were disclosed. Author tests were not read.

## Exact source and scope

Repository: Jacob-Met/workflow-checks, PT issue #43. Primary commit 0418e6308d886d0678ace759a9b984c1d06ac54d, tree 92c62093a0bd4d86e8a518a50cb2869d809cbe63. All 15 baseline inputs were checked against primary Git blobs. The full primary tree and the baseline source closure are included.

Final source pins:

| File | SHA256 | Git blob |
| --- | --- | --- |
| pt_auth/ptauth/allocated.py | 343cecb2e6dcca2accff77cd7b75db57a47b61043ca4e07478824af66a918a1a | cd8a391067639f5f647818ed03a122089b4bad74 |
| pt_auth/ptauth/report.py | 18f0faf298e96e28ac1f2d9d05bb8620bac1005beb1127a10e9816d52c225fcb | ef95e177ee35e32447743ab6867e739be5cbe9ba |
| pt_auth/ptauth/ui.html | 4281cb85515441e9bce852a1f842e5e55ee240228319fc9cfc566e77112bb5ef | af7dadb2755bb587494644d85c26d3ae51abcbe3 |

The original candidate UI was 0ed0e49cbdbb5c0b32b2ff7568c95a1650a8dffc38f51f9dd72d28e50b835cc0. The final UI adds exactly 132 bytes of scoped CSS: a 64rem fixed-layout allocation table and nonwrapping dates. Removing those bytes restores the original UI exactly. All JavaScript and the other 15 copied files remain identical.

The independent audit removes the five declared report additions and the declared UI insertions to recover exact primary bytes. The README is insert-only; all 12 inherited, unowned files remain exact. Engine, data loading, existing web routes, CLI, calendar, staff review and audit behavior were not changed. Subsequent primary main 4f434591c166fc7d3ea7831e52edafe6c23d8843/tree b9935837bf6ee5377a2ed9d1e3b025762502d4a2 was reported and checked by root/producer as containing byte-identical PT source; this worker's executable receiving remains bound to the independently recorded 0418 closure.

## Native receiving evidence

The fixture has 67 raw visits, 15 authorization ledgers, 52 allocated visits, 14 allocated authorization occurrences and seven raw visit clinic groups. It yields 26 used memberships and 26 scheduled memberships. The oracle matched 260 manually specified allocation/provenance facts against actual unchanged baseline engine memberships.

The fixture challenges overlapping amendments, repeated authorization numbers, distinct periods and patient/payer identities, completed-first capacity, inclusive windows, completed future visits and past scheduled visits, over-capacity/outside-window visits, ignored statuses and visit types, unknown payer/missing name, offset timestamps, duplicate rows, blank and multiline clinics, Unicode, quoted newlines, regex punctuation and literal HTML. All data is synthetic.

| Run | Actual outcome |
| --- | --- |
| Primary baseline native | 21 methods: six ordinary controls passed; 15 distinct missing-feature methods failed with 19 failure entries; no errors or skips. |
| Frozen candidate native | 21 methods passed; no failures, errors or skips. |

The native runner invokes the public CLI on mixed and empty fixtures, reads through the real make_handler HTTP server, compares the complete 21-field CSV and summary projection with the independent 52-row oracle, checks full printable digest and escaping, and verifies source/input/report/staff-state/audit custody. Existing worklist, ledger, uncovered-visits and visit-status CSV bytes are identical to baseline. Only disclosed feature keys/generated time are normalized in summary comparisons; only timestamp is normalized in audit comparison.

The accepted native run remains applicable to the CSS successor because both Python sources and the full receiving dependency closure are unchanged. It has not been repeated.

## Browser evidence and the real finding

All browser requests used the actual loopback application and synthetic saved reports. Non-loopback requests were blocked. A known Chrome internal date-input SVG remained blocked and was classified only by its exact observed URL digest; no network exception was enabled.

| Run or diagnostic | Actual outcome |
| --- | --- |
| First baseline browser | 16 groups: two passed, 14 failed; one failure was the receiver's classification of the blocked built-in SVG. |
| Baseline with exact SVG classification | 16 groups: three controls passed, 13 missing-panel groups failed; no errors. |
| Original candidate UI | 16 groups: eight passed, eight failed; no errors. |
| Existing baseline keyboard controls | Native visible-label typeahead and plain Backspace/Delete editing were qualified on existing input/select controls. |
| Final corrected affected replay | Pending: refused before Node/Chrome at the fresh capacity check. |

The original candidate already passed ordinary tabs/calendar access and actual ledger CSV download, the complete allocation panel and provenance, restrictive-filter full CSV download plus full printable digest, missing/nonlist legacy handling, completed empty output, injection/read-only checks, and source/report custody.

The original eight failing groups comprised keyboard/filter/search mechanisms (and the dependent compound-filter group) plus a real narrow-screen readability defect. The existing-control event trace demonstrated the platform behavior before changing the receiver: Home/Arrow keys did not select the expected option, and Meta+A/Control+A/triple-click did not reliably select all input text. The corrected receiver uses the independently proven native visible-label typeahead and plain edit keys; it has **not** yet completed the affected product replay.

At 390px viewport width, the original eight-column allocation table compressed into a 350px region. Recorded dates and headings wrapped to one/few characters per line; ordinary rows were approximately 378px tall, with 52 rows spanning approximately 21,033px. Text was present, but scanning it was impractical. The exact screenshot and geometry are retained. The producer accepted this finding and made only the 132-byte CSS correction. The pending check measures readable date lines, readable font/column geometry, native Tab access to the review region, and access to the rightmost source column where scrolling is necessary. Horizontal overflow itself is not treated as the product goal.

One real preexisting ledger.csv browser download has SHA256 d5f93394e1c69357c470ee759c8a27399fc420dea4423a1cd7ac1d36da0d0a9b in both baseline and candidate.

## Preserved failures and remaining gate

The original browser/probe versions, selector correction, blocked-resource classification, baseline key traces, first label-prefix mistake and correction, source audit's initial list-join receiver error, native pre-execution ENOSPC, screenshots, commands, raw logs and custody receipts are preserved. Corrections to receiver mechanics are not represented as production fixes.

At 2026-10-08 17:09:05 UTC, the queued affected run's wrapper measured 151,523,328 bytes free against its unchanged 268,435,456-byte floor and exited before Node or Chrome. No output directory or browser profile was created. The slot was released. Later read-only file inventory and three file reads through Remote Desktop Commander timed out with MCP error -32603; no file loss or production behavior is inferred from those transport failures.

**Remaining independent gate:** run the current b72c64b4 receiver's affected keyboard/filter groups against the original candidate; then run the readable-layout/access group against the exact 4281cb85 CSS successor, retaining per-run GET/source/custody guards. These are queued, not passed. Root also owns the existing hosted test matrix and final receiving-tree checks. This partial packet does not authorize merge by itself.

## Reproduction and file layout

Run the included extractor with an empty owned directory. It verifies every restored byte and refuses to overwrite a differing file. recorded-evidence.json includes original source copies, synthetic fixtures, all executed probe versions, raw results, reports, downloads, screenshots and correction lineage. evidence-catalog.json provides each path, size and SHA256 without opening the compressed contents.

The approved native device was 0e3d582f-e25b-44b2-8418-9639fc4e4e33. Runtime: /usr/local/bin/python3 (3.13.7), /opt/homebrew/Cellar/node/26.3.0/bin/node (26.3.0), installed Puppeteer at /Users/me/.npm/_npx/4b4c857f6efdfb61/node_modules/puppeteer/lib/puppeteer/puppeteer.js, and /Applications/Google Chrome.app/Contents/MacOS/Google Chrome (154.0.8037.98). No dependencies were installed.

From the extracted root, native reproduction is:
```sh
PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3 -B independent_pt_receiver.py --source baseline --out replay-baseline-native
PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3 -B independent_pt_receiver.py --source candidate --out replay-candidate-native
```

The pending bounded browser commands use fresh output names and the already recorded candidate-native reports:
```sh
PT_REVIEW_GROUPS=3,4,5,6,7,8,9,11,14,15 /opt/homebrew/Cellar/node/26.3.0/bin/node independent_pt_browser.cjs candidate candidate-native replay-original-affected
PT_REVIEW_GROUPS=11,14,15 /opt/homebrew/Cellar/node/26.3.0/bin/node independent_pt_browser.cjs candidate-mobile candidate-native replay-mobile-affected
```

The first pending command intentionally retains the original CSS, so its readability group is expected to retain the source-level negative witness. The second targets the corrected CSS. Expectations are separate from actual recorded outcomes. Respect the unchanged launch floor and serialized browser slot before running either.

There was no use of real patient data, live accounts, installed app data, calendar submission, deployment or real service mutation.
