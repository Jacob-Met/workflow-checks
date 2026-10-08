# Canonical Freight terminal caller contract

This contract is frozen before the new caller and its tests are authored. It replaces the old proposed outer format with the published pure `build_batch_bundle` API. Root authorized this distinct caller at workflow-checks issue37 comment6064195824 after PR47 merged; no direct owner agreement is asserted. The old offer and its independent results remain historical and unchanged.

## Exact baseline and source fence

Repository: Jacob-Met/workflow-checks. Current main is 995a48cd92ebf1202fea08e08f90c7ce010ca424, tree3f50ec92b2dcf5c0d3351f0687eb1dbc7f5c0f05. The latest change is additive Utility source inspection. The published Freight producer pins are batch_handoff.py 2ae68efdfe0c0c45135e2a5764749a5444da62d7; web.py 9215adc3241f722344a452b4f789a4a5b59a25ec; handoff.py bdcb63507b57d07eed1a6598d7d37d5f5d9db802; cli.py a64a4d60816654595b1767ff9f96cd2cd9c49c32. These are independently checked against current primary bytes before source staging.

Only new freight_packets/freightpkt/terminal_review_export.py, new freight_packets/tests/test_terminal_review_export.py, standalone freight_packets/TERMINAL_REVIEW_EXPORT.md, unique qualification evidence and the narrow export-reviews parser/dispatch addition to freight_packets/freightpkt/cli.py may change. Shared batch/browser/handoff/README/pipeline/packet allocator files are preserved.

## Caller and archive

The direct helper is `export_reviews(out_dir: Path, load_ids: list[str], destination: Path) -> dict` in the new module. The CLI is `python -m freightpkt export-reviews --out SAVED --load EXACT_ID [--load EXACT_ID ...] --destination NEW.zip`.

The request is an explicit set of1–100 unique, nonempty string IDs. The caller uses sorted literal ID order. It captures strict saved summary.json, optional decisions.json, and only the packets selected through the literal packet.file mapping. It never reconstructs filenames from IDs. Duplicate JSON keys/nonfinite values, missing or ambiguous selections, outside-source or nonregular captured paths, and observed source changes refuse before publication.

The captured private view uses actual App.summary and App.review_bundle. For every selected ID, obtain its current captured evidence_version and review_version, then call the native review_bundle with those exact values. Feed the resulting identity dictionary, native filename and native ZIP bytes to the unchanged `build_batch_bundle(list[tuple[dict, str, bytes]]) -> tuple[str, bytes]`. Its exact bytes and returned filename remain canonical; the caller does not construct or add archive members, labels or manifest fields. The private view has no live-server or cross-process lease. No generation, review writing, browser, server or external delivery is requested.

## Exact result and stdout schema

The helper returns exactly these fields after successful archive publication:

~~~json
{
  "schema": "freight-review-terminal-export.v1",
  "count": 2,
  "destination": "/resolved/parent/new.zip",
  "archive_filename": "the exact filename returned by build_batch_bundle",
  "archive_bytes": 123,
  "archive_sha256": "lowercase sha256 of the exact delivered ZIP",
  "source_summary_sha256": "lowercase sha256 of captured summary.json bytes",
  "source_decisions_sha256": null,
  "identities": [
    {"load_id": "literal ID", "evidence_version": "native64hex", "review_version": "native64hex"}
  ]
}
~~~

`source_decisions_sha256` is null only when decisions.json was absent; otherwise it hashes those exact captured bytes. `identities` follows the sorted literal selection order; each entry has exactly the three fields required by the canonical assembler. `destination` is the normalized absolute destination constructed from its resolved existing parent and literal filename. Count equals identities length. The separate CLI receipt is `json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False)` plus one LF; no extra success text. Captured hashes are observations, not authentication or approval. The receipt is not a second archive format or a sidecar file.

## Bounds, custody and delivery

Each saved JSON file is capped at16MiB, each selected packet at8MiB, and the total unique capture at64MiB. Native constituent decoded content and original ZIP retention are capped at128MiB before invoking the shared assembler. The complete shared archive's decoded member sum is capped at128MiB, and its ZIP bytes at129MiB before publication. These are terminal admission limits, not changes to shared producer semantics. All selections and the complete archive are admitted before a destination is linked.

The destination must have an existing parent outside the source output and must not already exist, including symlinks. Capture/recheck uses bounded regular-file reads. Private captured source and archive staging are under an owned temporary sibling directory. Write/flush/fsync the full returned ZIP; recheck all captured source paths/bytes and absent decisions; then atomically link the staged file without clobber. A race winner is preserved. Cleanup is restricted to owned staging. Before-publication failures leave no delivered archive and preserve source bytes; no cross-process freshness lease is claimed.

Publication precedes the stdout receipt. New CLI receipt write/flush failure returns2 with an explicit published-archive diagnostic when stderr is available; the complete delivered ZIP stays in place, and a retry to that destination refuses. This preserves the substantive old observed boundary, whose frozen implementation returned120 after stdout=/dev/full. Do not relabel that old120 receipt as new2, claim all nonzero exits mean no delivery, or promise rollback after publication.

No source or authored tests existed when this document was frozen. Independent receiving is to freeze canonical archive and stdout expectations before reading the new caller/test source. The old App oracle may be reused only where its producer and fixture bytes match; canonical outer-archive qualification must run the actual current published assembler.
