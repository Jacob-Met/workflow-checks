"""Independent receiving from the frozen calendar contract; no author tests imported."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source" / "pt_auth"
sys.path.insert(0, str(SOURCE))
from ptauth import worklist_calendar as target

FIXED = datetime(2026, 12, 31, 23, 30, 19, tzinfo=timezone(timedelta(hours=-7)))
ARTIFACTS = ROOT / "actual-files"
ARTIFACTS.mkdir(exist_ok=True)


def item(identifier="review-a", *, deadline="2024-02-29", clinic="Synthetic clinic", priority="P1"):
    return {
        "key": f"{identifier}|review-payer|review-auth",
        "patient_id": identifier, "patient_name": "Synthetic receiver",
        "clinic": clinic, "payer_id": "review-payer", "payer_name": "Fictional payer",
        "auth_no": "review-auth", "priority": priority, "submit_by": deadline,
        "auth_end": "2027-02-28", "next_visit": "2026-12-21",
        "reasons": ["Recorded reason"], "detail": ["Recorded detail"],
        "checklist": ["Recorded checklist"], "evidence": ["source.csv: row 3"],
    }


def report(rows=None, states=None, zone="America/New_York"):
    return {
        "banner": "SYNTHETIC INDEPENDENT RECEIVER — no real patient data",
        "generated_at": "2020-01-02T03:04:05+00:00", "as_of": "2026-10-08",
        "clinic_timezone": zone, "worklist": rows if rows is not None else [item()],
        "states": states if states is not None else {},
    }


def unescape_text(value):
    output = []
    pos = 0
    while pos < len(value):
        char = value[pos]
        if char == "\\":
            pos += 1
            if pos == len(value):
                raise AssertionError("Incomplete TEXT escape")
            char = value[pos]
            if char in "nN":
                output.append("\n")
            elif char in "\\;,":
                output.append(char)
            else:
                raise AssertionError(f"Unsupported TEXT escape {char!r}")
        else:
            if char in ";,":
                raise AssertionError("Unescaped TEXT delimiter")
            output.append(char)
        pos += 1
    return "".join(output)


def parse_calendar(raw):
    """Parse independently, including physical-byte and component invariants."""
    if not isinstance(raw, bytes) or not raw.endswith(b"\r\n"):
        raise AssertionError("Expected bytes terminated by CRLF")
    physical = raw[:-2].split(b"\r\n")
    if any(not line or b"\r" in line or b"\n" in line or len(line) > 75 for line in physical):
        raise AssertionError("Invalid physical line or octet folding")
    # Each physical piece is independently valid UTF-8, so no code point was split.
    decoded = [line.decode("utf-8") for line in physical]
    logical = []
    for line in decoded:
        if line[0] in " \t":
            if not logical:
                raise AssertionError("Orphan continuation")
            logical[-1] += line[1:]
        else:
            logical.append(line)
    if logical[0] != "BEGIN:VCALENDAR" or logical[-1] != "END:VCALENDAR":
        raise AssertionError("Bad calendar envelope")
    events = []
    current = None
    calendar = {}
    for line in logical[1:-1]:
        if line == "BEGIN:VEVENT":
            if current is not None:
                raise AssertionError("Nested event")
            current = {}
        elif line == "END:VEVENT":
            if current is None:
                raise AssertionError("Unmatched event end")
            events.append(current)
            current = None
        else:
            if line.startswith(("BEGIN:", "END:")):
                raise AssertionError("Unexpected injected component")
            key, value = line.split(":", 1)
            destination = current if current is not None else calendar
            if key in destination:
                raise AssertionError(f"Duplicate property {key}")
            destination[key] = value
    if current is not None:
        raise AssertionError("Unclosed event")
    if calendar.get("VERSION") != "2.0" or not calendar.get("PRODID"):
        raise AssertionError("Missing required calendar metadata")
    for event in events:
        if set(event) != {"UID", "DTSTAMP", "DTSTART;VALUE=DATE", "SUMMARY", "DESCRIPTION", "TRANSP"}:
            raise AssertionError(f"Unexpected event properties {set(event)}")
        if not re.fullmatch(r"[0-9]{8}", event["DTSTART;VALUE=DATE"]):
            raise AssertionError("DTSTART must be an unchanged DATE")
        if not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z", event["DTSTAMP"]):
            raise AssertionError("DTSTAMP must use UTC")
        if event["TRANSP"] != "TRANSPARENT":
            raise AssertionError("A deadline handoff must not reserve availability")
        event["SUMMARY"] = unescape_text(event["SUMMARY"])
        event["DESCRIPTION"] = unescape_text(event["DESCRIPTION"])
    return events, calendar, logical


def export(summary, keys=None, **filters):
    plan = target.prepare_calendar(summary, keys, **filters)
    raw = target.render_calendar(plan, now=FIXED)
    events, calendar, logical = parse_calendar(raw)
    return plan, raw, events


def identities(events):
    result = {}
    for event in events:
        fields = [line.removeprefix("Work-item key: ") for line in event["DESCRIPTION"].splitlines()
                  if line.startswith("Work-item key: ")]
        if len(fields) != 1:
            raise AssertionError("Missing or ambiguous preserved work-item key")
        result[fields[0]] = event["UID"]
    return result


def file_hashes(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file() and not path.is_symlink()}


class IndependentCalendarReceiving(unittest.TestCase):
    def test_selected_statuses_and_overlapping_exclusion_reasons(self):
        rows = [item("default"), item("submitted", deadline="2026-03-08"),
                item("approved"), item("not-applicable", deadline=None),
                item("undated", deadline=None)]
        states = {
            rows[1]["key"]: {"state": "submitted", "note": "Awaiting an answer", "at": "original time"},
            rows[2]["key"]: {"state": "approved", "note": ""},
            rows[3]["key"]: {"state": "n/a", "note": ""},
        }
        original = report(rows, states)
        plan, raw, events = export(original)
        self.assertEqual({e["DTSTART;VALUE=DATE"] for e in events}, {"20240229", "20260308"})
        self.assertEqual(set(identities(events)), {rows[0]["key"], rows[1]["key"]})
        metadata = target.calendar_metadata(plan)
        self.assertEqual((metadata["selected"], metadata["events"], len(metadata["excluded"])), (5, 2, 3))
        self.assertEqual((metadata["undated"], metadata["completed_state"]), (2, 2))
        self.assertIn("Staff state: open", events[0]["DESCRIPTION"])
        self.assertIn("Staff state: submitted", events[1]["DESCRIPTION"])
        self.assertIn("Awaiting an answer", events[1]["DESCRIPTION"])
        (ARTIFACTS / "status-selection.ics").write_bytes(raw)
        (ARTIFACTS / "status-selection-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    def test_filter_intersection_and_explicit_no_eligible_result(self):
        rows = [item("a", clinic="North", priority="P1"), item("b", clinic="South", priority="P1"),
                item("c", clinic="North", priority="P2")]
        summary = report(rows)
        plan, _, events = export(summary, [rows[0]["key"], rows[1]["key"]], clinic="North", priority="P1")
        self.assertEqual(plan["selected"], 1)
        self.assertEqual(set(identities(events)), {rows[0]["key"]})
        empty = target.prepare_calendar(summary, [rows[1]["key"]], clinic="North")
        self.assertEqual(empty["selected"], 0)
        with self.assertRaises(target.CalendarInputError):
            target.render_calendar(empty)

    def test_recorded_dates_survive_dst_year_boundaries_and_process_zones(self):
        dates = ["2024-02-29", "2026-03-08", "2026-11-01", "2026-12-31",
                 "2027-01-01", "0001-01-01", "9999-12-31"]
        previous = os.environ.get("TZ")
        try:
            for process_zone in ["UTC0", "EST5EDT", "JST-9"]:
                os.environ["TZ"] = process_zone
                time.tzset()
                with self.subTest(process_zone=process_zone):
                    rows = [item(f"date-{index}", deadline=value) for index, value in enumerate(dates)]
                    _, _, events = export(report(rows, zone="Pacific/Kiritimati"))
                    self.assertEqual([e["DTSTART;VALUE=DATE"] for e in events],
                                     [value.replace("-", "") for value in dates])
        finally:
            if previous is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = previous
            time.tzset()

    def test_missing_date_never_borrows_another_date(self):
        row = item(deadline=None)
        plan = target.prepare_calendar(report([row]))
        self.assertEqual(plan["included"], [])
        self.assertEqual(plan["excluded"][0]["reasons"], ["undated"])
        with self.assertRaises(target.CalendarInputError):
            target.render_calendar(plan)
        self.assertIsNone(row["submit_by"])

    def test_invalid_recorded_dates_do_not_create_events(self):
        for value in ["2026-02-29", "2024-02-30", "2026-13-01", "2026-00-01",
                      "2026-1-01", "20261008", "2026-W41-4", "2026-10-08T00:00:00Z",
                      "", True, 20261008, "0000-01-01", "٢٠٢٦-١٠-٠٨"]:
            with self.subTest(value=value), self.assertRaises(target.CalendarInputError):
                target.prepare_calendar(report([item(deadline=value)]))

    def test_export_timestamp_is_utc_and_distinct_from_report_time(self):
        _, _, events = export(report())
        self.assertEqual(events[0]["DTSTAMP"], "20270101T063019Z")
        self.assertIn("2020-01-02T03:04:05+00:00", events[0]["DESCRIPTION"])
        plan = target.prepare_calendar(report())
        before = int(datetime.now(timezone.utc).timestamp())
        actual, _, _ = parse_calendar(target.render_calendar(plan))
        after = int(datetime.now(timezone.utc).timestamp())
        observed = int(datetime.strptime(actual[0]["DTSTAMP"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).timestamp())
        self.assertLessEqual(before, observed)
        self.assertLessEqual(observed, after)
        with self.assertRaises(target.CalendarInputError):
            target.render_calendar(plan, now=datetime(2026, 1, 1))

    def test_identity_stable_across_date_timestamp_filter_and_report_order(self):
        rows = [item("a"), item("b", deadline="2026-12-31")]
        summary = report(rows)
        first = identities(export(summary)[2])
        summary["worklist"].reverse()
        summary["generated_at"] = "a later recorded generation"
        summary["as_of"] = "2026-12-30"
        summary["worklist"][0]["submit_by"] = "2027-01-01"
        second = identities(export(summary)[2])
        self.assertEqual(first, second)
        only = export(summary, [rows[0]["key"]])[2]
        self.assertEqual(identities(only), {rows[0]["key"]: first[rows[0]["key"]]})
        plan = target.prepare_calendar(summary)
        later, _, _ = parse_calendar(target.render_calendar(plan, now=FIXED + timedelta(days=31)))
        self.assertEqual(identities(later), first)

    def test_distinct_declared_identity_components_do_not_collapse(self):
        original = report()
        uid = export(original)[2][0]["UID"]
        variants = []
        for field, value in [("clinic", "Different clinic"), ("auth_end", "2028-02-29")]:
            case = copy.deepcopy(original)
            case["worklist"][0][field] = value
            variants.append(case)
        case = copy.deepcopy(original)
        case["clinic_timezone"] = "America/Los_Angeles"
        variants.append(case)
        case = report([item("different-record")])
        variants.append(case)
        values = [export(case)[2][0]["UID"] for case in variants]
        self.assertNotIn(uid, values)
        self.assertEqual(len(set(values)), len(values))

    def test_blank_native_identity_context_stays_blank_and_supported(self):
        row = item(clinic="")
        row["patient_name"] = ""
        row["auth_no"] = ""
        row["key"] = f"{row['patient_id']}|{row['payer_id']}|"
        _, _, events = export(report([row]))
        self.assertIn("\nClinic: \n", events[0]["DESCRIPTION"])
        self.assertIn("\nAuthorization: \n", events[0]["DESCRIPTION"])
        self.assertIn("Patient: review-a — \n", events[0]["DESCRIPTION"])

    def test_utf8_octet_folding_and_text_injection_round_trip(self):
        payload = ("é漢🧪: value; next, last\\literal\t" * 55
                   + "\r\nBEGIN:VEVENT\r\nATTENDEE:mailto:injected@example.invalid\nEND:VEVENT")
        row = item("unicode-" + "漢🧪" * 20, clinic=payload)
        row["patient_name"] = payload
        row["payer_name"] = payload
        row["reasons"] = [payload]
        row["detail"] = [payload]
        row["checklist"] = [payload]
        row["evidence"] = [payload]
        original = report([row], {row["key"]: {"state": "submitted", "note": payload}})
        _, raw, events = export(original)
        self.assertEqual(len(events), 1)
        expected = payload.replace("\r\n", "\n").replace("\r", "\n")
        self.assertEqual(events[0]["DESCRIPTION"].count(expected), 8)
        self.assertIn(row["patient_id"], events[0]["SUMMARY"])
        self.assertNotIn(b"\r\nATTENDEE:", raw)
        self.assertEqual(raw.count(b"BEGIN:VEVENT\r\n"), 1)
        self.assertGreater(max(len(line) for line in raw.split(b"\r\n")), 70)
        (ARTIFACTS / "unicode-and-delimiter-roundtrip.ics").write_bytes(raw)

    def test_original_evidence_details_notes_and_context_remain_inspectable(self):
        row = item()
        original = report([row], {row["key"]: {"state": "submitted", "note": "Saved note", "at": "Saved at"}})
        _, _, events = export(original)
        text = events[0]["DESCRIPTION"]
        for field in ["key", "patient_id", "patient_name", "payer_id", "payer_name", "auth_no", "clinic", "priority"]:
            self.assertIn(row[field], text)
        for field in ["reasons", "detail", "checklist", "evidence"]:
            for value in row[field]:
                self.assertIn(value, text)
        for value in ["Saved note", "Saved at", original["banner"], original["clinic_timezone"], original["as_of"]]:
            self.assertIn(value, text)

    def test_caller_data_and_prepared_plan_do_not_change_each_other(self):
        original = report()
        before = copy.deepcopy(original)
        plan = target.prepare_calendar(original)
        target.render_calendar(plan, now=FIXED)
        self.assertEqual(original, before)
        original["worklist"][0]["submit_by"] = "2029-01-01"
        original["worklist"][0]["evidence"].append("later unrelated evidence")
        actual, _, _ = parse_calendar(target.render_calendar(plan, now=FIXED))
        self.assertEqual(actual[0]["DTSTART;VALUE=DATE"], "20240229")
        self.assertNotIn("later unrelated evidence", actual[0]["DESCRIPTION"])

    def test_unknown_staff_state_and_identity_mismatch_refuse(self):
        key = item()["key"]
        for state in ["open", None, {}, {"state": "done"}, {"state": "open", "note": 42}]:
            with self.subTest(state=state), self.assertRaises(target.CalendarInputError):
                target.prepare_calendar(report(states={key: state}))
        wrong = item()
        wrong["key"] = "a different identity"
        with self.assertRaises(target.CalendarInputError):
            target.prepare_calendar(report([wrong]))
        with self.assertRaises(target.CalendarInputError):
            target.prepare_calendar(report([item(), item()]))

    def test_unknown_duplicate_selected_keys_and_content_drift(self):
        original = report()
        for keys in [["absent"], [item()["key"], item()["key"]]]:
            with self.subTest(keys=keys), self.assertRaises(target.CalendarInputError):
                target.prepare_calendar(original, keys)
        first = target.snapshot_token(original)
        original["unrelated_projection"] = {"declared": ["additional report output"]}
        self.assertNotEqual(first, target.snapshot_token(original))
        self.assertEqual(export(original)[2][0]["DTSTART;VALUE=DATE"], "20240229")
        original["states"][item()["key"]] = {"state": "submitted", "note": ""}
        self.assertNotEqual(first, target.snapshot_token(original))

    def test_cli_saved_files_filters_and_current_stamp_without_engine_or_state_write(self):
        rows = [item("north", clinic="North"), item("south", clinic="South", priority="P2"), item("missing", deadline=None)]
        summary = report(rows)
        with tempfile.TemporaryDirectory(prefix="independent-pt-calendar-") as name:
            root = Path(name)
            saved = root / "saved"
            saved.mkdir()
            (saved / "summary.json").write_text(json.dumps({k: v for k, v in summary.items() if k != "states"}))
            before = file_hashes(saved)
            output = root / "selected.ics"
            command = [sys.executable, "-B", "-m", "ptauth", "calendar", "--report", str(saved),
                       "--output", str(output), "--clinic", "North", "--priority", "P1"]
            result = subprocess.run(command, cwd=SOURCE, capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            metadata = json.loads(result.stdout)
            self.assertEqual((metadata["selected"], metadata["events"]), (1, 1))
            events, _, _ = parse_calendar(output.read_bytes())
            self.assertEqual(set(identities(events)), {rows[0]["key"]})
            self.assertEqual(file_hashes(saved), before)
            self.assertFalse((saved / "work_state.json").exists())
            (ARTIFACTS / "actual-cli-selection.ics").write_bytes(output.read_bytes())
            (ARTIFACTS / "actual-cli-stdout.json").write_bytes(result.stdout)
            sentinel = b"EXISTING USER OUTPUT MUST SURVIVE\n"
            output.write_bytes(sentinel)
            repeat = subprocess.run(command, cwd=SOURCE, capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            self.assertNotEqual(repeat.returncode, 0)
            self.assertEqual(output.read_bytes(), sentinel)
            self.assertEqual(file_hashes(saved), before)
            (ARTIFACTS / "actual-cli-no-clobber.stderr").write_bytes(repeat.stderr)

    def test_cli_invalid_summary_does_not_create_output_or_change_saved_inputs(self):
        with tempfile.TemporaryDirectory(prefix="independent-pt-invalid-") as name:
            root = Path(name)
            saved = root / "saved"
            saved.mkdir()
            bad = report([item(deadline="2026-02-30")])
            (saved / "summary.json").write_text(json.dumps({k: v for k, v in bad.items() if k != "states"}))
            (saved / "work_state.json").write_text("{}")
            before = file_hashes(saved)
            output = root / "refused.ics"
            result = subprocess.run([sys.executable, "-B", "-m", "ptauth", "calendar", "--report", str(saved),
                                     "--output", str(output)], cwd=SOURCE, capture_output=True,
                                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
            self.assertEqual(file_hashes(saved), before)
            (ARTIFACTS / "actual-cli-invalid.stderr").write_bytes(result.stderr)

    def test_ambiguous_json_and_incomplete_utf8_refuse_before_output(self):
        for raw in [b'{"worklist":[],"worklist":[1]}', b'{"value":NaN}', b'{"value":Infinity}', b'{"value":"\xff"}']:
            with self.subTest(raw=raw), self.assertRaises(target.CalendarInputError):
                target.decode_json(raw)

    def test_exclusive_output_handles_actual_destination_race_and_cleanup(self):
        with tempfile.TemporaryDirectory(prefix="independent-pt-output-") as name:
            root = Path(name)
            output = root / "calendar.ics"
            raw = export(report())[1]
            real_link = os.link
            sentinel = b"OTHER WRITER\n"
            def race(source, destination):
                Path(destination).write_bytes(sentinel)
                return real_link(source, destination)
            with mock.patch.object(target.os, "link", side_effect=race), self.assertRaises(FileExistsError):
                target.write_calendar(output, raw)
            self.assertEqual(output.read_bytes(), sentinel)
            self.assertEqual([p.name for p in root.iterdir()], ["calendar.ics"])
            output.unlink()
            with mock.patch.object(target.os, "link", side_effect=OSError("independent publication failure")), self.assertRaises(OSError):
                target.write_calendar(output, raw)
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
