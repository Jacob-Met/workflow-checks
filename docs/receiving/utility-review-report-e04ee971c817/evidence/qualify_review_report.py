"""Run only the new worksheet-view consumer suite in an owned temporary namespace."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    if output.exists():
        raise SystemExit("refusing to replace an earlier qualification receipt")
    package = root / "candidate" / "utility_watch"
    temporary = root / "temporary-tests"
    temporary.mkdir(exist_ok=True)
    tempfile.tempdir = str(temporary)
    sys.path.insert(0, str(package))
    suite = unittest.defaultTestLoader.discover(str(package / "tests"), pattern="test_review_report.py")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    pins = {}
    for relative in [
        "utility_watch/uwatch/review_report.py", "utility_watch/uwatch/cli.py",
        "utility_watch/tests/test_review_report.py", "utility_watch/docs/review-report.md",
    ]:
        raw = (root / "candidate" / relative).read_bytes()
        pins[relative] = {
            "git_blob": hashlib.sha1(b"blob " + str(len(raw)).encode() + bytes([0]) + raw).hexdigest(),
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
        }
    receipt = {
        "result": "PASS" if result.wasSuccessful() else "FAIL",
        "python": sys.version, "optimized": sys.flags.optimize,
        "tests_run": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "skips": len(result.skipped),
        "log": stream.getvalue(), "candidate_files": pins,
        "limits": "Seven new focused consumer methods only. The complete inherited suite is not rerun here. Publication failures are controlled fsync/link injections; no real production/filesystem failure is claimed.",
    }
    with output.open("x", encoding="utf-8") as target:
        json.dump(receipt, target, ensure_ascii=False, indent=2)
        target.write("\n")
    print(stream.getvalue(), end="")
    print(json.dumps({k: receipt[k] for k in ("result", "optimized", "tests_run", "failures", "errors", "skips")}))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
