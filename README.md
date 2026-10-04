# workflow-checks

Three working proofs of concept for verification-first back-office checks.

> **Synthetic data, not deployed for any client.** Every company, person, account and amount in this repository is invented by a seeded generator. These are demos of an approach, not products, and no savings or accuracy figures are claimed for real data.

| PoC | For | Folder | UI |
|---|---|---|---|
| Detention / chargeback packet builder, plus a carrier invoice vs rate-con vs POD match | Asset carriers and freight brokers | [`freight_packets/`](freight_packets/README.md) | http://127.0.0.1:8765 |
| PT authorization and visit-limit tracker, with a daily re-auth worklist | Multi-clinic outpatient physical therapy | [`pt_auth/`](pt_auth/README.md) | http://127.0.0.1:8766 |
| Utility bill exception checker, with a payment-approval queue | Multifamily operators paying portfolio utilities | [`utility_watch/`](utility_watch/README.md) | static `out/report.html` |

Shared principles:
- **Synthetic data only.** Seeded generators write an independent answer key (`expected.json`) that the tests check against.
- **Deterministic rules first.** Anything uncertain goes to a human exception queue, and nothing is sent, filed or submitted.
- **Append-only `audit.jsonl`.** Every decision carries evidence pointers, formatted as file:row.
- **Minimal dependencies.** The runtime uses only the Python standard library (3.10+), and `pytest` is used for tests. There are no paid APIs and no network calls. The UIs are single-page, use no CDN, and bind to 127.0.0.1.

## Quick start (Windows PowerShell)

```powershell
pip install pytest            # only needed for tests
.\demo.ps1 freight            # generate + run + serve the freight PoC
.\demo.ps1 pt                 # generate + run + serve the PT PoC
.\demo.ps1 utility            # generate + run the utility checker, open report.html
.\demo.ps1 test               # run all three test suites
```

## Running on Linux / macOS

```sh
pip install pytest
(cd freight_packets && python3 -m pytest -q)
(cd pt_auth && python3 -m pytest -q)
(cd utility_watch && python3 -m pytest -q)
```

## What the tests do and do not show

- **They show internal consistency.** Each generator writes the synthetic data and an `expected.json` answer key from the same seed, and the tests check the engine against that key plus hand-written edge cases (see each `HARDENING.md`). A green run means the rules do what the README says on data built to exercise them.
- **They do not show real-world accuracy, savings or time saved.** No result here was measured on a real company's exports, so none is claimed. Any figure in a demo script (for example a detention total) is a property of the synthetic sample, not a typical or expected result.
- **A real pilot starts from a baseline.** The per-PoC READMEs list what a pilot needs: the client's own exports, their real rules, and a manual audit to compare against. Claims about a pilot would be limited to what that comparison measured, for that client and period.

## Status, support and contributions

- **Demos, provided as-is.** No warranty, no support commitment and no maintenance schedule. They are not production software and must not be pointed at real patient, financial or personal data as they stand (see `pt_auth/README.md` for the HIPAA gaps).
- **Not accepting outside contributions** for now. Issues may be read but are not guaranteed a reply.
- **Built with AI coding assistance**, then checked by the test suites in this repository; CI runs them on every push.
- **Licensed under the MIT License** (see [`LICENSE`](LICENSE)). The runtime has no third-party dependencies; `pytest` (MIT) is a test-only dependency and is not distributed here.

## Contact

Interested in a scoped pilot on your own redacted exports? See [jacobmetoyer.com](https://jacobmetoyer.com).
