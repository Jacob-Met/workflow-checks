# Ambiguous PT CSV column names

The PT loaders apply the existing header normalization: trim and lowercase each
name, then replace a run of whitespace or hyphens with an underscore. A file
must have distinct nonempty names after that normalization. For example,
`Visit Date`, `visit-date` and `visit_date` name the same column.

A repeated name is refused before any record is yielded. The error identifies
the filename, the physical line where the header ends, the normalized name,
and the two one-based column positions. Fix the original export so each named
column has one intended meaning, then run the report again. Identically named
columns are ambiguous even when their cells happen to agree, and unused named
columns follow the same rule. A header-only file with a duplicate also refuses.

This applies to `schedule.csv`, `authorizations.csv`, `payers.csv` and the
optional `patients.csv`. The existing report command loads all four inputs
before creating or writing report output. A refused header therefore preserves
an existing report and audit file and does not create an absent output directory:

~~~sh
cd pt_auth
python -m ptauth run --data sample_data --out out --as-of 2026-09-28
~~~

An error exits 2 through the existing CLI input-error path. The original input
files are never rewritten. This is header admission, not a transaction system
or a guarantee against files being changed by another process during a report.

Blank trailing column names remain accepted, including repeated blank names.
Distinct extra columns, UTF-8 BOM and existing cp1252 fallback, quoted/multiline
fields, blank rows, optional fields, row source positions, status aliases and
clinic date interpretation keep their existing behavior. No columns are renamed,
no values are selected from conflicting columns, and no payer or allocation rule
changes.

Focused tests use temporary synthetic CSV exports and the actual native CLI:

~~~sh
cd pt_auth
python -B -m unittest discover -s tests -p test_csv_headers.py -v
~~~

They exercise every loader, normalized and identical collisions, header-only
files, physical header lines, accepted encoding/row controls, and refusal before
report creation or replacement. Existing project qualification and independent
receiving are retained separately in the contribution's evidence directory.
