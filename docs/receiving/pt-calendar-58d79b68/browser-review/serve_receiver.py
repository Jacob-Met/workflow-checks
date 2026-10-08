"""Run the exact PT server on an ephemeral local port for independent browser receiving."""
from __future__ import annotations
import argparse
import json
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--source", type=Path, required=True)
ap.add_argument("--fixture", type=Path, required=True)
args = ap.parse_args()
sys.path.insert(0, str(args.source.resolve()))
from ptauth.web import App, make_handler

app = App(args.fixture / "data", args.fixture / "out", clinic_timezone="America/Los_Angeles")
server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
print(json.dumps({"url": "http://127.0.0.1:" + str(server.server_port),
    "source": str(args.source.resolve()), "fixture": str(args.fixture.resolve()),
    "clinic_timezone": app.timezone_label}), flush=True)
try:
    server.serve_forever()
finally:
    server.server_close()
