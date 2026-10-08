#!/usr/bin/env python3
"""Verify this independent evidence packet without executing product code."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def relative(value):
    p = PurePosixPath(value)
    assert value and not p.is_absolute() and ".." not in p.parts and "\\" not in value
    return p


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--extract-artifacts", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / "manifest.json").read_text())
    seen = set()
    for row in manifest["files"]:
        path = str(relative(row["path"]))
        assert path not in seen
        seen.add(path)
        data = (root / path).read_bytes()
        assert len(data) == row["bytes"] and digest(data) == row["sha256"] and git_blob(data) == row["git_blob"]
    encoded = (root / "native-artifacts.json.gz.b64").read_bytes()
    raw = gzip.decompress(base64.b64decode(encoded, validate=True))
    assert digest(raw) == manifest["native_archive"]["decoded_sha256"]
    archive = json.loads(raw)
    contents = {key: base64.b64decode(value, validate=True) for key, value in archive["contents"].items()}
    assert all(key == digest(value) for key, value in contents.items())
    seen = set()
    for row in archive["files"]:
        path = str(relative(row["path"]))
        assert path not in seen
        seen.add(path)
        if row["type"] == "symlink":
            assert isinstance(row["target"], str)
            continue
        assert row["type"] == "file"
        data = contents[row["sha256"]]
        assert len(data) == row["bytes"] and git_blob(data) == row["git_blob"]
    if args.extract_artifacts is not None:
        args.extract_artifacts.mkdir(parents=True, exist_ok=False)
        for row in archive["files"]:
            if row["type"] != "file":
                continue
            path = args.extract_artifacts / str(relative(row["path"]))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents[row["sha256"]])
            path.chmod(row["mode"])
    print(json.dumps({"result": "PASS", "packet_files": len(manifest["files"]),
                      "artifact_records": len(archive["files"]),
                      "unique_content_payloads": len(contents),
                      "product_executions": 0, "symlinks_recreated": 0}))


if __name__ == "__main__":
    main()
