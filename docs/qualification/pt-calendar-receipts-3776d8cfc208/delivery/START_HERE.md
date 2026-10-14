# PT calendar-only portable source — reviewed draft

This small source kit creates a new calendar file from an existing **synthetic**
saved PT worklist. It contains the repaired calendar command and its exact four
runtime files. It does not generate a report, run authorization rules, open a
web application or send a calendar invitation.

## Extract and run

1. Extract the complete ZIP into a new directory. Open the extracted `pt_auth`
   folder; keep its `ptauth` subdirectory and four Python files together.
2. Use an existing Python 3.10 or later. The calendar path uses only the standard
   library; no package installation or service is needed.
3. Point `--report` to a previously generated fictional report directory containing
   `summary.json` and, when present, its `work_state.json`. A missing state file is
   treated by the existing reader as empty staff state. Choose a new `.ics` output
   path whose parent directory already exists.
4. Run this command **from the extracted `pt_auth` folder**, replacing the example
   paths with your explicit report and new destination:

```sh
python -B -m ptauth calendar --report "/absolute/saved-report" --output "/absolute/new-calendar.ics"
```

The unchanged calendar selection rules create events for dated open/submitted
items and report exclusions for undated/completed items. Optional filters are
`--priority P1`, an exact `--clinic` value and repeatable exact `--key` values.
See [CALENDAR_RECEIPTS.md](CALENDAR_RECEIPTS.md) for the maintained usage and output
contract. No saved report or sample data is included in this kit.

Only the **calendar** subcommand is supported by this package. The unchanged
shared CLI may list `generate`, `run` and `serve` in its help, but their modules
and full-application dependencies are deliberately not bundled. Use a separate
full checkout for those workflows. This kit does not replace the previous
portable review package or adopt its separate date-admission change.

## Check the process status and destination

Status **0** means the command created the calendar and delivered its newline-
terminated JSON receipt to stdout. The receipt uses JSON Unicode escapes, so
parse it as JSON to recover the actual Unicode path and recorded values. The
calendar bytes retain their existing UTF-8 encoding and CRLF line endings.

Status **2** requires reading the diagnostic and inspecting the destination
before retrying. An admission/publication refusal emits no success receipt.
If the calendar was created but receipt writing or flushing failed, the complete
calendar remains and the best-effort diagnostic says so. A stream may fail after
part of a receipt was written. Do not treat partial output as success or blindly
create a second calendar. A failed stderr channel may carry no explanation.

Existing destination paths are refused; the command never deliberately replaces
one. A post-publication cleanup failure can still leave a completed new file.
The module entry point handles the reviewed stdout shutdown-flush failure; this
does not qualify every interpreter channel or an imported caller's stream
lifecycle. Importing a file into a calendar application is a separate action
that this kit does not perform or qualify.

## Source status and exact inventory

The source pin is the reviewed **draft** snapshot
[`1bd30de4cecff7ee7564dccadf53561f3e21c284`](https://github.com/Jacob-Met/workflow-checks/commit/1bd30de4cecff7ee7564dccadf53561f3e21c284)
in `Jacob-Met/workflow-checks`, for [issue114](https://github.com/Jacob-Met/workflow-checks/issues/114).
It is **not a main-branch merge or installed update**. The existing dynamic
Pages/Actions integration hold recorded in
[issue106](https://github.com/Jacob-Met/workflow-checks/issues/106) remains in force;
no workflow, repository setting or deployment was changed for this package.

The complete archive has eight members:

- `MANIFEST.json` at the archive root;
- `pt_auth/ptauth/__init__.py`, `__main__.py`, `cli.py` and `worklist_calendar.py`;
- `pt_auth/CALENDAR_RECEIPTS.md`, this `START_HERE.md` and `SOURCE_MANIFEST.json`.

The outer manifest maps all seven selected payload sizes and SHA-256 values.
The source manifest records the five exact draft source/guide Git identities,
their repository paths and the separate delivery note. These identities verify
the packaged files, not the truth of any saved worklist or external payer policy.
The package includes no report, clinical record, account credential, dependency,
test suite, server, installation script or automatic launcher.

The source repair's author and independent CLI courses are separate from package
receiving. A package receiving record states whether the extracted calendar
command was actually run. No browser, Windows terminal, real-patient, payer or
external-calendar acceptance is implied by this source-only distribution.
