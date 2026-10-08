"""Receive only the report-row revision against its unchanged raw R1 witness."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest


def pin(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--r1", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.candidate.resolve()
    code = source / "freight_packets"
    before = {p.relative_to(source).as_posix(): pin(p.read_bytes()) for p in sorted(source.rglob("*")) if p.is_file()}
    sys.path.insert(0, str(code))
    spec = importlib.util.spec_from_file_location("terminal_shape_regression", code / "tests/test_terminal_review_export.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite = unittest.TestSuite([module.TerminalReviewExportTests(
        "test_malformed_native_report_row_refuses_and_empty_report_is_valid")])
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    after = {p.relative_to(source).as_posix(): pin(p.read_bytes()) for p in sorted(source.rglob("*")) if p.is_file()}
    records = module.TerminalReviewExportTests.cli_records
    original = json.loads(args.r1.read_bytes())
    raw_preserved = len(records) == 2 and records[0]["fixture_base64"] == original["fixture"]
    receipt = {"schema": "canonical-freight-terminal-shape-receiving.v1", "python": sys.version,
               "passed": result.wasSuccessful() and before == after and raw_preserved,
               "methods": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
               "new_cli_processes": len(records), "original_raw_witness_preserved": raw_preserved,
               "original_returncode": original["returncode"], "source_preserved": before == after,
               "source_before": before, "source_after": after, "cli": records,
               "original_witness": pin(args.r1.read_bytes()), "log": stream.getvalue(),
               "boundary": "Only the new shape-admission regression: exact raw flags:[null] R1 refusal plus valid-empty native canonical parity control. Earlier authored/native/independent results are not replayed or relabeled."}
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k: v for k, v in receipt.items() if k in {
        "passed", "methods", "failures", "errors", "new_cli_processes", "original_raw_witness_preserved",
        "original_returncode", "source_preserved", "log"}}))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
