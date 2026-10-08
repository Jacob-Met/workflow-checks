"""Before/after public route witness; uses only generated, owned synthetic loads."""
from __future__ import annotations
import hashlib, io, json, sys, threading, urllib.request, urllib.error, zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path
root, output = map(Path, sys.argv[1:3])
sys.path.insert(0, str(root / "freight_packets"))
from freightpkt.synth import generate
from freightpkt.pipeline import run
from freightpkt.web import App, make_handler
output.mkdir(parents=True, exist_ok=False)
data, out = output / "data", output / "out"
generate(data, n_loads=8, seed=7)
run(data, out, run_by="batch-before-fixture")
app = App(data, out)
summary = app.summary()
chosen = [p["load_id"] for p in summary["packets"][:3]]
if len(chosen) != 3:
    raise RuntimeError("fixture must expose three generated packets")
app.decide({"load_id":chosen[0], "decision":"adjust", "note":"OPENCLI-E2E- synthetic freight note A",
            "evidence_version":summary["evidence_versions"][chosen[0]]})
app.decide({"load_id":chosen[1], "decision":"approve", "note":"Synthetic local fixture only: retained review B",
            "evidence_version":summary["evidence_versions"][chosen[1]]})
summary = app.summary()
items = [{"load_id":lid, "evidence_version":summary["evidence_versions"][lid],
          "review_version":summary["review_versions"][lid]} for lid in chosen]
def hashes():
    return {str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest()
            for base in (data,out) for p in sorted(base.rglob("*")) if p.is_file()}
before = hashes()
server = ThreadingHTTPServer(("127.0.0.1",0), make_handler(app))
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
origin = f"http://127.0.0.1:{server.server_port}"
def request(path, body=None):
    req = urllib.request.Request(origin+path, data=None if body is None else json.dumps(body).encode(),
                                 headers={} if body is None else {"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()
try:
    from urllib.parse import urlencode
    ordinary = []
    (output/"downloads").mkdir()
    for pos, item in enumerate(items,1):
        status, headers, body = request("/api/review-bundle?"+urlencode(item))
        if status != 200 or headers.get("Content-Type") != "application/zip":
            raise RuntimeError("inherited single-load control failed")
        (output/"downloads"/f"single-{pos}.zip").write_bytes(body)
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            review = json.loads(z.read("review.json"))
            ordinary.append({"load_id":item["load_id"],"bytes":len(body),
                             "sha256":hashlib.sha256(body).hexdigest(),"members":z.namelist(),
                             "review_state":None if review["review"] is None else review["review"]["review_state"]})
    status, headers, batch = request("/api/review-batch", {"loads":items})
    (output/"batch-response.bin").write_bytes(batch)
    checks={"three_existing_single_load_bundles":len(ordinary)==3,
            "existing_inputs_outputs_unchanged":hashes()==before,
            "batch_endpoint_returns_zip":status==200 and headers.get("Content-Type")=="application/zip"}
    members=[]
    if checks["batch_endpoint_returns_zip"]:
        with zipfile.ZipFile(io.BytesIO(batch)) as z:
            members=z.namelist()
            manifest=json.loads(z.read("manifest.json"))
            checks["chosen_loads_in_requested_order"]=[row["load_id"] for row in manifest["loads"]]==chosen
            checks["readable_batch_cover"]="index.html" in members
    else:
        checks["chosen_loads_in_requested_order"]=False
        checks["readable_batch_cover"]=False
    receipt={"schema":"freight-batch-native-probe.v1","python":sys.version,"source_root":str(root),
             "base_commit":"5b12dcd4c3a2c09d6602b2313e2bb556ac5997f7",
             "fixture":{"loads":8,"seed":7,"selected":items},"single_load_controls":ordinary,
             "batch":{"status":status,"content_type":headers.get("Content-Type"),"bytes":len(batch),
                      "sha256":hashlib.sha256(batch).hexdigest(),"members":members,
                      "non_zip_body":None if status==200 else batch.decode("utf-8",errors="replace")},
             "checks":checks,"source_io_before":before,"source_io_after":hashes()}
    (output/"receipt.json").write_text(json.dumps(receipt,indent=2,ensure_ascii=True)+"\n",encoding="utf-8")
    print(json.dumps({"checks":checks,"batch_status":status,"single_loads":chosen,"receipt":str(output/"receipt.json")}))
    sys.exit(0 if all(checks.values()) else 1)
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
