#!/usr/bin/env python3
"""Independent terminal receiving; only synthetic saved reports, no server or inputs.

Pass original and frozen candidate freight_packets directories. This does not import
or execute candidate test code. Outputs are append-only in a new --output directory.
The Linux-only delivery witnesses use RLIMIT_FSIZE and /dev/full, not monkeypatches.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import os
from pathlib import Path
import random
import re
import resource
import signal
import stat
import subprocess
import sys
import traceback
import zipfile


IDS = ['Dock/A<&"', 'Dock?A<&"']
HIDDEN = "UNSELECTED_PRIVATE_PACKET_4ea7c14c"
PACKETS = ["packets/opaque-9b0ac7.html", "packets/unrelated-location-14.html"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def inventory(root):
    result = {}
    for p in sorted(root.rglob("*")):
        s = p.lstat()
        row = {"mode": stat.S_IMODE(s.st_mode), "inode": s.st_ino, "device": s.st_dev,
               "mtime_ns": s.st_mtime_ns, "size": s.st_size}
        if p.is_symlink():
            row.update(type="symlink", target=os.readlink(p))
        elif p.is_file():
            row.update(type="file", sha256=sha(p.read_bytes()))
        elif p.is_dir():
            row.update(type="directory")
        else:
            row.update(type="other")
        result[p.relative_to(root).as_posix()] = row
    return result


def fixture(root):
    root.mkdir()
    (root / "packets").mkdir()
    rows = []
    for n, load_id in enumerate(IDS):
        noise = random.Random(11073 + n).randbytes(4096).hex()
        data = ("<!doctype html>\n<title>" + html.escape(load_id) + "</title>\n"
                "<p>Saved native packet " + str(n) + "</p><pre>" + noise + "</pre>\n").encode()
        (root / PACKETS[n]).write_bytes(data)
        rows.append({"load_id": load_id, "file": PACKETS[n], "carrier": "Synthetic only"})
    (root / "packets/not-selected.html").write_bytes(HIDDEN.encode())
    rows.insert(1, {"load_id": HIDDEN, "file": "packets/not-selected.html"})
    report = {"packets": rows, "generated_fixture": True, "global_private_marker": HIDDEN,
              "stops": [{"load_id": IDS[1], "stop_no": 9, "note": "retained <literal>"},
                        {"load_id": IDS[0], "stop_no": 2, "note": "second before first"},
                        {"load_id": IDS[0], "stop_no": 1, "note": "evidence identity"}],
              "flags": [{"load_id": HIDDEN, "detail": HIDDEN}],
              "fines": [], "settlements": [], "exceptions": []}
    save_json(root / "summary.json", report)
    (root / "audit.jsonl").write_text(json.dumps({"private": HIDDEN}) + "\n")
    (root / "reports.csv").write_text("private\n" + HIDDEN + "\n")


def native_oracle(args):
    # This subprocess imports only the original producer's App and handoff code.
    sys.path.insert(0, str(args.baseline))
    from freightpkt.web import App
    import freightpkt.web as web
    import freightpkt.handoff as handoff
    source = args.output / "saved-report"
    oracle = args.output / "oracle"
    oracle.mkdir()
    app = App(args.output / "original-inputs-intentionally-absent", source)
    first = app.summary()
    records = {
        IDS[0]: {"decision": "approve", "note": "literal <&\" café> final approval",
                 "at": "2026-09-13T11:10:00+00:00", "reviewer_extra": {"ticket": "manual/44"},
                 "evidence_version": first["evidence_versions"][IDS[0]],
                 "history": [{"decision": "reject", "note": "previous rejection kept",
                              "at": "2026-09-13T10:00:00+00:00",
                              "evidence_version": "0" * 64},
                             {"decision": "adjust", "note": "previous adjustment kept",
                              "at": "2026-09-13T10:30:00+00:00",
                              "evidence_version": first["evidence_versions"][IDS[0]]}]},
        IDS[1]: {"decision": "approve", "note": "old approval must stay stale",
                 "at": "2026-09-12T10:00:00+00:00", "evidence_version": "f" * 64,
                 "history": [{"decision": "clear", "note": "history clear retained",
                              "at": "2026-09-11T10:00:00+00:00", "evidence_version": "a" * 64}]},
        HIDDEN: {"decision": "reject", "note": HIDDEN, "history": []},
    }
    save_json(source / "decisions.json", records)
    view = app.summary()
    save_json(oracle / "original-projection.json", view)
    bundles = []
    for n, load_id in enumerate(IDS):
        filename, content = app.review_bundle(load_id, view["evidence_versions"][load_id],
                                             view["review_versions"][load_id])
        path = oracle / f"native-{n + 1}.zip"
        path.write_bytes(content)
        bundles.append({"load_id": load_id, "original_filename": filename,
                        "path": path.name, "sha256": sha(content)})
    save_json(oracle / "producer.json", {
        "web_path": str(Path(web.__file__).resolve()), "web_sha256": sha(Path(web.__file__).read_bytes()),
        "handoff_path": str(Path(handoff.__file__).resolve()),
        "handoff_sha256": sha(Path(handoff.__file__).read_bytes()), "bundles": bundles,
        "input_directory_exists": app.data_dir.exists(),
    })
    print("unchanged native App.review_bundle: two constituent oracles saved")
    return 0


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    fixture(args.output / "saved-report")
    deliveries = args.output / "deliveries"
    deliveries.mkdir()
    events = args.output / "processes"
    events.mkdir()
    receipt = {"schema": "independent-freight-terminal-receiving.v1", "outcome": "RUNNING",
               "python": sys.version, "python_executable": sys.executable,
               "baseline": str(args.baseline), "candidate": str(args.candidate),
               "candidate_tests_used": False, "live_server_or_service_calls": 0,
               "product_source_mutations": 0, "checks": [], "processes": []}
    baseline_before = inventory(args.baseline)
    candidate_before = inventory(args.candidate)

    def check(name, value, details=None):
        receipt["checks"].append({"name": name, "passed": bool(value), "details": details})
        save_json(args.output / "receipt.json", receipt)
        if not value:
            raise AssertionError(name)

    def process(name, command, cwd, *, full_stdout=False, limit=None):
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONHASHSEED"] = "0"
        env.pop("PYTHONUNBUFFERED", None)
        env.pop("PYTHONPATH", None)

        def set_limit():
            signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
            resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))

        if full_stdout:
            with open("/dev/full", "wb") as stream:
                result = subprocess.run(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                        stdout=stream, stderr=subprocess.PIPE, timeout=20)
            stdout = b""
        else:
            result = subprocess.run(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20,
                                    preexec_fn=set_limit if limit is not None else None)
            stdout = result.stdout
        (events / f"{name}.stdout").write_bytes(stdout)
        (events / f"{name}.stderr").write_bytes(result.stderr)
        record = {"name": name, "command": list(map(str, command)), "cwd": str(cwd),
                  "returncode": result.returncode, "stdout_sha256": sha(stdout),
                  "stderr_sha256": sha(result.stderr),
                  "stdout_target": "/dev/full" if full_stdout else "captured pipe",
                  "kernel_file_size_limit": limit}
        receipt["processes"].append(record)
        save_json(events / f"{name}.json", record)
        save_json(args.output / "receipt.json", receipt)
        return result, stdout

    def cli(name, destination, **kwargs):
        command = [sys.executable, "-B", "-m", "freightpkt", "export-reviews", "--out",
                   str(args.output / "saved-report")]
        for load_id in reversed(IDS):
            command.extend(["--load", load_id])
        command.extend(["--destination", str(destination)])
        return process(name, command, args.candidate, **kwargs)

    try:
        result, _ = process("01-original-native-oracle",
                            [sys.executable, "-B", str(Path(__file__).resolve()),
                             "--baseline", str(args.baseline), "--candidate", str(args.candidate),
                             "--output", str(args.output), "--oracle"], args.baseline)
        check("original API oracle completed", result.returncode == 0)
        source = args.output / "saved-report"
        original = inventory(source)
        save_json(args.output / "source-before.json", original)
        projection = json.loads((args.output / "oracle/original-projection.json").read_text())
        check("native positive and stale meanings established",
              projection["decisions"][IDS[0]]["review_state"] == "current"
              and projection["decisions"][IDS[1]]["review_state"] == "stale")
        labels = [re.sub(r"[^A-Za-z0-9_-]+", "-", x).strip("-")[:64] for x in IDS]
        check("distinct literal IDs share a sanitized label", IDS[0] != IDS[1] and labels[0] == labels[1])
        destination = deliveries / "ordinary.zip"
        result, stdout = cli("02-exact-constituents", destination)
        check("actual terminal export succeeded", result.returncode == 0 and b"saved 2 load review(s)" in stdout)
        data = destination.read_bytes()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            check("published ZIP is complete", archive.testzip() is None)
            names = archive.namelist()
            check("outer paths unique", len(names) == len(set(names)))
            manifest = json.loads(archive.read("manifest.json"))
            check("literal sorted selection retained", manifest["load_ids"] == sorted(IDS))
            native_details = []
            expected_names = {"index.html", "manifest.json"}
            for record in manifest["reviews"]:
                load_id = record["load_id"]
                number = IDS.index(load_id) + 1
                with zipfile.ZipFile(args.output / f"oracle/native-{number}.zip") as native:
                    native_names = native.namelist()
                    check("original native five-file contract " + str(number),
                          set(native_names) == {"index.html", "packet.html", "evidence.json", "review.json", "manifest.json"})
                    for name in native_names:
                        path = record["directory"] + "/" + name
                        expected_names.add(path)
                        want = native.read(name)
                        actual = archive.read(path)
                        check(f"constituent {number}/{name} byte identity", actual == want)
                        native_details.append({"load_id": load_id, "path": path, "bytes": len(actual), "sha256": sha(actual)})
                check("saved identity versions retained " + str(number),
                      record["evidence_version"] == projection["evidence_versions"][load_id]
                      and record["review_version"] == projection["review_versions"][load_id]
                      and record["review_state"] == projection["decisions"][load_id]["review_state"])
            check("only native constituents and batch cover/manifest included", set(names) == expected_names)
            check("opaque file property preserved in evidence",
                  all(json.loads(archive.read(row["directory"] + "/evidence.json"))["packets"][0]["file"]
                      == PACKETS[IDS.index(row["load_id"])] for row in manifest["reviews"]))
            check("source identity hashes exact",
                  manifest["source_summary_sha256"] == sha((source / "summary.json").read_bytes())
                  and manifest["source_decisions_sha256"] == sha((source / "decisions.json").read_bytes()))
            check("every advertised member size and checksum exact",
                  {x["path"] for x in manifest["files"]} == expected_names - {"manifest.json"}
                  and all(x["bytes"] == len(archive.read(x["path"]))
                          and x["sha256"] == sha(archive.read(x["path"])) for x in manifest["files"]))
            cover = archive.read("index.html").decode()
            check("cover links exact native directories and literal escaped IDs",
                  all(html.escape(x, quote=True) in cover for x in IDS)
                  and all('href="' + x["directory"] + '/index.html"' in cover for x in manifest["reviews"]))
            check("unselected content excluded", all(HIDDEN.encode() not in archive.read(n) for n in names))
            save_json(args.output / "native-identity.json", native_details)
        check("successful export source custody", inventory(source) == original)
        check("positive run leaves no staging", not list(deliveries.glob(".freight-reviews-*")))

        symlink = deliveries / "existing-source-link.zip"
        symlink.symlink_to(source / PACKETS[0])
        link_before = inventory(deliveries)[symlink.name]
        result, _ = cli("03-no-clobber-source-symlink", symlink)
        check("source-targeting symlink refuses", result.returncode == 2 and b"already exists" in result.stderr)
        check("symlink itself and its source target remain unchanged",
              inventory(deliveries)[symlink.name] == link_before and inventory(source) == original)

        limit = max(row["size"] for row in original.values() if row["type"] == "file") + 512
        check("kernel staging limit fits every source file but not complete ZIP", limit < len(data),
              {"limit": limit, "complete_zip_bytes": len(data)})
        failed = deliveries / "kernel-write-failure.zip"
        result, _ = cli("04-kernel-staging-write-failure", failed, limit=limit)
        check("real kernel write failure refuses before publication",
              result.returncode == 2 and b"File too large" in result.stderr and not os.path.lexists(failed))
        check("write failure preserves sources and removes only own staging",
              inventory(source) == original and not list(deliveries.glob(".freight-reviews-*")))

        delivered = deliveries / "stdout-failed.zip"
        result, _ = cli("05-publication-before-stdout-failure", delivered, full_stdout=True)
        check("post-publication status delivery failure observed",
              result.returncode != 0 and b"No space left on device" in result.stderr)
        check("failed status output leaves exact complete delivered ZIP", delivered.read_bytes() == data)
        delivered_before = inventory(deliveries)[delivered.name]
        retry, _ = cli("06-same-destination-recovery", delivered)
        check("retry refuses to overwrite the already delivered result",
              retry.returncode == 2 and b"already exists" in retry.stderr
              and inventory(deliveries)[delivered.name] == delivered_before)
        check("all cases preserve input paths bytes identity and timestamps", inventory(source) == original)
        check("no original input directory or source staging was created",
              not (args.output / "original-inputs-intentionally-absent").exists()
              and not list(deliveries.glob(".freight-reviews-*")))
        check("original and candidate production source preserved",
              inventory(args.baseline) == baseline_before and inventory(args.candidate) == candidate_before)
        save_json(args.output / "source-after.json", inventory(source))
        receipt.update(outcome="ACCEPT_WITH_EXPLICIT_DELIVERY_BOUNDARY", native_api_processes=1,
                       candidate_cli_processes=5, native_member_byte_comparisons=10,
                       exact_archive_sha256=sha(data),
                       ownership="Source/API/format agreement remains a separate held adoption gate.",
                       delivery_boundary="A completed no-clobber publication survives a later stdout failure; a nonzero process exit does not by itself prove no ZIP exists. Inspect destination; retry cannot replace it.")
    except BaseException:
        (args.output / "receiving-failure.txt").write_text(traceback.format_exc())
        receipt["outcome"] = "REVISE_OR_INTERRUPTED"
        raise
    finally:
        save_json(args.output / "receipt.json", receipt)
    print(json.dumps({"outcome": receipt["outcome"], "processes": len(receipt["processes"]),
                      "checks": len(receipt["checks"]), "receipt_sha256": sha((args.output / "receipt.json").read_bytes())}))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--oracle", action="store_true")
    arguments = parser.parse_args()
    arguments.baseline = arguments.baseline.resolve()
    arguments.candidate = arguments.candidate.resolve()
    arguments.output = arguments.output.resolve()
    raise SystemExit(native_oracle(arguments) if arguments.oracle else main(arguments))
