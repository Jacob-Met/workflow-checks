# README promise audit

Audit date: 2026-09-29. Scope: `utility_watch` only.

| README check | Implemented? | Actual behavior |
|---|---|---|
| `USAGE_SPIKE` | Yes | Compares usage/day with the same service month one year earlier and flags ratios above 1.5. Cross-month periods use the month containing most service days; leap-year day counts are normalized. Missing or incompatible-unit baselines become exceptions. |
| `RATE_CHANGE` | Yes | Compares positive-usage bills of at least $100 with the median effective rate from compatible-unit bills in the preceding 12 months. Requires at least six historical rates and flags ratios above 1.2. |
| `DUPLICATE_BILL` | Yes | Detects a repeated nonblank invoice number or equal period and amount within an account. The later copy is flagged and both copies are withheld from the payment queue. Blank invoice numbers are exceptions, not duplicate keys. |
| `PERIOD_OVERLAP` | Yes | Detects inclusive date overlap against the prior period with the furthest end date and reports overlap days. This covers nested periods. Exact duplicate bills are handled by `DUPLICATE_BILL` instead. |
| `MISSING_BILL` | Partial | For monthly common accounts with at least one bill, checks each completed service month from the later of the first bill month and evaluation start through the last full month. The schema has no account-open date, so it cannot safely call months before the first exported bill missing. |
| `LATE_FEE_OR_PAST_DUE` | Yes | Flags any non-zero late fee or prior balance, including negative credits/adjustments. |
| `PAYMENT_MISMATCH` | Yes | Groups payments dated on or before the review date by account and invoice, then flags multiple payment rows or a total differing from net amount due by more than $1. |
| `UNPAID_PAST_DUE` | Yes | Flags evaluated, nonduplicate, known-account bills with no matching payment when due date is before the review date. Credit bills and blank-invoice bills are withheld from this automated payment match. |
| `VACANT_UNIT_USAGE` | Yes | Joins unit accounts to vacancy rows by property and unit, requires vacancy to cover the whole service period, and compares usage/day with the utility ceiling. Partial or absent vacancy coverage becomes an exception. |

## Queue and evidence promises

- Unknown accounts, missing baselines/invoices, zero or negative usage, credits/zero balances, changed usage units, partial vacancy, missing standby thresholds, and unit bills without vacancy evidence go to `exceptions.csv`.
- Any bill in the exception queue, either side of a duplicate pair, and any flagged bill is excluded from `payment_queue.csv`. The queue is advisory and does not pay anything.
- Duplicate-history exclusions, duplicate holds, flags and exceptions use the account together with the bill ID. A matching bill ID on another account does not change its baseline or payment-queue eligibility.
- Flags, exceptions, and payment-queue decisions carry `file.csv:row` evidence and are appended to `audit.jsonl`.
- Generated datasets retain the synthetic label. Client folders without `expected.json` get a review-only client report instead.

## Known limits left intentionally

- Account or meter renames cannot be joined automatically because the input schema has no stable meter identifier or alias table. The renamed account receives `NO_BASELINE`; a human must confirm the relationship. Cosmetic usage-unit case changes are tolerated, but actual unit changes receive `USAGE_UNIT_CHANGED` rather than an attempted conversion.
- `MISSING_BILL` cannot assess an account with no bills or months before its first exported bill because the account schema has no service-start date.
- Vacancy analysis assumes the occupancy export completely covers the billed unit and dates. It does not prorate usage across partial vacancy.
- Rate thresholds and standby ceilings are defaults, not client-calibrated tariff models.
- Dates are intentionally limited to unambiguous ISO or US month-first formats. PDF parsing, locale-specific day-first dates, and currency conversion remain out of scope.
