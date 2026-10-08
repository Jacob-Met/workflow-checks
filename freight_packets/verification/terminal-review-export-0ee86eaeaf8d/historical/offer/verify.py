"""Verify this frozen source/evidence offer without executing captured code."""
import base64
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath


root = Path(__file__).resolve().parent
manifest = json.loads((root / "manifest.json").read_bytes())
encoded = (root / manifest["archive"]["path"]).read_bytes()
assert len(encoded) == manifest["archive"]["bytes"]
assert hashlib.sha256(encoded).hexdigest() == manifest["archive"]["sha256"]
raw = gzip.decompress(base64.b64decode(encoded, validate=False))
assert len(raw) == manifest["archive"]["decoded_bytes"]
assert hashlib.sha256(raw).hexdigest() == manifest["archive"]["decoded_sha256"]
archive = json.loads(raw)
expected = {row["path"]: row for row in manifest["files"]}
assert len(expected) == len(manifest["files"]) == manifest["archive"]["files"]
seen = set()
for row in archive["files"]:
    path = PurePosixPath(row["path"])
    assert not path.is_absolute() and ".." not in path.parts
    assert row["path"] not in seen
    seen.add(row["path"])
    data = base64.b64decode(row["base64"], validate=True)
    summary = {key: value for key, value in row.items() if key != "base64"}
    assert summary == expected[row["path"]]
    assert len(data) == row["bytes"]
    assert hashlib.sha256(data).hexdigest() == row["sha256"]
    assert hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == row["git_blob"]
assert seen == set(expected)
print(json.dumps({"verified_files": len(seen), "encoded_bytes": len(encoded), "decoded_bytes": len(raw)}))
