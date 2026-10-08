# PT calendar producer qualification

The implementation adds a local, explicit submit-by calendar handoff to the
existing synthetic authorization worklist. Its source is frozen at native commit
`d75fb908a9893fd40b21112f62af16d32027bbe1`, tree
`94074bd3d39705fced23629038ab79057e943aff`, parent
`9e931fa9f42033bf2368f7149684fb5631345715`. The published feature commit
`a68a667f3610153618c6cc8952c72abe980d89aa` has exactly that entire tree.
The native authored patch is retained separately; these are not the same commit.

## Consequential receiving

The unchanged baseline CLI has generate/run/serve and refuses the new calendar
command with exit 2. Running the actual sample report produces 26 work items, 18
with existing submit-by dates. The candidate's real CLI exports 18 all-day
VEVENTs and reports the eight undated exclusions. The original report is retained
with its output hashes and raw command logs.

The first draft passed 18 maintained tests, but a subsequent actual native report
with the optional patients.csv absent revealed an overrestriction: existing PT
rules admit blank clinic/name fields, while the draft refused a blank clinic.
The exact six-file v1 source, original successful report, rejected calendar
command and absent-output observation remain in this packet. The correction
preserves admitted blank fields and permits an exact blank-clinic CLI filter.
The corrected actual CLI exports that same report successfully.

The final additive suite passes 19 standard-library tests. It exercises the
calendar wire format through an independent physical-line/unfolding parser,
recorded leap/century/end-of-range/DST dates, unchanged all-day semantics,
explicit overlapping exclusions, key/filter admission, stable and changed
identities, actual UTC export timestamps, Unicode/control-character handling,
source text retention, immutable prepared plans, file-read drift, existing and
racing output preservation, actual CLI commands and actual local HTTP requests.
HTTP receiving verifies successful bytes, malformed and empty selections, changed
staff state, stale snapshots and report drift during rendering, with no report
generation or source/state writes.

The complete existing-plus-additive PT suite passes **116 tests**, with **one
existing skip** and **45 subtests passed**, on native Python 3.14.4. Node syntax
validation passes for the new module. The repository's existing CRLF text leaves
remain CRLF. Plain git diff --check reports those CR characters as whitespace;
the recorded `git -c core.whitespace=cr-at-eol diff --check` passes while preserving
the original line-ending convention.

Hosted source-stage checks on Python 3.10 and 3.12 passed at the exact published
feature head. See `source-stage-hosted-ci.json` and
[the hosted run](https://github.com/Jacob-Met/workflow-checks/actions/runs/37785036652).
This source-stage result does not assert a later evidence/publication head.

## Semantic and ownership fences

Only existing submit_by dates are exported, as one-day all-day DATE events under
[RFC 5545](https://www.rfc-editor.org/rfc/rfc5545.html). There is no fallback date,
appointment time, clinic-zone conversion, recurring reminder, attendee, alarm,
payer action or calendar import. The UID binds the existing work-item key,
clinic, authorization end and recorded clinic-zone label. Repeat-import,
deduplication and cancellation behavior in calendar applications is unclaimed.

The current report and staff state are read and compared before and after
rendering. A reviewed snapshot binds observed contents; it is neither reviewer
authentication nor a lock on other writers. The browser independently retires a
pending download when its current selection/source context changes.

There are four modified original leaves and three new leaves. All **343 unrelated
parent leaves** remain exact. Core data, report, engine, synthetic inputs,
existing tests and the staff-state writer remain intact. The native source
freeze includes all 55 PT package leaves, with mode, Git blob, SHA256 and size
records. The complete 98,915-byte source archive and the original authored patch
support reproducible receiving without another full clone.

Earlier uncovered-visits issue26 retains its projection/CSV/tab/search and
additive shared-file scopes. Exact UI/CLI/README hook coordination was posted
before publication, and the sibling's future source must be preserved during
current-parent composition. The Calendar #27 source claim remains active.

## Current gate status

At this producer packet stage, independent Mac browser/download receiving and
root date/export review are pending. This producer result is not their verdict.
No PR, merge, deployment, real patient data, payer submission, calendar account
write or native goal adoption is claimed. Later immutable review and integration
receipts will state their own exact source and evidence scope.

## Replay

From the frozen PT source directory:

~~~sh
python3 -B -m unittest discover -s tests -p test_worklist_calendar.py -v
python3 -B -m pytest -q -p no:cacheprovider tests
python3 -B -m ptauth calendar --report SAVED_REPORT --output NEW_FILE.ics
~~~

The standard-library tests require no package installation. The existing complete
suite uses pytest already installed in this native environment. Use disposable
synthetic report/output directories; the CLI intentionally refuses an existing
destination. Independent browser scripts and receipts will remain separate from
the authored test oracle.
