"""Reconstruct and replay this four-path patch against its exact selected native base."""
from __future__ import annotations
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
BASE = ROOT / "baseline"
CANDIDATE = ROOT / "candidate"
PARSER = "    review_report = sub.add_parser(\"review-report\", help=\"read or print a saved review worksheet as HTML\")\r\n    review_report.add_argument(\"--worksheet\", type=Path, required=True, help=\"saved uwatch-review-v1 CSV worksheet\")\r\n    review_report.add_argument(\"--out\", type=Path, required=True, help=\"new HTML path in an existing directory; never replaces a file\")\r\n".encode()
DISPATCH = "    if a.cmd == \"review-report\":\r\n        from .review_report import export_html\r\n        try:\r\n            result = export_html(a.worksheet, a.out)\r\n        except (OSError, ValueError, KeyError) as exc:\r\n            print(f\"uwatch: review report error: {exc}\", file=sys.stderr)\r\n            return 2\r\n        print(f\"review report: {result['current']} current findings; {result['history']} prior findings\")\r\n        print(f\"worksheet SHA256: {result['worksheet_sha256']}\")\r\n        print(f\"report: {a.out}\")\r\n        return 0\r\n".encode()

def pin(raw):
    return {"git_blob": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}

def require(ok, message):
    if not ok:
        raise RuntimeError(message)

receipt = {"result": "INCOMPLETE", "python": sys.version, "checks": [], "commands": []}
def checked(name, condition):
    require(condition, name)
    receipt["checks"].append({"name": name, "ok": True})

source = json.loads((ROOT / "source-pins.json").read_text())
qualified = json.loads((ROOT / "evidence/candidate-normal.json").read_text())["candidate_files"]
baseline = {}
for name, expected in source["files"].items():
    if not name.startswith("baseline/"):
        continue
    relative = name.removeprefix("baseline/")
    raw = (ROOT / name).read_bytes()
    checked("exact pinned native " + relative, pin(raw) == expected)
    baseline[relative] = raw
actual = {}
for name, expected in qualified.items():
    raw = (CANDIDATE / name).read_bytes()
    actual[name] = pin(raw)
    checked("unchanged qualified candidate " + name, pin(raw) == expected)

cli = (CANDIDATE / "utility_watch/uwatch/cli.py").read_bytes()
checked("single additive parser span", cli.count(PARSER) == 1)
checked("single additive dispatch span", cli.count(DISPATCH) == 1)
restored = cli.replace(PARSER, b"", 1).replace(DISPATCH, b"", 1)
restored = restored.replace(b"<generate|run|review|review-report>", b"<generate|run|review>", 1)
checked("entire prior CLI restored byte exactly", restored == baseline["utility_watch/uwatch/cli.py"])
checked("CLI line endings remain CRLF", cli.count(b"\n") == cli.count(b"\r\n"))
support = {}
for name, raw in baseline.items():
    if name == "utility_watch/uwatch/cli.py":
        continue
    preserved = (CANDIDATE / name).read_bytes()
    checked("entire native dependency preserved " + name, preserved == raw)
    support[name] = pin(preserved)

temporary_parent = ROOT / "temporary-tests"
temporary_parent.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="utility-review-patch-", dir=temporary_parent) as folder:
    repo = Path(folder)
    def git(*args, data=None):
        command = ["git", "-c", "core.autocrlf=false", "-c", "core.hooksPath=/dev/null",
                   "-c", "commit.gpgsign=false", "-c", "user.name=Utility Watch receiving",
                   "-c", "user.email=utility-receiving@invalid.local", *args]
        completed = subprocess.run(command, cwd=repo, input=data, capture_output=True, timeout=30)
        receipt["commands"].append({"argv": command, "returncode": completed.returncode,
                                    "stdout": "" if args and args[0] == "diff" and "--binary" in args else completed.stdout.decode("utf8"),
                                    "stderr": completed.stderr.decode("utf8")})
        require(completed.returncode == 0, "git command failed: " + repr(args))
        return completed.stdout
    git("init", "--quiet", "--template=")
    for name, raw in baseline.items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    git("add", "--", *baseline)
    git("commit", "--quiet", "-m", "Exact selected native Utility Watch base")
    for name in qualified:
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((CANDIDATE / name).read_bytes())
    git("add", "--", *qualified)
    changed = git("diff", "--cached", "--name-only", "-z").decode().split("\0")[:-1]
    checked("patch changes exactly the four reserved paths", sorted(changed) == sorted(qualified))
    patch = git("diff", "--cached", "--binary", "--full-index", "--no-ext-diff")
    checked("ordinary repository-relative patch headers", b"diff --git a/utility_watch/" in patch and b"baseline/" not in patch and b"candidate/" not in patch)
    with (ROOT / "candidate.patch").open("xb") as stream:
        stream.write(patch)
    git("reset", "--hard", "HEAD")
    git("apply", "--check", "--index", "-", data=patch)
    git("apply", "--index", "-", data=patch)
    for name in sorted(set(baseline) | set(qualified)):
        checked("native git apply replay exact " + name, (repo / name).read_bytes() == (CANDIDATE / name).read_bytes())
    receipt["patch"] = pin(patch)

receipt.update(result="PASS", source_ref=source["source_ref"], source_tree=source["source_tree"],
               candidate_files=actual, native_support=support,
               limits=["This is an exact selected-source replay; it is not a complete repository checkout.",
                       "No remote calls, Git hooks, installed source changes, or inherited full test suite.",
                       "Git stderr is retained verbatim, including any line-ending whitespace diagnostics."])
with (ROOT / "evidence/preservation.json").open("x") as stream:
    stream.write(json.dumps(receipt, indent=2) + "\n")
print(json.dumps({"result":receipt["result"], "checks":len(receipt["checks"]), "changed_paths":changed,
                  "patch":receipt["patch"], "git_stderr":[item["stderr"] for item in receipt["commands"] if item["stderr"]]}))

