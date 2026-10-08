"""Reject ambiguous CSV columns without changing Freight's value or alias rules."""
from __future__ import annotations

import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from freightpkt.ingest import (
    load_invoices,
    load_loads,
    load_telematics,
    load_tracking_stops,
)
from freightpkt.pipeline import run
from freightpkt.synth import generate


class CsvHeaderAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def cases(self):
        return (
            ("loads", load_loads,
             ["load_id", "customer", "carrier", "tractor", "trailer",
              "pod_received", "ratecon_file", "mode"],
             ["L1", "Customer", "Carrier", "T1", "", "N", "RC.txt", "asset"],
             "pod_received", "Y"),
            ("invoices", load_invoices,
             ["invoice_no", "load_id", "carrier", "invoice_date",
              "invoice_total", "line_code", "line_amount"],
             ["I1", "L1", "Carrier", "2026-09-01", "100.00", "LINEHAUL", "100.00"],
             "invoice_total", "900.00"),
            ("telematics", load_telematics,
             ["Vehicle Name", "Address Name", "Event", "Time"],
             ["T1", "Depot", "entry", "2026-09-01T10:00:00Z"],
             "Time", "2026-09-01T11:00:00Z"),
            ("tracking", load_tracking_stops,
             ["Load Number", "Stop Name", "Actual Arrival", "Actual Departure"],
             ["L1", "Depot", "2026-09-01T10:00:00Z", "2026-09-01T12:00:00Z"],
             "Actual Arrival", "2026-09-01T11:00:00Z"),
        )

    def write_csv(self, name, header, rows, *, bom=False):
        path = self.root / (name + ".csv")
        with path.open("w", newline="", encoding="utf-8-sig" if bom else "utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(rows)
        return path

    def expect_header_refusal(self, reader, path, first, second):
        with self.assertRaisesRegex(ValueError, "duplicate CSV header") as caught:
            reader(path)
        message = str(caught.exception)
        self.assertIn(path.name, message)
        self.assertIn(repr(first), message)
        self.assertIn(repr(second), message)

    def test_duplicate_headers_are_refused_by_all_four_csv_readers(self):
        for name, reader, header, row, duplicate, changed in self.cases():
            with self.subTest(reader=name):
                path = self.write_csv(name, header + [duplicate], [row + [changed]])
                self.expect_header_refusal(reader, path, duplicate, duplicate)

    def test_equal_values_do_not_make_duplicate_columns_unambiguous(self):
        for name, reader, header, row, duplicate, _ in self.cases():
            with self.subTest(reader=name):
                path = self.write_csv(
                    name, header + [duplicate], [row + [row[header.index(duplicate)]]]
                )
                self.expect_header_refusal(reader, path, duplicate, duplicate)

    def test_duplicate_headers_are_rejected_even_without_data_rows(self):
        for name, reader, header, _, duplicate, _ in self.cases():
            with self.subTest(reader=name):
                path = self.write_csv(name, header + [duplicate], [])
                self.expect_header_refusal(reader, path, duplicate, duplicate)

    def test_alias_readers_reject_their_existing_strip_lower_collisions(self):
        for name, reader, header, row, duplicate, changed in self.cases()[2:]:
            with self.subTest(reader=name):
                variant = " " + duplicate.swapcase() + " "
                path = self.write_csv(name, header + [variant], [row + [changed]])
                self.expect_header_refusal(reader, path, duplicate, variant)

    def test_fixed_schema_readers_keep_exact_extra_column_names(self):
        name, reader, header, row, _, _ = self.cases()[0]
        path = self.write_csv(
            name, header + ["POD_RECEIVED", " pod_received "], [row + ["Y", "Y"]]
        )
        self.assertFalse(reader(path)[0].pod_received)
        name, reader, header, row, _, _ = self.cases()[1]
        path = self.write_csv(
            name, header + ["INVOICE_TOTAL", " invoice_total "],
            [row + ["900.00", "800.00"]],
        )
        self.assertEqual(reader(path)[0].total_cents, 10000)

    def test_distinct_alias_priority_is_preserved(self):
        name, reader, header, row, _, _ = self.cases()[2]
        path = self.write_csv(
            name, header + ["vehicle", "asset", "Timestamp"],
            [row + ["OTHER-1", "OTHER-2", "2026-09-02T10:00:00Z"]],
        )
        event = reader(path)[0]
        self.assertEqual((event.asset, event.time), ("T1", datetime(2026, 9, 1, 10)))
        name, reader, header, row, _, _ = self.cases()[3]
        path = self.write_csv(
            name, header + ["Load ID", "Arrival Time"],
            [row + ["OTHER-LOAD", "2026-09-02T10:00:00Z"]],
        )
        events = reader(path)
        self.assertEqual([e.asset for e in events], ["L1", "L1"])
        self.assertEqual([e.time for e in events],
                         [datetime(2026, 9, 1, 10), datetime(2026, 9, 1, 12)])

    def test_bom_and_existing_alias_header_normalization_are_preserved(self):
        for name, reader, header, row, _, _ in self.cases():
            with self.subTest(reader=name):
                if name in ("telematics", "tracking"):
                    header = [" " + field.swapcase() + " " for field in header]
                path = self.write_csv(name, header, [row], bom=True)
                result = reader(path)
                self.assertEqual(len(result), 2 if name == "tracking" else 1)
                self.assertIn(path.name, result[0].source_row)

    def test_valid_multiline_invoice_keeps_existing_group_and_money_rules(self):
        name, reader, header, row, _, _ = self.cases()[1]
        first = row[:]
        first[4:] = ["100.00", "LINEHAUL", "70.00"]
        second = row[:]
        second[2:] = [" Carrier ", " 2026-09-01 ", "$100.00", " fuel ", "$30.00"]
        invoice = reader(self.write_csv(name, header, [first, second]))[0]
        self.assertEqual((invoice.invoice_no, invoice.load_id, invoice.total_cents),
                         ("I1", "L1", 10000))
        self.assertEqual([(line.code, line.amount_cents) for line in invoice.lines],
                         [("LINEHAUL", 7000), ("FUEL", 3000)])
        self.assertEqual(invoice.source_row, "invoices.csv:row2")

    def test_quoted_headers_are_checked_as_parsed_csv_fields(self):
        name, reader, header, row, _, _ = self.cases()[0]
        duplicate = "extra,quoted"
        path = self.write_csv(name, header + [duplicate, duplicate], [row + ["a", "b"]])
        self.assertIn('"extra,quoted"', path.read_text())
        self.expect_header_refusal(reader, path, duplicate, duplicate)

    def test_telematics_json_remains_unchanged(self):
        path = self.root / "events.json"
        path.write_text(json.dumps({"data": [{
            "vehicle": {"name": "T1"}, "address": {"name": "Depot"},
            "eventType": "GeofenceEntry", "time": "2026-09-01T10:00:00Z",
        }]}), encoding="utf-8")
        event = load_telematics(path)[0]
        self.assertEqual((event.asset, event.location, event.event, event.time),
                         ("T1", "Depot", "entry", datetime(2026, 9, 1, 10)))
        self.assertEqual(event.source_row, "events.json#data[0]")

    def test_existing_duplicate_load_identity_refusal_is_preserved(self):
        name, reader, header, row, _, _ = self.cases()[0]
        path = self.write_csv(name, header, [row, row])
        with self.assertRaisesRegex(ValueError, r"duplicate load_id L1.*row2.*row3"):
            reader(path)

    def test_ambiguous_pod_refuses_before_replacing_prior_reports(self):
        data, out = self.root / "data", self.root / "out"
        generate(data, 24, 7)
        summary = run(data, out)
        path = data / "loads.csv"
        with path.open(newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh))
        header = rows[0]
        li, pi = header.index("load_id"), header.index("pod_received")
        missing = [row[li] for row in rows[1:] if row[pi] == "N"]
        self.assertEqual(len(missing), 1)
        target = missing[0]
        settlement = next(x for x in summary["settlements"] if x["load_id"] == target)
        self.assertEqual(settlement["status"], "HOLD")
        self.assertIn("MISSING_POD", settlement["hold_reasons"])
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header + ["pod_received"])
            for row in rows[1:]:
                writer.writerow(row + ["Y" if row[li] == target else row[pi]])

        def hashes(root):
            return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(root.rglob("*")) if p.is_file()}

        before_outputs, before_inputs = hashes(out), hashes(data)
        with self.assertRaisesRegex(ValueError, "duplicate CSV header"):
            run(data, out)
        self.assertEqual(hashes(out), before_outputs)
        self.assertEqual(hashes(data), before_inputs)
        retained = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(next(x for x in retained["settlements"]
                              if x["load_id"] == target)["status"], "HOLD")


if __name__ == "__main__":
    unittest.main()
