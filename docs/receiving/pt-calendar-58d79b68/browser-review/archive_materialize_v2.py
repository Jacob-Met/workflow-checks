import pathlib,tarfile,json,hashlib,os
root=pathlib.Path('/Users/me/pt-calendar-browser-review-58d79b68c9e4')
(root/'receiver-archive-preflight-v1.json').write_text(json.dumps({'kind':'receiver_setup_correction','failed_before_extract':True,'error':"RuntimeError: unexpected archive member pt_auth type b'5'",'reason':'First validator refused ordinary directory entries. Revised validator accepts only directory prefixes of expected regular files; links and other types remain rejected.','candidate_failure':False},indent=2)+'\n')
manifest=json.loads((root/'candidate-source-freeze-v2.json').read_text())
expected={x['path']:x for x in manifest['pt_source_files']}
archive=root/'pt-runtime-v2.tar.gz'
with tarfile.open(archive,'r:gz') as tf:
 members=tf.getmembers()
 files={}
 for m in members:
  p=pathlib.PurePosixPath(m.name)
  if p.is_absolute() or '..' in p.parts:
   raise RuntimeError('unsafe archive member '+m.name)
  if m.isdir():
   if not any(name.startswith(m.name.rstrip('/')+'/') for name in expected):raise RuntimeError('unexpected directory '+m.name)
   continue
  if not m.isfile():
   raise RuntimeError('unexpected archive member '+m.name+' type '+str(m.type))
  if m.name in files or m.name not in expected:
   raise RuntimeError('unexpected/duplicate file '+m.name)
  data=tf.extractfile(m).read()
  e=expected[m.name]
  if len(data)!=e['bytes'] or hashlib.sha256(data).hexdigest()!=e['sha256']:
   raise RuntimeError('archive byte mismatch '+m.name)
  blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
  if blob!=e['git_blob'] or ('100755' if m.mode & 0o111 else '100644')!=e['mode']:
   raise RuntimeError('archive blob/mode mismatch '+m.name)
  files[m.name]=(data,0o755 if e['mode']=='100755' else 0o644)
 if set(files)!=set(expected): raise RuntimeError('missing files')
 out=root/'candidate'
 out.mkdir()
 for name,(data,mode) in files.items():
  p=out/name
  p.parent.mkdir(parents=True,exist_ok=True)
  with p.open('xb') as f:f.write(data)
  p.chmod(mode)
 for name,e in expected.items():
  p=out/name
  if hashlib.sha256(p.read_bytes()).hexdigest()!=e['sha256']:raise RuntimeError('readback mismatch')
 receipt={'ok':True,'commit':manifest['commit'],'tree':manifest['tree'],'files':len(files),'bytes':sum(len(v[0]) for v in files.values()),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'all_file_hashes_blobs_modes_verified':True,'source_test_bodies_not_read_as_oracle':True,'free_bytes':os.statvfs(root).f_bavail*os.statvfs(root).f_frsize}
 (root/'candidate-materialization-v2.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt))
