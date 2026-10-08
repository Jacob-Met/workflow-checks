# Selected Freight review batches — qualified contribution

This packet adds a local Downloads workflow for selecting 1–100 displayed saved reviews and retaining them in one ZIP. The group index links each existing review cover. Every selected load retains the five original member files and the exact original per-load ZIP under an ordinal directory such as `loads/0001/`. Displayed load labels never become archive directory names.

Repository: Jacob-Met/workflow-checks. Original receiving base: `5b12dcd4c3a2c09d6602b2313e2bb556ac5997f7`; complete base tree: `e16dd0815e252c7e1715545999918f303bc823af`. Ownership is recorded in [issue 37](https://github.com/Jacob-Met/workflow-checks/issues/37). The complete tree had no AGENTS.md or WORKSTREAMS. The existing Freight README and HARDENING instructions were read.

## Receiving contract

`POST /api/review-batch` accepts exactly one `loads` array of exact load/evidence/review identities. It rejects empty, duplicate, malformed, excessive and extra-field requests. Selection validation precedes collection. One outer instance of the existing reentrant review lock spans unchanged per-load bundle calls; a missing, ambiguous or changed selected identity refuses the whole archive. It neither omits the failing row nor silently refreshes a review.

The browser takes selection identities from the displayed summary, keeps displayed order and exposes no new decision action. Unsaved notes and pending review/pipeline work block download. Cancellation, selection changes, note edits and review/pipeline actions retire an active request. Refreshing a changed selected identity clears the whole selection with a message; an unselected change retains it. Failures make no automatic retry.

Current, not-reviewed, stale, unbound and cleared states retain the existing cover meanings. No new aggregate payment amount or approval is inferred. Downloads write no inputs, reviews, histories, reports or archives to the application output directory. All qualification used isolated synthetic fixtures and loopback HTTP; no operational load, service or account was used.

## Exact source boundary

Seven final paths are bound in final-source-pins.json: three existing files (web.py, ui.html and the Freight README) plus batch_handoff.py, batch_handoff_ui.js, test_review_batch.py and the optional native browser receiver. Existing handoff.py, pipeline/rules/review writers, CLI, workflows and inherited tests are unchanged.

source-preservation.json verifies all 27 staged original blobs, all 24 untouched original files, and exact inverse byte restoration of the three edited originals. All 12 existing App methods are AST-identical. web.py and ui.html retain their existing CRLF encoding. The inverse operations are listed explicitly in inverse-spans.json. This is original-base source evidence, not a claim about a later merged tree.

The adjacent [issue 39](https://github.com/Jacob-Met/workflow-checks/issues/39) owns portable packet filename allocation in pipeline.py and packet_names.py. This contribution does not change that behavior: the unchanged per-load path reads the summary's existing file property, and the batch stores the resulting payload unchanged under ordinal directories. Publication must preserve that owner's later source if it has landed.

## Qualification

| Receiver | Original / first candidate | Qualified candidate |
| --- | --- | --- |
| Same five-observation native App/HTTP probe | Two existing controls pass; three missing-batch observations fail with 404 | Five observations pass, including a three-load archive and no input/output changes |
| Author stdlib suite | Original ten methods produce 19 failed assertions/subtests; raw log retained | Corrected ten methods pass; twelve methods pass after adding contention and path-collision controls |
| Author real Chrome receiver | First three attempts stop in note-restoration harness setup, retaining actual earlier successes | Corrected unchanged nine-group receiver passes on both first production UI and final UI |
| Independent native App/HTTP receiver | Three existing controls pass; nineteen missing-batch methods fail | 22/22 methods; 232 actual HTTP calls |
| Independent real Chrome receiver | One ordinary per-load control passes; ten missing-panel groups fail | First UI: 10/11; final UI-only successor: 11/11 |

The independent packet documents its own contract, freeze, source custody, exact probes and outcomes. Its 232 HTTP calls comprise 163 GET and 69 POST: 169 successes, seven stale conflicts, ten missing/ambiguous refusals and 46 malformed-selection refusals. The intentional concurrent reviewer is the only writer in those checks; it writes decisions.json and audit.jsonl after the batch lock releases. There was no duplicate API suite for the UI-only correction.

Author browser qualification uses installed Chrome 154.0.8037.98, Puppeteer and Node 26.3.0, a fresh owned profile, actual local Python 3.13.7 HTTP and actual native downloads. The final nine groups pass with zero page errors and zero non-loopback requests. The downloaded two-load ZIP is 22,761 bytes, SHA256 `300479cee3562cbc77f79259f09d010212817d354a7cd966f12cd4f7ac2bed1c`; its 14 members retain both original ZIPs and all ten original member files exactly. The separate saved-review download also completed.

The final screenshots were visually inspected at desktop and 390px width. The group panel stays within the viewport and its three displayed action buttons are 44px high. The inherited horizontally overflowing tab strip was not changed. Browser response observation records attachment responses with zero captured body bytes; attachment custody is established by the actual downloaded files and ZIP readback, not by those empty observer buffers.

## Preserved correction history

The first probe called the native generator with an unsupported loads keyword and failed before product execution. probe_batch.py and before-v1-failure.json are retained; probe_batch_v2.py uses the native n_loads signature.

The first author test helper inadvertently substituted a default selection for explicit None; a separate ambiguous-row fixture duplicated a potentially unselected row. Both setup corrections preceded the qualified ten-method run. Executed original and corrected test bytes and all logs are retained.

The first browser harness used triple-click to clear a textarea, which removed only its final character in this headless browser. Its second attempt used an unsupported Puppeteer Meta+A chord; the third used individual modifier calls that did not select the field. These failures remain in runs.zip. The qualified receiver uses native textarea selection followed by a real Backspace input event. No application change was made to satisfy those setup errors.

Independent review found a real visible-state defect in the first production UI, SHA256 e1d919b7b3c713781707f7f927551072bc74bcf92bf4444e11cc120775f43377: while a real review response was held, the group download button looked enabled. Its click guard refused submission, so this was not an admitted stale export. The final script, SHA256 bd300f25abf279ca16f11bddc4bf4c277f4e99b9146b5321904ecc82afaaca18, preserves capture-phase cancellation and adds a bubbling control refresh after the existing target handler sets reviewBusy. Only that event-order span changed. The original script, 10/11 result and direct zero-request witness are retained, and the unchanged independent browser probe passes 11/11 on the successor.

A first source-proof script addressed the payload wrapper as an array, so it stopped before verification. verify-source-v1.cjs is retained; the executed successor selects the documented files array and passes all proof operations.

## Full-suite receiving gate and limits

The existing .github/workflows/tests.yml runs on push and pull_request, on Ubuntu with Python 3.10 and 3.12. The unchanged Freight command is:

```sh
# working-directory: freight_packets
python -m pytest -q
```

The local full-suite attempt hit exhausted container storage, exited 120 and left a 4,096-byte partial log. That run is a capacity hold, not a product regression or a passing suite. A separately inspected native Linux runtime could not stage the fixture because writes returned quota error -122; empty/partial setup files did not execute a suite. The Mac default Python had no pytest. No dependencies were installed and no further runtime hunt was performed. The full unchanged hosted matrix is therefore pending at this handoff and must be checked by the publication owner.

This packet does not qualify cross-process writers, hostile filesystem changes, unbounded archive sizes or live operational use. It retains the existing instance-lock and per-load read contract. It contains no deployment claim.

## Evidence custody and replay

Direct JSON receipts and screenshots are accompanied by runs.zip and runs-manifest.json. The archive is a lossless copy of the original before/after fixtures, downloaded bytes, response bodies, failed harnesses, first-source script, source transport and local logs. No profile is included and no original was deleted. The archive builder verifies every member byte after writing; the external manifest pins each retained path.

The final test and browser receiver live in the native test directory. The browser receiver is optional and installs nothing: it requires existing PYTHON, PUPPETEER_MODULE and BROWSER_BIN paths, and accepts an explicit FREIGHT_BATCH_SOURCE and FREIGHT_BATCH_EVIDENCE. It creates only its own synthetic fixture and profile and aborts non-loopback requests.

The publication manifest maps each repository destination to the exact native file with byte count, SHA256 and Git blob identity. Root owns fresh-base composition, GitHub publication, hosted gates, merge and any separate release receiving. The original qualified evidence is immutable; later composition evidence should be appended.
