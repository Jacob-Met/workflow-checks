# PT authorization and visit-limit tracker (PoC)

> **SYNTHETIC DATA ONLY: NOT REAL PATIENTS.**
>
> - Every patient ID is `SYN-####`, every name is "Test …", and clinics are labeled "(synthetic)".
> - Payers and their rules are **placeholders, not real plan policy**.
> - The UI, the digest and the data folder all carry this label.
> - Nothing is submitted to any payer.

This was built for multi-clinic outpatient PT groups where an authorization specialist or care coordinator must verify required authorizations before scheduled visits. Only the payer rules table changes from one group to another.

## What it does

1. **Ingests four CSVs.**
   - `schedule.csv`: visit, patient, date, clinic, therapist, payer, status, and visit type (eval / treatment / re-eval).
   - `authorizations.csv`: auth #, patient, payer, visits authorized, start and end dates, and status (approved / pending / denied).
   - `payers.csv`: the **per-payer rules table**. Each row covers whether auth is required, the re-auth thresholds (N visits left or N days left), turnaround days, any annual visit cap, whether evals count against the auth, and a re-auth packet checklist.
   - `patients.csv`: display names and clinics.
2. **Builds a visit/auth ledger.** Each non-cancelled visit is assigned to the approved auth that covers its date and still has capacity. Completed visits are assigned first, then scheduled visits in date order. From that, the tracker calculates visits used, visits scheduled, visits remaining, remaining after scheduled visits, and days left.
3. **Produces a prioritized daily worklist.** Each item carries a reason code, a *submit-by* date, and the pre-filled payer checklist.

   | Code | Meaning | Priority |
   |---|---|---|
   | `UNCOVERED_VISIT` | A scheduled visit falls outside any approved auth, by date **or** because the visit count is exhausted | P1 if the visit is within 7 days, else P2 |
   | `UNAUTHORIZED_DONE` | A completed visit had no covering auth (billing/denial risk) | P1 |
   | `REAUTH_BY_VISITS` / `REAUTH_BY_DATE` | The payer's visits-left or days-left threshold has been reached and visits continue | P2; P1 once submit-by has passed |
   | `PENDING_FOLLOWUP` | Upcoming visits rely on a still-pending auth | P2; P1 if the visit is within 2 days |
   | `ANNUAL_LIMIT` | The patient is near or over the payer's calendar-year visit cap | P3; P2 if scheduled visits exceed the cap |
   | `UNKNOWN_PAYER` | Visits or a live auth use a payer id that is not in `payers.csv`, so its rules could not be checked | P2 |

   - **Submit-by** is the earlier of the auth end date or the date of the visit that uses up the auth, minus the payer's turnaround days.
   - Auths that already have a successor auth (approved or pending, starting no earlier and ending later) are not re-flagged, because that work is already in progress.
   - Self-pay and no-auth payers are never flagged for authorization. Only `ANNUAL_LIMIT` can apply to them, if the payer has a cap.
   - **Messy exports are handled or rejected, never guessed.** The loaders accept a BOM or cp1252 encoding, "Visit Date" style headers, blank and comma-only rows, date+time values, and common status spellings. A visit repeated across appended exports counts once. Anything they can't interpret (for example an unknown status, a day-first date, or a blank visit count) stops the run with the file, line and reason. See `HARDENING.md`.
4. **Writes outputs.** It writes `worklist.csv`, `ledger.csv`, `digest.html` (a printable daily digest with checklists), `summary.json`, and `audit.jsonl`.

The runtime uses the Python 3.10+ standard library. Tests use `pytest`.
Named clinic time zones use the system's IANA database. On a system without
that database, such as a typical Windows installation, install Python's
first-party `tzdata` package to use the named-zone option below.

## Run it

```powershell
cd pt_auth
python -m ptauth generate --out sample_data --patients 40 --seed 21 --as-of 2026-09-28
python -m ptauth run --data sample_data --out out           # add --as-of YYYY-MM-DD to time-travel
python -m ptauth serve --data sample_data --out out         # http://127.0.0.1:8766/
python -m pytest -q
```

