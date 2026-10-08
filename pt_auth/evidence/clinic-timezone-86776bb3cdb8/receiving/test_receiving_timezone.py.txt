"""Independent clinic-date receiving over actual CLI and loopback HTTP paths."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import pytest

SOURCE = Path(os.environ.get("PT_RECEIVING_SOURCE", Path(__file__).resolve().parents[2]))
PACIFIC = "America/Los_Angeles"
AS_OF = "2026-09-27"


def write_clinic(root, pairs=None):
    """Give each synthetic visit its own date-only, one-day authorization oracle."""
    root.mkdir(parents=True)
    if pairs is None:
        pairs = [("2026-09-29T01:30:00Z", "2026-09-28")]
    schedules = ["visit_id,patient_id,visit_date,clinic,therapist,payer_id,status,visit_type"]
    auths = ["auth_no,patient_id,payer_id,visits_authorized,start_date,end_date,status"]
    patients = ["patient_id,display_name,clinic,primary_payer"]
    for i, (raw, day) in enumerate(pairs):
        patient = f"SYN-{i:04}"
        schedules.append(f"V{i},{patient},{raw},Clinic (synthetic),Test PT,P,scheduled,treatment")
        auths.append(f"A{i},{patient},P,10,{day},{day},approved")
        patients.append(f"{patient},Test Date {i},Clinic (synthetic),P")
    for name, rows in [("schedule.csv", schedules), ("authorizations.csv", auths), ("patients.csv", patients)]:
        (root / name).write_text("\n".join(rows) + "\n", encoding="utf-8")
    (root / "payers.csv").write_text(
        "payer_id,payer_name,requires_auth,reauth_visits_before,reauth_days_before,"
        "turnaround_days,annual_visit_limit,counts_evals,checklist\n"
        "P,Plan (placeholder),Y,0,0,0,,Y,Test note\n", encoding="utf-8",
    )
    return root


def child_env(host="UTC", no_database=False):
    env = dict(os.environ, PYTHONPATH=str(SOURCE / "pt_auth"), TZ=host, PYTHONUNBUFFERED="1")
    if no_database:
        env["PYTHONTZPATH"] = ""
    return env


def run_cli(data, out, zone=None, host="UTC", as_of=AS_OF, no_database=False):
    command = [sys.executable, "-B"]
    if no_database:
        command.append("-S")
    command += ["-m", "ptauth", "run", "--data", str(data), "--out", str(out)]
    if as_of is not None:
        command += ["--as-of", as_of]
    if zone is not None:
        command += ["--clinic-timezone", zone]
    return subprocess.run(command, cwd=SOURCE, env=child_env(host, no_database),
                          capture_output=True, text=True, timeout=8)


def summary(out):
    return json.loads((out / "summary.json").read_text(encoding="utf-8"))


def events(out):
    return [json.loads(line) for line in (out / "audit.jsonl").read_text(encoding="utf-8").splitlines()]


def get_json(base, path="/api/summary", body=None):
    request = Request(base + path, data=None if body is None else json.dumps(body).encode(),
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=2) as response:
        return json.load(response)


@contextmanager
def serve_cli(data, out, tmp_path, zone=None, host="UTC"):
    with socket.socket() as selected:
        selected.bind(("127.0.0.1", 0))
        port = selected.getsockname()[1]
    command = [sys.executable, "-B", "-m", "ptauth", "serve", "--data", str(data),
               "--out", str(out), "--port", str(port)]
    if zone is not None:
        command += ["--clinic-timezone", zone]
    log_path = tmp_path / "serve.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=SOURCE, env=child_env(host), stdout=log, stderr=log)
        base = f"http://127.0.0.1:{port}"
        try:
            deadline = time.monotonic() + 6
            while True:
                if process.poll() is not None:
                    raise AssertionError(log_path.read_text(encoding="utf-8"))
                try:
                    get_json(base)
                    break
                except URLError:
                    if time.monotonic() >= deadline:
                        raise AssertionError("Actual serve CLI did not become ready: " + log_path.read_text())
                    time.sleep(0.02)
            yield base
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)


@pytest.mark.parametrize("host", ["UTC", "Pacific/Kiritimati"])
def test_actual_cli_dst_midnights_and_ambiguous_hours_keep_clinic_dates(tmp_path, host):
    pairs = [
        ("2026-03-08T07:59:59Z", "2026-03-07"),
        ("2026-03-08T08:00:00Z", "2026-03-08"),
        ("2026-03-08T09:59:59Z", "2026-03-08"),
        ("2026-03-08T10:00:00Z", "2026-03-08"),
        ("2026-03-09T06:59:59Z", "2026-03-08"),
        ("2026-03-09T07:00:00Z", "2026-03-09"),
        ("2026-11-01T06:59:59Z", "2026-10-31"),
        ("2026-11-01T07:00:00Z", "2026-11-01"),
        ("2026-11-01T08:30:00Z", "2026-11-01"),
        ("2026-11-01T09:30:00Z", "2026-11-01"),
        ("2026-11-02T07:59:59Z", "2026-11-01"),
        ("2026-11-02T08:00:00Z", "2026-11-02"),
        ("2026-03-08T02:30:00", "2026-03-08"),
        ("2026-11-01T01:30:00", "2026-11-01"),
        ("2026-02-28", "2026-02-28"),
        ("11/1/2026 1:30 AM", "2026-11-01"),
    ]
    data = write_clinic(tmp_path / "data", pairs)
    out = tmp_path / "out"
    result = run_cli(data, out, PACIFIC, host, "2026-01-01")
    assert result.returncode == 0, result.stderr
    value = summary(out)
    assert value["clinic_timezone"] == PACIFIC
    assert value["counts"]["uncovered_scheduled"] == 0, value["uncovered"]
    assert len(value["ledger"]) == len(pairs)
    assert all(row["scheduled"] == 1 for row in value["ledger"])


@pytest.mark.parametrize("host", ["UTC", PACIFIC])
def test_actual_cli_fractional_offset_midnight_has_no_whole_hour_rounding(tmp_path, host):
    pairs = [("2026-09-28T18:14:59Z", "2026-09-28"),
             ("2026-09-28T18:15:00Z", "2026-09-29")]
    data = write_clinic(tmp_path / "data", pairs)
    out = tmp_path / "out"
    result = run_cli(data, out, "Asia/Kathmandu", host)
    assert result.returncode == 0, result.stderr
    assert summary(out)["counts"]["uncovered_scheduled"] == 0
    assert all(row["scheduled"] == 1 for row in summary(out)["ledger"])


def test_actual_cli_auth_instant_end_remains_inclusive_only_on_its_clinic_day(tmp_path):
    data = write_clinic(tmp_path / "data", [("2026-09-28", "2026-09-28"),
                                           ("2026-09-29", "2026-09-28")])
    (data / "authorizations.csv").write_text(
        "auth_no,patient_id,payer_id,visits_authorized,start_date,end_date,status\n"
        "A0,SYN-0000,P,10,2026-09-28T07:00:00Z,2026-09-29T06:59:59Z,approved\n"
        "A1,SYN-0001,P,10,2026-09-28T07:00:00Z,2026-09-29T06:59:59Z,approved\n"
    )
    out = tmp_path / "out"
    result = run_cli(data, out, PACIFIC, "Pacific/Kiritimati")
    assert result.returncode == 0, result.stderr
    value = summary(out)
    assert value["counts"]["uncovered_scheduled"] == 1
    assert [row["visit_id"] for row in value["uncovered"]] == ["V1"]
    assert all(row["start"] == row["end"] == "2026-09-28" for row in value["ledger"])


@pytest.mark.parametrize("cache_kind", [
    "different_named",
    "missing_provenance",
    pytest.param("local_moved_host", marks=pytest.mark.skipif(
        not hasattr(time, "tzset"), reason="Host TZ substitution requires POSIX time.tzset",
    )),
])
def test_actual_serve_refreshes_zone_cache_retaining_reviewed_day_then_reuses_it(tmp_path, cache_kind):
    data = write_clinic(tmp_path / "data")
    out = tmp_path / "out"
    producer_zone = "UTC" if cache_kind != "local_moved_host" else None
    result = run_cli(data, out, producer_zone, "UTC")
    assert result.returncode == 0, result.stderr
    assert summary(out)["counts"]["uncovered_scheduled"] == 1
    if cache_kind == "missing_provenance":
        previous = summary(out)
        previous.pop("clinic_timezone", None)
        (out / "summary.json").write_text(json.dumps(previous), encoding="utf-8")
    zone = None if cache_kind == "local_moved_host" else PACIFIC
    with serve_cli(data, out, tmp_path, zone, PACIFIC) as base:
        current = get_json(base)
        assert current["as_of"] == AS_OF
        assert current["counts"]["uncovered_scheduled"] == 0
        assert current["ledger"][0]["scheduled"] == 1
        if zone:
            assert current["clinic_timezone"] == zone
        assert len(events(out)) == 2
        assert get_json(base) == current
        assert len(events(out)) == 2
        rerun = get_json(base, "/api/run", {"as_of": "2026-09-28", "clinic_timezone": "UTC"})
        assert rerun["as_of"] == "2026-09-28"
        assert rerun["clinic_timezone"] == current["clinic_timezone"]
        assert rerun["counts"]["uncovered_scheduled"] == 0
        with urlopen(base + "/out/digest.html", timeout=2) as response:
            digest = response.read().decode()
        assert current["clinic_timezone"] in digest


def test_actual_serve_keeps_matching_named_cache_across_host_change(tmp_path):
    data = write_clinic(tmp_path / "data")
    out = tmp_path / "out"
    result = run_cli(data, out, "UTC", "UTC")
    assert result.returncode == 0, result.stderr
    before = (out / "audit.jsonl").read_bytes()
    with serve_cli(data, out, tmp_path, "UTC", PACIFIC) as base:
        value = get_json(base)
        assert value["as_of"] == AS_OF
        assert value["counts"]["uncovered_scheduled"] == 1
        assert value["clinic_timezone"] == "UTC"
        assert (out / "audit.jsonl").read_bytes() == before


def test_actual_serve_rejects_zone_before_generation_output_or_busy_port_bind(tmp_path):
    data, out = tmp_path / "absent_data", tmp_path / "absent_out"
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        result = subprocess.run(
            [sys.executable, "-B", "-m", "ptauth", "serve", "--data", str(data),
             "--out", str(out), "--port", str(port), "--clinic-timezone", "Not/A_Zone"],
            cwd=SOURCE, env=child_env(), capture_output=True, text=True, timeout=4,
        )
    assert result.returncode == 2
    assert "clinic time zone" in result.stderr.lower() and "Traceback" not in result.stderr
    assert "Address already in use" not in result.stderr
    assert not data.exists() and not out.exists()


@pytest.mark.parametrize("command", ["run", "serve"])
def test_actual_missing_timezone_database_explains_and_refuses_before_side_effects(tmp_path, command):
    data, out = tmp_path / "absent_data", tmp_path / "absent_out"
    result = subprocess.run(
        [sys.executable, "-B", "-S", "-m", "ptauth", command, "--data", str(data),
         "--out", str(out), "--clinic-timezone", PACIFIC],
        cwd=SOURCE, env=child_env(no_database=True), capture_output=True, text=True, timeout=4,
    )
    assert result.returncode == 2
    assert "tzdata" in result.stderr and "Traceback" not in result.stderr
    assert not data.exists() and not out.exists()


@pytest.mark.parametrize("zone,offset", [("Etc/GMT+12", -12), ("Etc/GMT-14", 14)])
def test_actual_cli_fallback_today_uses_selected_calendar_day(tmp_path, zone, offset):
    data = write_clinic(tmp_path / "data")
    out = tmp_path / "out"
    before = (datetime.now(timezone.utc) + timedelta(hours=offset)).date().isoformat()
    result = run_cli(data, out, zone, "UTC", as_of=None)
    after = (datetime.now(timezone.utc) + timedelta(hours=offset)).date().isoformat()
    assert result.returncode == 0, result.stderr
    assert summary(out)["as_of"] in {before, after}
