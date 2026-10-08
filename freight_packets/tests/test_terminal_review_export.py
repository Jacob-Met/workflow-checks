"""Native saved-source and delivery controls for the canonical terminal caller."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from freightpkt import terminal_review_export as terminal
from freightpkt.batch_handoff import build_batch_bundle
from freightpkt.web import App


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(root):
    return {p.relative_to(root).as_posix(): {
        "sha256": sha(p.read_bytes()), "bytes": p.stat().st_size,
        "inode": p.stat().st_ino, "mtime_ns": p.stat().st_mtime_ns,
    } for p in sorted(root.rglob("*")) if p.is_file() and not p.is_symlink()}


def bodies(root):
    return {p.relative_to(root).as_posix(): base64.b64encode(p.read_bytes()).decode()
            for p in sorted(root.rglob("*")) if p.is_file() and not p.is_symlink()}


class TerminalReviewExportTests(unittest.TestCase):
    cli_records = []

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="freight-terminal-case-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.source = self.work / "saved"
        self.source.mkdir()
        (self.source / "packets").mkdir()
        self.received = self.work / "received"
        self.received.mkdir()
        self.destination = self.received / "handoff.zip"
        self.ids = ["load/A", "load?A", "stale", "clear", "unbound", "unreviewed"]
        packets = []
        for number, load_id in enumerate(self.ids):
            name = f"packets/opaque-{number}.html"
            (self.source / name).write_bytes(
                f'<html><p>Retained synthetic packet {number}: {load_id}</p></html>\n'.encode())
            packets.append({"load_id": load_id, "file": name})
        summary = {"packets": packets, "stops": [], "flags": [], "fines": [],
                   "settlements": [], "exceptions": [], "unrelated": "retained source metadata"}
        self.write_json("summary.json", summary)
        versions = self.app().summary()["evidence_versions"]
        previous = {"decision": "reject", "note": "historical <literal> & café",
                    "at": "2026-10-01T12:00:00+00:00", "evidence_version": "0" * 64}
        decisions = {}
        for number, (load_id, decision) in enumerate(zip(self.ids, ("approve", "adjust", "reject", "clear"))):
            decisions[load_id] = {"decision": decision, "note": f'Note {number}\nKeep "quotes" & <text>.',
                                  "at": "2026-10-02T12:00:00+00:00", "history": [previous],
                                  "evidence_version": "0" * 64 if load_id == "stale" else versions[load_id]}
        decisions["unbound"] = {"decision": "approve", "note": "Old unbound record", "history": []}
        self.write_json("decisions.json", decisions)

    def app(self):
        return App(self.work / "unavailable-original-inputs", self.source)

    def write_json(self, name, value):
        (self.source / name).write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    def native(self, ids):
        app = self.app()
        view = app.summary()
        bundles = []
        for load_id in sorted(ids):
            row = {"load_id": load_id, "evidence_version": view["evidence_versions"][load_id],
                   "review_version": view["review_versions"][load_id]}
            filename, content = app.review_bundle(load_id, row["evidence_version"], row["review_version"])
            bundles.append((row, filename, content))
        return bundles, build_batch_bundle(bundles)

    def cli(self, ids=None, destination=None, *, stdout_full=False, file_limit=None):
        ids = self.ids[:2] if ids is None else ids
        destination = self.destination if destination is None else destination
        code = Path(__file__).resolve().parents[1]
        source_before, code_before = snapshot(self.source), snapshot(code)
        fixture = bodies(self.source)
        command = [sys.executable, "-B", "-m", "freightpkt", "export-reviews", "--out", str(self.source)]
        for load_id in ids:
            command.extend(("--load", load_id))
        command.extend(("--destination", str(destination)))
        options = {}
        sink = None
        if stdout_full:
            sink = open("/dev/full", "wb")
            self.addCleanup(sink.close)
            options["stdout"] = sink
        else:
            options["stdout"] = subprocess.PIPE
        if file_limit is not None:
            def restrict():
                import resource
                import signal
                signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
                resource.setrlimit(resource.RLIMIT_FSIZE, (file_limit, file_limit))
            options["preexec_fn"] = restrict
        result = subprocess.run(command, cwd=code, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
                               "PYTHONPATH": str(code)}, stderr=subprocess.PIPE, timeout=30, **options)
        after = snapshot(self.source)
        archive = destination.read_bytes() if destination.is_file() and not destination.is_symlink() else None
        self.cli_records.append({"test": self.id(), "argv": command, "returncode": result.returncode,
                                 "stdout": None if result.stdout is None else result.stdout.decode(),
                                 "stderr": result.stderr.decode(), "stdout_full": stdout_full,
                                 "file_limit": file_limit, "fixture_base64": fixture,
                                 "source_before": source_before, "source_after": after,
                                 "code_preserved": code_before == snapshot(code),
                                 "archive_base64": None if archive is None else base64.b64encode(archive).decode()})
        self.assertEqual(source_before, after)
        self.assertEqual(code_before, snapshot(code))
        self.assertFalse(list(self.received.glob(".freight-reviews-*")))
        self.assertNotIn(b"Traceback", result.stderr)
        return result

    def refuse(self, result):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertFalse(os.path.lexists(self.destination))

    def test_exact_native_archive_all_saved_states_and_literal_set_order(self):
        bundles, (filename, expected) = self.native(self.ids)
        result = self.cli(list(reversed(self.ids)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.destination.read_bytes(), expected)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt, {
            "schema": "freight-review-terminal-export.v1", "count": len(self.ids),
            "destination": str(self.destination.resolve()), "archive_filename": filename,
            "archive_bytes": len(expected), "archive_sha256": sha(expected),
            "source_summary_sha256": sha((self.source / "summary.json").read_bytes()),
            "source_decisions_sha256": sha((self.source / "decisions.json").read_bytes()),
            "identities": [row for row, _, _ in bundles],
        })
        self.assertEqual(result.stdout, (json.dumps(receipt, ensure_ascii=True, sort_keys=True,
                         indent=2, allow_nan=False) + "\n").encode())
        with zipfile.ZipFile(io.BytesIO(expected)) as archive:
            self.assertEqual(len(archive.namelist()), 6 * len(self.ids) + 2)
            for index, (_, _, raw) in enumerate(bundles, 1):
                prefix = f"loads/{index:04d}/"
                self.assertEqual(archive.read(prefix + "review.zip"), raw)
                with zipfile.ZipFile(io.BytesIO(raw)) as native:
                    for name in native.namelist():
                        self.assertEqual(archive.read(prefix + name), native.read(name))
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual([row["review_state"] for row in manifest["loads"]],
                             ["cleared", "current", "current", "stale", "unbound", None])
            self.assertNotIn("source_summary_sha256", manifest)
        other = self.received / "again.zip"
        repeated = self.cli(self.ids, other)
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(other.read_bytes(), expected)

    def test_absent_decisions_are_null_without_initializing_source(self):
        (self.source / "decisions.json").unlink()
        result = self.cli(["unreviewed"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(json.loads(result.stdout)["source_decisions_sha256"])
        self.assertFalse((self.source / "decisions.json").exists())
        self.assertFalse((self.work / "unavailable-original-inputs").exists())

    def test_selection_admission_refuses_whole_request(self):
        for selected in ([], [""], [self.ids[0], self.ids[0]], [self.ids[0], "zz-missing"],
                         [f"L{number}" for number in range(101)]):
            with self.subTest(selected=selected[:3], count=len(selected)):
                self.refuse(self.cli(selected))

    def test_malformed_saved_json_refuses_without_receipt_or_archive(self):
        original = (self.source / "summary.json").read_bytes()
        for raw in (b'{"packets":[],"packets":[]}', b'[]', b'{"packets":[],"x":NaN}',
                    b'{"packets":[],"x":1e999}', b'{"packets":['):
            with self.subTest(raw=raw):
                (self.source / "summary.json").write_bytes(raw)
                self.refuse(self.cli())
        (self.source / "summary.json").write_bytes(original)
        self.write_json("decisions.json", {self.ids[0]: None})
        self.refuse(self.cli())

    def test_missing_or_ambiguous_later_packet_refuses(self):
        original = (self.source / "summary.json").read_bytes()
        (self.source / "packets/opaque-1.html").unlink()
        self.refuse(self.cli())
        (self.source / "packets/opaque-1.html").write_bytes(b"restored fixture packet")
        summary = json.loads(original)
        summary["packets"].append(dict(summary["packets"][1]))
        self.write_json("summary.json", summary)
        self.refuse(self.cli())

    def test_malformed_native_report_row_refuses_and_empty_report_is_valid(self):
        shutil.rmtree(self.source)
        (self.source / "packets").mkdir(parents=True)
        raw = b'{"packets":[{"load_id":"A","file":"packets/a.html"}],"flags":[null]}\n'
        (self.source / "summary.json").write_bytes(raw)
        (self.source / "packets/a.html").write_bytes(b"<html>synthetic shape control</html>\n")
        self.refuse(self.cli(["A"]))
        self.assertEqual((self.source / "summary.json").read_bytes(), raw)
        (self.source / "summary.json").write_bytes(raw.replace(b"[null]", b"[]"))
        _, (_, expected) = self.native(["A"])
        result = self.cli(["A"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.destination.read_bytes(), expected)

    def test_packet_mapping_cannot_escape_capture_or_overwrite_summary(self):
        original = json.loads((self.source / "summary.json").read_bytes())
        outside = self.work / "outside.html"
        outside.write_bytes(b"outside sentinel")
        for name in ("../outside.html", str(outside), "summary.json", "decisions.json"):
            with self.subTest(name=name):
                summary = json.loads(json.dumps(original))
                summary["packets"][1]["file"] = name
                self.write_json("summary.json", summary)
                self.refuse(self.cli())
        self.assertEqual(outside.read_bytes(), b"outside sentinel")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unavailable")
    def test_source_symlink_outside_and_destination_symlink_are_preserved(self):
        packet = self.source / "packets/opaque-0.html"
        old = packet.read_bytes()
        outside = self.work / "outside.html"
        outside.write_bytes(old)
        packet.unlink()
        packet.symlink_to(outside)
        self.refuse(self.cli())
        packet.unlink()
        packet.write_bytes(old)
        self.destination.symlink_to(packet)
        result = self.cli()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertTrue(self.destination.is_symlink())
        self.assertEqual(outside.read_bytes(), old)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO unavailable")
    def test_nonregular_source_refuses_without_blocking(self):
        packet = self.source / "packets/opaque-0.html"
        packet.unlink()
        os.mkfifo(packet)
        self.refuse(self.cli())

    def test_no_clobber_and_outside_source_destination_admission(self):
        self.destination.write_bytes(b"existing destination")
        before = self.destination.stat()
        result = self.cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.destination.read_bytes(), b"existing destination")
        self.assertEqual(self.destination.stat().st_ino, before.st_ino)
        self.destination.unlink()
        result = self.cli(destination=self.source / "new.zip")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.source / "new.zip").exists())
        result = self.cli(destination=self.received / "absent-parent" / "new.zip")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.received / "absent-parent").exists())

    @unittest.skipUnless(sys.platform.startswith("linux") and Path("/dev/full").exists(), "Linux /dev/full")
    def test_receipt_failure_preserves_delivered_archive_and_retry_refuses(self):
        _, (_, expected) = self.native(self.ids[:2])
        result = self.cli(stdout_full=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(b"archive published", result.stderr)
        self.assertEqual(self.destination.read_bytes(), expected)
        before = self.destination.stat()
        retry = self.cli()
        self.assertEqual(retry.returncode, 2)
        self.assertEqual(self.destination.read_bytes(), expected)
        self.assertEqual(self.destination.stat().st_ino, before.st_ino)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux resource limit")
    def test_real_kernel_stage_write_failure_has_no_publication(self):
        self.assertTrue(all(row["bytes"] < 4096 for row in snapshot(self.source).values()))
        _, (_, expected) = self.native(self.ids)
        self.assertGreater(len(expected), 4096)
        self.refuse(self.cli(self.ids, file_limit=4096))

    def test_observed_source_change_after_canonical_assembly_refuses(self):
        packet = self.source / "packets/opaque-0.html"
        original = packet.read_bytes()
        def interleave(bundles):
            result = build_batch_bundle(bundles)
            packet.write_bytes(original + b"changed after capture")
            return result
        with patch.object(terminal, "build_batch_bundle", interleave):
            with self.assertRaisesRegex(ValueError, "source changed"):
                terminal.export_reviews(self.source, self.ids[:2], self.destination)
        self.assertEqual(packet.read_bytes(), original + b"changed after capture")
        self.assertFalse(self.destination.exists())
        self.assertFalse(list(self.received.glob(".freight-reviews-*")))

    def test_read_only_native_methods_and_caller_limits(self):
        before = snapshot(self.source)
        summary_size = (self.source / "summary.json").stat().st_size
        packet_size = (self.source / "packets/opaque-0.html").stat().st_size
        for option, limit in (("MAX_JSON_BYTES", summary_size - 1),
                              ("MAX_PACKET_BYTES", packet_size - 1),
                              ("MAX_INPUT_BYTES", summary_size), ("MAX_OUTPUT_BYTES", 1),
                              ("MAX_ARCHIVE_BYTES", 1)):
            with self.subTest(option=option), patch.object(terminal, option, limit):
                with self.assertRaises(ValueError):
                    terminal.export_reviews(self.source, [self.ids[0]], self.destination)
                self.assertFalse(self.destination.exists())
        with patch.object(App, "decide", side_effect=AssertionError("unexpected decision")), \
                patch.object(App, "rerun", side_effect=AssertionError("unexpected generation")), \
                patch.object(App, "regenerate", side_effect=AssertionError("unexpected generation")):
            result = terminal.export_reviews(self.source, [self.ids[0]], self.destination)
        self.assertEqual(result["count"], 1)
        self.assertEqual(before, snapshot(self.source))

    def test_exact_load_count_limit_accepts_one_hundred(self):
        packets = []
        ids = [f"L{number:03d}" for number in range(100)]
        for number, load_id in enumerate(ids):
            name = f"packets/limit-{number}.html"
            (self.source / name).write_bytes(f"synthetic packet {number}".encode())
            packets.append({"load_id": load_id, "file": name})
        self.write_json("summary.json", {"packets": packets})
        (self.source / "decisions.json").unlink()
        result = terminal.export_reviews(self.source, ids, self.destination)
        self.assertEqual(result["count"], 100)
        with zipfile.ZipFile(self.destination) as archive:
            self.assertEqual(len(archive.namelist()), 602)
        self.assertFalse(list(self.received.glob(".freight-reviews-*")))


if __name__ == "__main__":
    unittest.main()
