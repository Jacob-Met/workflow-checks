# PT authorization what-if

A self-contained, static demonstration of the existing PT authorization worklist.
Open `index.html` in a modern browser, or serve this directory as its own
`ptauth-whatif/` route. The repository's existing Pages workflow serves the exact
generated copy at `docs/demos/ptauth-whatif/index.html`, whose established project
URL is `https://jacobmetoyer.com/workflow-checks/demos/ptauth-whatif/` after
publication. It has no runtime dependencies, requests, storage, account,
upload or submission action. Reloading returns to the original sample.

**Synthetic data only.** The eight patients are fictional, the payer rules are
placeholders, and priority is an administrative rule label. The result is not
medical advice, coverage confirmation, clinical urgency or a payer submission.
Do not substitute real patient data into this artifact.

## Explore the worklist

1. Choose a synthetic patient and an authorization or scheduled visit.
2. Change authorized capacity, inclusive expiry, one scheduled visit date or the
   global as-of date. Apply changes to calculate the scenario. Draft and invalid
   inputs hide the prior output; apply or reset before switching records.
3. Compare the selected patient's original and current priority, inspect all
   changed fields and read the rule reasons, submit-by date and row evidence.
4. Follow the approved-authorization ledger and every recorded visit's actual
   allocation. Pending authorizations do not supply approved capacity.

The three boundary examples each start from the original sample, then exhaust an
authorization's capacity, expire an authorization before its next visit, or move
one visit just beyond the inclusive expiry. Reset returns all eight patients and
all controls to their original state. Date controls accept 2026–2027; capacity
accepts whole counts from 0 through 200. These are demonstration input bounds.

The as-of date changes rule cutoffs. It does not change recorded visit statuses
or infer attendance. Past scheduled rows can still reserve capacity under the
pinned source. The accepted PR #12 rule update keeps past scheduled rows as
context for annual-limit alerts, then omits placeholders with no reason after
all rules finish. This demo consumes that accepted behavior; the separate
visit-status reconciliation UI and exports remain in their existing project.

## Source and build

Receiving parent: `Jacob-Met/workflow-checks`
`2f1e5f777197eedd69d51a4d81c0da744b65ad88`, tree
`86e6201872d2f2400537b84a50f026a1335a8c3d`.

- `model.mjs` projects `pt_auth/ptauth/engine.py::build_worklist` into a browser
  without requiring a Python runtime. Authoritative engine Git blob:
  `39c97f35d61ff949b5c2381f0ad60d7af8d74226`.
- `build.py` uses the actual Python CSV loaders and engine. It selects
  `SYN-1001` through `SYN-1008` from the existing sample, keeping their complete
  151-visit histories, nine authorization records and all five payer rows. No
  sample record or rule is rewritten. It serializes the native baseline and
  hashes every source input in `fixture.json`.
- `app.mjs`, `style.css` and `page.html` implement the interface. Build output
  `index.html` inlines those sources, the same model and fixture. The builder
  writes identical bytes to `docs/demos/ptauth-whatif/index.html` for the existing
  Pages delivery route. Data is rendered through DOM text nodes. A restrictive
  policy disallows runtime connections.
- `receive.mjs` installs only that generated page into an explicit isolated
  route and preserves exact before/after snapshots for rollback.

Build from any working directory with the repository present and Python 3.10+:

```sh
python /path/to/workflow-checks/demos/ptauth-whatif/build.py
```

The builder refuses a change to any of its six pinned source inputs. Its source pin is explicit,
not inferred from a later repository HEAD. Reconcile and independently qualify
any changed rule source before updating the pin. Date inputs are already
normalized, date-only values; this static demo does not duplicate CSV parsing
or the project's clinic-timezone conversion.

`evaluate(input)` accepts `{as_of, visits, auths, payers, patients}` using the
Python dataclass fields, ISO calendar dates and keyed payer/patient objects. It
returns `{items, ledgers, uncovered}`. Items retain every dataclass field plus
`key`; ledgers retain their authorization, ordered used/scheduled visits and
remaining counters. This surface exists for direct native-oracle comparison,
not as a general policy API. The interface checks its baseline against the
serialized Python result before enabling the controls.

