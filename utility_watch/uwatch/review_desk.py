"""Local worksheet annotation editing and explicit read-only source inspection."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import secrets
import stat
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from . import review
from .review_evidence import EvidenceChanged, inspect_evidence

MAX_WORKSHEET_BYTES = 8 * 1024 * 1024
MAX_REQUEST_BYTES = 4 * 1024 * 1024
DOWNLOAD_NAME = "utility-review-edited.csv"
ASSETS = {
    "/": ("review_desk.html", "text/html; charset=utf-8"),
    "/review_desk.js": ("review_desk.js", "text/javascript; charset=utf-8"),
    "/review_desk.css": ("review_desk.css", "text/css; charset=utf-8"),
    "/review_evidence.js": ("review_evidence.js", "text/javascript; charset=utf-8"),
}


class WorksheetChanged(ValueError):
    """The file selected at startup no longer contains the admitted snapshot."""


def _read_worksheet(path: Path) -> bytes:
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("the selected worksheet must be a regular file")
    with path.open("rb") as source:
        raw = source.read(MAX_WORKSHEET_BYTES + 1)
    if len(raw) > MAX_WORKSHEET_BYTES:
        raise ValueError("worksheet exceeds the 8 MiB desk limit")
    return raw


def _serialize(rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    # CRLF quotes standalone CR as well as LF inside a cell.
    writer = csv.DictWriter(stream, fieldnames=review.COLUMNS, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


class DeskSnapshot:
    """An immutable, native-validated worksheet and its explicit edit boundary."""

    def __init__(self, worksheet: Path):
        self.path = Path(worksheet).absolute()
        self.raw = _read_worksheet(self.path)
        try:
            review._previous(self.raw)
            _, incoming = review._csv(self.raw, "worksheet")
        except csv.Error as exc:
            raise ValueError(f"malformed worksheet CSV: {exc}") from exc
        self.rows = [dict(row) for _, row in incoming]
        self.snapshot = hashlib.sha256(self.raw).hexdigest()
        self.manifest = next(row for row in self.rows if row["row_state"] == "manifest")
        self.current = {row["row_id"]: row for row in self.rows if row["row_state"] == "current"}
        self.ensure_unchanged()

    def ensure_unchanged(self) -> None:
        try:
            current = _read_worksheet(self.path)
        except (OSError, ValueError) as exc:
            raise WorksheetChanged(
                "The selected worksheet is no longer readable as the admitted file. "
                "Keep your in-page notes and restart the desk with the intended worksheet."
            ) from exc
        if current != self.raw:
            raise WorksheetChanged(
                "The selected worksheet changed on disk. This action is refused; your in-page "
                "edits remain. Restart the desk with the intended worksheet before editing it."
            )

    def view(self) -> dict:
        self.ensure_unchanged()
        return {
            "filename": self.path.name,
            "snapshot": self.snapshot,
            "schema": review.SCHEMA,
            "metadata": {key: self.manifest[key] for key in ("as_of", "eval_from", "data_mode")},
            "rows": [dict(row) for row in self.rows if row["row_state"] != "manifest"],
        }

    def inspect(self, request: dict, data: Path | None, report: Path | None) -> bytes:
        self.ensure_unchanged()
        if not isinstance(request, dict) or set(request) != {"snapshot", "row_id"}:
            raise ValueError("source inspection needs exactly snapshot and row_id")
        if request["snapshot"] != self.snapshot:
            raise WorksheetChanged("This inspection belongs to another worksheet snapshot.")
        row_id = request["row_id"]
        if not isinstance(row_id, str) or row_id not in self.current:
            raise ValueError("Select one current saved finding to inspect its source records.")
        if data is None or report is None:
            raise ValueError("Source inspection needs both --data and --report when starting the desk.")
        raw = inspect_evidence(data, report, self.current[row_id], self.manifest)
        self.ensure_unchanged()
        return raw

    def download(self, request: dict) -> bytes:
        self.ensure_unchanged()
        if not isinstance(request, dict) or set(request) != {"snapshot", "changes"}:
            raise ValueError("download needs exactly snapshot and changes")
        if request["snapshot"] != self.snapshot:
            raise WorksheetChanged("This edit belongs to another worksheet snapshot; download refused.")
        changes = request["changes"]
        if not isinstance(changes, list) or len(changes) > len(self.current):
            raise ValueError("changes must contain at most one edit for each current finding")
        updates = {}
        for change in changes:
            if not isinstance(change, dict) or set(change) != {"row_id", *review.EDITABLE}:
                raise ValueError("edit only row_id, review_status, reviewer and note")
            if any(not isinstance(value, str) for value in change.values()):
                raise ValueError("all annotation fields and row_id must be text")
            row_id = change["row_id"]
            if row_id not in self.current or row_id in updates:
                raise ValueError("each edit must identify one distinct current finding")
            updates[row_id] = change
        rows = [dict(row) for row in self.rows]
        for row in rows:
            change = updates.get(row["row_id"])
            if change is not None:
                for key in review.EDITABLE:
                    row[key] = change[key]
        raw = _serialize(rows)
        if len(raw) > MAX_WORKSHEET_BYTES:
            raise ValueError("edited worksheet exceeds the 8 MiB desk limit")
        try:
            review._previous(raw)
        except csv.Error as exc:
            raise ValueError(f"malformed edited worksheet CSV: {exc}") from exc
        self.ensure_unchanged()
        return raw


class DeskServer(HTTPServer):
    """One loopback listener with a fixed worksheet and fixed asset routes."""

    def __init__(self, worksheet: Path, port: int = 0, *,
                 data: Path | None = None, report: Path | None = None):
        if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
            raise ValueError("port must be between 0 and 65535")
        if (data is None) != (report is None):
            raise ValueError("Supply both --data and --report to enable source inspection.")
        self.data, self.report = data, report
        self.desk = DeskSnapshot(worksheet)
        self.token = secrets.token_urlsafe(32)
        self.assets = {
            route: (Path(__file__).with_name(filename).read_bytes(), mime)
            for route, (filename, mime) in ASSETS.items()
        }
        super().__init__(("127.0.0.1", port), DeskHandler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.host = f"127.0.0.1:{self.server_port}"

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address


class DeskHandler(BaseHTTPRequestHandler):
    server: DeskServer

    def log_message(self, _format, *_args):
        # The command prints its URL once; never log worksheet or request contents.
        pass

    def _send(self, status: int, body: bytes, content_type: str,
              download: bool = False) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
        )
        self.send_header("Connection", "close")
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{DOWNLOAD_NAME}"')
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, status: int, value: dict) -> None:
        self._send(status, json.dumps(value, ensure_ascii=True).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _allowed(self) -> bool:
        if self.headers.get_all("Host") != [self.server.host]:
            self._json(403, {"error": "Open the exact loopback URL printed by this desk."})
            return False
        origin = self.headers.get_all("Origin")
        if origin is not None and origin != [self.server.origin]:
            self._json(403, {"error": "This request did not come from the local review desk."})
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            self._json(403, {"error": "Open the local review desk directly."})
            return False
        return True

    def do_GET(self):
        if not self._allowed():
            return
        if self.path in self.server.assets:
            body, mime = self.server.assets[self.path]
            self._send(200, body, mime)
        elif self.path == "/api/worksheet":
            try:
                payload = self.server.desk.view()
                payload["token"] = self.server.token
                payload["source_evidence"] = self.server.data is not None
                self._json(200, payload)
            except WorksheetChanged as exc:
                self._json(409, {"error": str(exc)})
        else:
            self._json(404, {"error": "No such review-desk route."})

    def do_POST(self):
        if not self._allowed():
            return
        if self.path not in ("/api/download", "/api/evidence"):
            self._json(404, {"error": "No such review-desk route."})
            return
        token = self.headers.get_all("X-Review-Token")
        if (token is None or len(token) != 1 or not token[0].isascii() or
                not secrets.compare_digest(token[0], self.server.token)):
            self._json(403, {"error": "Reload this desk to obtain its current download session."})
            return
        if self.headers.get_content_type() != "application/json" or self.headers.get("Transfer-Encoding"):
            self._json(400, {"error": "Send one bounded JSON edit request."})
            return
        lengths = self.headers.get_all("Content-Length")
        if lengths is None or len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
            self._json(400, {"error": "A single Content-Length is required."})
            return
        if len(lengths[0]) > 10:
            self._json(413, {"error": "Annotation request exceeds the 4 MiB limit."})
            return
        length = int(lengths[0])
        if not 0 < length <= MAX_REQUEST_BYTES:
            self._json(413, {"error": "Annotation request must be between 1 byte and 4 MiB."})
            return
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("the annotation request was incomplete")
            request = review._read_json(body)
            if self.path == "/api/evidence":
                output = self.server.desk.inspect(request, self.server.data, self.server.report)
            else:
                output = self.server.desk.download(request)
        except (WorksheetChanged, EvidenceChanged) as exc:
            self._json(409, {"error": str(exc)})
        except (ValueError, csv.Error, RecursionError) as exc:
            self._json(400, {"error": str(exc)})
        except TimeoutError:
            self._json(408, {"error": "The edit request timed out. Your in-page edits remain."})
        except OSError as exc:
            self._json(400, {"error": f"Cannot read the configured source evidence: {exc}"})
        else:
            if self.path == "/api/evidence":
                self._send(200, output, "application/json; charset=utf-8")
            else:
                self._send(200, output, "text/csv; charset=utf-8", download=True)


def serve(worksheet: Path, port: int = 0, *,
          data: Path | None = None, report: Path | None = None) -> None:
    """Serve until Ctrl+C. Inputs are read-only; edited CSV leaves through a download."""
    with DeskServer(worksheet, port, data=data, report=report) as server:
        print(f"Utility Watch review desk: {server.origin}", flush=True)
        print("Open that URL locally. Download a new worksheet to keep edits. Ctrl+C stops the desk.",
              flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
