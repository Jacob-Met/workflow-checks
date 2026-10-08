"""Native worksheet-to-HTML consumer checks; no external services or test dependencies."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest import mock

from uwatch import review
from uwatch import review_report


class ReportReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.records = {}
        self.active = None
        self.tags = []
        self.attributes = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)
        if tag == "article":
            fields = dict(attrs)
            self.active = fields["id"]
            self.records[self.active] = {"state": fields["data-row-state"], "text": ""}

    def handle_endtag(self, tag):
        if tag == "article":
            self.active = None

    def handle_data(self, data):
        if self.active is not None:
            self.records[self.active]["text"] += data


def finding(number, *, state="current", status="open", account="A-1", key="B-1",
            reviewer="", note="", kind="flag", code="USAGE_SPIKE"):
    row = dict.fromkeys(review.COLUMNS, "")
    row.update(
        review_status=status, reviewer=reviewer, note=note, row_state=state,
        kind=kind, account_no=account, finding_key=key, code=code,
        property="Cypress <Court> & Annex", utility="electric",
        detail='Recorded 150 < 200 units; preserve the "original" description.',
        evidence='["bills.csv:2","accounts.csv:1"]',
        as_of="2026-09-28", eval_from="2026-03-01", data_mode="synthetic",
        row_id=f"{number:032x}", evidence_version=review._digest(["fixture", number]),
    )
    row["finding_id"] = review._identity(row)
    return review._seal(row)


def worksheet(rows, *, mode="synthetic"):
    metadata = {"as_of": "2026-09-28", "eval_from": "2026-03-01", "data_mode": mode}
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=review.COLUMNS, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows([*rows, review._manifest(rows, metadata)])
    return b"\xef\xbb\xbf" + stream.getvalue().encode("utf-8")


class ReviewReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="uwatch-review-report-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "notes <team> & Zoë.csv"
        self.rows = [
            finding(1),
            finding(2, account="A-2", key="B-2", kind="exception", code="NO_BASELINE",
                    status="in_progress", reviewer="Mina", note="Asked for the earlier bill."),
            finding(3, account="A-3", key="B-3", status="reviewed", reviewer="Kai",
                    note="Recorded follow-up; eligibility is unchanged."),
            finding(4, state="changed", status="reviewed", reviewer="Zoë 李 <AP>",
                    note='Old evidence only.\r\nVendor says "credit next month".'),
            finding(5, state="absent", account="A-4", key="B-4", status="in_progress",
                    reviewer="Rae", note="Keep this prior note even if it returns."),
        ]
        self.raw = worksheet(self.rows)
        self.source.write_bytes(self.raw)

    def test_current_and_historical_annotations_remain_separate(self):
        document, result = review_report.render_html(self.raw, self.source.name)
        parsed = ReportReader()
        parsed.feed(document)
        self.assertEqual(result["current"], 3)
        self.assertEqual(result["history"], 2)
        self.assertEqual(result["statuses"], {"open": 1, "in_progress": 1, "reviewed": 1})
        self.assertEqual(len(parsed.records), len(self.rows))
        for row in self.rows:
            record = parsed.records["row-" + row["row_id"]]
            self.assertEqual(record["state"], row["row_state"])
            for field in ("account_no", "finding_key", "code", "property", "utility", "detail",
                          "as_of", "eval_from", "data_mode", "row_id", "finding_id",
                          "evidence_version", "record_sha256"):
                self.assertIn(row[field], record["text"], field)
            for pointer in json.loads(row["evidence"]):
                self.assertIn(pointer, record["text"])
            if row["reviewer"]:
                self.assertIn(row["reviewer"], record["text"])
            if row["note"]:
                self.assertIn(row["note"], record["text"])
        current = parsed.records["row-" + self.rows[0]["row_id"]]["text"]
        self.assertIn("Open", current)
        self.assertNotIn("Old evidence only", current)
        self.assertNotIn("Zoë", current)
        self.assertIn("absence does not establish resolution or payment", document)
        self.assertIn(hashlib.sha256(self.raw).hexdigest(), document)

    def test_native_cli_exports_without_rechecking_or_changing_inputs(self):
        tripwires = """import runpy,socket,subprocess,sys
