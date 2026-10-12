# Current fines and settlement downloads

Every successful Freight Packets run writes `fines.csv` and `settlement.csv`
from that run's calculated records. When the optional `fines_schedule.csv`
input is absent, the two downloads contain their normal column headers and
zero data rows, matching the empty fines and settlement sections in the
current summary.

Previously, a run without that schedule skipped writing both files. Reusing
an output directory could leave the previous run's fines and settlement
amounts downloadable even though the screen showed no current records. A
first run without the schedule instead left the two listed downloads absent.

After removing or restoring the schedule, rerun the existing command or use
the review app's existing rerun action:

```sh
python3 -m freightpkt run --data sample_data --out out
```

The command is run from `freight_packets/`. Removing the schedule disables
this optional calculation; it does not establish that an invoice has been
approved or paid. Restoring it and rerunning reconstructs the fines and
settlement rows from the supplied inputs and existing rules.

The refresh changes only publication of these two generated CSVs. Their
columns, quoting, amounts, evidence pointers and ordering are unchanged when
the schedule is supplied. The existing append-only audit history and saved
reviewer decisions remain retained. A saved review can still become stale
when its supporting evidence changes, under the existing review rules.

This is a successful-run consistency repair. The pipeline still writes its
outputs in sequence; it does not offer transactional publication across all
files or recovery from a failed run.

Run the maintained regression from the repository root with:

```sh
python3 -m pytest -q freight_packets/tests/test_optional_report_refresh.py
```
