# Inspect a finding's source CSV records

Use `evidence` when a flag or exception needs the actual source records behind its
file-and-row pointers. Supply the same CSV export and a saved native
`summary.json`. The command checks that report against the current checker and a
fixed snapshot of the supplied export before writing a new JSON file.

From `utility_watch/`:

~~~sh
python -m uwatch evidence \
  --data client_export \
  --report out/summary.json \
  --kind flag \
  --account A-01 \
  --key BILL-001 \
  --code USAGE_SPIKE \
  --out inspected-bill.json
~~~

Choose the identity from `flags_detail` or `exceptions_detail` in `summary.json`:

| Option | Saved report field |
| --- | --- |
| `--kind flag` | A member of `flags_detail` |
| `--kind exception` | A member of `exceptions_detail` |
| `--account` | That finding's `account_no` |
| `--key` | That finding's `key` |
| `--code` | A flag's `code`, or an exception's `reason` |

All four selectors must match exactly. The same bill ID on two accounts and two
codes on one bill remain separate findings. Missing and ambiguous identities are
refused. Review annotations and payment-queue entries are not finding selectors.

## What the file contains

The `uwatch-evidence-v1` JSON document contains the selected finding, its existing
source-bound finding/evidence identities, the report's dates and data mode, and
the records cited by that finding in their original pointer order. Repeated
pointers remain repeated. Each record has:

- `pointer`: the checker's original pointer, such as `bills.csv:3`.
- `file` and `record_end_line`: the source filename and the pointer's line number.
- `columns`: the original CSV header order.
- `fields`: the original decoded cell strings, including spaces, commas, Unicode,
  embedded newlines and formula-looking text. Values are not evaluated or trimmed.

The existing CSV parser reads complete logical records, including a UTF-8 BOM,
CRLF and quoted multiline fields. The native checker defines a pointer's number
as the **physical ending line of the complete logical record**. It is not an
instruction to take one physical line or the Nth object in a JSON list. A pointer
inside a multiline record is refused unless it names that record's ending line.

The source manifest records the exact byte length and SHA-256 of all four CSVs
and the saved report, plus the presence/hash of `expected.json` and the current
checker source hash/rules. Parsed cell values do not preserve CSV quoting syntax;
the hashes identify the admitted original bytes. No absolute input directory is
included in the JSON. The same input bytes, report filename and checker produce
the same output bytes.

The report validator is the existing `review._current` implementation. It checks
the native summary's dates, data mode, counts, findings, queue and baseline
results against `engine.load`/`engine.check` using their current default rules.
It does not accept a saved report whose checked fields disagree with the supplied
export. If it refuses a stale report, inspect the change and generate a new
report with `uwatch run`.

## File and failure behavior

The output's parent directory must already exist. The output must be a new file;
existing files, symbolic links and protected source/report names are refused.
Input leaves must be regular files, and the data directory must be a real
directory. Parent paths are resolved once to their canonical directories.

The command reads the sources and report without editing them. Checker
validation uses private temporary copies. It checks directory identity, file
identity and exact input bytes again after staging the output and immediately
before publishing it. Observed edits, replacements, missing inputs and changes
to the optional synthetic-data marker cause refusal. Publication uses one
complete same-directory temporary file and an exclusive hard link, so a file
created by another writer at the destination is preserved. No partial JSON is
published on a failed write. On a filesystem without hard-link support,
publication fails without replacing a destination.

These checks detect changes observed during the operation; they do not lock the
export or promise a cross-file transaction with a concurrently writing exporter.
Finish exporting the source files before inspection. A failure to remove an
owned temporary name does not undo an already complete publication or hide its
original error.

Errors exit with status 2 and a reason on stderr. A successful command reports
the selected identity, record count and output path. Inspection does not change
billing rules, annotations, payment eligibility or any source/report file.
