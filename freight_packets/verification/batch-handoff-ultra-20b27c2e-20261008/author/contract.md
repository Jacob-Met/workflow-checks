# Freight selected batch handoff — frozen intended contract

Repository: Jacob-Met/workflow-checks
Baseline: 5b12dcd4c3a2c09d6602b2313e2bb556ac5997f7
Tree: e16dd0815e252c7e1715545999918f303bc823af

Billing staff can select one to 100 current displayed draft packet reviews in Downloads and download one ZIP. A readable batch index links each load's existing review cover. Each load has an ordinal directory, its five byte-exact per-load members, and the byte-exact existing per-load ZIP for a separate handoff. Labels never become archive paths.

POST /api/review-batch accepts exactly {"loads": [{"load_id": "...", "evidence_version": "<64 lowercase hex>", "review_version": "<64 lowercase hex>"}]}. Preserve explicit request order. Empty, duplicate, malformed or excessive selections are rejected. App.review_batch validates the whole selection before collecting existing App.review_bundle results under one outer existing RLock. Missing/ambiguous packets or one mismatched evidence/review identity refuse the whole archive. Downloading never initializes/reruns the pipeline or writes decisions, history, source inputs, reports or output archives.

A selection records displayed identities. The browser exposes no new decision action. Unsaved current note edits and pending review updates prevent a download. Selection changes, selected-summary changes, note edits, pipeline/review actions, cancellation or replaced request state prevent a late response from becoming a download. A refreshed selected identity clears the batch selection with an explicit message; unselected changes preserve it. Failures retain working reviews and make no automatic request retry.

Current, unreviewed, cleared, stale and unbound review states remain distinct through the unchanged per-load cover. An old approval must not become approval of changed evidence. Archive contents are local draft snapshots, with no external request, transmission, invoice, payment or operational-state change.

Source boundary: new batch_handoff.py and batch_handoff_ui.js; web.py import, App.review_batch, two exact source/download routes; ui.html script load, controller initialization and render hook; README section; new native tests/browser receiving and unique verification evidence. All existing handoff.py, review/decision/rules/pipeline/CLI/workflow source and tests are preserved.
