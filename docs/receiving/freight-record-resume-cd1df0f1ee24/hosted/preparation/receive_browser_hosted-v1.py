#!/usr/bin/env python3
"""PROPOSAL ONLY. One hosted run of the byte-exact v4 Freight receiver.
The supervisor owns only its fresh Node session and the Chrome session registered
by its executable shim. It never changes or retries the receiver or product.
"""
import argparse, base64, gzip, hashlib, io, json, os, pathlib, signal
import subprocess, sys, tarfile, time, traceback

ARCHIVE_SHA = "b06e59f6bdefd3c9d988cc5a9a883439364aaac7982a2e3a0184be1022a58e21"
DRIVER_SHA = "d44e2d17eeb3e583d11e856fbda1bb988d9ec8f871bf40e3f33f2b5425d333d8"
PUPPETEER_VERSION = "25.12.0"

def digest(b):
    return hashlib.sha256(b).hexdigest()

def file_meta(p):
    b = p.read_bytes()
    return {"bytes": len(b), "sha256": digest(b)}

def write_json(p, value):
    b = (json.dumps(value, indent=2) + "\n").encode()
    tmp = p.with_name(p.name + ".new")
    tmp.write_bytes(b)
    tmp.replace(p)

def proc(pid):
    try:
        p = pathlib.Path("/proc") / str(pid)
        raw = (p / "stat").read_text()
        end = raw.rfind(")")
        a = raw[end + 2:].split()
        args = (p / "cmdline").read_bytes().split(b"\0")
        return {"pid": pid, "ppid": int(a[1]), "pgid": int(a[2]),
                "sid": int(a[3]), "state": a[0], "start_ticks": int(a[19]),
                "uid": p.stat().st_uid, "comm": raw[raw.find("(")+1:end],
                "args": [x.decode(errors="replace") for x in args if x]}
    except (OSError, ValueError, IndexError):
        return None

def group(pgid):
    rows = []
    for p in pathlib.Path("/proc").iterdir():
        if p.name.isdigit():
            row = proc(int(p.name))
            if row and row["pgid"] == pgid:
                rows.append(row)
    return rows

def public_row(row):
    return {k: v for k, v in row.items() if k != "args"}

