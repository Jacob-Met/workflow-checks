# Utility Watch: usage and rate explorer

A standalone static interpretation of two existing Utility Watch rules on one
invented gas account. Change consumption, bill amount and inclusive service dates,
then recheck the daily usage and effective rate against the original sample history.
The original fixture stays unchanged. Presets are synthetic examples, not suggested
consumption levels or prices for a real property.

## Run

Python 3.10+ can serve the files; the browser runtime has no package, CDN, account,
API, storage or payment dependency. From this directory:

```sh
python3 -m http.server 8768 --bind 127.0.0.1
```

Open `http://127.0.0.1:8768/`. A server is required for local module/fixture loading.
This directory is separate from the existing shared sample site and its generator.

## What the two checks mean

`USAGE_SPIKE` compares inclusive-day-normalized consumption with the compatible
service month one year earlier. Its threshold is strictly greater than 1.5×; a
positive reading above a zero baseline is also flagged. Service periods belong to
the month with the most days; a tie selects the latest month among those maxima.
The ending month wins when it is one of the tied months.

`RATE_CHANGE` compares amount/usage with the median of compatible positive bills
in the previous 12 service months. At least six rates and a current amount of $100
are required; its threshold is strictly greater than 1.2×. The source defaults,
18 account bills, source rows and fixed evaluation dates are generated directly
from the existing Python checker and its synthetic sample CSVs.

The display explicitly scopes itself to these checks. A duplicate current bill is
withheld before comparison, matching the source ordering. Missing baselines,
incompatible units, zero/negative usage and credit amounts retain review signals.
An unevaluated historical period is not presented as a clean bill. Other utility
checks, approval queues, actual review decisions and payment matching are outside
this explorer. Nothing is paid, filed or sent, and no real-world accuracy is claimed.

Inputs use ISO dates from 1900 through 2100, at most 366 inclusive days, finite
numbers bounded to ±1 billion, and bill amounts with at most two decimal places.
These are explicit browser-demo bounds, not changes to CSV ingestion. Invalid edits
remain in the form; the last result is labeled as stale until a successful recheck.

## Source authority and verification

The authoritative logic remains `utility_watch/uwatch/engine.py`. This static
browser projection is pinned to Git blob
`9deb205ad468381ffc91716f0d7ae6ab88d76f2a`, received from main
`26d6bb87ee3269930db4ab5885cde2b74e93bf7e`. `fixture.json` records each consumed
source/input blob and SHA256. Mixed fixture/model source versions refuse to load.

The builder imports the actual unchanged Python `load()` and `check()` functions.
Its 91 oracle cases run against the full original portfolio with only the chosen
bill altered. The cases compare the two advertised flag codes, exact evidence rows,
relevant exceptions, duplicate suppression and the actual `Bill` date/day properties.
They cover strict usage and rate boundaries, the rate amount cutoff, zero/negative values,
cross-month and leap dates, outside-window periods and duplicate intervals.

From this directory:

```sh
python3 build_fixture.py --check
node --test tests/model.test.mjs
```

`--check` refuses stale generated fixtures without rewriting them. After an
intentional source update, run `python3 build_fixture.py`, update the qualified
engine pin if appropriate, and rerun parity and actual browser receiving before
publishing. A changed rule must not be accepted by merely regenerating its oracle.

The optional native browser receiver is `tests/browser.mjs`. It uses an existing
Playwright/Chrome installation, a fresh profile and an ephemeral loopback server.
It checks actual form/preset interactions, stale-result and invalid-edit recovery,
exact source evidence, source-version refusal, keyboard operation and both viewport
sizes. Every served file hash is recorded; external requests are blocked.

## Install, roll back and read back

The installer copies only the five static runtime files into an absent dedicated
target. It records their exact SHA256 values and the prior absent state. It never
replaces an existing directory or changes a service, browser profile, public route
or shared landing page.

```sh
python3 install.py install --target /tmp/my-utility-explorer
python3 install.py readback --target /tmp/my-utility-explorer
python3 install.py rollback --target /tmp/my-utility-explorer
python3 install.py install --target /tmp/my-utility-explorer
python3 install.py readback --target /tmp/my-utility-explorer
python3 -m http.server 8768 --bind 127.0.0.1 --directory /tmp/my-utility-explorer
```

Rollback verifies ownership and every remaining file before removing only this
installation. Changed, redirected or unexpected files cause refusal and are
preserved. Source, tests and receiving evidence remain in the repository.

## Estate scope

This implements new isolated source for the unfinished native product objective
`build-demo-utility-whatif` / `goal_a181ba826d504f53bb78`, under cohort
`estate-81ba1ed0179c`; repository coordination is issue #15. The prior goal was
settled failed after read-only calls. This contribution does not replay that goal,
claim a native worker lease, overwrite another owner's source or alter its state.
The broader public sample site and report-reader remain separate.
