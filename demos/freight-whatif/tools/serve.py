"""Serve the bundled synthetic demo on loopback. No third-party packages."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--port", type=int, default=8765)
parser.add_argument("--site", type=Path, default=Path(__file__).resolve().parents[1] / "site")
args = parser.parse_args()
if not 0 <= args.port <= 65535:
    parser.error("--port must be from 0 to 65535 (0 chooses an unused port)")
site = args.site.resolve()
if not (site / "index.html").is_file():
    parser.error("--site must point to the freight what-if site directory")
handler = partial(SimpleHTTPRequestHandler, directory=str(site))
server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
print(f"Freight what-if: http://127.0.0.1:{server.server_port}/  (Ctrl-C to stop)", flush=True)
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    server.server_close()
