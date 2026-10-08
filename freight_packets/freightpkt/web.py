"""Local review UI: stdlib http.server, no CDN, binds 127.0.0.1.

Reviewer decisions bind to the generated per-load evidence displayed by the UI.
Inputs must be rerun before reviewing their new results; nothing is sent or paid.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .pipeline import audit, run
from .handoff import build_bundle, bundle_filename, review_version
from .batch_handoff import build_batch_bundle, validate_selection

UI = Path(__file__).with_name("ui.html")
REVIEW_SECTIONS = ("stops", "flags", "fines", "settlements", "exceptions", "packets")


class ReviewConflict(ValueError):
    """The client has not reviewed the current generated packet."""


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


class App:
    def __init__(self, data_dir: Path, out_dir: Path):
        self.data_dir, self.out_dir = Path(data_dir), Path(out_dir)
        # One local server: a review must not race its own pipeline or another review.
        self._lock = threading.RLock()

    @property
    def decisions_path(self) -> Path:
        return self.out_dir / "decisions.json"

    def _read_decisions(self) -> dict:
        p = self.decisions_path
        decisions = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        if not isinstance(decisions, dict) or any(not isinstance(d, dict) for d in decisions.values()):
            raise ValueError("saved reviews are not a valid decision map")
        return decisions

    def _evidence_versions(self, summary: dict) -> dict:
        versions = {}
        for packet in summary["packets"]:
            load_id = packet["load_id"]
            target = (self.out_dir / packet["file"]).resolve()
            if self.out_dir.resolve() not in target.parents:
                continue
            try:
                packet_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            except OSError:
                # A remaining summary row or old decision is not evidence of a readable packet.
                continue
            evidence = {
                "schema": "freight-review.v1",
                "packet_sha256": packet_hash,
                **{section: sorted(
                    (r for r in summary.get(section, []) if r.get("load_id") == load_id),
                    key=_canonical,
                ) for section in REVIEW_SECTIONS},
            }
            versions[load_id] = hashlib.sha256(_canonical(evidence).encode("utf-8")).hexdigest()
        return versions

    def _decision_view(self, versions: dict) -> dict:
        result = {}
        for load_id, decision in self._read_decisions().items():
            if decision.get("decision") == "clear":
                state = "cleared"
            elif load_id not in versions:
                state = "missing"
            elif not decision.get("evidence_version"):
                state = "unbound"
            elif decision["evidence_version"] != versions[load_id]:
                state = "stale"
            else:
                state = "current"
            result[load_id] = {**decision, "review_state": state}
        return result

    def summary(self) -> dict:
        with self._lock:
            p = self.out_dir / "summary.json"
            if not p.exists():
                if not (self.data_dir / "loads.csv").exists():
                    from .synth import generate
                    generate(self.data_dir)
                run(self.data_dir, self.out_dir, run_by="web")
            summary = json.loads(p.read_text(encoding="utf-8"))
            versions = self._evidence_versions(summary)
            summary["evidence_versions"] = versions
            summary["decisions"] = self._decision_view(versions)
            summary["review_versions"] = {
                packet["load_id"]: review_version(summary["decisions"].get(packet["load_id"]))
                for packet in summary["packets"]
            }
            return summary

    def rerun(self) -> dict:
        with self._lock:
            run(self.data_dir, self.out_dir, run_by="web")
            return self.summary()

    def regenerate(self, loads: int, seed: int) -> dict:
        from .synth import generate
        with self._lock:
            generate(self.data_dir, loads, seed)
            # Retain the prior reviews; changed/missing packets cannot inherit them.
            return self.rerun()

    def _write_decisions(self, decisions: dict) -> None:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.out_dir,
                                             prefix=".decisions-", suffix=".tmp", delete=False) as file:
                temporary = Path(file.name)
                json.dump(decisions, file, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.decisions_path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def decide(self, body: dict) -> dict:
        if not isinstance(body, dict):
            raise ValueError("review must be a JSON object")
        load_id, decision = body.get("load_id"), body.get("decision")
        if not isinstance(load_id, str) or not load_id:
            raise ValueError("load_id must identify a current packet")
        if decision not in ("approve", "reject", "adjust", "clear"):
            raise ValueError("decision must be approve|reject|adjust|clear")
        expected = body.get("evidence_version")
        if not isinstance(expected, str) or len(expected) != 64:
            raise ValueError("evidence_version is required; reload the packet before reviewing")
        note = body.get("note", "")
        if not isinstance(note, str):
            raise ValueError("reviewer note must be text")
        note = note[:500]
        with self._lock:
            versions = self.summary()["evidence_versions"]
            if load_id not in versions:
                raise ValueError("load is not a current readable packet; reload before reviewing")
            if expected != versions[load_id]:
                raise ReviewConflict("packet evidence changed; reload and review it before saving")
            decisions = self._read_decisions()
            previous = decisions.get(load_id)
            history = list(previous.get("history", [])) if previous else []
            if previous:
                history.append({k: v for k, v in previous.items() if k != "history"})
            record = {
                "decision": decision, "note": note,
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "evidence_version": versions[load_id],
                "history": history,
            }
            decisions[load_id] = record
            self._write_decisions(decisions)
            audit(self.out_dir, "reviewer_decision", load_id=load_id, decision=decision,
                  note=note, evidence_version=versions[load_id])
            return self._decision_view(versions)

    def review_bundle(self, load_id: str, expected: str, saved_version: str) -> tuple[str, bytes]:
        if not isinstance(load_id, str) or not load_id:
            raise ValueError("load_id must identify a current packet")
        for value in (expected, saved_version):
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("current evidence_version and review_version are required")
        with self._lock:
            # Downloading never invokes summary()'s first-run pipeline initializer.
            if not (self.out_dir / "summary.json").is_file():
                raise FileNotFoundError("the generated summary is unavailable")
            summary = self.summary()
            matches = [p for p in summary["packets"] if p["load_id"] == load_id]
            if len(matches) != 1 or load_id not in summary["evidence_versions"]:
                raise FileNotFoundError("load is not a current readable packet")
            if expected != summary["evidence_versions"][load_id]:
                raise ReviewConflict("packet evidence changed; reload the review page before downloading")
            saved_review = summary["decisions"].get(load_id)
            if saved_version != review_version(saved_review):
                raise ReviewConflict("saved review changed; reload the review page before downloading")
            _, packet = self.output(matches[0]["file"], expected)
            evidence = {
                "schema": "freight-review.v1",
                "packet_sha256": hashlib.sha256(packet).hexdigest(),
                **{section: sorted(
                    (row for row in summary.get(section, []) if row.get("load_id") == load_id),
                    key=_canonical,
                ) for section in REVIEW_SECTIONS},
            }
            content = build_bundle(load_id, packet, evidence, saved_review, expected, saved_version)
            return bundle_filename(load_id, expected), content

    def review_batch(self, loads) -> tuple[str, bytes]:
        selection = validate_selection(loads)
        # The existing RLock is reentrant: every per-load snapshot shares this lock.
        with self._lock:
            bundles = []
            for row in selection:
                filename, content = self.review_bundle(
                    row["load_id"], row["evidence_version"], row["review_version"])
                bundles.append((row, filename, content))
            return build_batch_bundle(bundles)

    def output(self, relative: str, expected: str | None = None) -> tuple[Path, bytes]:
        with self._lock:
            target = (self.out_dir / relative).resolve()
            if self.out_dir.resolve() not in target.parents or not target.is_file():
                raise FileNotFoundError
            if expected is not None:
                summary = self.summary()
                packet = next((p for p in summary["packets"] if p["file"] == relative), None)
                if packet is None or summary["evidence_versions"].get(packet["load_id"]) != expected:
                    raise ReviewConflict("packet evidence changed; reload the review page")
            return target, target.read_bytes()


def make_handler(app: App):
    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code, body: bytes, ctype="application/json", download=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            if download is not None:
                self.send_header("Content-Disposition", f'attachment; filename="{download}"')
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, default=str).encode())

        def do_GET(self):
            url = urlsplit(self.path)
            path = unquote(url.path)
            try:
                if path == "/":
                    return self._send(200, UI.read_bytes(), "text/html; charset=utf-8")
                if path == "/batch-handoff-ui.js":
                    content = UI.with_name("batch_handoff_ui.js").read_bytes()
                    return self._send(200, content, "text/javascript; charset=utf-8")
                if path == "/api/summary":
                    return self._json(app.summary())
                if path == "/api/review-bundle":
                    query = parse_qs(url.query, keep_blank_values=True)
                    values = []
                    for field in ("load_id", "evidence_version", "review_version"):
                        supplied = query.get(field, [])
                        if len(supplied) != 1 or not supplied[0]:
                            raise ValueError("one " + field + " is required")
                        values.append(supplied[0])
                    filename, content = app.review_bundle(*values)
                    return self._send(200, content, "application/zip", download=filename)
                if path.startswith("/out/"):
                    versions = parse_qs(url.query, keep_blank_values=True).get("evidence_version")
                    if versions is not None and len(versions) != 1:
                        raise ValueError("one evidence_version is required")
                    target, content = app.output(path[5:], versions[0] if versions else None)
                    ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                    if ctype.startswith("text/"):
                        ctype += "; charset=utf-8"
                    return self._send(200, content, ctype)
            except FileNotFoundError:
                return self._send(404, b"not found", "text/plain")
            except ReviewConflict as error:
                return self._send(409, str(error).encode(), "text/plain; charset=utf-8")
            except (ValueError, KeyError, TypeError) as error:
                return self._json({"error": str(error)}, 400)
            except OSError:
                return self._json({"error": "could not read the local review files"}, 500)
            self._send(404, b"not found", "text/plain")

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("request must be a JSON object")
                if self.path == "/api/review-batch":
                    if set(body) != {"loads"}:
                        raise ValueError("a batch request needs only its selected loads")
                    try:
                        filename, content = app.review_batch(body["loads"])
                    except FileNotFoundError:
                        return self._json({"error": "a selected packet or generated summary is unavailable"}, 404)
                    except OSError:
                        return self._json({"error": "could not read the selected review files"}, 500)
                    return self._send(200, content, "application/zip", download=filename)
                if self.path == "/api/run":
                    return self._json(app.rerun())
                if self.path == "/api/generate":
                    return self._json(app.regenerate(int(body.get("loads", 24)), int(body.get("seed", 7))))
                if self.path == "/api/decision":
                    return self._json(app.decide(body))
            except ReviewConflict as error:
                return self._json({"error": str(error)}, 409)
            except (ValueError, KeyError, TypeError) as error:
                return self._json({"error": str(error)}, 400)
            except OSError:
                # A post-save audit failure may leave a saved review. Inspect; never auto-retry it.
                return self._json({"error": "could not complete the update; reload to inspect the saved review"}, 500)
            self._json({"error": "not found"}, 404)

    return H


def serve(data_dir: Path, out_dir: Path, port: int = 8765) -> None:
    app = App(data_dir, out_dir)
    app.summary()
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    print(f"Freight packet review UI: http://127.0.0.1:{port}/  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
