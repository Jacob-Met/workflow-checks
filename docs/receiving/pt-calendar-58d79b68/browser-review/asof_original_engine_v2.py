import sys,json,hashlib,pathlib
from datetime import date
root=pathlib.Path('/Users/me/pt-calendar-browser-review-58d79b68c9e4')
source=root/'baseline/pt_auth'
sys.path.insert(0,str(source))
from ptauth.report import run
engine=source/'ptauth/engine.py'
assert hashlib.sha256(engine.read_bytes()).hexdigest()=='bfa7049e9b133d654ce947b135c17ac401bd7b1fcd76350bdb10de5b7a1ad1f7'
data=root/'fixture-template/data'
before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in data.iterdir() if p.is_file()}
states=json.loads((root/'fixture-template/out/work_state.json').read_text())
out=root/'asof-original-engine-v2'
out.mkdir()
runs=[]
for label,day,count in [('after_all_appointments',date(2026,11,2),0),('before_appointments',date(2026,10,30),7)]:
 target=out/label
 run(data,target,day,run_by='independent_browser_oracle_correction',clinic_timezone='America/Los_Angeles')
 report=json.loads((target/'summary.json').read_text())
 assert len(report['worklist'])==count
 eligible=[{'key':r['key'],'submit_by':r['submit_by']} for r in report['worklist'] if r['submit_by'] is not None and states.get(r['key'],{}).get('state','open') in ('open','submitted')]
 runs.append({'case':label,'as_of':report['as_of'],'worklist_count':len(report['worklist']),'eligible':eligible,'summary_sha256':hashlib.sha256((target/'summary.json').read_bytes()).hexdigest()})
after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in data.iterdir() if p.is_file()}
assert before==after
assert len(runs[0]['eligible'])==0 and len(runs[1]['eligible'])==3
r={'schema':'pt_calendar.independent_asof_oracle.v2','baseline_commit':'9e931fa9f42033bf2368f7149684fb5631345715','engine_sha256':hashlib.sha256(engine.read_bytes()).hexdigest(),'method':'Unchanged original engine, independent CSVs and frozen existing staff states; no candidate formatter/tests','v1_failure':'Receiver incorrectly required export to be enabled after November 2 although every fixture appointment is November 1. Original native15/16 run and failure-7.png remain unchanged.','runs':runs,'source_csv_preserved':before==after,'input_sha256':before}
(root/'asof-original-engine-v2.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r))
