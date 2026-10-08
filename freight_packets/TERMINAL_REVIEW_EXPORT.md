# Export saved Freight reviews from the terminal

Use `export-reviews` to retain an explicitly selected set of saved load reviews in one offline ZIP. It reads an existing generated output directory and uses the same per-load exporter and batch assembler as the local review application. The archive contains the original review ZIP and its five unchanged member files for every selected load, together with the shared batch index and manifest.

Run from `freight_packets`:

```sh
python -m freightpkt export-reviews \
  --out ./out \
  --load 'LD260901' \
  --load 'LD260905' \
  --destination ../handoffs/reviewed-loads.zip
```

The destination's parent must already exist and be outside the source output directory. Choose a new destination filename. The command will refuse an existing file, directory or symlink, including one created by another writer during export.

Supply each exact load ID through a separate `--load`. The selection contains between 1 and 100 unique, nonempty IDs and is sorted by literal ID for a stable terminal set order. Each ID must identify exactly one readable saved packet. The caller follows the summary's `packets[].file` value, including opaque allocated filenames; it never derives a filename from an ID. IDs that would produce similar display or download labels remain distinct in the shared archive's ordinal directories.

## What is retained

The shared `build_batch_bundle` is the sole archive assembler. Each selected load has a fixed `loads/0001/`, `loads/0002/`, … directory containing:

- `index.html`, `packet.html`, `evidence.json`, `review.json` and `manifest.json`: the exact native per-load member bytes.
- `review.zip`: the exact original per-load ZIP, including its native filename recorded by the shared manifest.

The top-level `index.html` links to the included saved reviews and original ZIPs. Extract the complete archive before opening it. The shared manifest records the selected evidence and review identities and file checksums. The terminal does not add a second manifest schema, provenance fields or another archive member.

Saved current, stale, unbound, cleared and unreviewed meanings come from the existing per-load exporter. An earlier or unbound approval does not become a current approval. The command does not generate fresh packets, edit reviewer notes or decisions, start the browser/server, send the handoff, or operate a financial system. This remains a draft review snapshot, not a payment instruction.

## Separate capture receipt

After publishing the complete ZIP, the command prints one JSON receipt to stdout. It contains:

| Field | Meaning |
| --- | --- |
| `schema` | `freight-review-terminal-export.v1` |
| `count` | Number of selected reviews |
| `destination` | Absolute destination built from its resolved existing parent and chosen filename |
| `archive_filename` | Exact suggested filename returned by the shared batch assembler |
| `archive_bytes`, `archive_sha256` | Byte length and SHA-256 of the delivered ZIP |
| `source_summary_sha256` | SHA-256 of the captured raw `summary.json` bytes |
| `source_decisions_sha256` | SHA-256 of the captured raw `decisions.json`, or JSON `null` when absent |
| `identities` | Sorted selection with each native `load_id`, `evidence_version` and `review_version` |

The caller uses ASCII-escaped, sorted-key JSON with two-space indentation and one final newline. There is no additional success text or automatically created sidecar. You may retain stdout separately with normal shell redirection, choosing a path that does not overwrite a source file or the archive destination. Shell redirection happens before the program starts and is outside the caller's destination checks.

Capture hashes identify the observed local bytes. They do not authenticate an author, prove external approval or establish that original inputs are current. Original input files, unselected packet bodies and the global audit log are excluded from the archive.

## Source capture and limits

The command captures `summary.json`, optional `decisions.json`, and the selected packet files into its own temporary view. All saved JSON must be an object with no duplicate keys or non-finite numeric values. The existing application still validates the native summary and decision structures. Capture paths must resolve to regular files inside the source output directory.

Consumer limits contain the request before destination publication:

| Limit | Maximum |
| --- | ---: |
| Explicit unique load IDs | 100 |
| Each saved JSON file | 16 MiB |
| Each selected packet | 8 MiB |
| Total unique captured source bytes | 64 MiB |
| Native decoded constituent bytes plus retained original ZIP bytes | 128 MiB |
| Complete shared ZIP's decoded member bytes | 128 MiB |
| Complete shared ZIP bytes | 129 MiB |

These are terminal consumer limits; the shared producer and its format are unchanged. They are admission/output bounds, not a claim that process peak memory equals the archive byte limit.

The private view supplies the existing `App.summary` and `App.review_bundle` with captured source, then passes the exact identity/filename/ZIP tuples to the shared assembler. It uses no original-input directory or first-run initializer. Before publication, the caller rereads captured paths and bytes and checks whether a previously absent decisions file appeared. An observed change refuses the export. These checks do not hold the running browser server's lock, create a cross-process lease, prevent hostile parent-directory races or guarantee freshness after the last check.

## Delivery and failure behavior

All selections and the complete archive are validated before publication. The caller writes and flushes the archive in an owned temporary sibling directory, calls `fsync` on the staged file, rechecks captured source, and links the complete file to the new destination without replacing another writer's entry. It removes only its own staging. Unsupported link behavior or storage/write failure refuses the operation; there is no overwrite fallback.

A failure before the link leaves no archive at the requested destination. Existing sources and race-winning destination entries remain intact. A post-publication failure is different: the complete ZIP already exists. In particular, failure to write or flush the stdout receipt returns exit code 2 and reports that the archive was published, when stderr is available. The archive stays in place; a retry to the same destination refuses and preserves it. A rare staging-cleanup failure after publication is also identified as already published. A nonzero exit is therefore not proof that no archive was delivered.

The earlier, non-adopted terminal offer independently produced exit code 120 when stdout was `/dev/full`, after publishing a complete archive. That historical observation remains in its original evidence. This caller explicitly flushes the separate JSON receipt and handles the same delivery boundary with exit code 2; the old result is not relabeled as a result of this implementation.

## Python use

```python
from pathlib import Path
from freightpkt.terminal_review_export import export_reviews

receipt = export_reviews(
    Path("out"),
    ["LD260901", "LD260905"],
    Path("../handoffs/reviewed-loads.zip"),
)
```

The helper returns the same receipt dictionary after publication. It raises clean admission or filesystem errors instead of returning a partial selection. It does not write stdout. Existing native calculations, review-state projection, browser selection and locking remain with their original producers.
