"""Authored saved-copy comparisons through the unchanged native bundle producer."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from freightpkt.handoff import build_bundle, review_version
from freightpkt import review_compare as compare


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def native(lid="SYN-COMPARE", *, stops=None, flags=None, saved=None, packet=b"<p>Authored packet</p>"):
    evidence = {"schema": "freight-review.v1", "packet_sha256": hashlib.sha256(packet).hexdigest(),
                **{name: [] for name in compare.SECTIONS}}
    evidence["stops"] = copy.deepcopy(stops or [])
    evidence["flags"] = copy.deepcopy(flags or [])
    evidence["packets"] = [{"load_id": lid, "file": "packets/retained-native-name.html"}]
    version = hashlib.sha256(canonical(evidence)).hexdigest()
    saved = copy.deepcopy(saved)
    if saved is not None:
        saved.setdefault("evidence_version", version)
    return build_bundle(lid, packet, evidence, saved, version, review_version(saved))


def members(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def pack(files, *, rebind=True):
    files = dict(files)
    manifest = json.loads(files["manifest.json"])
    if rebind:
        manifest["files"] = [{"path": name, "bytes": len(files[name]),
                              "sha256": hashlib.sha256(files[name]).hexdigest()}
                             for name in compare.MEMBERS[:-1]]
        files["manifest.json"] = json.dumps(manifest).encode()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    return stream.getvalue()


def change_json(raw, name, change, *, rebind=True):
    files = members(raw)
    value = json.loads(files[name])
    change(value)
    files[name] = json.dumps(value, ensure_ascii=True).encode()
    return pack(files, rebind=rebind)


class ReviewComparisonTests(unittest.TestCase):
    def call(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = compare.main(list(map(str, args)))
            except SystemExit as error:
                rc = error.code
        return rc, out.getvalue(), err.getvalue()

    def test_same_copy_and_changed_departure_preserve_stale_review(self):
        old = {"load_id": "SYN-COMPARE", "stop": 1, "departure": "2026-10-01T12:30:00-05:00",
               "evidence": ["tracking.csv:row7"]}
        review = {"decision": "approve", "review_state": "current", "note": "Authored note",
                  "at": "2026-10-02T09:00:00Z", "history": []}
        a = compare.decode_bundle(native(stops=[old], saved=review), "Copy A.zip")
        same = compare.decode_bundle(native(stops=[old], saved=review), "Copy A again.zip")
        self.assertEqual(a.zip_sha256, same.zip_sha256)
        for section in compare.SECTIONS:
            result = compare.record_changes(a.evidence[section], same.evidence[section])
            self.assertEqual(result["only_a"], [])
            self.assertEqual(result["only_b"], [])
        new = {**old, "departure": "2026-10-01T14:00:00-05:00"}
        stale = {**a.review["review"], "review_state": "stale"}
        b = compare.decode_bundle(native(stops=[new], saved=stale,
                                         packet=b"<p>Changed authored departure</p>"), "Copy B.zip")
        result = compare.record_changes(a.evidence["stops"], b.evidence["stops"])
        self.assertEqual(result["only_a"], [{"record": old, "count": 1}])
        self.assertEqual(result["only_b"], [{"record": new, "count": 1}])
        report = compare.render_comparison(a, b)
        self.assertIn("tracking.csv:row7", report)
        self.assertIn("12:30:00-05:00", report)
        self.assertIn("14:00:00-05:00", report)
        self.assertIn("&quot;stale&quot;", report)
        self.assertIn(a.review["review"]["evidence_version"], report)
        self.assertIn("establishes no current approval", report)

    def test_multiplicity_and_json_type_distinctions(self):
        duplicate = {"load_id": "SYN-COMPARE", "stop": 7, "source": "tracking.csv:row9"}
        literal = {"load_id": "SYN-COMPARE", "stop": "Warehouse Δ <North>"}
        flags = [{"load_id": "SYN-COMPARE", "amount": value} for value in (0, False, None)]
        a = compare.decode_bundle(native(stops=[duplicate, duplicate, duplicate, literal], flags=flags))
        b = compare.decode_bundle(native(stops=[duplicate, literal], flags=flags))
        result = compare.record_changes(a.evidence["stops"], b.evidence["stops"])
        self.assertEqual(result["only_a"], [{"record": duplicate, "count": 2}])
        self.assertEqual(result["only_b"], [])
        self.assertEqual(sum(row["count"] for row in result["unchanged"]), 2)
        flags_result = compare.record_changes(a.evidence["flags"], b.evidence["flags"])
        self.assertEqual(len(flags_result["unchanged"]), 3)
        self.assertEqual({type(row["record"]["amount"]) for row in flags_result["unchanged"]},
                         {int, bool, type(None)})
        reverse = compare.record_changes(b.evidence["stops"], a.evidence["stops"])
        self.assertEqual(reverse["only_b"], result["only_a"])
        self.assertEqual(reverse["only_a"], [])

    def test_literal_text_unknown_fields_and_history_never_become_markup(self):
        text = 'café 日本語 <script>alert("literal")</script> & \nsecond line'
        row = {"load_id": "SYN-COMPARE", "detail": text,
               "opaque": {"null": None, "false": False, "zero": 0, "items": ["x", "y"]}}
        saved = {"decision": "adjust", "review_state": "unbound", "note": text + chr(0xD800),
                 "history": [{"decision": "reject", "note": 'Old <img onerror="literal"> note',
                              "opaque": [None, False, 0]}]}
        raw = native(flags=[row], saved=saved,
                     packet=b'<script>globalThis.PACKET_MUST_NOT_RUN=true</script>')
        a = compare.decode_bundle(raw, '<img src="source">.zip')
        self.assertEqual(a.evidence["flags"], [row])
        self.assertEqual(a.review["review"]["note"], saved["note"])
        report = compare.render_comparison(a, a)
        self.assertNotIn("<script", report.lower())
        self.assertNotIn('<img src="source">', report)
        self.assertNotIn("PACKET_MUST_NOT_RUN", report)
        self.assertIn("café 日本語", report)
        self.assertIn("&lt;script&gt;", report)
        self.assertIn("&lt;img", report)
        self.assertIn(r"\ud800", report)
        for literal in ('&quot;null&quot;: null', '&quot;false&quot;: false', '&quot;zero&quot;: 0'):
            self.assertIn(literal, report)

    def test_review_only_and_cover_only_changes_stay_separate(self):
        a = compare.decode_bundle(native(saved={"decision": "approve", "review_state": "current",
                                                 "note": "A", "history": []}))
        b = compare.decode_bundle(native(saved={"decision": "approve", "review_state": "current",
                                                 "note": "B", "history": []}))
        self.assertEqual(a.manifest["evidence_version"], b.manifest["evidence_version"])
        self.assertNotEqual(a.manifest["review_version"], b.manifest["review_version"])
        files = members(native())
        files["index.html"] += b"\n<!-- authored cover-only difference -->"
        cover = compare.decode_bundle(pack(files))
        plain = compare.decode_bundle(native())
        self.assertEqual(cover.manifest["evidence_version"], plain.manifest["evidence_version"])
        self.assertEqual(cover.manifest["review_version"], plain.manifest["review_version"])
        self.assertNotEqual(cover.zip_sha256, plain.zip_sha256)
        report = compare.render_comparison(plain, cover)
        self.assertIn("ZIP container or cover bytes can differ", report)
        self.assertIn("Changed bytes", report)
        self.assertNotIn("authored cover-only difference", report)

    def test_non_native_member_sets_and_corrupt_archives_are_refused(self):
        files = members(native())
        variants = [b"not a ZIP"]
        extra = dict(files); extra["unexpected.txt"] = b"extra"
        missing = dict(files); del missing["packet.html"]
        variants.extend((pack(extra, rebind=False), pack(missing, rebind=False)))
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            for name, value in files.items():
                archive.writestr(name, value)
            with self.assertWarns(UserWarning):
                archive.writestr("packet.html", files["packet.html"])
        variants.append(stream.getvalue())
        for raw in variants:
            with self.subTest(size=len(raw)), self.assertRaises(compare.BundleError):
                compare.decode_bundle(raw)

    def test_manifest_paths_sizes_and_hashes_are_required(self):
        raw = native()
        def replace_size(v): v["files"][0]["bytes"] = True
        def duplicate_path(v): v["files"][1]["path"] = v["files"][0]["path"]
        def wrong_hash(v): v["files"][0]["sha256"] = "0" * 64
        def missing_binding(v): v["files"].pop()
        for alter in (replace_size, duplicate_path, wrong_hash, missing_binding):
            with self.subTest(alter=alter.__name__), self.assertRaises(compare.BundleError):
                compare.decode_bundle(change_json(raw, "manifest.json", alter, rebind=False))
        files = members(raw); files["packet.html"] += b"not rebound"
        with self.assertRaises(compare.BundleError):
            compare.decode_bundle(pack(files, rebind=False))

    def test_rebound_files_cannot_bypass_native_content_identity(self):
        raw = native(saved={"decision": "approve", "review_state": "current", "history": []})
        variants = [
            change_json(raw, "evidence.json", lambda v: v.update(schema="freight-review.v2")),
            change_json(raw, "evidence.json", lambda v: v["packets"][0].update(file="different.html")),
            change_json(raw, "evidence.json", lambda v: v["packets"][0].update(load_id="OTHER")),
            change_json(raw, "review.json", lambda v: v.update(load_id="OTHER")),
            change_json(raw, "review.json", lambda v: v["review"].update(note="changed after token")),
            change_json(raw, "review.json", lambda v: v["review"].update(history=[42])),
        ]
        files = members(raw); files["packet.html"] += b"changed with manifest rebound"
        variants.append(pack(files))
        for i, changed in enumerate(variants):
            with self.subTest(case=i), self.assertRaises(compare.BundleError):
                compare.decode_bundle(changed)

    def test_duplicate_json_keys_nonfinite_values_and_bad_shapes_are_refused(self):
        raw = native()
        replacements = [
            ("evidence.json", b'{"schema":"freight-review.v1","schema":"freight-review.v1"}'),
            ("review.json", b'{"not_native":NaN}'),
            ("review.json", b"null"),
            ("manifest.json", b"[]"),
        ]
        for name, value in replacements:
            files = members(raw); files[name] = value
            changed = pack(files) if name != "manifest.json" else pack(files, rebind=False)
            with self.subTest(name=name, value=value), self.assertRaises(compare.BundleError):
                compare.decode_bundle(changed)

    def test_cli_checks_both_inputs_and_load_ids_before_any_output(self):
        with tempfile.TemporaryDirectory(prefix="freight-compare-") as directory:
            root = Path(directory)
            a, b, destination = root / "a.zip", root / "b.zip", root / "new.html"
            a.write_bytes(native()); b.write_bytes(b"bad second input")
            self.assertEqual(self.call(a, b, "--out", destination)[0], 2)
            self.assertFalse(destination.exists())
            b.write_bytes(native(lid="OTHER"))
            self.assertEqual(self.call(a, b, "--out", destination)[0], 2)
            self.assertFalse(destination.exists())
            b.write_bytes(native())
            with patch.object(compare, "render_comparison", side_effect=compare.BundleError("authored render refusal")):
                self.assertEqual(self.call(a, b, "--out", destination)[0], 2)
            self.assertFalse(destination.exists())
            with patch.object(compare, "render_comparison", side_effect=RuntimeError("authored program error")):
                with self.assertRaisesRegex(RuntimeError, "authored program error"):
                    self.call(a, b, "--out", destination)
            self.assertFalse(destination.exists())

    def test_cli_creates_complete_new_report_and_preserves_existing_bytes(self):
        with tempfile.TemporaryDirectory(prefix="freight-compare-") as directory:
            root = Path(directory)
            a, b, destination = root / "a.zip", root / "b.zip", root / "comparison.html"
            a.write_bytes(native()); b.write_bytes(native())
            before = {p: (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns) for p in (a, b)}
            rc, out, err = self.call(a, b, "--out", destination)
            self.assertEqual((rc, err), (0, ""))
            expected = compare.render_comparison(compare.read_bundle(a), compare.read_bundle(b)).encode()
            self.assertEqual(destination.read_bytes(), expected)
            self.assertTrue(out.startswith("Comparison written:"))
            saved = (destination.read_bytes(), destination.stat().st_ino, destination.stat().st_mtime_ns)
            self.assertEqual(self.call(b, a, "--out", destination)[0], 2)
            self.assertEqual((destination.read_bytes(), destination.stat().st_ino,
                              destination.stat().st_mtime_ns), saved)
            self.assertEqual({p: (p.read_bytes(), p.stat().st_ino, p.stat().st_mtime_ns) for p in (a, b)}, before)

    def test_output_failure_retains_partial_new_file_and_refuses_later_replacement(self):
        with tempfile.TemporaryDirectory(prefix="freight-compare-") as directory:
            root = Path(directory)
            a, b, destination = root / "a.zip", root / "b.zip", root / "partial.html"
            a.write_bytes(native()); b.write_bytes(native())
            original_open = Path.open
            class FailedWrite:
                def __enter__(self):
                    self.file = original_open(destination, "xb")
                    return self
                def write(self, content):
                    self.file.write(b"authored partial")
                    self.file.flush()
                    raise OSError("authored storage failure")
                def __exit__(self, *exc):
                    self.file.close()
            def intercept(path, mode="r", *args, **kwargs):
                if path == destination and mode == "xb":
                    return FailedWrite()
                return original_open(path, mode, *args, **kwargs)
            with patch.object(Path, "open", intercept):
                rc, _, err = self.call(a, b, "--out", destination)
            self.assertEqual(rc, 2)
            self.assertIn("authored storage failure", err)
            self.assertEqual(destination.read_bytes(), b"authored partial")
            self.assertEqual(self.call(a, b, "--out", destination)[0], 2)
            self.assertEqual(destination.read_bytes(), b"authored partial")

    def test_cli_help_and_argument_refusal_do_not_read_files(self):
        with patch.object(compare, "read_bundle", side_effect=AssertionError("must not read")):
            self.assertEqual(self.call("--help")[0], 0)
            self.assertEqual(self.call("a.zip", "b.zip")[0], 2)


if __name__ == "__main__":
    unittest.main()