Original source-row references remain stable when controls change a record.
Both the changes list and affected displayed evidence mark the row as
**scenario edited**; the source CSVs remain untouched.

## INSTALL / READBACK / ROLLBACK

Publication and choice of a served parent directory belong to the existing
delivery owner. This helper does not start a server, edit a landing page or
change hosting configuration. Use an owned, isolated target and serialize
operations. Node.js 18+ and existing target/receipt parent folders are required.
The receiving helper is qualified on Linux; it does not promise identical
permission semantics on other operating systems.

The target directory must be named `ptauth-whatif`. The supplied page and any
replaced page must carry `<!-- hamon-demo:ptauth-whatif -->`. An unrelated page
or symlink is refused. Use the exact SHA-256 from the accepted artifact receipt.

```sh
node receive.mjs install --source index.html --sha256 ARTIFACT_SHA256 --target /existing/demo-parent/ptauth-whatif --receipt /private/existing/receipts/pt-install-1.json
node receive.mjs readback --receipt /private/existing/receipts/pt-install-1.json
node receive.mjs rollback --receipt /private/existing/receipts/pt-install-1.json
node receive.mjs readback --receipt /private/existing/receipts/pt-install-1.json
```

Read the result's `state` and `matches_installed`/`matches_original` flags, not
only its exit code: a successful inspection can report `state: "changed"`.
Rollback requires the observed page still match the installed snapshot, or it
refuses replacement. An original file is restored byte-for-byte with its mode;
an originally absent file is removed. Other files and the route directory stay
in place. These checks detect observed changes and do not claim a transaction
across concurrent processes.

To finish an install→rollback trial with the candidate installed, run the same
install command with a **new** receipt filename, then read it back. Receipts are
immutable and contain exact page bytes; keep them outside all served directories.

## Qualification and boundaries

The independently received model passes 150 of 150 cases against the pinned
Python engine. The corpus includes analytic priority/date boundaries, allocation
order, successors, duplicate/amended records, leap/DST/year boundaries, annual
limits and independently generated multi-patient inputs. Six inherited cases
exercise the accepted omission of reasonless items; an additional case confirms
past scheduled evidence survives when it supports an annual-limit alert. Every
item field, evidence entry, ordered visit array and counter matches the native
result. Repeated evaluations are identical and inputs remain unchanged.

Receipts identify the exact engine, model and generated page. The earlier
149-case pass against engine
`27c21bd` and page `cd5e60ad` is historical evidence; it does not qualify a changed
source or artifact.

The final artifact passes 19 actual Chromium control groups (581 assertions),
covering edited scenarios, exact worklist reasons/evidence, all eight patient
ledgers and every recorded visit allocation, cumulative edits, boundary/reset
actions, dirty and invalid states, recovery, pending/no-auth cases, mobile
date-only behavior and the no-JavaScript fallback. No page error, external
request or persistent browser storage was observed. An actual six-step
install/readback/rollback/final-restore trial also passes on the same page.

- Model SHA-256: `c71fe28b6c70c72127acbcb6ebfdf3e99d7e4b0a75ed73a7afb7b4ee3fd662f9`
- Generated page SHA-256: `5d717ef14a8d1d0939dc96c9fac6922681d13158cfe5ce3ea4c05e70ea769727`
- Generated page size: 130,462 bytes; authoring and served copies are identical.
- Browser: Chromium 153.0.8010.0; separate visual inspection at 1280 and 320 CSS
  pixels found no horizontal page overflow.

Exact source, oracle, browser and installation receipts are preserved by the
independent receiving lane. Earlier artifacts and renderer failures observed
with nearly full shared temporary storage remain separate historical evidence. These results
qualify the synthetic artifact; publication is a separate delivery step.
No existing PT core/UI/export, Utility Watch, freight, workflow or shared
landing-page file is changed.
