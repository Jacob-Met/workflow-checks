# PT source distribution and CI receiving

The frozen seven-path contribution fits the supported source-checkout run path. No packaging, install, CI or build metadata change is required to include `uncovered.py`, the updated adjacent UI, or the generated CSV. This is source wiring evidence; no package installation, build, browser or behavior suite was run for this check.

## Exact source observation

A fresh read of `Jacob-Met/workflow-checks` main still resolved to `9e931fa9f42033bf2368f7149684fb5631345715`, tree `0b0c903801f432968e9cdfb1f1fa134cecc37217`. The complete 403-entry, non-truncated tree has no Python package/build manifest or dependency manifest among the names recorded in `source-readback.json`. The supported distribution is the checkout described by the root and PT READMEs, not an observed wheel or installed package.

| Existing path | Exact Git blob | Receiving role |
| --- | --- | --- |
| `README.md` | `d13a764020918c215f91263d97d6c949a827d385` | Python 3.10+, source-directory CLI and test instructions |
| `demo.ps1` | `04e135cf3ddc97654e58393e9b14c3541fe12d94` | Changes into `pt_auth`, then invokes `python -m ptauth` |
| `scripts/build_pages.py` | `c5c5506e5672b52362a09f0c0dadb870dc03c9ab` | Tests first; invokes the same PT CLI directly into `docs/pt` |
| `.github/workflows/tests.yml` | `d72b89ae3efb2963fbe7386021f467e82a8e1f2e` | Push/PR matrix for Python 3.10 and 3.12; installs pytest and runs it in `pt_auth` |
| `pt_auth/tests/conftest.py` | `e4c2fd4ff87c63061fb6a10f0fb01228c46c0875` | Adds the PT source directory to Python's import path |
| `.github/workflows/freight-whatif.yml` | `0c2981495c8167ea35cc87ac2ba41536f36ba18e` | Separate path-filtered freight job; its Node setup does not configure the PT job |

## Included runtime paths

The unchanged `ptauth/__main__.py` imports `.cli.main`. Its `run` branch imports `.report.run`; the frozen new report imports `.uncovered` directly from the same package directory. Publishing all seven recorded source paths therefore includes the new module without a package-file whitelist.

For `serve`, unchanged `web.py` imports the same report and reads `Path(__file__).with_name("ui.html")`. It serves the actual updated UI from the source package. The existing `/out/<file>` handler resolves files beneath the chosen output directory rather than enumerating export names, so it includes `uncovered_visits.csv`. Existing same-timezone saved reports may still need a worklist rerun to acquire the new field; the candidate explicitly reports that state.

The source-site builder runs the PT CLI with output `../docs/pt`. Its normal report invocation generates the new CSV, summary and full digest directly in that directory; no copy allowlist omits them. The existing static index links the printable digest and worklist CSV. It does not add a named link for the new CSV or publish the interactive local UI. No static site rebuild or deployment is claimed here.

## Interpreter and test entry points

The runtime remains within the documented Python 3.10+ standard-library path. Named clinic zones retain the existing IANA-database requirement; the PT README already describes `tzdata` where the system lacks that database. This contribution adds no runtime dependency.

The current CI command is `python -m pytest -q`, with working directory `pt_auth`, on Python 3.10 and 3.12. The new `tests/test_uncovered_review.py` follows the existing discovery location and contains a `unittest.TestCase` class. Its explicit source-directory default also works in the existing repository arrangement. The focused independent command remains `python -B -m unittest discover -s tests -p test_uncovered_review.py -v`.

The Node child is conditional on `shutil.which("node")` and uses `node --test` plus `node:test`. The PT CI job does not install or pin Node; absence is an explicit unittest skip. The IANA-specific method likewise declares a skip if that zone database is absent. Author qualification used Python 3.12.14 and Node 24.19.0 with zero skips; this distribution review did not execute the Python 3.10 matrix or pytest. Root should use the actual PR job results and skip counts for that evidence. Real-browser receiving is a separate review boundary.

## Scope and conclusion

All six readback files match the exact immutable-ref Git blobs and lengths. The seven candidate paths still match candidate manifest `46a503ccdd0c793cc1ad4ec1759e6d615c12c67e7aec8fad93cff2f55e8dadab` at local candidate `9676a5a20f3adab0ccf46e31e3052de04f50d267`. Existing metadata bytes were not changed.

There is no missing packaging prerequisite for the supported local run/serve path. Outstanding receiving evidence consists of actual hosted CI results and the separate browser review. A public sample-site update would require its existing rebuild/publication procedure and is not part of this source-only check.
