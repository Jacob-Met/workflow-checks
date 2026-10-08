"""Receive every byte through the actual bundled loopback server, then stop it."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import selectors
import signal
import socket
import subprocess
import sys
import urllib.request

DEMO = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--site", type=Path, required=True)
parser.add_argument("--server-script", type=Path, default=DEMO / "tools/serve.py")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
files = ["app.mjs", "data.mjs", "index.html", "model.mjs", "styles.css"]
pins = {name: hashlib.sha256((args.site / name).read_bytes()).hexdigest() for name in files}
process = subprocess.Popen(
    [sys.executable, str(args.server_script), "--site", str(args.site), "--port", "0"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
checks = []
origin = None
received = {}
try:
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    if not selector.select(timeout=5):
        raise AssertionError("Bundled server did not report its loopback listener")
    first = process.stdout.readline()
    selector.close()
    match = re.search(r"http://127\.0\.0\.1:(\d+)/", first)
    assert match, first
    port = int(match.group(1))
    origin = "http://127.0.0.1:" + str(port)
    for name in files:
        path = "/" if name == "index.html" else "/" + name
        with urllib.request.urlopen(origin + path, timeout=3) as response:
            body = response.read()
            assert hashlib.sha256(body).hexdigest() == pins[name], name
            content_type = response.headers.get_content_type()
            if name.endswith(".mjs"):
                assert content_type in ("text/javascript", "application/javascript"), content_type
            if name.endswith(".html"):
                assert content_type == "text/html", content_type
            received[name] = {"sha256": pins[name], "content_type": content_type, "bytes": len(body)}
    checks.append("all five installed files served byte-identical over actual loopback HTTP")
    checks.append("browser modules served with a JavaScript MIME type")
finally:
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
    try:
        stdout, stderr = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
        raise AssertionError("Server required forced termination")
assert process.returncode == 0, stderr
assert origin is not None
with socket.socket() as probe:
    probe.settimeout(1)
    assert probe.connect_ex(("127.0.0.1", port)) != 0
checks.append("owned server exited with zero status and listener closed")
assert {name: hashlib.sha256((args.site / name).read_bytes()).hexdigest() for name in files} == pins
receipt = {
    "schema": "freight-whatif.served-receipt.v1", "python": sys.version.split()[0],
    "site": str(args.site), "origin": origin, "passed": len(checks), "failed": 0,
    "checks": checks, "received": received, "source_unchanged": True,
    "server_sha256": hashlib.sha256(args.server_script.read_bytes()).hexdigest(),
    "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "cleanup": {"owned_pid": process.pid, "exit_code": process.returncode, "loopback_port_closed": True},
}
with args.output.open("x") as stream:
    stream.write(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt))
