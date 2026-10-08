"""Clinic-date qualification using authored CSVs and the actual CLI/HTTP path."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import pytest

from ptauth import data, report
from ptauth.web import App, make_handler

AS_OF = date(2026, 9, 27)
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACIFIC = "America/Los_Angeles"


@pytest.fixture
def clinic(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    inputs = {
        "schedule.csv": (
            "visit_id,patient_id,visit_date,clinic,therapist,payer_id,status,visit_type\n"
            "V1,SYN-1,2026-09-29T01:30:00Z,Clinic (synthetic),Test PT,P,scheduled,treatment\n"
        ),
        "authorizations.csv": (
            "auth_no,patient_id,payer_id,visits_authorized,start_date,end_date,status\n"
            "A1,SYN-1,P,10,2026-09-01,2026-09-28,approved\n"
        ),
        "payers.csv": (
            "payer_id,payer_name,requires_auth,reauth_visits_before,reauth_days_before,"
            "turnaround_days,annual_visit_limit,counts_evals,checklist\n"
            "P,Plan (placeholder),Y,0,0,0,,Y,Test note\n"
        ),
        "patients.csv": (
            "patient_id,display_name,clinic,primary_payer\n"
            "SYN-1,Test Zone,Clinic (synthetic),P\n"
        ),
    }
    for name, text in inputs.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


def cli(clinic, out, *args, host_timezone="UTC"):
    return subprocess.run(
        [sys.executable, "-B", "-m", "ptauth", "run", "--data", str(clinic),
         "--out", str(out), "--as-of", AS_OF.isoformat(), *args],
        cwd=PACKAGE_ROOT, env=dict(os.environ, TZ=host_timezone),
        capture_output=True, text=True, timeout=15,
    )


@pytest.mark.parametrize("host_timezone", ["UTC", "America/New_York", PACIFIC])
@pytest.mark.parametrize("clinic_timezone,uncovered", [(PACIFIC, 0), ("UTC", 1)])
def test_cli_named_clinic_zone_determines_coverage_independently_of_host(
    clinic, tmp_path, host_timezone, clinic_timezone, uncovered,
):
    out = tmp_path / "out"
    result = cli(clinic, out, "--clinic-timezone", clinic_timezone, host_timezone=host_timezone)
    assert result.returncode == 0, result.stderr
    summary = json.loads((out / "summary.json").read_text())
    assert summary["counts"]["uncovered_scheduled"] == uncovered
    assert summary["ledger"][0]["scheduled"] == 1 - uncovered
    assert summary["clinic_timezone"] == clinic_timezone
    assert clinic_timezone in result.stdout
    assert clinic_timezone in (out / "digest.html").read_text()
    [event] = [json.loads(line) for line in (out / "audit.jsonl").read_text().splitlines()]
    assert event["clinic_timezone"] == clinic_timezone


def test_auth_timestamps_and_visits_use_the_same_clinic_zone(clinic, tmp_path):
    (clinic / "authorizations.csv").write_text(
        "auth_no,patient_id,payer_id,visits_authorized,start_date,end_date,status\n"
        "A1,SYN-1,P,10,2026-09-28T07:00:00Z,2026-09-29T06:59:00Z,approved\n"
    )
    summary = report.run(clinic, tmp_path / "out", AS_OF, clinic_timezone=PACIFIC)
    assert summary["counts"]["uncovered_scheduled"] == 0
    assert summary["ledger"][0]["start"] == date(2026, 9, 28)
    assert summary["ledger"][0]["end"] == date(2026, 9, 28)


def test_named_zone_uses_historical_offset_and_preserves_dates_without_offsets(clinic):
    path = clinic / "schedule.csv"
    header = path.read_text().splitlines()[0]
    values = [
        ("2026-01-16T07:30:00Z", date(2026, 1, 15)),
        ("2026-07-16T07:30:00Z", date(2026, 7, 16)),
        ("2026-11-01T08:30:00Z", date(2026, 11, 1)),
        ("2026-11-01T09:30:00Z", date(2026, 11, 1)),
        ("2026-03-08T02:30:00", date(2026, 3, 8)),
        ("2026-09-28", date(2026, 9, 28)),
        ("9/28/2026 11:30 PM", date(2026, 9, 28)),
    ]
    rows = [f"V{i},SYN-1,{raw},Clinic (synthetic),Test PT,P,scheduled,treatment" for i, (raw, _) in enumerate(values)]
    path.write_text(header + "\n" + "\n".join(rows) + "\n")
    visits = data.load_visits(path, clinic_tz=ZoneInfo(PACIFIC))
    assert [visit.visit_date for visit in visits] == [expected for _, expected in values]


def test_parallel_reports_keep_their_own_zone_and_legacy_default(clinic, tmp_path, monkeypatch):
    monkeypatch.setattr(data, "CLINIC_TZ", timezone.utc)

    def run_for(zone):
        return report.run(clinic, tmp_path / zone.replace("/", "_"), AS_OF, clinic_timezone=zone)

    with ThreadPoolExecutor(max_workers=2) as pool:
        pacific, utc = list(pool.map(run_for, [PACIFIC, "UTC"]))
    assert pacific["counts"]["uncovered_scheduled"] == 0
    assert utc["counts"]["uncovered_scheduled"] == 1
    assert data.CLINIC_TZ is timezone.utc
    assert data.load_visits(clinic / "schedule.csv")[0].visit_date == date(2026, 9, 29)


@pytest.mark.parametrize("name", ["Not/A_Zone", "", "../UTC", "/etc/passwd"])
def test_invalid_zone_refuses_cli_before_changing_any_report(clinic, tmp_path, name):
    out = tmp_path / "out"
    out.mkdir()
    (out / "summary.json").write_text("previous reviewed summary\n")
    (out / "audit.jsonl").write_text("previous audit\n")
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    result = cli(clinic, out, "--clinic-timezone", name)
    assert result.returncode == 2
    assert "clinic time zone" in result.stderr.lower()
    assert "Traceback" not in result.stderr
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before
    absent = tmp_path / "absent"
    result = cli(clinic, absent, "--clinic-timezone", name)
    assert result.returncode == 2 and not absent.exists()


def test_serve_refuses_invalid_zone_before_creating_or_binding(clinic, tmp_path):
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-B", "-m", "ptauth", "serve", "--data", str(clinic),
         "--out", str(out), "--port", "0", "--clinic-timezone", "Not/A_Zone"],
        cwd=PACKAGE_ROOT, capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 2
    assert "clinic time zone" in result.stderr.lower() and "Traceback" not in result.stderr
    assert not out.exists()


def test_named_zone_controls_default_today_when_no_sample_as_of(clinic, tmp_path, monkeypatch):
    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            instant = datetime(2026, 9, 29, 1, 30, tzinfo=timezone.utc)
            return instant.astimezone(tz)

    monkeypatch.setattr(report, "datetime", FixedClock)
    summary = report.run(clinic, tmp_path / "out", clinic_timezone=PACIFIC)
    assert summary["as_of"] == date(2026, 9, 28)


def test_cached_summary_cannot_speak_for_another_or_unrecorded_zone(clinic, tmp_path):
    out = tmp_path / "out"
    previous = report.run(clinic, out, AS_OF, clinic_timezone="UTC")
    assert previous["counts"]["uncovered_scheduled"] == 1
    app = App(clinic, out, clinic_timezone=PACIFIC)
    current = app.summary()
    assert current["as_of"] == AS_OF.isoformat()
    assert current["clinic_timezone"] == PACIFIC
    assert current["counts"]["uncovered_scheduled"] == 0
    audit_bytes = (out / "audit.jsonl").read_bytes()
    assert app.summary() == current
    assert (out / "audit.jsonl").read_bytes() == audit_bytes
    current.pop("clinic_timezone")
    (out / "summary.json").write_text(json.dumps(current))
    assert app.summary()["clinic_timezone"] == PACIFIC


@contextmanager
def http_app(app):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()


def test_actual_http_run_and_digest_keep_server_clinic_zone(clinic, tmp_path):
    app = App(clinic, tmp_path / "out", clinic_timezone=PACIFIC)
    app.as_of = AS_OF
    with http_app(app) as base:
        with urlopen(base + "/api/summary", timeout=3) as response:
            initial = json.load(response)
        request = Request(base + "/api/run", data=json.dumps({"as_of": "2026-09-28"}).encode(),
                          headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=3) as response:
            rerun = json.load(response)
        with urlopen(base + "/out/digest.html", timeout=3) as response:
            digest = response.read().decode()
    assert initial["clinic_timezone"] == rerun["clinic_timezone"] == PACIFIC
    assert initial["counts"]["uncovered_scheduled"] == rerun["counts"]["uncovered_scheduled"] == 0
    assert rerun["as_of"] == "2026-09-28" and PACIFIC in digest


def test_unavailable_zone_database_explains_how_to_supply_it(clinic, tmp_path, monkeypatch):
    from zoneinfo import ZoneInfoNotFoundError

    def missing(_):
        raise ZoneInfoNotFoundError("authored missing database")

    monkeypatch.setattr(data, "ZoneInfo", missing)
    with pytest.raises(data.InputError, match="tzdata"):
        report.run(clinic, tmp_path / "out", AS_OF, clinic_timezone=PACIFIC)
    assert not (tmp_path / "out").exists()


@pytest.mark.skipif(not os.environ.get("PTAUTH_TEST_CHROME"), reason="set PTAUTH_TEST_CHROME for isolated browser qualification")
def test_actual_browser_displays_clinic_zone_with_coverage_and_digest(clinic, tmp_path):
    from playwright.sync_api import expect, sync_playwright

    app = App(clinic, tmp_path / "out", clinic_timezone=PACIFIC)
    app.as_of = AS_OF
    blocked = []
    with http_app(app) as base, sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.environ["PTAUTH_TEST_CHROME"],
                                             headless=True, args=["--no-sandbox"])
        context = browser.new_context(service_workers="block")
        try:
            def route_request(route):
                if route.request.url.startswith(base + "/"):
                    route.continue_()
                else:
                    blocked.append(route.request.url)
                    route.abort()

            context.route("**/*", route_request)
            page = context.new_page()
            page.goto(base, wait_until="domcontentloaded")
            expect(page.locator("#timezone")).to_have_text("Clinic time zone: " + PACIFIC)
            uncovered = page.locator("#cards .card").filter(has_text="scheduled visits outside auth").locator("b")
            expect(uncovered).to_have_text("0")
            page.get_by_role("button", name="Auth ledger", exact=True).click()
            expect(page.locator("#t-ledger tr").nth(1).locator("td").nth(6)).to_have_text("1")
            page.locator("#asof").fill("2026-09-28")
            with page.expect_response(lambda response: response.url == base + "/api/run") as rerun:
                page.get_by_role("button", name="Run worklist", exact=True).click()
            assert rerun.value.status == 200
            expect(uncovered).to_have_text("0")
            expect(page.locator("#timezone")).to_have_text("Clinic time zone: " + PACIFIC)
            page.get_by_role("button", name="Digest & exports", exact=True).click()
            with page.expect_popup() as popup:
                page.get_by_role("link", name="Daily digest (printable HTML)", exact=True).click()
            digest = popup.value
            expect(digest.locator("body")).to_contain_text("Clinic time zone: " + PACIFIC)
            assert not blocked
            print(json.dumps({
                "browser": browser.version, "clinic_timezone": PACIFIC,
                "uncovered_scheduled": 0, "scheduled_in_auth": 1,
                "rerun_as_of": "2026-09-28", "digest_contains_clinic_zone": True,
                "unhandled_requests": blocked,
                "boundary": "actual isolated browser, local HTTP handler, CSV loaders, report, UI and printable digest",
                "data": "authored synthetic clinic; no existing server, profile, patient or payer",
            }, indent=2))
        finally:
            context.close()
            browser.close()
