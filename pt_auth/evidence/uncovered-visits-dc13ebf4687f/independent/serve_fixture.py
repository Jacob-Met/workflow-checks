"""One ephemeral real App, pinned package, authored input/output, loopback only."""
import hashlib
import json
import signal
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

spec = json.loads(sys.argv[1])
root = Path(__file__).resolve().parent
source = Path(spec['source']).resolve()
data, output = Path(spec['data']).resolve(), Path(spec['output']).resolve()
if root not in data.parents or root not in output.parents:
    raise RuntimeError('fixture inputs/outputs must be in independent review root')
if not (data / 'schedule.csv').is_file() or not (output / 'summary.json').is_file():
    raise RuntimeError('preexisting authored input/report required; no generator fallback')
sys.path.insert(0, str(source))
from ptauth.web import App, UI, make_handler
import ptauth.web


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


app = App(data, output, clinic_timezone='UTC')
base = make_handler(app)


class Guarded(base):
    def do_GET(self):
        emit({'request': 'GET', 'path': self.path})
        if self.path not in ('/', '/api/summary', '/out/uncovered_visits.csv', '/favicon.ico'):
            return self._send(403, b'authored fixture route guard', 'text/plain')
        return super().do_GET()

    def do_POST(self):
        emit({'request': 'POST', 'path': self.path})
        if spec['label'] != 'legacy' or self.path != '/api/run':
            return self._send(403, b'authored fixture action guard', 'text/plain')
        return super().do_POST()


server = ThreadingHTTPServer(('127.0.0.1', 0), Guarded)
emit({'ready': True, 'label': spec['label'], 'origin': 'http://127.0.0.1:' + str(server.server_port),
      'source': str(source), 'ui_sha256': hashlib.sha256(UI.read_bytes()).hexdigest(),
      'web_sha256': hashlib.sha256(Path(ptauth.web.__file__).read_bytes()).hexdigest()})
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
try:
    server.serve_forever(poll_interval=0.05)
finally:
    server.server_close()
