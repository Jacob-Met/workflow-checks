# Independent Freight batch receiving contract

Reviewer: runtime_integration, ultra-20b27c2e-20261008.
Repository: Jacob-Met/workflow-checks.
Primary baseline: 5b12dcd4c3a2c09d6602b2313e2bb556ac5997f7.
Tree: e16dd0815e252c7e1715545999918f303bc823af.
Ownership: existing issue 37, "Download selected Freight review packets as one batch handoff."
This contract and the independent probes are frozen before reading the author's candidate or new batch tests.

## Public behavior and oracle

The recipient selects displayed Freight loads and receives one downloadable ZIP. The existing native App.review_bundle and GET /api/review-bundle remain the oracle for each selected load. Each ordinal loads/0001/ directory contains the original five members, byte for byte, plus review.zip equal to the entire original native ZIP. The top-level readable index links each ordinal cover. Explicit API request order is retained; browser selection must identify exactly the checked displayed identities, and the archive follows its recorded request order.

POST /api/review-batch accepts exactly an object with loads, a list of 1 through 100 objects containing load_id, evidence_version and review_version. Versions are the 64 lowercase hexadecimal values returned by the current summary. Duplicate selected IDs, missing or ambiguous selected records, stale evidence or stale saved review refuse the entire archive. A refusal is an error response, with no ZIP attachment or partial ZIP. A missing summary does not initialize or rerun the pipeline.

The actual app lock must enclose the complete native snapshot. A legitimate concurrent writer using that same app must not enter between two selected bundles. This guarantee concerns the documented single server and its own writers, not arbitrary external filesystem changes or cross-process transactions.

Batch and per-load downloads leave every input and output file byte unchanged. Current, cleared, stale, unbound and absent saved reviews retain their native meaning; no old approval is upgraded. Other loads and original global source/audit/decision files are not included as additional archive members. Ordinal paths do not use load labels as paths. Malicious-looking, colliding and Unicode labels must be inert text while preserving exact identity and constituent bytes. Malformed optional native review data causes a complete refusal while ordinary healthy per-load behavior remains available.

## Independent native probes

Use actual baseline generator/pipeline once to create a small synthetic fixture, then freeze and copy that fixture into each owned case. Use genuine App, make_handler, ThreadingHTTPServer and loopback HTTP. Build saved state using native decide for ordinary records and an explicitly identified legacy fixture for the unbound record. Cases derive from primary handoff/web semantics, not the author's expected test outputs.

Controls establish exact native per-load ZIP members, checksums, review states, stale/missing refusals and source custody. New cases cover unordered selected subsets and all review states; exact order; collision and text-injection labels; same-looking but distinct IDs; stale packet/report and saved-history identities; missing and ambiguous packets; duplicate or malformed selections; bounds; missing summary; unsafe packet targets; malformed optional review history; unselected-change isolation; and actual same-app lock contention. Read-only request windows receive complete before/after file hashes. The concurrency case labels its one deliberate native review write separately.

API errors are judged by documented kind where specified: malformed request 400, stale identity 409, missing/ambiguous current packet 404; no error response may be a ZIP or attachment. The baseline's missing route is a capability failure, not a passing negative case.

## Independent browser probes

Use the installed Chrome/Puppeteer with a fresh owned profile and actual loopback server. Deny every non-loopback network request. Exercise ordinary per-load download, visible Downloads selection, an actual saved batch file, and exact request identity. Record the actual returned response and download bytes.

Hold a real server response at the browser network boundary to test selection changes, cancellation, unsaved-note edits and pending/committed review changes. A retired response must not download or contaminate a later fresh request. A selected identity refresh clears invalid selection; an unselected identity refresh preserves valid selection. Malformed response type or unsafe attachment filename must not create a download. Displayed malicious-looking labels remain text. No production source or response payload is rewritten to make tests pass; network timing/envelope challenges are identified explicitly.

Browser selector adaptation, if needed, is restricted to locating the delivered public controls and recorded separately. It must not change the frozen behavioral assertions or response oracle.

## Boundaries and custody

All operational data is synthetic under /tmp/ultra-20b27c2e-runtime-freight-review on approved Mac 0e3d582f-e25b-44b2-8418-9639fc4e4e33. No real account, installed app data, provider, service deployment, global configuration, dependency installation or external write is used. Source/test/evidence in the author's namespace remains read-only. Root owns GitHub integration. Failures and environment/setup mistakes are retained before repairs; accepted pins and raw output are immutable.
