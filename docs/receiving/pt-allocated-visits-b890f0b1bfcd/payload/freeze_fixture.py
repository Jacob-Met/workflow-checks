"""Independent fictional inputs and manual allocation expectations, before candidate code inspection."""
from __future__ import annotations
import csv, hashlib, json, os, subprocess, sys
from pathlib import Path
from datetime import date

root=Path('/dev/shm/hamon-b890f0b1bfcd-pt-receiving')
source=root/'source'
out=root/'fixture-freeze'
out.mkdir(exist_ok=False)
inputs=out/'inputs';inputs.mkdir()
pins={'pt_auth/ptauth/data.py':'19a2a1b79eff6d2753507eebf3bf78011ddaaa87','pt_auth/ptauth/engine.py':'39c97f35d61ff949b5c2381f0ad60d7af8d74226','pt_auth/ptauth/cli.py':'559c0a76effa2204041e9318e9869a6c7389f50d'}
for path,sha in pins.items():
    actual=subprocess.check_output(['git','hash-object',path],cwd=source,text=True).strip()
    baseline=subprocess.check_output(['git','rev-parse','8fe2c9270f487729af9e88f40894e1c4530f2c20:'+path],cwd=source,text=True).strip()
    assert actual==baseline==sha,(path,actual,baseline)
def write(name,header,rows):
    with (inputs/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f,lineterminator='\r\n');w.writerow(header);w.writerows(rows)
long_visit='P6-LONG-'+('R'*254)
long_auth='AUTH-'+('X'*194)
long_clinic='Clinic-'+('Z'*160)
markup_visit='<img src=x onerror="window.__allocatedInjected=1">-FICTION'
patients=[
['P1','Fictional Alex <b>literal</b>','Home HQ','PAY1'],
['P2','Fictional Cross Token','Home South','PAY1'],
['P3','Fictional Zoë & "Kim"','Home HTML','PAY2'],
['P4','Fictional Empty','Home Empty','PAY1'],
['P5','Fictional Pending','Home Pending','PAY1'],
['P6','Fictional Long','Home Long','PAY1']]
payers=[
['PAY1','Fictional Plan <script>window.__allocatedInjected=1</script> & "one"','Y',1,3,2,'','Y','Demo only'],
['PAY2','Fictional Plan Café','Y',1,3,2,'','N','Demo only']]
auths=[
['AUTH-REPEAT','P1','PAY1',5,'2026-10-01','2026-10-15','approved'],
['AUTH-REPEAT','P1','PAY1',5,'2026-10-16','2026-10-31','approved'],
['AUTH-AMEND','P2','PAY1',1,'2026-10-01','2026-10-31','approved'],
['AUTH-AMEND','P2','PAY1',4,'2026-10-01','2026-10-31','approved'],
['AUTH-MARKUP','P3','PAY2',3,'2026-10-01','2026-10-31','approved'],
['AUTH-NO-VISITS','P4','PAY1',4,'2026-10-01','2026-10-31','approved'],
['AUTH-PENDING','P5','PAY1',2,'2026-10-01','2026-10-31','pending'],
[long_auth,'P6','PAY1',3,'2026-10-01','2026-10-31','approved']]
visits=[
['DUP-1','P1','2026-10-02','Clinic OLD','Therapist A','PAY1','completed','treatment'],
['P1-EARLY','P1','2026-10-03','Clinic A.*B','Therapist A','PAY1','completed','treatment'],
['P1-NEXT','P1','2026-10-10','Clinic Z','Therapist A','PAY1','scheduled','treatment'],
['P1-LATE','P1','2026-10-20','Clinic A.*B','Therapist A','PAY1','scheduled','treatment'],
['P1-LATE-DONE','P1','2026-10-21','Clinic Z','Therapist A','PAY1','completed','treatment'],
['P2-DONE','P2','2026-10-04','Visit South','Therapist B','PAY1','completed','treatment'],
['P2-NEXT','P2','2026-10-12','Visit North','Therapist B','PAY1','scheduled','treatment'],
['P2-TWIN','P2','2026-10-12','Visit North','Therapist B','PAY1','scheduled','treatment'],
['P3-EVAL','P3','2026-10-04','Clinic HTML','Therapist C','PAY2','completed','eval'],
[markup_visit,'P3','2026-10-06','Clinic HTML','Therapist "C", café','PAY2','completed','treatment'],
['P3-NEXT','P3','2026-10-12','Clinic HTML','Therapist C','PAY2','scheduled','treatment'],
['CANCEL','P1','2026-10-10','Clinic Z','Therapist A','PAY1','cancelled','treatment'],
['NO-SHOW','P1','2026-10-10','Clinic Z','Therapist A','PAY1','no_show','treatment'],
['NO-AUTH','P5','2026-10-09','Clinic Unknown','Therapist D','PAY1','scheduled','treatment'],
[long_visit,'P6','2026-10-07',long_clinic,'Therapist Long','PAY1','completed','treatment'],
['P6-NEXT','P6','2026-10-18',long_clinic,'Therapist Long','PAY1','scheduled','treatment'],
['DUP-1','P1','2026-10-05','Clinic A.*B','Therapist A','PAY1','completed','treatment'],
['P1-OUTSIDE','P1','2026-11-03','Clinic Z','Therapist A','PAY1','scheduled','treatment'],
['P1-EXTRA','P1','2026-10-11','Clinic A.*B','Therapist A','PAY1','scheduled','treatment']]
write('patients.csv',['patient_id','display_name','clinic','primary_payer'],patients)
write('payers.csv',['payer_id','payer_name','requires_auth','reauth_visits_before','reauth_days_before','turnaround_days','annual_visit_limit','counts_evals','checklist'],payers)
write('authorizations.csv',['auth_no','patient_id','payer_id','visits_authorized','start_date','end_date','status'],auths)
write('schedule.csv',['visit_id','patient_id','visit_date','clinic','therapist','payer_id','status','visit_type'],visits)
manual=[
{'auth_no':'AUTH-REPEAT (2026-10-01..2026-10-15)','auth_row':'authorizations.csv:row2','used':['P1-EARLY','DUP-1'],'scheduled':['P1-NEXT','P1-EXTRA']},
{'auth_no':'AUTH-REPEAT (2026-10-16..2026-10-31)','auth_row':'authorizations.csv:row3','used':['P1-LATE-DONE'],'scheduled':['P1-LATE']},
{'auth_no':'AUTH-AMEND','auth_row':'authorizations.csv:row5','used':['P2-DONE'],'scheduled':['P2-NEXT','P2-TWIN']},
{'auth_no':'AUTH-MARKUP','auth_row':'authorizations.csv:row6','used':[markup_visit],'scheduled':['P3-NEXT']},
{'auth_no':'AUTH-NO-VISITS','auth_row':'authorizations.csv:row7','used':[],'scheduled':[]},
{'auth_no':long_auth,'auth_row':'authorizations.csv:row9','used':[long_visit],'scheduled':['P6-NEXT']}]
last={v[0]:(i+2,v) for i,v in enumerate(visits)}
expected=[]
for a in manual:
    for allocation in ['used','scheduled']:
        for vid in a[allocation]:
            row,v=last[vid]
            expected.append({'allocation':allocation,'auth_no':a['auth_no'],'auth_source_row':a['auth_row'],'visit_id':vid,'visit_date':v[2],'patient_id':v[1],'payer_id':v[5],'clinic':v[3],'visit_status':v[6],'visit_type':v[7],'visit_source_row':'schedule.csv:row'+str(row)})
