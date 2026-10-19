"""Receiving tests for the sample-site builder; uses only unittest and stdlib.

Run: python -m unittest discover -s scripts -p test_build_pages.py -v
The build's pytest gates are observed but skipped inside these focused tests;
the report generators are real child processes on copied bundled sample data.
"""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sample_site_builder", SOURCE / "scripts/build_pages.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


class BuildPagesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.docs = self.root / "docs"
        for folder, module in (("freight_packets", "freightpkt"), ("pt_auth", "ptauth"),
                               ("utility_watch", "uwatch")):
            for child in (module, "sample_data"):
                shutil.copytree(SOURCE / folder / child, self.root / folder / child,
                                ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("freight", "pt", "utility"):
            (self.docs / name).mkdir(parents=True)
            (self.docs / name / "previous.html").write_bytes(("old " + name).encode())
        (self.docs / "index.html").write_bytes(b"old index")
        (self.docs / ".nojekyll").write_bytes(b"old marker")
        (self.docs / "independent-evidence").mkdir()
        (self.docs / "independent-evidence/receipt.txt").write_bytes(b"preserve receipt")
        self.before = snapshot(self.docs)
        self.calls = []

    def run_child(self, args, cwd):
        self.calls.append((list(args), cwd.name))
        if args[:2] == ["-m", "pytest"]:
            return
        return subprocess.run([sys.executable, *args], cwd=cwd, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def build(self, run=None):
        with patch.object(builder, "ROOT", self.root), patch.object(builder, "DOCS", self.docs), \
                patch.object(builder, "run", side_effect=run or self.run_child), redirect_stdout(io.StringIO()):
            builder.main()

    def assert_preserved(self):
        self.assertEqual(snapshot(self.docs), self.before)

    def test_final_native_generator_failure_preserves_every_previous_file(self):
        def run(args, cwd):
            if cwd.name == "utility_watch" and "--out" in args:
                account_file = cwd / "sample_data/accounts.csv"
                text = account_file.read_text()
                account_file.write_text(text + text.splitlines()[1] + "\n")
            self.run_child(args, cwd)
        with self.assertRaises(subprocess.CalledProcessError) as raised:
            self.build(run)
        self.assertEqual(raised.exception.returncode, 2)
        self.assertIn(b"duplicate account_no", raised.exception.stderr)
        self.assertEqual(len(self.calls), 6)
        self.assert_preserved()
        self.assertEqual(list(self.root.glob(".workflow-checks-build-*")), [])

    def test_test_gate_failure_stops_before_generating_or_replacing(self):
        def run(args, cwd):
            self.calls.append((list(args), cwd.name))
            raise subprocess.CalledProcessError(7, args)
        with self.assertRaises(subprocess.CalledProcessError):
            self.build(run)
        self.assertEqual(len(self.calls), 1)
        self.assert_preserved()
        self.assertEqual(list(self.root.glob(".workflow-checks-build-*")), [])

    def test_index_rendering_failure_preserves_every_previous_file(self):
        with patch.object(builder, "write_index", side_effect=ValueError("unreadable summary")):
            with self.assertRaisesRegex(ValueError, "unreadable summary"):
                self.build()
        self.assertEqual(len(self.calls), 6)
        self.assert_preserved()
        self.assertEqual(list(self.root.glob(".workflow-checks-build-*")), [])

    def test_success_publishes_real_reports_and_keeps_unrelated_docs(self):
        self.build()
        after = snapshot(self.docs)
        self.assertEqual(self.calls[:3], [(["-m", "pytest", "-q"], folder)
                                         for folder in ("freight_packets", "pt_auth", "utility_watch")])
        for name in ("freight", "pt", "utility"):
            self.assertNotIn(name + "/previous.html", after)
            self.assertIn(name + "/summary.json", after)
        self.assertIn("pt/digest.html", after)
        self.assertIn("utility/report.html", after)
        self.assertTrue(any(p.startswith("freight/packets/") and p.endswith(".html") for p in after))
        self.assertEqual(after["independent-evidence/receipt.txt"], b"preserve receipt")
        self.assertEqual(after[".nojekyll"], b"")
        index = after["index.html"].decode()
        self.assertIn("Synthetic data", index)
        self.assertIn("href='freight/invoice_flags.csv'", index)
        self.assertNotIn(".workflow-checks-build-", index)
        self.assertNotIn(str(self.root), index)
        self.assertEqual(list(self.root.glob(".workflow-checks-build-*")), [])

    def test_first_build_succeeds_without_docs_directory(self):
        shutil.rmtree(self.docs)
        self.build()
        self.assertTrue((self.docs / "index.html").is_file())
        self.assertTrue((self.docs / "freight/summary.json").is_file())

    def test_late_rename_failure_restores_every_previous_entry(self):
        original_replace = Path.replace
        def replace(path, target):
            if path.name == "index.html" and path.parent.name == "site":
                raise PermissionError("injected late destination failure")
            return original_replace(path, target)
        with patch.object(Path, "replace", new=replace):
            with self.assertRaisesRegex(PermissionError, "late destination failure"):
                self.build()
        self.assert_preserved()
        self.assertEqual(list(self.root.glob(".workflow-checks-build-*")), [])

    def test_failed_rollback_keeps_original_bytes_in_named_recovery_directory(self):
        original_replace = Path.replace
        def replace(path, target):
            if path.name == "index.html" and path.parent.name == "site":
                raise PermissionError("publication blocked")
            if path.name == "utility" and path.parent.name == "previous":
                raise PermissionError("rollback blocked")
            return original_replace(path, target)
        with patch.object(Path, "replace", new=replace):
            with self.assertRaises(builder.PublicationRecoveryError) as raised:
                self.build()
        retained = list(self.root.glob(".workflow-checks-build-*"))
        self.assertEqual(len(retained), 1)
        self.assertIn(str(retained[0]), str(raised.exception))
        self.assertEqual((retained[0] / "previous/utility/previous.html").read_bytes(), b"old utility")
        self.assertEqual((self.docs / "freight/previous.html").read_bytes(), b"old freight")
        self.assertEqual((self.docs / "pt/previous.html").read_bytes(), b"old pt")
        self.assertEqual((self.docs / "index.html").read_bytes(), b"old index")
        self.assertEqual((self.docs / "independent-evidence/receipt.txt").read_bytes(), b"preserve receipt")


if __name__ == "__main__":
    unittest.main()
