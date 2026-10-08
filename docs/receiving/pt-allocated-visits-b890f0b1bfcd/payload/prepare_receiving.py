from __future__ import annotations
from pathlib import Path
import csv,hashlib,json,os,subprocess,sys,time
root=Path('/dev/shm/hamon-b890f0b1bfcd-pt-receiving')
source=root/'source'; baseline=root/'baseline'
evidence=root/'receiving-v1';evidence.mkdir(exist_ok=False)
receipt={'started_at':time.time(),'source_head':'055c863a9484adb1f6f39f54bf6cce90825bf0ad','commands':[]}
def save(): (evidence/'native-preparation.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n')
def command(args,cwd,env=None):
    r=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,timeout=50)
    receipt['commands'].append({'args':args,'cwd':str(cwd),'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr});save()
    assert r.returncode==0,(args,r.returncode,r.stderr)
    return r
command(['git','worktree','add','--detach',str(baseline),'8fe2c9270f487729af9e88f40894e1c4530f2c20'],source)
expect_path=root/'fixture-freeze/expected-da5f0b3dcfcc3b2d80bcbf84a3edaa17e917ef4a6e4864f80506332bee9ca53b.json'
raw=expect_path.read_bytes();assert hashlib.sha256(raw).hexdigest()=='da5f0b3dcfcc3b2d80bcbf84a3edaa17e917ef4a6e4864f80506332bee9ca53b'
expected=json.loads(raw); inputs=root/'fixture-freeze/inputs'
empty_inputs=evidence/'empty-inputs';empty_inputs.mkdir()
for p in inputs.iterdir():
    if p.name=='schedule.csv': content=p.read_bytes().splitlines(keepends=True)[0]
    else: content=p.read_bytes()
    (empty_inputs/p.name).write_bytes(content)
outputs={}
for name,repo,data in [('normal',source,inputs),('legacy',baseline,inputs),('empty',source,empty_inputs)]:
    out=evidence/(name+'-out')
    env={**os.environ,'PYTHONPATH':str(repo/'pt_auth'),'PYTHONDONTWRITEBYTECODE':'1'}
    command([sys.executable,'-m','ptauth','run','--data',str(data),'--out',str(out),'--as-of','2026-10-08','--clinic-timezone','UTC'],repo,env)
    outputs[name]=str(out)
    summary=json.loads((out/'summary.json').read_text())
    if summary.get('worklist'):
        w=summary['worklist'][0];key=w.get('key') or '|'.join([w['patient_id'],w['payer_id'],w.get('auth_no') or ''])
        (out/'work_state.json').write_text(json.dumps({key:{'state':'submitted','note':'Retain this fictional staff note','at':'2026-10-08T12:00:00+00:00'}},indent=2)+'\n')
normal=json.loads((Path(outputs['normal'])/'summary.json').read_text())
legacy=json.loads((Path(outputs['legacy'])/'summary.json').read_text())
empty=json.loads((Path(outputs['empty'])/'summary.json').read_text())
assert 'allocation_review' not in legacy
assert empty['allocation_review']==[]
rows=normal['allocation_review'];assert len(rows)==13
mapping={'auth_evidence':'auth_source_row','status':'visit_status','visit_evidence':'visit_source_row'}
facts=[]
for actual,gold in zip(rows,expected['expected_records'],strict=True):
    for k,v in gold.items():
        actual_k={v:k for k,v in mapping.items()}.get(k,k)
        assert actual[actual_k]==v,(actual_k,actual[actual_k],v)
    assert actual['as_of']=='2026-10-08' and actual['clinic_timezone']=='UTC'
    facts.append({'visit_id':actual['visit_id'],'auth_no':actual['auth_no'],'allocation':actual['allocation'],'visit_evidence':actual['visit_evidence'],'auth_evidence':actual['auth_evidence']})
for x in expected['inputs']:
    p=inputs/x
    assert hashlib.sha256(p.read_bytes()).hexdigest()==expected['inputs'][x]['sha256']
def hash_files(paths):
    return {str(p):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(paths) if p.is_file()}
watched=list(inputs.iterdir())+list(empty_inputs.iterdir())
for directory in outputs.values():watched+=list(Path(directory).iterdir())
watched+=list((source/'pt_auth/ptauth').glob('*'))+list((baseline/'pt_auth/ptauth').glob('*'))
snapshot=hash_files(watched)
(evidence/'watched-before.json').write_text(json.dumps(snapshot,indent=2)+'\n')
(evidence/'ports.json').write_text('{}\n')
config={'root':str(root),'source':str(source),'evidence':str(evidence),'inputs':str(inputs),'empty_inputs':str(empty_inputs),'outputs':outputs,'expect_path':str(expect_path),'native_summary_sha256':hashlib.sha256((Path(outputs['normal'])/'summary.json').read_bytes()).hexdigest()}
(evidence/'config.json').write_text(json.dumps(config,indent=2)+'\n')
receipt.update({'status':'pass','three_actual_cli_processes':True,'manual_records_matched':13,'manual_fact_fields_matched':143,'legacy_detail_unavailable':True,'valid_empty_projection':True,'original_fixture_inputs_unchanged':True,'allocated_facts':facts,'outputs':outputs,'watched_files':len(snapshot),'completed_at':time.time()});save()
print(json.dumps({'status':'pass','manual_records':13,'cli_processes':3,'watched_files':len(snapshot),'receipt':str(evidence/'native-preparation.json'),'sha256':hashlib.sha256((evidence/'native-preparation.json').read_bytes()).hexdigest()}),flush=True)
