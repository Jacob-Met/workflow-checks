"""One actual saved-worksheet CLI control on the accepted current engine."""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
AUTHOR = Path(sys.argv[2]).resolve()
def pin(raw):
    return {"git_blob": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
def require(ok, message):
    if not ok:
        raise RuntimeError(message)
manifest = json.loads((ROOT / "current-source-pins.json").read_text())
before = {name: pin((ROOT / "candidate" / name).read_bytes()) for name in manifest["candidate_files"]}
require(before == manifest["candidate_files"], "current source drift")
worksheet = AUTHOR / "evidence/native-review-with-history.csv"
raw = worksheet.read_bytes()
require(hashlib.sha256(raw).hexdigest() == "d9305edacc7e94a7ac076809a9e0c7cab1ce0ba557616be9afd8a86b8b783ddd", "captured input drift")
target = ROOT / "evidence/current-review.html"
require(not target.exists(), "unexpected pre-existing receiving output")
tripwires = """import runpy,socket,subprocess,sys
import uwatch.engine as engine
import uwatch.review as review
import uwatch.synth as synth
def forbidden(*args,**kwargs): raise AssertionError('unexpected checker/reconciliation/generator/external entry')
engine.run=engine.load=engine.check=review.reconcile=review._current=synth.generate=forbidden
socket.socket=subprocess.Popen=forbidden
sys.argv=['uwatch',*sys.argv[1:]]
runpy.run_module('uwatch',run_name='__main__')
"""
command = [sys.executable, "-B", "-c", tripwires, "review-report",
           "--worksheet", str(worksheet), "--out", str(target)]
completed = subprocess.run(command, cwd=ROOT / "candidate/utility_watch",
                           capture_output=True, text=True, timeout=20)
checks = []
def check(name, condition):
    checks.append({"name": name, "ok": bool(condition)})
check("actual current-native CLI succeeds without trapped effects", completed.returncode == 0)
check("actual CLI stderr empty", completed.stderr == "")
check("captured native worksheet unchanged", worksheet.read_bytes() == raw)
check("output exists as a regular file", target.is_file())
if target.is_file():
    document = target.read_bytes()
    check("HTML remains exact across the accepted engine change", pin(document)["sha256"] == "6ba4c1eaeb71c6eece6a52229bd53e16ebc1b2dd87926c6025cb997feef0a653")
    check("exact same HTML byte count", len(document) == 21880)
else:
    document = b""
check("current/history counts retain the native saved snapshot", "14 current findings; 1 prior findings" in completed.stdout)
check("stdout binds the exact captured bytes", hashlib.sha256(raw).hexdigest() in completed.stdout)
after = {name: pin((ROOT / "candidate" / name).read_bytes()) for name in manifest["candidate_files"]}
check("all eight current source files unchanged by receiving", after == before)
require(pin((ROOT / "candidate/utility_watch/uwatch/engine.py").read_bytes())["git_blob"] == "b764a1f45ba718b31f7841e2c2f61d16a7fef5e9", "accepted engine not present")
result = {"result": "PASS" if all(item["ok"] for item in checks) else "FAIL",
          "python": sys.version, "source_ref": manifest["source_ref"], "source_tree": manifest["source_tree"],
          "candidate_files": before, "actual_cli_children": 1, "checks": checks,
          "command": command, "returncode": completed.returncode, "stdout": completed.stdout,
          "stderr": completed.stderr, "worksheet": pin(raw), "html": pin(document),
          "limits": ["One authored current-dependency receiving case, not a new independent review or repeated full suite.",
                     "The accepted account-identity policy itself is not re-evaluated; the view consumes the saved native worksheet without checker/reconciliation entry.",
                     "No live source, provider, service or payment effects."]}
with (ROOT / "evidence/current-dependency-results.json").open("x") as stream:
    stream.write(json.dumps(result, indent=2) + "\n")
print(json.dumps({"result": result["result"], "root": str(ROOT), "source_ref": result["source_ref"],
                  "conditions": len(checks), "failures": sum(not item["ok"] for item in checks),
                  "html": result["html"], "python": result["python"]}))
raise SystemExit(0 if result["result"] == "PASS" else 1)
