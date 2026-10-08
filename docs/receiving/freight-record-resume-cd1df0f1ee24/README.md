# Freight saved-record resume: draft receiving index

Issue: [workflow-checks #60](https://github.com/Jacob-Met/workflow-checks/issues/60).

This draft adds an explicit review route for an existing `workflow-checks.freight-whatif.v1` export. Opening checks its source pins, canonical baseline, sixteen inputs and freshly recomputed results. A read-only preview precedes Replace current scenario; cancellation, refusal and retired reads preserve the current draft. The Freight model and data remain unchanged.

**Delivery is incomplete.** The native browser attempt's final status and output have not been received after its host went offline. The current release ZIP is deliberately unchanged and therefore does not contain saved-record resume. This draft is not ready for acceptance or merge.

## Source custody

- [source-transport-v1.json](source-transport-v1.json): exact original 120,335-byte UTF-8 checkpoint, Git blob `6641513ee86a27c0e9481e6555019bada8e2c38b`, SHA-256 `ec460ed26466d0e1053c9a5f0578711d05898b5589fdd6a5ce86125db90460a3`. Contains all ten original source files (eight changed/new plus protected model/data), the one-step workflow change and explicit evidence boundaries.
- [source-manifest.json](source-manifest.json): all thirteen proposed product/test/doc/workflow paths. The four hosted mirrors have exactly the same bodies as their source runtime files, including the new sixth module.
- [readme-historical-clarification.json](readme-historical-clarification.json): two precise documentation-only successors clarify the original contribution's historical attribution and warn in Run it that the current ZIP lacks Open saved record. Both changes are recorded separately; the original README body and hashes remain in the transport.
- [composition-plan.json](composition-plan.json): exact source parent, complete nontruncated parent-tree boundary, planned overlay and protected delivery objects. The publication readback must verify every parent leaf outside the overlay remains exact.

The original claim baseline was `39ea75b0da2a7c3463e426dd32ba52860966cae4`. Source staging used `11e159f914617517e2322bdeb89de5e27007dcc5`; all five original Freight runtime files matched the claim baseline. This draft is based on `66030b1f930906d0b42fa46fc0a74c06678ec964`, tree `e38916e0e104a38bda1e225c64ea2a6b1aafc015`. Its incoming PT CSV-header contribution is preserved.

## Completed receiving, with raw evidence still pending recovery

These are the already observed outcomes recorded in the source transport, not new runs on the hosted draft:

| Gate | Observed outcome |
| --- | --- |
| Authored importer tests | 9 groups passed; Node 22.22.1, explicit exit 0, empty stderr |
| Independent importer admission | 131 cases passed: 28 accepted and 103 refused; explicit exit 0, empty stderr |
| Independent UI-state source review | Frozen app and HTML accepted without correction |
| Existing installer tests | Six controls passed; explicit exit 0, empty stderr |
| Actual ZIP packager | Explicit exit 0, empty stderr; every archived entry read back exactly |
| Source custody | Completed native runs retained identical before/after source pins |

The native author root is `/dev/shm/hamon-freight-source-cd1df0f1ee24` on d55. Its delivery receipt has SHA-256 `0daa91bc2f3adc3dd0a30ab6bf3b427c56df8e08ac07bd28b8ef6dc466987287`. The generated replacement ZIP is 29,559 bytes, SHA-256 `51a97be506fc3900e05b487939171fca8e63d701ccd4cfa070b9e55096f737d6`. Those raw receipts, logs and ZIP bytes are not included here because they have not been recovered from the offline host. No missing evidence body has been reconstructed.

The maintained repository ZIP remains Git blob `2a7e2b8f4b4abe5063c65befb7f74b0d6533387b` (24,333 bytes). Keep it unchanged until the replacement's actual bytes can be recovered and verified. Historical evidence ZIPs are also unchanged.

## Unresolved browser attempt

[browser-receiver-v4.mjs](browser-receiver-v4.mjs) is the unchanged independent receiver source: 29,352 bytes, Git blob `1e08bd4be25e149d568f1869c610b20f03fc6ac9`, SHA-256 `d44e2d17eeb3e583d11e856fbda1bb988d9ec8f871bf40e3f33f2b5425d333d8`. It retains seventeen frozen browser groups and an independent source-first design. It is preserved as evidence, **not presented as a self-contained runnable maintained suite**.

One attempt was launched on the exact frozen UI. The last successful status read showed a fresh profile; no completed group, final exit, browser receipt or capture was received before d55 went offline. No pass or failure is inferred, and no retry has been run.

Outstanding custody:
- Driver/config: `/dev/shm/hamon-freight-receiving-cd1df0f1ee24/browser-native/`.
- Config `config-ui-v1-attempt1.json`: SHA-256 `7d4c33189b8b01f2012e3ad700d3b3d7ef900cff98296cf356646ac7cb04bcfe`.
- Raw wrapper destination: `attempt1-process/`; wrapper PID 1598266, recorded Node PID 1598733.
- Browser output/profile: `/home/jacob/hamon-freight-browser-cd1df0f1ee24/attempt1/`.
- Explicit limits: 45-second launch, 240-second receiver and 255-second owned-process supervisor.

For later maintained delivery, recover the eight frozen fixture bodies and index, five original baseline runtime files or explicit immutable offline reconstruction, and caller-local configuration with exact source/fixture pins. Source-root labels alone do not define HTTP routes. The host-specific supervisor belongs in evidence. Linux/Chromium keyboard behavior is the intended runtime boundary; a DOM cancel event is not an OS-picker gesture claim.

## Remaining gates

1. Recover and classify the already launched browser attempt using its actual logs, process result, downloads and captures.
2. Recover intact author and independent evidence packets and bind them to the published source.
3. Recover/read back the generated ZIP before replacing the maintained dist deliverable.
4. Make the browser regression package complete before describing it as runnable.
5. Verify exact hosted CI checkout and full current-parent preservation; retain draft status until independent source, delivery and browser acceptance are complete.

The original engine, layout and earlier delivery receipts retain their own source and contributor attribution. This packet does not recast those historical results as importer qualification.
