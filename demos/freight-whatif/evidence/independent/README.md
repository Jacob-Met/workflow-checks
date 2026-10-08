# Independent receiving — Freight what-if

Accepted for source integration and standalone delivery. This review covers native_execution's contribution in workflow-checks #17, only under demos/freight-whatif. Source integration remains with the contribution owner and root.

## Exact receiving basis

| Stage | Actual result | Receipt |
| --- | --- | --- |
| Direct current Python rules versus browser projection | 39 of 39 independently authored cases match every serialized stop, flag and total | independent-parity-receipt.json |
| Installed desktop/mobile interactions | 15 passed groups, 1 failed card-clipping group | browser-initial/browser-receipt.json |
| Corrected responsive card | 13 passed checks: 12 layout states plus source/runtime/network custody | layout-final/layout-receipt.json |
| Final license and artifact custody | Exact canonical MIT comment addition; source, installed files and ZIP payload match | license-custody-receipt.json |

The model and data stayed fixed at their received hashes. The 39-case oracle calls the actual pinned freightpkt.detention.evaluate_load and freightpkt.invoice_match.match_invoices; it does not use the implementation author's fixture generator. Cases cover early/departure ordering, inclusive tracking limits, odd increments, rounding, cap/warning precedence, maximum valid values, civil dates, exact-cent mismatches, seven simultaneous finding types and missing evidence.

The first actual browser run found a material narrow-screen defect. At a 320-pixel viewport, a valid $24,000.00 detention result pushed the invoiced $0.00 text 9.3125 pixels beyond the clipped card edge, although document width was still 320. The negative screenshot, geometry and failed receipt remain unchanged in browser-initial/.

The owner corrected three CSS declarations so amount blocks wrap when their combined width cannot fit. The independent focused receiver exercised default, maximum invoice charges, maximum supported detention and evidence-exception states at 1440, 390 and 320 pixels. It checks text bounds inside the card, amount overlap, control bounds and document overflow. Desktop and resting mobile screenshots and the formerly failing card were visually inspected. All 13 focused checks passed and all temporary browsers/listeners/profiles were closed.

Final distribution CSS adds only a closed comment containing the exact repository MIT LICENSE. I verified that its preceding functional CSS is byte-for-byte identical to the 13-check received CSS, its notice matches canonical Git blob edb188254288b40f2895833e3647b7e0be34c962, and the other four site files are unchanged. This does not relabel the earlier functional run with a different source hash.

## Final payload

Baseline main: 2f1e5f777197eedd69d51a4d81c0da744b65ad88. Exact final site pins are in candidate-delivery-pins.json. The earlier candidate-initial-pins.json and candidate-final-pins.json preserve the original failing and corrected-layout stages.

Final ZIP SHA-256: 57a0d4d34e8156f7f3bb3f0722882b0902e17ec731503ddd0ef5fdf6ceff6c08 (24,333 bytes). Its five site files and standalone LICENSE were checked against source and the owner's final installed artifact. The exact ZIP entry inventory is in license-custody-receipt.json.

## Replay the card regression

The portable receiver takes explicit paths. Supply existing Playwright/Chromium dependencies; it does not install them. Keep independent-oracle.json beside independent_layout.mjs. Use a new output directory; the receiver refuses to reuse one.

```sh
FREIGHT_REVIEW_PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
node independent_layout.mjs \
  /absolute/path/to/installed-site \
  /absolute/path/to/new-output \
  candidate-delivery-pins.json \
  /absolute/path/to/chromium
```

The receiver serves only the five allowed files on a new loopback port, blocks external requests, performs actual UI interactions, records served/source/runtime hashes and geometry, captures fresh unscrolled resting screenshots, and checks cleanup. Original independent_browser.mjs is also retained exactly as executed for the broader input/export/keyboard receiving stage.

The original independent_parity.py and probe_model.mjs are retained exactly as executed on the native Mac (Python 3.12.8, Node 26.3.0). To rerun that original pair, copy both into a new owned directory first; they write their oracle and receipts beside themselves, and the Python script uses /opt/homebrew/bin/node. Pass the current repository path as its first argument. Its core-source pins must still match.

## Scope limits

This is a synthetic, one-stop rules explorer. The review does not establish carrier data quality, contractual entitlement, legal validity, payment approval, settlement or real-world savings. Exceptions must still display No automatic claim even though the underlying rule serializes zero supported detention. Actual Chromium desktop and emulated mobile receiving does not claim physical-device coverage.

No source merge, public deployment or live service activation is asserted here. The owner's installer/server and 185-case primary tests are separate primary evidence; their execution is not counted as independent reviewer work. Other workflow-checks #15/#16 and CI scopes remain outside this contribution.

review-manifest.json hashes every file in this frozen peer packet except the manifest itself. Original negative evidence and all source-stage distinctions are preserved.
