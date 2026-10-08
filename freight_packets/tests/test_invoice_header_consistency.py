"""Reject contradictory invoice headers before publishing freight reports."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from freightpkt.ingest import load_invoices
from freightpkt.invoice_match import match_invoices

FIELDS = (
    "invoice_no", "load_id", "carrier", "invoice_date", "invoice_total",
    "line_code", "line_amount",
)
PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def invoice_rows():
    header = dict(invoice_no="SYN-INV", load_id="SYN-L1",
                  carrier="Fictional Carrier A", invoice_date="2026-09-01",
                  invoice_total="1100.00")
    return [
        dict(header, line_code="LINEHAUL", line_amount="1000.00"),
        dict(header, line_code="FUEL", line_amount="100.00"),
    ]


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def file_hashes(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def write_cli_inputs(data):
    data.mkdir()
    (data / "ratecons").mkdir()
    write_csv(data / "loads.csv",
              ("load_id", "customer", "carrier", "tractor", "trailer",
               "pod_received", "ratecon_file", "mode"),
              [dict(load_id="SYN-L1", customer="Fictional Shipper",
                    carrier="Fictional Carrier A", tractor="", trailer="",
                    pod_received="yes", ratecon_file="RC-SYN.txt", mode="brokered")])
    (data / "ratecons" / "RC-SYN.txt").write_text(
        "Rate Con # RC-SYN\nLoad # SYN-L1\nCustomer: Fictional Shipper\n"
        "Carrier: Fictional Carrier A\nLinehaul: $1000.00\nFuel: $100.00\n"
        "Detention: $50.00 per hour\n2 hours free\n"
        "billed in 15 minute increments\n15 minute late grace\n"
        "PICKUP: Fictional Dock | Appt: 2026-09-01 10:00\n", encoding="utf-8")
    write_csv(data / "tracking.csv",
              ("load number", "stop name", "actual arrival", "actual departure"),
              [{"load number": "SYN-L1", "stop name": "Fictional Dock",
                "actual arrival": "2026-09-01 10:00",
                "actual departure": "2026-09-01 11:00"}])
    write_csv(data / "fines_schedule.csv",
              ("code", "description", "amount", "applies_to"),
              [dict(code="MISSING_PICKUP_PHOTOS", description="Authored fixture",
                    amount="100.00", applies_to="brokered")])
    write_csv(data / "documents.csv", ("load_id", "doc_type", "received_at"), [])
    write_csv(data / "disputes.csv", ("load_id", "fine_code", "received_at", "reason"),
              [dict(load_id="SYN-L1", fine_code="MISSING_PICKUP_PHOTOS",
                    received_at="2026-09-10 12:00", reason="Authored fixture")])
    write_csv(data / "carrier_invoices.csv", FIELDS, invoice_rows())
    (data / "README_SYNTHETIC.txt").write_text("All entities and amounts are invented.\n")


class InvoiceHeaderConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="freight-invoice-headers-")
        self.root = Path(self.temporary.name)
        self.path = self.root / "carrier_invoices.csv"

    def tearDown(self):
        self.temporary.cleanup()

    def conflicting_field(self, field, value):
        for reverse in (False, True):
            with self.subTest(field=field, reverse=reverse):
                rows = invoice_rows()
                rows[1][field] = value
                if reverse:
                    rows.reverse()
                write_csv(self.path, FIELDS, rows)
                before = self.path.read_bytes()
                with self.assertRaises(ValueError) as caught:
                    load_invoices(self.path)
                self.assertIn(field, str(caught.exception))
                self.assertIn("SYN-INV", str(caught.exception))
                self.assertIn("SYN-L1", str(caught.exception))
                self.assertIn("carrier_invoices.csv:row2", str(caught.exception))
                self.assertIn("carrier_invoices.csv:row3", str(caught.exception))
                self.assertEqual(before, self.path.read_bytes())

    def test_conflicting_carrier_is_not_selected_by_row_order(self):
        self.conflicting_field("carrier", "Fictional Carrier B")

    def test_conflicting_invoice_date_cannot_move_dispute_window(self):
        self.conflicting_field("invoice_date", "2026-09-10")

    def test_conflicting_invoice_total_is_not_silently_discarded(self):
        self.conflicting_field("invoice_total", "999.00")

    def test_all_conflicting_fields_and_source_records_are_reported(self):
        rows = invoice_rows()
        rows[1].update(carrier="Fictional Carrier B",
                       invoice_date="2026-09-10", invoice_total="999.00")
        write_csv(self.path, FIELDS, rows)
        with self.assertRaises(ValueError) as caught:
            load_invoices(self.path)
        for field in ("carrier", "invoice_date", "invoice_total"):
            self.assertIn(field, str(caught.exception))
        self.assertIn("carrier_invoices.csv:row2", str(caught.exception))
        self.assertIn("carrier_invoices.csv:row3", str(caught.exception))

    def test_existing_string_and_money_normalization_remains_valid(self):
        rows = invoice_rows()
        rows[0].update(invoice_total="$1,100.00", line_amount="$1,000.00")
        rows[1].update(invoice_no=" SYN-INV ", load_id=" SYN-L1 ",
                       carrier=" Fictional Carrier A ", invoice_date=" 2026-09-01 ",
                       invoice_total=" 1100 ", line_code=" fuel ", line_amount=" 100.00 ")
        write_csv(self.path, FIELDS, rows)
        invoices = load_invoices(self.path)
        self.assertEqual(len(invoices), 1)
        invoice = invoices[0]
        self.assertEqual((invoice.invoice_no, invoice.load_id, invoice.carrier,
                          invoice.invoice_date, invoice.total_cents, invoice.source_row),
                         ("SYN-INV", "SYN-L1", "Fictional Carrier A",
                          "2026-09-01", 110000, "carrier_invoices.csv:row2"))
        self.assertEqual([(line.code, line.amount_cents) for line in invoice.lines],
                         [("LINEHAUL", 100000), ("FUEL", 10000)])

    def test_nonadjacent_lines_preserve_existing_groups_and_duplicate_check(self):
        first, last = invoice_rows()
        other_load = dict(first, load_id="SYN-L2", invoice_date="2026-09-02",
                          invoice_total="25.00", line_amount="25.00")
        other_invoice = dict(first, invoice_no="SYN-OTHER", invoice_total="50.00",
                             line_amount="50.00")
        write_csv(self.path, FIELDS, [first, other_load, other_invoice, last])
        invoices = load_invoices(self.path)
        self.assertEqual([(i.invoice_no, i.load_id, len(i.lines), i.total_cents)
                          for i in invoices],
                         [("SYN-INV", "SYN-L1", 2, 110000),
                          ("SYN-INV", "SYN-L2", 1, 2500),
                          ("SYN-OTHER", "SYN-L1", 1, 5000)])
        flags = match_invoices(invoices, {}, {}, {})
        self.assertEqual([(f.invoice_no, f.load_id) for f in flags
                          if f.code == "DUPLICATE_INVOICE"],
                         [("SYN-INV", "SYN-L1"), ("SYN-INV", "SYN-L2")])

    def test_nonadjacent_conflict_identifies_first_and_current_record(self):
        first, last = invoice_rows()
        other = dict(first, invoice_no="SYN-OTHER", invoice_total="25.00",
                     line_amount="25.00")
        last["invoice_date"] = "2026-09-10"
        write_csv(self.path, FIELDS, [first, other, last])
        with self.assertRaises(ValueError) as caught:
            load_invoices(self.path)
        self.assertIn("carrier_invoices.csv:row2", str(caught.exception))
        self.assertIn("carrier_invoices.csv:row4", str(caught.exception))

    def test_cli_refuses_ambiguous_headers_and_preserves_previous_reports(self):
        data, out = self.root / "data", self.root / "out"
        write_cli_inputs(data)
        command = [sys.executable, "-B", "-m", "freightpkt", "run",
                   "--data", str(data), "--out", str(out)]
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        valid = subprocess.run(command, cwd=PACKAGE_ROOT, env=environment,
                               capture_output=True, timeout=30)
        self.assertEqual(valid.returncode, 0, valid.stderr.decode(errors="replace"))
        summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        settlement = summary["settlements"][0]
        self.assertEqual((settlement["status"], settlement["carrier"],
                          settlement["approved_cents"], settlement["fines_cents"],
                          settlement["net_cents"]),
                         ("READY", "Fictional Carrier A", 110000, 10000, 100000))
        prior_outputs = file_hashes(out)
        self.assertIn("audit.jsonl", prior_outputs)
        self.assertIn("settlement.csv", prior_outputs)
        self.assertIn("summary.json", prior_outputs)
        for field, value in (("carrier", "Fictional Carrier B"),
                             ("invoice_date", "2026-09-10"),
                             ("invoice_total", "999.00")):
            for reverse in (False, True):
                with self.subTest(field=field, reverse=reverse):
                    rows = invoice_rows()
                    rows[1][field] = value
                    if reverse:
                        rows.reverse()
                    write_csv(data / "carrier_invoices.csv", FIELDS, rows)
                    prior_inputs = file_hashes(data)
                    invalid = subprocess.run(command, cwd=PACKAGE_ROOT, env=environment,
                                             capture_output=True, timeout=30)
                    self.assertNotEqual(invalid.returncode, 0)
                    self.assertIn(field, invalid.stderr.decode(errors="replace"))
                    self.assertEqual(file_hashes(data), prior_inputs)
                    self.assertEqual(file_hashes(out), prior_outputs)


if __name__ == "__main__":
    unittest.main()
