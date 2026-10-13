"""Real worksheet-opening and saved-download controls on isolated fictional data."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from uwatch.review_desk import MAX_WORKSHEET_BYTES, _read_worksheet


OPEN_REPLACEMENT = r"""
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])
from uwatch.review_desk import _read_worksheet

selected = Path(sys.argv[2])
kind = sys.argv[3]
pipe = selected.with_name("replacement-pipe")
if kind == "symlink":
    os.mkfifo(pipe)
replacements = 0

def replace_before_open(event, args):
    global replacements
    if (event == "open" and replacements == 0 and
            isinstance(args[0], (str, bytes)) and
            os.fsdecode(args[0]) == str(selected)):
        replacements += 1
        selected.unlink()
        if kind == "symlink":
            selected.symlink_to(pipe)
        else:
            os.mkfifo(selected)

sys.addaudithook(replace_before_open)
try:
    _read_worksheet(selected)
except ValueError as exc:
    assert "regular file" in str(exc), str(exc)
    assert replacements == 1, replacements
    print(json.dumps({"refused": True, "replacements": replacements}))
else:
    raise AssertionError("replacement was admitted as a worksheet")
"""


DOWNLOAD_REPLACEMENT = r"""
import csv
import io
import json
import os
from pathlib import Path
import sys
import threading
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

package = Path(sys.argv[1])
sys.path[:0] = [str(package), str(package / "tests")]
from review_desk_fixture import build
from uwatch import review
from uwatch.review_desk import DeskServer

fixture = build(Path(sys.argv[2]))
selected = Path(fixture["worksheet"])
original = selected.read_bytes()
server = DeskServer(selected)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
opener = build_opener(ProxyHandler({}))
current = next(row for row in fixture["rows"]
               if row["row_state"] == "current" and row["account_no"] == "A")
change = {key: current[key] for key in ("row_id", *review.EDITABLE)}
change.update(review_status="reviewed", reviewer="Fictional receiving",
              note="Keep this exact note after the refused request.")
payload = json.dumps({"snapshot": server.desk.snapshot, "changes": [change]}).encode()
replacements = 0

def replace_before_open(event, args):
    global replacements
    if (event == "open" and replacements == 0 and
            isinstance(args[0], (str, bytes)) and
            os.fsdecode(args[0]) == str(selected)):
        replacements += 1
        selected.unlink()
        os.mkfifo(selected)

def download():
    request = Request(server.origin + "/api/download", data=payload,
                      headers={"Content-Type": "application/json",
                               "X-Review-Token": server.token})
    try:
        response = opener.open(request, timeout=2)
    except HTTPError as exc:
        response = exc
    with response:
        return response.status, response.read()

sys.addaudithook(replace_before_open)
try:
    first_status, first_body = download()
    assert first_status == 409, (first_status, first_body)
    assert "no longer readable" in json.loads(first_body)["error"]
    assert replacements == 1, replacements
    selected.unlink()
    selected.write_bytes(original)
    second_status, second_body = download()
    assert second_status == 200, (second_status, second_body)
    rows = list(csv.DictReader(io.StringIO(second_body.decode("utf-8"), newline="")))
    edited = next(row for row in rows if row["row_id"] == current["row_id"])
    assert edited["note"] == change["note"], edited
    assert review._previous(second_body)
    assert selected.read_bytes() == original
    print(json.dumps({"first_status": first_status, "second_status": second_status,
                      "replacements": replacements, "selected_bytes_unchanged": True}))
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
    assert not thread.is_alive(), "owned listener thread did not stop"
