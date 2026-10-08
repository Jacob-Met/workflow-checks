# Compare two saved freight review copies

Billing and settlement reviewers can compare two retained per-load ZIP handoffs without reopening a report directory or taking a new review action.

From the repository's Freight directory:

~~~sh
cd freight_packets
python -m freightpkt.review_compare COPY_A.zip COPY_B.zip --out comparison.html
~~~

Open the new HTML file in a browser. It is self-contained and includes print CSS; use the browser's Print command for a paper or PDF copy. The command uses Python 3.10+ and the standard library. It does not need the local review server, source input files or any account.

## What the report shows

Copy A and Copy B follow the supplied argument order. The comparison does not infer which copy is earlier or later, or whether either copy matches the current review app.

The record-count table links to all six native sections: stops, flags, fines, settlements, exceptions and packets. Each section shows complete records only in A, only in B, and unchanged records. Every group preserves the number of equal occurrences. Three identical records in A and one in B therefore produce two occurrences only in A and one unchanged occurrence.

Record equality uses canonical native JSON values. Object field order is immaterial; unknown record fields and array values remain part of equality. Numeric zero, false and null remain distinct. Section arrays are compared as collections with multiplicity, not as a sequence of presumed row identities. A changed departure appears as the complete original record only in A and the complete changed record only in B, with both original file:row references. Records are not paired by stop number, invoice or position. The source ZIPs retain the exact original array order and bytes.

Both complete saved review objects are displayed, including note, history, recorded state and any additional fields. A recorded approval or current state is attributed only to that supplied snapshot. An old approval does not approve changed evidence in the other copy. The report creates no new approval, invoice, filing, payment or audit event.

The identity section includes both source labels, ZIP sizes and SHA-256 hashes, packet hashes, canonical evidence/review versions, and all four payload member hashes. Cover or ZIP container bytes may change while the evidence and saved-review identities stay equal. Reordering a section array also changes its native evidence identity even when the multiset of records stays equal; inspect the original ZIP JSON for that original order.

Record strings are escaped as text, including Unicode, markup and legacy surrogate escapes in saved review notes. Neither supplied HTML member is embedded or executed. No supplied URL becomes an active link, and the report has no script, external asset or network dependency. Packet and cover bytes are represented by their identities; retain the original ZIPs to inspect those exact source files.

## Accepted input format

Use the existing per-load **Download saved review** ZIP produced by the Freight review app. Batch archives are not accepted as per-load input. Use the existing per-load handoff; this command does not unpack or adapt a different batch format.

Each input must contain exactly five uniquely named members:

- index.html
- packet.html
- evidence.json
- review.json
- manifest.json

The reader checks the native freight-review-bundle.v1 manifest, all four declared payload sizes and hashes, freight-review.v1 evidence, freight-review-snapshot.v1 saved review, their shared exact load ID and versions, the original packet digest, and the unchanged native canonical evidence/review identities. Both copies must have the same nonempty load ID.

The six evidence sections must be arrays of objects for that selected load. Nested record fields are retained. A saved review is an object or null; any history is an array of review objects. Unexpected top-level fields or schemas, duplicate JSON object keys, nonfinite numbers, missing/extra/duplicate ZIP members, invalid bindings and differing load IDs are refused. These checks follow the current native version; they do not silently accept an unknown format.

Manifest checks establish internal consistency, not authenticated authorship, freshness or a new decision. The producer uses hashes rather than a signature. The reader processes complete inputs in memory; it does not claim an archive-size, resource-exhaustion or concurrent-source-mutation guarantee. Each path is read once, and the report identifies the exact copied ZIP bytes used.

## Output and failures

Both inputs are read and validated, then the complete report is rendered, before the output path is opened exclusively. The destination must not already exist. This also prevents a supplied input path from being replaced accidentally. Parent directories must already exist; the command creates no directories and does not alter the source copies or app state.

Invalid input or an I/O error exits with status 2 and a concise error. Existing targets are never replaced. A storage failure after exclusive creation may leave a partial **new** file; a subsequent invocation refuses that retained path. Inspect it and choose a new destination. This is not an atomic-publication or automatic-cleanup guarantee.

The ordinary freightpkt generate, run and serve commands are unchanged. Packet filenames are copied as native record values; the comparison never reconstructs a packet path from a load ID. Existing review binding, generation, calculation, decision and audit semantics remain with their current interfaces.

## Focused checks

From freight_packets:

~~~sh
python -m unittest discover -s tests -p test_review_compare.py
~~~

The focused tests use the unchanged native bundle producer and authored synthetic records. They cover same-copy and changed-departure behavior, duplicate counts and JSON types, literal markup and saved history, review-only and cover-only differences, native content validation, supplied-order and load refusal, complete exclusive output, preserved inputs/targets and a retained partial output after an authored storage failure.

The existing repository CI runs Freight tests with Python 3.10 and 3.12. This feature adds no dependency or CI configuration. Source/HTML assertions do not establish a real browser rendering or printing result; any local qualification limitations are recorded with the receiving evidence.