import uwatch.engine as engine
import uwatch.review as review
import uwatch.synth as synth
def forbidden(*args,**kwargs): raise AssertionError('unexpected producer/external effect')
engine.run=engine.check=engine.load=review.reconcile=synth.generate=forbidden
socket.socket=subprocess.Popen=forbidden
sys.argv=['uwatch',*sys.argv[1:]]
runpy.run_module('uwatch',run_name='__main__')
"""
        output = self.root / "saved notes.html"
        command = [sys.executable]
        if sys.flags.optimize:
            command.append("-O")
        command += ["-B", "-c", tripwires, "review-report", "--worksheet", str(self.source), "--out", str(output)]
        completed = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                                   capture_output=True, text=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stderr, "")
        self.assertIn(hashlib.sha256(self.raw).hexdigest(), completed.stdout)
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(set(self.root.iterdir()), {self.source, output})
        parsed = ReportReader()
        parsed.feed(output.read_bytes().decode("utf-8"))
        self.assertEqual(len(parsed.records), len(self.rows))

    def test_html_keeps_user_text_inert_and_multiline(self):
        note = '<script>alert("review")</script>\r\n<img src="https://invalid.example/x"> & line 2'
        row = finding(6, status="reviewed", reviewer='"><iframe>Zoë 李', note=note)
        raw = worksheet([row])
        document, _ = review_report.render_html(raw, '"><script>worksheet.csv')
        parsed = ReportReader()
        parsed.feed(document)
        record = parsed.records["row-" + row["row_id"]]["text"]
        self.assertIn(note, record)
        self.assertIn(row["reviewer"], record)
        self.assertFalse(set(parsed.tags) & {"script", "iframe", "img", "form", "input", "button"})
        self.assertFalse(any(name.lower().startswith("on") for name, _ in parsed.attributes))
        self.assertTrue(all(not value or value.startswith("#") for name, value in parsed.attributes if name == "href"))
        self.assertIn("white-space:pre-wrap", document)
        self.assertIn("@media print", document)

    def test_empty_native_worksheet_has_explicit_sections(self):
        raw = worksheet([], mode="client_csv")
        self.source.write_bytes(raw)
        output = self.root / "empty.html"
        result = review_report.export_html(self.source, output)
        document = output.read_text(encoding="utf-8")
        self.assertEqual((result["current"], result["history"]), (0, 0))
        self.assertEqual(result["data_mode"], "client_csv")
        self.assertIn("No current findings in this worksheet", document)
        self.assertIn("No prior findings retained in this worksheet", document)
        self.assertIn("SAVED REVIEW", document)
        self.assertNotIn("SYNTHETIC DATA", document)
        self.assertIn("2026-09-28", document)
        self.assertEqual(self.source.read_bytes(), raw)

    def test_invalid_native_worksheets_publish_nothing(self):
        bad_review = finding(7, status="reviewed", reviewer="", note="Missing reviewer")
        inputs = [
            self.raw.replace(b"USAGE_SPIKE", b"ALTERED_CODE", 1),
            worksheet([bad_review]),
            b"\xffnot utf-8",
        ]
        for index, raw in enumerate(inputs):
            with self.subTest(index=index):
                self.source.write_bytes(raw)
                output = self.root / f"invalid-{index}.html"
                before = set(self.root.iterdir())
                with self.assertRaises(ValueError):
                    review_report.export_html(self.source, output)
                self.assertEqual(set(self.root.iterdir()), before)
                self.assertEqual(self.source.read_bytes(), raw)

    def test_existing_destinations_and_source_are_preserved(self):
        existing = self.root / "existing.html"
        existing.write_bytes(b"keep existing")
        directory = self.root / "directory"
        directory.mkdir()
        for output in (existing, self.source, directory):
            with self.subTest(output=output.name):
                with self.assertRaises(ValueError):
                    review_report.export_html(self.source, output)
                self.assertEqual(existing.read_bytes(), b"keep existing")
                self.assertEqual(self.source.read_bytes(), self.raw)
                self.assertTrue(directory.is_dir())
        dangling = self.root / "dangling.html"
        try:
            dangling.symlink_to(self.root / "absent-target.html")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        with self.assertRaises(ValueError):
            review_report.export_html(self.source, dangling)
        self.assertTrue(dangling.is_symlink())
        self.assertFalse((self.root / "absent-target.html").exists())

    def test_publication_failures_leave_incomplete_output_unpublished(self):
        for function in ("fsync", "link"):
            with self.subTest(function=function):
                output = self.root / f"{function}.html"
                before = set(self.root.iterdir())
                with mock.patch.object(review_report.os, function, side_effect=OSError("controlled publication failure")):
                    with self.assertRaises(OSError):
                        review_report.export_html(self.source, output)
                self.assertEqual(set(self.root.iterdir()), before)
                self.assertEqual(self.source.read_bytes(), self.raw)


if __name__ == "__main__":
    unittest.main()
