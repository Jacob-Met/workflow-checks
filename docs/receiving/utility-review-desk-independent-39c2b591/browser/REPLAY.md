# Replay and decode

The compact publication preserves all raw files, including exact downloaded CSVs, PNGs, original failures, all receiver versions, independent fixture/oracle, original native inputs and source intake receipts. `RAW_EVIDENCE.json.gz.b64` is a deterministic gzip/base64 encoding of one JSON file container. `RAW_EVIDENCE_MANIFEST.json` records encoded, compressed and decoded SHA-256 values plus every raw leaf. `unpack-receiving.py` verifies each layer and every file before creating a new output directory. It refuses an existing output.

## Inspect without rerunning

```sh
python3 unpack-receiving.py RAW_EVIDENCE.json.gz.b64 RAW_EVIDENCE_MANIFEST.json /ABSOLUTE/NEW/decoded
```

Then inspect `decoded/native-run/evidence-v2/browser-receipt.json`, both `*-native-validation.json` receipts, `filtered-complete-actual-download.csv`, `restored-source-actual-download.csv`, and the three PNGs. `native-run/evidence-v1/browser-failure.json` and `DRIVER_CORRECTION_V4.json` retain the first candidate failure. `CANDIDATE_SOURCE.json` maps all 355 executed source leaves.

## Re-execute only when an affected source change needs it

Obtain a separate clean checkout of exact candidate commit `fa057a67c428fb6ccd1517e7f9eb51d946ab12d6`, tree `9124788f2224f99f153642754c6dc832ed4762c2`, from the original author bundle or retained native candidate. Its source is complete; history before the declared shallow parent `9e931fa9` is not supplied. The native receiving lineage remains preserved separately.

The complete-tree portable bundle instead uses two explicitly separate snapshot commits: a source snapshot with exact tree `9124788f`, then a receiving snapshot with the evidence append. Their full pins are in `FINAL_HANDOFF.json` beside that bundle. For this route, detach the source snapshot before replay. The driver enforces the exact source tree, while `UTILITY_DESK_FROZEN_COMMIT` identifies the original executed native candidate. A snapshot replay is a new result on byte-identical source, not a claim of original public ancestry. Do not use either receiving commit as the candidate tree: it adds evidence paths.

The decoded fixture and original `baseline-source/utility_watch` are sufficient for the receiver; they must remain unchanged. The verifier finds `BASELINE_SOURCE.json` beside `fixture-v1`. Copy the two exposed driver/verifier files together only if not using their copies already in the decoded root.

On the qualified ThinkPad route, prepare a new owned directory whose prefix is `/dev/shm/snap.chromium.`. Its `profiles`, `temp`, and new `evidence` subdirectories are only for this replay. Set these exact receiving inputs using real absolute paths:

```sh
UTILITY_DESK_FROZEN_COMMIT=fa057a67c428fb6ccd1517e7f9eb51d946ab12d6 \
UTILITY_DESK_SOURCE_TREE=9124788f2224f99f153642754c6dc832ed4762c2 \
UTILITY_DESK_CHROMIUM=/snap/bin/chromium \
UTILITY_DESK_PROFILE_ROOT=/ABSOLUTE/OWNED/profiles \
UTILITY_DESK_EVIDENCE_DIR=/ABSOLUTE/OWNED/NEW/evidence \
TMPDIR=/ABSOLUTE/OWNED/temp \
PYTHONDONTWRITEBYTECODE=1 \
node /ABSOLUTE/decoded/utility-desk-consumer-v4.mjs \
 /ABSOLUTE/CLEAN/EXACT_CANDIDATE \
 /ABSOLUTE/decoded/fixture-v1 \
 /ABSOLUTE/decoded/baseline-source
```

The driver starts the actual loopback review-desk command, uses real browser downloads and invokes the original native verifier/reconciliation. Its successful execution performs six groups; it does not run a separate renderer probe or the entire native checker suite. The temporary selected CSV is a copy made inside new evidence. The fixed original source worksheet is never edited.

Node 22.22.1 supplied native WebSocket and Chromium was 153.0.8010.47 snap. The process uses existing sandbox permissions with the supported shared-memory prefix. Do not add `--disable-dev-shm-usage`, alter AppArmor, change permissions, reuse another author’s profile or write into the author’s checkout. Other environments require their own legitimate installed-browser path; their execution is a new receiving result.

Do not reuse the original-engine reconciliation oracle as an expectation for a changed engine. Use the exact source map and the current author’s bounded composition gate to decide which assertions remain applicable.
