# PT portable browser workflow — received review packet

The existing [portable PT source ZIP](https://drive.google.com/file/d/1uuBHZynhfWRfFyLYoAi9GrZvIFbtf8Ti/view) has now been received through its local browser UI as well as the earlier command-line course. The accepted browser successor completed **21/21 checks**, including a complete 196-row CSV download while the page showed eight filtered visits. The two original captured views and complete CSV are preserved with both browser receipts in the compact review packet described below.

This uses the unchanged published source snapshot [69f3c8e0577b579ee36256da0a075fccb201af8f](https://github.com/Jacob-Met/workflow-checks/tree/69f3c8e0577b579ee36256da0a075fccb201af8f), source ZIP Git `facfbd93a4d7faa331c975021d48bd97986180fd`, 77,452 bytes, SHA-256 `ba9941d29489f584e3fcd0b7b379b9a4de57d1fb56bede960983450650d1bd43`. It remains on the opt-in issue-116 branch, **not merged into main**. The dynamic Pages / no-Actions hold and other owners' staff-review and allocation source remain unchanged. No PT product source or existing package byte changed for this browser receiving.

## Practical local workflow

Extract the existing source ZIP, read its START_HERE and change to the extracted `pt_auth` directory. Python 3.10 or later and IANA time-zone data for the explicit UTC zone are required. Use a new report directory and unused local port:

```sh
python -B -m ptauth serve --data sample_data --out NEW_UI_REPORT --clinic-timezone UTC --port 8765
```

Open `http://127.0.0.1:8765/` in a browser. Server startup creates a fresh report; the inherited writers do not promise a universal create-only transaction, so do not reuse reports you need to preserve. Stop the server with Ctrl+C when finished. The sample is fictional seed-21 data with recorded date 2026-09-28 and clinic zone UTC.

The received workflow selects P1, searches `SYN-1014`, and opens the five-item checklist for `AUTH-70039` with Enter. It then selects Uncovered visits, Upcoming scheduled and the same patient ID. The screen retains original visits V1271–V1278. The complete-export action downloads all 196 original uncovered visits rather than only the eight visible rows. At narrow widths the table's internal horizontal review region exposes the other columns.

No staff-state change, Run-button action, calendar export, synthetic-data generation, payer contact or installed deployment was exercised. The earlier [85-check extracted CLI course](../delivery/README.md), [source qualification](../README.md), 68-check/five-command composition course and 19-method/four-subtest course remain separate; their counts are not added to these browser checks.

## Frozen receiving and original failure

The receiver was frozen with literal expectations from the actual bundled sample and exact source/archive pins. The [original protocol](controls/PROTOCOL-original.md), [original controller](controls/run_course_original.py) and [freeze](controls/freeze.json) are retained. Before execution, independent review required one narrow cleanup amendment: after an already-reaped unsuccessful Node exit without an outer timeout, the controller makes one recorded kill attempt on that same owned process group. It does not repeat the timeout cleanup. The [amendment](controls/cleanup-amendment.json) preserves both versions. The executed controller is `9367ccb119788c9be8dbf3645a107ee6302cdf2b`; protocol `6b9be3d8f1d9cac9ccb5d70d043b7768948c093f` and oracle `a072989cfab2f17e7c6b805a22e084b0c46ef703` are retained in each course.

The first course used driver `3f9906b118ad74f69f46df4e141a664a6f8c1288`. Its [original receiving record](first/received-course/receiving.json), Git `bcd9446cdf3e5e8246fe062e6e7198524ef9af34`, remains `passed: false`: **14 functional checks passed, one inline-resource classification check failed, and two cleanup checks passed**. The receiver treated the built-in `data:image/svg+xml;base64,...` calendar icon as non-loopback traffic. All observed HTTP requests were GETs to its own loopback origin. One complete CSV and both screenshots already existed. Checks after the failed classification assertion were not reached and are not inferred from the artifacts.

[The first outer observation](controls/first-outer-observation.json) records RDC PID 706302 collected exit 1 in 1.91 seconds. Native Node PID 706369 returned 1, was reaped, did not hit the outer timeout, and had an outer interval of 1,817,361,729 ns. Browser 706376 acknowledged closure, was absent and had launcher exit 0. Server 706382 was terminated, waited/reaped and absent. The controller's later owned-group kill attempt recorded already absent. All 33 input byte/native-mtime records remained exact. This failure is a receiver classification result, not an observed PT product defect.

## One-expression successor and accepted course

The [inline-resource amendment](controls/inline-amendment.json) changes only the request predicate: accept the exact observed inline SVG GET in addition to the unchanged own-origin GET requests. External HTTP/HTTPS, own-origin POST, other data URLs and deceptive origins remain refused. A separate [helper-only predicate proof](controls/predicate-proof.json) retains ten literal predicate cases plus the original and successor recorded-request-set checks; it does not run a browser or product. Every other receiver assertion, stimulus, source/sample byte, deadline and cleanup rule remains unchanged. The successor driver is `3d3c477e19731b0ce87c71e7390685c521f27cf0`.

The subsequent [raw receiving record](final/received-course/receiving.json), Git `ca19af9ad0a16db698ce493e3638a90d1c27786a`, reports **21/21 checks passed**. The [separate terminal observation](controls/final-outer-observation.json) records RDC PID 713563 collected exit 0 in 1.91 seconds. Native Node PID 713630 returned 0, was reaped, had no outer timeout and an outer interval of 1,817,404,288 ns. Browser 713637 acknowledged closure, was absent and had launcher exit 0. Server 713643 was terminated with SIGTERM, waited/reaped and absent. These intervals describe their individual receiving courses, not a performance comparison.

This actual ThinkPad Linux course used Python 3.14.4, Node 22 and Chromium 153. It started one necessary local server from a fresh extraction of the actual downloaded ZIP, generated one new report at startup, then exercised the browser. It did not repeat a separate direct `run` CLI invocation. The predecessor also had its own server/startup report; neither attempt is erased or folded into a single run.

The successful checks cover the fictional scope/date/zone, count cards and 26 work items, eleven P1 rows, the exact selected work item and five-item checklist, all 196 original uncovered visit IDs, 194 scheduled rows, all eight selected visit field maps, explicit full-export label, complete exact CSV and retained filter, available narrow page width and internal scrollable table, request/JavaScript boundaries, exactly one download, all seven report files unchanged and no staff state or bytecode cache created. The complete outer before/after records preserve all **33 inputs** by bytes and native mtime. Report snapshots preserve all **seven outputs** by bytes and native mtime across UI interactions.

## Exact downloadable CSV and captured views

| Original output | Bytes | Git blob |
|---|---:|---|
| [Complete CSV](final/received-course/downloaded-uncovered-visits.csv) | 31,101 | `e750ad287278f3857be3684c8009d0afe7dd2a35` |
| [Worklist desktop PNG](final/received-course/worklist-desktop.png) | 150,560 | `4b1a9b728ac0a299e69e2c2616ba4b47622b785f` |
| [Uncovered narrow PNG](final/received-course/uncovered-narrow.png) | 60,998 | `b89ba0b65e193ae12ed0f9f07fe0bfec6ae8ded9` |

The CSV's SHA-256 is `adef91b6f7086f8f4e192a6267a84ad9e63b437e51b62df115a133497422a8ec`; its original bytes include all 196 data rows. Both attempts produced the same PNG bytes and same CSV bytes.

Root visually inspected the original 1280×900 desktop and 390×844 narrow captures. The desktop is scrolled to the filtered work item and expanded checklist. The narrow capture shows the left columns of the eight-row result inside its existing horizontally scrollable review region; its measured page client/content width is 375 pixels within the 390-pixel viewport. The acceptance is limited to these captured states, not a full-page, print, physical-input or accessibility review. No image was cropped, annotated or regenerated for this packet.

## Raw evidence and complete body receiving

[publication-manifest.json](publication-manifest.json) maps **120 paths, 2,003,969 bytes and 74 unique bodies**. It preserves both courses' 53 native files and native manifests, plus 12 frozen-control/history/outer records. The raw first and final bodies are kept under their separate directories, including original failed receipts, streams and generated reports. All native path mappings are retained verbatim; the local manifest paths are historical capture locations, not reconstruction prerequisites.

All 120 mappings and the publication manifest have complete remote body equality. The 71 unique UTF-8 bodies were compared as complete bytes. The actual ZIP and two unique PNGs were fetched through immutable contents/Base64 at detached commit `a863c4f23d2b24c4a2f78844e8e9ee3425cea09a` and matched the retained native bytes. Both attempts' image paths reuse those same two blobs. [The complete-body receipt](complete-body-readback.json), Git `4682b4501554d2bc59fe09cbb029b7f91195dfee`, records the exact scope. No runtime or upload was repeated to close this body gate.

For reconstruction, fetch the exact source ZIP and the protocol, expectations, controller and chosen driver from the same preserved course directory; the controller CLI declares its explicit file arguments and new output directory. Admit the external ZIP/source identities first and use a fresh owned output/profile stage on a suitable Linux route. The history files explain why the first attempt and successor differ. This record documents completed receiving and does not request another course.

## Compact offline review delivery

The compact review ZIP contains seven selected payloads plus the maintained packer's MANIFEST: static OPEN_REVIEW.html, START_HERE.md, the two exact PNGs, the exact complete CSV, and both original browser receiving JSONs. Extract the whole archive and open OPEN_REVIEW.html. Its prose and layout are new explanatory material; the five native evidence payloads retain their original bytes. It contains no PT runtime, browser launcher, script or automatic network resource. The existing source ZIP is linked as an optional separate download.

The [received review ZIP](https://drive.google.com/file/d/1Jx9qC8zmWdjIZJqbpdCnaJ3H6Y2hpWZe/view), `PT-Portable-Browser-Review-69f3c8e0.zip`, is 215,029 bytes, SHA-256 `ce91c36b2577a1d83e90730216aa09081fa3c4ba9c2089ecee855263ff7c5223`, Git `8128e03eb534fec539d432613091c6fd32355e95`. The unchanged maintained packer `34e192096abed7216025e8141a9cf3106bb82dfd` ran once. [Its receipt](packaging/packaging-receipt.json) records exact eight-member layout, all selected bytes and CRC, exit 0/reaped, and all nine packer/selection/payload byte/native-mtime records unchanged. [Selection provenance](packaging/review-provenance.json) distinguishes the original native payloads from the new explanatory HTML and note.

One direct upload to the existing PT artifact folder and one complete actual Drive fetch produced byte-identical ZIPs; [the transfer receipt](packaging/drive-receiving.json) also checks every archive payload. There was no text conversion, runtime repeat or replacement of the existing source ZIP. Root then ran one [retrospective independent archive receiver](review-independent/receive_review.py) on those actual downloaded bytes. Its [original receipt](review-independent/receiving.json) records **21/21 byte/layout checks** and five watched local input byte/mtime records unchanged: exact eight-member/CRC/metadata layout, all seven manifested payloads, external accepted note/image/CSV identities, original receipts, all 196 frozen visit IDs and static HTML resource/link boundaries. This is a separate archive inspection from the 21-check native browser course; it did not extract or execute the application, server or browser.

The new static opening HTML received full prose/source review. The available local Playwright module had no browser executable; no renderer was installed and no rendered-page check is claimed for the opening page. The original accepted PNGs were inspected directly. [Complete review-body readback](packaging/review-body-readback.json) retains the full new text comparisons and immutable contents/Base64 comparison of the exact review ZIP at detached commit `dede2cb99f065f492b7879296d0609d378122a32`; the then-current guide is identified separately from this final paragraph completion.
