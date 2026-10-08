"""Replay only the optimized fixture interrupted by external ENOSPC."""
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

root = Path(sys.argv[1]).resolve()
output = root / "evidence/candidate-optimized-destination-replay-v2.json"
if output.exists() or sys.flags.optimize != 1:
    raise SystemExit("requires a new receipt and optimized Python")
prior = json.loads((root / "evidence/candidate-optimized.json").read_text())
if prior["tests_run"] != 7 or prior["errors"] != 1 or "No space left on device" not in prior["log"]:
    raise SystemExit("unexpected interrupted qualification")
for path, pin in prior["candidate_files"].items():
    if hashlib.sha256((root / "candidate" / path).read_bytes()).hexdigest() != pin["sha256"]:
        raise SystemExit("candidate source drift: " + path)
temporary = root / "temporary-tests"
temporary.mkdir(exist_ok=True)
tempfile.tempdir = str(temporary)
sys.path[:0] = [str(root / "candidate/utility_watch"), str(root / "candidate/utility_watch/tests")]
name = "test_review_report.ReviewReportTests.test_existing_destinations_and_source_are_preserved"
suite = unittest.defaultTestLoader.loadTestsFromName(name)
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
receipt = {
    "result": "PASS" if result.wasSuccessful() else "FAIL",
    "optimized": sys.flags.optimize, "python": sys.version, "test": name,
    "tests_run": result.testsRun, "failures": len(result.failures),
    "errors": len(result.errors), "skips": len(result.skipped), "log": stream.getvalue(),
    "candidate_files": prior["candidate_files"],
    "reason": "Only this fixture was interrupted by real ENOSPC before product invocation. The original seven-method optimized receipt is retained unchanged; its other six methods passed. A first portable replay lacked its empty temporary parent after mirroring and also stopped in fixture setup; that receipt is preserved. This v2 runner creates its owned parent.",
}
with output.open("x", encoding="utf-8") as target:
    json.dump(receipt, target, ensure_ascii=False, indent=2)
    target.write("\n")
print(stream.getvalue(), end="")
print(json.dumps({key: receipt[key] for key in ("result", "optimized", "tests_run", "failures", "errors", "skips")}))
raise SystemExit(0 if result.wasSuccessful() else 1)
