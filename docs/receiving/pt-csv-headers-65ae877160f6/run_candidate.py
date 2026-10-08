from pathlib import Path
import json,subprocess,os,sys,datetime,hashlib
root=Path(__file__).parent; source=root/'candidate'; output=root/'author-candidate'
output.mkdir(exist_ok=False)
command=[sys.executable,'-B','-m','pytest','-q','-rs']
r=subprocess.run(command,cwd=source/'pt_auth',capture_output=True,text=True,timeout=180,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
(output/'stdout.txt').write_text(r.stdout);(output/'stderr.txt').write_text(r.stderr)
meta=json.loads((root/'baseline-source.json').read_text())
preserved=[]
for f in meta['materialized']:
 if f['path']=='pt_auth/ptauth/data.py':continue
 b=(source/f['path']).read_bytes();h=hashlib.sha1(b'blob '+str(len(b)).encode()+bytes([0])+b).hexdigest()
 assert h==f['sha'],f['path'];preserved.append(f['path'])
receipt={'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':command,'cwd':str(source/'pt_auth'),'exit_code':r.returncode,'python':sys.version,'stdout_sha256':hashlib.sha256(r.stdout.encode()).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr.encode()).hexdigest(),'data_sha256':hashlib.sha256((source/'pt_auth/ptauth/data.py').read_bytes()).hexdigest(),'test_sha256':hashlib.sha256((source/'pt_auth/tests/test_csv_headers.py').read_bytes()).hexdigest(),'preserved_original_inputs':preserved}
(output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt),r.stdout,r.stderr,flush=True)
