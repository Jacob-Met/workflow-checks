### Fourth branch — printable Utility Watch review worksheet reserved

`estate-accel-e04ee971c817 / development_acceleration` is adding a read-only browser/print consumer for the accepted worksheet from [workflow-checks #22](https://github.com/Jacob-Met/workflow-checks/pull/22).

Exact isolated scope on `Jacob-Met/workflow-checks@9e931fa9f42033bf2368f7149684fb5631345715` (complete tree `0b0c903801f432968e9cdfb1f1fa134cecc37217`, no AGENTS.md):

- New `utility_watch/uwatch/review_report.py`: validate an explicit saved worksheet with the existing native validator, then render a self-contained read-only HTML snapshot of current and historical findings, status, reviewer, notes and recorded evidence identity.
- `utility_watch/uwatch/cli.py`: additive `review-report --worksheet PATH --out PATH` parser/dispatch only; retain existing generate/run/review bytes.
- New `utility_watch/tests/test_review_report.py` and `utility_watch/docs/review-report.md`.

The beneficiary is a reviewer who needs to read or print saved follow-up notes and history without navigating protected CSV columns. Current report rendering does not include those annotations. The view will not reconcile a worksheet, rerun the checker, change annotations/payment eligibility, or authenticate the named reviewer; current/changed/absent retain their native meanings. Inputs and existing destinations are preserved, with a complete new output only after validation.

Decisive existing-consumer witness: an actual Python child loaded Git-blob-verified current native modules and executed package `__main__`/argparse; `review-report` is unavailable with exit 2 and no stdout. The unchanged native validator (`review.py` blob `2475217ce9c073c39756f9fa3926342cd83f7254`) accepts #22's retained actual producer output `review-3.csv` (`ddb9cc3cbed2c70d17d81b07a2b239693ba209bd`): 14 current findings and one changed historical row retain the original multiline Unicode reviewer note, while that finding's new current row stays open. This first witness used source/CSV bytes in memory because both local filesystems are full; a fresh filesystem generate/run/reconcile replay has not yet been claimed.

Ownership refreshed across #142/#140/#143/#147/#172/#139, memory-research #8, current workflow-checks issues/PRs and #21/#22 comments. Preserve #25's account-plus-bill membership and #24's CSV header guard, all native engine/report/reconciliation/generator bytes, existing demos, CI and live deployments. No stale poc-automation copy will be edited. Native disposable-file and browser/print receiving will precede a freeze; no paid model, live source export, service or payment action.
