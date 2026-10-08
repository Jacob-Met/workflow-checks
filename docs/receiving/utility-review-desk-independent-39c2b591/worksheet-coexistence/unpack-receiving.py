import base64,gzip,hashlib,json,pathlib,sys
here=pathlib.Path(__file__).parent
manifest=json.loads((here/"RAW_EVIDENCE_MANIFEST.json").read_text())
encoded=(here/"RAW_EVIDENCE.json.gz.b64").read_bytes()
sha=lambda b:hashlib.sha256(b).hexdigest()
assert len(encoded)==manifest["base64"]["bytes"] and sha(encoded)==manifest["base64"]["sha256"]
compressed=base64.b64decode(encoded,validate=True)
assert len(compressed)==manifest["gzip"]["bytes"] and sha(compressed)==manifest["gzip"]["sha256"]
raw=gzip.decompress(compressed)
assert len(raw)==manifest["container"]["bytes"] and sha(raw)==manifest["container"]["sha256"]
payload=json.loads(raw)
dest=pathlib.Path(sys.argv[1]);dest.mkdir(parents=True,exist_ok=False)
assert len(payload["files"])==manifest["file_count"]
for e in payload["files"]:
 p=pathlib.PurePosixPath(e["path"])
 assert not p.is_absolute() and ".." not in p.parts
 b=base64.b64decode(e["base64"],validate=True)
 assert len(b)==e["bytes"] and sha(b)==e["sha256"]
 target=dest/pathlib.Path(*p.parts);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b)
print(json.dumps({"verified_files":len(payload["files"]),"raw_bytes":sum(e["bytes"] for e in payload["files"]),"container_sha256":sha(raw)}))
