#!/usr/bin/env python3
"""Verify and optionally restore the independent evidence; never run the product."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath


def pin(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}


def check(data, expected):
    assert pin(data) == {key: expected[key] for key in ("bytes", "sha256", "git_blob")}


def safe_path(value):
    path = PurePosixPath(value)
    assert not path.is_absolute() and path.parts and all(part not in ("", ".", "..") for part in path.parts)
    assert "\\" not in value
    return Path(*path.parts)


def write(root, name, data):
    target = root / safe_path(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", type=Path, help="new, absent directory for evidence and replay layout")
    parser.add_argument("--author-evidence", type=Path, help="shared terminal-review-export evidence root")
    parser.add_argument("--repository", type=Path, help="exact qualified repository root; with author evidence, restores an R2 source-review view")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / "manifest.json").read_bytes())
    for entry in manifest["files"]:
        check((root / safe_path(entry["path"])).read_bytes(), entry)
        assert entry["mode"] == "100644"
    archive = json.loads(gzip.decompress(base64.b64decode((root / "artifacts.json.gz.b64").read_bytes(), validate=True)))
    bodies = {key: base64.b64decode(value, validate=True) for key, value in archive["contents"].items()}
    for key, data in bodies.items():
        assert hashlib.sha256(data).hexdigest() == key
    files = {}
    for entry in archive["files"]:
        safe_path(entry["path"])
        assert entry["path"] not in files and entry["mode"] == "100644"
        data = bodies[entry["sha256"]]
        check(data, entry)
        files[entry["path"]] = data
    assert set(bodies) == {entry["sha256"] for entry in archive["files"]}
    oracle = json.loads(files["oracle-manifest.json"])
    assert hashlib.sha256(files["oracle-manifest.json"]).hexdigest() == "20b2323561353eaa4418cabe2e5573d8920a5e864c9c7b848400848a83f3f043"
    for entry in oracle["files"]:
        check(files[entry["path"]], entry)
    for outside, inside in manifest["readable_receipt_copies"].items():
        assert (root / outside).read_bytes() == files[inside]
    independent = json.loads(files["native-r1/receipt.json"])
    assert independent["result"] == "ACCEPT" and independent["processes"] == 6
    assert all(case["result"] == "ACCEPT" for case in independent["cases"])
    supplement = json.loads(files["guard-r2/receipt.json"])
    assert supplement["independent_additional_native_processes"] == 0
    assert supplement["received_author_processes"] == 2
    shared = manifest["shared_author_files"]
    author_files = {}
    if args.author_evidence:
        for entry in shared:
            data = (args.author_evidence / safe_path(entry["path"])).read_bytes()
            check(data, entry)
            author_files[entry["path"]] = data
    assert not args.repository or args.author_evidence, "--repository requires --author-evidence"
    if args.extract:
        args.extract.mkdir(parents=True, exist_ok=False)
        for name, data in files.items():
            write(args.extract, name, data)
        proof = json.loads(files["fixture-reuse-proof.json"])
        for entry in proof["reused"]:
            data = files[entry["new_path"]]
            check(data, entry)
            write(args.extract / "replay-historical", entry["historical_path"], data)
        if author_files:
            original = json.loads(gzip.decompress(base64.b64decode(author_files["native-r1/execution.json.gz.b64"])))
            for name, entry in original["source_images"].items():
                data = base64.b64decode(entry["base64"], validate=True)
                check(data, entry)
                write(args.extract / "replay-r1-source", name, data)
        if args.repository:
            view = args.extract / "replay-author"
            for name, data in author_files.items():
                write(view, name, data)
            current = json.loads(author_files["candidate-manifest-r2.json"])
            for entry in current["files"]:
                data = (args.repository / safe_path(entry["path"])).read_bytes()
                check(data, entry)
                write(view / "candidate", entry["path"], data)
    print(json.dumps({"result": "ACCEPT", "packet_files": len(manifest["files"]) + 1,
                      "artifact_paths": len(files), "unique_bodies": len(bodies),
                      "frozen_oracle_files": len(oracle["files"]),
                      "shared_author_files_verified": len(author_files),
                      "native_product_processes": 0, "extracted": args.extract is not None}, sort_keys=True))


if __name__ == "__main__":
    main()
