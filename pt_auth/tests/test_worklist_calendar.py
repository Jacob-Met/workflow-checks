"""Read the real saved-report, CLI and HTTP boundaries with independent ICS checks.

Run without optional packages:
  python -B -m unittest discover -s tests -p test_worklist_calendar.py -v
The repository's existing pytest runner discovers these tests too.
"""
from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from ptauth import worklist_calendar as cal
from ptauth.web import App, make_handler

PT_ROOT = Path(__file__).resolve().parents[1]
STAMP = datetime(2026, 10, 8, 13, 4, 5, tzinfo=timezone.utc)


def item(number, *, day="2028-02-29", priority="P1", clinic="Clinic North (synthetic)"):
    patient, payer, auth = f"SYN-{number}", "P-SYN", f"AUTH-{number}"
    return {"key": f"{patient}|{payer}|{auth}", "patient_id": patient,
            "patient_name": "Test Calendar " + str(number), "payer_id": payer,
            "payer_name": "Plan (placeholder)", "auth_no": auth,
            "clinic": clinic, "priority": priority, "submit_by": day,
            "auth_end": "2028-03-31", "next_visit": "2028-03-02",
            "reasons": ["REAUTH_BY_DATE"], "detail": ["Recorded native worklist reason"],
            "checklist": ["Progress note", "Plan of care"], "evidence": ["authorizations.csv:row2"]}


def report():
    return {"banner": "SYNTHETIC DATA — NOT REAL PATIENTS", "as_of": "2028-02-20",
            "generated_at": "2028-02-20T08:09:10", "clinic_timezone": "UTC",
            "worklist": [item(1), item(2, day=None), item(3, priority="P2", clinic="Clinic South")],
            "states": {}}


def parse_events(raw):
    """Independent wire oracle: physical octets, unfolding, event properties."""
    assert raw.endswith(b"\r\n") and b"\n" not in raw.replace(b"\r\n", b"")
    physical = raw[:-2].split(b"\r\n")
    assert all(0 < len(line) <= 75 for line in physical)
    logical = []
    for line in physical:
        text = line.decode("utf-8")  # Each physical line must preserve UTF-8 boundaries.
        if text.startswith((" ", "\t")):
            assert logical
            logical[-1] += text[1:]
        else:
            logical.append(text)
    assert logical[0] == "BEGIN:VCALENDAR" and logical[-1] == "END:VCALENDAR"
    events, current = [], None
    for line in logical:
        if line == "BEGIN:VEVENT":
            assert current is None
            current = {}
        elif line == "END:VEVENT":
            assert current is not None
            events.append(current)
            current = None
        elif current is not None:
            key, value = line.split(":", 1)
            assert key not in current, "Unexpected duplicate property"
            current[key] = value
    assert current is None
    return events


def unescape(text):
    return re.sub(r"\\([\\;,nN])", lambda m: "\n" if m[1] in "nN" else m[1], text)


def render(source, keys=None, **filters):
    return cal.render_calendar(cal.prepare_calendar(source, keys, **filters), now=STAMP)


