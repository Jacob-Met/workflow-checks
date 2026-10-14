# PT composed portable package — actual download receiving

The [versioned PT source ZIP](https://drive.google.com/file/d/1uuBHZynhfWRfFyLYoAi9GrZvIFbtf8Ti/view) contains the complete selected PT runtime and browser assets, existing fictional sample, two focused test modules, license and practical instructions. Extract all files, read [START_HERE.md](independent/course/extracted/START_HERE.md), and run commands from the extracted `pt_auth` directory. Python 3.10 or later is required. The ordinary command uses only the standard library; the explicitly named `UTC` zone requires IANA time-zone data on the host.

```sh
python -B -m ptauth run --data sample_data --out NEW_REPORT --as-of 2026-09-28 --clinic-timezone UTC
```

Choose a new report directory. The inherited report writers do not provide a universal create-only transaction. The bundled sample is fictional, seed 21 and as-of 2026-09-28. Its generated reports are examples, not clinical advice or evidence of an installed deployment. The archive includes the existing local browser UI, but this receiving course exercised the command line only. START_HERE separately describes optional calendar, local server, generation and the two packaged tests; broader inherited repository test instructions can name files outside this focused kit.

## Source and publication boundary

The 25 maintained payloads are exact files from reviewed draft source [69f3c8e0577b579ee36256da0a075fccb201af8f](https://github.com/Jacob-Met/workflow-checks/tree/69f3c8e0577b579ee36256da0a075fccb201af8f), tree `3c2a77730ab23915fb5a33ae02b70497812da7c7`. That commit composes the retained calendar and date repairs. It is published on the issue-116 review branch, **not integrated into main**. The existing dynamic Pages / no-Actions hold remains in force. Package availability does not change that hold, install an application, deploy Pages or supersede another owner's source.

The exact 25-file inventory consists of twelve runtime/UI files, LICENSE, the maintained README, CALENDAR_RECEIPTS, two focused tests, six existing sample files, HARDENING and CSV_HEADERS. START_HERE and SOURCE_MANIFEST make 27 selected payloads; the packer's MANIFEST makes 28 regular archive members. Both web assets and original repository-relative paths are retained. No generated report or user data is included in the distributed ZIP.

[SOURCE_MANIFEST.json](independent/course/extracted/SOURCE_MANIFEST.json) maps the 25 maintained files plus START_HERE to byte length, SHA-256, Git blob and provenance. [MANIFEST.json](independent/course/extracted/MANIFEST.json) covers all 27 selected payloads. [Source admission](packaging/source-admission.json), [tree admission](packaging/prebinding-tree-admission.json) and [final binding](packaging/source-binding.json) retain the exact source comparison and the final source-placeholder-only START change.

The earlier [calendar-only ZIP](https://drive.google.com/file/d/1SzuSMOdsuae9MsTX3o_l5IlRXM2ZWVrv/view) and [date-repair portable ZIP](https://drive.google.com/file/d/1Av1gUHMs5sm84ZIRhX_Lu61rQS_IH7c6/view) remain unchanged. Their source and receiving histories are separate.

## Exact delivered identity

| Field | Value |
|---|---|
| Ready filename | `PT-Auth-Composed-Review-69f3c8e0.zip` |
| Stable Drive ID | `1uuBHZynhfWRfFyLYoAi9GrZvIFbtf8Ti` |
| Bytes | 77,452 |
| SHA-256 | `ba9941d29489f584e3fcd0b7b379b9a4de57d1fb56bede960983450650d1bd43` |
| Git blob | `facfbd93a4d7faa331c975021d48bd97986180fd` |
| Archive members | 28 regular files |
| START_HERE Git blob | `29376053ab58aa240c50bd71a275daf74b24afda` |
| SOURCE_MANIFEST Git blob | `3045f338f985c279ba7ef065ea92ed258abf8689` |

The file was uploaded once with a candidate metadata name. The ready filename is a metadata-only promotion after accepted receiving; it does not change these bytes. [The original transfer receipt](packaging/drive-receiving.json) deliberately retains its then-pending runtime status. It records one direct local upload and one full actual Drive download, exact byte equality and all 28 member bytes. It contains stable IDs and hashes, with no signed transport URL.

The unchanged maintained [make_delivery_zip.py](https://github.com/Jacob-Met/estate-push-tools/blob/3b4ffc20300a2bdf7d00281c61f1a1c5a4bcf91b/make_delivery_zip.py), blob `34e192096abed7216025e8141a9cf3106bb82dfd`, ran once through [assemble_delivery.py](packaging/assemble_delivery.py). The [packaging receipt](packaging/receiving.json) records exit 0, reaped process, CRC and every selected byte checked, and all 29 watched packer/selection/payload byte and native-mtime records unchanged. [stdout](packaging/packer.stdout) and [stderr](packaging/packer.stderr) are retained. No PT application command ran during packaging.

## One independent course on the actual download

The [protocol](independent/PROTOCOL.md), [literal expectations](independent/expected.json) and [receiver](independent/receive_kit.py) were frozen and independently reviewed before archive exposure. They admit the fixed 28-member inventory, external source pins, both manifests and literal existing sample expectations. Consumer runtime then used the full actual downloaded [ZIP](independent/actual-drive.zip), extracted a fresh directory and executed exactly one ordinary `run` command shown above with a new absolute report path.

The complete [raw receiving receipt](independent/course/receiving.json) reports **85/85 checks passed** on Linux x86-64 / Python 3.12.14. Child PID 4 returned 0, was reaped and did not hit the fixed 30-second bound; stderr is empty. The [outer execution observation](independent/outer-exec.json) separately records exit 0. All 32 watched archive, receiver, protocol, expectations and extracted-member byte/native-mtime records are unchanged. These execution intervals are receiving observations, not a performance comparison.

The seven new outputs are retained under [course/new-report](independent/course/new-report): audit.jsonl, digest.html, ledger.csv, summary.json, uncovered_visits.csv, visit_status_review.csv and worklist.csv. Frozen literal checks cover 40 patients, 842 visits and 46 authorizations, plus the exact expected sets of 194 scheduled uncovered visit IDs and two completed unauthorized visit IDs. The observed 26 worklist rows are independently cross-checked through CSV, summary and priority-count associations; 26 was not a frozen literal expected count. The audit's run scope and UTC timestamp are checked against that invocation. This course does not repeat calendar generation, synthetic-data generation, the tests, a browser/server session, or any installed application.

The [source qualification](../README.md) records separate source-level work: the five-command / 68-check composition course and unchanged 19-method plus four-subtest course. Those results are not added to the 85 package checks. Likewise, the earlier calendar-only package's 33 checks remain its own one-command course. The package sample is the retained seed-21 dataset, distinct from the source composition course's new seed-53 six-patient dataset.

## Raw evidence and reconstruction

[native-manifest.json](independent/native-manifest.json) preserves all 43 native path mappings verbatim: 716,364 bytes and 43 unique bodies, including the actual archive, all 28 extracted members, seven reports, raw streams, protocol, expectations, driver and receipts. Paths are relative to `independent/`. The complete original records are retained rather than rewritten to replace local execution paths.

For an independent repeat, fetch this exact archive, verify its external size/SHA-256, extract it into a new directory and follow START_HERE. To repeat the frozen receiving logic specifically, use the retained receiver, protocol and expectations together in their original relative layout and pass a fresh output directory as documented by the receiver's CLI. No old output directory is reused. This documentation does not request another execution of the completed course.

All 43 native paths (716,364 bytes / 43 unique bodies) plus the native manifest have complete remote body equality: the 42 non-ZIP files were compared as full UTF-8 bytes, retaining original CRLF, and the ZIP was fetched through immutable contents/Base64 at detached commit `979c2a3c9a4f7614a9fa2180bff351bcd621a615` and compared byte for byte. The [complete-body readback receipt](independent/complete-body-readback.json) records those routes and exact identities. This final transport gate is distinct from the completed actual Drive byte comparison and one extracted-runtime course; no build, upload or runtime was repeated.
