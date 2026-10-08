# Utility Watch duplicate account admission — source evidence

Claim: https://github.com/Jacob-Met/workflow-checks/issues/46
Repository: Jacob-Met/workflow-checks
Original commit: 125339ec63eeb7c4989c9b240c01202555dce573
Original tree: e3a3501d60ee8f301f9d45ea15d0d324b814e59a
Native author/reviewer lane: chatgpt:/root/source_integration@8ef1dfe65b8f
Device: Mac.lan (5f462f1b-490d-4a0d-8caa-51742c9d09b4), Python 3.13.7

## Finding and change

On unchanged source, three actual CLI runs produce property metadata "Original
property", "Replacement property" after adding a repeated account number, and
"Original property" again after reversing those two records. All three exit 0.
Repeated normalized account numbers therefore silently overwrite the first
record and make report metadata depend on CSV row order.

The four-line engine.load correction refuses a repeated account_no and reports
both physical CSV end-line locations, using the first record's existing _row.
The account metadata is not included in the diagnostic. Existing normalization,
case sensitivity, _rows, checker, report writer and reviewer source are
preserved. The accompanying review-test setup now expects earlier refusal for
its duplicate-account case and retains the subsequent reviewer-refusal check.
PR 24 owns the distinct duplicate-header reader/test change; later integration
must preserve both test cases.

engine.run creates its output directory before load. The refusal guarantees
no report or audit FILE writes; it does not promise no directory creation.

## Original qualification, retained verbatim

baseline-receipt.json records the original observation at 15:42:52Z on
2026-10-08. The new regression was frozen before the source edit: 4 methods
failed and 5 control methods passed. The receipt records the three row-order
witness runs and SHA256 hashes of their six output files. The failure log is
logs/baseline-new-tests.stderr.log.

candidate-receipt.json records the native qualification at 15:46:09Z:

- Baseline inherited utility suite: 110 tests and 34 subtests passed.
- Candidate full utility suite: 119 tests and 36 subtests passed.
- New regression: all 9 methods passed under normal and optimized Python.
- Six actual CLI outputs on valid input matched the original byte for byte.
- All 17 original Git blobs were verified, 14 original paths were preserved,
  and load was the only changed engine definition; 9 definitions were unchanged.

The included five nonempty suite logs are original bytes. Empty counterpart
stdout/stderr files are omitted; their empty-content hashes remain in the
receipts. No original receipt was rewritten to reflect a later rerun.
Only synthetic authored data was used. No live service or real account data
was modified. The full native observation packet, including generated CSV and
report bytes, remains in original custody at:
/Users/me/workflow-utility-duplicate-account-8ef1dfe65b8f-20261008

The independent Windows receiver's frozen cases and result are separate
receiving evidence maintained by /root/windows_execution.

## Exact-source reproduction

source-pins.json records the original commit/tree, original file URLs and byte
identities, plus all four candidate path identities. It contains no source
file bodies. The committed regression module supplies the authored fixtures.

Given an authenticated local repository containing the original commit and
the published candidate commit, use an existing Python environment with
pytest and run:

    python3 -B replay.py --repo /path/to/workflow-checks --candidate-ref FULL_CANDIDATE_COMMIT --out /path/to/new-proof --pytest-python /path/to/existing/python

The candidate ref must be an explicit full commit SHA. The driver uses git show
to receive only the relevant source files, then verifies every byte length,
SHA256 and Git blob ID before execution. It requires a new output directory
and writes only there. The original and candidate source trees are staged
temporarily from those exact bytes; the original gets the same committed new
regression so its four original failures are observable.

For an independently received, byte-preserved snapshot, the equivalent mode is:

    python3 -B replay.py --baseline-dir /path/to/baseline --candidate-dir /path/to/candidate --out /path/to/new-proof --pytest-python /path/to/existing/python

Each source directory contains utility_watch/. That mode validates the same
Git blob identities and records that it received files rather than a Git
commit. The native author validated this mode after writing the replay driver;
Git mode additionally requires the subsequently published candidate commit.

Replay checks the original four failures, inherited original suite, full
candidate suite, optimized regression, original CLI row-order counterexample,
six-file valid-input parity, preserved source bytes and the load-only engine
scope. It keeps all new stdout/stderr, generated outputs and receipt.json in
the requested proof directory. It never installs dependencies or writes a
pytest cache/bytecode. The original source packet and receipts stay untouched.
