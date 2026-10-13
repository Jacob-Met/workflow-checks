# Freight sample load-count admission

The `freightpkt generate` CLI accepts a nonnegative integer for `--loads`.
A negative count is refused before the generator is imported or called:
exit 2, an argparse diagnostic mentioning `--loads must be nonnegative`, and
no successful stdout. An absent output directory stays absent; existing
fictional sample files and directories remain unchanged.

From `freight_packets`, using an existing Python 3.10+ interpreter:

```sh
python -B -m freightpkt generate --out sample-two --loads 2 --seed 7
python -B -m freightpkt generate --out sample-empty --loads 0 --seed 7
python -B -m freightpkt generate --out not-created --loads=-1
```

The last command is intentionally rejected. Zero remains a valid request for
an empty fixture, and omitting `--loads` retains the existing default of 24.
Positive counts, signed seed handling and deterministic generated content are
unchanged. Choose the intended output directory before running a valid command:
accepted generation retains its existing ability to replace sample files.

This guard belongs to the CLI's `generate` branch. The lower-level
`synth.generate` API, generator source, other subcommands and all report rules
are unchanged. This is not a general transactional writer or an overwrite
confirmation mechanism. Every generated company, driver, facility and amount
is fictional; no invoice or payment operation is performed.

## Focused regression

From `freight_packets`:

```sh
python -B -m unittest discover -s tests -p test_generate_load_count_dec0.py -v
python -O -B -m unittest discover -s tests -p test_generate_load_count_dec0.py -v
```

Four methods execute five actual CLI children per mode. They check negative
counts against absent and independently authored existing output, zero and
two-load complete UTF-8 content from the original probe (normalizing CRLF to LF for platform text writes), and the existing
24-load default. Child Python flags follow the selected normal or optimized
profile. No report pipeline, server, browser or external service is invoked.

The optional `FREIGHT_COUNT_TEST_ARTIFACTS` environment variable names a new
artifact directory for complete child stdout/stderr and command/exit records.
Ordinary test fixtures are temporary. The delivered evidence retains the
original positive and zero-load fixtures, original negative observations, both
source versions, and separate author/independent receipts. Directory inventories
establish retained final state; they are not operating-system write-call traces.

