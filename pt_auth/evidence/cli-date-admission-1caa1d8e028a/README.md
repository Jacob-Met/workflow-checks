# PT CLI explicit date admission

Issue: [workflow-checks #106](https://github.com/Jacob-Met/workflow-checks/issues/106).

An explicitly empty `run --as-of` value used to select the report's default date.
With an existing worklist, this could silently replace a report reviewed for one
date with a report for the sample date or today. The CLI now parses an explicit
date while admitting arguments, before the generator or report opens its inputs
or writes outputs. An empty, whitespace-only, malformed, or impossible calendar
date produces the usual argparse usage error and exit status 2.

Omitting `run --as-of` still uses the existing sample-date or today default.
The generator retains its `2026-09-28` default, and explicit valid dates still
reach the existing generator and report as `datetime.date` values.

## Source boundary

The original is the PT source at main
`d2b583ae9350b30aec1453e93797dc231888417d`. The local checkout has an older
repository parent, `ec92e0b071d8cef9c314cece9bff6dbbe9a3382d`; all 29 PT runtime,
test, and synthetic-sample inputs were compared with the current remote tree and
are byte-identical. Their hashes are in [baseline-source-pins.json](baseline-source-pins.json).
The existing PT README was also matched to remote blob
`2c6440e7f9bdbc9f4d15e60d05b5626921d35cef` before its small insertion.

Publication applies only this increment's changed blobs to the actual current
remote tree. The old checkout's repository ancestry is not a publication base.

The product change is four lines in [ptauth/cli.py](../../ptauth/cli.py): both
`--as-of` options use `date.fromisoformat` as their argparse converter, the
generator's default is already a date, and both consumers receive that parsed
value. All 95 original CRLF line endings are retained. The new
[real-CLI regressions](../../tests/test_cli_date_admission.py) and the short
[usage contract](../../README.md) accompany that change. The generator, input
loader, report engine, clinical rules, time-zone logic, and other CLI commands
are unchanged.

The exact three source-file hashes are in
[candidate-source-freeze.json](candidate-source-freeze.json).

## Original behavior and author verification

All receiving inputs were generated fictional data. The first direct original
CLI run generated six patients for `2026-09-28`, wrote a report explicitly dated
`2026-10-01`, and then ran against the same output with `--as-of ''`.
That final command returned 0 and replaced the report with one dated
`2026-09-28`. The preserved [receipt](original-cli-reproduction/receipt.json)
and adjacent command stdout/stderr record this behavior. An impossible date
returned 1 with a traceback instead of a usage error.

The identical new regression file was then run against original and candidate
source in that order:

| Check | Original | Candidate |
| --- | --- | --- |
| New CLI regression module | 9 failed, 2 passed | 11 passed |
| Complete maintained PT suite, including the new module | Not rerun | 146 passed, 1 skipped |

The new cases exercise existing report preservation, existing synthetic-data
preservation, absent output destinations, empty and invalid dates, valid explicit
dates, omitted dates, and leap-day generation through the real CLI. Preservation
checks bind file bytes and directory entries along with inode, mode, and mtime.
The one maintained-suite skip is the existing opt-in Chrome qualification case;
the run does not claim that browser qualification.

The author runs used Python 3.12.14 and cached pytest 8.3.5 with external plugin
autoload disabled. Initial missing-pytest setup attempts did not execute tests;
the receipts below are the completed runs after the dependency was resolved.

- [Original/candidate commands and results](author-regression-02.json)
- [Original regression output](original-tests-02.stdout)
- [Candidate regression output](candidate-tests-02.stdout)
- [Full PT suite command and result](full-pt-tests-01.json)
- [Full PT suite output](full-pt-tests-01.stdout)

From an environment with pytest installed, the maintained commands are:

```sh
cd pt_auth
python -m pytest -q tests/test_cli_date_admission.py
python -m pytest -q tests
```

## Independent receiving

A second worker froze [receive_pt_date.py](independent/receive_pt_date.py)
before reading the candidate, exercised the original first, and then ran that
unchanged standard-library receiver against the frozen candidate. It used a
different three-patient seed and an explicitly selected `2026-10-04` review date.
The original met six controls and failed five date-admission expectations; the
candidate met all eleven. The original blank-date overwrite changed October 4
to September 28. The receiver retained a ZIP of the actual pre-overwrite report.

The worker also read the complete four-line runtime diff, the new regression
module, and the README insertion. Eleven other runtime files are byte-identical.
Default and compact-date generated files match exactly between original and
candidate, and selected, omitted, and leap-day review summaries match except for
their generated timestamp. The compact date spelling `20280229` remains
accepted by the same Python date converter; the generator's acknowledgement now
prints the canonical `2028-02-29` rather than the raw compact spelling.

The exact [independent review](independent/review.json) binds the receiver and
both receipt hashes. Complete receiving trees, including all command logs,
synthetic inputs, reports, pre-overwrite ZIPs, and receipts, are preserved in
[original-receiving.tar.gz](independent/original-receiving.tar.gz) and
[candidate-receiving.tar.gz](independent/candidate-receiving.tar.gz). Each archive
contains 57 files and six directories. Adjacent
[original](independent/original-inventory.json) and
[candidate](independent/candidate-inventory.json) inventories bind every member's
name, mode, size, content hash, and observed modification time. Their contents
were reopened and compared with those inventories after packaging.

From the repository root, this command runs the receiver against the checked-out
source and requires a fresh destination:

```sh
python pt_auth/evidence/cli-date-admission-1caa1d8e028a/independent/receive_pt_date.py --source pt_auth --out /path/to/new-receiving-output
```

The candidate returns 0 for all eleven contracts. The original returns 1 for the
five preserved failures. These results qualify the real CLI in cloud Linux;
they do not establish an installed native consumer or browser adoption.

## Integration boundary

The existing main commit `d2b583ae9350b30aec1453e93797dc231888417d` has a
`[skip actions]` annotation, yet GitHub recorded the dynamic
[Pages build and deployment run 38314005867](https://github.com/Jacob-Met/workflow-checks/actions/runs/38314005867)
on that exact commit. The current YAML files alone do not describe this trigger.
The user's no-Actions constraint therefore requires holding a main merge while
that dynamic Pages behavior remains unresolved. This increment can be reviewed
and published on its skip-annotated feature branch without changing repository
settings or invoking a deployment.
