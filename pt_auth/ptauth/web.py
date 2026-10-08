"""Local worklist UI: stdlib http.server, single page, no CDN, 127.0.0.1 only.

  GET  /               single-page app
  GET  /api/summary    latest run + staff work states
  POST /api/run        {"as_of": "YYYY-MM-DD"?}
  POST /api/generate   {"seed": int}
  POST /api/state      {"key", "state": open|submitted|approved|n/a, "note"}
  POST /api/calendar   {"snapshot", "keys"} -> read-only reviewed .ics handoff
  GET  /out/<file>     digest.html, worklist.csv, ledger.csv, audit.jsonl
"""
from __future__ import annotations

import json
import mimetypes
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .data import clinic_timezone_label, resolve_clinic_timezone
from .report import audit, run
from .worklist_calendar import (CalendarInputError, CalendarStaleError, decode_json,
                                load_report, prepare_calendar, render_calendar, snapshot_token)

UI = Path(__file__).with_name("ui.html")
STATES = ("open", "submitted", "approved", "n/a")


class App:
    def __init__(self, data_dir: Path, out_dir: Path, *, clinic_timezone: str | None = None):
        self.timezone_label = clinic_timezone_label(resolve_clinic_timezone(clinic_timezone))
        self.clinic_timezone = clinic_timezone
        # A host-local label cannot establish equivalence with another machine.
        self._local_zone_checked = clinic_timezone is not None
        self.data_dir, self.out_dir = Path(data_dir), Path(out_dir)
        self.as_of: date | None = None

    @property
    def state_path(self) -> Path:
        return self.out_dir / "work_state.json"

    def states(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.exists() else {}

    def run(self):
        if not (self.data_dir / "schedule.csv").exists():
            from .synth import generate
            generate(self.data_dir)
        result = run(self.data_dir, self.out_dir, self.as_of, run_by="web",
                     clinic_timezone=self.clinic_timezone)
        self._local_zone_checked = True
        return result

    def summary(self) -> dict:
        p = self.out_dir / "summary.json"
        if not p.exists():
            self.run()
        s = json.loads(p.read_text(encoding="utf-8"))
        if s.get("clinic_timezone") != self.timezone_label or not self._local_zone_checked:
            # A timezone change reinterprets this report's same reviewed date.
            if self.as_of is None:
                self.as_of = date.fromisoformat(s["as_of"])
            self.run()
            s = json.loads(p.read_text(encoding="utf-8"))
        s["states"] = self.states()
        try:
            s["calendar_snapshot"] = prepare_calendar(s)["snapshot"]
        except CalendarInputError as e:
            s["calendar_snapshot"] = None
            s["calendar_error"] = str(e)
        return s

    def calendar(self, body: dict) -> bytes:
        if not isinstance(body, dict) or set(body) != {"snapshot", "keys"}:
            raise CalendarInputError("Calendar request requires snapshot and selected keys")
        expected = body["snapshot"]
        if not isinstance(expected, str) or len(expected) != 64:
            raise CalendarInputError("A reviewed calendar snapshot is required")
        if not isinstance(body["keys"], list):
            raise CalendarInputError("Selected keys must be an array")
        current = load_report(self.out_dir)
        if snapshot_token(current) != expected:
            raise CalendarStaleError("Report or staff state changed; refresh the worklist before exporting")
        plan = prepare_calendar(current, body["keys"])
        content = render_calendar(plan)
        if snapshot_token(load_report(self.out_dir)) != expected:
            raise CalendarStaleError("Report or staff state changed during export; refresh and try again")
        return content

    def set_state(self, body: dict) -> dict:
        key, st = str(body.get("key", "")), str(body.get("state", ""))
        if st not in STATES or not key:
            raise ValueError(f"state must be one of {STATES}")
        d = self.states()
        d[key] = {"state": st, "note": str(body.get("note", ""))[:300],
                  "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        self.state_path.write_text(json.dumps(d, indent=2), encoding="utf-8")
        # audit records the work-item key only (ids are synthetic; in production keep PHI out of logs)
        audit(self.out_dir, "work_state", key=key, state=st)
        return d


def make_handler(app: App):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body: bytes, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, o, code=200):
            self._send(code, json.dumps(o, default=str).encode())

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                return self._send(200, UI.read_bytes(), "text/html; charset=utf-8")
            if path == "/calendar_ui.js":
                return self._send(200, UI.with_name("calendar_ui.js").read_bytes(), "text/javascript; charset=utf-8")
            if path == "/api/summary":
                return self._json(app.summary())
            if path.startswith("/out/"):
                t = (app.out_dir / path[5:]).resolve()
                if app.out_dir.resolve() not in t.parents or not t.is_file():
                    return self._send(404, b"not found", "text/plain")
                ct = mimetypes.guess_type(t.name)[0] or "application/octet-stream"
                return self._send(200, t.read_bytes(), ct + ("; charset=utf-8" if ct.startswith("text/") else ""))
            self._send(404, b"not found", "text/plain")

        def _calendar(self):
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if not 0 < n <= 2 * 1024 * 1024:
                    raise CalendarInputError("Calendar request must contain at most 2 MiB of JSON")
                content = app.calendar(decode_json(self.rfile.read(n)))
            except CalendarStaleError as e:
                return self._json({"error": str(e)}, 409)
            except (CalendarInputError, OSError, ValueError) as e:
                return self._json({"error": str(e)}, 400)
            return self._send(200, content, "text/calendar; charset=utf-8")

        def do_POST(self):
            if self.path == "/api/calendar":
                return self._calendar()
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
                if self.path == "/api/run":
                    if body.get("as_of"):
                        app.as_of = date.fromisoformat(body["as_of"])
                    app.run()
                    return self._json(app.summary())
                if self.path == "/api/generate":
                    from .synth import generate
                    generate(app.data_dir, seed=int(body.get("seed", 21)))
                    app.as_of = None
                    if app.state_path.exists():
                        app.state_path.unlink()
                    app.run()
                    return self._json(app.summary())
                if self.path == "/api/state":
                    return self._json(app.set_state(body))
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                return self._json({"error": str(e)}, 400)
            self._json({"error": "not found"}, 404)

    return H


def serve(data_dir: Path, out_dir: Path, port: int = 8766, *, clinic_timezone: str | None = None) -> None:
    app = App(data_dir, out_dir, clinic_timezone=clinic_timezone)
    app.summary()
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    print(f"PT auth tracker UI (SYNTHETIC DATA): http://127.0.0.1:{port}/  (Ctrl+C to stop)")
    print(f"Clinic time zone: {app.timezone_label}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
