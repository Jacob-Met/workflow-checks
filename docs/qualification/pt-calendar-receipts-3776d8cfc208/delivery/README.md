# Calendar-only portable receiving — reviewed draft source

Download [PT-Calendar-Receipts-1bd30de4.zip](https://drive.google.com/file/d/1SzuSMOdsuae9MsTX3o_l5IlRXM2ZWVrv/view), extract the complete archive, and open its `pt_auth` folder. With an existing Python 3.10 or later, run:

```sh
python -B -m ptauth calendar --report "/absolute/saved-report" --output "/absolute/new-calendar.ics"
```

Use an existing fictional saved report and a new output path whose parent exists. Read [START_HERE.md](START_HERE.md) and the bundled `CALENDAR_RECEIPTS.md` first. This package supports only the calendar command; the unchanged shared help may name other commands whose dependencies are not bundled. It includes no saved report, full application, installer or automatic launcher.

## Source and artifact identities

The five source/guide files are exact at reviewed draft snapshot [`1bd30de4cecff7ee7564dccadf53561f3e21c284`](https://github.com/Jacob-Met/workflow-checks/commit/1bd30de4cecff7ee7564dccadf53561f3e21c284), published through [draft PR 115](https://github.com/Jacob-Met/workflow-checks/pull/115). This is not a main merge or installed update. The existing dynamic Pages/Actions integration hold from [issue 106](https://github.com/Jacob-Met/workflow-checks/issues/106) remains. No repository setting, workflow or deployment was changed for this delivery. The earlier full portable/date-admission package remains separate.

The actual downloaded ZIP is **13,763 bytes**, SHA-256 `ff2e5208a60173a79f0b348452741b996d1293d69d8e0630709c8aedf2a95661`, Git blob `88b16fed1400cd08c65ec5f35fb3f1aa237178a5`. Its eight members are root `MANIFEST.json` and, under `pt_auth/`, the four `ptauth` runtime files, `CALENDAR_RECEIPTS.md`, `START_HERE.md` and `SOURCE_MANIFEST.json`. The outer manifest maps seven payloads; the source manifest records the exact five source identities and separate delivery note. Both manifests are integrity/provenance records, not validation of saved worklist declarations or payer policy.

## Packaging and actual transfer

The unchanged maintained [`make_delivery_zip.py`](https://github.com/Jacob-Met/estate-push-tools/blob/3b4ffc20300a2bdf7d00281c61f1a1c5a4bcf91b/make_delivery_zip.py), blob `34e192096abed7216025e8141a9cf3106bb82dfd`, ran once. [The packaging receipt](packaging/receiving.json) records exit 0, empty stderr, exact eight-member inventory/CRC/payload comparisons, and all nine watched tool/selection/payload byte and nanosecond-mtime records unchanged. This was archive construction, without importing or executing the application.

Before that first build, the nested source records were sorted by path to match the independently frozen interface. [The amendment](manifest-order-amendment.json) preserves both metadata identities; all five source and accepted START bytes remained unchanged. [selection.json](selection.json) is the exact outer manifest. [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) contains the source lineage.

One direct local-file upload produced the current Drive ID; one complete raw download was byte-identical to the built ZIP and every member. [drive-receiving.json](drive-receiving.json) records that comparison without transient transfer references. The same file was renamed from candidate to ready after the independent extracted course; no rebuild or second upload was needed.

## Independent extracted ordinary course

`consumer_runtime` froze [the protocol](independent/PROTOCOL.md) and [receiver](independent/receive_kit.py) before opening the START or ZIP. Root reviewed the complete receiver. On local Linux x86-64/Python 3.12.14, one command from the actual downloaded/extracted `pt_auth` directory passed **33/33 checks**. [The raw receipt](independent/course/receiving.json) retains child PID 4, exit 0, reaped/no timeout, empty stderr, eight admitted members and all seventeen watched source/archive/oracle/report byte and native-nanosecond-mtime records unchanged. [The outer result](independent/ordinary-outer-exec.json) separately records the receiver exit 0.

The fictional two-file report produced one event and the expected exclusions in a 1,223-byte UTF-8/CRLF calendar. The full wire bytes match the prior literal oracle after normalizing only its single valid `DTSTAMP`, bounded to this invocation's UTC interval. This timestamp is produced at export time. The JSON receipt matches the literal oracle after replacing only the chosen output path. No calendar matching/date logic was recomputed by the receiver. [The emitted calendar](independent/course/calendar-%E9%9B%AA.ics), stdout, source fixtures and raw records remain separately preserved. No cache or extra output appeared.

The [independent packet manifest](independent/packet-manifest.json) preserves 23 paths/94,380 bytes and 21 unique bodies. All twenty non-ZIP bodies and that manifest have complete remote equality; the actual ZIP's immutable Base64 readback is recorded separately when complete. This ordinary package course is distinct from the source repair's eight author methods and independent five-command/57-check matrix. It does not repeat their failed-stdout cases.

## Limits and reproduction

Status 0 requires successful calendar publication and the flushed newline-terminated JSON receipt. Status 2 requires inspecting the diagnostic and destination: a calendar can remain complete after receipt output fails. Do not infer success from partial stdout or blindly create another output. A failed stderr channel may be silent. The entry-point cleanup does not qualify every interpreter or caller-owned stream lifecycle.

To reconstruct this package, fetch the exact five source paths listed in `SOURCE_MANIFEST.json` at its source commit, add the separately pinned START and source manifest, and run the pinned packer using `selection.json` as in [assemble_delivery.py](assemble_delivery.py). To inspect the receiving course, use the preserved actual ZIP and literal oracle files with the frozen receiver; no machine-local path is the only source of an input. No extra run is required to use the already received archive.

This is a calendar-only source distribution and one Linux extracted-command acceptance. It does not qualify Windows terminals, a browser, installation, patient data, payer decisions, external calendar import, full-application workflows or the historical Pages deployment. Packaging/transfer: `continuity_delivery`; independent receiving: `consumer_runtime`; source/START and receiver review: root.
