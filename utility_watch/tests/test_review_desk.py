"""Actual native worksheet, HTTP, and existing reconciliation consumer controls."""
import copy
import csv
import hashlib
import io
import json
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(Path(__file__).parent))
from review_desk_fixture import build, read_csv, write_csv  # noqa: E402
from uwatch import review  # noqa: E402
from uwatch.review_desk import DeskServer, DeskSnapshot, WorksheetChanged  # noqa: E402


@pytest.fixture
def fixture(tmp_path):
    return build(tmp_path / "fixture")


def current(fixture, account):
    return next(row for row in fixture["rows"] if row["row_state"] == "current" and row["account_no"] == account)


def request(snapshot, row, **edits):
    change = {key: row[key] for key in ("row_id", *review.EDITABLE)}
    change.update(edits)
    return {"snapshot": snapshot.snapshot, "changes": [change]}


def parsed(raw):
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8"), newline="")))


def hashes(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


def test_complete_csv_preserves_protected_cells_manifest_history_and_other_account(fixture):
    path = Path(fixture["worksheet"])
    before = hashes(path.parent)
    desk = DeskSnapshot(path)
    a, d = current(fixture, "A"), current(fixture, "D")
    assert a["finding_key"] == d["finding_key"] == "SHARED"
    text = '  Native Zoë 李, "quoted"  '
    note = '=literal <script>no execution</script>\nCR alone:\r Unicode 🌿\r\nLast line  '
    raw = desk.download(request(desk, a, review_status="in_progress", reviewer=text, note=note))
    result = parsed(raw)
    assert len(result) == len(fixture["rows"])
    for original, edited in zip(fixture["rows"], result):
        expected = dict(original)
        if original["row_id"] == a["row_id"]:
            expected.update(review_status="in_progress", reviewer=text, note=note)
        assert edited == expected
    assert any(row["row_state"] == "changed" for row in result)
    assert any(row["row_state"] == "absent" for row in result)
    assert review._previous(raw)
    assert hashes(path.parent) == before


def test_download_is_not_a_server_save_and_each_request_uses_the_original_snapshot(fixture):
    path = Path(fixture["worksheet"])
    desk = DeskSnapshot(path)
    initial = path.read_bytes()
    a = current(fixture, "A")
    changed = desk.download(request(desk, a, reviewer="First reviewer", note="Temporary browser change"))
    unchanged = desk.download({"snapshot": desk.snapshot, "changes": []})
    assert parsed(changed) != parsed(unchanged)
    assert parsed(unchanged) == fixture["rows"]
    assert path.read_bytes() == initial
    assert desk.view()["rows"] == [r for r in fixture["rows"] if r["row_state"] != "manifest"]


def test_invalid_status_identity_duplicates_history_and_protected_edits_refuse(fixture):
    path = Path(fixture["worksheet"])
    desk = DeskSnapshot(path)
    before = hashes(path.parent)
    a = current(fixture, "A")
    historical = next(row for row in fixture["rows"] if row["row_state"] == "changed")
    valid = request(desk, a, review_status="reviewed", reviewer="Reviewer", note="Checked")
    cases = []
    for edits in ({"review_status": "approved"}, {"reviewer": ""}, {"note": " \n"},
                  {"reviewer": False}, {"row_id": "missing"}, {"row_id": historical["row_id"]},
                  {"account_no": "D"}):
        case = copy.deepcopy(valid)
        case["changes"][0].update(edits)
        cases.append(case)
    duplicate = copy.deepcopy(valid)
    duplicate["changes"] *= 2
    cases.extend([duplicate, {"snapshot": desk.snapshot, "changes": {}, "extra": 1},
                  {"snapshot": "wrong", "changes": []}])
    for case in cases:
        with pytest.raises(ValueError):
            desk.download(case)
        assert hashes(path.parent) == before
    assert review._previous(desk.download(valid))
    assert hashes(path.parent) == before


def test_invalid_selected_worksheet_refuses_before_opening_listener(fixture):
    root = Path(fixture["worksheet"]).parent
    invalid = root / "invalid.csv"
    rows = copy.deepcopy(fixture["rows"])
    rows[0]["detail"] = "Unsealed different bill evidence"
    write_csv(invalid, rows, review.COLUMNS)
    before = hashes(root)
    with pytest.raises(ValueError, match="protected finding"):
        DeskServer(invalid)
    assert hashes(root) == before


def test_observed_source_change_or_removal_refuses_and_same_bytes_can_retry(fixture):
    path = Path(fixture["worksheet"])
    original = path.read_bytes()
    desk = DeskSnapshot(path)
    edited = request(desk, current(fixture, "A"), reviewer="Kept in browser", note="Retry me")
    path.write_bytes(original + b"\n")
    with pytest.raises(WorksheetChanged):
        desk.download(edited)
    path.unlink()
    with pytest.raises(WorksheetChanged):
        desk.view()
    path.write_bytes(original)
    raw = desk.download(edited)
    assert next(r for r in parsed(raw) if r["row_id"] == current(fixture, "A")["row_id"])["note"] == "Retry me"
    assert path.read_bytes() == original


def test_actual_download_remains_an_existing_native_review_consumer(fixture):
    path = Path(fixture["worksheet"])
    desk = DeskSnapshot(path)
    a = current(fixture, "A")
    raw = desk.download(request(desk, a, review_status="reviewed",
                                reviewer="Fictional receiving", note="Complete exact source check."))
    downloaded = path.parent / "downloaded.csv"
    downloaded.write_bytes(raw)
    before = hashes(path.parent)
    destination = path.parent / "reconciled.csv"
    child = subprocess.run(
        [sys.executable, "-B", "-m", "uwatch", "review", "--data", fixture["data"],
         "--report", fixture["report"], "--previous", str(downloaded), "--out", str(destination)],
        cwd=PACKAGE, capture_output=True, text=True, timeout=30)
    assert child.returncode == 0, child.stderr
    retained = next(r for r in read_csv(destination) if r["row_id"] == a["row_id"])
    assert (retained["review_status"], retained["reviewer"], retained["note"]) == (
        "reviewed", "Fictional receiving", "Complete exact source check.")
    after = hashes(path.parent)
    assert {key: after[key] for key in before} == before


@contextmanager
def running(path):
    server = DeskServer(path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def http(server, route, body=None, headers=None):
    data = None if body is None else body if isinstance(body, bytes) else json.dumps(body).encode()
    merged = {} if body is None else {"Content-Type": "application/json"}
    merged.update(headers or {})
    req = Request(server.origin + route, data=data, headers=merged)
    try:
        response = urlopen(req, timeout=10)
    except HTTPError as exc:
        response = exc
    with response:
        return response.status, response.headers, response.read()


def test_actual_http_serves_fixed_assets_and_native_csv_without_source_writes(fixture):
    path = Path(fixture["worksheet"])
    before = hashes(path.parent)
    with running(path) as server:
        assert server.server_address[0] == "127.0.0.1"
        for route, mime in (("/", "text/html"), ("/review_desk.js", "text/javascript"),
                            ("/review_desk.css", "text/css")):
            status, headers, content = http(server, route)
            assert status == 200 and mime in headers["Content-Type"] and content
            assert headers["Cache-Control"] == "no-store"
        status, _, content = http(server, "/api/worksheet")
        payload = json.loads(content)
        assert status == 200 and payload["snapshot"] == server.desk.snapshot
        edit = request(server.desk, current(fixture, "A"), reviewer="HTTP receiver", note="All rows retained.")
        status, headers, raw = http(server, "/api/download", edit, {"X-Review-Token": payload["token"]})
        assert status == 200
        assert headers["Content-Disposition"] == 'attachment; filename="utility-review-edited.csv"'
        assert len(parsed(raw)) == len(fixture["rows"])
        assert review._previous(raw)
    assert hashes(path.parent) == before


def test_http_refuses_other_origins_tokens_paths_and_malformed_requests_then_recovers(fixture):
    path = Path(fixture["worksheet"])
    before = hashes(path.parent)
    with running(path) as server:
        body = {"snapshot": server.desk.snapshot, "changes": []}
        token = {"X-Review-Token": server.token}
        cases = [
            ("/api/download", body, {}, 403),
            ("/api/download", body, {**token, "Origin": "http://elsewhere.invalid"}, 403),
            ("/api/download", body, {**token, "Host": "elsewhere.invalid"}, 403),
            ("/api/download", body, {**token, "Content-Type": "text/plain"}, 400),
            ("/api/download", b'{"snapshot":"x","snapshot":"y","changes":[]}', token, 400),
            ("/api/download", b'{"changes":NaN}', token, 400),
            ("/api/download", b'{"changes":', token, 400),
            ("/api/download", b"x", {**token, "Content-Length": str(4 * 1024 * 1024 + 1)}, 413),
            ("/api/path/../../selected.csv", None, {}, 404),
            ("/api/download?path=/tmp/other", body, token, 404),
        ]
        for route, value, headers, wanted in cases:
            assert http(server, route, value, headers)[0] == wanted
        # A full oversized sender can receive the server's early 413 or lose its
        # write to the deliberately closed unread body. The header-only control
        # above proves the HTTP status; this separate control retains the real
        # original upload boundary without accepting arbitrary network failures.
        try:
            assert http(server, "/api/download", b"x" * (4 * 1024 * 1024 + 1), token)[0] == 413
        except URLError as exc:
            assert isinstance(exc.reason, (BrokenPipeError, ConnectionResetError))
        assert http(server, "/api/download", body, token)[0] == 200
    assert hashes(path.parent) == before


def test_empty_current_and_bom_reordered_columns_preserve_native_cells(fixture):
    path = Path(fixture["worksheet"])
    rows = list(reversed(fixture["rows"]))
    write_csv(path, rows, tuple(reversed(review.COLUMNS)))
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    desk = DeskSnapshot(path)
    assert parsed(desk.download({"snapshot": desk.snapshot, "changes": []})) == rows
    empty = path.parent / "empty.csv"
    manifest = review._manifest([], desk.manifest)
    write_csv(empty, [manifest], review.COLUMNS)
    with running(empty) as server:
        assert server.desk.view()["rows"] == []
        assert parsed(server.desk.download({"snapshot": server.desk.snapshot, "changes": []})) == [manifest]
