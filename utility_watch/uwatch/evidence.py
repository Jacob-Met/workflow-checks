"""Inspect the actual CSV records cited by one source-validated native finding."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import engine, review

SCHEMA = "uwatch-evidence-v1"


def _identity(info: os.stat_result) -> tuple:
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _directory(path: Path) -> tuple:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError(f"directory must be a real directory, not a symbolic link: {path}")
    # Adding our temporary output must not invalidate the directory guard.
    return info.st_dev, info.st_ino, info.st_mode


@dataclass(frozen=True)
class _Input:
    raw: bytes
    identity: tuple


def _read_regular(path: Path, *, optional: bool = False) -> _Input | None:
    try:
        before = path.lstat()
    except FileNotFoundError:
        if optional:
            return None
        raise
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"input must be a regular file, not a symbolic link: {path.name}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as source:
        opened = os.fstat(source.fileno())
        if not stat.S_ISREG(opened.st_mode) or _identity(opened) != _identity(before):
            raise ValueError(f"input changed while opening: {path.name}")
        raw = source.read()
        after = os.fstat(source.fileno())
    if _identity(after) != _identity(before) or _identity(path.lstat()) != _identity(after):
        raise ValueError(f"input changed while reading: {path.name}")
    return _Input(raw, _identity(after))


def _leaf(path: Path) -> Path:
    """Resolve the parent, retaining the leaf so symlinks can be refused."""
    absolute = Path(os.path.abspath(path))
    return absolute.parent.resolve(strict=True) / absolute.name


def _records(pointers: list, source: dict[str, bytes]) -> list[dict]:
    if not isinstance(pointers, list) or not pointers:
        raise ValueError("finding has no source evidence pointers")
    parsed = {}
    records = []
    for pointer in pointers:
        if not isinstance(pointer, str) or not re.fullmatch(
                r"(?:accounts|bills|occupancy|payments)\.csv:[1-9][0-9]*", pointer):
            raise ValueError(f"unsupported source evidence pointer: {pointer!r}")
        name, number = pointer.split(":")
        if name not in source:
            raise ValueError(f"missing source file for evidence: {name}")
        if name not in parsed:
            columns, rows = review._csv(source[name], name)
            parsed[name] = columns, dict(rows)
        columns, rows = parsed[name]
        line = int(number)
        if line not in rows:
            raise ValueError(f"source evidence does not identify a complete CSV record: {pointer}")
        records.append({
            "pointer": pointer, "file": name, "record_end_line": line,
            "columns": list(columns), "fields": dict(rows[line]),
        })
    return records


def _publish(path: Path, raw: bytes, recheck) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".uwatch-evidence-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as target:
            target.write(raw)
            target.flush()
            os.fsync(target.fileno())
        # Check after staging, immediately before the new destination is published.
        recheck()
        # A same-directory hard link publishes complete bytes without replacing a raced writer.
        os.link(temporary, path)
    finally:
        # Do not mask a write/link error or misreport an already complete publication.
        try:
            os.unlink(temporary)
        except OSError:
            pass


def write_evidence(data: Path, report: Path, out: Path, *,
                   kind: str, account: str, key: str, code: str) -> dict:
    """Write one new evidence JSON file; never edits CSVs, reports or review notes."""
    if kind not in ("flag", "exception") or any(
            not isinstance(value, str) or not value for value in (account, key, code)):
        raise ValueError("choose a flag or exception with an exact account, key and code")
    data, report, out = _leaf(Path(data)), _leaf(Path(report)), _leaf(Path(out))
    protected = {data / name for name in (*review.DATA_FILES, "expected.json")}
    protected.update(report.parent / name for name in review.REPORT_FILES)
    protected.add(report)
    if out in protected or out.exists() or out.is_symlink():
        raise ValueError("--out must name a new evidence file; source and reports cannot be replaced")
    directories = {path: _directory(path) for path in (data, report.parent, out.parent)}
    inputs = {report: _read_regular(report)}
    inputs.update({data / name: _read_regular(data / name) for name in review.DATA_FILES})
    marker = data / "expected.json"
    inputs[marker] = _read_regular(marker, optional=True)

    def recheck():
        for path, original in directories.items():
            if _directory(path) != original:
                raise ValueError(f"input/output directory changed during evidence inspection: {path}")
        for path, original in inputs.items():
            if _read_regular(path, optional=original is None) != original:
                raise ValueError(f"input changed during evidence inspection: {path.name}")
        # A directory could have changed while its files were being reread.
        for path, original in directories.items():
            if _directory(path) != original:
                raise ValueError(f"input/output directory changed during evidence inspection: {path}")

    recheck()
    source = {name: inputs[data / name].raw for name in review.DATA_FILES}
    try:
        # Admit fixed bytes through the existing report/checker validator, independently
        # of any edits to the caller's directory during that potentially lengthy check.
        with tempfile.TemporaryDirectory(prefix="uwatch-evidence-source-") as staging:
            snapshot = Path(staging)
            snapshot_data = snapshot / "data"
            snapshot_data.mkdir()
            for name, raw in source.items():
                (snapshot_data / name).write_bytes(raw)
            if inputs[marker] is not None:
                (snapshot_data / "expected.json").write_bytes(inputs[marker].raw)
            snapshot_report = snapshot / "summary.json"
            snapshot_report.write_bytes(inputs[report].raw)
            current, validated, _ = review._current(snapshot_data, snapshot_report)
        matches = [row for row in current if (
            row["kind"], row["account_no"], row["finding_key"], row["code"]
        ) == (kind, account, key, code)]
        if len(matches) != 1:
            raise ValueError(f"expected one exact finding; found {len(matches)} for "
                             f"{kind}, account {account!r}, key {key!r}, code {code!r}")
        row = matches[0]
        pointers = review._read_json(row["evidence"].encode("utf-8"))
        records = _records(pointers, source)
    except csv.Error as exc:
        raise ValueError(f"malformed CSV: {exc}") from exc

    def manifest(path: Path, label: str) -> dict:
        admitted = inputs[path]
        return {
            "file": label, "present": admitted is not None,
            "bytes": len(admitted.raw) if admitted is not None else None,
            "sha256": hashlib.sha256(admitted.raw).hexdigest() if admitted is not None else None,
        }

    document = {
        "schema": SCHEMA,
        "finding": {**{field: row[field] for field in (
            "kind", "account_no", "finding_key", "code", "property", "utility",
            "detail", "finding_id", "evidence_version",
        )}, "evidence": pointers},
        "review": {field: validated[field] for field in ("as_of", "eval_from", "data_mode")},
        "source": {
            "report": manifest(report, report.name),
            "inputs": [manifest(data / name, name) for name in (*review.DATA_FILES, "expected.json")],
            "engine_sha256": hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest(),
            "rules": engine.DEFAULT_RULES,
        },
        "records": records,
    }
    raw = (json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")
    _publish(out, raw, recheck)
    return document
