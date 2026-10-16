"""Receive Freight CSV rows without silently losing undeclared values."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from freightpkt.ingest import (
    load_invoices,
    load_loads,
    load_telematics,
    load_tracking_stops,
)
from freightpkt.synth import generate


CASES = (
    ("loads.csv", load_loads,
     ["load_id", "customer", "carrier", "tractor", "pod_received"],
     ["L1", "Customer", "Carrier", "T1", "Y"]),
    ("carrier_invoices.csv", load_invoices,
     ["invoice_no", "load_id", "carrier", "invoice_date",
      "invoice_total", "line_code", "line_amount"],
     ["I1", "L1", "Carrier", "2026-09-01", "100.00", "LINEHAUL", "100.00"]),
    ("telematics.csv", load_telematics,
     ["Vehicle Name", "Address Name", "Event", "Time"],
     ["T1", "Depot", "entry", "2026-09-01T10:00:00Z"]),
    ("tracking_stops.csv", load_tracking_stops,
     ["Load Number", "Stop Name", "Actual Arrival", "Actual Departure"],
     ["L1", "Depot", "2026-09-01T10:00:00Z", "2026-09-01T12:00:00Z"]),
)


def file_hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


class CsvRowAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, header, rows, *, bom=False):
        path = self.root / name
        with path.open("w", newline="", encoding="utf-8-sig" if bom else "utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(rows)
        return path

    def test_all_four_readers_refuse_surplus_content(self):
        for name, reader, header, row in CASES:
            with self.subTest(reader=name):
                path = self.write(name, header, [row + ["undeclared value"]])
                before = path.read_bytes()
                with self.assertRaises(ValueError) as caught:
                    reader(path)
                self.assertEqual(
                    str(caught.exception),
                    f"{name}: CSV row ending at line 2 has nonempty values "
                    f"beyond the header in columns {len(header) + 1}",
                )
                self.assertNotIn("undeclared value", str(caught.exception))
                self.assertEqual(path.read_bytes(), before)

    def test_later_surplus_cells_and_whitespace_are_not_hidden_by_empty_cells(self):
        for name, reader, header, row in CASES:
            for extra in ("0", " ", "\t", "quoted, value", "line one\nline two"):
                with self.subTest(reader=name, extra=repr(extra)):
                    path = self.write(name, header, [row + ["", extra, "", "last"]])
                    with self.assertRaises(ValueError) as caught:
                        reader(path)
                    self.assertIn(
                        f"columns {len(header) + 2}, {len(header) + 4}",
                        str(caught.exception),
                    )

    def test_literal_empty_surplus_cells_preserve_the_accepted_records(self):
        for name, reader, header, row in CASES:
            with self.subTest(reader=name):
                path = self.write(name, header, [row])
                original = reader(path)
                self.write(name, header, [row + ["", "", ""]])
                self.assertEqual(reader(path), original)

    def test_named_extra_columns_and_quoted_multiline_fields_remain_accepted(self):
        for name, reader, header, row in CASES:
            with self.subTest(reader=name):
                path = self.write(name, header, [row])
                original = reader(path)
                self.write(name, header + ["Export note"],
                           [row + ["a comma, and\na second line", ""]], bom=True)
                self.assertEqual(reader(path), original)

    def test_physical_line_and_column_after_a_multiline_named_field(self):
        name, reader, header, row = CASES[1]
        path = self.write(name, header + ["Export note"], [
            row + ["first\nsecond"],
            row + ["third\nfourth", "", "surplus"],
        ], bom=True)
        with self.assertRaises(ValueError) as caught:
            reader(path)
        self.assertEqual(
            str(caught.exception),
            "carrier_invoices.csv: CSV row ending at line 5 has nonempty "
            "values beyond the header in columns 10",
        )

    def test_existing_header_refusal_still_precedes_row_admission(self):
        for name, reader, header, row in CASES:
            with self.subTest(reader=name):
                path = self.write(name, header + [header[0]], [row + [row[0], "surplus"]])
                with self.assertRaisesRegex(ValueError, "duplicate CSV header"):
                    reader(path)

    def test_json_telematics_does_not_acquire_csv_shape_rules(self):
        path = self.root / "telematics.json"
        path.write_text(json.dumps({"data": [{
            "vehicle": {"name": "T1"}, "address": {"name": "Depot"},
            "eventType": "GeofenceEntry", "time": "2026-09-01T10:00:00Z",
            "export_note": ["extra", "values"],
        }]}), encoding="utf-8")
        events = load_telematics(path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].source_row, "telematics.json#data[0]")

    def run_cli(self, data, output):
        command = [sys.executable]
        if sys.flags.optimize:
            command.append("-O")
        command.extend(["-m", "freightpkt", "run", "--data", str(data), "--out", str(output)])
        return subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                              capture_output=True, text=True, timeout=30)

    def test_actual_cli_refuses_each_late_malformed_row_and_retains_prior_outputs(self):
        for name, _, _, _ in CASES:
            with self.subTest(input=name):
                data = self.root / name / "data"
                output = self.root / name / "output"
                generate(data, 24, 7)
                accepted = self.run_cli(data, output)
                self.assertEqual(accepted.returncode, 0, accepted.stderr)
                path = data / name
                with path.open(newline="", encoding="utf-8-sig") as fh:
                    rows = list(csv.reader(fh))
                rows[-1].extend(["", "undeclared value"])
                with path.open("w", newline="", encoding="utf-8") as fh:
                    csv.writer(fh).writerows(rows)
                before_inputs, before_outputs = file_hashes(data), file_hashes(output)
                refused = self.run_cli(data, output)
                self.assertNotEqual(refused.returncode, 0)
                self.assertIn(f"{name}: CSV row ending at line", refused.stderr)
                self.assertIn("nonempty values beyond the header", refused.stderr)
                self.assertEqual(file_hashes(data), before_inputs)
                self.assertEqual(file_hashes(output), before_outputs)

    def test_actual_cli_refusal_publishes_no_report_or_audit_for_new_output(self):
        data, output = self.root / "data", self.root / "new-output"
        generate(data, 24, 7)
        path = data / "carrier_invoices.csv"
        with path.open("a", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(CASES[1][3] + ["discarded"])
        refused = self.run_cli(data, output)
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(file_hashes(output), {})


if __name__ == "__main__":
    unittest.main()
