"""Uncovered appointment review through real synthetic report, CLI and HTTP paths."""
from __future__ import annotations

import copy
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

SOURCE = Path(os.environ.get("PTAUTH_TEST_SOURCE", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(SOURCE))
from ptauth import data, report
from ptauth.engine import build_worklist
from ptauth.web import App, make_handler
from http.server import ThreadingHTTPServer

AS_OF = date(2026, 10, 8)
FIXTURE = json.loads("{\"authorizations.csv\":\"auth_no,patient_id,payer_id,visits_authorized,start_date,end_date,status\\nAUTH-OLD,SYN-A,PAY-A,1,2026-09-01,2026-09-30,approved\\nAUTH-COVERED,SYN-B,PAY-A,2,2026-10-01,2026-10-31,approved\\n\",\"patients.csv\":\"patient_id,display_name,clinic,primary_payer\\nSYN-A,\\\"Test <A> & \\\"\\\"café\\\"\\\"\\\",Home clinic (synthetic),PAY-A\\nSYN-B,Test Covered,Other clinic (synthetic),PAY-A\\nSYN-C,Test Exempt,Other clinic (synthetic),PAY-N\\n\",\"payers.csv\":\"payer_id,payer_name,requires_auth,reauth_visits_before,reauth_days_before,turnaround_days,annual_visit_limit,counts_evals,checklist\\nPAY-A,\\\"Placeholder <A> & plan\\\",Y,2,7,3,,Y,Auth request\\nPAY-N,No-auth placeholder,N,0,0,0,,Y,\\n\",\"schedule.csv\":\"visit_id,patient_id,visit_date,clinic,therapist,payer_id,status,visit_type\\nV-COVERED-DONE,SYN-A,2026-09-29,Actual clinic <A>,PT-A,PAY-A,completed,treatment\\nV-DONE-1,SYN-A,2026-10-01,Actual clinic <A>,PT-A,PAY-A,completed,treatment\\nV-DONE-2,SYN-A,2026-10-02,Actual clinic <A>,PT-A,PAY-A,completed,treatment\\nV-PAST-SCHEDULED,SYN-A,2026-10-03,Actual clinic <A>,PT-A,PAY-A,scheduled,treatment\\nV-UPCOMING-1,SYN-A,2026-10-08,Actual clinic <A>,PT-A,PAY-A,scheduled,treatment\\nV-UPCOMING-2,SYN-A,2026-10-09,Actual clinic <A>,PT-A,PAY-A,scheduled,treatment\\nV-UPCOMING-3,SYN-A,2026-10-10,Actual clinic <A>,PT-A,PAY-A,scheduled,treatment\\nV-UPCOMING-4,SYN-A,2026-10-11,Actual clinic <A>,PT-A,PAY-A,scheduled,treatment\\nV-UPCOMING-5,SYN-A,2026-10-12,Actual clinic <A>,PT-A,PAY-A,scheduled,treatment\\nV-UPCOMING-6,SYN-A,2026-10-13,Actual clinic <A>,PT-A,PAY-A,scheduled,treatment\\nV-CANCELLED,SYN-A,2026-10-14,Actual clinic <A>,PT-A,PAY-A,cancelled,treatment\\nV-COVERED-FUTURE,SYN-B,2026-10-09,Other clinic (synthetic),PT-B,PAY-A,scheduled,treatment\\nV-EXEMPT,SYN-C,2026-10-10,Other clinic (synthetic),PT-C,PAY-N,scheduled,treatment\\n\"}")
IDS = ["V-DONE-1", "V-DONE-2"] + [f"V-UPCOMING-{i}" for i in range(1, 7)]


class UncoveredReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pt-uncovered-", dir=os.environ.get("PTAUTH_TEST_TMP"))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "data"
        self.inputs.mkdir()
        for name, content in FIXTURE.items():
            (self.inputs / name).write_text(content, encoding="utf-8", newline="")
        self.runs = 0

    def run_report(self, *, zone="UTC"):
        self.runs += 1
        out = self.root / f"out-{self.runs}"
        return report.run(self.inputs, out, AS_OF, clinic_timezone=zone), out

    def append_visit(self, row):
        with (self.inputs / "schedule.csv").open("a", newline="", encoding="utf-8") as stream:
            csv.writer(stream, lineterminator="\n").writerow(row)

    def csv_rows(self, path):
        with path.open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))

    def test_complete_review_matches_the_existing_engine_and_source_rows(self):
        visits = data.load_visits(self.inputs / "schedule.csv", clinic_tz=data.resolve_clinic_timezone("UTC"))
        auths = data.load_auths(self.inputs / "authorizations.csv", clinic_tz=data.resolve_clinic_timezone("UTC"))
        payers = data.load_payers(self.inputs / "payers.csv")
        patients = data.load_patients(self.inputs / "patients.csv")
        worklist, ledgers, uncovered = build_worklist(visits, auths, payers, patients, AS_OF)
        before = copy.deepcopy((visits, auths, payers, patients, worklist, ledgers, uncovered))
        summary, out = self.run_report()
        rows = summary["uncovered_review"]
        self.assertEqual([row["visit_id"] for row in rows], IDS)
        self.assertEqual(len(rows), summary["counts"]["uncovered_scheduled"] + summary["counts"]["unauthorized_done"])
        self.assertEqual((summary["counts"]["uncovered_scheduled"], summary["counts"]["unauthorized_done"],
                          summary["counts"]["past_scheduled"]), (6, 2, 1))
        expected = [v for v in uncovered if v.status == "completed" or (v.status == "scheduled" and v.visit_date >= AS_OF)]
        self.assertCountEqual([row["visit_id"] for row in rows], [v.visit_id for v in expected])
        actual = {row["visit_id"]: row for row in rows}
        for visit in expected:
            row = actual[visit.visit_id]
            self.assertEqual((row["visit_date"], row["status"], row["clinic"], row["therapist"],
                              row["visit_type"], row["evidence"]),
                             (visit.visit_date, visit.status, visit.clinic, visit.therapist,
                              visit.visit_type, visit.source_row))
        self.assertEqual(actual["V-UPCOMING-6"]["evidence"], "schedule.csv:row11")
        self.assertEqual(actual["V-UPCOMING-6"]["clinic"], "Actual clinic <A>")
        self.assertEqual([r["visit_id"] for r in summary["visit_status_review"]], ["V-PAST-SCHEDULED"])
        self.assertEqual((visits, auths, payers, patients, worklist, ledgers, uncovered), before)
        self.assertEqual([r["visit_id"] for r in self.csv_rows(out / "uncovered_visits.csv")], IDS)

    def test_csv_and_print_preserve_all_rows_and_literal_multiline_context(self):
        patients = self.csv_rows(self.inputs / "patients.csv")
        literal_name = 'Test <script>fixture</script> & "café"\nsecond line'
        patients[0]["display_name"] = literal_name
        with (self.inputs / "patients.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(patients[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(patients)
        summary, out = self.run_report()
        rows = self.csv_rows(out / "uncovered_visits.csv")
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(row["patient_name"] == literal_name for row in rows))
        self.assertTrue(all(row["payer_rules_known"] == "True" for row in rows))
        printable = (out / "digest.html").read_text(encoding="utf-8")
        section = printable.split("<h2>Uncovered visits", 1)[1].split("<h2>Visit status review", 1)[0]
        for visit_id in IDS:
            self.assertIn(visit_id, section)
        self.assertIn("&lt;script&gt;fixture&lt;/script&gt;", section)
        self.assertIn("&quot;café&quot;\nsecond line", section)
        self.assertNotIn("<script>fixture</script>", section)
        self.assertIn("Actual clinic &lt;A&gt;", section)
        self.assertEqual(summary["uncovered_review"][0]["patient_name"], literal_name)

    def test_unknown_context_and_future_completed_keep_recorded_facts(self):
        self.append_visit(["V-UNKNOWN", "SYN-UNKNOWN", "2026-10-28", "", "", "PAY-MISSING", "completed", "treatment"])
        summary, out = self.run_report()
        row = next(r for r in summary["uncovered_review"] if r["visit_id"] == "V-UNKNOWN")
        self.assertEqual(row["visit_date"], date(2026, 10, 28))
        self.assertEqual(row["status"], "completed")
        self.assertEqual((row["patient_name"], row["payer_name"], row["clinic"], row["therapist"]), ("", "", "", ""))
        self.assertFalse(row["payer_rules_known"])
        self.assertEqual(row["evidence"], "schedule.csv:row15")
        self.assertEqual(summary["counts"]["unauthorized_done"], 3)
        self.assertIn("Rules unavailable", (out / "digest.html").read_text(encoding="utf-8"))

    def test_latest_source_corrections_clear_review_without_hiding_past_status(self):
        first, _ = self.run_report()
        self.assertEqual(len(first["uncovered_review"]), 8)
        source = {v["visit_id"]: v for v in self.csv_rows(self.inputs / "schedule.csv")}
        for visit_id in IDS:
            row = source[visit_id]
            row["status"] = "cancelled"
            self.append_visit(list(row.values()))
        summary, out = self.run_report()
        self.assertEqual(summary["uncovered_review"], [])
        self.assertEqual(self.csv_rows(out / "uncovered_visits.csv"), [])
        self.assertTrue((out / "uncovered_visits.csv").read_text().startswith("visit_id,visit_date,status,"))
        self.assertEqual([v["visit_id"] for v in summary["visit_status_review"]], ["V-PAST-SCHEDULED"])
        self.assertEqual((summary["counts"]["uncovered_scheduled"], summary["counts"]["unauthorized_done"]), (0, 0))
        self.assertIn("No appointments are in this review", (out / "digest.html").read_text())

    def test_clinic_timezone_already_controls_the_review_date(self):
        try:
            data.resolve_clinic_timezone("America/Los_Angeles")
        except ValueError:
            self.skipTest("IANA America/Los_Angeles data is unavailable")
        rows = self.csv_rows(self.inputs / "schedule.csv")
        with (self.inputs / "schedule.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerow(dict(zip(rows[0], ["V-ZONE", "SYN-A", "2026-10-08T01:30:00Z",
                                               "Actual clinic <A>", "PT-A", "PAY-A", "scheduled", "treatment"])))
        utc, _ = self.run_report()
        pacific, _ = self.run_report(zone="America/Los_Angeles")
        self.assertEqual([v["visit_id"] for v in utc["uncovered_review"]], ["V-ZONE"])
        self.assertEqual(utc["uncovered_review"][0]["visit_date"], AS_OF)
        self.assertEqual(pacific["uncovered_review"], [])
        self.assertEqual(pacific["counts"]["uncovered_scheduled"], 0)
        self.assertEqual(pacific["visit_status_review"][0]["visit_date"], date(2026, 10, 7))
        self.assertEqual(pacific["clinic_timezone"], "America/Los_Angeles")

    def test_older_printable_summary_requests_rerun_instead_of_false_zero(self):
        summary, _ = self.run_report()
        legacy = copy.deepcopy(summary)
        legacy.pop("uncovered_review", None)
        legacy.pop("uncovered_review_note", None)
        printable = report.render_digest(legacy)
        self.assertIn("Run worklist to build uncovered-visit details for this saved report.", printable)
        section = printable.split("<h2>Uncovered visits", 1)[1].split("<h2>Visit status review", 1)[0]
        self.assertNotIn("No appointments are in this review", section)

    def test_existing_http_csv_and_staff_states_keep_the_review_independent(self):
        out = self.root / "web-output"
        app = App(self.inputs, out, clinic_timezone="UTC")
        app.as_of = AS_OF
        app.run()
        input_bytes = {p.name: p.read_bytes() for p in self.inputs.iterdir()}
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        opener = build_opener(ProxyHandler({}))
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            def get(route):
                with opener.open(base + route, timeout=5) as response:
                    return response.read()
            before = json.loads(get("/api/summary"))
            exported = get("/out/uncovered_visits.csv")
            self.assertEqual(len(list(csv.DictReader(io.StringIO(exported.decode())))), 8)
            self.assertIn(b'data-t="uncovered"', get("/"))
            key = before["worklist"][0]["key"]
            request = Request(base + "/api/state", data=json.dumps({"key": key, "state": "approved"}).encode(),
                              headers={"Content-Type": "application/json"}, method="POST")
            with opener.open(request, timeout=5) as response:
                states = json.load(response)
            self.assertEqual(states[key]["state"], "approved")
            after = json.loads(get("/api/summary"))
            self.assertEqual(before["uncovered_review"], after["uncovered_review"])
            self.assertEqual(before["counts"], after["counts"])
            self.assertEqual(get("/out/uncovered_visits.csv"), exported)
            self.assertEqual({p.name: p.read_bytes() for p in self.inputs.iterdir()}, input_bytes)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())

    def test_actual_cli_reports_complete_export(self):
        out = self.root / "cli-output"
        command = [sys.executable, "-B"] + (["-O"] if sys.flags.optimize else []) + [
            "-m", "ptauth", "run", "--data", str(self.inputs), "--out", str(out),
            "--as-of", AS_OF.isoformat(), "--clinic-timezone", "UTC"]
        child = subprocess.run(command, cwd=SOURCE, capture_output=True, text=True, timeout=10)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertIn("8 uncovered visits to inspect: ", child.stdout)
        self.assertIn(str(out / "uncovered_visits.csv"), child.stdout)
        self.assertEqual(len(self.csv_rows(out / "uncovered_visits.csv")), 8)

    @unittest.skipUnless(shutil.which("node"), "Node is unavailable for the explicit UI-script receiving check")
    def test_actual_inline_ui_through_node(self):
        _, out = self.run_report()
        env = dict(os.environ, PTAUTH_UI_SOURCE=str(SOURCE / "ptauth/ui.html"),
                   PTAUTH_UI_SUMMARY=str(out / "summary.json"))
        program = Path(__file__).with_name("browser") / "uncovered_review.test.cjs"
        child = subprocess.run([shutil.which("node"), "--test", str(program)], env=env,
                               capture_output=True, text=True, timeout=15)
        self.assertEqual(child.returncode, 0, child.stdout + child.stderr)


if __name__ == "__main__":
    unittest.main()
