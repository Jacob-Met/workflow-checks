"""Verify the retained terminal source/evidence bytes without product execution."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET
import zipfile


def identity(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}


def check(data, row):
    actual = identity(data)
    for key in actual:
        if key in row:
            assert actual[key] == row[key], (key, actual[key], row[key])
    return actual


def relative(value):
    path = PurePosixPath(value)
    assert value and not path.is_absolute() and ".." not in path.parts and "\\" not in value
    return str(path)


def read_json(path):
    return json.loads(path.read_bytes())


def unpack(path):
    raw = gzip.decompress(base64.b64decode(path.read_bytes().strip(), validate=True))
    return raw, json.loads(raw)


def verify_inventory_archive(path):
    raw, archive = unpack(path)
    if "contents" in archive:
        contents = {key: base64.b64decode(value, validate=True) for key, value in archive["contents"].items()}
        assert all(key == identity(value)["sha256"] for key, value in contents.items())
    else:
        contents = {}
    seen = set()
    for row in archive["files"]:
        name = relative(row["path"])
        assert name not in seen
        seen.add(name)
        if row.get("type") == "symlink":
            assert isinstance(row["target"], str)
            continue
        data = base64.b64decode(row["base64"], validate=True) if "base64" in row else contents[row["sha256"]]
        check(data, row)
    return {"files": len(seen), "decoded_bytes": len(raw), "decoded_sha256": identity(raw)["sha256"]}


def verify_cli(records):
    for row in records:
        assert row["source_before"] == row["source_after"] and row["code_preserved"]
        assert set(row["fixture_base64"]) == set(row["source_before"])
        for path, encoded in row["fixture_base64"].items():
            relative(path)
            check(base64.b64decode(encoded, validate=True), row["source_before"][path])
        if row["returncode"] == 0:
            archive = base64.b64decode(row["archive_base64"], validate=True)
            receipt = json.loads(row["stdout"])
            assert receipt["archive_sha256"] == identity(archive)["sha256"]
            assert receipt["archive_bytes"] == len(archive)
            with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
                assert len(bundle.namelist()) == 6 * receipt["count"] + 2
                manifest = json.loads(bundle.read("manifest.json"))
                for member in manifest["files"]:
                    check(bundle.read(relative(member["path"])), member)
        elif row["stdout_full"]:
            assert row["returncode"] == 2 and "archive published" in row["stderr"]
            with zipfile.ZipFile(io.BytesIO(base64.b64decode(row["archive_base64"], validate=True))) as bundle:
                assert "manifest.json" in bundle.namelist()
        else:
            assert row["returncode"] == 2 and row["stdout"] == ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    repository = args.repository.resolve() if args.repository else here.parents[2]
    manifest = read_json(here / "manifest.json")
    seen = set()
    for row in manifest["files"]:
        path = relative(row["path"])
        assert path not in seen
        seen.add(path)
        check((repository / path).read_bytes(), row)

    snapshot = read_json(here / "source-snapshot.json")
    source = {}
    for row in snapshot["files"]:
        data = row["content"].encode()
        check(data, row)
        source[relative(row["path"])] = data
    assert len(source) == 27
    final = read_json(here / "candidate-manifest-r2.json")
    for path in final["changed_paths"]:
        source[path] = (repository / path).read_bytes()
    final_pins = {path: identity(body) for path, body in source.items()}
    assert len(final_pins) == 30
    for row in final["files"]:
        check(source[row["path"]], row)

    receipt = read_json(here / "native-r1/receipt.json")
    encoded = (here / "native-r1/execution.json.gz.b64").read_bytes()
    check(encoded, receipt["execution_archive"])
    raw, execution = unpack(here / "native-r1/execution.json.gz.b64")
    check(raw, receipt["execution_decoded"])
    assert execution["source_before"] == execution["source_after"] == receipt["source_pins"]
    for name, row in execution["source_images"].items():
        body = base64.b64decode(row["base64"], validate=True)
        check(body, row)
        check(body, execution["source_before"][name])
    assert len(execution["source_images"]) == 30
    verify_cli(execution["cli"])
    assert len(execution["cli"]) == 29
    assert all(row["passed"] for row in execution["subtests"])
    log = (here / "native-r1/unittest.txt").read_bytes()
    check(log, receipt["test_log"])
    assert receipt["passed"] is False and receipt["errors"] == 4 and receipt["failures"] == 0
    assert log.count(b"ModuleNotFoundError: No module named 'pytest'") == 4
    assert sum(line.endswith(b" ... ok") for line in log.splitlines()) == 47

    recovery = read_json(here / "pytest-recovery/receipt.json")
    assert recovery["returncode"] == 0 and recovery["source_preserved"]
    assert recovery["source_before"] == recovery["source_after"] == receipt["source_pins"]
    for name, row in recovery["outputs"].items():
        check((here / "pytest-recovery" / relative(name)).read_bytes(), row)
    tests = ET.fromstring((here / "pytest-recovery/junit.xml").read_bytes()).findall(".//testcase")
    assert len(tests) == 58 and all(test.find("failure") is None and test.find("error") is None for test in tests)

    failed_shape = read_json(here / "shape-r1.json")
    shape = read_json(here / "shape-r2.json")
    assert failed_shape["returncode"] == 1 and "AttributeError" in failed_shape["stderr"]
    assert shape["passed"] and shape["new_cli_processes"] == 2 and shape["original_raw_witness_preserved"]
    assert shape["cli"][0]["fixture_base64"] == failed_shape["fixture"]
    assert shape["source_before"] == shape["source_after"] == final_pins
    verify_cli(shape["cli"])

    nested = {}
    for relative_root in ("historical/offer", "historical/independent", "independent"):
        root = here / relative_root
        packet = read_json(root / "manifest.json")
        if relative_root != "historical/offer":
            for row in packet["files"]:
                check((root / relative(row["path"])).read_bytes(), row)
        for path in root.glob("*.json.gz.b64"):
            nested[relative_root + "/" + path.name] = verify_inventory_archive(path)

    print(json.dumps({"status": "BYTE_CUSTODY_VERIFIED", "publication_payloads": len(seen),
                      "baseline_source_images": len(snapshot["files"]), "r1_source_images": 30,
                      "r1_cli_processes_archived": 29, "r1_executed_unittest_methods": 47,
                      "recovered_pytest_tests": len(tests), "r2_cli_processes_archived": 2,
                      "nested_archives": nested, "product_or_test_execution": False}))


if __name__ == "__main__":
    main()
