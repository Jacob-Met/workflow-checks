from pathlib import Path
import json,subprocess,os,sys,datetime,hashlib
root=Path(__file__).parent
output=root/'author-baseline'
output.mkdir(exist_ok=False)
runs=[]
commands=[
 ('inherited',[sys.executable,'-B','-m','pytest','-q'],root/'baseline/pt_auth'),
 ('new-headers',[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_csv_headers.py','-v'],root/'candidate/pt_auth'),
]
for name,command,cwd in commands:
 r=subprocess.run(command,cwd=cwd,capture_output=True,text=True,timeout=180,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
 (output/(name+'.stdout.txt')).write_text(r.stdout)
 (output/(name+'.stderr.txt')).write_text(r.stderr)
 runs.append({'name':name,'command':command,'cwd':str(cwd),'exit_code':r.returncode,'stdout_sha256':hashlib.sha256(r.stdout.encode()).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr.encode()).hexdigest()})
 print(name,r.returncode,r.stdout[-1000:],r.stderr[-1000:],flush=True)
receipt={'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runs':runs,'python':sys.version,'production_unchanged':(root/'baseline/pt_auth/ptauth/data.py').read_bytes()==(root/'candidate/pt_auth/ptauth/data.py').read_bytes(),'test_sha256':hashlib.sha256((root/'candidate/pt_auth/tests/test_csv_headers.py').read_bytes()).hexdigest()}
(output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
