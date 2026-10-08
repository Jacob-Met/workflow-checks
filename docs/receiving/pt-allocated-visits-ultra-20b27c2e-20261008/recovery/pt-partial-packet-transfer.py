#!/usr/bin/env python3
"""Bounded, source-preserving publication transfer for an independently reviewed repo contribution.
Default output is one self-contained UTF-8 export on stdout. --write writes exact additive
packet files and manifests only under this worker's own native namespace. No browser/test,
capacity polling, networking, configuration change, or source modification is performed.
"""
from pathlib import Path
import argparse, base64, datetime, hashlib, json, sys, zlib

ROOT=Path("/tmp/ultra-20b27c2e-runtime-pt-allocations-review")
PREFIX="docs/receiving/pt-allocated-visits-ultra-20b27c2e-20261008/independent-review/"
REVIEW="# Independent receiving: PT allocated visits (partial browser qualification)\n\n## Disposition\n\nThe native projection, actual CLI exports and actual loopback HTTP receiving paths are qualified on the frozen Python sources. The narrow browser successor is **not yet independently qualified**. Keep the source contribution in draft and retain the affected browser gate before merge.\n\nThis review was authored independently by runtime_integration, ultra-20b27c2e-20261008. The contract, mixed synthetic fixture, manual facts, baseline oracle and executable probes were frozen at 2026-10-08 15:56:06 UTC before candidate source or author tests were disclosed. Author tests were not read.\n\n## Exact source and scope\n\nRepository: Jacob-Met/workflow-checks, PT issue #43. Primary commit 0418e6308d886d0678ace759a9b984c1d06ac54d, tree 92c62093a0bd4d86e8a518a50cb2869d809cbe63. All 15 baseline inputs were checked against primary Git blobs. The full primary tree and the baseline source closure are included.\n\nFinal source pins:\n\n| File | SHA256 | Git blob |\n| --- | --- | --- |\n| pt_auth/ptauth/allocated.py | 343cecb2e6dcca2accff77cd7b75db57a47b61043ca4e07478824af66a918a1a | cd8a391067639f5f647818ed03a122089b4bad74 |\n| pt_auth/ptauth/report.py | 18f0faf298e96e28ac1f2d9d05bb8620bac1005beb1127a10e9816d52c225fcb | ef95e177ee35e32447743ab6867e739be5cbe9ba |\n| pt_auth/ptauth/ui.html | 4281cb85515441e9bce852a1f842e5e55ee240228319fc9cfc566e77112bb5ef | af7dadb2755bb587494644d85c26d3ae51abcbe3 |\n\nThe original candidate UI was 0ed0e49cbdbb5c0b32b2ff7568c95a1650a8dffc38f51f9dd72d28e50b835cc0. The final UI adds exactly 132 bytes of scoped CSS: a 64rem fixed-layout allocation table and nonwrapping dates. Removing those bytes restores the original UI exactly. All JavaScript and the other 15 copied files remain identical.\n\nThe independent audit removes the five declared report additions and the declared UI insertions to recover exact primary bytes. The README is insert-only; all 12 inherited, unowned files remain exact. Engine, data loading, existing web routes, CLI, calendar, staff review and audit behavior were not changed. Subsequent primary main 4f434591c166fc7d3ea7831e52edafe6c23d8843/tree b9935837bf6ee5377a2ed9d1e3b025762502d4a2 was reported and checked by root/producer as containing byte-identical PT source; this worker's executable receiving remains bound to the independently recorded 0418 closure.\n\n## Native receiving evidence\n\nThe fixture has 67 raw visits, 15 authorization ledgers, 52 allocated visits, 14 allocated authorization occurrences and seven raw visit clinic groups. It yields 26 used memberships and 26 scheduled memberships. The oracle matched 260 manually specified allocation/provenance facts against actual unchanged baseline engine memberships.\n\nThe fixture challenges overlapping amendments, repeated authorization numbers, distinct periods and patient/payer identities, completed-first capacity, inclusive windows, completed future visits and past scheduled visits, over-capacity/outside-window visits, ignored statuses and visit types, unknown payer/missing name, offset timestamps, duplicate rows, blank and multiline clinics, Unicode, quoted newlines, regex punctuation and literal HTML. All data is synthetic.\n\n| Run | Actual outcome |\n| --- | --- |\n| Primary baseline native | 21 methods: six ordinary controls passed; 15 distinct missing-feature methods failed with 19 failure entries; no errors or skips. |\n| Frozen candidate native | 21 methods passed; no failures, errors or skips. |\n\nThe native runner invokes the public CLI on mixed and empty fixtures, reads through the real make_handler HTTP server, compares the complete 21-field CSV and summary projection with the independent 52-row oracle, checks full printable digest and escaping, and verifies source/input/report/staff-state/audit custody. Existing worklist, ledger, uncovered-visits and visit-status CSV bytes are identical to baseline. Only disclosed feature keys/generated time are normalized in summary comparisons; only timestamp is normalized in audit comparison.\n\nThe accepted native run remains applicable to the CSS successor because both Python sources and the full receiving dependency closure are unchanged. It has not been repeated.\n\n## Browser evidence and the real finding\n\nAll browser requests used the actual loopback application and synthetic saved reports. Non-loopback requests were blocked. A known Chrome internal date-input SVG remained blocked and was classified only by its exact observed URL digest; no network exception was enabled.\n\n| Run or diagnostic | Actual outcome |\n| --- | --- |\n| First baseline browser | 16 groups: two passed, 14 failed; one failure was the receiver's classification of the blocked built-in SVG. |\n| Baseline with exact SVG classification | 16 groups: three controls passed, 13 missing-panel groups failed; no errors. |\n| Original candidate UI | 16 groups: eight passed, eight failed; no errors. |\n| Existing baseline keyboard controls | Native visible-label typeahead and plain Backspace/Delete editing were qualified on existing input/select controls. |\n| Final corrected affected replay | Pending: refused before Node/Chrome at the fresh capacity check. |\n\nThe original candidate already passed ordinary tabs/calendar access and actual ledger CSV download, the complete allocation panel and provenance, restrictive-filter full CSV download plus full printable digest, missing/nonlist legacy handling, completed empty output, injection/read-only checks, and source/report custody.\n\nThe original eight failing groups comprised keyboard/filter/search mechanisms (and the dependent compound-filter group) plus a real narrow-screen readability defect. The existing-control event trace demonstrated the platform behavior before changing the receiver: Home/Arrow keys did not select the expected option, and Meta+A/Control+A/triple-click did not reliably select all input text. The corrected receiver uses the independently proven native visible-label typeahead and plain edit keys; it has **not** yet completed the affected product replay.\n\nAt 390px viewport width, the original eight-column allocation table compressed into a 350px region. Recorded dates and headings wrapped to one/few characters per line; ordinary rows were approximately 378px tall, with 52 rows spanning approximately 21,033px. Text was present, but scanning it was impractical. The exact screenshot and geometry are retained. The producer accepted this finding and made only the 132-byte CSS correction. The pending check measures readable date lines, readable font/column geometry, native Tab access to the review region, and access to the rightmost source column where scrolling is necessary. Horizontal overflow itself is not treated as the product goal.\n\nOne real preexisting ledger.csv browser download has SHA256 d5f93394e1c69357c470ee759c8a27399fc420dea4423a1cd7ac1d36da0d0a9b in both baseline and candidate.\n\n## Preserved failures and remaining gate\n\nThe original browser/probe versions, selector correction, blocked-resource classification, baseline key traces, first label-prefix mistake and correction, source audit's initial list-join receiver error, native pre-execution ENOSPC, screenshots, commands, raw logs and custody receipts are preserved. Corrections to receiver mechanics are not represented as production fixes.\n\nAt 2026-10-08 17:09:05 UTC, the queued affected run's wrapper measured 151,523,328 bytes free against its unchanged 268,435,456-byte floor and exited before Node or Chrome. No output directory or browser profile was created. The slot was released. Later read-only file inventory and three file reads through Remote Desktop Commander timed out with MCP error -32603; no file loss or production behavior is inferred from those transport failures.\n\n**Remaining independent gate:** run the current b72c64b4 receiver's affected keyboard/filter groups against the original candidate; then run the readable-layout/access group against the exact 4281cb85 CSS successor, retaining per-run GET/source/custody guards. These are queued, not passed. Root also owns the existing hosted test matrix and final receiving-tree checks. This partial packet does not authorize merge by itself.\n\n## Reproduction and file layout\n\nRun the included extractor with an empty owned directory. It verifies every restored byte and refuses to overwrite a differing file. recorded-evidence.json includes original source copies, synthetic fixtures, all executed probe versions, raw results, reports, downloads, screenshots and correction lineage. evidence-catalog.json provides each path, size and SHA256 without opening the compressed contents.\n\nThe approved native device was 0e3d582f-e25b-44b2-8418-9639fc4e4e33. Runtime: /usr/local/bin/python3 (3.13.7), /opt/homebrew/Cellar/node/26.3.0/bin/node (26.3.0), installed Puppeteer at /Users/me/.npm/_npx/4b4c857f6efdfb61/node_modules/puppeteer/lib/puppeteer/puppeteer.js, and /Applications/Google Chrome.app/Contents/MacOS/Google Chrome (154.0.8037.98). No dependencies were installed.\n\nFrom the extracted root, native reproduction is:\n```sh\nPYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3 -B independent_pt_receiver.py --source baseline --out replay-baseline-native\nPYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3 -B independent_pt_receiver.py --source candidate --out replay-candidate-native\n```\n\nThe pending bounded browser commands use fresh output names and the already recorded candidate-native reports:\n```sh\nPT_REVIEW_GROUPS=3,4,5,6,7,8,9,11,14,15 /opt/homebrew/Cellar/node/26.3.0/bin/node independent_pt_browser.cjs candidate candidate-native replay-original-affected\nPT_REVIEW_GROUPS=11,14,15 /opt/homebrew/Cellar/node/26.3.0/bin/node independent_pt_browser.cjs candidate-mobile candidate-native replay-mobile-affected\n```\n\nThe first pending command intentionally retains the original CSS, so its readability group is expected to retain the source-level negative witness. The second targets the corrected CSS. Expectations are separate from actual recorded outcomes. Respect the unchanged launch floor and serialized browser slot before running either.\n\nThere was no use of real patient data, live accounts, installed app data, calendar submission, deployment or real service mutation.\n"
EXTRACTOR="#!/usr/bin/env python3\n\"\"\"Restore exact synthetic receiving evidence; no dependencies.\"\"\"\nfrom pathlib import Path, PurePosixPath\nimport argparse, base64, hashlib, json, zlib\np=argparse.ArgumentParser()\np.add_argument(\"--bundle\",type=Path,default=Path(__file__).with_name(\"recorded-evidence.json\"))\np.add_argument(\"--out\",type=Path,required=True)\na=p.parse_args()\nbundle=json.loads(a.bundle.read_text(encoding=\"utf-8\"))\nroot=a.out.resolve(); root.mkdir(parents=True,exist_ok=True)\nrestored=0\nfor rel,info in sorted(bundle[\"files\"].items()):\n    name=PurePosixPath(rel)\n    if name.is_absolute() or not name.parts or any(v in (\"\",\".\",\"..\") for v in name.parts):\n        raise ValueError(\"Unsafe evidence path: \"+rel)\n    target=root.joinpath(*name.parts)\n    if not target.resolve().is_relative_to(root):\n        raise ValueError(\"Evidence destination escapes root: \"+rel)\n    encoded=bundle[\"blobs\"][info[\"sha256\"]]\n    raw=zlib.decompress(base64.b64decode(encoded[\"data\"],validate=True))\n    if len(raw)!=info[\"bytes\"] or hashlib.sha256(raw).hexdigest()!=info[\"sha256\"]:\n        raise ValueError(\"Evidence digest mismatch: \"+rel)\n    target.parent.mkdir(parents=True,exist_ok=True)\n    if target.exists():\n        if target.is_symlink() or target.read_bytes()!=raw:\n            raise FileExistsError(\"Refusing to replace different existing file: \"+str(target))\n    else:\n        with target.open(\"xb\") as f: f.write(raw)\n    restored+=1\nprint(json.dumps({\"restored_files\":restored,\"out\":str(root)}))\n"
PINS={
 "ROOT-CONTRACT.md":"034a68919ba10a0bc7c206e1b3f2653c4c8196422120850b3ca0b8692f0fdd0d",
 "oracle.json":"eed5ac9d3226d0040df97ba4d11591b059c9b8d5c5ba55cfd868180c2c31b996",
 "independent_pt_receiver.py":"c5cdb324a7775e00fec2290652841700f7738242d1c27b1891f96f30ecb00543",
 "independent_pt_browser.cjs":"b72c64b4ec53e342892c65a65b16005250ea6e5cb0b0e958c110a6ced169b18d",
 "pt_browser_server.py":"751f2363c0ca3548560143f3db03fde3559d8abe8d8e3e8bc97cb39d2a3d6188",
 "candidate/pt_auth/ptauth/allocated.py":"343cecb2e6dcca2accff77cd7b75db57a47b61043ca4e07478824af66a918a1a",
 "candidate/pt_auth/ptauth/report.py":"18f0faf298e96e28ac1f2d9d05bb8620bac1005beb1127a10e9816d52c225fcb",
 "candidate/pt_auth/ptauth/ui.html":"0ed0e49cbdbb5c0b32b2ff7568c95a1650a8dffc38f51f9dd72d28e50b835cc0",
 "candidate-mobile/pt_auth/ptauth/allocated.py":"343cecb2e6dcca2accff77cd7b75db57a47b61043ca4e07478824af66a918a1a",
 "candidate-mobile/pt_auth/ptauth/report.py":"18f0faf298e96e28ac1f2d9d05bb8620bac1005beb1127a10e9816d52c225fcb",
 "candidate-mobile/pt_auth/ptauth/ui.html":"4281cb85515441e9bce852a1f842e5e55ee240228319fc9cfc566e77112bb5ef"
}
DIRECT=[
 "ROOT-CONTRACT.md","public-contract.json","independent-freeze.json",
 "primary-source.json","baseline-closure.json","oracle.json",
 "independent_pt_receiver.py","independent_pt_browser.cjs","pt_browser_server.py",
 "audit_pt_scope.py","independent-scope-audit.json","final-scoped.diff",
 "mobile-css-only.diff","mobile-source-receipt.json"
]
def sha(b): return hashlib.sha256(b).hexdigest()
def blob(b): return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def jb(v): return (json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")
def read(rel): return (ROOT/rel).read_bytes()
for rel,expected in PINS.items():
    actual=sha(read(rel))
    if actual!=expected: raise ValueError("Source/evidence drift: "+rel+" "+actual)
native=json.loads(read("candidate-native/result.json"))
if not (native["tests_run"]==21 and native["failures"]==native["errors"]==native["skips"]==0):
    raise ValueError("Native acceptance receipt differs")
browser=json.loads(read("candidate-browser/result.json"))
if tuple(browser[k] for k in ("groups","passed","failures","errors"))!=(16,8,8,0):
    raise ValueError("Original browser receipt differs")
before=json.loads(read("before-browser-classified/result.json"))
if tuple(before[k] for k in ("groups","passed","failures","errors"))!=(16,3,13,0):
    raise ValueError("Classified baseline browser receipt differs")

# Read this one owned namespace only; retain source, failed attempts, and exact raw evidence.
# Exclude only disposable runtime caches and previously derived export files.
excluded_dirs={"chrome-profile","__pycache__",".pytest_cache",".git","node_modules","publication-partial"}
excluded_roots={"publication-partial-files.json","publication-partial-export.json","pt-partial-packet-transfer-20261008.py"}
files={}; blobs={}; total=0
for p in sorted(ROOT.rglob("*")):
    rel=p.relative_to(ROOT)
    if p.is_symlink(): continue
    if not p.is_file() or any(x in excluded_dirs for x in rel.parts) or rel.as_posix() in excluded_roots:
        continue
    if rel.parts[0].startswith("publication-"): continue
    data=p.read_bytes(); total+=len(data)
    if total>40*1024*1024: raise ValueError("Owned evidence exceeds bounded 40 MiB input budget")
    digest=sha(data); files[rel.as_posix()]={"bytes":len(data),"sha256":digest,"git_blob_sha":blob(data)}
    if digest not in blobs:
        blobs[digest]={"encoding":"zlib-base64","data":base64.b64encode(zlib.compress(data,9)).decode("ascii")}
hold={
 "observed_at":"2026-10-08T17:09:05.391279+00:00",
 "free_bytes":151523328,"minimum_bytes":268435456,
 "status":"held_before_node_or_chrome","profile_created":False,"browser_launched":False,
 "planned_groups":[3,4,5,6,7,8,9,11,14,15],
 "probe_sha256":PINS["independent_pt_browser.cjs"],
 "transport_followup":"Owned read-only inventory and three source/receipt reads returned MCP -32603 request timed out. No source mutation or test was attempted.",
 "evidence_origin":"Exact approved-device start_process output preserved in collaboration transcript; it exited at wrapper preflight."
}
status={
 "reviewer":"runtime_integration","identity":"ultra-20b27c2e-20261008",
 "repository":"Jacob-Met/workflow-checks","issue":43,
 "primary_commit":"0418e6308d886d0678ace759a9b984c1d06ac54d",
 "primary_tree":"92c62093a0bd4d86e8a518a50cb2869d809cbe63",
 "disposition":"partial_independent_receiving_do_not_merge_before_affected_browser_gate",
 "native":{"methods":21,"passed":21,"failures":0,"errors":0,"skips":0,"receipt":"candidate-native/result.json"},
 "baseline_native":{"methods":21,"positive_methods":6,"missing_feature_methods":15,"failure_entries":19,"errors":0,"skips":0,"receipt":"before-native/result.json"},
 "original_browser":{"groups":16,"passed":8,"failed":8,"errors":0,"receipt":"candidate-browser/result.json"},
 "classified_baseline_browser":{"groups":16,"passed":3,"failed":13,"errors":0,"receipt":"before-browser-classified/result.json"},
 "source_audit":"independent-scope-audit.json",
 "final_ui_inverse_bytes":132,"all_javascript_unchanged":True,
 "source_finding":"390px table compressed recorded dates into one/few-character lines; corrected by scoped CSS, affected replay pending",
 "pending_groups":{"original_candidate":[3,4,5,6,7,8,9,11,14,15],"final_css_candidate":[11,14,15]},
 "original_candidate_group11_expected":"retained negative readability witness; expectation is not an executed result",
 "hosted_matrix":"owned by root; no local pytest or hosted acceptance claimed",
 "source_pins":PINS,"hold":hold
}
bundle={"format":"exact-owned-evidence-v1","files":files,"blobs":blobs}
catalog={"format":bundle["format"],"files":files,"total_file_bytes":total,"unique_blobs":len(blobs)}
payload={
 "REVIEW.md":REVIEW.encode("utf-8"),
 "independent-status.json":jb(status),
 "environment-hold-170905.json":jb(hold),
 "evidence-catalog.json":jb(catalog),
 "recorded-evidence.json":jb(bundle),
 "extract_evidence.py":EXTRACTOR.encode("utf-8")
}
for rel in DIRECT: payload[rel]=read(rel)
if sum(map(len,payload.values()))>12*1024*1024:
    raise ValueError("Packet exceeds bounded 12 MiB output budget")
base=ROOT/"publication-partial"
entries=[]
for name,data in sorted(payload.items()):
    entries.append({"repository_path":PREFIX+name,"local_path":str(base/name),
      "mode":"100644","bytes":len(data),"sha256":sha(data),"git_blob_sha":blob(data)})
manifest={"repository":"Jacob-Met/workflow-checks","prefix":PREFIX,
 "qualification":"partial; affected browser replay pending",
 "payload_files":len(entries),"payload_bytes":sum(x["bytes"] for x in entries),
 "recorded_files":len(files),"recorded_bytes":total,"entries":entries}
export={"manifest":manifest,"files":[{**entry,"content":payload[entry["repository_path"][len(PREFIX):]].decode("utf-8")} for entry in entries]}
parser=argparse.ArgumentParser();parser.add_argument("--write",action="store_true");args=parser.parse_args()
if args.write:
    base.mkdir(exist_ok=True)
    writes={base/name:data for name,data in payload.items()}
    writes[ROOT/"publication-partial-files.json"]=jb(manifest)
    writes[ROOT/"publication-partial-export.json"]=jb(export)
    for p,data in writes.items():
        if p.exists():
            if p.read_bytes()!=data: raise FileExistsError("Different existing derived artifact: "+str(p))
        else:
            with p.open("xb") as f: f.write(data)
        if sha(p.read_bytes())!=sha(data): raise IOError("Written byte mismatch: "+str(p))
    print(json.dumps({"manifest_path":str(ROOT/"publication-partial-files.json"),
      "manifest_sha256":sha(jb(manifest)),"export_path":str(ROOT/"publication-partial-export.json"),
      "export_sha256":sha(jb(export)),"files":len(entries),"bytes":manifest["payload_bytes"],
      "recorded_files":len(files),"recorded_bytes":total}))
else:
    sys.stdout.write(jb(export).decode("utf-8"))

