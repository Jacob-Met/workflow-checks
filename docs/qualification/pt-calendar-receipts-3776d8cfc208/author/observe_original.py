"""Four fixed original calendar CLI observations; never imports the product."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def identity(path):
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "git_blob": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
            "mtime_ns": path.stat().st_mtime_ns}


def item(patient, *, day):
    return {"key": patient + "|DEMO-PAYER|DEMO-AUTH", "patient_id": patient,
            "patient_name": "Fictional calendar observation", "payer_id": "DEMO-PAYER",
            "payer_name": "Fictional payer", "auth_no": "DEMO-AUTH", "clinic": "Fictional clinic 雪",
            "priority": "P1", "submit_by": day, "auth_end": "2026-10-31",
            "next_visit": None, "reasons": ["Authored receipt test"], "detail": [],
            "checklist": [], "evidence": ["Authored fixture; no source records"]}


def inspect_calendar(path):
    raw = path.read_bytes()
    assert raw.startswith(b"BEGIN:VCALENDAR\r\n") and raw.endswith(b"END:VCALENDAR\r\n")
    assert b"\n" not in raw.replace(b"\r\n", b"")
    lines = raw[:-2].split(b"\r\n")
    assert all(0 < len(line) <= 75 for line in lines)
    logical = []
    for line in lines:
        text = line.decode("utf-8")
        if text.startswith(" "):
            logical[-1] += text[1:]
        else:
            logical.append(text)
    assert logical.count("BEGIN:VEVENT") == logical.count("END:VEVENT") == 1
    assert "DTSTART;VALUE=DATE:20261021" in logical
    assert "TRANSP:TRANSPARENT" in logical
    return {"complete": True, "events": 1, **identity(path)}


def main():
    source = ROOT / "original"
    pins = {"__init__.py": "a6f4545ac17e2578317ef694f7bb548489f6c71c",
            "__main__.py": "3c93dd90cf357624c77ab3589ef2b201868c181e",
            "cli.py": "559c0a76effa2204041e9318e9869a6c7389f50d",
            "worklist_calendar.py": "e125f9ed77343fcc3d82e6d6f25a7296b0463aa7"}
    for name, pin in pins.items():
        assert identity(source / "ptauth" / name)["git_blob"] == pin
    out = ROOT / "original-course"
    out.mkdir(exist_ok=False)
    reports = out / "saved-report"
    reports.mkdir()
    rows = [item("DEMO-ONE", day="2026-10-21"), item("DEMO-雪", day=None)]
    summary = {"banner": "SYNTHETIC DATA ONLY — authored fixture", "as_of": "2026-10-14",
               "generated_at": "2026-10-14T00:00:00Z", "clinic_timezone": "UTC", "worklist": rows}
    states = {rows[1]["key"]: {"state": "n/a", "note": "Fictional excluded note 雪"}}
    for name, doc in [("summary.json", summary), ("work_state.json", states)]:
        (reports / name).write_bytes((json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    watched = [source / "ptauth" / n for n in pins] + list(reports.iterdir()) + [Path(__file__), ROOT / "ORIGINAL_PROTOCOL.md"]
    before = {str(p): identity(p) for p in watched}
    observations = []
    cases = [("ordinary-utf8", "ptauth", "utf-8:strict", False),
             ("ascii-output", "ptauth", "ascii:strict", False),
             ("canonical-closed-pipe", "ptauth", "utf-8:strict", True),
             ("cli-closed-pipe", "ptauth.cli", "utf-8:strict", True)]
    for name, module, encoding, closed in cases:
        destination = out / (name + "-雪.ics")
        argv = [sys.executable, "-B", "-m", module, "calendar", "--report", str(reports), "--output", str(destination)]
        env = {**os.environ, "PYTHONIOENCODING": encoding, "PYTHONDONTWRITEBYTECODE": "1"}
        env.pop("PYTHONUNBUFFERED", None)
        write_fd = None
        if closed:
            read_fd, write_fd = os.pipe()
            os.close(read_fd)
        start = time.monotonic_ns()
        try:
            child = subprocess.Popen(argv, cwd=source, env=env, stdin=subprocess.DEVNULL,
                                     stdout=write_fd if closed else subprocess.PIPE, stderr=subprocess.PIPE)
        finally:
            if write_fd is not None:
                os.close(write_fd)
        timeout = False
        try:
            stdout, stderr = child.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            timeout = True
            child.kill()
            stdout, stderr = child.communicate()
        elapsed = time.monotonic_ns() - start
        stdout = stdout or b""
        (out / (name + ".stdout")).write_bytes(stdout)
        (out / (name + ".stderr")).write_bytes(stderr)
        result = {"name": name, "argv": argv, "output_encoding": encoding, "preclosed_pipe": closed,
                  "pid": child.pid, "exit": child.returncode, "timeout": timeout,
                  "reaped": child.poll() is not None, "elapsed_ns": elapsed,
                  "stdout_bytes": len(stdout), "stderr_bytes": len(stderr), "output_exists": destination.exists()}
        if destination.exists():
            result["calendar"] = inspect_calendar(destination)
        if name == "ordinary-utf8":
            metadata = json.loads(stdout)
            assert child.returncode == 0 and not stderr and not timeout
            assert [metadata[k] for k in ("selected", "events", "undated", "completed_state")] == [2, 1, 1, 1]
            assert metadata["output"] == str(destination)
            assert metadata["excluded"][0]["patient_id"] == "DEMO-雪"
            result["ordinary_metadata_exact"] = True
        observations.append(result)
    after = {str(p): identity(p) for p in watched}
    report = {"schema": "pt.calendar.original-stdout-observation/1", "source_before": before,
              "source_after": after, "custody_exact": before == after, "observations": observations,
              "no_staging_files": not list(out.glob(".ptauth-calendar-*")),
              "scope": "Four original CLI processes on authored saved JSON. No repaired implementation, engine, server, network, calendar app or clinical validation."}
    with (out / "observation.json").open("x", encoding="ascii") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    print(json.dumps({"custody_exact": report["custody_exact"], "runs": [
        {k: row[k] for k in ("name", "exit", "timeout", "reaped", "output_exists")} for row in observations]}))


if __name__ == "__main__":
    main()
