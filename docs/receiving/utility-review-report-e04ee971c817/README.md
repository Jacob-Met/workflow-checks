# Utility Watch: read and print a saved review worksheet

This packet adds an explicit **review-report** consumer to the existing Utility Watch worksheet. A reviewer can open or print saved findings, statuses, reviewer names, notes and recorded source-row identities. Current findings and retained history are separate. The view uses the native worksheet validator and captures the exact worksheet bytes read; it does not rerun the checker or reconcile annotations.

## Source and ownership

Repository: **Jacob-Met/workflow-checks**. Exact main before-image: **9e931fa9f42033bf2368f7149684fb5631345715**, complete tree **0b0c903801f432968e9cdfb1f1fa134cecc37217**. The same main/tree was re-read after qualification. The complete 403-entry tree contains no AGENTS.md.

The scope was announced before implementation in [HAMON #142, comment 6060070875](https://github.com/Jacob-Met/hamon/issues/142#issuecomment-6060070875). It consumes the worksheet accepted in [workflow-checks #22](https://github.com/Jacob-Met/workflow-checks/pull/22), merge **65461ca8f6bd636cd85c0086210ccb1e6837fbee**. The older poc-automation repository was not changed.

The four intended source/test/documentation paths are:

- utility_watch/uwatch/review_report.py
- utility_watch/uwatch/cli.py
- utility_watch/tests/test_review_report.py
- utility_watch/docs/review-report.md

The existing engine, checker report, reconciliation, generator and package entry modules are byte-exact. Existing generate/run/review CLI behavior and CRLF are preserved; removing the two enumerated additions and the updated command-list docstring reconstructs the entire original CLI. Account-plus-bill membership (#25), duplicate-header validation (#24), demos and CI remain their owners' work.

These directories contain selected source, not a replacement repository tree. Publication must overlay only the four intended paths and a unique evidence packet on a fresh complete upstream tree, with current source/dependency checks.

## Decisive consumer result

A fresh native Python 3.14 fixture executed six actual CLI children against synthetic data: generate, check, first worksheet, changed-source check, worksheet reconciliation, and the previously unavailable view command. It retained 14 current findings and one changed historical row. That row kept the multiline note and Unicode reviewer; the changed current finding reopened with blank annotations. The baseline view command exited 2 and produced no output.

The candidate actual CLI renders this same retained worksheet into **21,880 bytes** of self-contained HTML. Native Python 3.14 and local Python 3.12 output are byte-identical:

- Worksheet SHA256: d9305edacc7e94a7ac076809a9e0c7cab1ce0ba557616be9afd8a86b8b783ddd
- HTML SHA256: 6ba4c1eaeb71c6eece6a52229bd53e16ebc1b2dd87926c6025cb997feef0a653

The native first candidate tool receipt is retained exactly in evidence/candidate-native-cli-tool.json; evidence/candidate-html-portability.json records the separate actual Python 3.12 command. Neither operation changed its input.

Example use, from utility_watch in a checkout containing the change:

    python -m uwatch review-report --worksheet review-2.csv --out saved-review.html

The destination must be new and its parent must already exist. Validation and rendering finish before publication; the writer flushes and fsyncs its own temporary file, then uses an exclusive hard link. An existing file, directory or symlink is preserved. The file system must support this operation. The native worksheet's integrity checks are not reviewer authentication or current payment authorization.

## Qualification, including interrupted work

| Receiving boundary | Observed result |
| --- | --- |
| Fresh native baseline producer/reconciliation | Six actual CLI children; missing view exits 2; 14 current + 1 retained historical row |
| New focused methods, Python 3.14 normal | 7 passed; no failures, errors or skips |
| Same initial Python 3.14 optimized invocation | 6 methods passed; one fixture directory creation raised real ENOSPC before product invocation |
| Bounded replay of only that interrupted method, Python 3.12 optimized | 1 passed; all four candidate file pins unchanged |
| Actual retained worksheet, Python 3.12 CLI | Exit 0; exact native 3.14 HTML bytes; input preserved |
| Exact source and ordinary Git patch replay | 33 conditions passed; four paths only; all ten resulting selected files byte-exact; no Git stderr |
| Actual installed Chromium browser and print | 105 conditions passed; zero failures; 14 current + 1 historical; PDF text retains history, reviewer and literal note |

The optimized result is not described as a clean seven-method native optimized run. evidence/candidate-optimized.json retains the actual ENOSPC traceback. A subsequent attempted replay-script write also hit ENOSPC and left an empty file. Executing that empty draft returned zero without running any test; evidence/interrupted-replay-write.json explicitly disclaims it as a pass. That exact empty file remains. The first restored local replay lacked its empty temporary parent after mirroring and also stopped in setup; its failed receipt remains. The v2 bounded runner creates its own parent and records the one real passing replay. No failed receipt was rewritten.

The focused methods cover native current/changed/absent semantics, statuses, exact note/evidence text, empty valid worksheets, invalid worksheet refusal, existing destinations and controlled fsync/link failures. An actual package CLI child traps checker/reconciliation/generator and network/subprocess entry. The complete inherited suite was not rerun.

## Browser and printed result

The installed Node **22.22.1** and Chromium **153.0.8010.47 snap** ran as the ordinary jacob user on ThinkPad **d55b2499-5e82-4805-819a-d0d7ddea1efe**. The loopback server served only the captured HTML, with an empty favicon response. A fresh profile beneath /home/jacob/snap/chromium/common was removed after the owned browser exited.

The first launch refused at a 64 MiB headroom gate when shared disk availability fell from 127 MiB to zero between preflight and launch. That refusal occurred before profile/browser creation and is retained in evidence/browser-capacity-refusal.json. The later successful run's exact receipt is evidence/browser-results.json.

The successful run compares every row's state, reviewer/note, evidence pointers, identities and detail against the native validator's records. It checks 1280-pixel desktop and 390-pixel mobile layouts, inert HTML-like note text, in-document links, no page runtime/resource failures and print styles. The actual PDF's extracted text contains the historical note and reviewer. Observed page requests were loopback; this is not a claim about every Chromium background operation.

The desktop, history and mobile captures were visually inspected after readback. Text was readable and the prior note appeared only under the historical finding. Their raw bytes and the PDF were reassembled from native reads and checked against the original artifact SHA256 values before saving locally.

The browser harness's CDP/loopback/owned-process lifecycle was adapted from the existing ShadeWindow historical-review browser-smoke.mjs (SHA256 468bc9276153f2e2a656597f948a6b55cab93cb525d2be5ee3283fa5a17e268b), whose original native lifecycle cites blob 3bab61a1dbaa386074ed33033cc42db9db4b46b3. Its scenario driver was not run or changed.

## Replaying the focused checks

No package installation is required for the Python checks:

    cd candidate/utility_watch
    python -B -m unittest discover -s tests -p test_review_report.py -v

candidate.patch has ordinary repository-relative Git headers. In a separate checkout at the exact baseline, git apply --check and git apply reproduce the four changed paths. evidence/qualify_preservation.py records the tested reconstruction and index replay. To rerun that helper, give it a fresh packet directory containing baseline/, candidate/, source-pins.json and evidence/candidate-normal.json; its patch and receipt outputs are exclusive and must not already exist.

For an optional actual browser replay, create a fresh owned fixture directory with an evidence/ child. Copy only native-review-with-history.csv and browser-expected.json into it. Run the candidate CLI to create evidence/example-saved-review.html there, using the same worksheet filename. Then run:

    node evidence/browser_review_report.mjs FRESH_FIXTURE_ROOT INSTALLED_CHROMIUM OWNED_PROFILE_PARENT

Use an already installed Node 22+ and Chromium. On Snap Chromium the profile parent must be within the user's permitted snap common directory. The helper creates its own unique profile, uses only loopback, and cleans up its own process/profile. Its screenshot/PDF/receipt outputs are exclusive, so use a fresh fixture rather than the already qualified packet's evidence directory. The browser fixture is a POSIX-native optional check, not a Windows browser qualification.

All input data is synthetic. No real source export, provider/model call, payment operation, service, deployment, dependency installation or paused browser profile was used. The view captures a saved worksheet; it does not establish whether underlying findings remain current.

