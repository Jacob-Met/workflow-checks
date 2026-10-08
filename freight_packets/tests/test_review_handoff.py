"""Native HTTP receiving for the selected-load review handoff."""
from __future__ import annotations
import hashlib
import io
import json
import tempfile
import threading
import unittest
import zipfile
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from freightpkt.pipeline import run
from freightpkt.synth import generate
from freightpkt.web import App, make_handler

SECTIONS = ("stops", "flags", "fines", "settlements", "exceptions", "packets")


class ReviewHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="freight-handoff-test-")
        self.root = Path(self.temp.name)
        self.data, self.out = self.root / "data", self.root / "out"
        generate(self.data, n_loads=24, seed=7)
        run(self.data, self.out)
        self.app = App(self.data, self.out)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=.01), daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.first = self.summary()
        self.selected, self.other = [p["load_id"] for p in self.first["packets"][:2]]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def request(self, route, body=None):
        req = Request(self.base + route, data=None if body is None else json.dumps(body).encode(),
                      headers={"Content-Type": "application/json"})
        try:
            response = urlopen(req, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, dict(response.headers), response.read()

    def summary(self):
        status, _, raw = self.request("/api/summary")
        self.assertEqual(status, 200)
        return json.loads(raw)

    def decide(self, load=None, decision="approve", note="selected review"):
        load = self.selected if load is None else load
        summary = self.summary()
        status, _, raw = self.request("/api/decision", {
            "load_id": load, "decision": decision, "note": note,
            "evidence_version": summary["evidence_versions"][load]})
        self.assertEqual(status, 200, raw)
        return self.summary()

    def bundle(self, summary=None, load=None, **overrides):
        summary = self.summary() if summary is None else summary
        load = self.selected if load is None else load
        fields = {"load_id": load, "evidence_version": summary["evidence_versions"].get(load, "0"*64),
                  "review_version": summary.get("review_versions", {}).get(load, "0"*64)}
        fields.update(overrides)
        return self.request("/api/review-bundle?" + urlencode(fields))

    def hashes(self):
        return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob("*") if p.is_file()}

    def unpack(self, summary, result):
        status, headers, raw = result
        self.assertEqual(status, 200, raw[:300])
        self.assertEqual(headers["Content-Type"], "application/zip")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertRegex(headers["Content-Disposition"], r'^attachment; filename="freight-review-[A-Za-z0-9_.-]+\.zip"$')
        self.assertEqual(int(headers["Content-Length"]), len(raw))
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertEqual(set(archive.namelist()),
                             {"index.html", "packet.html", "evidence.json", "review.json", "manifest.json"})
            files = {name: archive.read(name) for name in archive.namelist()}
        evidence = json.loads(files["evidence.json"])
        canonical = json.dumps(evidence, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"), allow_nan=False).encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), summary["evidence_versions"][self.selected])
        self.assertEqual(evidence["packet_sha256"], hashlib.sha256(files["packet.html"]).hexdigest())
        for section in SECTIONS:
            self.assertTrue(all(row["load_id"] == self.selected for row in evidence[section]))
            expected = sorted((row for row in summary[section] if row["load_id"] == self.selected),
                              key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
            self.assertEqual(evidence[section], expected)
        packet = next(row for row in summary["packets"] if row["load_id"] == self.selected)
        self.assertEqual(files["packet.html"], (self.out / packet["file"]).read_bytes())
        review = json.loads(files["review.json"])
        self.assertEqual(review["load_id"], self.selected)
        self.assertEqual(review["review"], summary["decisions"].get(self.selected))
        review_canonical = json.dumps(review["review"], sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=True, allow_nan=False).encode()
        self.assertEqual(hashlib.sha256(review_canonical).hexdigest(), summary["review_versions"][self.selected])
        self.assertEqual(review["evidence_version"], summary["evidence_versions"][self.selected])
        self.assertEqual(review["review_version"], summary["review_versions"][self.selected])
        manifest = json.loads(files["manifest.json"])
        self.assertEqual(manifest["load_id"], self.selected)
        self.assertEqual(manifest["review_version"], review["review_version"])
        self.assertEqual(manifest["evidence_version"], review["evidence_version"])
        self.assertEqual({row["path"] for row in manifest["files"]}, set(files) - {"manifest.json"})
        for row in manifest["files"]:
            self.assertEqual(row["bytes"], len(files[row["path"]]))
            self.assertEqual(row["sha256"], hashlib.sha256(files[row["path"]]).hexdigest())
        files["index.html"].decode("utf-8")
        return files

    def test_unreviewed_native_handoff_is_complete_and_read_only(self):
        before = self.hashes()
        files = self.unpack(self.first, self.bundle(self.first))
        self.assertIn(b"Not reviewed", files["index.html"])
        self.assertIsNone(json.loads(files["review.json"])["review"])
        self.assertEqual(self.hashes(), before)

    def test_only_selected_saved_review_and_history_are_included(self):
        self.decide(self.other, note="OTHER-LOAD-PRIVATE-NOTE")
        self.decide(note="first selected note")
        summary = self.decide(decision="adjust", note="second selected note")
        before = self.hashes()
        files = self.unpack(summary, self.bundle(summary))
        for raw in files.values():
            self.assertNotIn(b"OTHER-LOAD-PRIVATE-NOTE", raw)
        review = json.loads(files["review.json"])["review"]
        self.assertEqual(review["history"][0]["note"], "first selected note")
        self.assertEqual(review["note"], "second selected note")
        self.assertIn(b"Current saved review: Needs adjust", files["index.html"])
        self.assertEqual(self.hashes(), before)

    def test_saved_review_change_refuses_old_view_without_touching_files(self):
        prior = self.decide(note="first")
        current = self.decide(note="new saved note")
        self.assertEqual(prior["evidence_versions"], current["evidence_versions"])
        before = self.hashes()
        status, headers, body = self.bundle(prior)
        self.assertEqual(status, 409)
        self.assertIn(b"saved review changed", body)
        self.assertNotIn("Content-Disposition", headers)
        self.assertEqual(self.hashes(), before)
        self.unpack(current, self.bundle(current))

    def test_changed_packet_refuses_old_view_and_preserves_stale_review(self):
        prior = self.decide()
        packet = self.out / prior["packets"][0]["file"]
        packet.write_bytes(packet.read_bytes() + b"\n<!-- authored changed evidence -->\n")
        current = self.summary()
        self.assertEqual(current["decisions"][self.selected]["review_state"], "stale")
        before = self.hashes()
        self.assertEqual(self.bundle(prior)[0], 409)
        files = self.unpack(current, self.bundle(current))
        self.assertIn("Previous review — review again", files["index.html"].decode())
        self.assertNotIn(b"Current saved review: Approve", files["index.html"])
        self.assertEqual(self.hashes(), before)

    def test_each_native_report_section_is_part_of_the_fence(self):
        original = (self.out / "summary.json").read_bytes()
        prior = self.summary()
        for section in SECTIONS:
            with self.subTest(section=section):
                obj = json.loads(original)
                row = next((row for row in obj[section] if row["load_id"] == self.selected), None)
                if row is None:
                    obj[section].append({"load_id": self.selected, "authored_review_marker": section})
                else:
                    row["authored_review_marker"] = section
                (self.out / "summary.json").write_text(json.dumps(obj))
                self.assertEqual(self.bundle(prior)[0], 409)
                current = self.summary()
                self.unpack(current, self.bundle(current))
                (self.out / "summary.json").write_bytes(original)

    def test_other_load_changes_do_not_change_selected_bundle(self):
        prior = self.decide()
        before = self.bundle(prior)
        self.decide(self.other, decision="reject", note="other note")
        other_packet = next(row for row in prior["packets"] if row["load_id"] == self.other)
        path = self.out / other_packet["file"]
        path.write_bytes(path.read_bytes() + b"\n<!-- other changed -->")
        obj = json.loads((self.out / "summary.json").read_bytes())
        obj["generated_at"] = "unrelated later run metadata"
        for row in obj["stops"]:
            if row["load_id"] == self.other:
                row["authored_other_marker"] = "ONLY-OTHER-LOAD"
        (self.out / "summary.json").write_text(json.dumps(obj))
        current = self.summary()
        self.assertEqual(self.bundle(current)[2], before[2])
        self.assertEqual(self.bundle(prior)[2], before[2])

    def test_cleared_and_legacy_unbound_review_remain_distinct(self):
        self.decide()
        cleared = self.decide(decision="clear")
        files = self.unpack(cleared, self.bundle(cleared))
        self.assertIn(b"Saved review cleared", files["index.html"])
        self.app.decisions_path.write_text(json.dumps({self.selected: {
            "decision": "approve", "note": "legacy unbound", "at": "2026-10-01", "history": []}}))
        unbound = self.summary()
        self.assertEqual(unbound["decisions"][self.selected]["review_state"], "unbound")
        files = self.unpack(unbound, self.bundle(unbound))
        self.assertIn(b"Previous review has no evidence binding", files["index.html"])
        self.assertNotIn(b"Current saved review: Approve", files["index.html"])

    def test_unicode_hostile_and_escaped_surrogate_note_roundtrip(self):
        note = 'café 日本語 <script>window.injected=true</script> & "quoted" ' + chr(0xD800)
        summary = self.decide(note=note)
        files = self.unpack(summary, self.bundle(summary))
        self.assertEqual(json.loads(files["review.json"])["review"]["note"], note)
        cover = files["index.html"].decode("utf-8")
        self.assertNotIn("<script>", cover)
        self.assertIn("&lt;script&gt;", cover)
        self.assertIn("café 日本語", cover)
        self.assertIn(r"\ud800", cover)

    def test_missing_generated_summary_does_not_initialize_or_write(self):
        summary = self.decide()
        (self.out / "summary.json").unlink()
        before = self.hashes()
        status, headers, raw = self.bundle(summary)
        self.assertEqual(status, 404, raw[:200])
        self.assertNotIn("Content-Disposition", headers)
        self.assertEqual(self.hashes(), before)

    def test_missing_packet_and_unknown_load_return_no_download(self):
        summary = self.decide()
        path = self.out / summary["packets"][0]["file"]
        path.unlink()
        before = self.hashes()
        for result in [self.bundle(summary), self.bundle(summary, load="not-present")]:
            self.assertEqual(result[0], 404)
            self.assertNotIn("Content-Disposition", result[1])
        self.assertEqual(self.hashes(), before)

    def test_missing_duplicate_and_invalid_versions_are_refused(self):
        summary = self.decide()
        fields = {"load_id": self.selected, "evidence_version": summary["evidence_versions"][self.selected],
                  "review_version": summary["review_versions"][self.selected]}
        before = self.hashes()
        for field in fields:
            for query in [urlencode({k: v for k, v in fields.items() if k != field}),
                          urlencode({**fields, field: ""}), urlencode(fields) + "&" + urlencode({field: fields[field]})]:
                with self.subTest(field=field, query=query):
                    status, headers, _ = self.request("/api/review-bundle?" + query)
                    self.assertEqual(status, 400)
                    self.assertNotIn("Content-Disposition", headers)
        for field in ("evidence_version", "review_version"):
            self.assertEqual(self.bundle(summary, **{field: "g"*64})[0], 400)
        self.assertEqual(self.hashes(), before)

    def test_bundle_serialization_failure_is_not_a_download_or_a_write(self):
        summary = self.decide()
        before = self.hashes()
        with patch("freightpkt.web.build_bundle", side_effect=OSError("authored output failure")):
            status, headers, _ = self.bundle(summary)
        self.assertEqual(status, 500)
        self.assertNotIn("Content-Disposition", headers)
        self.assertEqual(self.hashes(), before)

    def test_native_lock_keeps_download_and_later_review_as_separate_snapshots(self):
        import freightpkt.web as web
        summary = self.decide(note="snapshot before")
        entered, release, decision_started = threading.Event(), threading.Event(), threading.Event()
        original = web.build_bundle
        def held(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(5))
            return original(*args, **kwargs)
        def later_review():
            decision_started.set()
            return self.request("/api/decision", {"load_id": self.selected, "decision": "reject",
                "note": "snapshot after", "evidence_version": summary["evidence_versions"][self.selected]})
        with ThreadPoolExecutor(max_workers=2) as pool, patch("freightpkt.web.build_bundle", side_effect=held):
            download = pool.submit(self.bundle, summary)
            self.assertTrue(entered.wait(5))
            decision = pool.submit(later_review)
            self.assertTrue(decision_started.wait(5))
            self.assertFalse(decision.done())
            release.set()
            result = download.result(timeout=5)
            self.assertEqual(decision.result(timeout=5)[0], 200)
        files = self.unpack(summary, result)
        self.assertEqual(json.loads(files["review.json"])["review"]["note"], "snapshot before")
        current = self.summary()
        self.assertEqual(current["decisions"][self.selected]["note"], "snapshot after")
        self.assertEqual(self.bundle(summary)[0], 409)


if __name__ == "__main__":
    unittest.main()

