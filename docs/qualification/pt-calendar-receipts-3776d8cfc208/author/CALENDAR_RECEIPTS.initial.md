# Calendar files and command receipts

The `calendar` command reads an existing saved report and creates a new `.ics`
file. It does not rerun the worklist engine. Run it from `pt_auth` in a source
checkout, using a report directory that contains `summary.json` and
`work_state.json`:

```sh
python -B -m ptauth calendar --report saved-report --output worklist.ics
```

Use a new output filename. Existing destinations are refused. The command
supports `--priority P1`, an exact `--clinic` name, and repeatable exact `--key`
filters. It retains the saved report's calendar selection and rendering rules:
dated open or submitted items become events; undated and completed items are
reported as exclusions. These are draft outputs from the existing proof of
concept, with no external calendar invitation or payer submission.

## Read the status and the receipt together

On success, stdout contains one JSON object followed by a newline. The command
explicitly flushes that receipt before returning status `0`. Its decoded values
are unchanged, including the output path, snapshot identity, selection counts
and exclusion details. Unicode is represented using JSON escapes so that a
restrictive ASCII output stream can carry the receipt. Parse it as JSON instead
of treating an escaped path as a literal filename. The calendar itself keeps
its existing UTF-8 encoding and CRLF line endings.

Status `2` means that the command could not complete normally. Read stderr
when available and inspect the destination before deciding whether to retry.
There are two materially different situations:

| Situation | Output and next action |
| --- | --- |
| Report admission or calendar publication failed | No success receipt is emitted. Inspect the diagnostic and destination. Existing output is never deliberately overwritten; a post-publication cleanup failure may still leave a complete new calendar. |
| The calendar was created, but its JSON receipt could not be written or flushed | The completed calendar is retained. The best-effort diagnostic explicitly says it was created and asks you to inspect the destination before retrying. Do not blindly rerun to another filename and create an unintended duplicate. |

A receipt can be partly written before a stream fails. An apparent JSON value
without a successful process status does not establish complete delivery.
Diagnostics use ASCII escapes and are best effort: if stderr also fails, it
cannot carry an explanation. The command keeps status `2` for handled receipt
write/flush failures even when that diagnostic cannot be delivered.

Both `python -m ptauth` and `python -m ptauth.cli` use a direct-entry wrapper.
When a returned error status meets a failing stdout flush, the wrapper disables
the subsequent interpreter shutdown retry. A closed pipe therefore does not
replace the intended status with Python's shutdown-flush failure status.
Imported `ptauth.cli.main(argv)` keeps the caller's stdout object and bytecode
policy; an embedding application owns its own stream lifecycle.

## Focused controls

From `pt_auth`, run the maintained regression file with:

```sh
python -B -m unittest discover -s tests -p test_calendar_receipt_output.py -v
```

The eight methods exercise ordinary Unicode output, both public module entry
points under restrictive ASCII, actual preclosed pipes, existing destination
and unmatched-selection refusal, and imported-main write/flush/diagnostic
failures. They use authored fictional saved reports and inspect the actual
calendar bytes. The inherited preclosed-pipe method runs on POSIX; it is
explicitly skipped on other platforms. Imported-stream controls remain a
separate scope from a native Windows terminal receiving course.

## Availability of this increment

Issue [114](https://github.com/Jacob-Met/workflow-checks/issues/114) tracks this
receipt repair. Source publication and an opt-in calendar-only package are
separate from merging or installing an update. Main integration remains held
at the existing Pages/Actions boundary recorded in
[issue 106](https://github.com/Jacob-Met/workflow-checks/issues/106). This change
does not modify the date parsing owner's lines, the existing calendar renderer,
workflow files, deployment settings, or an installed application. A package's
own source manifest and instructions identify its exact version and supported
command; an older checkout does not acquire the repair automatically.
