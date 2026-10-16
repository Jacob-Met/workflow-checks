# CSV values must have a declared column

The Freight CSV readers reject a row containing a value beyond its header.
Previously those values were silently discarded while the remaining fields were
used to rebuild review reports. The check applies to `loads.csv`,
`carrier_invoices.csv`, geofence telematics CSVs and tracking-stop CSVs.

For example, a five-column row with a sixth value reports:

```text
loads.csv: CSV row ending at line 2 has nonempty values beyond the header in columns 6
```

Column positions start at one. The line number is the physical line where that
CSV record ends, so a quoted field spanning several lines is located accurately.
The error identifies every nonempty surplus column without copying its content
into the diagnostic. Correct the export's header or quoting and run the ordinary
command again:

```sh
python -m freightpkt run --data sample_data --out out
```

The command exits unsuccessfully before appending audit decisions or replacing
any existing report. Input files also remain unchanged. For a new destination,
the existing pipeline may create its output and `packets` directories before
reading input, but the refused invocation writes no report or audit file.

An extra delimiter with a literal empty cell remains accepted. A space, tab or
other value in a surplus cell is refused. Extra **named** columns remain accepted
under the existing schema and alias rules, as do BOM-prefixed CSVs and correctly
quoted comma or multiline fields. Existing required/duplicate-header checks keep
their precedence. JSON telematics, missing-cell behavior, source-row identities,
invoice grouping, money parsing and settlement rules are unchanged. This is not
a general CSV schema validator or a transaction over later output failures.

Run the maintained regression from `freight_packets`:

```sh
python -m unittest discover -s tests -p test_csv_row_admission.py -v
python -O -m unittest discover -s tests -p test_csv_row_admission.py -v
```

The tests exercise all four native readers and actual CLI processes. They cover
later malformed rows, multiple surplus columns, empty-cell compatibility,
multiline location reporting and byte-for-byte preservation of earlier reports
and the append-only audit.
