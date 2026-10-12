"""Successful reruns must download the same current optional rows they report."""

import csv
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
from freightpkt.pipeline import run
from freightpkt.synth import generate
from freightpkt.web import App

REPORTS = ("fines.csv", "settlement.csv")
FREIGHT_ROOT = Path(__file__).resolve().parents[1]


def _rows(raw):
    return list(csv.reader(io.StringIO(raw.decode("utf-8"), newline="")))


def _cli(data, out):
    result = subprocess.run(
        [sys.executable, "-B", "-m", "freightpkt", "run", "--data", str(data), "--out", str(out)],
        cwd=FREIGHT_ROOT, capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    return json.loads((out / "summary.json").read_bytes())


def test_first_run_without_schedule_publishes_empty_optional_reports(tmp_path):
    data, out = tmp_path / "data", tmp_path / "out"
    generate(data, 12, 5)
    (data / "fines_schedule.csv").unlink()
    summary = run(data, out)

    assert summary["fines"] == [] and summary["settlements"] == []
    app = App(data, out)
    for name in REPORTS:
        _, raw = app.output(name)
        rows = _rows(raw)
        assert len(rows) == 1
        assert rows[0][0] == ("fine_id" if name == "fines.csv" else "invoice_no")


@pytest.mark.parametrize("seed,loads", [(7, 24), (99, 40)])
def test_real_cli_remove_and_restore_schedule_refreshes_downloads(tmp_path, seed, loads):
    data, out = tmp_path / "data", tmp_path / "out"
    generate(data, loads, seed)
    schedule_path = data / "fines_schedule.csv"
    schedule = schedule_path.read_bytes()
    first = _cli(data, out)
    original = {name: (out / name).read_bytes() for name in REPORTS}
    assert all(len(_rows(raw)) > 1 for raw in original.values())
    preserved = {
        name: (out / name).read_bytes()
        for name in ("detention_claims.csv", "invoice_flags.csv")
    }
    app = App(data, out)
    current = app.summary()
    load_id = current["packets"][0]["load_id"]
    app.decide({"load_id": load_id, "decision": "approve", "note": "Retain this review",
                "evidence_version": current["evidence_versions"][load_id]})
    decisions = app.decisions_path.read_bytes()
    audit_prefix = (out / "audit.jsonl").read_bytes()
    (out / "retained-review.txt").write_bytes(b"Unrelated saved review\n")

    schedule_path.unlink()
    current = _cli(data, out)
    assert current["fines"] == [] and current["settlements"] == []
    for name, old in original.items():
        _, raw = app.output(name)
        assert _rows(raw) == [_rows(old)[0]]
    for name, raw in preserved.items():
        assert (out / name).read_bytes() == raw
    assert app.decisions_path.read_bytes() == decisions
    assert (out / "retained-review.txt").read_bytes() == b"Unrelated saved review\n"
    assert (out / "audit.jsonl").read_bytes().startswith(audit_prefix)

    schedule_path.write_bytes(schedule)
    restored = _cli(data, out)
    assert {k: v for k, v in restored.items() if k != "generated_at"} == {
        k: v for k, v in first.items() if k != "generated_at"
    }
    assert {name: app.output(name)[1] for name in REPORTS} == original
    assert app.decisions_path.read_bytes() == decisions
