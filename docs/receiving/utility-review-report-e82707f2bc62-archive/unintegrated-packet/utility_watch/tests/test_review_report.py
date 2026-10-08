"""Create a fictional, genuinely reconciled worksheet through the existing CLI."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def create_fixture(root: Path, source: Path):
    data = root / "data"
    data.mkdir(parents=True)
    accounts = [dict(account_no=key, property="Fictional Courtyard (synthetic)",
                     utility="gas", vendor="Placeholder Gas", scope="common", unit="", cycle="monthly")
                for key in ("SYN-A", "SYN-B", "SYN-C")]
    write_csv(data / "accounts.csv", list(accounts[0]), accounts)
    bills = []
    for account in accounts:
        for year in (2025, 2026):
            key = account["account_no"]
            bills.append(dict(bill_id=f"{key}-{year}", account_no=key,
                              vendor_invoice_no=f"INV-{key}-{year}",
                              period_start=f"{year}-09-01", period_end=f"{year}-09-30",
                              usage="100", usage_unit="therm", amount="100", late_fee="1" if year == 2026 else "0",
                              prior_balance="0", due_date=f"{year}-10-25", received_date=f"{year}-10-01"))
    write_csv(data / "bills.csv", list(bills[0]), bills)
    write_csv(data / "occupancy.csv", ["property", "unit", "status", "from", "to"], [])
    write_csv(data / "payments.csv", ["payment_id", "account_no", "vendor_invoice_no", "amount", "paid_date"], [])
    (data / "expected.json").write_text(json.dumps({"as_of": "2026-10-05", "eval_from": "2026-09-01",
                                                  "fixture": "authored fictional review-report scenario"}))
    env = dict(os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE="1")
    commands = []

    def cli(*args):
        process = subprocess.run([sys.executable, "-B", "-m", "uwatch", *map(str, args)], env=env,
                                 cwd=source, capture_output=True, text=True, timeout=30)
        commands.append({"args": list(map(str, args)), "returncode": process.returncode,
                         "stdout": process.stdout, "stderr": process.stderr})
        if process.returncode:
            raise AssertionError(commands[-1])

    report = root / "reports"
    cli("run", "--data", data, "--out", report, "--as-of", "2026-10-05", "--eval-from", "2026-09-01")
    first = root / "review-1.csv"
    cli("review", "--data", data, "--report", report / "summary.json", "--out", first)
    with first.open(encoding="utf-8", newline="") as src:
        reader = csv.DictReader(src)
        columns, rows = reader.fieldnames, list(reader)
    assert len(rows) == 4, rows
    for row in rows:
        if row["row_state"] == "manifest":
            continue
        row["review_status"] = "reviewed" if row["account_no"] != "SYN-C" else "in_progress"
        row["reviewer"] = "Alex & Co" if row["account_no"] == "SYN-A" else "Blair"
        row["note"] = "Called placeholder vendor, reference 17.\nSecond line: <b>literal only</b>."
    write_csv(first, columns, rows)
    for bill in bills:
        if bill["bill_id"] == "SYN-B-2026":
            bill["late_fee"] = "2"
        if bill["bill_id"] == "SYN-C-2026":
            bill["late_fee"] = "0"
    write_csv(data / "bills.csv", list(bills[0]), bills)
    cli("run", "--data", data, "--out", report, "--as-of", "2026-10-05", "--eval-from", "2026-09-01")
    second = root / "review-2.csv"
    cli("review", "--data", data, "--report", report / "summary.json", "--previous", first, "--out", second)
    with second.open(encoding="utf-8", newline="") as src:
        final_rows = list(csv.DictReader(src))
    assert [r["row_state"] for r in final_rows] == ["current", "current", "changed", "absent", "manifest"], final_rows
    return second, commands


import shutil
import tempfile
import unittest
from html.parser import HTMLParser

import uwatch

SOURCE = Path(uwatch.__file__).resolve().parent.parent


class Document(HTMLParser):
    def __init__(self, value):
        super().__init__(convert_charrefs=True)
        self.articles = []
        self.tags = []
        self.text = []
        self.active = None
        self.feed(value)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag == "article":
            self.active = {"attrs": attrs, "text": []}
            self.articles.append(self.active)

    def handle_endtag(self, tag):
        if tag == "article":
            self.active = None

    def handle_data(self, data):
        self.text.append(data)
        if self.active is not None:
            self.active["text"].append(data)


class ReviewReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_temp = tempfile.TemporaryDirectory(prefix="uwatch-report-source-")
        cls.fixture = Path(cls.fixture_temp.name)
        cls.worksheet, cls.original_commands = create_fixture(cls.fixture, SOURCE)
        cls.original_bytes = {p: p.read_bytes() for p in cls.fixture.rglob("*") if p.is_file()}

    @classmethod
    def tearDownClass(cls):
        cls.fixture_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="uwatch-report-test-")
        self.root = Path(self.temp.name)
        self.input = self.root / "saved review.csv"
        self.input.write_bytes(self.worksheet.read_bytes())

    def tearDown(self):
        for path, original in self.original_bytes.items():
            self.assertEqual(path.read_bytes(), original, f"original fixture changed: {path}")
        self.temp.cleanup()

    def cli(self, worksheet=None, out=None):
        return subprocess.run(
            [sys.executable, "-B", "-m", "uwatch", "review-report", "--worksheet",
             str(worksheet or self.input), "--out", str(out or self.root / "review.html")],
            cwd=self.root, env=dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE="1"),
            capture_output=True, text=True, timeout=30,
        )

    def parsed(self):
        process = self.cli()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("2 current findings; 2 historical records", process.stdout)
        return Document((self.root / "review.html").read_text()), process

    def rows(self):
        with self.input.open(encoding="utf-8", newline="") as src:
            reader = csv.DictReader(src)
            return reader.fieldnames, list(reader)

    def refused(self, message, out=None):
        before = self.input.read_bytes()
        process = self.cli(out=out)
        self.assertEqual(process.returncode, 2)
        self.assertIn("uwatch: review report error:", process.stderr)
        self.assertIn(message, process.stderr)
        self.assertNotIn("Traceback", process.stderr)
        self.assertEqual(self.input.read_bytes(), before)
        self.assertFalse((self.root / "review.html").exists())
        self.assertEqual(list(self.root.glob(".uwatch-review-report-*")), [])

    def test_native_reconciled_annotations_stay_with_exact_evidence(self):
        document, _ = self.parsed()
        _, rows = self.rows()
        records = [r for r in rows if r["row_state"] != "manifest"]
        self.assertEqual(len(document.articles), len(records))
        for article, row in zip(document.articles, records):
            text = "".join(article["text"])
            for key in ("account_no", "finding_key", "code", "detail", "finding_id",
                        "evidence_version", "row_id", "as_of"):
                self.assertIn(row[key], text)
            self.assertIn(row["row_state"].title(), text)
            self.assertIn(row["review_status"].replace("_", " "), text)
            self.assertIn(row["reviewer"] or "Unassigned", text)
            self.assertIn(row["note"] or "No saved note.", text)
            for pointer in json.loads(row["evidence"]):
                self.assertIn(pointer, text)
        current_b = "".join(document.articles[1]["text"])
        history_b = "".join(document.articles[2]["text"])
        self.assertIn("Unassigned", current_b)
        self.assertNotIn("Called placeholder vendor", current_b)
        self.assertIn("Blair", history_b)
        self.assertIn("Called placeholder vendor", history_b)

    def test_standalone_snapshot_preserves_sources_and_is_deterministic(self):
        before = self.input.read_bytes()
        first = self.cli(out=self.root / "one.html")
        second = self.cli(out=self.root / "two.html")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((self.root / "one.html").read_bytes(), (self.root / "two.html").read_bytes())
        self.assertEqual(self.input.read_bytes(), before)
        text = (self.root / "one.html").read_text()
        self.assertIn(hashlib.sha256(before).hexdigest(), text)
        self.assertIn("snapshot of the validated worksheet", text)
        self.assertIn("does not reopen or verify the original CSV exports", text)
        self.assertFalse((self.root / "data").exists())

    def test_notes_names_and_filename_are_literal_text(self):
        columns, rows = self.rows()
        rows[0]["reviewer"] = 'Élodie & <svg onload="window.bad=1">'
        rows[0]["note"] = '</script><img src="https://example.invalid/probe" onerror="window.bad=2">\n=1+1 & "quoted"'
        write_csv(self.input, columns, rows)
        document, _ = self.parsed()
        literal = "".join(document.articles[0]["text"])
        self.assertIn(rows[0]["reviewer"], literal)
        self.assertIn(rows[0]["note"], literal)
        self.assertEqual(sum(tag == "script" for tag, _ in document.tags), 1)
        self.assertFalse(any(tag in ("img", "svg", "iframe", "object", "embed") for tag, _ in document.tags))
        self.assertFalse(any(key.lower().startswith("on") for _, attrs in document.tags for key in attrs))
        self.assertFalse(any(key in ("src", "href") and value.startswith(("http:", "https:", "//"))
                             for _, attrs in document.tags for key, value in attrs.items()))

    def test_complete_content_is_available_without_javascript(self):
        document, _ = self.parsed()
        self.assertEqual(len(document.articles), 4)
        self.assertTrue(all("hidden" not in a["attrs"] for a in document.articles))
        sections = [attrs for tag, attrs in document.tags if tag == "section"]
        self.assertTrue(sections)
        self.assertTrue(all("hidden" not in attrs for attrs in sections))
        self.assertTrue(any(tag == "noscript" for tag, _ in document.tags))
        self.assertIn("Historical review records", "".join(document.text))
        self.assertIn("absence does not establish resolution", "".join(document.text))

    def test_protected_finding_change_refuses_before_output(self):
        columns, rows = self.rows()
        rows[0]["detail"] = "Changed amount without a native review"
        write_csv(self.input, columns, rows)
        self.refused("protected finding columns changed")

    def test_removed_finding_refuses_complete_worksheet(self):
        columns, rows = self.rows()
        write_csv(self.input, columns, rows[1:])
        self.refused("manifest mismatch")

    def test_duplicate_finding_refuses_complete_worksheet(self):
        columns, rows = self.rows()
        write_csv(self.input, columns, rows[:1] + rows)
        self.refused("invalid or duplicate row identity")

    def test_incomplete_review_annotation_is_rejected(self):
        columns, rows = self.rows()
        rows[0]["note"] = " "
        write_csv(self.input, columns, rows)
        self.refused("a non-open review needs both reviewer and note")

    def test_invalid_utf8_has_clean_error_and_no_partial_report(self):
        self.input.write_bytes(b"\xff")
        self.refused("utf-8")

    def test_existing_destination_and_worksheet_are_preserved(self):
        destination = self.root / "prior.html"
        destination.write_bytes(b"retain this prior report")
        self.refused("existing files cannot be replaced", out=destination)
        self.assertEqual(destination.read_bytes(), b"retain this prior report")
        self.refused("worksheet and existing files cannot be replaced", out=self.input)

    def test_empty_native_worksheet_is_a_readable_report(self):
        data = self.root / "clean-data"
        shutil.copytree(self.fixture / "data", data)
        with (data / "bills.csv").open(encoding="utf-8", newline="") as src:
            reader = csv.DictReader(src)
            columns, rows = reader.fieldnames, list(reader)
        for row in rows:
            row["late_fee"] = "0"
        write_csv(data / "bills.csv", columns, rows)
        env = dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONDONTWRITEBYTECODE="1")
        report = self.root / "clean-engine-report"
        empty = self.root / "empty.csv"
        for args in (("run", "--data", data, "--out", report),
                     ("review", "--data", data, "--report", report / "summary.json", "--out", empty)):
            process = subprocess.run([sys.executable, "-B", "-m", "uwatch", *map(str, args)],
                                     cwd=self.root, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr)
        process = self.cli(worksheet=empty)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("0 current findings; 0 historical records", process.stdout)
        document = Document((self.root / "review.html").read_text())
        self.assertEqual(document.articles, [])
        self.assertIn("This worksheet has no current findings", "".join(document.text))


if __name__ == "__main__":
    unittest.main()
