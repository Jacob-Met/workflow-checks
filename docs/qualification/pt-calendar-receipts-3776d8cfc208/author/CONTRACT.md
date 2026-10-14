# PT calendar receipt delivery repair

Issue114; current base5b7ece2ff6fadf1c3a194e9ca292f660787a2cd9. The original
four-process witness is immutable: ordinary UTF-8 exit0; restrictive real ASCII
stdout exit1/UnicodeEncodeError; both canonical and direct-module preclosed
stdout pipes exit120/shutdown BrokenPipeError. All four created complete ICS
files; all eight source/input/observer/protocol byte+mtime records remained
unchanged. No output is discarded or silently retried.

## Narrow behavior

The `calendar` subcommand keeps its current report reading, validation,
selection, metadata values, renderer and create-only publication. Successful
stdout delivers the same JSON value using ASCII JSON escapes, followed by one
newline and an explicit flush before returning0. Escaped Unicode is a wire
representation change; decoded paths and recorded strings are unchanged.

If this success receipt cannot be written or flushed because of OSError or
UnicodeError, calendar main returns2. It attempts one ASCII-only stderr message
stating that the calendar was created but its receipt could not be delivered;
the user should inspect the destination before retrying. It does not remove,
rewrite or republish the already created calendar. A failed stderr attempt
must not obscure status2. Existing calendar admission/publication failures also
remain status2 with no success stdout; diagnostics escape non-ASCII characters
so a restrictive terminal does not invent a traceback. Do not claim rollback
for the existing publisher's post-publication cleanup failures.

Calling imported `main(argv)` preserves the caller's stdout object and bytecode
policy. A separate direct-entry wrapper invokes main. Only if the returned
status is2 does that wrapper attempt to flush stdout and suppress a subsequent
interpreter-shutdown retry by setting stdout to None when that flush raises
OSError or UnicodeError. Both `python -m ptauth` and `python -m ptauth.cli`
use this wrapper. It does not swallow unrelated exceptions or change command
argument admission, other subcommand bodies, or general import policy.

## Source boundary

Modify only the calendar error/success output handling, one small private
diagnostic helper and direct-entry wrapper in cli.py, and the canonical entry
call/import in __main__.py. Retain exact CRLF outside edited spans. Preserve
date owner106's two declarations/two consumer lines and README span verbatim.
One new focused stdlib regression file and one standalone calendar-output guide
may be added. The initializer, worklist_calendar.py, all scientific/business
rules, data, web/UI, dependencies, workflows and settings remain unchanged.

## Qualification and integration

Author regressions use actual canonical/direct subprocesses, real preclosed
stdout, restrictive ASCII output, ordinary Unicode receipt values and complete
ICS wire inspection. Include existing-output/no-match refusal custody and
direct imported-main stream-policy/error handling. Preserve the original four
observations separately, including their created calendars and native integer
mtime records. A second worker reviews the exact source and receives the public
CLI with independently authored expected values; no application suite rerun is
needed beyond the concrete output/entry risks.

The dynamic Pages/no-Actions main-integration restriction recorded by owner106
is unresolved. Publish reviewed source as a skip-annotated draft after fresh
gates, verify exact remote changes/zero runs, deliver a versioned opt-in package
to the existing project destination and link its existing Notion record. Do not
merge main or change deployment/workflow settings to bypass that restriction.
No real records, service installation, browser or external calendar invitation
is involved. A qualified command-line package is a distinct receiving scope.
