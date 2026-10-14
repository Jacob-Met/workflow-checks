# PT composition: existing two-module ThinkPad test receiving

Freeze this controller before viewing the private composed source. Root owns
the source composition and release gate; source_delivery owns the separate
ordinary generate → run → calendar consumer course. This controller runs only
the unchanged two existing test modules, once, on the already installed
ThinkPad Python/pytest environment. It does not install packages or alter the
Pages/Actions main-integration boundary.

## Source and environment admission

Require host hamon-thinkpad, account jacob, Linux, /usr/bin/python3 version
3.14.4, installed pytest9.0.2. The prior read-only import was collected as
PID586962 exit0 and retained independently. At execution, admit exactly17
regular source files against an explicitly supplied, SHA-256-pinned manifest
whose only top key is files and whose records have path/bytes/git_blob/sha256.
All names are relative below the separate owned SOURCE_ROOT:

- LICENSE
- pt_auth/README.md
- pt_auth/CALENDAR_RECEIPTS.md
- pt_auth/ptauth/__init__.py
- pt_auth/ptauth/__main__.py
- pt_auth/ptauth/calendar_ui.js
- pt_auth/ptauth/cli.py
- pt_auth/ptauth/data.py
- pt_auth/ptauth/engine.py
- pt_auth/ptauth/report.py
- pt_auth/ptauth/synth.py
- pt_auth/ptauth/ui.html
- pt_auth/ptauth/uncovered.py
- pt_auth/ptauth/web.py
- pt_auth/ptauth/worklist_calendar.py
- pt_auth/tests/test_cli_date_admission.py
- pt_auth/tests/test_calendar_receipt_output.py

The manifest is bound after the receiver freeze and source peer release; no
source body is read as part of writing this receiver. Source-root and a new
exclusive output directory must be under the verified account home, resolved
without changing HOME. Output must be outside source-root. Record actual
interpreter/platform and manifest identity. Original file bytes and native
mtime values are retained as decimal strings.

## One exact test command

From SOURCE_ROOT/pt_auth execute one child process group:

```text
/usr/bin/python3 -I -B -m pytest -q -p no:cacheprovider --basetemp OWN_NEW_OUTPUT/pytest-temp tests/test_cli_date_admission.py tests/test_calendar_receipt_output.py
```

Remove PYTEST_ADDOPTS, PYTHONPATH, PYTHONHOME and PT_CALENDAR_SOURCE from the
child environment. Set PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and
PYTHONDONTWRITEBYTECODE=1. Do not discover other tests, rewrite either module,
inject a replacement package or invoke the full application suite. Expected
result is19 passed:11 existing date-admission controls and8 receipt controls.
Preserve stdout/stderr unchanged; pytest's own output is the test-result
record. The controller's elapsed time is only an outer observation.

Use a fixed60second child bound. On timeout kill only the new owned POSIX
process group and wait/reap with a10second bound. Retain timeout, status,
streams and all partial outputs; no automatic replay. Any cleanup failure is
separate from successful reaping. The controller never terminates unrelated
processes.

## Preservation and result

Watch all17 source files, controller and protocol before/after (19 paths), and
watch the supplied manifest separately. Require exact byte/Git/SHA/native-ns
records and exactly the original17 source file paths afterward. Pytest's
basetemp and logs live in the new owned output directory. Retain collected
child PID/exit/reaped/timeout, complete logs and controlled receiving.json.
Success requires exit0, expected19-pass summary, no failure/error/skip/xfail
summary, unchanged files and source inventory. Do not infer Windows behavior,
runtime application composition success, calendar-app import or deployment
from this test course. Root's source review and the distinct consumer course
remain separate evidence.
