# Freight ambiguous CSV header repair — native qualification

A repeated pod_received column can silently remove a missing-document hold because the CSV mapping keeps its later cell. The actual original Mac CLI returned zero for both inputs: invoice CAL-7122 / load LD261054 changed from HOLD to READY while the original N cell remained. Its net stayed 260300 cents. The exact report and reproducer are retained under retained-mac; original full Mac input/output/process custody remains on that unavailable host and is not claimed recovered here.

The repair validates headers before row mapping in four freightpkt.ingest CSV readers. Load/invoice names compare exactly; telematics/tracking use their existing strip/lower convention. It preserves distinct alias priority, value parsing, money, multiline invoices, grouping, JSON and settlement contracts. CSV_HEADERS.md describes admission and limits. No fines/document/dispute reader or UI/CLI/rule writer is changed.

## Native evidence

Original public pin 76e6175d91320ac816cee019df969c0f0e1bbfc7 is an explicit 33-file partial closure. The retained Mac import tree was reproduced exactly on Windows. Original ingest blob dad18f470035318241a9c432326d1f4bafa26edf remains unchanged on the later main inspected for publication.

Native baseline import 690827796354da066e3c0e16820c1aed5678462e, frozen test-only 6111a94356901c75f3274182f411d40ab61e31c6, and candidate d9ab19be7e2fd1742ad90889c41aff3d0c93f00f / tree fb7647c0f8c6ae5403df5f9ab0c4dbf5cfde1a81 are retained in the source Git bundle before packet composition.

The same 12 maintained methods on Windows 3.11.9 produce 16 failure entries across 6 methods before repair, with 6 other methods passing; candidate passes all 12 with no skips/errors. Failure entries include subtests, not separately collected methods. Both source maps are unchanged by execution.

Actual candidate CLI generator/valid-source/duplicate-header-rerun exits are 0 / 0 / 1. The refusal names loads.csv and the conflicting sixth/ninth columns. All 22 prior output artifacts, 68 input files and 36 source files remain byte-identical. The retained settlement stays HOLD with MISSING_POD. Detailed receipt and raw streams are under windows/cli-candidate.

Processes use installed Python 3.11.9 on DESKTOP-LA7CMTA/Windows 10 build 19045 through direct RDC as NT AUTHORITY\SYSTEM. Interpreter/site isolation and exact paths are recorded. No dependency or interpreter was installed. Original red gate, candidate gate, source patch, receiving drivers, Mac ENOSPC interruption and process codes remain separate. Native unittest qualification is not the full repository hosted Python 3.10/3.12 gate.

## Review and integration boundary

Independent review and exact public-head hosted gates are pending at this checkpoint. Publication will transplant only three owned source/test/guide paths and this unique evidence directory onto fresh full main, preserving other owners. Receiving drivers are .py.txt; no extra test collection path is introduced.

The fixtures/output ZIP preserves all synthetic CLI inputs and unchanged reports. packet-manifest.json inventories packet files and ZIP members, excluding its own checksum. No atomic directory publication or concurrent-input snapshot is claimed. Invalid headers preserve earlier report files; ordinary output-directory creation can still precede validation.

No real client/financial data, payment, service, deployment, account change, firmware action or migration/cutover occurred.
