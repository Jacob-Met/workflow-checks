# Freight CSV column admission

Freight refuses repeated column names before these CSV readers construct their data rows. A mapping with two columns called `pod_received`, for example, would otherwise keep only the later value. That can remove a missing-document hold even though the first cell still says N.

The error names the input file, the conflicting column names and their one-based column positions. Correct the source export so that the intended column is unambiguous, then rerun the existing command. Freight does not choose between conflicting cells or merge them.

| Input reader | Header comparison |
| --- | --- |
| Load records (`loads.csv`) | Exact column names |
| Carrier invoices (`carrier_invoices.csv`) | Exact column names |
| Geofence telematics CSV | Existing whitespace trimming and lowercase comparison |
| Tracking-stop CSV | Existing whitespace trimming and lowercase comparison |

Thus `Time` and ` time ` conflict in a geofence export. Fixed-schema load and invoice readers retain their existing exact-name behavior: an extra column called `POD_RECEIVED` is not the `pod_received` input. Ordinary distinct extra columns remain accepted. Where a template includes different supported aliases, the existing alias priority still selects the field; this check does not change that selection.

CSV quoting and the existing UTF-8 BOM handling are preserved. Even equal cell values or a header-only file do not make repeated column names unambiguous. The check concerns the parsed header fields, so a quoted comma in a column name is handled by the standard CSV reader.

Value trimming, timestamps, amounts, multiline invoice grouping, load identity, eligibility and settlement calculations keep their existing contracts. A refused header does not replace the previous report files. The ordinary run may still create its output directories before input validation; this is not a directory transaction or a snapshot across changing input files.

This admission applies to the four CSV entrypoints in `freightpkt.ingest`. Telematics JSON and the separate fines, document and dispute loaders retain their existing behavior. It does not add missing-column, row-shape or new value-validation rules.

The maintained regression is `tests/test_csv_header_admission.py`. Its product control retains a synthetic missing-POD settlement on HOLD and verifies that an ambiguous rerun leaves every prior report artifact and the input bytes intact.
