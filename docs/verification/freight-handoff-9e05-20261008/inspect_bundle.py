"""Independently decode a real browser download and verify its native snapshot."""
import hashlib, json, sys, zipfile
from pathlib import Path
archive, snapshot, output, receipt = map(Path, sys.argv[1:5])
summary = json.loads(snapshot.read_text())
with zipfile.ZipFile(archive) as z:
    assert set(z.namelist()) == {"index.html", "packet.html", "evidence.json", "review.json", "manifest.json"}
    files = {name: z.read(name) for name in z.namelist()}
manifest = json.loads(files["manifest.json"])
review = json.loads(files["review.json"])
evidence = json.loads(files["evidence.json"])
load = manifest["load_id"]
assert review["load_id"] == load
assert manifest["schema"] == "freight-review-bundle.v1"
assert review["schema"] == "freight-review-snapshot.v1"
assert evidence["schema"] == "freight-review.v1"
sha = lambda data: hashlib.sha256(data).hexdigest()
canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
assert sha(canonical(evidence)) == summary["evidence_versions"][load] == manifest["evidence_version"] == review["evidence_version"]
assert evidence["packet_sha256"] == sha(files["packet.html"])
for section in ("stops", "flags", "fines", "settlements", "exceptions", "packets"):
    assert evidence[section] == sorted((r for r in summary[section] if r["load_id"] == load), key=canonical)
assert review["review"] == summary["decisions"].get(load)
review_hash = sha(json.dumps(review["review"], sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode())
assert review_hash == manifest["review_version"] == review["review_version"] == summary["review_versions"][load]
assert {r["path"] for r in manifest["files"]} == set(files) - {"manifest.json"}
for row in manifest["files"]:
    assert row["bytes"] == len(files[row["path"]])
    assert row["sha256"] == sha(files[row["path"]])
output.mkdir(parents=True, exist_ok=True)
for name, data in files.items():
    (output / name).write_bytes(data)
record = {"passed": True, "archive": archive.name, "bytes": archive.stat().st_size, "sha256": sha(archive.read_bytes()),
          "load_id": load, "evidence_version": manifest["evidence_version"], "review_version": manifest["review_version"],
          "review_state": review["review"].get("review_state") if review["review"] else "unreviewed",
          "members": [{"path": n, "bytes": len(b), "sha256": sha(b)} for n, b in files.items()]}
receipt.write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record))
