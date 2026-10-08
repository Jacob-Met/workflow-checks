"""Run the current native Freight test composition once and retain exact evidence."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest


def identity(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    code = args.candidate.resolve() / "freight_packets"
    args.output.mkdir(parents=True, exist_ok=False)
    files = {p.relative_to(args.candidate.resolve()).as_posix(): p.read_bytes()
             for p in sorted(args.candidate.resolve().rglob("*")) if p.is_file()}
    before = {name: identity(data) for name, data in files.items()}
    sys.path.insert(0, str(code))
    suite = unittest.defaultTestLoader.discover(str(code / "tests"), pattern="test*.py")

    class RecordedResult(unittest.TextTestResult):
        subtests = []

        def addSubTest(self, test, subtest, error):
            self.subtests.append({"test": str(test), "subtest": str(subtest), "passed": error is None})
            super().addSubTest(test, subtest, error)

    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=RecordedResult).run(suite)
    output = stream.getvalue().encode()
    after = {p.relative_to(args.candidate.resolve()).as_posix(): identity(p.read_bytes())
             for p in sorted(args.candidate.resolve().rglob("*")) if p.is_file()}
    records = sys.modules["test_terminal_review_export"].TerminalReviewExportTests.cli_records
    execution = {"schema": "canonical-freight-terminal-native-execution.v1", "python": sys.version,
                 "source_images": {name: {**identity(data), "base64": base64.b64encode(data).decode()}
                                   for name, data in files.items()},
                 "cli": records, "subtests": result.subtests,
                 "source_before": before, "source_after": after}
    raw = (json.dumps(execution, sort_keys=True, indent=2) + "\n").encode()
    packed = base64.b64encode(gzip.compress(raw, mtime=0)) + b"\n"
    (args.output / "execution.json.gz.b64").write_bytes(packed)
    (args.output / "unittest.txt").write_bytes(output)
    receipt = {"schema": "canonical-freight-terminal-native-receipt.v1", "python": sys.version,
               "passed": result.wasSuccessful() and before == after,
               "methods": result.testsRun, "subtests": len(result.subtests),
               "failures": len(result.failures), "errors": len(result.errors), "skips": len(result.skipped),
               "new_cli_processes": len(records),
               "successful_cli": sum(r["returncode"] == 0 for r in records),
               "refused_cli": sum(r["returncode"] == 2 for r in records),
               "postpublication_receipt_refusal": sum(r["stdout_full"] for r in records),
               "source_files_unchanged": before == after, "source_pins": before,
               "execution_decoded": identity(raw), "execution_archive": identity(packed),
               "test_log": identity(output),
               "boundary": "One current native unittest composition. New real CLI processes are recorded separately from direct API boundary/interleaving controls and inherited Freight tests. Exact canonical batch/per-load producers; no old baseline replay, browser automation, external delivery or hosted-runtime claim."}
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k: v for k, v in receipt.items() if k in {
        "passed", "methods", "subtests", "failures", "errors", "skips", "new_cli_processes",
        "successful_cli", "refused_cli", "postpublication_receipt_refusal", "source_files_unchanged"}}))
    if not receipt["passed"]:
        print(stream.getvalue())
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
