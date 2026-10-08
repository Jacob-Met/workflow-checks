"""Decode the lossless native receiving packet into a new directory."""
import argparse,base64,gzip,hashlib,json,pathlib
ap=argparse.ArgumentParser()
ap.add_argument('payload',type=pathlib.Path)
ap.add_argument('manifest',type=pathlib.Path)
ap.add_argument('output',type=pathlib.Path)
a=ap.parse_args()
digest=lambda b:hashlib.sha256(b).hexdigest()
manifest=json.loads(a.manifest.read_text())
encoded=a.payload.read_bytes()
assert digest(encoded)==manifest['encoded_sha256'],'Encoded payload changed'
compressed=base64.b64decode(b''.join(encoded.split()),validate=True)
assert digest(compressed)==manifest['gzip_sha256'],'Compressed payload changed'
raw=gzip.decompress(compressed)
assert digest(raw)==manifest['json_sha256'],'Raw container changed'
container=json.loads(raw)
assert container['schema']=='hamon.raw_file_container.v1'
assert len(container['files'])==manifest['file_count']
expected={x['path']:x for x in manifest['files']}
assert len(expected)==len(container['files'])
decoded=[]
for item in container['files']:
 name=pathlib.PurePosixPath(item['path'])
 assert not name.is_absolute() and '..' not in name.parts and str(name)==item['path']
 assert item['path'] in expected
 data=base64.b64decode(item['base64'],validate=True)
 meta=expected.pop(item['path'])
 assert len(data)==item['bytes']==meta['bytes']
 assert digest(data)==item['sha256']==meta['sha256']
 decoded.append((name,data))
assert not expected
a.output.mkdir(parents=True,exist_ok=False)
for name,data in decoded:
 target=a.output.joinpath(*name.parts)
 target.parent.mkdir(parents=True,exist_ok=True)
 target.write_bytes(data)
print(json.dumps({'status':'pass','files':len(decoded),'bytes':sum(len(v) for _,v in decoded),'json_sha256':manifest['json_sha256'],'output':str(a.output)},indent=2))
