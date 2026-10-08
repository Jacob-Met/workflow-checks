# Utility Watch account-specific bill decisions

This packet contains the accepted account-and-bill identity correction for
workflow-checks issue 25. The source scope remains four paths: engine.check,
one maintained regression file, README and HARDENING. The separate CSV-header
owner retains engine._rows and its test. Any subsequently merged header change
must be preserved by root's final current-parent composition.

The correction keeps duplicate exclusions, duplicate holds, flags and exceptions
within the account that owns each bill ID. Same-account duplicate rules, native
usage/rate thresholds, output schemas and account/invoice payment matching remain
unchanged. A reused exported ID on another account no longer removes a clean bill
from the advisory queue or removes a relevant historical baseline.

## Exact source

- Original commit: 65461ca8f6bd636cd85c0086210ccb1e6837fbee.
- Last verified receiving parent: 9e931fa9f42033bf2368f7149684fb5631345715;
  freight integration preserves all four Utility before-images.
- Original engine SHA256: 48c968584d0494ee5fb0538fc7d4c685c2cc3128a45c33f57c2079234cdb7775.
- Accepted engine SHA256: ff0dc3a473235c55639e4373e3b5a4c786a0cd9ae7badd2be9113f39a4efd3d0.

## Authored qualification — memory_path

Five actual CSV/CLI histories produced one passing control and four account
isolation failures on the original code, then five passes on the correction.
The eight maintained regression methods produced six failing methods and two
passing controls on the original source (ten failure records with subtests),
then eight passes in normal and optimized Python. Four unchanged maintained
Utility test modules passed 81 methods on both original and corrected source.
The clean two-account control's six generated files were byte-identical.

The author archive, manifest and receipt are unchanged from publication-v1.
Their full inputs, outputs, source snapshots, raw negative/positive logs, patch
and setup failures remain historical records. The transient ENOSPC partial-copy
and default-interpreter missing-pytest incidents were setup failures, not tests.
The retained suite used the existing read-only Python 3.12.14/pytest 9.1.1 runtime.

## Independent receiving — root

Root independently created ten native scenarios and ran them with the original
and corrected engine: original three passes/seven failures, corrected ten passes.
A separate eleventh candidate scenario passed the existing review CLI's source
migration and same-source annotation-retention workflow. These counts come from
30 actual native CLI processes on the existing Mac Python 3.13.7 and are separate
from the authored test counts.

The five queue scenarios cover another account's late-fee flag, zero-usage
exception, unknown-account exception and either member of a duplicate pair.
Four historical scenarios cover prior-year and trailing-three baselines with
the unrelated account sorted before and after the protected account. Native
usage, effective-rate and naive comparison findings are retained. A compound
delimiter collision control preserves distinct tuples. All six clean-reference
files are byte-identical and every native source file stayed unchanged.

root-evidence.tar.gz preserves all 384 payloads plus its manifest: exact source
contexts, independent carrier, four-CSV fixtures plus synthetic markers,
reports, commands, original failed comparisons, and review worksheets. The
direct root review/result/carrier match their archived bytes. The carrier is
named receive_account_identity.py and is not a discoverable pytest test.
root-intake-receipt.json records complete readback and source/hash binding.

## Existing review binding and remaining integration

review.py, report.py and the CLI remain unchanged. Review evidence includes the
engine source hash: upgrading the checker can make an old annotation historical
and require a new current review even if rounded finding text is unchanged.
The independent native review check verifies the prior note remains exact in
history and a current annotation survives a subsequent same-source reconciliation.
No annotation is automatically waived or approved by this correction.

Root owns final current-parent preservation, hosted gates and publication.
This packet itself does not claim a PR24 merge, hosted success or deployment.
All inputs are synthetic; no customer bills, payments, providers or services ran.
Historical tests stay inside the evidence archives. Only
utility_watch/tests/test_account_bill_keys.py is a new maintained test module.
