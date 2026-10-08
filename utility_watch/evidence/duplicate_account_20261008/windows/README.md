# Independent Windows receiving

This directory preserves a receiver frozen before candidate exposure, its compact
outcome records and exact source/fixture manifest for workflow-checks issue46.
The original native packet remains at:

`C:\Users\minec\hamon\stage\utility-watch-receiving-8ef1dfe65b8f`

Native Python3.13.15 on Windows10 executed the actual `python -m uwatch` CLI.
The receiver is byte-preserved with SHA256
`8cb6ebf47ad456bae8a92417892be121ac94058326e09bf3b7bfb7614afb2c9b`.
Its nine baseline source files came from commit
`125339ec63eeb7c4989c9b240c01202555dce573`.
Candidate receiving changed only the engine input to Git blob
`dd1b752972b74232090ed602d11b84759bda19e3`; the author's full utility suite
separately receives all four candidate source/document/test paths.

## Observed results

The baseline had 25 expected failures among50 checks: five duplicate variants
silently succeeded and rewrote reports. Conflicting and reversed account rows
selected different property metadata. Valid, shared-bill-ID, case-sensitive,
blank-account and reviewer controls passed.

The same frozen receiver and fixture bytes passed all59 candidate checks.
All five duplicate variants exited2 without stdout, named both physical CSV
rows (2/3 or multiline3/6), preserved six existing report/audit files plus an
unrelated sentinel, and left fresh output directories without report files.
Valid, shared-bill-ID and case-sensitive controls retained the native baseline's
six output files and stdout/stderr bytes. Existing reviewer refusal was exact.
Output-directory creation is allowed; no absence-of-directory guarantee is made.

The two compact receipts retain checks, observations and hashes while moving
duplicated source/fixture manifests into `windows_input_manifest.json`.
They contain `original_receipt_sha256` linking the untouched native originals:

- Baseline: `f1aea62dca4069ec1602d92238a62f6c2b5fd5752fdd64f2edf1fe8fbe641159`
- Candidate: `8b3fc75bc2165a87cc51e06a9d8874ae08030d51abb5d1290d6a0816fac6a9eb`

These compact exports have their own byte identities and are not presented as
the original full receipts. No generated CSV/report contents, worker
configuration or credentials are included.

## Reconstructing the frozen input

The receiver deliberately refuses to reuse an existing baseline or candidate
directory. Copy `windows_receiver.py` into a new receiving directory on Windows.

Reconstruct `inputs.json` there from the nine `github_sources` paths in the
manifest, using exact `git show BASE_COMMIT:PATH` bytes from an authorized
repository. Its JSON shape is
`{"base": "125339ec63eeb7c4989c9b240c01202555dce573", "source": {PATH: {"content": UTF8_TEXT, "git_blob_sha": EXPECTED_BLOB}}}`.
Keep decoded UTF-8 line endings intact. Verify each blob and SHA256 against
`native_source_baseline`.

Reconstruct `candidate.json` from an explicit full published candidate commit's
`utility_watch/uwatch/engine.py`, with fields `base`, `content` and `sha256`.
Its SHA256 must be
`8d61b55e88415275ffe1c5edca6f914f10c4f47f6cfd9d0b56ba76854f6f1180`.
Then run the frozen script with native Python, first `baseline`, then `candidate`.
The first invocation records the original50 checks and expected25 failures;
the second requires59 passing checks. The script creates its synthetic CSVs
from the frozen definitions and stores new receipts in that new directory.
It does not install dependencies or operate on services.

The separate parent `replay.py` reproduces the authored before/after suites
directly from pinned Git source; it is a different receiving lane.
