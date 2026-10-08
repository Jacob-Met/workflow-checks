# Worksheet and printable-report coexistence

This receiving merge composes the original four worksheet registration/dispatch lines into the exact CLI delivered by printable report PR36. The existing branch head is `9483f0a7226fecbd25fc428a217c34da0f2167d0`; the received main is `5a70e458ed455d47ef672ed9b5a614ec59812f0c`, tree `86f234b92173176c7f3c8ae4e1e4d5d3c41d36fd`. The merge commit retains the old branch as its first parent and current main as its second parent, permitting a normal fast-forward branch update.

Only `utility_watch/uwatch/cli.py` changes relative to the original worksheet product candidate. Removing the four original lines restores the complete current owner CLI, including its CRLF bytes. Its new `review_report.py`, tests, guide and all current owner source remain exact. The other four worksheet product/test/doc files and all original evidence remain unchanged. The original packet/manifest describe immutable head `9483f0a7`; this directory's `current-manifest.json` binds the combined publication.

## Exact source

- Current owner CLI: Git `27bfe687d071ff045bd5642f6408413c8cc6a805`, SHA-256 `d7e223edf55790642b011f8159d113da0433416c6344c6be255037d558dd9c45`.
- Composed CLI: Git `034935eeb633ecf68bfda4c5dd1181c7931880e6`, SHA-256 `80cb716a37aa810c63ad69916ab293fcbfd83a44b51570d013339c0b217c7cb3`.
- Current owner report module remains Git `be869a940436172253c0a6d5020ba24860f1a7eb`.

`composition.json` records all 26 locally used source files: the five worksheet product/test/doc files and 21 exact current-parent inputs. `cli-integration.patch` contains only the four added lines.

## Actual saved-file receiving

The retained independent receiver's `07-reconciled-current.csv` has two current findings and one historical finding. Three actual native CLI children performed:

1. `worksheet list` on that original saved file.
2. `worksheet annotate` on the exact current row ID returned by list, with an explicit reviewer, status and Unicode/CRLF note containing literal HTML-looking text, to a new file.
3. The unchanged owner's `review-report` on the annotated file, producing a new HTML report.

All three returned zero. Ten receiving assertions passed: exact list identity/context, only the three intended cells changed, all protected/history/manifest/other-reviewer cells remained exact, the report retained all row identities, and the selected note decoded to the complete original literal text. HTML-looking input was escaped and introduced no element in the selected article. The report names the annotated input's exact digest. The actual retained worksheet and all 26 source files remain byte-exact.

`native/receipt.json` contains commands, stdout/stderr, source pins and checks. The actual input copy, annotated CSV and generated HTML are retained beside it. Parsing used the standard-library HTML parser; it is not browser/layout or print execution.

The original 43-invocation suite was not repeated. This narrow receiver resolves the new CLI coexistence risk; earlier original/current-engine tests and hosted checks stay pinned to their previous source.

## Replay

From the repository root, choose a new output directory:

```sh
python -B docs/receiving/utility-worksheet-61749b/review-report-coexistence/receive_coexistence.py \
  --package utility_watch \
  --worksheet docs/receiving/utility-worksheet-61749b/independent/native/07-reconciled-current.csv \
  --out NEW_DIRECTORY
```

All data is retained synthetic local data. No browser, new dependency, account, payment, provider, installed source or service operation was performed.
