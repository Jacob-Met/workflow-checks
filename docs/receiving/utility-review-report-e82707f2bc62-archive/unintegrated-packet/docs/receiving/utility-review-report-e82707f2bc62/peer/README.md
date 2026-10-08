# Independent Utility Watch review-report receiving

This receipt qualifies the frozen native report consumer for [workflow-checks #30](https://github.com/Jacob-Met/workflow-checks/issues/30). The reviewer wrote and froze the four-case protocol before reading candidate source. The final identical test produces four unsupported-command failures on original commit `9e931fa9f42033bf2368f7149684fb5631345715` and four passing methods on the frozen candidate.

The receiver uses real `python -B -m uwatch run`, `review` and `review-report` subprocesses. All CSV inputs are explicitly synthetic, and protected worksheet fields come from the native reconciliation implementation. It does not construct replacement seals or substitute a renderer. Twelve native setup processes succeed; the candidate then gives two successful report processes and four deliberate refusal processes.

The source-change/restoration case retains distinct account identities even when bill keys match. Its final worksheet contains six current, six changed and one absent finding. The report has thirteen corresponding semantic articles with exact saved annotations and evidence pointers. Old annotations do not revive when former source evidence returns. A separate exception-only case receives BOM/reordered CSV and literal multiline review text. Missing-manifest and destination-alias/failure cases preserve source, saved worksheets and existing destinations.

## Exact source and test

- New `uwatch/review_report.py`: Git blob `b8ce9d487ddb9872fb1a53eedebcb33def9feffc`; SHA256 `a8d6a5d8b0d071e40474757a7fcca6c74373383584c2551afe78c2e82adc83ff`.
- Additive `uwatch/cli.py`: Git blob `48b849d17795c0eb032acb447c0efce48e743b88`; SHA256 `e406ec30f156e70fac472b26f70f2ec02988841528d0853b74c56a4ec2ce720b`.
- Receiver: Git blob `aa191f85b6d9e533751041284ea2fad193f380bf`; SHA256 `aa29c49faa0b75f9dc25324786c712bb786458730f9790d4ffa0113a60fabf95`.

Six existing runtime files match their original blobs. Each native case also checks that all runtime Python files remain byte-identical throughout execution. The JSON receipt records output, source, test and log hashes. The ZIP preserves exact original/final protocols, both baseline runs, candidate logs and generated native evidence. Every ZIP member was read back and checked against its recorded SHA256.

The first blind protocol overconstrained inert HTML search metadata; the reviewer corrected only that assertion before candidate access and retained the original evidence. No production correction was requested by this receiver.

## Acceptance boundary

Local receiving ran on Python 3.12 using only the standard library. The HTML assertions parse actual emitted semantic articles and literal text. No installed browser was available, so this receipt does **not** qualify interactive filters, visual layout, print rendering or browser behavior. Full current-parent repository composition and hosted CI remain the author's gates.

The test is ordinary `unittest` discovery code under `utility_watch/tests/`. With the product directory on `PYTHONPATH`, run its normal discovery invocation; without `UWATCH_RECEIVING_OUTPUT`, all generated files live in a temporary directory. Setting that optional variable preserves per-case evidence under the chosen directory.
