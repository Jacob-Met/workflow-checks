"""Reject ambiguous PT export headers before records or report writes."""
from __future__ import annotations

import csv
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from ptauth import data

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "sample_data"


def csv_bytes(rows, encoding="utf-8"):
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\r\n").writerows(rows)
    return stream.getvalue().encode(encoding)


def files(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*") if p.is_file()
    } if root.exists() else {}


class HeaderAdmission(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pt-csv-headers-")
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def path(self, rows, *, filename="schedule.csv", encoding="utf-8"):
        path = self.root / filename
        path.write_bytes(csv_bytes(rows, encoding))
        return path

    def test_identical_headers_refuse_before_any_row(self):
        path = self.path([["status", "status"], ["completed", "cancelled"]])
        with self.assertRaises(data.InputError) as raised:
            next(data._rows(path))
        message = str(raised.exception)
        self.assertIn("schedule.csv", message)
        self.assertIn("line 1", message)
        self.assertIn("status", message)
        self.assertIn("columns 1 and 2", message)

    def test_existing_normalization_aliases_are_ambiguous(self):
        for first, second in [
            ("Visit Date", "visit_date"),
            (" Patient-ID ", "PATIENT ID"),
            ("requires\tauth", "requires-auth"),
            (" visits--authorized ", "visits_authorized"),
        ]:
            with self.subTest(first=first, second=second):
                path = self.path([[first, "other", second], ["one", "value", "two"]])
                with self.assertRaises(data.InputError) as raised:
                    list(data._rows(path))
                self.assertIn("columns 1 and 3", str(raised.exception))

    def test_header_only_files_refuse_in_every_loader(self):
        for name, loader in [
            ("schedule.csv", data.load_visits),
            ("authorizations.csv", data.load_auths),
            ("payers.csv", data.load_payers),
            ("patients.csv", data.load_patients),
        ]:
            with self.subTest(file=name):
                path = self.path([["unused", "UNUSED"]], filename=name)
                with self.assertRaises(data.InputError):
                    loader(path)

    def test_unused_named_duplicates_also_refuse(self):
        path = self.path([
            ["visit_id", "patient_id", "visit_date", "payer_id", "status", "Extra", "extra"],
            ["V1", "SYN-1", "2026-09-28", "P1", "scheduled", "", ""],
        ])
        with self.assertRaises(data.InputError):
            data.load_visits(path)

    def test_multiline_header_reports_physical_header_end(self):
        path = self.path([["Visit\nDate", "visit_date"], ["first", "second"]])
        with self.assertRaises(data.InputError) as raised:
            list(data._rows(path))
        self.assertIn("line 2", str(raised.exception))
        self.assertIn("columns 1 and 2", str(raised.exception))

    def test_bom_does_not_hide_collision(self):
        path = self.path([["Visit ID", "visit_id"]], encoding="utf-8-sig")
        with self.assertRaises(data.InputError):
            list(data._rows(path))

    def test_blank_trailing_headers_rows_and_source_lines_are_preserved(self):
        path = self.path([
            ["Visit ID", "Patient-ID", "Visit Date", "Payer ID", "Status", "Therapist", "", ""],
            ["V1", "0007", "2026-09-28", "p1", "booked", 'Literal, "name"\nsecond line', "", ""],
            ["", "", "", "", "", "", "", ""],
            ["V2", "0007", "2026-09-29", "p1", "checked out", "Second", "", ""],
        ])
        visits = data.load_visits(path)
        self.assertEqual([v.visit_id for v in visits], ["V1", "V2"])
        self.assertEqual([v.status for v in visits], ["scheduled", "completed"])
        self.assertEqual([v.patient_id for v in visits], ["7", "7"])
        self.assertEqual([v.source_row for v in visits], ["schedule.csv:row3", "schedule.csv:row5"])
        self.assertEqual(visits[0].therapist, 'Literal, "name"\nsecond line')
        self.assertEqual(visits[0].visit_type, "treatment")

    def test_distinct_extra_columns_and_encodings_remain_accepted(self):
        for encoding, name in [("utf-8-sig", "Café 雪"), ("cp1252", "Café – test")]:
            with self.subTest(encoding=encoding):
                path = self.path([
                    ["Patient ID", "Display Name", "Clinic", "Primary Payer", "unknown_one", "unknown-two"],
                    ["0007", name, "North", "p1", "a", "b"],
                ], filename="patients.csv", encoding=encoding)
                patients = data.load_patients(path)
                self.assertEqual(patients["7"].display_name, name)
                self.assertEqual(patients["7"].primary_payer, "P1")

    def test_empty_and_missing_optional_files_keep_existing_meaning(self):
        empty = self.root / "schedule.csv"
        empty.write_bytes(b"")
        self.assertEqual(data.load_visits(empty), [])
        self.assertEqual(data.load_patients(self.root / "missing-patients.csv"), {})

    def test_cli_refusal_keeps_report_and_inputs_for_all_four_files(self):
        cases = [
            ("schedule.csv", "Status", "cancelled"),
            ("authorizations.csv", "Visits-Authorized", "100"),
            ("payers.csv", " Requires Auth ", "N"),
            ("patients.csv", "patient_id", "SYN-ALIAS"),
        ]
        for number, (name, header, value) in enumerate(cases):
            for existing in (False, True):
                with self.subTest(file=name, existing=existing):
                    case = self.root / f"run-{number}-{existing}"
                    inputs, output = case / "data", case / "out"
                    shutil.copytree(SAMPLES, inputs)
                    path = inputs / name
                    with path.open(encoding="utf-8-sig", newline="") as stream:
                        rows = list(csv.reader(stream))
                    rows[0].append(header)
                    for row in rows[1:]:
                        if any(row):
                            row.append(value)
                    path.write_bytes(csv_bytes(rows))
                    if existing:
                        output.mkdir()
                        for filename in ["summary.json", "digest.html", "audit.jsonl", "unrelated.bin"]:
                            (output / filename).write_bytes(b"keep previous report\x00\r\n")
                    input_before, output_before = files(inputs), files(output)
                    result = subprocess.run(
                        [sys.executable, "-B", "-m", "ptauth", "run", "--data", str(inputs),
                         "--out", str(output), "--as-of", "2026-09-28"],
                        cwd=ROOT, capture_output=True, text=True, timeout=20,
                        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    )
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertIn(name, result.stderr)
                    self.assertIn("columns", result.stderr)
                    self.assertIn("no outputs were written", result.stderr)
                    self.assertEqual(files(inputs), input_before)
                    self.assertEqual(files(output), output_before)
                    self.assertEqual(output.exists(), existing)


if __name__ == "__main__":
    unittest.main()