class CalendarFormatTests(unittest.TestCase):
    def test_actual_date_is_all_day_without_invented_time_or_rules(self):
        source = report()
        before = copy.deepcopy(source)
        events = parse_events(render(source))
        self.assertEqual(len(events), 2)
        self.assertEqual([x["DTSTART;VALUE=DATE"] for x in events], ["20280229", "20280229"])
        for event in events:
            self.assertEqual(event["DTSTAMP"], "20261008T130405Z")
            self.assertEqual(event["TRANSP"], "TRANSPARENT")
            self.assertEqual(set(event), {"UID", "DTSTAMP", "DTSTART;VALUE=DATE", "SUMMARY", "DESCRIPTION", "TRANSP"})
        self.assertEqual(source, before)

    def test_dates_at_century_end_and_dst_boundaries_are_not_shifted(self):
        for day in ("0001-01-01", "2000-02-29", "2026-03-08", "2026-11-01", "9999-12-31"):
            for zone in ("UTC", "America/New_York", "Pacific/Kiritimati", "system local (recorded)"):
                with self.subTest(day=day, zone=zone):
                    source = report()
                    source["clinic_timezone"] = zone
                    source["worklist"] = [item(1, day=day)]
                    event, = parse_events(render(source))
                    self.assertEqual(event["DTSTART;VALUE=DATE"], day.replace("-", ""))
                    self.assertIn(zone, unescape(event["DESCRIPTION"]))

    def test_invalid_or_missing_dates_do_not_fall_back_to_next_visit(self):
        for day in ("1900-02-29", "2026-02-29", "2026-04-31", "0000-01-01", "2026-10-08T10:00:00Z", "", 20261008):
            with self.subTest(day=day):
                source = report()
                source["worklist"][0]["submit_by"] = day
                with self.assertRaises(cal.CalendarInputError):
                    render(source)
        source = report()
        del source["worklist"][0]["submit_by"]
        with self.assertRaises(cal.CalendarInputError):
            render(source)

    def test_exclusions_are_explicit_and_counts_can_overlap(self):
        source = report()
        a, b, c = [row["key"] for row in source["worklist"]]
        source["states"] = {a: {"state": "submitted", "note": "sent for staff review"},
                            b: {"state": "n/a"}, c: {"state": "approved"}}
        plan = cal.prepare_calendar(source)
        meta = cal.calendar_metadata(plan)
        self.assertEqual((meta["selected"], meta["events"], meta["undated"], meta["completed_state"]), (3, 1, 1, 2))
        self.assertEqual(meta["excluded"], [
            {"key": b, "patient_id": "SYN-2", "state": "n/a", "reasons": ["undated", "completed_state"]},
            {"key": c, "patient_id": "SYN-3", "state": "approved", "reasons": ["completed_state"]}])
        event, = parse_events(cal.render_calendar(plan, now=STAMP))
        self.assertIn("Staff state: submitted", unescape(event["DESCRIPTION"]))

    def test_selection_uses_canonical_keys_priority_and_exact_clinic(self):
        source = report()
        key = source["worklist"][2]["key"]
        event, = parse_events(render(source, [key], priority="P2", clinic="Clinic South"))
        self.assertIn(key, unescape(event["DESCRIPTION"]))
        for keys in ([], [key, key], ["foreign-key"], "not-an-array", [None]):
            with self.subTest(keys=keys), self.assertRaises(cal.CalendarInputError):
                render(source, keys)
        with self.assertRaises(cal.CalendarInputError):
            render(source, [key], clinic="Clinic south")

    def test_optional_native_patient_name_and_clinic_remain_blank(self):
        source = report()
        source["worklist"][0].update(patient_name="", clinic="")
        event, = parse_events(render(source, clinic=""))
        description = unescape(event["DESCRIPTION"])
        self.assertIn("Patient: SYN-1 — \n", description)
        self.assertIn("Clinic: \n", description)
        self.assertNotIn("Clinic South", description)

    def test_uid_is_stable_across_filter_date_status_and_report_time_changes(self):
        source = report()
        original = parse_events(render(source))[0]["UID"]
        key = source["worklist"][0]["key"]
        source["worklist"][0]["submit_by"] = "2028-03-01"
        source["states"][key] = {"state": "submitted", "note": "changed note"}
        source["as_of"] = "2028-02-21"
        source["generated_at"] = "2028-02-21T01:02:03"
        event, = parse_events(render(source, [key]))
        self.assertEqual(event["UID"], original)
        self.assertEqual(event["DTSTART;VALUE=DATE"], "20280301")
        for kind in ("auth_end", "clinic", "clinic_timezone"):
            changed = copy.deepcopy(source)
            if kind == "clinic_timezone":
                changed[kind] = "America/New_York"
            else:
                changed["worklist"][0][kind] = "2028-04-01" if kind == "auth_end" else "Another clinic"
            self.assertNotEqual(parse_events(render(changed, [key]))[0]["UID"], original)

    def test_utc_export_time_is_actual_aware_input_not_naive_report_time(self):
        source = report()
        plan = cal.prepare_calendar(source)
        zoned = STAMP.astimezone(timezone(timedelta(hours=-7)))
        self.assertEqual(cal.render_calendar(plan, now=zoned), cal.render_calendar(plan, now=STAMP))
        later = cal.render_calendar(plan, now=STAMP + timedelta(seconds=1))
        self.assertEqual(later.replace(b"20261008T130406Z", b"20261008T130405Z"),
                         cal.render_calendar(plan, now=STAMP))
        with self.assertRaises(cal.CalendarInputError):
            cal.render_calendar(plan, now=STAMP.replace(tzinfo=None))

    def test_unicode_escaping_folding_and_source_text_round_trip(self):
        source = report()
        row = source["worklist"][0]
        row["patient_name"] = "Test é😀汉字" * 13
        recorded = "First, semicolon; slash\\literal\\n\r\nSecond line\rThird 😀" * 4
        row["detail"] = [recorded, "END:VEVENT\nBEGIN:VEVENT"]
        source["states"][row["key"]] = {"state": "submitted", "note": recorded, "at": "2028-02-20T10:00:00+00:00"}
        raw = render(source, [row["key"]])
        event, = parse_events(raw)
        description = unescape(event["DESCRIPTION"])
        self.assertIn(recorded.replace("\r\n", "\n").replace("\r", "\n"), description)
        for field in ("patient_name", "payer_name", "key", "clinic"):
            self.assertIn(row[field], description)
        for value in row["checklist"] + row["evidence"]:
            self.assertIn(value, description)
        self.assertEqual(raw.count(b"BEGIN:VEVENT\r\n"), 1)

    def test_malformed_unselected_rows_cannot_be_hidden_by_filtering(self):
        source = report()
        selected = [source["worklist"][0]["key"]]
        bads = [
            lambda s: s["worklist"].append(copy.deepcopy(s["worklist"][0])),
            lambda s: s["worklist"][1].update(key="wrong"),
            lambda s: s["worklist"][1].update(submit_by="not-a-date"),
            lambda s: s["worklist"][1].update(checklist="not-an-array"),
            lambda s: s["worklist"][1].update(patient_name="bad\0value"),
            lambda s: s.update(clinic_timezone=None),
            lambda s: s["states"].update({s["worklist"][1]["key"]: {"state": "pending"}}),
            lambda s: s.update(counts={"unsupported": float("nan")}),
        ]
        for i, change in enumerate(bads):
            changed = copy.deepcopy(source)
            change(changed)
            with self.subTest(case=i), self.assertRaises(cal.CalendarInputError):
                render(changed, selected)

    def test_prepared_export_is_isolated_from_later_caller_mutation(self):
        source = report()
        plan = cal.prepare_calendar(source)
        before = cal.render_calendar(plan, now=STAMP)
        source["worklist"][0]["detail"].append("later mutation")
        source["states"][source["worklist"][0]["key"]] = {"state": "approved"}
        self.assertEqual(cal.render_calendar(plan, now=STAMP), before)


class SavedReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pt-calendar-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report_dir = self.root / "report"
        self.report_dir.mkdir()
        self.source = report()
        self.save()

    def save(self):
        self.summary_path = self.report_dir / "summary.json"
        self.summary_path.write_text(json.dumps({k: v for k, v in self.source.items() if k != "states"}),
                                     encoding="utf-8")
        if self.source["states"]:
            (self.report_dir / "work_state.json").write_text(json.dumps(self.source["states"]), encoding="utf-8")

    def files(self):
        return {p.name: p.read_bytes() for p in self.report_dir.iterdir() if p.is_file()}

    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", "-m", "ptauth", "calendar",
                               "--report", str(self.report_dir), *map(str, args)],
                              cwd=PT_ROOT, capture_output=True, text=True,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})

    def test_existing_report_read_is_nonmutating_and_missing_report_is_not_created(self):
        before = self.files()
        self.assertEqual(cal.load_report(self.report_dir), self.source)
        self.assertEqual(self.files(), before)
        absent = self.root / "missing"
        with self.assertRaises(cal.CalendarInputError):
            cal.load_report(absent)
        self.assertFalse(absent.exists())

    def test_bad_json_duplicate_fields_nonfinite_and_symlink_are_refused(self):
        for raw in (b'{"worklist":[],"worklist":[]}', b'{"bad":NaN}', b'[]', b'\xff', b'{'):
            self.summary_path.write_bytes(raw)
            with self.subTest(raw=raw), self.assertRaises(cal.CalendarInputError):
                cal.load_report(self.report_dir)
        self.summary_path.unlink()
        self.summary_path.symlink_to(self.root / "absent-target")
        with self.assertRaises(cal.CalendarInputError):
            cal.load_report(self.report_dir)
        self.assertFalse((self.root / "absent-target").exists())

    def test_changed_pair_is_refused_at_read_boundary(self):
        original = cal._read
        calls = 0
        def changing(path, **kwargs):
            nonlocal calls
            calls += 1
            value = original(path, **kwargs)
            if calls == 3:
                return value + b"\n"
            return value
        with patch.object(cal, "_read", changing), self.assertRaises(cal.CalendarStaleError):
            cal.load_report(self.report_dir)

    def test_cli_real_output_and_changed_inputs_preserve_saved_files(self):
        first, later = self.root / "first.ics", self.root / "later.ics"
        before = self.files()
        result = self.cli("--output", first)
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        meta = json.loads(result.stdout)
        self.assertEqual((meta["events"], meta["undated"], meta["selected"]), (2, 1, 3))
        self.assertEqual(self.files(), before)
        original = parse_events(first.read_bytes())[0]["UID"]
        self.source["worklist"][0]["submit_by"] = "2028-03-01"
        self.save()
        changed_files = self.files()
        result = self.cli("--output", later, "--key", self.source["worklist"][0]["key"])
        self.assertEqual(result.returncode, 0, result.stderr)
        event, = parse_events(later.read_bytes())
        self.assertEqual((event["UID"], event["DTSTART;VALUE=DATE"]), (original, "20280301"))
        self.assertEqual(self.files(), changed_files)

    def test_cli_refusals_have_no_stdout_or_output_and_preserve_existing_destinations(self):
        destination = self.root / "refused.ics"
        for extra in (("--key", "unknown"), ("--clinic", "not in this report")):
            result = self.cli("--output", destination, *extra)
            self.assertEqual((result.returncode, result.stdout, destination.exists()), (2, "", False))
        destination.write_bytes(b"keep this file exactly")
        result = self.cli("--output", destination)
        self.assertEqual((result.returncode, result.stdout, destination.read_bytes()), (2, "", b"keep this file exactly"))
        result = self.cli("--output", self.summary_path)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(cal.load_report(self.report_dir), self.source)
        self.assertFalse(list(self.root.glob(".ptauth-calendar-*")))

    def test_exclusive_publication_preserves_a_racing_writer_and_cleans_own_stage(self):
        destination = self.root / "race.ics"
        native_link = os.link
        def racer(src, dst):
            Path(dst).write_bytes(b"other writer")
            return native_link(src, dst)
        with patch.object(cal.os, "link", racer), self.assertRaises(FileExistsError):
            cal.write_calendar(destination, render(self.source))
        self.assertEqual(destination.read_bytes(), b"other writer")
        self.assertFalse(list(self.root.glob(".ptauth-calendar-*")))

    def test_real_http_snapshot_download_and_changed_staff_state_refusal(self):
        app = App(self.root / "no-data", self.report_dir, clinic_timezone="UTC")
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=3)))
        base = f"http://127.0.0.1:{server.server_port}"

        def request(path, body=None, raw=None):
            req = urllib.request.Request(base + path, data=raw if raw is not None else
                                         json.dumps(body).encode() if body is not None else None,
                                         headers={"Content-Type": "application/json"})
            try:
                response = urllib.request.urlopen(req, timeout=5)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                return response.status, response.headers.get("Content-Type"), response.read()

        with patch.object(app, "run", side_effect=AssertionError("Calendar must not run report rules")):
            code, _, raw = request("/api/summary")
            self.assertEqual(code, 200)
            ui = json.loads(raw)
            self.assertEqual(ui["calendar_snapshot"], cal.snapshot_token(self.source))
            before = self.files()
            selected = [self.source["worklist"][0]["key"]]
            body = {"snapshot": ui["calendar_snapshot"], "keys": selected}
            code, content_type, content = request("/api/calendar", body)
            self.assertEqual((code, content_type), (200, "text/calendar; charset=utf-8"))
            self.assertEqual(len(parse_events(content)), 1)
            self.assertEqual(self.files(), before)
            self.assertFalse((self.root / "no-data").exists())
            for invalid in ({**body, "keys": []}, {**body, "keys": ["foreign"]},
                            {**body, "keys": selected * 2}, {**body, "keys": None}, [], {"keys": selected}):
                code, _, raw = request("/api/calendar", invalid)
                self.assertEqual(code, 400, raw)
                self.assertIn("error", json.loads(raw))
            self.assertEqual(request("/api/calendar", raw=b'{"keys":[],"keys":[]}')[0], 400)
            self.assertEqual(self.files(), before)

            state_path = self.report_dir / "work_state.json"
            state_path.write_text(json.dumps({selected[0]: {"state": "approved", "note": "changed externally"}}))
            changed_files = self.files()
            code, _, raw = request("/api/calendar", body)
            self.assertEqual(code, 409, raw)
            self.assertEqual(self.files(), changed_files)
            code, _, raw = request("/api/summary")
            fresh = json.loads(raw)
            self.assertNotEqual(fresh["calendar_snapshot"], ui["calendar_snapshot"])
            code, _, raw = request("/api/calendar", {"snapshot": fresh["calendar_snapshot"], "keys": selected})
            self.assertEqual(code, 400, raw)
            self.assertEqual(self.files(), changed_files)

    def test_report_drift_during_render_and_malformed_snapshot_are_refused(self):
        app = App(self.root / "no-data", self.report_dir, clinic_timezone="UTC")
        body = {"snapshot": cal.snapshot_token(self.source), "keys": [self.source["worklist"][0]["key"]]}
        original = cal.render_calendar
        def changing(plan):
            raw = original(plan)
            source = json.loads(self.summary_path.read_text())
            source["generated_at"] = "2028-02-21T00:00:00"
            self.summary_path.write_text(json.dumps(source))
            return raw
        with patch("ptauth.web.render_calendar", changing), self.assertRaises(cal.CalendarStaleError):
            app.calendar(body)
        with self.assertRaises(cal.CalendarInputError):
            app.calendar({"snapshot": None, "keys": []})


if __name__ == "__main__":
    unittest.main()
