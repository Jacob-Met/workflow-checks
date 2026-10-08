# Reproduce the independent native-oracle comparison

From the repository root, with Python 3.10+ and Node.js 18+ on PATH:

```sh
python demos/ptauth-whatif/tests/parity.py
```

The script also accepts an absolute script path from another working directory.
Use `--node /path/to/node` if Node is not on PATH. It needs only the standard
Python and Node runtimes; it installs nothing, makes no network calls and
changes no repository file. It prints a JSON receipt and exits nonzero on a
source, oracle or model mismatch.

`cases.jsonl` is the unchanged, independently selected 150-case receiving corpus
for Python engine Git blob `39c97f35d61ff949b5c2381f0ad60d7af8d74226`.
Its SHA-256 is
`21ccfcace933dec7a047f9efb2464ec14e6b8ca8663775aafa37571a0221a324`.
The corpus keeps every input and every recorded native output. All people and
payers in these cases are fictional. No patient file or external dataset is
needed.

The Python driver checks the exact three repository source files in `pins.json`,
then invokes their actual `build_worklist` function through the receiving
dataclass/date serializer. Every fresh result must equal its recorded output.
Those fresh results pass directly to the existing Node comparator over stdin;
no temporary corpus is created. Node imports the pinned `model.mjs` and compares
every item field, evidence entry, ordered visit array and counter. It also checks
repeat determinism and that the caller's input is unchanged.

The inherited case named `legacy-stale-scheduled-p3-empty-reasons` retains its
original scenario name. Its current expected worklist is empty. Six inherited
cases exercise the accepted PR #12 omission of reasonless placeholders. The
additional `pr12-stale-anchor-retained-through-annual-cap` case confirms that
past scheduled evidence survives when it supports a real annual-limit alert.
No new rule implementation or scenario generator is included here.

Expected current result: 150 native results equal the recorded outputs and
150 browser-model comparisons pass, with zero failures, unchanged inputs and
identical repeat results. The pin is explicit: a future source change must be
reconciled and independently qualified before updating it.

These files make the already completed model comparison portable. Full actual
browser, generated-artifact, installation and historical negative receipts
remain in the independent receiving packet; this command does not claim to
rerun those separate checks.
