import pathlib,json,hashlib,tarfile,io,base64,sys,stat
p=pathlib.Path(sys.argv[1]).resolve();out=pathlib.Path(sys.argv[2]).resolve();out.mkdir()
files=[p/n for n in ['identity.json','admission.json','PROTOCOL.md','expected.json','receive_ui.js','run_course.py','actual-drive.zip']]
course=p/'received-course';files += [f for f in course.iterdir() if f.is_file()]
files += sorted((course/'extracted').rglob('*'));files += sorted((course/'new-report').rglob('*'))
files=sorted(set(f for f in files if f.is_file()),key=lambda f:str(f.relative_to(p)))
assert len(files)<100

def meta(f):
 s=f.lstat();assert stat.S_ISREG(s.st_mode);b=f.read_bytes();return dict(path=str(f.relative_to(p)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),git_blob=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),mtime_ns=str(s.st_mtime_ns))
before=[meta(f) for f in files];assert sum(r['bytes'] for r in before)<16777216
manifest=dict(schema='pt.ui.native-export/1',source=str(p),files=before)
raw=(json.dumps(manifest,indent=2)+'\n').encode();(out/'native-manifest.json').write_bytes(raw)
with tarfile.open(out/'native.tar.gz','w:gz') as tf:
 for f,r in zip(files,before):
  b=f.read_bytes();t=tarfile.TarInfo(r['path']);t.size=len(b);t.mode=0o644;t.mtime=0;tf.addfile(t,io.BytesIO(b))
 t=tarfile.TarInfo('native-manifest.json');t.size=len(raw);t.mode=0o644;t.mtime=0;tf.addfile(t,io.BytesIO(raw))
after=[meta(f) for f in files];assert before==after
b=(out/'native.tar.gz').read_bytes();encoded=base64.b64encode(b).decode();parts=[]
for i in range(0,len(encoded),100000):
 n='part-'+str(i//100000)+'.b64';(out/n).write_text(encoded[i:i+100000]);parts.append(n)
r=dict(files=len(files),bytes=sum(x['bytes'] for x in before),custody_exact=True,tar_bytes=len(b),tar_sha256=hashlib.sha256(b).hexdigest(),parts=parts)
(out/'export.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
