# Freight saved-record resume: draft receiving index

Issue: [workflow-checks #60](https://github.com/Jacob-Met/workflow-checks/issues/60).

This draft adds Open saved record, a read-only preview of all sixteen inputs, and explicit Replace current scenario. The existing v1 envelope is checked against pinned rules and the canonical starting case; saved results are recomputed through the unchanged model. Cancel, refusals and retired reads preserve the current raw draft.

**The original native six-runtime-file ZIP has now been recovered and independently accepted. Browser receiving remains incomplete, so this is still a draft.** No production or test run was repeated to recover the archive or evidence.

## Current source and delivered ZIP

The source workbench, hosted mirrors and maintained [release ZIP](../../../demos/freight-whatif/dist/freight-whatif.zip) contain the same six runtime files. The ZIP is the original 29,559-byte native artifact, SHA-256 `51a97be506fc3900e05b487939171fca8e63d701ccd4cfa070b9e55096f737d6`, Git blob `66c8f3cfac37164349f75bcd33fc6b57db83c58e`. Its original [package receipt](native-delivery/package-receipt.json) is also installed at the maintained bundle-receipt path.

[Independent ZIP acceptance](independent-zip/acceptance-native-v1.json) checks all eleven exact members, local/central/EOCD structure, modes, README, manifest and six runtime bodies against a [contract](independent-zip/contract-v1.json) frozen before receiving the archive. The [receiver](independent-zip/receive_zip.py) decoded the actual recovered bytes in memory; it did not extract or execute the ZIP. The old maintained receipt is retained [unchanged](history/bundle-receipt-before-resume.json), and all other historical bundle evidence remains intact.

The temporary Run it warning about the old ZIP was removed only after this acceptance. [That precise README successor](readme-delivery-successor.json) preserves all other text. The earlier two documentation changes remain in [their original record](readme-historical-clarification.json).

## Source and evidence boundaries

- [Original source transport](source-transport-v1.json): unchanged 120,335-byte checkpoint, Git `6641513ee86a27c0e9481e6555019bada8e2c38b`, SHA-256 `ec460ed26466d0e1053c9a5f0578711d05898b5589fdd6a5ce86125db90460a3`. Includes original v1 source/test/README bodies and exact protected model/data.
- [Initial draft source manifest](source-manifest.json) and [initial composition plan](composition-plan.json): unchanged historical records for first draft head `6da2c7c2867e6eeb9d11a097a14d977a2b010b70`. The later README and dist changes are explicitly recorded by the delivery successor manifest.
- [Delivery successor manifest](delivery-successor-manifest.json): current product/delivery pins, evidence payload and exact parent boundary for this update.
- [Original-native recovery manifest](native-delivery/recovery-manifest.json): read-only recovery origins, original file hashes, process receipts and explicit separation from the unexecuted hosted fallback.
- [Independent recovery index](independent-recovery-index.json): exact original admission archive/readable files and ZIP receiving objects. Its prepublication archive-readback status is preserved; publication verifies binary bodies separately.

The original claim baseline was `39ea75b0da2a7c3463e426dd32ba52860966cae4`; source staging used `11e159f914617517e2322bdeb89de5e27007dcc5`. The native production inputs match the corresponding later published PR67 blobs, but the original native runs are not represented as execution of a later Git commit.

## Completed native qualification

| Gate | Recorded result and evidence |
| --- | --- |
| Authored importer | [Receipt](author/receipt.json), [raw TAP](author/stdout.txt), [stderr](author/stderr.txt): Node 22.22.1, nine passed, zero failed/skipped, explicit exit 0, source unchanged |
| Independent admission | [131-case receipt](independent-admission/admission-candidate-v1-receipt.json): 28 accepts and 103 refusals passed, explicit exit 0, empty stderr |
| Independent source review | [Importer review](independent-admission/module-source-review-v1.json); UI-state review remains separately attributed |
| Installer | [Original receipt](native-delivery/installer-receipt.json), [stdout](native-delivery/installer.stdout.txt), [stderr](native-delivery/installer.stderr.txt): six controls, exit 0 |
| ZIP production | [Original receipt](native-delivery/package-receipt.json), [stdout](native-delivery/packager.stdout.txt), [stderr](native-delivery/packager.stderr.txt): exit 0, all archived entries exact |
| Delivery source preservation | [Combined receipt](native-delivery/receipt.json): Python 3.14.4, source before/after exact, both child exits 0 |

Original author and delivery runners are retained beside their receipts. Empty stderr files are the recovered originals, not synthesized placeholders. The [independent admission archive](independent-admission/admission-packet-v1.tar.gz) is the unchanged 86,837-byte packet, SHA-256 `256f3f69564e38210227507cfca863f63849df18276b88bb54bc68178c85336b`; its fifteen outer members and complete original preimplementation packet were independently verified after recovery.

## Failed browser attempt and remaining gate

The single original browser receiving attempt was recovered as a **failed execution**: the bounded supervisor timed out, Node exited -9 after 261.798 seconds. No completed group receipt, captures or downloads were found. Stderr includes DevTools listening, so the hang is not classified as a failure to obtain an endpoint. Its cause remains unclassified; there is no claim that no internal browser execution occurred.

[browser-receiver-v4.mjs](browser-receiver-v4.mjs) remains the unchanged seventeen-group receiver source. The [failed-attempt packet](browser-native/packet.tar.gz), [manifest](browser-native/manifest.json), [receipt](browser-native/receipt.json) and [guide](browser-native/README.md) preserve all sixty indexed payloads plus the manifest: preparation, eleven runtime inputs, eight canonical fixtures, raw output, supervisor result and separately authorized cleanup. All sixty-one archive members were read back exactly. This is failed-attempt custody, not browser acceptance. No browser retry was performed for this delivery update.

The original five runtime baseline inputs, eight frozen fixtures and caller-local configuration are required for a complete maintained receiver package. A receiver file alone is not advertised as a runnable suite. Any later execution must retain the same independent expectations and distinguish the failed attempt.

The hosted ZIP fallback was source-reviewed and checkpointed, but neither its workflow nor producer was published or executed because the original native archive was recovered. It is not the origin of the ZIP delivered here.

The first draft's hosted source gate passed on synthetic checkout `d4e8c5bfc6500b078ba6b98be128dd3b556aff51`, tree `cdc32c100179ceeedf97ecd89c112c3bb518f3ec`: 237 model checks, nine importer tests and six installer controls, plus the existing Python suites. This later evidence/delivery commit requires its own hosted checkout verification. Keep draft status until browser and final current-source receiving are accepted.