### Choose the clinic's calendar time zone

Use an IANA name when importing timestamps with an offset, especially when
the program runs on a different machine from the clinic:

```powershell
python -m ptauth run --data sample_data --out out --clinic-timezone America/Los_Angeles
python -m ptauth serve --data sample_data --out out --clinic-timezone America/Los_Angeles
# If the named zone is unavailable on this machine:
python -m pip install tzdata
```

The same selected zone applies to offset-bearing visit timestamps and
authorization start/end timestamps before the tracker takes their calendar
dates. Historical daylight-saving offsets are applied at each timestamp.
For example, `2026-09-29T01:30:00Z` is a September 28 visit in
`America/Los_Angeles`, so it can fit an authorization ending September 28.
An explicitly chosen `UTC` zone makes it a September 29 visit.

Date-only values and timestamps without offsets keep their written calendar
date. The selected zone also supplies "today" when no `--as-of` or sample
`expected.json` date is present; those explicit calendar dates keep their
existing meaning. One zone applies to the complete input batch. Use separate
runs for exports whose locations require different zones.

The CLI, UI, printable digest, `summary.json`, and run audit record identify
the zone used. A server started with a different zone, or with a legacy
summary that has no zone record, rebuilds the report from the CSVs while
preserving its previous as-of date. Ordinary subsequent reads reuse that
report. Omitting the flag preserves host-local date conversion and labels it
`system local`; because this depends on the machine, that mode refreshes a
cached report once when the server starts. Choose a named zone for consistent
clinic dates across hosts using the same time-zone rules.

An invalid or unavailable zone stops before report output, synthetic
generation, or server startup. The error names the zone and explains how to
supply time-zone data. Python's [zoneinfo documentation](https://docs.python.org/3/library/zoneinfo.html)
describes its IANA rules and system/`tzdata` data sources.

The UI is a single page with no CDN, bound to 127.0.0.1 only. It has:
- a visible clinic time zone matching the generated report
- summary cards
- a worklist filterable by priority, clinic and search, with visit meters and expandable checklists
- a per-item status (open / submitted / approved / n/a), saved to `work_state.json` and the audit log
- an auth ledger tab
- a digest and exports tab
- an **as-of date** picker to show how the worklist changes day to day
- a "New synthetic clinic" generator

## Verification

The clinic-zone controls exercise the actual CLI under UTC, Eastern, and
Pacific host settings, shared visit/auth conversion, seasonal and DST
boundaries, concurrent reports with different zones, invalid-zone output
preservation, cached-report refresh, and the local HTTP run/digest path.
An optional real-browser check verifies the visible zone, visit coverage,
rerun, and printable digest in a fresh intercepted browser context:

```sh
PTAUTH_TEST_CHROME=/absolute/path/to/chromium python -B -m pytest -q -s tests/test_clinic_timezone.py
```

This optional check also needs Playwright installed in the test environment.
All these inputs are authored synthetic records.

The generator writes `expected.json`, an answer key computed from the seeded auth parameters and not from the engine. The tests assert:
- **Zero missed uncovered visits.** The set of scheduled visits outside an auth equals the key exactly, and every such patient reaches the worklist.
- The re-auth-due patient set **equals the manual audit** exactly.
- Completed visits without an auth and pending auths are all caught.
- "Clean" patients are **never** flagged.
- Unit tests cover the rules: thresholds, successors, eval exclusion, annual cap, and self-pay.

I also checked the answer key manually on 5 more seeds (1, 2, 3, 99 and 1234, with 80 patients each). All matched.

## 2-minute demo script (screen-record)