assert len(expected)==13
sys.path.insert(0,str(source/'pt_auth'))
from ptauth.data import load_visits,load_auths,load_payers
from ptauth.engine import build_ledger
loaded=load_visits(inputs/'schedule.csv')
ledger,uncovered=build_ledger(loaded,load_auths(inputs/'authorizations.csv'),load_payers(inputs/'payers.csv'),date(2026,10,8))
actual=[]
for key,led in ledger.items():
    actual.append({'auth_no':key,'auth_row':led.auth.source_row,'used':[v.visit_id for v in led.used],'scheduled':[v.visit_id for v in led.scheduled]})
assert actual==manual,(actual,manual)
assert [v.visit_id for v in uncovered]==['NO-AUTH','P1-OUTSIDE']
record={'phase':'frozen before candidate projection/template read','source_pin':'055c863a9484adb1f6f39f54bf6cce90825bf0ad','unchanged_baseline_pin':'8fe2c9270f487729af9e88f40894e1c4530f2c20','baseline_module_pins':pins,'as_of':'2026-10-08','raw_visits':19,'allocated_visits':13,'used':6,'scheduled':7,'manual_ledger':manual,'expected_records':expected,'expected_uncovered_ids':['NO-AUTH','P1-OUTSIDE'],'explicit_exclusions':['old DUP-1 row2','P3-EVAL','CANCEL','NO-SHOW','NO-AUTH','P1-OUTSIDE'],'fixture_text':{'long_visit':long_visit,'long_auth':long_auth,'long_clinic':long_clinic,'markup_visit':markup_visit},'inputs':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(inputs.iterdir())},'baseline_engine_matches_manual':True,'receiver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
data=(json.dumps(record,indent=2,ensure_ascii=False)+'\n').encode()
sha=hashlib.sha256(data).hexdigest()
target=out/('expected-'+sha+'.json');target.write_bytes(data);target.chmod(0o444)
print(json.dumps({'status':'frozen','path':str(target),'sha256':sha,'records':len(expected),'raw_visits':len(visits),'source_module_pins_exact':True}),flush=True)
