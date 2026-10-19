"""Independent original-first subprocess oracle for PT CLI date admission."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def snapshot(root):
    if not root.exists():
        return None
    result = {}
    for path in [root, *sorted(root.rglob("*"))]:
        info = path.stat()
        result[str(path.relative_to(root))] = {
            "directory": path.is_dir(), "mode": info.st_mode, "mtime_ns": info.st_mtime_ns,
            "inode": info.st_ino,
            **({"bytes": info.st_size, "sha256": digest(path.read_bytes())} if path.is_file() else {}),
        }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source, out = args.source.resolve(), args.out.resolve()
    if out.exists():
        raise SystemExit("Receiver output must be absent")
    if shutil.disk_usage(out.parent).free < 850_000:
        raise SystemExit("Need 850000 free bytes for this bounded receiving")
    source_before = snapshot(source / "ptauth")
    out.mkdir()
    env = dict(os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    records = []

    def invoke(name, arguments, expected_exit, protected=(), output=None, expected_date=None):
        before = {str(p): snapshot(p) for p in protected}
        command = [sys.executable, "-B", "-S", "-m", "ptauth", *map(str, arguments)]
        process = subprocess.run(command, cwd=out, env=env, capture_output=True, timeout=15)
        (out / f"{name}.stdout").write_bytes(process.stdout)
        (out / f"{name}.stderr").write_bytes(process.stderr)
        after = {str(p): snapshot(p) for p in protected}
        actual_date = None
        if output is not None:
            for filename in ("summary.json", "expected.json"):
                path = output / filename
                if path.exists():
                    actual_date = json.loads(path.read_bytes())["as_of"]
                    break
        usage = expected_exit != 2 or (b"usage:" in process.stderr and b"--as-of" in process.stderr
                                       and b"Traceback" not in process.stderr and not process.stdout)
        unchanged = before == after
        absent = expected_exit != 2 or output is None or output.exists() is False
        matched = (process.returncode == expected_exit and usage and unchanged and absent
                   and (expected_date is None or actual_date == expected_date))
        row = {"case": name, "command": command, "expected_exit": expected_exit,
               "exit": process.returncode, "expected_date": expected_date, "actual_date": actual_date,
               "usage_without_traceback": usage, "protected_unchanged": unchanged,
               "new_output_absent": absent, "before": before, "after": after,
               "stdout_sha256": digest(process.stdout), "stderr_sha256": digest(process.stderr),
               "contract_met": matched}
        records.append(row)
        return row

    data = out / "synthetic-input"
    invoke("default_generator", ["generate", "--out", data, "--patients", "3", "--seed", "37"],
           0, expected_date="2026-09-28", output=data)
    report = out / "saved-review"
    invoke("selected_review", ["run", "--data", data, "--out", report,
                              "--as-of", "2026-10-04", "--clinic-timezone", "UTC"],
           0, protected=(data,), expected_date="2026-10-04", output=report)
    with zipfile.ZipFile(out / "saved-review-before.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(report.rglob("*")):
            if path.is_file():
                archive.write(path, str(path.relative_to(report)))
    invoke("blank_run_preserves_saved_review", ["run", "--data", data, "--out", report,
                                                "--as-of", "", "--clinic-timezone", "UTC"],
           2, protected=(data, report))
    invoke("impossible_run_no_output", ["run", "--data", data, "--out", out / "impossible-output",
                                        "--as-of", "2027-02-29", "--clinic-timezone", "UTC"],
           2, protected=(data,), output=out / "impossible-output")
    invoke("whitespace_run_before_missing_inputs", ["run", "--data", out / "missing-input",
                                                    "--out", out / "whitespace-output", "--as-of", " \t "],
           2, protected=(out / "missing-input",), output=out / "whitespace-output")
    invoke("blank_generate_preserves_saved_data", ["generate", "--out", data, "--as-of", ""],
           2, protected=(data,))
    invoke("malformed_generate_no_output", ["generate", "--out", out / "bad-generated", "--as-of", "2026/10/04"],
           2, output=out / "bad-generated")
    invoke("omitted_run_uses_sample_date", ["run", "--data", data, "--out", out / "sample-review",
                                          "--clinic-timezone", "UTC"],
           0, protected=(data,), output=out / "sample-review", expected_date="2026-09-28")
    invoke("explicit_leap_day_review", ["run", "--data", data, "--out", out / "leap-review",
                                       "--as-of", "2028-02-29", "--clinic-timezone", "UTC"],
           0, protected=(data,), output=out / "leap-review", expected_date="2028-02-29")
    invoke("accepted_compact_generator_date", ["generate", "--out", out / "compact-data", "--patients", "3",
                                               "--seed", "37", "--as-of", "20280229"],
           0, output=out / "compact-data", expected_date="2028-02-29")
    invoke("missing_date_argument", ["run", "--data", data, "--out", out / "missing-argument-output", "--as-of"],
           2, protected=(data,), output=out / "missing-argument-output")
    source_after = snapshot(source / "ptauth")
    receipt = {"schema": "pt-cli-date-independent.v1", "platform": platform.platform(), "python": sys.version,
               "source": str(source), "source_before": source_before, "source_after": source_after,
               "source_unchanged": source_before == source_after, "synthetic_only": True,
               "cases": records, "contracts_met": sum(r["contract_met"] for r in records),
               "all_contracts_met": all(r["contract_met"] for r in records) and source_before == source_after}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"receipt": str(out / "receipt.json"), "contracts_met": receipt["contracts_met"],
                      "source_unchanged": receipt["source_unchanged"],
                      "cases": [{k: r[k] for k in ("case", "exit", "actual_date", "protected_unchanged", "contract_met")}
                                for r in records]}, indent=2))
    return 0 if receipt["all_contracts_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
