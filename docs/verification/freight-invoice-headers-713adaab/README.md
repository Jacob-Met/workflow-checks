# Freight invoice headers: admission repair and native receiving

This packet qualifies the bounded repair for [workflow-checks issue 28](https://github.com/Jacob-Met/workflow-checks/issues/28). An invoice's repeated carrier, date and total must agree within the existing trimmed invoice/load group. Conflicting rows now stop input loading with the relevant fields and the first/conflicting record references, before an audit append or replacement of existing generated reports.

## Product defect and behavior

The original loader silently kept the first row's invoice header. Seven authored, fictional CLI cases reproduced the effect on commit `9e931fa9f42033bf2368f7149684fb5631345715`: every command exited 0 and produced a READY draft. Reversing two carrier rows changed the draft payee. Reversing the date rows moved the dispute deadline from September 8 to September 17 and changed the synthetic fine deduction from 10,000 cents to zero. Reversing the total rows made the existing TOTAL_MISMATCH flag appear or disappear. These were draft reports from synthetic data; no payment, filing or external transmission occurred.

The repair changes only `load_invoices` in `freight_packets/freightpkt/ingest.py`. It compares carrier/date after the same surrounding-whitespace trim already used by the loader, and compares totals after the unchanged dollars-to-cents conversion. It retains the existing invoice/load grouping, valid nonadjacent multiline invoices, first-record evidence, line calculations, duplicate matching and settlement behavior. It does not infer carrier aliases, case equivalence, alternate date spellings or a new monetary precision policy.

The original README declared one row per invoice line and did not document a blank continuation-header inheritance convention. The original generator writes complete repeated headers. The pinned shipped sample contains 76 rows in 25 multiline groups, with no blank or conflicting carrier/date/total field. See `contract/contract-review.json` and the unchanged pinned sample. The new guide makes that repeated-header contract explicit. This tightens former silent acceptance of omitted or conflicting later headers; it is not a promise to accept arbitrary undocumented AP-export conventions.

## Exact source and scope

- Original upstream commit: `9e931fa9f42033bf2368f7149684fb5631345715`.
- Original ingest SHA-256: `1d5fb49d5656819c2b857a4d3d45f288b38885e109f0504992786714fe65382b`.
- Accepted candidate ingest SHA-256: `1179675d011d55781c6de3ae806b905698df2a21fcc621ea788d73c6e29d6276`.
- Maintained regression SHA-256: `1fda13d4c63ce4e2c311323db1995bd663a660c4637bc93bfded460ee2ae57d8`.
- Four owned source/guide paths: ingest.py, tests/test_invoice_header_consistency.py, README.md and HARDENING.md under freight_packets. Every byte before load_invoices in ingest.py is unchanged, including its monetary parser; original CRLF bytes are retained.
- `source-changes.patch` is the four-file native diff; `source-records.json` gives full before/after byte, Git-blob and SHA-256 pins. `upstream-source-manifest.json` pins the imported source closure.

The native repository is an explicitly partial 27-file import of that upstream closure, with native import commit `a29bd6704c9b67860038ed27d323c57bcdf5d203`. Its isolated commit is custody provenance, not a claim to be an upstream ancestor. Publication must be composed on the full current upstream tree, changing only the four owned paths plus this evidence directory. The current receiving parent recorded in `receiving-base.json` has the same freight before-images; unrelated Utility work remains present.

## Observed gates

| Receiving gate | Original source | Candidate source |
| --- | --- | --- |
| Same 8 maintained regression methods, native Linux Python 3.14.4 | 6 methods fail, 2 valid controls pass; 14 failure records including subtests; process exit 1 | 8 methods pass, process exit 0 |
| Complete freight pytest suite, native Linux Python 3.14.4 / pytest 9.0.2 | Not rerun as a broad negative gate | 79 passed plus 27 passed subtests, no skips/errors, process exit 0 |
| Original seven synthetic CLI cases, native Linux | Seven exits 0; conflicting rows silently affect draft results | Not repeated as another Linux sequence |
| Same seven fixture inputs, actual Windows 10 / Python 3.11.9 | Historical original behavior retained in Linux raw receipts | Actual CLI exits 0 / 1 / 1 / 1 / 1 / 1 / 1; coherent result unchanged and six conflicts refused |

The paired regression runs used identical test bytes and unchanged original versus candidate source. The tests cover each conflicting field in both row orders, combined conflicts, nonadjacent grouping and record references, valid trimmed/formatted equivalents, existing cross-load duplicate matching, and actual CLI refusal preserving prior reports/audit/inputs. Raw stdout, stderr, exact argv, Python and hashes are retained in `newtests-baseline/`, `newtests-candidate/` and `freight-full-candidate/`; the full positive JUnit is included. The failing original run is intentional regression evidence, not a claimed passing baseline.

The project declares Python 3.10+ and uses only its standard library at runtime. The native Linux and Windows versions above are actual observations. Hosted checks on the published exact head are a later integration gate and are not claimed by this packet's original run receipts.

## Actual Windows receiving

The receiver ran on DESKTOP-LA7CMTA, Windows 10 build 19045, ordinary installed CPython 3.11.9, with NTFS private fixtures at:

`C:\Users\minec\AppData\Local\Temp\hamon-freight-headers-713adaab-fb3a2ca166494553ba685bb70cf11acb`

The receiving driver parent used `py -3.11 -I -S -B -X utf8`; it then launched each real product CLI using the resolved interpreter with `-B -m freightpkt run --data <case>/data --out <shared private reports>`. Product subprocesses were ordinary Python, with PYTHONPATH/PYTHONHOME removed, PYTHONDONTWRITEBYTECODE=1 and UTF-8 I/O. No interpreter or dependency was installed.

The first coherent result retained Fictional Carrier A, READY, approved 110000 cents, fines 10000 cents and net 100000 cents, with no invoice flags. Each of the following six ambiguous cases returned actual exit 1 and identified its conflicting field plus CSV records 2 and 3. All seven existing report/audit files remained byte-identical after every refusal. All 28 candidate source-closure files and all 56 fixture input files remained identical across receiving. The wrapper qualification and setup/upload/execution/download transport processes each returned 0.

- Raw Windows report SHA-256: `6680fc84b0fef2934f5231bfec2c809a10450a6ef4d068c0837c49ab64f2aea0`.
- Source bundle: 96301 bytes, SHA-256 `4332367b24e1fda29ae7955a3439a12cf6b880d526ee59b7d4b13829526260f1`.
- Native evidence ZIP: 21235 bytes, SHA-256 `9af189a2abf3102c02ca6d33d44ac494c974fc84d09744af8269e0a34f9ce8b1`.

Both complete original ZIPs are included under `windows/`, alongside the raw extracted logs/reports, commands, inner return codes, volume observation and source manifest. This deliberately retains 117536 bytes of binary transport custody; it is not hidden or omitted as a duplicate. The empty `windows/native/reports/packets` extraction entry reflects the archive's empty directory entry and is not asserted as an additional product report file. The authoritative product-file inventory is the native JSON hash map, and the original archive is retained unchanged.

`drivers/receive_freight_headers.py` is the exact receiving driver. `drivers/transport_freight_headers.py` is the exact one-shot carrier, including source packaging, strict known-host SSH/SCP routing, native PowerShell setup, process launch and evidence export. They are archived receiving procedures, not normal test-discovery modules. The original seven-case Linux reproduction driver and complete synthetic inputs/outputs are included too. Do not rerun an exclusive receiving namespace.

## Limits and ownership

A conflict raises ValueError through the existing CLI, which presently gives exit 1 and a traceback ending with the descriptive error. The pipeline may create its output/packets directories before input validation; the asserted guarantee is preservation of existing generated file/audit bytes, not zero filesystem effects. This packet does not qualify concurrent writers, power-loss behavior, arbitrary malformed CSV, real carrier exports, payment approval, browser workflows or deployment.

Fresh existing GitHub/native ownership evidence found no competing header claim before issue 28 and native Conscience claim seq 4113 (`cev_05df869f8e714caf86456ba6`) were registered under `chatgpt:/root/migration_execution`. The published ownership summary preserves the external coverage gap and source references. Other owners' broad native coordination payloads are retained privately, not republished in this product packet. Existing review-download, invoice matching, settlement and other project ownership are preserved.

The complete source changes and raw qualification were produced in an owned tmpfs workspace because the ThinkPad's persistent data volume had no free space. Native Windows custody and qualified Git publication retain the result independently of that volatile workspace. Installation, service changes, migration/cutover, firmware action and live customer data mutation remain false. `file-inventory.json` hashes every packet payload except itself; Git binds the inventory's own bytes without a circular self-checksum.
