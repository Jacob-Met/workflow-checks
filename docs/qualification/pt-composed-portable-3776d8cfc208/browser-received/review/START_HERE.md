# PT browser review — received portable source

Extract this entire review ZIP into one folder and open **OPEN_REVIEW.html**. It shows the two original captured views and links the complete CSV and both receiving records. No Python, server or network is required to read this packet; the source-download link opens online only when selected.

The supplied data is fictional. The successful course used the existing seed-21 sample, report date **2026-09-28**, and clinic zone **UTC**. The page displayed 26 work items. Filtering the uncovered table to eight visits for `SYN-1014` still downloaded all **196** original uncovered visits: 194 scheduled and two completed without authorization. The included `uncovered_visits.csv` is that exact 31,101-byte browser download.

## What was received

The accepted successor completed **21/21 browser checks**, one complete CSV download, and owned browser/server closure. All 33 watched input byte/mtime records and all seven generated report byte/mtime records remained unchanged. The two PNGs are exact captured viewports: the desktop shows one filtered work item and its expanded five-item checklist; the narrow capture shows left-hand visit columns inside the app's horizontally scrollable table. They are not full-page captures or an accessibility review.

The first course is retained separately as `receiving-first.json`, with `passed: false`: 14 functional checks and two cleanup checks passed, while a receiver assertion misclassified the built-in inline calendar SVG as non-loopback traffic. The receiver's one-expression successor admits that exact inline image alongside the same own-origin GET requests. The PT application, source ZIP, sample, stimuli and deadlines did not change. `receiving-final.json` records the subsequent 21/21 course. Counts from the two courses are not added together.

## Try the same portable application

Download and extract the separate [PT-Auth-Composed-Review-69f3c8e0.zip](https://drive.google.com/file/d/1uuBHZynhfWRfFyLYoAi9GrZvIFbtf8Ti/view). That unchanged 77,452-byte source ZIP has SHA-256 `ba9941d29489f584e3fcd0b7b379b9a4de57d1fb56bede960983450650d1bd43`. It includes its own START_HERE and manifests.

From its extracted `pt_auth` directory, using Python 3.10 or later:

```sh
python -B -m ptauth serve --data sample_data --out NEW_UI_REPORT --clinic-timezone UTC --port 8765
```

Choose a new report directory and an unused local port. The named UTC zone requires IANA time-zone data on the host. Server startup generates a fresh report from the bundled sample; open `http://127.0.0.1:8765/` in your browser and stop your server with Ctrl+C when finished. The inherited writers do not provide a universal create-only transaction, so preserve existing report directories.

To follow the received workflow, select P1 and search `SYN-1014`, then open its five-item checklist with Enter. Select Uncovered visits, choose Upcoming scheduled, and search the same ID. Review the eight rows and use the complete CSV export. At a narrow window size, scroll the table horizontally to reach the other columns. The receiving course did not change staff status, click Run, generate a calendar, contact a payer or install/deploy anything.

The source snapshot is the published, reviewed opt-in commit [69f3c8e0577b579ee36256da0a075fccb201af8f](https://github.com/Jacob-Met/workflow-checks/tree/69f3c8e0577b579ee36256da0a075fccb201af8f). It is **not merged into main**; the existing dynamic Pages / no-Actions hold remains. This packet does not contain the application runtime. Prior source, CLI, calendar and date-repair packages retain their separate identities and qualification.

## Files and identities

- `OPEN_REVIEW.html` — static opening page; no JavaScript or automatic network requests.
- `worklist-desktop.png` — original 1280 × 900 capture, 150,560 bytes, Git `4b1a9b728ac0a299e69e2c2616ba4b47622b785f`.
- `uncovered-narrow.png` — original 390 × 844 capture, 60,998 bytes, Git `b89ba0b65e193ae12ed0f9f07fe0bfec6ae8ded9`.
- `uncovered_visits.csv` — all 196 data rows, 31,101 bytes, SHA-256 `adef91b6f7086f8f4e192a6267a84ad9e63b437e51b62df115a133497422a8ec`.
- `receiving-first.json` and `receiving-final.json` — original browser receipts, including captured local paths and synthetic identifiers.
- `MANIFEST.json` — SHA-256 and size for each of the seven selected payloads, including this note.

The screenshots are identical across the two courses. The separate source evidence preserves both complete attempts, receiver history, native streams and custody records. These observations qualify this fixed fictional workflow on the received Linux/Chromium environment; they do not establish a clinical outcome, production deployment or general browser/platform compatibility.
