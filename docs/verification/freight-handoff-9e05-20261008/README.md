# Freight saved-review handoff verification

## Result and scope

The final candidate adds a portable handoff for the currently selected freight load. A reviewer can download a ZIP containing the original generated packet, its existing six report sections, the exact saved review and history, and a readable cover. It uses the native evidence version and a separate saved-review version so the downloaded bytes describe the same displayed snapshot.

Source parent: `Jacob-Met/workflow-checks` commit `2f1e5f777197eedd69d51a4d81c0da744b65ad88`, tree `86e6201872d2f2400537b84a50f026a1335a8c3d`. The selected baseline comprised 21 files whose Git blobs were checked against that connected tree. The final source freeze contains 23 files; five are changed or new. The native tree contains no `AGENTS.md`.

Coordination: [HAMON #140, comment 6058419406](https://github.com/Jacob-Met/hamon/issues/140#issuecomment-6058419406). The scope is the existing freight review application, not the separately owned freight what-if demo.

The final source is candidate v2. Its manifest SHA-256 is `8cb5c17c01d589067779a573e8a66bc5227feed08fbbeb9f33dd2aa557db732d`. Production line endings in the existing Python, HTML and README files were retained.

| Validation | Attribution | Preserved result |
| --- | --- | --- |
| Original native HTTP feature probe | Producer, before implementation | Saved review exists; bundle GET returns 404; no download control; no mutation by that GET |
| Final complete freight test suite | Producer using an existing Python 3.12 interpreter | 71 passed, 15 subtests passed; 58 inherited methods plus 13 new methods |
| Independent native HTTP receiving | Separate reviewer `estate_work`, independently pinned source | Same 10-method carrier: v1 has one failure, v2 passes 10/10 |
| Actual native browser receiving | Producer browser carrier, fresh Mac Chromium context | Same 11-check carrier: v1 passes 10/11; v2 passes 11/11 with 10 actual ZIP downloads |

These are separate gates, not an aggregate count of independent tests. The final result does not claim a customer pilot, a production deployment, or a send/payment integration.

## Receiving contract

The page reads the existing native `/api/summary`. Its additional `review_versions` map identifies each selected load's exact current native decision view, including history, or JSON null when unreviewed.

The download request is:

```text
GET /api/review-bundle?load_id=<load>&evidence_version=<shown evidence>&review_version=<shown saved review>
```

All three parameters must be supplied once. Under the existing application lock, the handler requires the already generated summary and a readable selected packet, checks both displayed versions, and creates the archive in memory. A missing current summary is refused before the native summary initializer can generate or write anything. A stale client version returns 409; malformed, missing and failed requests have no attachment header. The normal download leaves native data, reports, decisions and audit bytes unchanged.

A currently displayed review may itself be unreviewed, cleared, stale or unbound. The cover preserves and labels that native state. There is no added approval gate. An old saved approval is not promoted to approval of changed evidence.

Each ZIP has exactly five fixed members:

| Member | Contents |
| --- | --- |
| `index.html` | Offline cover, saved-review state, note and history, member links and snapshot identities |
| `packet.html` | Original selected packet bytes |
| `evidence.json` | Exact native evidence-hash input: schema, packet SHA-256, and selected rows from stops, flags, fines, settlements, exceptions and packets |
| `review.json` | Schema, selected load, both versions and `review`, the exact native selected decision view or null |
| `manifest.json` | Schema, selected load, both versions and `files`, an array of `{path, bytes, sha256}` for the other four members |

The original native evidence hash recipe is unchanged. The new review identity uses sorted compact JSON with ASCII escaping so accepted escaped-surrogate notes remain representable. JSON values round-trip exactly; the cover escapes HTML and shows an escaped form for text that cannot encode directly as UTF-8. Same-snapshot ZIP bytes are stable. Hashes establish byte agreement, not authorship or independent authenticity.

The archive preserves only this load's saved review and history. It does not include original input files, global decisions, the global audit log or other-load records. The selected evidence retains its original file/row references.

The UI labels the gesture **Download saved review**. Unsaved note edits disable it with a save/undo explanation. A change of selection, an edited note, a review save, a pipeline action or explicit cancellation invalidates a pending browser download. A failed or canceled gesture is not automatically retried.

## Preserved failures and repairs

1. **Missing generated summary caused a write during GET.** The independent v1 receiver first generated the native fixture, saved a selected approval, captured both displayed tokens, removed `out/summary.json`, then followed the old download link. V1 returned 200 and recreated the report and appended audit through the native `summary()` initializer. The complete counterexample, actual ZIP, before/after hashes and failed gate are retained. V2 adds only the existing-lock preflight for the generated summary. The unchanged independent carrier now receives 404 and unchanged native files. A producer regression was also first observed failing against v1 production, then passes in the final suite.
2. **A failed save restored an unsaved note after enabling the button.** The real v1 browser generated changed evidence through the native seed-8 API, submitted a stale review, received 409 and observed the preserved unsaved note. The displayed download button was enabled even though the click guard refused it. The screenshot and 10/11 result are retained. V2 dispatches the ordinary input event after the existing programmatic restoration. The unchanged browser carrier now sees the disabled control and save/undo explanation, and download succeeds only after the note is restored to its saved value.

The separate first implementation freeze and final freeze, raw logs, unchanged carriers and genuine negative artifacts are retained. No test expectation was weakened for the repair.

## Browser evidence

The carrier runs the actual pinned native Python application through its normal handler, synthetic generator and pipeline, using an ephemeral loopback port and a fresh headless Chromium context. It does not replace the application with a mock implementation. Delayed-delivery controls obtain genuine native ZIP bytes and hold only their browser delivery.

The 11 final checks cover an unreviewed download; note edit/undo/save and offline cover; identical repeated bytes; selected history and other-load isolation; a newly saved review's 409 and reload recovery; explicit cancel; late old-load delivery after selection; note edits during delivery; pipeline rerun during delivery; a genuine rejected save with retained unsaved note; and a genuine missing-packet 404. Each accepted download is decoded independently with Python, reconstructs the native evidence hash, checks review identity/member hashes, and compares the packet bytes with native output.

The raw v2 archive is `b485f057d7e2ddf078112668dce50e84c406de69dd6eb2af24a7456968fe8e09` (557,203 bytes). The raw v1 archive is `7c37dd43f87925a942b1a49367f7e59c42ebe9e4f83a1516154a23ebe50e957f` (782,505 bytes). Both were transferred from the isolated Mac run and rehashed locally. The runtime's 16 production-file hashes match their respective source freezes. The browser harness and both Python carriers are byte-identical across v1 and v2.

Screenshots inside the raw final archive are `browser-evidence/native-review.png` and `browser-evidence/offline-cover.png`. The actual saved download is `browser-evidence/saved-review.zip`; all ten final downloads, corresponding summaries and member receipts are retained.

## Packet contents and reproduction

`source-pins.json` records the original, first and final source pins and carrier hashes. `results.json` contains the attributed result inventory and archive hashes. `evidence.tar.gz` contains the full original/final selected source, first-source custody, raw producer and browser failures, both raw browser archives, and the independent reviewer's frozen source/evidence packet. Historical test source is confined to this archive and is not collected by repository pytest discovery.

Full evidence archive: **1,861,010** bytes, SHA-256 **ffcf4e6d53727c1b8047e5d90dfbcb65e13248ba76bf3fd39931f2c64e99c24b**, Git blob **137f5d221d651b6694bc6851c0b219f7007457b4**.

The retained project suite runs from `freight_packets`:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider tests
```

The three browser carriers are optional. They require an already installed compatible Node Playwright package, Chromium executable and Python interpreter. Use a disposable root with this layout; `candidate/freight_packets` may be a symlink to the exact checkout being reviewed:

```text
<qa-root>/
  candidate/freight_packets/
  browser_handoff.cjs
  qa_server.py
  inspect_bundle.py
```

Run with explicit existing runtime paths:

```sh
FREIGHT_TEST_PLAYWRIGHT=/absolute/playwright/package \
FREIGHT_TEST_CHROMIUM=/absolute/chromium \
FREIGHT_TEST_PYTHON=/absolute/python3 \
node /absolute/qa-root/browser_handoff.cjs /absolute/qa-root
```

The carrier creates only its own `browser-state` and `browser-evidence` directories. It stops its own server and browser at completion. The recorded run used Node v26.3.0, the existing Mac Chromium headless shell build 1243 and Python 3.13.7.

The native application supports one server per output directory. This work retains that envelope; it makes no filesystem-wide transaction claim for a second CLI process or another writer. The test inputs are synthetic. No rate, detention, fines, settlement, billing or approval rule was modified, and no provider, production account or external delivery path was exercised.
