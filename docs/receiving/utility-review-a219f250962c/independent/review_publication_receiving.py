"""Independent CLI failure-boundary controls; inject only a synthetic concurrent writer/I/O fault."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import review_cli_receiving as base


HOOK = r'''
import json, os, runpy, sys
from pathlib import Path
from uwatch import review

plan = json.loads(Path(sys.argv[1]).read_text())
events = []
def event(value):
    events.append(value)
    Path(plan["events"]).write_text(json.dumps(events))
def mutate():
    target = Path(plan["target"])
    if plan["mutation"] == "remove":
        target.unlink()
    else:
        target.write_bytes(bytes.fromhex(plan["content_hex"]))
    event("foreign_writer_mutated_input")

if plan["hook"] == "check":
    original = review.engine.check
    def check(*args, **kwargs):
        result = original(*args, **kwargs)
        event("actual_native_check_returned")
        mutate()
        return result
    review.engine.check = check
elif plan["hook"] == "combine":
    original = review._combine
    def combine(*args, **kwargs):
        result = original(*args, **kwargs)
        event("actual_reconciliation_returned")
        mutate()
        return result
    review._combine = combine
elif plan["hook"] == "link":
    original = review.os.link
    def link(source, destination, *args, **kwargs):
        event("completed_temporary_output_present")
        assert Path(source).read_bytes().startswith(b"review_status,reviewer,note,")
        if plan["rival_kind"] == "file":
            Path(destination).write_bytes(bytes.fromhex(plan["rival_hex"]))
        else:
            Path(destination).symlink_to(plan["rival_target"])
        event("foreign_writer_claimed_destination")
        return original(source, destination, *args, **kwargs)
    review.os.link = link
elif plan["hook"] == "fsync":
    def fsync(fd):
        event("injected_fsync_failure")
        raise OSError("independent synthetic fsync failure")
    review.os.fsync = fsync
elif plan["hook"] == "unlink":
    original = review.os.unlink
    def unlink(path, *args, **kwargs):
        if Path(path).name.startswith(".uwatch-review-") and str(path).endswith(".csv"):
            event("injected_post_publication_cleanup_failure")
            raise OSError("independent synthetic cleanup failure")
        return original(path, *args, **kwargs)
    review.os.unlink = unlink

sys.argv = ["uwatch", *plan["arguments"]]
runpy.run_module("uwatch", run_name="__main__")
'''


class PublicationReceiving(unittest.TestCase):
    def fixture(self, label):
        fixture = base.ActualCLIReceiving()
        fixture._testMethodName = label
        fixture.setUp()
        return fixture

    def injected_cli(self, fixture, plan, previous=None):
        output = fixture.case / "new-review.csv"
        arguments = ["review", "--data", str(fixture.data), "--report", str(fixture.report / "summary.json"), "--out", str(output)]
        if previous is not None:
            arguments += ["--previous", str(previous)]
        event_path = fixture.case / "injection-events.json"
        plan.update(arguments=arguments, events=str(event_path))
        plan_path = fixture.case / "injection-plan.json"
        plan_path.write_text(json.dumps(plan, indent=2) + "\n")
        env = dict(os.environ, PYTHONPATH=str(base.SOURCE), PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(fixture.case))
        result = subprocess.run([sys.executable, "-B", "-c", HOOK, str(plan_path)],
                                cwd=base.SOURCE, env=env, capture_output=True, text=True, timeout=15)
        self.assertTrue(event_path.exists(), "fault injection seam never ran")
        base.EXECUTIONS.append({"case": fixture._testMethodName, "arguments": arguments,
                                "source": str(base.SOURCE), "injection": plan,
                                "events": json.loads(event_path.read_text()), "exit": result.returncode,
                                "stdout": result.stdout, "stderr": result.stderr})
        return result, output

    def test_observed_input_mutations_refuse_publication(self):
        for kind in ("source", "report", "marker", "previous"):
            with self.subTest(kind=kind):
                fixture = self.fixture("observed_" + kind)
                previous = fixture.review()
                fixture.annotate(previous, note="Prior annotation must not be emitted against concurrent evidence.")
                before = fixture.protected()
                before[str(previous)] = previous.read_bytes()
                target = {"source": fixture.data / "bills.csv", "report": fixture.report / "summary.json",
                          "marker": fixture.data / "expected.json", "previous": previous}[kind]
                # Whitespace alone changes the exact read snapshot; malformed values are unnecessary.
                content = (target.read_bytes() + b"\n") if target.exists() else b"{}\n"
                result, output = self.injected_cli(fixture, {"hook": "combine" if kind == "previous" else "check",
                    "mutation": "write", "target": str(target), "content_hex": content.hex()}, previous)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("input changed during review", result.stderr)
                self.assertFalse(output.exists())
                self.assertEqual(target.read_bytes(), content)
                for path, raw in before.items():
                    if path != str(target):
                        self.assertEqual(Path(path).read_bytes(), raw, path)
                self.assertFalse(list(fixture.case.glob(".uwatch-review-*.csv")))

    def test_real_link_preserves_raced_destination(self):
        for kind in ("file", "symlink"):
            with self.subTest(kind=kind):
                fixture = self.fixture("raced_" + kind)
                before = fixture.protected()
                rival = b"Independent competing writer owns this exact destination.\n"
                plan = {"hook": "link", "rival_kind": kind, "rival_hex": rival.hex(),
                        "rival_target": str(fixture.data / "bills.csv")}
                result, output = self.injected_cli(fixture, plan)
                self.assertEqual(result.returncode, 2, result.stderr)
                if kind == "file":
                    self.assertEqual(output.read_bytes(), rival)
                    self.assertFalse(output.is_symlink())
                else:
                    self.assertTrue(output.is_symlink())
                    self.assertEqual(os.readlink(output), str(fixture.data / "bills.csv"))
                self.assertEqual(before, fixture.protected())
                self.assertFalse(list(fixture.case.glob(".uwatch-review-*.csv")))

    def test_io_failure_and_completed_publication_have_truthful_cli_exit(self):
        for hook in ("fsync", "unlink"):
            with self.subTest(hook=hook):
                fixture = self.fixture("io_" + hook)
                previous = fixture.review()
                fixture.annotate(previous, note="Literal annotation survives a completed publication.")
                prior = previous.read_bytes()
                before = fixture.protected()
                result, output = self.injected_cli(fixture, {"hook": hook}, previous)
                self.assertEqual(result.returncode, 2 if hook == "fsync" else 0, result.stderr)
                self.assertEqual(output.exists(), hook == "unlink")
                self.assertEqual(before, fixture.protected())
                self.assertEqual(previous.read_bytes(), prior)
                temporary = list(fixture.case.glob(".uwatch-review-*.csv"))
                if hook == "fsync":
                    self.assertEqual(temporary, [])
                else:
                    self.assertEqual(fixture.current(output)["note"], fixture.current(previous)["note"])
                    self.assertEqual(len(temporary), 1)
                    self.assertEqual(temporary[0].read_bytes(), output.read_bytes())
                    # Prove the completed file is accepted by an unmodified actual CLI.
                    fixture.review(previous=output, out=fixture.case / "received-complete.csv")


if __name__ == "__main__":
    before = {str(p.relative_to(base.SOURCE)): base.sha(p) for p in (base.SOURCE / "uwatch").glob("*.py")}
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=base.REPO, text=True).strip()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PublicationReceiving))
    after = {str(p.relative_to(base.SOURCE)): base.sha(p) for p in (base.SOURCE / "uwatch").glob("*.py")}
    receipt = {"source": str(base.SOURCE), "commit": commit, "source_sha256": before,
        "source_unchanged_during_review": before == after, "synthetic_inputs_only": True,
        "actual_cli_invocations": len(base.EXECUTIONS), "controlled_fault_cases": 8,
        "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "successful": result.wasSuccessful(), "executions": base.EXECUTIONS,
        "boundary": "Actual CLI and original checker/combiner/link. Only synthetic foreign writer or selected I/O fault injected; stable source export required."}
    (base.RUN / "publication-receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    print("RECEIPT", base.RUN / "publication-receipt.json")
    sys.exit(0 if result.wasSuccessful() and before == after else 1)
