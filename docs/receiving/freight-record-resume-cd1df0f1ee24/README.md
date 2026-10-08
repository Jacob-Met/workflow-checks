# Freight saved-record resume: current receiving index

Issue: [workflow-checks #60](https://github.com/Jacob-Met/workflow-checks/issues/60). Draft: [PR67](https://github.com/Jacob-Met/workflow-checks/pull/67).

Open saved record validates the existing v1 envelope, previews all sixteen inputs and replaces the current scenario only after explicit confirmation. The model, application, saved-record validator and independent seventeen-group browser receiver remain unchanged by this qualification update.

## Current boundary: one hosted browser attempt

This commit configures **one authorized hosted qualification attempt** using the exact reviewed [supervisor](../../../demos/freight-whatif/tools/receive_browser_hosted.py), [unchanged receiver](../../../demos/freight-whatif/tests/scenario-record-browser.mjs) and [PR67-specific workflow](../../../.github/workflows/freight-pr67-browser-qualification.yml). It records source and lifecycle acceptance; **no actual hosted browser result is recorded here**. Keep the PR in draft until the observed hosted checkout, raw result, complete evidence bundle and visual output have been independently received.

The [approved proposal](hosted/preparation/proposal-v2.json), [lead source review](hosted/lead-source-review.json), [independent source review](hosted/source-review/review-v5.json) and [qualification contribution manifest](hosted/contribution-manifest.json) bind the precise version boundary. Earlier proposal and supervisor revisions remain historical evidence under the hosted directory. The source review's original mock-pending wording is preserved; the completed mock receipt below is its separate successor evidence.

The supervisor registers a fresh browser session before execution and verifies PID start identity, UID, session, process group and exact profile before signaling it. Cleanup remains bounded when Node exits or diagnostics fail. No process-name cleanup, existing profile deletion, receiver/oracle change or automatic retry is authorized. The workflow uses the unchanged original failed-attempt packet for its pinned baseline, candidate and fixture inputs; it does not relabel that old failed run as hosted success.

## Completed independent lifecycle receiving

The [original seven-control receipt](hosted/lifecycle/receipt.json), [process result](hosted/lifecycle/process.json), [raw stdout](hosted/lifecycle/stdout.txt) and [raw stderr](hosted/lifecycle/stderr.txt) record Python 3.14.4, seven passed, zero failed, explicit exit 0 and empty stderr. Total child time was 11.75 seconds, with a longest control of 5.85 seconds.

The controls received an owned separate group after mock Node exit; preserved an unrelated different-profile sentinel; refused wrong start identity and profile mismatches without signaling; handled an already-exited group and a real kernel ESRCH race; escalated a TERM-ignoring own mock to KILL; and completed cleanup despite diagnostic OSError. Every signal was guarded against the receiver's own freshly created process registry. No original mock identity remained live after the audit.

The unchanged [24-member packet](hosted/lifecycle/packet.tar.gz), [member manifest](hosted/lifecycle/artifact-manifest.json), [seal](hosted/lifecycle/seal.json) and [guide](hosted/lifecycle/README.md) retain the frozen contracts, exact source, independent harness/mocks, raw results and process identities. These are lifecycle infrastructure checks. They did not run Chrome, Puppeteer, npm, the Freight app or a network request, and they do not establish browser acceptance.

## Accepted delivery and historical failure

The [delivery record at head 8e01](receiving-index-delivery-8e01.md) is preserved byte-for-byte in the same directory, so its original relative evidence links remain valid. It records the recovered original native 29,559-byte [release ZIP](../../../demos/freight-whatif/dist/freight-whatif.zip), exact package receipt, nine authored importer groups, 131 independent admission cases, six installer controls and complete source-preservation evidence. The ZIP and all of that evidence are unchanged by this hosted qualification update.

The original native browser attempt remains a failed execution: supervisor timeout, Node exit −9, no completed group receipt, captures or downloads found, and an unclassified hang. Stderr includes DevTools listening. The complete [failed-attempt packet](browser-native/packet.tar.gz), [receipt](browser-native/receipt.json) and [guide](browser-native/README.md) retain that boundary and the separately authorized cleanup.

The earlier unexecuted hosted **ZIP producer** fallback is unrelated to this browser qualification. The delivered ZIP is the accepted original native artifact. Older hosted source checks also retain their recorded checkout boundary; they are not substituted for the new browser result.
