"""Measure the current checker and full CLI on one explicit local CSV export.

Run from any directory; results are JSON on stdout. Every full-command sample
writes to a new temporary directory. Source CSVs and existing reports are read-only.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from uwatch import engine


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def input_hashes(data):
    return {name: digest((data / name).read_bytes()) if (data / name).exists() else None
            for name in ("accounts.csv", "bills.csv", "occupancy.csv", "payments.csv", "expected.json")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--eval-from", type=date.fromisoformat, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args(argv)
    if not 1 <= args.repeats <= 100:
        parser.error("--repeats must be between 1 and 100")
    data = args.data.resolve()
    source = input_hashes(data)
    loaded = engine.load(data)
    check_args = (*loaded, args.as_of, args.eval_from)
    result = engine.check(*check_args)
    expected = json.dumps(([asdict(f) for f in result[0]], *result[1:]), sort_keys=True).encode()
    checks = []
    for _ in range(args.repeats):
        start = time.perf_counter()
        actual = engine.check(*check_args)
        checks.append(time.perf_counter() - start)
        if json.dumps(([asdict(f) for f in actual[0]], *actual[1:]), sort_keys=True).encode() != expected:
            raise RuntimeError("checker results changed between equivalent runs")
    tracemalloc.start()
    engine.check(*check_args)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    cli_times, output_hashes = [], None
    with tempfile.TemporaryDirectory(prefix="uwatch-benchmark-") as temporary:
        for number in range(args.repeats):
            output = Path(temporary) / str(number)
            start = time.perf_counter()
            subprocess.run(
                [sys.executable, "-m", "uwatch", "run", "--data", str(data), "--out", str(output),
                 "--as-of", args.as_of.isoformat(), "--eval-from", args.eval_from.isoformat()],
                cwd=ROOT, capture_output=True, text=True, check=True)
            cli_times.append(time.perf_counter() - start)
            hashes = {p.name: digest(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()}
            if output_hashes is not None and hashes != output_hashes:
                raise RuntimeError("full CLI output bytes changed between equivalent runs")
            output_hashes = hashes
    if input_hashes(data) != source:
        raise RuntimeError("input changed during measurement")
    print(json.dumps({
        "python": platform.python_version(), "platform": platform.platform(),
        "engine_sha256": digest(Path(engine.__file__).read_bytes()), "data_sha256": source,
        "as_of": args.as_of.isoformat(), "eval_from": args.eval_from.isoformat(),
        "accounts": len(loaded[0]), "bills": len(loaded[1]), "repeats": args.repeats,
        "check_seconds": checks, "check_median_seconds": statistics.median(checks),
        "cli_seconds": cli_times, "cli_median_seconds": statistics.median(cli_times),
        "check_peak_allocated_bytes": peak,
        "flags": len(result[0]), "exceptions": len(result[1]), "payment_queue": len(result[2]),
        "result_sha256": digest(expected), "output_sha256": output_hashes,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