SHIM = r'''#!/usr/bin/env python3
import json, os, pathlib, sys, time
pid = os.getpid()
if os.getpgrp() != pid:
    os.setsid()
assert os.getpgrp() == pid and os.getsid(0) == pid
profile = os.environ["FREIGHT_OWNED_PROFILE"]
assert "--user-data-dir=" + profile in sys.argv[1:]
assert "--no-sandbox" not in sys.argv and "--disable-setuid-sandbox" not in sys.argv
p = pathlib.Path(os.environ["FREIGHT_BROWSER_IDENTITY"])
assert not p.exists(), "A second browser launch is forbidden"
raw = pathlib.Path("/proc/self/stat").read_text()
a = raw[raw.rfind(")")+2:].split()
data = {"pid": pid, "pgid": os.getpgrp(), "sid": os.getsid(0),
        "start_ticks": int(a[19]), "profile": profile,
        "registered_before_exec_unix": time.time(),
        "chrome": os.environ["FREIGHT_CHROME"]}
p.write_text(json.dumps(data, indent=2) + "\n")
os.execv(data["chrome"], [data["chrome"], *sys.argv[1:]])
'''

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--packet", required=True)
    ap.add_argument("--puppeteer-root", required=True)
    ap.add_argument("--chrome", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--emit-bundle", action="store_true")
    args = ap.parse_args()
    root = pathlib.Path(args.root).resolve(strict=True)
    packet = pathlib.Path(args.packet).resolve(strict=True)
    pp_root = pathlib.Path(args.puppeteer_root).resolve(strict=True)
    chrome = pathlib.Path(args.chrome).resolve(strict=True)
    out = pathlib.Path(args.output).absolute()
    assert str(out) == str(out.resolve()) and out != pathlib.Path("/")
    out.mkdir(parents=True, exist_ok=False)
    report = {"format": "freight-hosted-attempt/1", "started": time.time(),
              "automatic_retry": False, "product_receiver_modified": False,
              "native_failed_attempt_preserved_separately": True,
              "signals": [], "observations": [], "errors": [], "pass": False}
    run = out / "run"
    identity_path = out / "browser-identity.json"
    journal = out / "lifecycle.ndjson"
    child = None
    node_identity = None
    browser_identity = None
    seen_browser = {}
    pin_rows = []
    cleanup_ok = True

    def event(kind, **fields):
        row = {"unix": time.time(), "kind": kind, **fields}
        with journal.open("a") as f:
            f.write(json.dumps(row) + "\n")

    def observe_browser():
        nonlocal browser_identity
        if identity_path.exists() and browser_identity is None:
            browser_identity = json.loads(identity_path.read_text())
            assert browser_identity["pgid"] == browser_identity["pid"] == browser_identity["sid"]
            assert browser_identity["profile"] == str(run / "profile")
            event("browser-shim-registration", identity=browser_identity)
        if browser_identity:
            pgid = browser_identity["pgid"]
            rows = group(pgid)
            leader = next((r for r in rows if r["pid"] == pgid), None)
            anchor = leader and leader["start_ticks"] == browser_identity["start_ticks"]
            if not anchor:
                anchor = any(seen_browser.get(r["pid"]) == r["start_ticks"] for r in rows)
            if rows:
                assert anchor, "Browser group lacks an original identity anchor"
                assert all(r["uid"] == os.getuid() and r["sid"] == pgid for r in rows)
                if leader:
                    assert leader["start_ticks"] == browser_identity["start_ticks"]
                    # The shim records before exec. Its exact same PID/start is the authority
                    # until Chrome exec; afterwards require its exact owned profile argument.
                    if leader["comm"] not in ("python3", "python"):
                        assert "--user-data-dir=" + str(run / "profile") in leader["args"]
                for row in rows:
                    if row["pid"] in seen_browser:
                        assert seen_browser[row["pid"]] == row["start_ticks"], "PID reused"
                    seen_browser[row["pid"]] = row["start_ticks"]
            return rows
        return []

    def stop_browser():
        rows = observe_browser()
        if not rows:
            return
        assert browser_identity is not None
        pgid = browser_identity["pgid"]
        for sig, wait_seconds in [(signal.SIGTERM, 5), (signal.SIGKILL, 2)]:
            rows = observe_browser()
            live = [r for r in rows if r["state"] != "Z"]
            if not live:
                break
            report["signals"].append({"target": "browser-session", "signal": sig.name,
                                      "pgid": pgid, "members": [public_row(r) for r in rows]})
            event("signal", target="browser-session", pgid=pgid, signal=sig.name)
            os.killpg(pgid, sig)
            deadline = time.monotonic() + wait_seconds
            while time.monotonic() < deadline:
                if not any(r["state"] != "Z" for r in observe_browser()):
                    break
                time.sleep(.1)
        final = observe_browser()
        report["browser_group_after_cleanup"] = [public_row(r) for r in final]
        assert not any(r["state"] != "Z" for r in final), "Owned browser still running"

    def stop_node():
        if child is None or child.poll() is not None:
            return
        current = proc(child.pid)
        assert current and node_identity and current["start_ticks"] == node_identity["start_ticks"]
        assert current["pgid"] == current["sid"] == child.pid
        for sig, seconds in [(signal.SIGTERM, 3), (signal.SIGKILL, 2)]:
            if child.poll() is not None:
                break
            current = proc(child.pid)
            assert current and current["start_ticks"] == node_identity["start_ticks"]
            rows = group(child.pid)
            assert all(r["uid"] == os.getuid() and r["sid"] == child.pid for r in rows)
            report["signals"].append({"target": "node-session", "signal": sig.name,
                                      "pgid": child.pid, "members": [public_row(r) for r in rows]})
            event("signal", target="node-session", pgid=child.pid, signal=sig.name)
            os.killpg(child.pid, sig)
            try:
                child.wait(timeout=seconds)
            except subprocess.TimeoutExpired:
                pass
        assert child.poll() is not None, "Owned Node still running"

    try:
        event("supervisor-start")
        assert digest(packet.read_bytes()) == ARCHIVE_SHA
        unpack = out / "packet"
        unpack.mkdir()
        with tarfile.open(packet, "r:gz") as tar:
            members = tar.getmembers()
            assert all(m.isfile() and not m.name.startswith("/") and ".." not in pathlib.PurePosixPath(m.name).parts for m in members)
            for m in members:
                dst = unpack / m.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(tar.extractfile(m).read())
        manifest = json.loads((unpack / "manifest.json").read_text())
        for row in manifest["members"]:
            p = unpack / row["path"]
            assert file_meta(p) == {"bytes": row["bytes"], "sha256": row["sha256"]}
        pp = json.loads((pp_root / "package.json").read_text())
        assert pp["name"] == "puppeteer-core" and pp["version"] == PUPPETEER_VERSION
        driver = root / "demos/freight-whatif/tests/scenario-record-browser.mjs"
        assert digest(driver.read_bytes()) == DRIVER_SHA
        assert driver.read_bytes() == (unpack / "preparation/browser-receiver-v4.mjs").read_bytes()
        cfg = json.loads((unpack / "preparation/config-ui-v1-attempt1.json").read_text())
        cfg["runRoot"] = str(run)
        cfg["baselineRoot"] = str(unpack / "inputs/baseline")
        cfg["candidateRoot"] = str(root / "demos/freight-whatif/site")
        for row in cfg["sourcePins"]:
            parent = cfg["baselineRoot"] if row["route"] == "baseline" else cfg["candidateRoot"]
            row["path"] = str(pathlib.Path(parent) / pathlib.Path(row["path"]).name)
        for row in cfg["fixturePins"]:
            row["path"] = str(unpack / "inputs/fixtures" / row["name"])
        shim = out / "owned-chrome-launcher.py"
        shim.write_text(SHIM)
        shim.chmod(0o700)
        cfg["chromiumPath"] = str(shim)
        cfg["puppeteerPath"] = str(pp_root / "lib/puppeteer/puppeteer-core.js")
        config = out / "hosted-config.json"
        write_json(config, cfg)
        for p in [driver, config, pathlib.Path(__file__).resolve(), shim, packet,
                  *[pathlib.Path(r["path"]) for r in cfg["sourcePins"]],
                  *[pathlib.Path(r["path"]) for r in cfg["fixturePins"]]]:
            pin_rows.append({"path": str(p), **file_meta(p)})
        report["input_pins"] = pin_rows
        report["checkout"] = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        report["environment"] = {
            "node": subprocess.check_output(["node", "--version"], text=True).strip(),
            "chrome": subprocess.check_output([str(chrome), "--version"], text=True, timeout=10).strip(),
            "puppeteer_core": pp["version"], "default_sandbox": True,
            "github_sha": os.environ.get("GITHUB_SHA"), "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_event_name": os.environ.get("GITHUB_EVENT_NAME")}
        lock = pp_root.parent.parent / "package-lock.json"
        assert lock.exists()
        (out / "temporary-dependency-package-lock.json").write_bytes(lock.read_bytes())
        report["temporary_dependency_lock"] = file_meta(lock)
        write_json(out / "preflight.json", report)
        env = os.environ.copy()
        env.update(FREIGHT_OWNED_PROFILE=str(run / "profile"),
                   FREIGHT_BROWSER_IDENTITY=str(identity_path), FREIGHT_CHROME=str(chrome))
        with (out / "stdout.log").open("wb") as stdout, (out / "stderr.log").open("wb") as stderr:
            child = subprocess.Popen(["node", str(driver), str(config)], stdout=stdout, stderr=stderr,
                                     start_new_session=True, env=env)
            node_identity = proc(child.pid)
            assert node_identity and node_identity["pgid"] == node_identity["sid"] == child.pid
            event("node-start", identity=public_row(node_identity))
            report["node_identity"] = public_row(node_identity)
            deadline = time.monotonic() + 255
            previous = None
            while child.poll() is None:
                rows = observe_browser()
                observation = {
                    "input_directory_present": (run / "inputs").is_dir(),
                    "devtools_active_port_present": (run / "profile/DevToolsActivePort").is_file(),
                    "partial": file_meta(run / "browser-receipt.partial.json") if (run / "browser-receipt.partial.json").is_file() else None,
                    "final": file_meta(run / "browser-receipt.json") if (run / "browser-receipt.json").is_file() else None,
                    "browser_members": [public_row(r) for r in rows],
                    "stdout_bytes": (out / "stdout.log").stat().st_size,
                    "stderr_bytes": (out / "stderr.log").stat().st_size}
                if observation != previous:
                    event("observation", **observation)
                    previous = observation
                if time.monotonic() >= deadline:
                    report["supervisor_timed_out"] = True
                    event("supervisor-timeout")
                    break
                time.sleep(.2)
            report.setdefault("supervisor_timed_out", False)
    except BaseException:
        report["errors"].append(traceback.format_exc())
        event("supervisor-error", error=report["errors"][-1])
    finally:
        # Persist before any close operation. Cleanup must not delay the only receipt.
        write_json(out / "supervisor-receipt.pre-cleanup.json", report)
        for cleanup in [stop_node, stop_browser]:
            try:
                cleanup()
            except BaseException:
                cleanup_ok = False
                report["errors"].append(traceback.format_exc())
        report["cleanup_complete"] = cleanup_ok
        report["exit_code"] = child.poll() if child else None
        report["source_unchanged"] = bool(pin_rows) and all(file_meta(pathlib.Path(r["path"])) == {"bytes":r["bytes"],"sha256":r["sha256"]} for r in pin_rows)
        raw_report = run / "browser-receipt.json"
        if raw_report.is_file():
            observed = json.loads(raw_report.read_text())
            report["browser_receipt_summary"] = {k: observed.get(k) for k in ["pass","completed","browserClosed","sourceUnchanged","fatal","groups"]}
            events = observed.get("downloadEvents", [])
            report["final_event_gate"] = all(not observed.get(k) for k in ["pageErrors","externalRequests","consoleErrors","storageWrites"])
            report["final_download_gate"] = len([e for e in events if e.get("kind") == "begin"]) == len(observed.get("downloads", []))
            report["pass"] = (report["exit_code"] == 0 and observed.get("pass") is True and len(observed.get("groups", [])) == 17
                              and report["source_unchanged"] and cleanup_ok and not report["errors"]
                              and not report.get("supervisor_timed_out") and report["final_event_gate"] and report["final_download_gate"])
        report["ended"] = time.time()
        write_json(out / "supervisor-receipt.json", report)
        evidence = {}
        for p in sorted(out.rglob("*")):
            rel = p.relative_to(out)
            if p.is_file() and "profile" not in rel.parts and "packet" not in rel.parts:
                evidence[str(rel)] = p.read_bytes()
        index = {name: {"bytes":len(b),"sha256":digest(b)} for name,b in evidence.items()}
        write_json(out / "evidence-index.json", index)
        evidence["evidence-index.json"] = (out / "evidence-index.json").read_bytes()
        if args.emit_bundle:
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                for name, b in sorted(evidence.items()):
                    info = tarfile.TarInfo(name)
                    info.size = len(b); info.mtime = 0; info.mode = 0o644
                    tar.addfile(info, io.BytesIO(b))
            archive = gzip.compress(buf.getvalue(), mtime=0)
            assert len(archive) <= 8 * 1024 * 1024, "Evidence exceeds log transport bound; native job files retained"
            encoded = base64.b64encode(archive).decode()
            print("FREIGHT_HOSTED_BUNDLE_BEGIN " + json.dumps({"bytes":len(archive),"sha256":digest(archive),"files":len(evidence)}), flush=True)
            for start in range(0,len(encoded),60000):
                print("FREIGHT_HOSTED_BUNDLE_CHUNK " + encoded[start:start+60000], flush=True)
            print("FREIGHT_HOSTED_BUNDLE_END", flush=True)
        print(json.dumps({"pass":report["pass"],"receipt":str(out/"supervisor-receipt.json")}), flush=True)
    return 0 if report["pass"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
