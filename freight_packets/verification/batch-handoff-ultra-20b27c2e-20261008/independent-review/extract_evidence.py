#!/usr/bin/env python3
"""Restore exact independently recorded files; stdlib only, no native test execution."""
import argparse
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import zlib

p = argparse.ArgumentParser()
p.add_argument("bundle")
p.add_argument("destination")
args = p.parse_args()
bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
if bundle.get("schema") != "freight-independent-files.v1":
    raise ValueError("Unsupported evidence bundle")
destination = Path(args.destination).resolve()
destination.mkdir(parents=True, exist_ok=True)
seen = set()
verified = []
for row in bundle["files"]:
    relative = PurePosixPath(row["path"])
    if relative.is_absolute() or ".." in relative.parts or "\\" in row["path"]:
        raise ValueError("Unsafe recorded path")
    if row["path"] in seen:
        raise ValueError("Repeated recorded path")
    seen.add(row["path"])
    record = bundle["blobs"][row["sha256"]]
    if record["encoding"] != "zlib-base64":
        raise ValueError("Unsupported evidence encoding")
    if not isinstance(row["bytes"], int) or not 0 <= row["bytes"] <= 8 * 1024 * 1024:
        raise ValueError("Unexpected evidence size")
    decoder = zlib.decompressobj()
    data = decoder.decompress(base64.b64decode(record["data"], validate=True), row["bytes"] + 1)
    if decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:
        raise ValueError("Truncated, trailing or oversized encoded evidence")
    if len(data) != row["bytes"] or hashlib.sha256(data).hexdigest() != row["sha256"]:
        raise ValueError("Recorded bytes do not match")
    target = destination.joinpath(*relative.parts)
    if destination not in target.resolve().parents:
        raise ValueError("Recorded destination escapes output root")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != data:
            raise FileExistsError("Refusing to replace different existing bytes: " + str(target))
    else:
        with target.open("xb") as out:
            out.write(data)
    verified.append({"path": row["path"], "bytes": len(data), "sha256": row["sha256"]})
print(json.dumps({"verified_files": len(verified), "verified_bytes": sum(r["bytes"] for r in verified),
                  "destination": str(destination)}, indent=2))
