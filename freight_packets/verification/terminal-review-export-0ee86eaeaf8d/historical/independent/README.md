# Independent receiving: frozen Freight terminal batch offer

**Native result: ACCEPT, with an explicit post-publication status-delivery boundary.**
Source/API/format adoption remains held for the browser owner’s agreement in
[workflow-checks #37](https://github.com/Jacob-Met/workflow-checks/issues/37).
This packet does not authorize a competing module, renamed implementation, branch,
browser route, or main integration. No remote write or live service call occurred.

## Exact qualified inputs

The original offer remains unchanged at
`coordination/freight-review-inspection/frozen-cli-offer/`.
Its manifest SHA-256 is
`9583fb235f29a2ed5ddc9c2f11b3409c71d91dcb3b798178f8424f3048964766`.
Its source base is commit `5b12dcd4c3a2c09d6602b2313e2bb556ac5997f7`,
tree `e16dd0815e252c7e1715545999918f303bc823af`.

| Input | Git blob |
| --- | --- |
| Frozen terminal module | `4caba3c09c45043bfc7ca46710362e367686db80` |
| Frozen CLI | `8815aaa58a347afc4c0686549e871ca7f4b9d20c` |
| Frozen dedicated author test, not read or run as the oracle | `a2b33a0a2c6cdd065dd38ffd5a0b7c6d4c82453e` |
| Frozen README | `975dcc6867174c58c792c184796ae777b672777b` |
| Unchanged original App producer | `e26f84ff9e0d3475c910f681d80e19256f70eccc` |
| Unchanged original native bundle builder | `bdcb63507b57d07eed1a6598d7d37d5f5d9db802` |

All 141 entries of the original offer’s encoded evidence archive were checked for
byte size, SHA-256 and Git blob identity. Only 34 production/source files were
restored into the receiver’s own namespace; the author’s tests and fixtures were
not used to design the independent oracle. `archive-custody.json` retains all
restored source pins and the original encoded/decoded archive identities. The
original negative and interrupted author records remain in that unchanged offer.

## Independent native evidence

The receiver used CPython 3.12.14 and six processes total: one unchanged original
`App.review_bundle` process, followed by five actual `python -B -m freightpkt
export-reviews` invocations. All 40 receiving assertions passed. The full author
suite was not repeated.

The synthetic saved report contains two distinct literal IDs whose sanitized
labels are equal, opaque packet filenames unrelated to either ID, one current
approval with full earlier history, one stale approval, and an unselected private
sentinel. There is no original input directory or review server.

| Native witness | Observed result |
| --- | --- |
| Normal export, selectors supplied in reverse order | Status 0; literal sorted identities, unique constituent paths and escaped links retained. All ten nested files match the two original native API bundles byte for byte. Exact evidence/review identities, current/stale meanings, history and opaque `file` properties are preserved. |
| Existing destination symlink pointing to a selected source packet | Status 2; symlink and target retain bytes, inode, mode and modification time. |
| Kernel `RLIMIT_FSIZE=8797`, above every input file but below the 18,663-byte complete ZIP | Status 2 with `Errno 27: File too large`; no destination or remaining staging directory. This is an actual kernel write refusal, not a product monkeypatch. |
| Standard output directed to `/dev/full` | Status 120 at interpreter output flush, with `Errno 28`. The already published ZIP is complete and byte-identical to the normal result. |
| Retry against that already delivered ZIP | Status 2; the delivered file’s bytes and identity remain unchanged. |

Every advertised member checksum and size matches. Only selected native
constituents plus the batch cover and manifest are included; original inputs,
unselected packet/report/audit content and full summary/decisions are absent.
Saved source paths, bytes, inodes, modes and modification times are unchanged
after every relevant case; both original and candidate production sources are
unchanged. No first-run input directory or source pipeline output appeared.

The completed ZIP has SHA-256 recorded in `receipt.json`. The delivery observation
is not a request to roll back an already published file: a nonzero process exit
alone cannot establish that no delivery occurred. A caller should inspect its
chosen destination after a status-output failure; the no-clobber retry cannot
replace that result. The current README specifically covers validation/read/
staging/publication failure and does not promise rollback after a later status
message fails. This boundary is retained for an eventual caller-policy agreement.

## Replay and preservation

From a new receiver directory, with exact original/candidate `freight_packets`
trees restored from the frozen offer:

```bash
python3 -B receive_terminal.py \
  --baseline /absolute/original/freight_packets \
  --candidate /absolute/frozen/freight_packets \
  --output /absolute/new-receiving-directory
```

The output directory must not already exist. Linux `resource.RLIMIT_FSIZE`,
`SIGXFSZ`, and `/dev/full` are required for the two real operating-system failure
witnesses. There are no package installs, network dependencies or account inputs.

`native-artifacts.json.gz.b64` preserves every original receiving file and the
destination symlink’s metadata. Identical contents are deduplicated by SHA-256;
process arguments/status/stdout/stderr, fixtures, both native oracles, the delivered
ZIPs, and before/after custody records remain reconstructable. `verify.py` checks
the packet and every archived byte without executing the product. It can extract
regular artifacts into a new directory; symlink metadata stays in the archive and
is not recreated. The original `native-r1` execution remains untouched.

The latest captured #37 comments contain the shared-assembler proposal and the
separate #39 packet-filename notice. No shared API/format agreement is recorded.
This receiver explicitly follows `summary.packets[].file`, consistent with that
notice, and does not qualify the other owner’s unpublished Windows implementation.
Browser live-lock/freshness admission, assembly ownership and current-main
integration remain separate gates. This result qualifies only the frozen terminal
consumer and its unchanged native constituent producer.
