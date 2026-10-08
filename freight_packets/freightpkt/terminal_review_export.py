"""Capture saved reviews and deliver the canonical batch archive to a new file."""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import tempfile
import zipfile

from .batch_handoff import build_batch_bundle
from .web import App, REVIEW_SECTIONS

MAX_LOADS = 100
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_PACKET_BYTES = 8 * 1024 * 1024
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_OUTPUT_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_BYTES = MAX_OUTPUT_BYTES + 1024 * 1024


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode(data: bytes, name: str) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"{name} has a repeated JSON key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError(f"{name} contains a non-finite JSON value")

    def finite(token):
        value = float(token)
        return value if math.isfinite(value) else constant(token)

    value = json.loads(data, object_pairs_hook=pairs, parse_constant=constant,
                       parse_float=finite)
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a saved JSON object")
    return value


def _read(path: Path, root: Path, limit: int) -> tuple[Path, bytes]:
    resolved = path.resolve(strict=True)
    if root not in resolved.parents:
        raise ValueError("saved source must be a regular file within the output directory")
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(resolved, flags)
    with os.fdopen(descriptor, "rb") as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise ValueError("saved source must be a regular file")
        data = source.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"saved source exceeds its {limit}-byte limit: {path.name}")
    return resolved, data


def _destination(out_dir: Path, destination: Path) -> Path:
    parent = destination.parent.resolve(strict=True)
    if not parent.is_dir():
        raise ValueError("the destination parent must be an existing directory")
    target = parent / destination.name
    if out_dir == parent or out_dir in parent.parents:
        raise ValueError("the destination must be outside the source output directory")
    if os.path.lexists(target):
        raise FileExistsError("the destination already exists; choose a new filename")
    return target


def _decoded_size(raw: bytes) -> int:
    # These bytes are returned by the native producers, never a user-supplied ZIP.
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        return sum(member.file_size for member in archive.infolist())


def export_reviews(out_dir: Path, load_ids: list[str], destination: Path) -> dict:
    """Publish one new canonical archive and return its separate capture receipt.

    Before/after source checks detect observed changes. They do not hold a live
    server lock, establish a cross-process lease or authenticate a saved review.
    A later receipt-output failure cannot roll back the already-published file.
    """
    if not isinstance(load_ids, (list, tuple)) or not 1 <= len(load_ids) <= MAX_LOADS:
        raise ValueError(f"select between 1 and {MAX_LOADS} load IDs explicitly")
    if any(not isinstance(value, str) or not value for value in load_ids):
        raise ValueError("every selected load ID must be nonempty text")
    if len(set(load_ids)) != len(load_ids):
        raise ValueError("a load ID was selected more than once")
    selected = sorted(load_ids)
    out_dir = Path(out_dir).resolve(strict=True)
    if not out_dir.is_dir():
        raise ValueError("the source output must be an existing directory")
    destination = _destination(out_dir, Path(destination))
    captured = {}
    total_input = 0

    def capture(relative: Path, limit: int) -> bytes:
        nonlocal total_input
        if relative in captured:
            return captured[relative][1]
        resolved, data = _read(out_dir / relative, out_dir, limit)
        total_input += len(data)
        if total_input > MAX_INPUT_BYTES:
            raise ValueError("the selected source snapshot exceeds the input limit")
        captured[relative] = (resolved, data, limit)
        return data

    summary_bytes = capture(Path("summary.json"), MAX_JSON_BYTES)
    summary = _decode(summary_bytes, "summary.json")
    has_decisions = os.path.lexists(out_dir / "decisions.json")
    decisions_bytes = capture(Path("decisions.json"), MAX_JSON_BYTES) if has_decisions else None
    if decisions_bytes is not None:
        _decode(decisions_bytes, "decisions.json")
    packets = summary.get("packets")
    if not isinstance(packets, list) or any(
            not isinstance(row, dict) or not isinstance(row.get("load_id"), str)
            or not isinstance(row.get("file"), str) for row in packets):
        raise ValueError("summary.json must contain the native packet list")
    for section in REVIEW_SECTIONS:
        records = summary.get(section, [])
        if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
            raise ValueError(f"summary.json {section} must be a list of native records")
    for load_id in selected:
        matches = [row for row in packets if row["load_id"] == load_id]
        if len(matches) != 1:
            raise ValueError(f"selected load must identify exactly one saved packet: {load_id!r}")
        relative = Path(os.path.normpath(matches[0]["file"]))
        if (relative.is_absolute() or not relative.parts or relative.parts[0] == ".."
                or relative.parts[0] in {"summary.json", "decisions.json"}):
            raise ValueError("selected packet must have a relative path inside the output directory")
        capture(relative, MAX_PACKET_BYTES)

    published = False
    try:
        with tempfile.TemporaryDirectory(prefix=".freight-reviews-", dir=destination.parent) as temporary:
            work = Path(temporary)
            snapshot = work / "snapshot"
            snapshot.mkdir()
            for relative, (_, data, _) in captured.items():
                target = snapshot / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)

            app = App(work / "unused-inputs", snapshot)
            view = app.summary()
            bundles, identities = [], []
            total_output = 0
            for load_id in selected:
                version = view["evidence_versions"].get(load_id)
                if version is None:
                    raise ValueError("selected packet is not readable in the captured snapshot")
                identity = {"load_id": load_id, "evidence_version": version,
                            "review_version": view["review_versions"][load_id]}
                filename, native = app.review_bundle(
                    load_id, identity["evidence_version"], identity["review_version"])
                total_output += _decoded_size(native) + len(native)
                if total_output > MAX_OUTPUT_BYTES:
                    raise ValueError("the native review contents exceed the output limit")
                identities.append(identity)
                bundles.append((identity, filename, native))

            filename, content = build_batch_bundle(bundles)
            if len(content) > MAX_ARCHIVE_BYTES:
                raise ValueError("the ZIP exceeds the archive size limit")
            if _decoded_size(content) > MAX_OUTPUT_BYTES:
                raise ValueError("the batch contents exceed the decoded output limit")
            receipt = {
                "schema": "freight-review-terminal-export.v1",
                "count": len(identities), "destination": str(destination),
                "archive_filename": filename, "archive_bytes": len(content),
                "archive_sha256": _hash(content),
                "source_summary_sha256": _hash(summary_bytes),
                "source_decisions_sha256": _hash(decisions_bytes) if decisions_bytes is not None else None,
                "identities": identities,
            }
            staged = work / "handoff.zip"
            with staged.open("xb") as complete:
                complete.write(content)
                complete.flush()
                os.fsync(complete.fileno())
            for relative, (resolved, data, limit) in captured.items():
                current_resolved, current_data = _read(out_dir / relative, out_dir, limit)
                if current_resolved != resolved or current_data != data:
                    raise ValueError("saved source changed during export; finish edits and try again")
            if not has_decisions and os.path.lexists(out_dir / "decisions.json"):
                raise ValueError("saved reviews appeared during export; finish edits and try again")
            # A raced file, directory or symlink wins; never replace that destination.
            os.link(staged, destination, follow_symlinks=False)
            published = True
    except OSError as error:
        if published:
            raise OSError(f"archive published to {destination}, but staging cleanup failed: {error}") from error
        raise
    return receipt
