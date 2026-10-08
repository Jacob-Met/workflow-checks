# Freight review evidence binding — receiving record

Reviewer approvals now refer to the generated packet and supporting per-load records. Changed evidence requires a fresh review; a stale browser cannot overwrite that review with an old evidence version. Prior decisions and notes remain available in local history. The browser refreshes after a refused or uncertain save without resubmitting it.

## Qualified source

- Author base: `58d18344b1ba81e704a22096d05ead2f5d5cdddd`.
- Final author commit: `ebbf4cf1114c4c680776c66d158f80f8c2429d22`.
- Receiving base: `4ae20a6d98c78e5d98fe4893f961812cc155dd52`.
- A complete receiving-tree comparison found only unrelated UtilityWatch changes; every freight base blob remains identical.
- Runtime: Python standard library, one local server per output directory. Source input edits must be rerun before reviewing their generated results. Concurrent CLI/other output writers remain outside that server's lock.

The six authored source/document/test blobs are preserved exactly, including original CRLF where present. The attached source receipt contains their byte counts, Git blobs and SHA-256 hashes.

## Observed verification

The original implementation failed two real HTTP probes: an approval survived a changed carrier and regenerated packet, and a stale browser overwrote the decision with HTTP 200. Both raw failures are preserved.

Native ThinkPad pytest passed **58/58 tests**. The new cases cover changed and unchanged evidence, unrelated-load independence, stale clients, legacy reviews, missing/changed packet bytes, prior notes and clear, task-local history, concurrent reviews and failed decision/audit writes. The final commit adds only the optional browser harness, browser-qualified CSS and README beyond the backend-qualified source.

Actual Chromium **153.0.8010.0** passed six browser boundaries: current approval counting; stale-client HTTP 409 with original review and typed note preserved; changed evidence removed from approved totals and visibly requiring review; explicit re-review with previous note history; a 390-pixel viewport without page overflow; and removed-packet selection with its historical decision retained. The first narrow-screen run found a 632-pixel page; the tab strip and review text were repaired, and the final screenshot was visually inspected. Earlier unavailable-browser and native quota failures are retained as setup failures, not passing browser runs.

Lead review checked that the deterministic version covers actual packet bytes plus the six per-load report sections, that backend comparison precedes any decision write, that the local lock serializes reruns/reviews, and that atomic decision replacement preserves the prior record on failed replacement. An audit append is a separate effect; an error after a decision save asks the user to reload and inspect rather than silently repeat the save.

## Reproduction and evidence

Run the existing freight pytest suite and `node tests/review_browser_smoke.cjs` as described in the README. The latter uses an installed Playwright/Chromium with disposable synthetic data.

[Complete evidence archive](freight-review-evidence.zip), 392,819 bytes, SHA-256 `f8d306bd781297320b9da53e8bf1dea35a9eed27b2e1dc4e2f2b008eeee73fdd`, includes the frozen source receipt, native passing/failed logs, browser receipt and desktop/mobile PNGs. No operational shipment data, live product server, payment or outbound message was changed by qualification.
