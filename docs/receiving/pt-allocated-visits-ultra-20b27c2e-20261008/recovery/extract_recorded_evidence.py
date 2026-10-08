#!/usr/bin/env python3
"""Restore exact synthetic receiving evidence; no dependencies."""
from pathlib import Path, PurePosixPath
import argparse, base64, hashlib, json, zlib
p=argparse.ArgumentParser()
p.add_argument("--bundle",type=Path,default=Path(__file__).with_name("recorded-evidence.json"))
p.add_argument("--out",type=Path,required=True)
a=p.parse_args()
bundle=json.loads(a.bundle.read_text(encoding="utf-8"))
root=a.out.resolve(); root.mkdir(parents=True,exist_ok=True)
restored=0
for rel,info in sorted(bundle["files"].items()):
    name=PurePosixPath(rel)
    if name.is_absolute() or not name.parts or any(v in ("",".","..") for v in name.parts):
        raise ValueError("Unsafe evidence path: "+rel)
    target=root.joinpath(*name.parts)
    if not target.resolve().is_relative_to(root):
        raise ValueError("Evidence destination escapes root: "+rel)
    encoded=bundle["blobs"][info["sha256"]]
    raw=zlib.decompress(base64.b64decode(encoded["data"],validate=True))
    if len(raw)!=info["bytes"] or hashlib.sha256(raw).hexdigest()!=info["sha256"]:
        raise ValueError("Evidence digest mismatch: "+rel)
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        if target.is_symlink() or target.read_bytes()!=raw:
            raise FileExistsError("Refusing to replace different existing file: "+str(target))
    else:
        with target.open("xb") as f: f.write(raw)
    restored+=1
print(json.dumps({"restored_files":restored,"out":str(root)}))
