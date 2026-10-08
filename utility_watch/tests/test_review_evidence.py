"""Native source-record receiving through the existing producer, desk and HTTP boundary."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
import unittest
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE), str(Path(__file__).parent)]
import test_evidence as original_evidence_tests  # noqa: E402
from review_desk_fixture import build  # noqa: E402
from uwatch import evidence, review, review_evidence  # noqa: E402
from uwatch.review_desk import DeskServer, DeskSnapshot, WorksheetChanged  # noqa: E402


@contextmanager
def running(worksheet, data=None, report=None):
    with DeskServer(worksheet, data=data, report=report) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(5)


class SourceRecordDeskTests(unittest.TestCase):
    def setUp(self):
        # Reuse the original producer's actual BOM/multiline/Unicode/account fixture.
        self.seed = original_evidence_tests.EvidenceTests()
        self.seed.setUp()
        self.addCleanup(self.seed.doCleanups)
        self.root = self.seed.root
        self.worksheet = self.root / "review.csv"
        review.reconcile(self.seed.data, self.seed.report, self.worksheet)
        self.desk = DeskSnapshot(self.worksheet)
        self.row = next(row for row in self.desk.current.values()
                        if row["account_no"] == "A" and row["code"] == "USAGE_SPIKE")
        self.request = {"snapshot": self.desk.snapshot, "row_id": self.row["row_id"]}

    def inspect(self, request=None):
        return self.desk.inspect(self.request if request is None else request,
                                 self.seed.data, self.seed.report)

    def inputs(self):
        return {**self.seed.inputs(), str(self.worksheet): self.worksheet.read_bytes()}

    def test_exact_native_bytes_keep_literal_cells_header_order_and_all_inputs(self):
        before = self.inputs()
        document = self.seed.emit("native-reference.json")
        raw = self.inspect()
        self.assertEqual(raw, (self.root / "native-reference.json").read_bytes())
        self.assertEqual(json.loads(raw), document)
        chosen = next(record for record in document["records"]
                      if record["fields"].get("bill_id") == "SHARED")
        self.assertEqual(chosen["fields"]["memo"], self.seed.bills[1]["memo"])
        self.assertEqual(chosen["columns"], original_evidence_tests.HEADERS["bills.csv"])
        self.assertEqual(document["finding"]["evidence"], json.loads(self.row["evidence"]))
        self.assertEqual(self.inputs(), before)

    def test_same_bill_keys_stay_with_the_selected_account_and_history_refuses(self):
        fixture = build(self.root / "desk-fixture")
        desk = DeskSnapshot(Path(fixture["worksheet"]))
        reports = []
        for account in ("A", "D"):
            row = next(row for row in desk.current.values() if row["account_no"] == account)
            self.assertEqual(row["finding_key"], "SHARED")
            raw = desk.inspect({"snapshot": desk.snapshot, "row_id": row["row_id"]},
                               Path(fixture["data"]), Path(fixture["report"]))
            doc = json.loads(raw)
            self.assertEqual(doc["finding"]["account_no"], account)
            self.assertEqual(doc["finding"]["evidence_version"], row["evidence_version"])
            for record in doc["records"]:
                if "account_no" in record["fields"]:
                    self.assertEqual(record["fields"]["account_no"], account)
            reports.append(raw)
        self.assertNotEqual(*reports)
        for row in fixture["rows"]:
            if row["row_state"] in ("changed", "absent"):
                with self.subTest(state=row["row_state"], row=row["row_id"]):
                    with self.assertRaisesRegex(ValueError, "current saved finding"):
                        desk.inspect({"snapshot": desk.snapshot, "row_id": row["row_id"]},
                                     Path(fixture["data"]), Path(fixture["report"]))

    def test_request_shape_identity_and_unconfigured_source_refuse_before_producer(self):
        cases = [None, [], {}, {"snapshot": self.desk.snapshot},
                 {**self.request, "data": str(self.seed.data)},
                 {**self.request, "changes": []},
                 {**self.request, "row_id": []},
                 {**self.request, "row_id": True},
                 {**self.request, "row_id": "missing"},
                 {**self.request, "snapshot": "another-snapshot"}]
        before = self.inputs()
        with patch.object(evidence, "write_evidence") as producer:
            for request in cases:
                with self.subTest(request=request):
                    with self.assertRaises(ValueError):
                        self.desk.inspect(request, self.seed.data, self.seed.report)
            with self.assertRaisesRegex(ValueError, "--data and --report"):
                self.desk.inspect(self.request, None, None)
            producer.assert_not_called()
        self.assertEqual(self.inputs(), before)

    def test_changed_worksheet_refuses_before_and_after_native_production(self):
        original = self.worksheet.read_bytes()
        self.worksheet.write_bytes(original + b"\n")
        with patch.object(evidence, "write_evidence") as producer:
            with self.assertRaises(WorksheetChanged):
                self.inspect()
            producer.assert_not_called()
        self.worksheet.write_bytes(original)
        actual_writer = evidence.write_evidence

        def change_during(*args, **kwargs):
            result = actual_writer(*args, **kwargs)
            self.worksheet.write_bytes(original + b"\n")
            return result

        sources = self.seed.inputs()
        with patch.object(evidence, "write_evidence", side_effect=change_during):
            with self.assertRaises(WorksheetChanged):
                self.inspect()
        self.assertEqual(self.seed.inputs(), sources)

    def test_new_report_date_is_not_silently_presented_as_the_saved_report(self):
        self.seed.regenerate(as_of=date(2026, 9, 29))
        current = self.seed.emit("new-date-evidence.json")
        self.assertEqual(current["finding"]["evidence_version"], self.row["evidence_version"])
        self.assertNotEqual(current["review"]["as_of"], self.row["as_of"])
        before = self.inputs()
        with self.assertRaises(review_evidence.EvidenceChanged):
            self.inspect()
        self.assertEqual(self.inputs(), before)

    def test_changed_source_context_refuses_even_when_finding_fields_stay_the_same(self):
        self.seed.bills[1]["memo"] += " Revised"
        self.seed.write_csv("bills.csv", self.seed.bills)
        self.seed.regenerate()
        current = self.seed.emit("new-context-evidence.json")
        for key in ("kind", "account_no", "finding_key", "code", "property", "utility", "detail", "finding_id"):
            self.assertEqual(current["finding"][key], self.row[key], key)
        self.assertNotEqual(current["finding"]["evidence_version"], self.row["evidence_version"])
        before = self.inputs()
        with self.assertRaises(review_evidence.EvidenceChanged):
            self.inspect()
        self.assertEqual(self.inputs(), before)

    def test_native_stale_report_refusal_is_not_bypassed(self):
        self.seed.bills[1]["usage"] = "500"
        self.seed.write_csv("bills.csv", self.seed.bills)
        before = self.inputs()
        with self.assertRaisesRegex(ValueError, "report does not match"):
            self.inspect()
        self.assertEqual(self.inputs(), before)

    def test_protected_fields_pointers_and_manifest_metadata_are_bound(self):
        before = self.inputs()
        for key in ("property", "utility", "detail", "finding_id", "evidence_version", "evidence"):
            row = dict(self.row)
            row[key] = "[]" if key == "evidence" else row[key] + " changed"
            with self.subTest(field=key):
                with self.assertRaises(review_evidence.EvidenceChanged):
                    review_evidence.inspect_evidence(self.seed.data, self.seed.report, row, self.desk.manifest)
        metadata = {**self.desk.manifest, "as_of": "2026-09-29"}
        with self.assertRaises(review_evidence.EvidenceChanged):
            review_evidence.inspect_evidence(self.seed.data, self.seed.report, self.row, metadata)
        self.assertEqual(self.inputs(), before)

    def test_whole_response_bound_refuses_without_truncating_or_writing_inputs(self):
        expected = self.inspect()
        before = self.inputs()
        with patch.object(review_evidence, "MAX_EVIDENCE_BYTES", len(expected) - 1):
            with self.assertRaisesRegex(ValueError, "8 MiB"):
                self.inspect()
        with patch.object(review_evidence, "MAX_EVIDENCE_BYTES", len(expected)):
            self.assertEqual(self.inspect(), expected)
        self.assertEqual(self.inputs(), before)

    def test_annotation_download_and_native_reconciliation_survive_inspection(self):
        change = {"row_id": self.row["row_id"], "review_status": "reviewed",
                  "reviewer": "Zoë 李", "note": "  =literal\r\n<script>not executed</script>  "}
        request = {"snapshot": self.desk.snapshot, "changes": [change]}
        before = self.inputs()
        first = self.desk.download(request)
        self.inspect()
        self.assertEqual(self.desk.download(request), first)
        self.assertEqual(self.inputs(), before)
        downloaded = self.root / "download.csv"
        downloaded.write_bytes(first)
        reconciled = self.root / "reconciled.csv"
        review.reconcile(self.seed.data, self.seed.report, reconciled, downloaded)
        result = next(row for row in review._previous(reconciled.read_bytes())
                      if row["row_id"] == self.row["row_id"])
        for field in review.EDITABLE:
            self.assertEqual(result[field], change[field])

    def test_actual_http_returns_native_bytes_and_retains_existing_auth_boundary(self):
        before = self.inputs()
        expected = self.inspect()
        with running(self.worksheet, self.seed.data, self.seed.report) as server:
            with urlopen(server.origin + "/api/worksheet", timeout=5) as response:
                view = json.load(response)
            self.assertTrue(view["source_evidence"])
            headers = {"Content-Type": "application/json", "X-Review-Token": view["token"],
                       "Origin": server.origin}
            body = json.dumps(self.request).encode()
            with urlopen(Request(server.origin + "/api/evidence", data=body, headers=headers), timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get_content_type(), "application/json")
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(response.read(), expected)
            for extra in ({"X-Review-Token": "wrong"}, {"Origin": "http://other.invalid"},
                          {"Host": "other.invalid"}, {"Sec-Fetch-Site": "cross-site"}):
                with self.subTest(headers=extra):
                    with self.assertRaises(HTTPError) as refused:
                        urlopen(Request(server.origin + "/api/evidence", data=body,
                                        headers={**headers, **extra}), timeout=5)
                    self.assertEqual(refused.exception.code, 403)
            with self.assertRaises(HTTPError) as malformed:
                urlopen(Request(server.origin + "/api/evidence", data=b'{"snapshot":1,"snapshot":2}',
                                headers=headers), timeout=5)
            self.assertEqual(malformed.exception.code, 400)
        self.assertEqual(self.inputs(), before)

    def test_cli_requires_paired_configuration_and_default_desk_stays_usable(self):
        for option, value in (("--data", self.seed.data), ("--report", self.seed.report)):
            result = subprocess.run([sys.executable, "-B", "-m", "uwatch", "review-desk",
                                     "--worksheet", str(self.worksheet), option, str(value)],
                                    cwd=PACKAGE, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("both --data and --report", result.stderr)
        with running(self.worksheet) as server:
            with urlopen(server.origin + "/api/worksheet", timeout=5) as response:
                view = json.load(response)
            self.assertFalse(view["source_evidence"])
            self.assertTrue(self.desk.download({"snapshot": self.desk.snapshot, "changes": []}))


if __name__ == "__main__":
    unittest.main()
