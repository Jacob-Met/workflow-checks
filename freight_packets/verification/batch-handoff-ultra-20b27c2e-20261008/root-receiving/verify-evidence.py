import base64, hashlib, io, json, sys, zipfile, zlib
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
PINS = [
  {
    "path": "/private/tmp/ultra-20b27c2e-memory-freight-batch/publication/runs.zip",
    "bytes": 1543908,
    "sha256": "60c2425eb74dde1b7bd3d51f3ceed3a6cd9e6b61cfee788edb74968c041f6129",
    "git_blob": "ac2ead10077f827d884633bcba397714616769fb"
  },
  {
    "path": "/private/tmp/ultra-20b27c2e-memory-freight-batch/publication/runs-manifest.json",
    "bytes": 83045,
    "sha256": "067f8817a7997a78a761228522586191edc8f5ead8d9a5b48545e4fbd8f48f28",
    "git_blob": "3261a53800bad82e1368875fc03855d2b8ada9fa"
  },
  {
    "path": "/tmp/ultra-20b27c2e-runtime-freight-review/packet/recorded-artifacts.json",
    "bytes": 361839,
    "sha256": "e814e138cb2ffcc57e58f27420594de4d38db3ee41b9669a562f53e3616ad57d",
    "git_blob": "47532cc06abc856e503e7a1adcbb6595838d8cea"
  },
  {
    "path": "/tmp/ultra-20b27c2e-runtime-freight-review/packet/recorded-browser.json",
    "bytes": 69934,
    "sha256": "4c52e6c777feb7fbab9d004a9ead9987acff646d3a508e6375b73d119a6640cb",
    "git_blob": "df48e4795886dd7e0d2292ef522f1ebcd00c2d74"
  },
  {
    "path": "/tmp/ultra-20b27c2e-runtime-freight-review/packet/recorded-fixture.json",
    "bytes": 73208,
    "sha256": "9f87acbebe34c875dc38cc35b5ee85493eca0b1c055b0b67d7ec398ecc58c75b",
    "git_blob": "c9303313535f5f20a236c49e7c3275e295517198"
  },
  {
    "path": "/tmp/ultra-20b27c2e-runtime-freight-review/packet/recorded-native.json",
    "bytes": 141748,
    "sha256": "5d863f832688548a221ed7bbb6fd0afc6a0a4b000dab20e960f3a9ca583dd0e2",
    "git_blob": "a133fff17c74462600c4a0b7439863da00293f9f"
  }
]
def h(raw):
    return {"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"git_blob":hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()}
def safe(name):
    p=PurePosixPath(name)
    if not name or p.is_absolute() or ".." in p.parts or "\\" in name:
        raise ValueError("unsafe evidence member")
raws={}
for pin in PINS:
    raw=Path(pin["path"]).read_bytes()
    if h(raw)!={k:pin[k] for k in ("bytes","sha256","git_blob")}:
        raise ValueError("outer evidence changed: "+pin["path"])
    raws[Path(pin["path"]).name]=raw
manifest=json.loads(raws["runs-manifest.json"])
members=manifest["members"]
if len(members)!=340 or len({r["path"] for r in members})!=340:
    raise ValueError("author cardinality")
total=0
with zipfile.ZipFile(io.BytesIO(raws["runs.zip"])) as archive:
    if set(archive.namelist())!={r["path"] for r in members} or len(archive.namelist())!=340:
        raise ValueError("author ZIP members")
    for row in members:
        safe(row["path"])
        data=archive.read(row["path"])
        if h(data)!={"bytes":row["bytes"],"sha256":row["sha256"],"git_blob":row["git_blob_sha"]}:
            raise ValueError("author member mismatch: "+row["path"])
        total+=len(data)
if total!=manifest["original_bytes"]:
    raise ValueError("author byte total")
bundles=[]
for name in ("recorded-fixture.json","recorded-native.json","recorded-browser.json","recorded-artifacts.json"):
    bundle=json.loads(raws[name])
    if bundle["schema"]!="freight-independent-files.v1": raise ValueError("schema")
    seen=set(); nbytes=0
    for row in bundle["files"]:
        safe(row["path"])
        if row["path"] in seen: raise ValueError("duplicate recorded member")
        seen.add(row["path"])
        n=row["bytes"]
        if type(n) is not int or not 0<=n<=8*1024*1024: raise ValueError("unbounded member")
        blob=bundle["blobs"][row["sha256"]]
        if blob["encoding"]!="zlib-base64": raise ValueError("encoding")
        decoder=zlib.decompressobj()
        data=decoder.decompress(base64.b64decode(blob["data"],validate=True),n+1)
        if decoder.unconsumed_tail or decoder.unused_data or not decoder.eof: raise ValueError("compressed boundary")
        if len(data)!=n or hashlib.sha256(data).hexdigest()!=row["sha256"]: raise ValueError("recorded member bytes")
        nbytes+=n
    bundles.append({"path":name,"files":len(seen),"bytes":nbytes})
receipt={"schema":"freight-batch-root-evidence-receiving.v1","recorded_at_utc":datetime.now(timezone.utc).isoformat(),"device":"0e3d582f-e25b-44b2-8418-9639fc4e4e33","python":sys.version,"outer_files":PINS,"author_archive":{"files":len(members),"bytes":total},"independent_bundles":bundles,"independent_files":sum(x["files"] for x in bundles),"independent_bytes":sum(x["bytes"] for x in bundles),"wrote_files":False,"executed_product_or_recorded_code":False}
print(json.dumps(receipt,ensure_ascii=False,sort_keys=True))
