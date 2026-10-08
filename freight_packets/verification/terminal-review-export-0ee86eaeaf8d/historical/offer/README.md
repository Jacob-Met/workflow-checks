# Native freight batch CLI — frozen receiving offer

This is the already implemented local command and its complete native evidence,
held for coordination with [workflow-checks issue 37](https://github.com/Jacob-Met/workflow-checks/issues/37).
No branch or pull request has been published by this lane. Independent receiving
of this candidate is still pending. The browser owner keeps its UI, locked server
route and implementation scope; shared filenames and archive format require an
explicit composition or adoption agreement before publication.

## Capability and source

`python -m freightpkt export-reviews --out GENERATED --load LOAD --load LOAD
--destination NEW.zip` exports an explicit set of saved reviews without the
original input directory or a running server. The complete ZIP links to the exact
five native members for each chosen load. It retains existing saved-review states,
uses numbered safe archive directories and escaped literal labels, refuses the
whole request on invalid selections or observed source changes, and never
overwrites a destination. Source and destination ownership, limits and failure
behavior are recorded in the candidate README.

Source base: `Jacob-Met/workflow-checks` main
`5b12dcd4c3a2c09d6602b2313e2bb556ac5997f7`, tree
`e16dd0815e252c7e1715545999918f303bc823af`. The root claim was published at
2026-10-08 14:18:04 UTC; issue 37 appeared six seconds later. Later main
`5a70e458ed455d47ef672ed9b5a614ec59812f0c` has identical freight source, tests and
README. That is a read-only composition check, not execution of changed PT or
Utility code.

The four exact candidate paths and hashes are in `manifest.json`. Fifteen inherited
native product files remain unchanged. Removing only the additive command parser,
dispatch and docstring term reproduces the original CLI exactly; removing the
README append reproduces its original bytes. Original CRLF remains intact.

## Executed native evidence

- The unchanged baseline uses four real Python CLI processes and six loopback HTTP
  responses: generate/run/serve, two saved reviews and two separate downloads, then
  the absent proposed command (status 2 and no destination). All inputs and output
  files remain unchanged across the read-only downloads and absent command.
- One initial receiver-only logging error is retained. It started three native CLI
  processes and received one HTTP response before `Request.method` failed. The
  temporary context removed those partial results; no successful qualification is
  attributed to that interrupted run. The exact original script and traceback are
  present, as is the one-expression `Request.get_method()` transport correction.
- The first candidate CLI creates one two-load batch. Every nested file is byte
  identical to the two original real HTTP downloads, with source output unchanged.
- Eleven authored methods and twenty subtests pass. These include 22 actual CLI
  processes: five accepted and seventeen refused. The exact outputs, complete
  synthetic fixture, archive bytes and before/after source hashes are preserved.
  Source-change, destination-race, staging-write, publication and reduced-output-
  budget controls use explicitly identified direct API fault injection; they are
  not counted as CLI processes.
- The complete current freight test suite passes **90 tests and 47 subtests** on
  CPython 3.12.14 / pytest 9.1.1. It uses the already existing read-only environment,
  with bytecode and pytest cache writes disabled. It retains all seven inherited
  test files and all source bytes. It is a separate full-suite gate, including
  repetitions naturally performed by that suite.

No installer, shared environment modification, new native seat, browser execution,
external delivery, billing/payment action or hosted-runtime result is claimed.
The new local command has no lock shared with a concurrent writer: use a finished
report without simultaneous edits. Its before/after checks detect observed
changes and its output remains an explicitly identified saved snapshot.

## Inspect or reproduce

`native-evidence.json.gz.b64` is a base64-encoded gzip JSON file inventory. Every
decoded file carries its original relative path, byte count, SHA-256, Git blob
identity and base64 bytes. `verify.py` checks the complete archive without
executing any captured script. The manifest separately binds the encoded and
decoded archive and all payloads.

For an independent reproduction, restore only `candidate/` into a new disposable
directory, with the original source and test bytes intact. From its
`candidate/freight_packets` directory, use an existing Python 3.10+ installation:

```bash
PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -p test_review_batch.py -v
```

If pytest is already available, the full package command is
`python -B -m pytest -q -p no:cacheprovider`. The captured source has no repository
pytest configuration. Choose an existing writable temporary directory if needed.
These commands create only synthetic temporary inputs and recipient outputs.
Never run a receiver into the preserved original evidence directories: the
historical results are immutable. Runtime/version and path differences in a new
run are new evidence, not byte identity with the recorded executions.