1. **(0:00) Terminal:** run `python -m ptauth generate` and then `python -m ptauth run`. Say: *"This is a synthetic three-clinic practice: 40 fake patients, about 850 visits, and four placeholder payers, each with its own re-auth rules."* Point at the P1/P2 counts and the number of visits outside an auth.
2. **(0:20) Open the UI:** run `python -m ptauth serve` and open http://127.0.0.1:8766. Point at the red **SYNTHETIC DATA** banner, then the cards: *"11 things to do today, 15 this week, and 194 scheduled visits that currently have no auth behind them."*
3. **(0:35) Walk through the top P1 row.** Say: *"This patient has 2 of 12 visits left, and the schedule already runs past the auth. The submit-by date was last week, given this payer's 7-day turnaround. Here's the payer's checklist, pre-filled."* Expand the checklist.
4. **(0:55) Filter by clinic** and search a patient. Set a status to **submitted**. Say: *"Staff work the list, and every change is logged."*
5. **(1:10) Auth ledger tab.** Say: *"Every auth shows authorized, used, scheduled, and remaining after scheduled. Negative numbers in red are visits that will be denied."*
6. **(1:25) Change the as-of date** a week ahead and click **Run worklist**. Say: *"Here's what next Monday's list looks like. Nothing slips because nobody checked."*
7. **(1:40) Digest tab.** Open the printable daily digest. Say: *"It runs on synthetic data today. For your clinics we'd connect a de-identified schedule and auth export first, and cover HIPAA before any real data."*

## HIPAA considerations for a real deployment

This PoC contains **no PHI** and must not be pointed at real patient data as-is. A production version needs the following.

- **BAA first.** Sign a Business Associate Agreement with the clinic before any PHI is accessed. Also get BAAs with any sub-processors: hosting, backups, email, and any LLM vendor. **Don't use an LLM on PHI** unless the vendor signs a BAA and has zero data retention. The PoC uses none.
- **Minimum necessary.** The tracker only needs a patient identifier, visit dates and status, payer, and auth numbers, counts and dates. It needs no diagnoses, notes, or DOB. Use an internal MRN or a tokenized ID, and keep names only in the EMR view.
- **Deployment inside the clinic's boundary.** Run it on their HIPAA-covered infrastructure: an on-prem box, or their Azure/AWS tenant under a BAA. Encrypt at rest (BitLocker / encrypted volume / encrypted DB) and in transit (TLS; the PoC's plain HTTP on 127.0.0.1 is demo-only).
- **Access control.** Require SSO/MFA and role-based access (front desk vs. auth specialist vs. admin). Add automatic session timeout, and no shared logins.
- **Audit controls (§164.312(b)).** Keep an append-only access and activity log covering who viewed or changed which work item, and when. The PoC's `audit.jsonl` shows the pattern and deliberately records only work-item keys, not names. Production should log user identity, be tamper-evident, and be retained per policy (commonly 6 years for documentation).
- **Data retention and disposal.** Keep exports in a controlled folder, purge them on a schedule, and don't send CSVs by email. The digest should be viewed in-app, not emailed. If it is emailed, send it only to internal encrypted mailboxes with no PHI in subject lines.
- **Integration surface.** Prefer read-only exports or reports from the EMR/PM system (WebPT, Raintree, Prompt, etc.) or a vendor-sanctioned API, over screen-scraping. Any write-back to the EMR stays out of scope until it's validated.
- **Risk analysis and breach process.** Update the clinic's security risk assessment to include this tool, and document incident response and breach notification responsibilities in the BAA.
- **Testing.** Validate against a manual audit on de-identified data (Safe Harbor: remove the 18 identifiers, and shift dates consistently if needed) before go-live.

## What a real pilot needs from the client

- **Exports**, de-identified at first, covering 60–90 days of schedule history plus 30 days ahead:
  - the schedule/appointments report, with status and visit type
  - the authorization log, whether from a spreadsheet or the EMR's auth module
  - the list of active payers
- **Payer rules.** The clinic's real per-payer rules: which payers require auth, typical visits per auth, re-auth lead time, turnaround, whether evals count, annual caps, and the documentation each payer wants. Their Authorization Specialist is the source of truth, and the tool only encodes what they tell us.
- **Manual audit baseline.** A current manual audit for one clinic, used to measure the worklist against.
- **Workflow.** Who works the list and when (a morning huddle?), what the statuses should be, and whether they want the digest per clinic or per specialist.
- **Compliance.** A signed BAA, a hosting decision inside their HIPAA environment, and SSO/MFA identities before any identified data is used.