"""


class WorksheetFileKindTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="uwatch-file-kinds-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "Fictional Zoë's desk"
        self.root.mkdir()
        self.selected = self.root / "selected.csv"

    def fingerprint(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns

    def run_child(self, script, *args):
        # subprocess.run kills and reaps the child if the filesystem open blocks.
        result = subprocess.run(
            [sys.executable, "-B", "-c", script, str(PACKAGE), *map(str, args)],
            cwd=self.root, capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_regular_worksheet_retains_exact_utf8_and_crlf_bytes(self):
        raw = 'reviewer,note\r\n"Zoë 李","line one\r\nline two"\r\n'.encode("utf-8")
        self.selected.write_bytes(raw)
        before = self.fingerprint(self.selected)
        self.assertEqual(_read_worksheet(self.selected), raw)
        self.assertEqual(self.fingerprint(self.selected), before)

    def test_regular_worksheet_symlink_retains_target_bytes(self):
        target = self.root / "original.csv"
        raw = b"reviewer,note\r\nFictional,unchanged\r\n"
        target.write_bytes(raw)
        try:
            self.selected.symlink_to(target)
        except (NotImplementedError, OSError) as exc:
            self.skipTest(f"regular symlink unavailable: {exc}")
        before = self.fingerprint(target)
        self.assertEqual(_read_worksheet(self.selected), raw)
        self.assertTrue(self.selected.is_symlink())
        self.assertEqual(self.fingerprint(target), before)

    def test_existing_eight_mib_limit_and_input_bytes_are_preserved(self):
        raw = b"x" * MAX_WORKSHEET_BYTES
        self.selected.write_bytes(raw)
        before = self.fingerprint(self.selected)
        self.assertEqual(_read_worksheet(self.selected), raw)
        self.assertEqual(self.fingerprint(self.selected), before)
        self.selected.write_bytes(raw + b"x")
        before = self.fingerprint(self.selected)
        with self.assertRaisesRegex(ValueError, "8 MiB"):
            _read_worksheet(self.selected)
        self.assertEqual(self.fingerprint(self.selected), before)

    def test_directory_is_still_refused_as_a_nonregular_worksheet(self):
        self.selected.mkdir()
        with self.assertRaisesRegex(ValueError, "regular file"):
            _read_worksheet(self.selected)
        self.assertTrue(self.selected.is_dir())
        self.assertEqual(list(self.selected.iterdir()), [])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX named pipes required")
    def test_direct_fifo_and_fifo_symlink_keep_the_existing_refusal(self):
        pipe = self.root / "pipe"
        os.mkfifo(pipe)
        self.selected.symlink_to(pipe)
        script = r"""
import json
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
from uwatch.review_desk import _read_worksheet
for name in sys.argv[2:]:
    try:
        _read_worksheet(Path(name))
    except ValueError as exc:
        assert "regular file" in str(exc), str(exc)
    else:
        raise AssertionError("nonregular worksheet was admitted")
print(json.dumps({"refused": len(sys.argv) - 2}))
"""
        self.assertEqual(self.run_child(script, pipe, self.selected), {"refused": 2})
        self.assertTrue(self.selected.is_symlink())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX named pipes required")
    def test_fifo_replacement_after_path_admission_refuses_without_blocking(self):
        self.selected.write_bytes(b"original regular worksheet\n")
        result = self.run_child(OPEN_REPLACEMENT, self.selected, "fifo")
        self.assertEqual(result, {"refused": True, "replacements": 1})

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX named pipes required")
    def test_fifo_symlink_replacement_after_path_admission_refuses_without_blocking(self):
        self.selected.write_bytes(b"original regular worksheet\n")
        result = self.run_child(OPEN_REPLACEMENT, self.selected, "symlink")
        self.assertEqual(result, {"refused": True, "replacements": 1})

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX named pipes required")
    def test_saved_download_refuses_replaced_file_then_recovers_with_same_edits(self):
        result = self.run_child(DOWNLOAD_REPLACEMENT, self.root / "fixture")
        self.assertEqual(result, {"first_status": 409, "second_status": 200,
                                  "replacements": 1, "selected_bytes_unchanged": True})


if __name__ == "__main__":
    unittest.main()
