# Independent receiving: canonical Freight terminal export

**ACCEPT, with revision boundaries preserved.** One actual call to the published shared batch assembler supplied the canonical reference. Six independently designed actual CLI processes accepted the original terminal caller. The later report-row guard is accepted through an exact source/data proof and independent inspection of the author's two recorded CLI outcomes. The six original processes were not repeated or attributed to the revised source. Publication, current merge composition, hosted execution and source-owner adoption are subsequent gates.

## Source and oracle custody

The oracle was frozen before reading the new terminal caller or its tests. `oracle-manifest.json` has SHA-256 `20b2323561353eaa4418cabe2e5573d8920a5e864c9c7b848400848a83f3f043` and binds 25 payloads, the complete fixture, public-seam receiver and canonical reference. The published assembler is Git blob `2ae68efdfe0c0c45135e2a5764749a5444da62d7` from `Jacob-Met/workflow-checks`; the base was `995a48cd92ebf1202fea08e08f90c7ce010ca424`.

Eleven original fixture/per-load payloads were reused only after comparison with the retained historical archive. The per-load handoff source and every existing `App` method were unchanged. No old App, missing-capability, fault matrix or whole-suite execution was repeated. Literal IDs `Dock/A<&"` and `Dock?A<&"` use opaque, unrelated `packet.file` names and colliding sanitized labels. One saved approval is current and one is stale. A third unselected packet must remain absent from every exported member.

The actual shared assembler returned `freight-review-batch-2-4025e069efc5.zip`: **33,061 bytes**, SHA-256 `6f61713c9e7d32a631f98147a635421ab5f366ffee2fba100cf5fd98944ee026`. The reference checks all 14 members, 13 manifest checksums, both exact constituent ZIPs, ten native constituent files, saved identities/status/history and literal packet mapping. Source capture hashes remain solely in the caller's separate stdout receipt; the archive and schema stay canonical.

## Six actual CLI processes at R1

The original caller is blob `89f49004173305804330443b87dc04b5d97ab149`, SHA-256 `d82b9ce962f09612c4456f2aca9d4d2d0bc4fd75f8196741cb8d37435ecc9ef8`. Its CLI is blob `27c299e31ff8db27e6126f36c4773c6c613c83aa`, SHA-256 `a5526591bd58702578dc3d90bd1bed908f6816404a3d452df1f2e7dc8ed1399d`.

| Process | Observed result |
|---|---|
| Reverse-order selected IDs | Exit 0; entire ZIP equals the canonical reference; exact sorted stdout receipt; source unchanged. |
| Selected source resolves to a new path containing identical bytes | Exit 2 after actual assembly; no publication; externally replaced path remains intact. |
| Previously absent decisions appear after capture | Exit 2; no publication; external decisions remain intact; the interim actual canonical archive has unreviewed constituent states. |
| Another writer creates the destination after assembly | Exit 2; winner's bytes, inode, mode and modification time preserved. |
| Receipt writes to `/dev/full` | Clean exit 2 with explicit already-published diagnostic; the complete canonical ZIP remains delivered; no traceback. |
| Retry after receipt failure | Exit 2; delivered archive and its inode, mode and modification time preserved. |

Three interleavings wrap the **public** `build_batch_bundle`, execute the actual published implementation first, record its inputs/result, then inject an external change before returning to the caller. They do not patch private caller helpers or claim a cross-process lease. The other cases invoke the real `python -m freightpkt` CLI. Raw stdout, stderr, requests, probes, delivered artifacts and custody records are retained. Receipt `receiving-r1.json` has SHA-256 `b3fee2c04da65cea26a7d714bcc24a4974a2e892eaee424290dcaa345552ce08`.

## Narrow R2 guard supplement

Final module `676159e8a79d00143b9e6b69ba94740489b1794d` has SHA-256 `c697780be9bb7d1d6e3182c9419fe316f833c8148b14ff5c174266b9b5fb2db5`. It adds only the native `REVIEW_SECTIONS` import and four-line list-of-dict admission guard. The CLI, all later capture/App/per-load/assembler/receipt/recheck/publication bytes and 28 other candidate files remain exact. Every frozen independent fixture section satisfies the added guard.

The author retained the original `flags: [null]` traceback (exit 1, no destination/source mutation). We independently decoded its byte-identical revised input and verified clean exit 2, no traceback or publication, plus the author's valid-empty control's exact canonical ZIP and unchanged inputs. This is **two recorded author CLI processes received and zero additional independent native processes**. `guard-r2-receipt.json` has SHA-256 `8cc5a55d19e82193c9c84f8b984b0f62e1733c138bcda4bce8594f3c033b8778`.

The old held caller and old-format exit 120 after delivery remain historical evidence under the enclosing packet's `historical/` directories. That outcome is not a new-format qualification. No live account, server, dispatch, invoice, payment, browser or source-generation operation was performed.

## Verify and replay

`artifacts.json.gz.b64` is a content-addressed archive of all frozen oracle inputs and all independent native artifacts. `manifest.json` binds every packet file and shared source record. These scripts use the Python standard library and never install dependencies.

```sh
python3 -B verify_and_extract.py
python3 -B verify_and_extract.py --extract /tmp/freight-independent-evidence \
  --author-evidence .. --repository /path/to/exact/qualified/repository
```

Extraction requires a new directory. The optional shared author evidence is resolved relative to the enclosing `freight_packets/verification/terminal-review-export-0ee86eaeaf8d/` root. Its `source-snapshot.json` preserves the 27 baseline bodies; `native-r1/execution.json.gz.b64` preserves all 30 original R1 source images. These whole source/test snapshots are not duplicated here. Providing the exact repository additionally restores the final source-review view and checks every qualified file pin.

After extraction, the complete original six-process receiver can be replayed explicitly against the restored R1 source:

```sh
python3 -B /tmp/freight-independent-evidence/receive_canonical_terminal.py \
  --candidate /tmp/freight-independent-evidence/replay-r1-source/freight_packets \
  --module-sha256 d82b9ce962f09612c4456f2aca9d4d2d0bc4fd75f8196741cb8d37435ecc9ef8 \
  --cli-sha256 a5526591bd58702578dc3d90bd1bed908f6816404a3d452df1f2e7dc8ed1399d \
  --output /tmp/freight-independent-new-run
```

This receiver requires POSIX symlinks and `/dev/full`; qualification ran on Python 3.12.14. `HAMON_REVIEW_TMP` optionally selects its private temporary parent. Every replay output directory must be absent. A new run is a new result and must not overwrite the retained receipt.

The exact shared assembler reference is reproducible with `build_canonical_oracle.py --previous /tmp/freight-independent-evidence/replay-historical --source /tmp/freight-independent-evidence/canonical-source --output NEW_DIRECTORY`. The later guard supplement is reproducible without product execution using `review_guard_r2.py --author /tmp/freight-independent-evidence/replay-author --receiver /tmp/freight-independent-evidence --output NEW_DIRECTORY` after restoring the optional exact repository view.
