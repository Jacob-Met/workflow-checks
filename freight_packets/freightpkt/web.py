"""Local review UI: stdlib http.server, one HTML page, no CDN, binds 127.0.0.1.

Endpoints
  GET  /                      single-page app
  GET  /api/summary           latest run summary + reviewer decisions
  POST /api/run               re-run the pipeline on the data dir
  POST /api/generate          regenerate synthetic data {"seed": int, "loads": int}
  POST /api/decision          {"load_id", "decision": approve|reject|adjust, "note"}
  GET  /out/<path>            packets / CSVs from the output dir
"""
from __future__ import annotations

import json
import mimetypes
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .pipeline import audit, run

UI = Path(__file__).with_name("ui.html")


class App:
    def __init__(self, data_dir: Path, out_dir: Path):
        self.data_dir, self.out_dir = Path(data_dir), Path(out_dir)

    @property
    def decisions_path(self) -> Path:
        return self.out_dir / "decisions.json"

    def decisions(self) -> dict:
        p = self.decisions_path
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def summary(self) -> dict:
        p = self.out_dir / "summary.json"
        if not p.exists():
            if not (self.data_dir / "loads.csv").exists():
                from .synth import generate
                generate(self.data_dir)
            run(self.data_dir, self.out_dir, run_by="web")
        s = json.loads(p.read_text(encoding="utf-8"))
        s["decisions"] = self.decisions()
        return s

    def decide(self, body: dict) -> dict:
        lid, dec = str(body.get("load_id", "")), str(body.get("decision", ""))
        if dec not in ("approve", "reject", "adjust", "clear"):
            raise ValueError("decision must be approve|reject|adjust|clear")
        d = self.decisions()
        if dec == "clear":
            d.pop(lid, None)
        else:
            d[lid] = {"decision": dec, "note": str(body.get("note", ""))[:500],
                      "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        self.decisions_path.write_text(json.dumps(d, indent=2), encoding="utf-8")
        audit(self.out_dir, "reviewer_decision", load_id=lid, decision=dec, note=body.get("note", ""))
        return d


def make_handler(app: App):
    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # quiet
            pass

        def _send(self, code, body: bytes, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, default=str).encode())

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                return self._send(200, UI.read_bytes(), "text/html; charset=utf-8")
            if path == "/api/summary":
                return self._json(app.summary())
            if path.startswith("/out/"):
                target = (app.out_dir / path[5:]).resolve()
                if app.out_dir.resolve() not in target.parents or not target.is_file():
                    return self._send(404, b"not found", "text/plain")
                ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                if ctype.startswith("text/"):
                    ctype += "; charset=utf-8"
                return self._send(200, target.read_bytes(), ctype)
            self._send(404, b"not found", "text/plain")

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "bad json"}, 400)
            try:
                if self.path == "/api/run":
                    run(app.data_dir, app.out_dir, run_by="web")
                    return self._json(app.summary())
                if self.path == "/api/generate":
                    from .synth import generate
                    generate(app.data_dir, int(body.get("loads", 24)), int(body.get("seed", 7)))
                    if app.decisions_path.exists():
                        app.decisions_path.unlink()
                    run(app.data_dir, app.out_dir, run_by="web")
                    return self._json(app.summary())
                if self.path == "/api/decision":
                    return self._json(app.decide(body))
            except (ValueError, KeyError) as e:
                return self._json({"error": str(e)}, 400)
            self._json({"error": "not found"}, 404)

    return H


def serve(data_dir: Path, out_dir: Path, port: int = 8765) -> None:
    app = App(data_dir, out_dir)
    app.summary()  # make sure there is something to show
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    print(f"Freight packet review UI: http://127.0.0.1:{port}/  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
