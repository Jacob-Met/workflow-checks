"""Native per-load-preserving batch handoff controls on authored synthetic files."""
from __future__ import annotations
import hashlib, io, json, tempfile, threading, unittest, urllib.error, urllib.request, zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from freightpkt.pipeline import run
from freightpkt.synth import generate
from freightpkt.web import App, make_handler

class BatchHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="freight-batch-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data, self.out = self.root / "data", self.root / "out"
        generate(self.data, n_loads=8, seed=7)
        run(self.data, self.out, run_by="batch-test")
        self.app = App(self.data, self.out)
        self.summary = self.app.summary()
        self.ids = [p["load_id"] for p in self.summary["packets"][:3]]
        self.assertEqual(len(self.ids), 3)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def request(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.server.server_port}" + path, data=data,
            headers={} if data is None else {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=5) as result:
                return result.status, dict(result.headers), result.read()
        except urllib.error.HTTPError as error:
            return error.code, dict(error.headers), error.read()

    def selection(self, ids=None):
        summary = self.app.summary()
        return [{"load_id": key, "evidence_version": summary["evidence_versions"][key],
                 "review_version": summary["review_versions"][key]}
                for key in (self.ids if ids is None else ids)]

    def hashes(self):
        return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for base in (self.data, self.out) for p in sorted(base.rglob("*")) if p.is_file()}

    def batch(self, selection=None):
        return self.request("/api/review-batch", {"loads": self.selection() if selection is None else selection})

    def test_public_batch_preserves_exact_single_load_members_and_zip(self):
        selection = self.selection(list(reversed(self.ids)))
        ordinary = [self.app.review_bundle(x["load_id"], x["evidence_version"], x["review_version"])
                    for x in selection]
        before = self.hashes()
        status, headers, raw = self.batch(selection)
        self.assertEqual(status, 200, raw)
        self.assertEqual(headers["Content-Type"], "application/zip")
        self.assertRegex(headers["Content-Disposition"], r'^attachment; filename="freight-review-batch-3-[0-9a-f]{12}\.zip"$')
        self.assertEqual(self.hashes(), before)
        with zipfile.ZipFile(io.BytesIO(raw)) as batch:
            manifest = json.loads(batch.read("manifest.json"))
            self.assertEqual([x["load_id"] for x in manifest["loads"]], [x["load_id"] for x in selection])
            self.assertEqual(len(batch.namelist()), 20)
            for position, (row, (filename, original)) in enumerate(zip(manifest["loads"], ordinary), 1):
                directory = f"loads/{position:04d}/"
                self.assertEqual(row["index_path"], directory + "index.html")
                self.assertEqual(row["bundle_path"], directory + "review.zip")
                self.assertEqual(row["bundle_filename"], filename)
                self.assertEqual(batch.read(row["bundle_path"]), original)
                with zipfile.ZipFile(io.BytesIO(original)) as single:
                    for name in single.namelist():
                        self.assertEqual(batch.read(directory + name), single.read(name))
                self.assertIn(row["index_path"], batch.read("index.html").decode())
            for record in manifest["files"]:
                content = batch.read(record["path"])
                self.assertEqual(record["bytes"], len(content))
                self.assertEqual(record["sha256"], hashlib.sha256(content).hexdigest())
            self.assertEqual({x["path"] for x in manifest["files"]}, set(batch.namelist()) - {"manifest.json"})
        self.assertEqual(self.batch(selection)[2], raw)

    def test_one_selected_load_is_supported_without_other_loads(self):
        status, _, raw = self.batch(self.selection([self.ids[1]]))
        self.assertEqual(status, 200, raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as batch:
            manifest = json.loads(batch.read("manifest.json"))
            self.assertEqual([row["load_id"] for row in manifest["loads"]], [self.ids[1]])
            self.assertEqual(len(batch.namelist()), 8)

    def test_later_changed_saved_review_refuses_whole_batch(self):
        selection = self.selection()
        self.app.decide({"load_id": self.ids[-1], "decision": "adjust", "note": "new saved note",
                         "evidence_version": selection[-1]["evidence_version"]})
        before = self.hashes()
        status, _, raw = self.batch(selection)
        self.assertEqual(status, 409, raw)
        self.assertIn(b"saved review changed", raw)
        self.assertEqual(self.hashes(), before)

    def test_later_changed_packet_refuses_whole_batch(self):
        selection = self.selection()
        packet = next(p for p in self.summary["packets"] if p["load_id"] == self.ids[-1])
        target = self.out / packet["file"]
        target.write_bytes(target.read_bytes() + b"\n<!-- changed fixture -->\n")
        before = self.hashes()
        status, _, raw = self.batch(selection)
        self.assertEqual(status, 409, raw)
        self.assertIn(b"packet evidence changed", raw)
        self.assertEqual(self.hashes(), before)

    def test_missing_later_packet_refuses_whole_batch(self):
        selection = self.selection()
        packet = next(p for p in self.summary["packets"] if p["load_id"] == self.ids[-1])
        (self.out / packet["file"]).unlink()
        before = self.hashes()
        status, _, raw = self.batch(selection)
        self.assertEqual(status, 404, raw)
        self.assertEqual(self.hashes(), before)

    def test_ambiguous_selected_packet_refuses_whole_batch(self):
        selection = self.selection()
        path = self.out / "summary.json"
        summary = json.loads(path.read_text())
        summary["packets"].append(dict(next(p for p in summary["packets"] if p["load_id"] == self.ids[-1])))
        path.write_text(json.dumps(summary))
        before = self.hashes()
        status, _, raw = self.batch(selection)
        self.assertEqual(status, 404, raw)
        self.assertEqual(self.hashes(), before)

    def test_missing_summary_does_not_initialize_pipeline(self):
        selection = self.selection()
        (self.out / "summary.json").unlink()
        before = self.hashes()
        status, _, raw = self.batch(selection)
        self.assertEqual(status, 404, raw)
        self.assertEqual(self.hashes(), before)

    def test_invalid_selections_fail_before_any_output(self):
        one = self.selection([self.ids[0]])[0]
        invalid = [None, {}, [], [one, one], [one] * 101, ["load"],
                   [{**one, "load_id": ""}], [{**one, "load_id": 3}],
                   [{**one, "evidence_version": "A" * 64}],
                   [{**one, "review_version": None}], [{"load_id": one["load_id"]}],
                   [{**one, "extra": "not allowed"}]]
        before = self.hashes()
        for selected in invalid:
            with self.subTest(selected=selected):
                status, _, raw = self.request("/api/review-batch", {"loads": selected})
                self.assertEqual(status, 400, raw)
                self.assertEqual(self.hashes(), before)
        status, _, raw = self.request("/api/review-batch", {"loads": [one], "extra": True})
        self.assertEqual(status, 400, raw)
        self.assertEqual(self.hashes(), before)

    def test_native_review_states_stay_distinct_in_existing_covers(self):
        selection = self.selection()
        decisions = {
            self.ids[0]: {"decision": "approve", "note": "older approval <&>", "at": "fixture-old",
                          "evidence_version": "0" * 64, "history": []},
            self.ids[1]: {"decision": "approve", "note": "no old binding", "at": "fixture-legacy", "history": []},
            self.ids[2]: {"decision": "clear", "note": "cleared note", "at": "fixture-clear", "history": []},
        }
        (self.out / "decisions.json").write_text(json.dumps(decisions))
        status, _, raw = self.batch()
        self.assertEqual(status, 200, raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as batch:
            manifest = json.loads(batch.read("manifest.json"))
            self.assertEqual([x["review_state"] for x in manifest["loads"]], ["stale", "unbound", "cleared"])
            self.assertIn(b"Previous review", batch.read("index.html"))
            self.assertNotIn(b"Current saved review: Approve", batch.read("index.html"))
            self.assertIn(b"older approval &lt;&amp;&gt;", batch.read("loads/0001/index.html"))
            for row in manifest["loads"]:
                saved = json.loads(batch.read(row["index_path"].replace("index.html", "review.json")))["review"]
                self.assertEqual(saved["review_state"], row["review_state"])

    def test_new_module_is_served_locally_and_ui_retains_single_load_flow(self):
        status, headers, body = self.request("/batch-handoff-ui.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers["Content-Type"])
        self.assertIn(b"createFreightBatchHandoff", body)
        status, _, ui = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b'download-review-bundle', ui)
        self.assertIn(b'/batch-handoff-ui.js', ui)

    def test_simultaneous_review_waits_for_the_complete_batch_snapshot(self):
        selected = self.selection()
        entered, release, attempt, updated = (threading.Event() for _ in range(4))
        original = self.app.review_bundle
        failure = []
        def guarded(*args):
            result = original(*args)
            if args[0] == selected[0]["load_id"]:
                entered.set()
                if not release.wait(3):
                    raise RuntimeError("test did not release the paused per-load read")
            return result
        self.app.review_bundle = guarded
        response = []
        batch_thread = threading.Thread(target=lambda: response.append(self.batch(selected)))
        batch_thread.start()
        self.assertTrue(entered.wait(3))
        def update():
            attempt.set()
            try:
                self.app.decide({"load_id": selected[-1]["load_id"], "decision": "adjust",
                                 "note": "later local review", "evidence_version": selected[-1]["evidence_version"]})
            except Exception as error:
                failure.append(error)
            finally:
                updated.set()
        update_thread = threading.Thread(target=update)
        update_thread.start()
        try:
            self.assertTrue(attempt.wait(1))
            self.assertFalse(updated.wait(.1), "a review changed between selected load snapshots")
        finally:
            release.set()
            batch_thread.join(4)
            update_thread.join(4)
        self.assertFalse(batch_thread.is_alive())
        self.assertFalse(update_thread.is_alive())
        self.assertFalse(failure)
        status, _, raw = response[0]
        self.assertEqual(status, 200, raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as batch:
            manifest = json.loads(batch.read("manifest.json"))
            self.assertEqual([row["review_version"] for row in manifest["loads"]],
                             [row["review_version"] for row in selected])
        self.assertNotEqual(self.app.summary()["review_versions"][selected[-1]["load_id"]],
                            selected[-1]["review_version"])

    def test_archive_paths_do_not_come_from_labels_or_per_load_filenames(self):
        from freightpkt.handoff import build_bundle, bundle_filename, review_version
        from freightpkt.batch_handoff import build_batch_bundle
        packet = b"<!doctype html><title>authored packet fixture</title>"
        evidence = {"schema": "freight-review.v1", "packet_sha256": hashlib.sha256(packet).hexdigest(),
                    "stops": [], "flags": [], "fines": [], "settlements": [], "exceptions": [], "packets": []}
        evidence_version = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":"),
                                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        saved = review_version(None)
        labels = ["../A B", "../A.B"]
        fixtures = [({"load_id": label, "evidence_version": evidence_version, "review_version": saved},
                     bundle_filename(label, evidence_version),
                     build_bundle(label, packet, evidence, None, evidence_version, saved))
                    for label in labels]
        self.assertEqual(fixtures[0][1], fixtures[1][1])
        _, raw = build_batch_bundle(fixtures)
        with zipfile.ZipFile(io.BytesIO(raw)) as batch:
            manifest = json.loads(batch.read("manifest.json"))
            self.assertEqual([row["load_id"] for row in manifest["loads"]], labels)
            self.assertEqual(len(set(batch.namelist())), len(batch.namelist()))
            self.assertFalse(any(".." in name or name.startswith("/") for name in batch.namelist()))
            for i, (_, _, original) in enumerate(fixtures, 1):
                self.assertEqual(batch.read(f"loads/{i:04d}/review.zip"), original)

if __name__ == "__main__":
    unittest.main(verbosity=2)
