from pathlib import Path
import json,subprocess,hashlib,os
root=Path('/home/jacob/workflow-pt-csv-65ae877160f6');baseline=root/'baseline'
meta=json.loads((root/'source-manifest-input.json').read_text())
if not baseline.exists():
 baseline.mkdir()
 for f in meta['materialized']:
  b=subprocess.check_output(['git','-C','/home/jacob/workflow-checks-pt-calendar-source-58d79b68','cat-file','blob',f['sha']])
  assert hashlib.sha1(b'blob '+str(len(b)).encode()+bytes([0])+b).hexdigest()==f['sha']
  p=baseline/f['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);p.chmod(int(f['mode'][-3:],8))
 subprocess.run(['git','init','-b','capture/pt-csv-65ae877160f6',str(baseline)],check=True,capture_output=True)
 subprocess.run(['git','-C',str(baseline),'add','.'],check=True)
 subprocess.run(['git','-C',str(baseline),'-c','user.name=HAMON estate source capture','-c','user.email=150724801+Jacob-Met@users.noreply.github.com','commit','-m','Capture exact canonical PT executable and fixture closure for CSV admission receiving'],check=True,capture_output=True)
 meta['native_capture_commit']=subprocess.check_output(['git','-C',str(baseline),'rev-parse','HEAD'],text=True).strip()
 (root/'baseline-source.json').write_text(json.dumps(meta,indent=2)+'\n')
else: meta=json.loads((root/'baseline-source.json').read_text())
for f in meta['materialized']:
 b=(baseline/f['path']).read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+bytes([0])+b).hexdigest()==f['sha']
print(json.dumps({'source':str(baseline),'capture':meta['native_capture_commit'],'data_sha256':hashlib.sha256((baseline/'pt_auth/ptauth/data.py').read_bytes()).hexdigest(),'files':len(meta['materialized']),'bytes':sum(x['size'] for x in meta['materialized'])}),flush=True)
