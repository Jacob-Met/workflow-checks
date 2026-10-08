"""Disposable real native freight app used only by the browser acceptance carrier."""
import hashlib, json, signal, sys
from http.server import ThreadingHTTPServer
from pathlib import Path

source, state = map(Path, sys.argv[1:3])
sys.dont_write_bytecode = True
sys.path.insert(0, str(source))
from freightpkt.synth import generate
from freightpkt.pipeline import run
from freightpkt.web import App, make_handler

state.mkdir(parents=True, exist_ok=True)
generate(state / "data", n_loads=24, seed=7)
run(state / "data", state / "out")
app = App(state / "data", state / "out")
server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
pins = [{"path": str(p.relative_to(source)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in sorted((source / "freightpkt").glob("*")) if p.is_file()]
ready = {"base_url": f"http://127.0.0.1:{server.server_port}", "source": str(source),
         "state": str(state), "python": sys.version, "source_files": pins,
         "fixture": {"generator": "freightpkt.synth.generate", "n_loads": 24, "seed": 7,
                     "pipeline": "freightpkt.pipeline.run", "external_requests": False}}
(state / "server-receipt.json").write_text(json.dumps(ready, indent=2) + "\n")
print(json.dumps(ready), flush=True)
signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(0)))
try:
    server.serve_forever(poll_interval=.05)
finally:
    server.server_close()
