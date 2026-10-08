#!/usr/bin/env python3
"""Independent native Freight batch review; no authored candidate tests are imported."""
from __future__ import annotations
import argparse
import copy
import hashlib
import http.client
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import sys
import tempfile
import threading
import time
import traceback
import unittest
import zipfile
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer

sys.dont_write_bytecode = True
P = argparse.ArgumentParser()
P.add_argument("mode", choices=("prepare", "api", "serve"))
P.add_argument("--source", required=True)
P.add_argument("--fixture", required=True)
P.add_argument("--output", required=True)
ARGS = P.parse_args()
SOURCE = Path(ARGS.source).resolve()
FIXTURE = Path(ARGS.fixture).resolve()
OUTPUT = Path(ARGS.output).resolve()
OUTPUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(SOURCE / "freight_packets"))
from freightpkt.web import App, make_handler

def sha(data):
    return hashlib.sha256(data).hexdigest()

def snapshot(root):
    return {str(p.relative_to(root)): {"bytes": p.stat().st_size, "sha256": sha(p.read_bytes())}
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n",
                    encoding="utf-8")

def source_pins():
    return {str(p.relative_to(SOURCE)): {"bytes": p.stat().st_size,
            "sha256": sha(p.read_bytes()),
            "git_blob_sha": hashlib.sha1(b"blob " + str(p.stat().st_size).encode()
                                        + b"\0" + p.read_bytes()).hexdigest()}
            for p in sorted((SOURCE / "freight_packets" / "freightpkt").iterdir())
            if p.is_file() and p.suffix in (".py", ".html", ".js")}

EXTERNAL_ATTEMPTS = []
_real_connect = socket.socket.connect
def loopback_connect(sock, address):
    if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1", "localhost"):
        EXTERNAL_ATTEMPTS.append(repr(address))
        raise RuntimeError("Independent fixture denies non-loopback networking")
    return _real_connect(sock, address)
socket.socket.connect = loopback_connect

def prepare():
    if FIXTURE.exists():
        raise RuntimeError("Fixture already exists; refusing to overwrite frozen bytes")
    from freightpkt.synth import generate
    from freightpkt.pipeline import run
    data, out = FIXTURE / "data", FIXTURE / "out"
    generate(data, 16, 149)
    run(data, out, run_by="independent-batch-fixture")
    app = App(data, out)
    initial = app.summary()
    ids = [p["load_id"] for p in initial["packets"]]
    if len(ids) < 8:
        raise RuntimeError("Native generator did not yield at least eight fixture packets")
    note = 'Saved <img src=x onerror="window.__freightInjection=1"> & note \U0001f9ed'
    def decide(index, value, text):
        current = app.summary()
        return app.decide({"load_id": ids[index], "decision": value, "note": text,
                           "evidence_version": current["evidence_versions"][ids[index]]})
    decide(0, "approve", "Earlier original note")
    decide(0, "adjust", note + " legacy surrogate: \ud800")
    decide(1, "reject", "Independent rejected draft")
    decide(2, "approve", "Before clear")
    decide(2, "clear", "Saved clear remains clear")
    decide(4, "approve", "Approval before later packet bytes")
    target = out / initial["packets"][4]["file"]
    target.write_bytes(target.read_bytes() + b"\n<!-- Changed after the saved approval -->\n")
    decisions = app._read_decisions()
    decisions[ids[5]] = {"decision": "approve", "note": "Legacy unbound approval",
                         "at": "2024-01-02T03:04:05Z", "history": []}
    app._write_decisions(decisions)
    decide(6, "approve", "Current unchanged approval")
    view = app.summary()
    receipt = {"kind": "one-time actual native generator/pipeline fixture",
               "source": str(SOURCE), "source_pins": source_pins(),
               "python": sys.version, "generator_loads": 16, "generator_seed": 149,
               "ids": ids, "review_states": {
                   load: view["decisions"].get(load, {}).get("review_state", "absent")
                   for load in ids},
               "files": snapshot(FIXTURE), "external_attempts": EXTERNAL_ATTEMPTS}
    dump(OUTPUT / "fixture-receipt.json", receipt)
    print(json.dumps({"fixture": str(FIXTURE), "file_count": len(receipt["files"]),
                      "bytes": sum(e["bytes"] for e in receipt["files"].values()),
                      "review_states": receipt["review_states"],
                      "receipt_sha256": sha((OUTPUT / "fixture-receipt.json").read_bytes())}))

class IndexParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.text, self.unsafe = [], [], []
    def handle_starttag(self, tag, attrs):
        pairs = dict(attrs)
        if tag in ("script", "iframe", "object", "embed", "img"):
            self.unsafe.append((tag, attrs))
        if any(k.lower().startswith("on") for k, _ in attrs):
            self.unsafe.append((tag, attrs))
        if "href" in pairs:
            self.links.append(pairs["href"])
        if any(k in pairs for k in ("src", "srcdoc")):
            self.unsafe.append((tag, attrs))
    def handle_data(self, data):
        self.text.append(data)

RESULT = {"source": str(SOURCE), "python": sys.version,
          "optimized": not __debug__, "cases": [], "http": [],
          "external_attempts": EXTERNAL_ATTEMPTS, "custody_snapshots": {}}

def intern_snapshot(value):
    identity = sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())
    RESULT["custody_snapshots"].setdefault(identity, value)
    return identity

class Receiving(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix=self._testMethodName + "-",
                                               dir=OUTPUT)
        self.root = Path(self.tmp.name)
        shutil.copytree(FIXTURE / "data", self.root / "data")
        shutil.copytree(FIXTURE / "out", self.root / "out")
        self.app = App(self.root / "data", self.root / "out")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.app))
        self.worker = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.01}, daemon=True)
        self.worker.start()
        self.case = {"method": self._testMethodName, "observations": []}
        RESULT["cases"].append(self.case)
    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=3)
        self.tmp.cleanup()
    def reset_files(self):
        for name in ("data", "out"):
            shutil.rmtree(self.root / name)
            shutil.copytree(FIXTURE / name, self.root / name)
    def need_batch(self):
        self.assertTrue(callable(getattr(self.app, "review_batch", None)),
                        "Native baseline has no App.review_batch capability")
    def selection(self, indices=None):
        view = self.app.summary()
        packets = view["packets"]
        chosen = packets if indices is None else [packets[i] for i in indices]
        return [{"load_id": p["load_id"],
                 "evidence_version": view["evidence_versions"][p["load_id"]],
                 "review_version": view["review_versions"][p["load_id"]]}
                for p in chosen]
    def request(self, method, path, body=None, raw=None, readonly=True):
        before = snapshot(self.root)
        wire = raw if raw is not None else (json.dumps(body, ensure_ascii=True).encode()
                                            if body is not None else None)
        con = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        con.request(method, path, body=wire,
                    headers={"Content-Type": "application/json"} if wire is not None else {})
        res = con.getresponse()
        code, headers, data = res.status, dict(res.getheaders()), res.read()
        con.close()
        after = snapshot(self.root)
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        record = {"case": self._testMethodName, "method": method, "path": path,
                  "request_bytes": len(wire or b""), "request_sha256": sha(wire or b""),
                  "status": code, "headers": headers, "response_bytes": len(data),
                  "response_sha256": sha(data), "readonly": readonly,
                  "changed_files": changed, "before_snapshot": intern_snapshot(before),
                  "after_snapshot": intern_snapshot(after)}
        if code != 200:
            record["error_text"] = data.decode("utf-8", errors="backslashreplace")[:2000]
        RESULT["http"].append(record)
        if readonly:
            self.assertEqual(before, after, "A read-only download changed fixture state")
        return code, headers, data
    def single(self, row, expected=200):
        from urllib.parse import urlencode
        code, headers, data = self.request("GET", "/api/review-bundle?" + urlencode(row))
        self.assertEqual(code, expected)
        if expected == 200:
            self.assertEqual(headers.get("Content-Type"), "application/zip")
            self.assertIn("attachment;", headers.get("Content-Disposition", ""))
        else:
            self.assertNotEqual(headers.get("Content-Type"), "application/zip")
            self.assertNotIn("Content-Disposition", headers)
        return data
    def batch(self, rows, expected=200, readonly=True):
        self.need_batch()
        code, headers, data = self.request("POST", "/api/review-batch",
                                            {"loads": rows}, readonly=readonly)
        self.assertEqual(code, expected)
        if expected == 200:
            self.assertEqual(headers.get("Content-Type"), "application/zip")
            self.assertIn("attachment;", headers.get("Content-Disposition", ""))
        else:
            self.assertNotEqual(headers.get("Content-Type"), "application/zip")
            self.assertNotIn("Content-Disposition", headers)
            self.assertFalse(data.startswith(b"PK"))
        return data
    def originals(self, rows):
        return [self.single(r) for r in rows]
    def assert_archive(self, data, rows, originals):
        with zipfile.ZipFile(io.BytesIO(data)) as batch:
            names = batch.namelist()
            self.assertEqual(len(names), len(set(names)), "Duplicate ZIP members")
            for name in names:
                p = PurePosixPath(name)
                self.assertFalse(p.is_absolute())
                self.assertNotIn("..", p.parts)
                self.assertNotIn("\\", name)
                self.assertNotIn("\x00", name)
                self.assertNotIn(":", name)
            expected_members = {"index.html"}
            for i, (row, original) in enumerate(zip(rows, originals), 1):
                prefix = f"loads/{i:04d}/"
                self.assertEqual(batch.read(prefix + "review.zip"), original)
                with zipfile.ZipFile(io.BytesIO(original)) as single:
                    self.assertEqual(set(single.namelist()),
                                     {"index.html", "packet.html", "evidence.json",
                                      "review.json", "manifest.json"})
                    for name in single.namelist():
                        expected_members.add(prefix + name)
                        self.assertEqual(batch.read(prefix + name), single.read(name))
                    review = json.loads(single.read("review.json"))
                    for key in ("load_id", "evidence_version", "review_version"):
                        self.assertEqual(review[key], row[key])
                    manifest = json.loads(single.read("manifest.json"))
                    for f in manifest["files"]:
                        value = single.read(f["path"])
                        self.assertEqual(f["bytes"], len(value))
                        self.assertEqual(f["sha256"], sha(value))
                expected_members.add(prefix + "review.zip")
            actual = set(names)
            self.assertTrue(actual in (expected_members, expected_members | {"manifest.json"}),
                            "Archive includes unexpected or missing content")
            parser = IndexParser()
            parser.feed(batch.read("index.html").decode("utf-8"))
            self.assertFalse(parser.unsafe, "Load label became active markup")
            covers = [x for x in parser.links if x.endswith("/index.html")]
            self.assertEqual(covers, [f"loads/{i:04d}/index.html"
                                      for i in range(1, len(rows) + 1)])
            for link in parser.links:
                self.assertIn(link, names, "Index link does not stay inside archive")
            visible = "".join(parser.text)
            for row in rows:
                self.assertIn(row["load_id"], visible)
            self.case["observations"].append({
                "archive_sha256": sha(data), "selected": rows,
                "members": [{"path": n, "bytes": len(batch.read(n)),
                             "sha256": sha(batch.read(n))} for n in names],
                "cover_links": covers})
    def output_summary(self):
        path = self.root / "out" / "summary.json"
        return path, json.loads(path.read_text())
    def save_summary(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=True) + "\n")
    def relabel(self, labels):
        path, summary = self.output_summary()
        old = [p["load_id"] for p in summary["packets"]]
        mapping = dict(zip(old, labels))
        for section in ("stops", "flags", "fines", "settlements", "exceptions", "packets"):
            for row in summary.get(section, []):
                if row.get("load_id") in mapping:
                    row["load_id"] = mapping[row["load_id"]]
        self.save_summary(path, summary)
        decisions = self.app._read_decisions()
        self.app._write_decisions({mapping.get(k, k): v for k, v in decisions.items()})
        return self.selection()
    def test_00_original_per_load_states_and_exact_members(self):
        rows = self.selection()
        states = ["current", "current", "cleared", None, "stale", "unbound", "current", None]
        for row, expected in zip(rows, states):
            data = self.single(row)
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                self.assertEqual(set(z.namelist()), {"index.html", "packet.html", "evidence.json",
                                                    "review.json", "manifest.json"})
                review = json.loads(z.read("review.json"))["review"]
                self.assertEqual(review.get("review_state") if review else None, expected)
                manifest = json.loads(z.read("manifest.json"))
                for member in manifest["files"]:
                    value = z.read(member["path"])
                    self.assertEqual((member["bytes"], member["sha256"]), (len(value), sha(value)))
            self.case["observations"].append({"load_id": row["load_id"], "state": expected,
                                               "single_sha256": sha(data)})
    def test_01_original_stale_and_missing_single_refusals(self):
        row = self.selection([0])[0]
        _, summary = self.output_summary()
        packet = self.root / "out" / summary["packets"][0]["file"]
        packet.write_bytes(packet.read_bytes() + b"\nchanged")
        self.single(row, 409)
        packet.unlink()
        self.single(row, 404)
    def test_02_original_report_isolation(self):
        rows = self.selection([0, 1])
        original = self.single(rows[0])
        path, summary = self.output_summary()
        summary["exceptions"].append({"load_id": rows[1]["load_id"], "stop": "",
                                      "reason": "Unselected report changed", "evidence": "fixture:999"})
        self.save_summary(path, summary)
        self.assertEqual(self.single(rows[0]), original)
        self.single(rows[1], 409)
    def test_10_exact_subset_all_review_states(self):
        self.need_batch()
        rows = self.selection([5, 3, 0, 2, 4, 1, 6])
        originals = self.originals(rows)
        data = self.batch(rows)
        self.assert_archive(data, rows, originals)
        (OUTPUT / "accepted-mixed-state-batch.zip").write_bytes(data)
        for i, value in enumerate(originals, 1):
            (OUTPUT / f"oracle-{i:02d}.zip").write_bytes(value)
    def test_11_one_selected_load_preserves_entire_native_zip(self):
        self.need_batch()
        rows = self.selection([0])
        self.assert_archive(self.batch(rows), rows, self.originals(rows))
    def test_12_explicit_request_order_is_not_sorted(self):
        self.need_batch()
        for indices in ([7, 1, 4], [4, 7, 1]):
            rows = self.selection(indices)
            self.assert_archive(self.batch(rows), rows, self.originals(rows))
    def test_13_ordinal_paths_and_inert_colliding_labels(self):
        self.need_batch()
        labels = ["A/B", "A?B", "..", "a\\b", "CON",
                  '"><svg onload="window.__freightInjection=1">', "Å \U0001f9ed", "A B"]
        rows = self.relabel(labels)
        self.assert_archive(self.batch(rows), rows, self.originals(rows))
    def test_14_exact_distinct_identity_not_normalized(self):
        self.need_batch()
        rows = self.relabel(["LOAD", "load", " LOAD", "LOAD ", "é", "e\u0301", "ＬＯＡＤ", "Load"])
        self.assert_archive(self.batch(rows), rows, self.originals(rows))
    def test_15_later_stale_packet_refuses_complete_batch(self):
        self.need_batch()
        rows = self.selection([0, 1])
        _, summary = self.output_summary()
        target = self.root / "out" / summary["packets"][1]["file"]
        target.write_bytes(target.read_bytes() + b"\n<!-- later evidence -->")
        self.batch(rows, 409)
        self.single(rows[0])
    def test_16_later_report_change_refuses_complete_batch(self):
        self.need_batch()
        rows = self.selection([0, 1])
        path, summary = self.output_summary()
        summary["exceptions"].append({"load_id": rows[1]["load_id"], "stop": "",
                                      "reason": "Changed report", "evidence": "source:51"})
        self.save_summary(path, summary)
        self.batch(rows, 409)
        self.single(rows[0])
    def test_17_saved_note_and_history_identity_are_fenced(self):
        self.need_batch()
        for field in ("note", "history"):
            with self.subTest(field=field):
                self.reset_files()
                rows = self.selection([1, 0])
                decisions = self.app._read_decisions()
                if field == "note":
                    decisions[rows[1]["load_id"]]["note"] += " later"
                else:
                    decisions[rows[1]["load_id"]]["history"].append(
                        {"decision": "reject", "note": "Later imported history", "at": "2025-01-01"})
                self.app._write_decisions(decisions)
                self.batch(rows, 409)
                self.single(rows[0])
    def test_18_missing_selection_refuses_complete_batch(self):
        self.need_batch()
        rows = self.selection([0, 1])
        _, summary = self.output_summary()
        (self.root / "out" / summary["packets"][1]["file"]).unlink()
        self.batch(rows, 404)
        self.single(rows[0])
    def test_19_ambiguous_packet_identity_refuses_complete_batch(self):
        self.need_batch()
        rows = self.selection([0, 1])
        path, summary = self.output_summary()
        summary["packets"].append(copy.deepcopy(summary["packets"][1]))
        self.save_summary(path, summary)
        fresh = self.selection([0, 1])
        self.batch(fresh, 404)
        self.single(fresh[0])
    def test_20_duplicate_selected_id_even_with_other_version_refuses(self):
        self.need_batch()
        row = self.selection([0])[0]
        for last in (row, {**row, "review_version": "0" * 64}):
            with self.subTest(last_version=last["review_version"]):
                self.batch([row, last], 400)
    def test_21_selection_size_boundaries(self):
        self.need_batch()
        row = self.selection([0])[0]
        self.batch([], 400)
        self.batch([row] * 101, 400)
        path, summary = self.output_summary()
        for section in ("stops", "flags", "fines", "settlements", "exceptions"):
            summary[section] = []
        summary["packets"] = []
        for i in range(100):
            relative = f"packets/bound-{i:03d}.html"
            (self.root / "out" / relative).write_bytes(b"<!doctype html><title>Tiny synthetic draft</title>")
            summary["packets"].append({"load_id": f"BOUND-{i:03d}", "file": relative,
                                      "detention_cents": 0, "late_stops": []})
        self.save_summary(path, summary)
        self.app._write_decisions({})
        rows = self.selection()
        self.assertEqual(len(rows), 100)
        self.assert_archive(self.batch(rows), rows, self.originals(rows))
    def test_22_malformed_body_and_field_types(self):
        self.need_batch()
        row = self.selection([0])[0]
        values = [None, [], "", 1, True, {}, {"loads": None}, {"loads": {}},
                  {"loads": [None]}, {"loads": ["bad"]}, {"loads": [True]},
                  {"loads": [row], "unexpected": True}]
        for field in ("load_id", "evidence_version", "review_version"):
            values.append({"loads": [{k: v for k, v in row.items() if k != field}]})
            for bad in (None, True, 7, [], {}, ""):
                values.append({"loads": [{**row, field: bad}]})
        values += [{"loads": [{**row, "extra": "not contract"}]},
                   {"loads": [{**row, "evidence_version": "A" * 64}]},
                   {"loads": [{**row, "review_version": "a" * 63}]},
                   {"loads": [{**row, "review_version": "a" * 63 + "g"}]}]
        for body in values:
            with self.subTest(body=body):
                code, headers, data = self.request("POST", "/api/review-batch", body)
                self.assertEqual(code, 400)
                self.assertNotEqual(headers.get("Content-Type"), "application/zip")
                self.assertNotIn("Content-Disposition", headers)
        for raw in (b'{"loads":', b"\xff", b"null", b"[]"):
            with self.subTest(raw=repr(raw)):
                self.assertEqual(self.request("POST", "/api/review-batch", raw=raw)[0], 400)
    def test_23_unknown_and_path_like_ids_never_become_paths(self):
        self.need_batch()
        row = self.selection([0])[0]
        for value in ("NOT-IN-SUMMARY", "../../decisions.json", "/etc/passwd",
                      "C:\\secrets", '<img src=x onerror="boom()">'):
            with self.subTest(load_id=value):
                self.batch([{**row, "load_id": value}], 404)
    def test_24_missing_summary_does_not_initialize(self):
        self.need_batch()
        rows = self.selection([0, 1])
        (self.root / "out" / "summary.json").unlink()
        self.batch(rows, 404)
        self.assertFalse((self.root / "out" / "summary.json").exists())
    def test_25_packet_path_escape_is_not_read_or_bundled(self):
        self.need_batch()
        rows = self.selection([0, 1])
        marker = self.root / "outside-sensitive-fixture.txt"
        marker.write_bytes(b"ONLY-IN-OWNED-FIXTURE-NOT-A-LOAD")
        path, summary = self.output_summary()
        summary["packets"][1]["file"] = "../outside-sensitive-fixture.txt"
        self.save_summary(path, summary)
        data = self.batch(rows, 404)
        self.assertNotIn(marker.read_bytes(), data)
        self.single(rows[0])
    def test_26_malformed_optional_review_history_is_atomic(self):
        self.need_batch()
        decisions = self.app._read_decisions()
        target = self.selection([0])[0]["load_id"]
        decisions[target]["history"] = ["not a review record"]
        self.app._write_decisions(decisions)
        rows = self.selection([1, 0])
        self.batch(rows, 400)
        self.single(rows[0])
    def test_27_unselected_changes_preserve_selected_snapshot(self):
        self.need_batch()
        rows = self.selection([0, 2])
        originals = self.originals(rows)
        path, summary = self.output_summary()
        other = summary["packets"][7]["load_id"]
        summary["generated_at"] = "2030-12-31T23:59:59"
        summary["exceptions"].append({"load_id": other, "stop": "", "reason": "Other-only",
                                      "evidence": "other:55"})
        self.save_summary(path, summary)
        self.assert_archive(self.batch(rows), rows, originals)
    def test_28_same_app_writer_cannot_split_batch_snapshot(self):
        self.need_batch()
        first_done, writer_attempted, writer_finished = (threading.Event() for _ in range(3))
        observed, writer_errors = [], []
        class ObservedApp(App):
            observing = False
            def review_bundle(inner, *args, **kwargs):
                if not inner.observing:
                    return super().review_bundle(*args, **kwargs)
                owned = inner._lock._is_owned()
                value = super().review_bundle(*args, **kwargs)
                observed.append({"load_id": args[0], "outer_lock_owned": owned})
                if len(observed) == 1:
                    first_done.set()
                    if not writer_attempted.wait(3):
                        raise RuntimeError("Independent writer did not start")
                    observed[-1]["writer_entered_before_batch_release"] = writer_finished.wait(0.15)
                return value
        self.app = ObservedApp(self.root / "data", self.root / "out")
        self.server.RequestHandlerClass = make_handler(self.app)
        rows = self.selection([0, 1])
        originals = self.originals(rows)
        old = snapshot(self.root)
        def writer():
            try:
                if not first_done.wait(3):
                    raise RuntimeError("Batch never reached native bundle")
                writer_attempted.set()
                self.app.decide({"load_id": rows[1]["load_id"], "decision": "adjust",
                                 "note": "Deliberate independent concurrent fixture write",
                                 "evidence_version": rows[1]["evidence_version"]})
            except BaseException:
                writer_errors.append(traceback.format_exc())
            finally:
                writer_finished.set()
        thread = threading.Thread(target=writer, daemon=True)
        thread.start()
        self.app.observing = True
        data = self.batch(rows, readonly=False)
        self.app.observing = False
        self.assertTrue(writer_finished.wait(3))
        thread.join(timeout=1)
        self.assertFalse(writer_errors)
        self.assertEqual([r["load_id"] for r in observed], [r["load_id"] for r in rows])
        self.assertTrue(all(r["outer_lock_owned"] for r in observed))
        self.assertFalse(observed[0]["writer_entered_before_batch_release"])
        self.assert_archive(data, rows, originals)
        new = snapshot(self.root)
        changed = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
        self.assertEqual(changed, ["out/audit.jsonl", "out/decisions.json"])
        self.batch(rows, 409)
        self.case["observations"].append({"lock_observations": observed,
                                          "deliberate_writer_changed": changed})

