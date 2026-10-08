"""Receive the real worksheet -> annotation -> printable-report CLI path.

Uses an explicit saved worksheet and a new output directory. No production
imports, browser, source edits or author-suite invocation are involved.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "git_blob": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()}


def source_pins(package):
    return {str(p.relative_to(package)): pin(p.read_bytes())
            for p in sorted(package.rglob("*")) if p.is_file()}


def rows(raw):
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline="")))


class PrintedRows(HTMLParser):
    """Read labeled fields from actual generated articles as decoded HTML text."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.records = []
        self.record = None
        self.term = None
        self.definition = None
        self.label = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article":
            self.record = {"id": attrs.get("id"), "state": attrs.get("data-row-state"),
                           "fields": {}, "tags": []}
        if self.record is not None:
            self.record["tags"].append(tag)
            if tag == "dt":
                self.term = []
            elif tag == "dd":
                self.definition = []

    def handle_data(self, data):
        if self.term is not None:
            self.term.append(data)
        if self.definition is not None:
            self.definition.append(data)

    def handle_endtag(self, tag):
        if self.record is None:
            return
        if tag == "dt":
            self.label = "".join(self.term or [])
            self.term = None
        elif tag == "dd":
            self.record["fields"][self.label] = "".join(self.definition or [])
            self.definition = None
        elif tag == "article":
            self.records.append(self.record)
            self.record = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", type=Path, required=True)
    ap.add_argument("--worksheet", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    package, worksheet, out = args.package.resolve(), args.worksheet.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / "tmp").mkdir()
    original = worksheet.read_bytes()
    (out / "input-07-reconciled-current.csv").write_bytes(original)
    before = source_pins(package)
    receipt = {
        "schema": "utility-worksheet-printable-coexistence-v1",
        "python": sys.version, "package": str(package), "input": str(worksheet),
        "input_pin": pin(original), "source_before": before,
        "commands": [], "checks": [], "passed": False,
        "author_suite_reexecuted": False, "browser_execution": False,
        "fixture_origin": "Retained independent absent-to-returned receiver's 07-reconciled-current.csv",
    }

    def check(label, value):
        if not value:
            raise AssertionError(label)
        receipt["checks"].append(label)

    def cli(*argv):
        command = [sys.executable, "-B", "-m", "uwatch", *map(str, argv)]
        result = subprocess.run(command, cwd=package,
                                env=dict(os.environ, PYTHONPATH=str(package),
                                         PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(out / "tmp")),
                                capture_output=True, text=True, timeout=30)
        receipt["commands"].append({"argv": command, "cwd": str(package),
                                    "exit": result.returncode, "stdout": result.stdout,
                                    "stderr": result.stderr})
        if result.returncode:
            raise AssertionError(receipt["commands"][-1])
        return result

    try:
        listed = json.loads(cli("worksheet", "list", "--worksheet", worksheet, "--json").stdout)
        check("list validates the retained saved input and exposes its exact digest and complete counts",
              listed["worksheet_sha256"] == pin(original)["sha256"]
              and listed["current"] == 2 and listed["history"] == 1 and listed["shown"] == 2)
        target = next(row for row in listed["rows"] if row["account_no"] == "RECV-A")
        old_rows = rows(original)
        check("selection comes from the native list and is one exact current CSV row",
              sum(row["row_id"] == target["row_id"] and row["row_state"] == "current"
                  for row in old_rows) == 1)
        fields = {"review_status": "in_progress", "reviewer": ' René & "QA" ',
                  "note": 'Printable coexistence: <b>literal</b> & "quoted".\r\nSecond line: 雪 — café\t.'}
        annotated, report = out / "annotated.csv", out / "review.html"
        cli("worksheet", "annotate", "--worksheet", worksheet,
            "--row-id", target["row_id"], "--status", fields["review_status"],
            "--reviewer", fields["reviewer"], "--note", fields["note"], "--out", annotated)
        annotated_raw = annotated.read_bytes()
        annotated_rows = rows(annotated_raw)
        check("annotation changes only the three selected cells; order, protected fields, history, manifest and other reviewers remain exact",
              annotated_rows == [dict(row, **fields) if row["row_id"] == target["row_id"] else row
                                 for row in old_rows])
        check("list and annotation leave the actual retained input byte-exact", worksheet.read_bytes() == original)
        rendered = cli("review-report", "--worksheet", annotated, "--out", report)
        document = report.read_bytes().decode("utf-8")
        parsed = PrintedRows()
        parsed.feed(document)
        expected = {"row-" + row["row_id"]: row for row in annotated_rows if row["row_state"] != "manifest"}
        actual = {row["id"]: row for row in parsed.records}
        check("the owner report renders each current and historical row exactly once with its native identity/state",
              len(parsed.records) == len(actual) == len(expected)
              and set(actual) == set(expected)
              and all(actual[key]["state"] == row["row_state"] for key, row in expected.items()))
        displayed = actual["row-" + target["row_id"]]
        check("the selected row displays the explicit status, reviewer and raw decoded Unicode/multiline note",
              displayed["fields"]["Review status"] == "In progress"
              and displayed["fields"]["Reviewer"] == fields["reviewer"]
              and displayed["fields"]["Note"] == fields["note"])
        check("literal markup is escaped text and introduces no element into the selected article",
              "&lt;b&gt;literal&lt;/b&gt; &amp; &quot;quoted&quot;" in document
              and "b" not in displayed["tags"] and "<b>literal</b>" not in document)
        check("the printable owner retains every other row's reviewer and note text",
              all(actual[key]["fields"]["Reviewer"] == row["reviewer"]
                  and actual[key]["fields"]["Note"] == row["note"]
                  for key, row in expected.items() if row["row_id"] != target["row_id"]))
        digest = pin(annotated_raw)["sha256"]
        check("printable provenance names the annotated worksheet digest and keeps its input byte-exact",
              digest in rendered.stdout and "<code>" + digest + "</code>" in document
              and annotated.read_bytes() == annotated_raw)
        check("all 26 composed source files and the retained peer input remain byte-exact after all three real commands",
              source_pins(package) == before and worksheet.read_bytes() == original and len(before) == 26)
        receipt.update(passed=True, selected_row_id=target["row_id"], explicit_annotation=fields,
                       annotated_pin=pin(annotated_raw), report_pin=pin(report.read_bytes()),
                       actual_cli_children=len(receipt["commands"]), source_after=source_pins(package))
    except BaseException:
        receipt["error"] = traceback.format_exc()
        receipt["source_after"] = source_pins(package)
    finally:
        receipt["files"] = {str(p.relative_to(out)): pin(p.read_bytes())
                            for p in sorted(out.rglob("*")) if p.is_file() and p.name != "receipt.json"}
        serialized = json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
        # Emit before persistence so shared storage cannot erase the observed result.
        print(serialized, end="", flush=True)
        (out / "receipt.json").write_text(serialized, encoding="utf-8")
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
