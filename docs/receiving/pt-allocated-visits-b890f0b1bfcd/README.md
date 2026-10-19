# PT allocated visits — independent browser and print receiving

This is a new receiving packet for [workflow-checks PR #56](https://github.com/Jacob-Met/workflow-checks/pull/56), measured on the exact recovered product source `055c863a9484adb1f6f39f54bf6cce90825bf0ad` (tree `1987ba3b41d4780dcbed19dc8ba9ee1c46dee529`). It qualifies the scoped allocation panel, complete downloads and printable digest against independently authored fictional inputs. No product source was changed.

The original browser run passed **16 of 20 groups**. Three groups reached the browser download event but the receiver could not copy Snap's private `/tmp` download artifact; one desktop screenshot timed out. An explicit additive replay kept the same assertions, used an owned browser-visible home profile/download directory and a 30-second screenshot timeout, and passed **all four affected groups**. Thus all 20 distinct groups have passing evidence, with the original four receiver failures retained. This is not a claim that the first run passed 20/20.

## Source, contract and independence

| Boundary | Exact identity |
| --- | --- |
| Candidate commit | `055c863a9484adb1f6f39f54bf6cce90825bf0ad` |
| Candidate tree | `1987ba3b41d4780dcbed19dc8ba9ee1c46dee529` |
| Actual baseline / legacy producer | `8fe2c9270f487729af9e88f40894e1c4530f2c20` |
| Public contract, before candidate implementation/template access | SHA256 `1bd70cbf71076e9621d0453aef0890b147034d8e91352fbcefd4e207cfba2630` |
| Fixture and manual expected records, frozen before candidate source access | SHA256 `da5f0b3dcfcc3b2d80bcbf84a3edaa17e917ef4a6e4864f80506332bee9ca53b` |
| Original browser driver | SHA256 `c5815d0567a5fadd671419cbb23c3356790a578243cc3e9987010e91835194a7` |
| Four-group additive replay driver | SHA256 `2497ace94a3a50baa1d35e6eaeb62aa5f3a6afc2687c767d2c99fef7ffbc8de0` |

The public-contract cases were written first. The actual unchanged baseline CSV schema, CLI and allocation engine were then read to construct four fictional input files and manual expected allocation membership. The baseline engine agreed with the manual records before candidate implementation was examined. Data loader, engine and CLI Git blobs are identical between the baseline and candidate; their identities and the three changed product files are recorded in `source-verification.json`.

The fixture contains six fictional patients, eight authorization rows and 19 visit identities after duplicate retention. It exercises two separate occurrences sharing an authorization number, an overlapping amendment where the later source row wins, duplicate visit replacement with preserved physical row provenance, an empty approved authorization, a pending authorization, excluded attendance/evaluation rows, and visits outside coverage. The expected allocation has **13 records: six used and seven reserved**. It includes literal markup, accented names, a visit ID containing 254 consecutive R characters, an authorization containing 194 X characters, and a clinic containing 160 Z characters.

Three real CLI invocations produced the ordinary candidate report, a legacy baseline report and a valid candidate report from a header-only schedule. All exited zero. Native preparation matched 143 manually expected record fields. Browser checks then compared 104 visible cells and their 208 primary/detail values against the actual report, including both source-row references.

## Observed behavior

The actual sandbox-enabled Chromium browser used the candidate's unchanged `App` and `make_handler` on private loopback servers. No browser API or allocation projection was mocked.

- All 13 rows retain the expected allocation membership, exact authorization occurrence, visit clinic, original visit identity and both source rows. The later `DUP-1` source row is the sole retained duplicate.
- Used/reserved, exact authorization period, actual visit clinic and literal case-insensitive per-field search work separately and together. Search does not join adjacent fields into a new matching string. Clearing the four filters restores all records.
- Native keyboard events select a filter. At a 390-pixel viewport, controls stay within the document and the local table region provides all 674 pixels of horizontal keyboard travel to the rightmost source columns. Native Tab navigation reaches the complete export link and Enter downloads it.
- At both 1280 and 390 pixels, the document width stays within the viewport. Desktop, phone-left and phone-right captures are retained. Long allocation text wraps in its cells, and the rightmost provenance columns remain accessible.
- A filter showing one visit still downloads all 13 native rows. The mouse and keyboard downloads are actual completed browser files, each **4,936 bytes**, SHA256 `289aea968ecc7f01be2641e809a0b790eeb7f43c10d8824d4c757e10945751ea`, byte-identical to the native complete CSV.
- An older report without allocation detail displays unavailable detail, disables all four controls and supplies no allocation download. A valid empty result displays zero of zero, retains controls and links, and actually downloads its **243-byte header-only CSV**, SHA256 `45e06adbffae69642a82d867bfb6fdb097ccf94c53728bdeee78c86d6479c1a8`.
- The printable link opens the complete 13-row digest despite the filter. The actual PDF is **three A4 pages, 42,936 bytes**, SHA256 `0dd860d2e5b04511fa8771932536e9c48ee22c6982b73320e33e9c5f5a0384d3`. All 13 exact identifiers occur in its raw reading order; every extracted word remains within the page bounds. All three pages were visually inspected, including the literal markup and long strings.
- Literal markup is displayed as text. The original run records zero page errors, dialogs and external requests. Every request observed by both native coordinators was GET.
- Both runs preserve all **58 watched source, input, generated report and fictional staff-state files**. Both Git worktrees remain clean. Each coordinator closed every private server; both browser profiles were closed and removed.

The original PDF `-layout` substring scan returned false for the two wrapped identifiers because neighboring columns interleave between their text fragments. That exact scan and result remain in the original execution receipt. A separate addendum reads the same unchanged PDF with Poppler's raw reading order and word geometry. It does not regenerate or alter the PDF.

## What this packet means for the owner

The **ultra-20b27c2e-20261008** owner retains PR #56, original source recovery and integration. Current ownership was checked in issue #43, PR #56, central coordination, all readable external contribution JSON records and native Conscience decisions. The separate PT CSV-header contribution in issue #58 is preserved. Our distinct receiving claim is Conscience seq **4865**, event `cev_49314b20d275499496c7011b`; [the source issue records the scope](https://github.com/Jacob-Met/workflow-checks/issues/43#issuecomment-6067595213).

This new ThinkPad packet does **not** reconstruct or replace the four unavailable original author test/documentation payloads or the missing original Mac measurements. It does not resolve the unknown original native write effects. It supplies new independently frozen fictional-data evidence for this exact recovered candidate. PR #56 remains the owner's incomplete draft, and its eventual complete composition still needs the owner's source recovery and then-current integration gates.

The qualification concerns application allocation visibility and provenance. It does not validate real payer authorization policy or real patient data. The browser capture shows the candidate's ordinary pre-existing authorization ledger above the new panel; that existing ledger is not redesigned by this contribution.

## Packet contents and reproduction boundary

`summary.json` maps each of the 20 distinct browser groups to its original or replay evidence. `source-verification.json` records exact source blobs and clean statuses. `manifest.json` gives every published payload's SHA256 and byte length. `native-packet-manifest.json` preserves the larger original evidence inventory separately.

The `payload` directory retains the frozen contract and fixtures, original seven receiving scripts, three CLI preparation results, both browser reports and execution receipts, the actual completed replay downloads, actual PDF and Poppler outputs, and selected visual captures. Scripts retain their real private paths and executor identities for forensic reproduction; they were not rewritten after measurement to look portable. To repeat on another receiver, prepare a distinct namespace and exact source worktrees and record that new run separately. Do not overwrite these measurements.

Runtime: native ThinkPad, Python 3.14.4, Node 22.22.1, Playwright 1.64.0 and Chromium 153.0.8010.47 with `chromiumSandbox: true`. Browser dependencies were already installed. Initial source hydration was refused by an owned `/tmp` capacity guard before cloning; the later source checkout used an independently guarded owned native `/dev/shm` namespace. The additive download replay used a small private browser-visible home profile after a fresh capacity guard and removed it after completion. Earlier transport failures and resource refusals are retained. No service, real calendar, patient, payer or provider operation was performed.