def run_api():
    initial_source = source_pins()
    initial_fixture = snapshot(FIXTURE)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Receiving)
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    RESULT.update({"methods_run": result.testsRun,
                   "failure_entries": len(result.failures), "error_entries": len(result.errors),
                   "skipped": result.skipped,
                   "failures": [{"test": str(t), "traceback": text} for t, text in result.failures],
                   "errors": [{"test": str(t), "traceback": text} for t, text in result.errors],
                   "source_before": initial_source, "source_after": source_pins(),
                   "fixture_before": initial_fixture, "fixture_after": snapshot(FIXTURE),
                   "source_unchanged": initial_source == source_pins(),
                   "fixture_unchanged": initial_fixture == snapshot(FIXTURE)})
    dump(OUTPUT / "result.json", RESULT)
    print(json.dumps({"methods": result.testsRun, "failure_entries": len(result.failures),
                      "error_entries": len(result.errors), "skips": len(result.skipped),
                      "source_unchanged": RESULT["source_unchanged"],
                      "fixture_unchanged": RESULT["fixture_unchanged"],
                      "http_calls": len(RESULT["http"]),
                      "external_attempts": EXTERNAL_ATTEMPTS}))
    return 0 if result.wasSuccessful() and RESULT["source_unchanged"] and RESULT["fixture_unchanged"] else 1

def serve():
    app = App(FIXTURE / "data", FIXTURE / "out")
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    info = {"url": "http://127.0.0.1:" + str(server.server_address[1]),
            "pid": os.getpid(), "source": str(SOURCE), "fixture": str(FIXTURE),
            "source_pins": source_pins(), "fixture_before": snapshot(FIXTURE)}
    dump(OUTPUT / "server.json", info)
    print(json.dumps({"url": info["url"], "pid": info["pid"]}), flush=True)
    server.serve_forever(poll_interval=0.05)

if __name__ == "__main__":
    if ARGS.mode == "prepare":
        prepare()
    elif ARGS.mode == "api":
        sys.exit(run_api())
    else:
        serve()
