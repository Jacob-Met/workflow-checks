# Independent receiving: saved Freight review comparison

Accepted the exact four-path source candidate carried by SHA-256 `14882de031e421460183b40c67d8bfb1429a6e008d65ba7b4c11973c3421bfd2`, with runtime Git blob `0d32c0574bda267f7066ec6ee673f15eefdaefde`. No source correction is requested.

The feature gives billing and settlement reviewers a complete comparison of two retained per-load handoffs. The production command is documented in `freight_packets/REVIEW_COMPARE.md`. This packet is independent receiving evidence for ordinary source integration; it is not a deployment or a live review action.

## Independent expectations and result

Before reading the candidate or its tests, the reviewer executed the unchanged `handoff.py` producer from workflow-checks main `125339ec63eeb7c4989c9b240c01202555dce573`. The sealed 64,371-byte oracle has SHA-256 `330f8969404d3987f1e01c204dfa36c192e8440e9d4af48c0b4003b5578d4de1` and was frozen at 2026-10-08T16:21:58.767374Z. Its gzip/base64 bytes and all nine exact authored input ZIPs are retained in `receiving/input.json`; decompress `oracle_gzip_base64` to obtain the exact original JSON.

The completed normal-CPython receiving makes **497 checks** across seven comparisons and six refusal controls. It verifies every native source/member identity and the full rendered records and saved objects:

- Same-copy identity and changed departure with unchanged section counts.
- Two versus four identical stop occurrences, plus a common literal record.
- Separate JSON zero, false, null, string zero, floating zero and negative floating zero.
- Packet-only, saved-review-only and container-only changes.
- Supplied A/B ordering when B has an earlier recorded timestamp.
- Complete unknown nested fields, source-row strings, Unicode, markup, newlines and a legacy surrogate in saved notes.
- Refusal of unbound payload bytes, rebound outer manifests with stale canonical evidence or review identity, duplicate JSON keys, an extra traversal member, and different internally valid load IDs.

Actual rendered HTML is parsed and checked for complete section counts, full JSON values, identities and member bindings. Only internal section anchors are active; supplied packet/cover markup is not embedded. These are HTML-structure checks, with no graphical browser or printing claim.

## Source and filesystem boundaries

All six physical candidate/dependency files matched their frozen pins before and after receiving. The README change is one 703-byte additive insertion; deleting it recovers the exact CRLF predecessor. The native producer, package initializer and ordinary App/pipeline/rule interfaces are preserved.

The independent filesystem gate observed zero available bytes, below its fixed 96 KiB floor. This reviewer therefore performed **zero output writes and zero CLI subprocess calls**. Source review confirms both-input validation and complete rendering precede exclusive creation.

The author separately ran three real-filesystem methods in normal and optimized modes and one actual `python -B -S -m freightpkt.review_compare` from an unrelated directory. The reviewer read those receipts and independently matched their retained A/B ZIP and 9,042-byte report hashes, sizes, inodes and modification times. Their actual command receipt is SHA-256 `7187ba81aa2f9d77ba829e1aef203c02385a80046c013190e86a81845347200d`; its report is `ad0b265b7f7abc5368e35bf02749bbbdb4759f9bc47b09f10f30b08433c68c3e`. Those runs remain author-attributed.

## Preserved failed reviewer control and limits

The first reviewer driver incorrectly expected alphabetically serialized oracle keys to define presentation order. Its failure is retained, together with an exact patch from that driver to the accepted version. The correction uses the original App section order only; the oracle and candidate bytes never changed. A separate tool-carrier lone-surrogate serialization limit is recorded in `run-observations.json`.

The checks establish internally bound retained copies, not authenticated authorship, freshness or current approval. The command reads complete inputs in memory and does not promise a resource bound or protection against concurrent source mutation. Existing targets are refused; a later storage failure can retain a partial new target. No automatic cleanup or atomic publication is claimed. No inherited suite, author test body, live data, App/server, provider, browser or native matrix was executed by this reviewer.

The source inputs and harness paths are historical locators. The scripts preserve the exact reviewed experiment; they are not a new supported portable CLI. Root retains fresh-parent composition, repository CI and source integration.
