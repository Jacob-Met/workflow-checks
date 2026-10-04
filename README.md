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

## Contact

Interested in a scoped pilot on your own redacted exports? See [jacobmetoyer.com](https://jacobmetoyer.com).
