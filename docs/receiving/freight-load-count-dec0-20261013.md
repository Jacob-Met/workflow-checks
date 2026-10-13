# Freight negative sample load counts — dec0, 2026-10-13

## Operator outcome and scope

An accidental negative `--loads` count now produces an argparse error before
the Freight sample generator can create or replace fictional input files.
Zero remains a valid empty fixture; positive counts and the 24-load default
retain their existing behavior.

Source selection: main `00f578c39df398aa7089f22dfdd7d50590c8c7d4`,
tree `2776bb8bf789a876abdde4541e76e62cebd135a5`.
[Owned scope](https://github.com/Jacob-Met/workflow-checks/issues/112).
Current composition, publication and integration pins are separate observations.

Only two lines in the `generate` branch of `freightpkt/cli.py` change.
The guard precedes generator import/call and uses the existing argparse error
path. Removing those exact CRLF lines restores the complete original file.
The `synth.generate` API and source, accepted generation, other subcommands,
report rules and workflow files are unchanged. Three new support files contain
the dedicated regression, [guide](../../freight_packets/GENERATE_LOAD_COUNT.md)
and this receipt.

| Path under freight_packets | SHA256 | Git blob |
|---|---|---|
| freightpkt/cli.py | 4bd5acb3259d2537dbe04995188951bb91e71d043c5ee4ce0ab8f090c309ff3f | 168bcd1a310873a3fef065c52c251919b4842192 |
| tests/test_generate_load_count_dec0.py | d3cef55881e5a4852fa652fcea11e0f99c86064d5332b36c44bb2e83604fcf24 | cdd964b0a330ca4bf577b401472d881153311f74 |
| GENERATE_LOAD_COUNT.md | f6f5ed8858753bc12567c0b400718440e79645b7c6846b23eed46120e3fbc11a | dbbd070827afcb06e3764496de3d041e11a48631 |

Original CLI: 2,672 bytes, SHA256
`268ced979f2863c2dac85b9e950c70e3818c827f222522f6374b4ecdcb9b8f15`,
Git `a64a4d60816654595b1767ff9f96cd2cd9c49c32`.
Candidate: 2,750 bytes, all 65 line endings remain CRLF.

## Original actual CLI observations

Four original CLI processes used the exact four-file generate closure and
only fictional data. Two-load and zero-load controls succeeded. Negative
`--loads -1` against both absent and existing output also exited 0 and wrote
empty data. The existing two-load fixture lost seven file bodies; ten files
were rewritten. The positive fixture and all source bytes/modes/mtimes were
retained unchanged. No product function or service was substituted.

Full command/exit records, child streams, generated files and before/after
inventories are retained. Original receipt SHA256:
`8d88e0409639791633d66e893c7408a50bc50d107d93a8a7c03ab1e1b04fbffb`.
Exact probe:
`5999cd33cc2246a4cd26a1deeb1e0af993ca4060021f111c5311f13af67e7e59`.

## Author regression and preserved test correction

The initial four-method regression used test SHA256
`f40460509bb92610e1f0137d581bdf05fbb91bab4a9e80ac376ae1fa0821b7a3`.
Original source passed two control methods and failed the two negative-count
admission methods, in both normal and actual optimized Python. The candidate
passed all four methods in each mode. Five actual CLI children per source and
profile give 20 children; complete suite and separate child stdout/stderr and
command/exit records are retained. Zero/two-load full file hashes matched the
retained original seed-7 fixtures; default count remained 24 loads/48 stops.
Receipt SHA256:
`8e4041dc7e05b4e6926dab3871a847a9823ba3201b496208e539e171f2cf128a`.

Before publication, static self-review identified that literal Linux raw output
hashes in the test could reject unchanged Windows text files because of newline
translation. The old test, guide, source fence and all 20 observations remain
unchanged. The maintained test now compares complete file content after
normalizing CRLF to LF; its reference hashes are derived from the same retained
original files. Other test methods remain byte-exact. The production candidate
did not change.

Only the revised positive-content method was then run normally and with actual
`-O`: one method/two CLI children per mode, all passing. These four new children
do not replay the admission or default-count cases. Full streams and an exact
test diff are retained, receipt SHA256:
`4395b492de2bf1b5dccdbe6f7b095fecc20c4efa6919190b5979b8e0090f8fb8`.
This is a focused correction check, not a full rerun of the revised suite or
Windows qualification.

## Independent runtime receiving

Engine froze separate expectations before candidate exposure and authored its
own receiver. Ten actual ordinary CLI processes ran once, five per source.
The original passed three controls and failed both negative-count contracts;
the candidate passed all five.

Both corrected negative cases exit 2, emit empty stdout and a controlled
95-byte stderr diagnostic with no traceback. An absent destination stays
absent. An independently authored nine-file fictional inventory, including
directory and file modes/mtimes, remains exact after refusal. Explicit zero,
two and default-24 controls use seed 11; their complete generated file bytes
and stdout/stderr equal the corresponding original same-host observations.
The receiver verifies the whole-source two-line inverse and unchanged
`__init__.py`, `__main__.py` and `synth.py`. All original/copied source custody
and all 20 raw streams/generated files are retained.

Independent receipt SHA256:
`1bb4eb7c81dfdb4807ba6a419fab0abbf0d2eb3ead934616c08e35d8c9877d7e`.
Exact receiver SHA256:
`d9f7e4332599a9c15266a9ba43c5a9eb007d45392e6c78c63cbc93df1d81422f`.
Pre-candidate expectations SHA256:
`decd877461fc7391a432d70f5340c02358ca830e0b9432e718892585febd09d9`.

Consumer separately accepts the complete three-file runtime/test/guide fence
and its author evidence, including the original versus revised test distinction.
No product code, generator, test or CLI was executed by that static review.
Receipt SHA256:
`33226e9694f8d42d4d752c8ba1eacfd54c109e660dadf12687a3dc434e1007b8`.

## Boundaries

All examples are synthetic and local. No report pipeline, server, browser,
PDF, installed consumer, invoice or payment operation is qualified here.
Independent runtime coverage is ordinary Python; optimized coverage belongs
to the author courses. No Windows execution is claimed. Final-state directory
inventories are not syscall traces.

Valid generation still replaces sample files as before. This guard is limited
to negative counts entering through the CLI; it does not change direct API
admission or add general transactional/overwrite protection. The current
no-Actions direction, unrelated owners and required merge checks remain
separate publication gates. Zero hosted runs or checks is never a CI pass.

