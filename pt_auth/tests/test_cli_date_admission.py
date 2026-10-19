"""An explicit review date must never silently select the default date."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def cli(cwd, *arguments):
    environment = os.environ.copy()
    environment.update(
        PYTHONPATH=str(PACKAGE_ROOT),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONIOENCODING="utf-8",
    )
    return subprocess.run(
        [sys.executable, "-m", "ptauth", *map(str, arguments)],
        cwd=cwd,
        env=environment,
        capture_output=True,
        encoding="utf-8",
        timeout=20,
    )


def snapshot(root):
    result = {}
    for path in [root, *sorted(root.rglob("*"))]:
        info = path.stat()
        result[str(path.relative_to(root))] = (
            info.st_ino,
            info.st_mode,
            info.st_mtime_ns,
            path.read_bytes() if path.is_file() else None,
        )
    return result


def assert_usage_error(result):
    assert result.returncode == 2, result
    assert result.stdout == "", result
    assert "--as-of" in result.stderr, result
    assert "Traceback" not in result.stderr, result


@pytest.fixture
def data(tmp_path):
    destination = tmp_path / "fictional data"
    generated = cli(
        tmp_path,
        "generate",
        "--out", destination,
        "--patients", "6",
        "--as-of", "2026-09-28",
    )
    assert generated.returncode == 0, generated
    return destination


@pytest.mark.parametrize("value", ["", " ", "2026-02-30", "not-a-date"])
def test_invalid_explicit_run_date_preserves_previous_worklist(tmp_path, data, value):
    report = tmp_path / "saved report"
    accepted = cli(
        tmp_path, "run", "--data", data, "--out", report,
        "--as-of", "2026-10-01", "--clinic-timezone", "UTC",
    )
    assert accepted.returncode == 0, accepted
    assert json.loads((report / "summary.json").read_text(encoding="utf-8"))["as_of"] == "2026-10-01"
    before = snapshot(tmp_path)

    refused = cli(
        tmp_path, "run", "--data", data, "--out", report,
        "--as-of", value, "--clinic-timezone", "UTC",
    )

    assert_usage_error(refused)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("value", ["", " ", "2026-02-30"])
def test_invalid_explicit_generator_date_preserves_existing_data(tmp_path, data, value):
    before = snapshot(tmp_path)

    refused = cli(
        tmp_path, "generate", "--out", data, "--patients", "6", "--as-of", value,
    )

    assert_usage_error(refused)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("command", ["generate", "run"])
def test_empty_explicit_date_does_not_create_requested_output(tmp_path, data, command):
    destination = tmp_path / "must remain absent"
    arguments = [command, "--out", destination, "--as-of", ""]
    if command == "run":
        arguments += ["--data", data, "--clinic-timezone", "UTC"]
    before = snapshot(tmp_path)

    refused = cli(tmp_path, *arguments)

    assert_usage_error(refused)
    assert not destination.exists()
    assert snapshot(tmp_path) == before


def test_omitted_and_explicit_run_dates_retain_native_behavior(tmp_path, data):
    before = snapshot(data)
    for name, arguments, expected in [
        ("omitted", [], "2026-09-28"),
        ("explicit", ["--as-of", "2026-10-01"], "2026-10-01"),
    ]:
        report = tmp_path / name
        accepted = cli(
            tmp_path, "run", "--data", data, "--out", report,
            "--clinic-timezone", "UTC", *arguments,
        )
        assert accepted.returncode == 0, accepted
        summary = json.loads((report / "summary.json").read_text(encoding="utf-8"))
        assert summary["as_of"] == expected
        assert summary["counts"]["patients"] == 6
        assert (report / "worklist.csv").is_file()
        assert (report / "digest.html").is_file()
    assert snapshot(data) == before


def test_generator_default_and_explicit_leap_day_reach_the_real_report(tmp_path):
    for name, arguments, expected in [
        ("default", [], "2026-09-28"),
        ("leap-day", ["--as-of", "2024-02-29"], "2024-02-29"),
    ]:
        source = tmp_path / (name + " data")
        report = tmp_path / (name + " report")
        generated = cli(
            tmp_path, "generate", "--out", source, "--patients", "6", *arguments,
        )
        assert generated.returncode == 0, generated
        assert json.loads((source / "expected.json").read_text(encoding="utf-8"))["as_of"] == expected
        accepted = cli(
            tmp_path, "run", "--data", source, "--out", report,
            "--clinic-timezone", "UTC",
        )
        assert accepted.returncode == 0, accepted
        assert json.loads((report / "summary.json").read_text(encoding="utf-8"))["as_of"] == expected
