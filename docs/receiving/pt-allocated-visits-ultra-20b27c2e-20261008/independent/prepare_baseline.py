"""Independent primary-baseline PT fixture and oracle; no candidate imports."""
from __future__ import annotations
import csv, hashlib, json, os, shutil, subprocess, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIELDS = ["auth_no","auth_patient_id","auth_payer_id","auth_start","auth_end",
          "auth_visits_authorized","auth_evidence","allocation","visit_id","visit_date",
          "status","visit_type","patient_id","patient_name","clinic","therapist",
          "payer_id","payer_name","visit_evidence","as_of","clinic_timezone"]
AS_OF, ZONE = "2026-10-08", "America/Los_Angeles"

def sha(b): return hashlib.sha256(b).hexdigest()
def blob(b): return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def snapshot(root):
    return {str(p.relative_to(root)):sha(p.read_bytes()) for p in sorted(root.rglob("*")) if p.is_file()}

primary=json.loads((ROOT/"primary-source.json").read_text())
assert primary["complete_blob_count"]==953 and not primary["truncated"] and not primary["instructions"]
baseline=ROOT/"baseline"
baseline.mkdir()
closure=[]
for e in primary["closure"]:
    src=Path(e["native_path"]); b=src.read_bytes()
    assert len(b)==e["bytes"] and sha(b)==e["sha256"] and blob(b)==e["git_blob"],e["repo_path"]
    dest=baseline/e["repo_path"];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
    closure.append({**e,"reviewer_path":str(dest)})
save(ROOT/"baseline-closure.json",{"primary_base":primary["base"],"tree":primary["tree"],"entries":closure})
contract=Path("/tmp/ultra-20b27c2e-root-pt-allocations/CONTRACT.md").read_bytes()
assert len(contract)==7238 and sha(contract)=="034a68919ba10a0bc7c206e1b3f2653c4c8196422120850b3ca0b8692f0fdd0d"
(ROOT/"ROOT-CONTRACT.md").write_bytes(contract)
save(ROOT/"public-contract.json",{
 "reviewer":"ultra-20b27c2e-20261008 / runtime_integration",
 "inherited_contract":"ROOT-CONTRACT.md","authority":"root-assigned independent receiver",
 "candidate_or_authored_tests_read":False,"csv_fields":FIELDS,"as_of":AS_OF,"clinic_timezone":ZONE,
 "search":"Case-insensitive literal substring within each of all 21 fields, never concatenated.",
 "ui":{"tab":'button[data-t="ledger"]',"status":"#alloc-status","auth":"#alloc-auth",
       "clinic":"#alloc-clinic","search":"#alloc-search","count":"#alloc-count",
       "rows":"#alloc-rows","export":"#alloc-export"},
 "native_scope":"Owned synthetic fixture, actual CLI, report renderer and web.make_handler.",
 "selection":"Option values remain opaque; exact membership groups are independently verified."})

fixture=ROOT/"fixture";fixture.mkdir()
patients=[]
def patient(i,name="Twin Name",clinic="Home fallback must not replace raw clinic",payer="RULE"):
    patients.append(dict(patient_id=i,display_name=name,clinic=clinic,primary_payer=payer))
for i in ["P-A","P-BOUND","P-DUP","P-AM","P-REUSE","P-SAME1","P-SAME2","P-EVAL","P-EXEMPT","P-PEND","P-DENY","P-BULK"]:
    patient(i)
patient("P-X",'Twin <img src=x onerror="window.__alloc_xss=17"> & Zöe',"Patient home clinic")
payers=[]
for i,name,req,evals in [("RULE","Rule payer","Y","Y"),("ALT","Alternate payer","Y","Y"),
                         ("NOEVAL","Evaluation-exempt rule","Y","N"),("NOAUTH","No-auth rule","N","Y")]:
    payers.append(dict(payer_id=i,payer_name=name,requires_auth=req,reauth_visits_before=0,
                       reauth_days_before=0,turnaround_days=2,annual_visit_limit=0,counts_evals=evals,
                       checklist="Synthetic source check|Confirm recorded period"))
auths=[];auth_labels=[]
def auth(label,num,pat,start,end,cap,payer="RULE",status="approved"):
    auth_labels.append(label)
    auths.append(dict(auth_no=num,patient_id=pat,payer_id=payer,visits_authorized=cap,
                      start_date=start,end_date=end,status=status))
auth("early","EARLY","P-A","2026-10-01","2026-10-08",2)
auth("late","LATE","P-A","2026-10-01","2026-10-31",3)
auth("boundary","ONE DAY","P-BOUND","2026-10-08","2026-10-08",3)
auth("duplicate","CORRECT","P-DUP","2026-10-01","2026-10-31",2)
auth("amend-old","AMENDED","P-AM","2026-09-01","2026-10-10",1)
auth("amend-new","AMENDED","P-AM","2026-10-01","2026-10-15",3)
auth("reuse-old","REUSED","P-REUSE","2026-09-01","2026-09-30",2)
auth("reuse-new","REUSED","P-REUSE","2026-10-01","2026-10-31",2)
auth("same-one","SHARED","P-SAME1","2026-10-01","2026-10-31",2)
auth("same-two","SHARED","P-SAME2","2026-10-01","2026-10-31",1)
auth("same-payer","SHARED","P-SAME1","2026-10-01","2026-10-31",1,"ALT")
auth("eval","EVAL RULE","P-EVAL","2026-10-01","2026-10-31",3,"NOEVAL")
auth("exempt","EXEMPT","P-EXEMPT","2026-10-01","2026-10-31",4,"NOAUTH")
auth("pending","PENDING","P-PEND","2026-10-01","2026-10-31",3,status="pending")
auth("denied","DENIED","P-DENY","2026-10-01","2026-10-31",3,status="denied")
auth("unknown","UNKNOWN RULES","P-UNKNOWN","2026-10-01","2026-10-31",3,"MISSING")
hostile_auth='AUTH <script>window.__alloc_xss=20</script>,\nÖ'
auth("hostile",hostile_auth,"P-X","2026-10-01","2026-10-31",3)
auth("bulk","BULK","P-BULK","2026-10-01","2026-10-31",40)
visits=[];visit_labels=[];manual={};excluded=[]
def visit(label,i,pat,day,status,expect=None,clinic="North",therapist="Synthetic therapist",
          payer="RULE",kind="treatment",settled_date=None):
    visit_labels.append(label)
    visits.append(dict(visit_id=i,patient_id=pat,visit_date=day,clinic=clinic,therapist=therapist,
                       payer_id=payer,status=status,visit_type=kind))
    if expect is not None:
        manual[i]={"allocation":expect[0],"auth_label":expect[1],"visit_label":label,
                   "visit_date":settled_date or day,"clinic":clinic}
    else: excluded.append(label)
visit("a-s0","A-S0"," p-a ","2026-10-01","scheduled",("scheduled","late"))
visit("a-c1","A-C1","P-A","2026-10-02","completed",("used","early"))
visit("a-c2","A-C2","P-A","2026-10-08","completed",("used","early"))
visit("a-future","A-CFUTURE","P-A","2026-10-30","completed",("used","late"))
visit("a-s1","A-S1","P-A","2026-10-08","scheduled",("scheduled","late"))
visit("a-over","A-OVER","P-A","2026-10-09","scheduled")
visit("a-out","A-OUT","P-A","2026-11-01","scheduled")
visit("a-cancel","A-CANCEL","P-A","2026-10-06","cancelled")
visit("a-no-show","A-NO-SHOW","P-A","2026-10-06","no_show")
visit("b-same","B-SAME-DAY","P-BOUND","2026-10-08","scheduled",("scheduled","boundary"),clinic="South")
visit("b-zone","B-OFFSET","P-BOUND","2026-10-09T00:30:00+00:00","completed",
      ("used","boundary"),clinic="South",settled_date="2026-10-08")
visit("b-before","B-BEFORE","P-BOUND","2026-10-07","completed")
visit("b-after","B-AFTER","P-BOUND","2026-10-09","scheduled")
visit("dup-old","Dup id","P-DUP","2026-10-01","completed",clinic="Wrong earlier clinic")
visit("dup-new","Dup id","P-DUP","2026-10-09","scheduled",("scheduled","duplicate"),
      clinic="",therapist='Dr "Q",\nSecond line')
visit("am-used","AM-USED","P-AM","2026-10-05","completed",("used","amend-new"),clinic="South")
visit("am-sched","AM-SCHED","P-AM","2026-10-14","scheduled",("scheduled","amend-new"),clinic="South")
visit("am-oldonly","AM-OLD-WINDOW","P-AM","2026-09-15","completed")
visit("r-old","R-OLD","P-REUSE","2026-09-30","completed",("used","reuse-old"),clinic="East")
visit("r-new","R-NEW","P-REUSE","2026-10-01","scheduled",("scheduled","reuse-new"),clinic="East")
visit("s-one","SHARED-ONE","P-SAME1","2026-10-03","completed",("used","same-one"),clinic="Same clinic")
visit("s-two","SHARED-TWO","P-SAME2","2026-10-03","scheduled",("scheduled","same-two"),clinic="Same clinic")
visit("s-payer","SHARED-ALT","P-SAME1","2026-10-03","completed",("used","same-payer"),clinic="Same clinic",payer="ALT")
visit("e-eval","EV-EXCLUDED","P-EVAL","2026-10-04","completed",payer="NOEVAL",kind="Initial Evaluation")
visit("e-reval","RE-EVAL-COUNTS","P-EVAL","2026-10-04","completed",("used","eval"),payer="NOEVAL",kind="Re-Evaluation")
visit("e-tx","E-TREATMENT","P-EVAL","2026-10-05","scheduled",("scheduled","eval"),payer="NOEVAL")
visit("e-cancel","EV-CANCELLED","P-EVAL","2026-10-05","cancelled",payer="NOEVAL")
visit("ex-c","EX-C","P-EXEMPT","2026-10-01","completed",payer="NOAUTH")
visit("ex-s","EX-S","P-EXEMPT","2026-10-10","scheduled",payer="NOAUTH")
visit("pending-c","PEND-C","P-PEND","2026-10-02","completed")
visit("pending-s","PEND-S","P-PEND","2026-10-11","scheduled")
visit("denied-s","DENY-S","P-DENY","2026-10-12","scheduled")
visit("unknown-c","UNKNOWN-C","P-UNKNOWN","2026-10-04","completed",("used","unknown"),payer="MISSING",clinic="")
visit("unknown-s","UNKNOWN-S","P-UNKNOWN","2026-10-09","scheduled",("scheduled","unknown"),payer="MISSING",clinic="")
hostile_visit='V,<img src=x onerror="window.__alloc_xss=19">\nΩ.*[x]'
visit("hostile",hostile_visit,"P-X","2026-10-07","scheduled",("scheduled","hostile"),
      clinic='West "A",\n第二诊所 [x]',therapist='<svg onload="window.__alloc_xss=18"> Kai.*[x]')
for n in range(32):
    day=f"2026-10-{2+n%26:02d}"
    status="completed" if n%2==0 else "scheduled"
    visit(f"bulk-{n}",f"BULK-{n:02d}","P-BULK",day,status,
          ("used" if status=="completed" else "scheduled","bulk"),clinic="Bulk clinic")

headers={
 "patients.csv":["patient_id","display_name","clinic","primary_payer"],
 "payers.csv":["payer_id","payer_name","requires_auth","reauth_visits_before","reauth_days_before",
               "turnaround_days","annual_visit_limit","counts_evals","checklist"],
 "authorizations.csv":["auth_no","patient_id","payer_id","visits_authorized","start_date","end_date","status"],
 "schedule.csv":["visit_id","patient_id","visit_date","clinic","therapist","payer_id","status","visit_type"]}
for filename,rows in [("patients.csv",patients),("payers.csv",payers),
                      ("authorizations.csv",auths),("schedule.csv",visits)]:
    with (fixture/filename).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=headers[filename],lineterminator="\r\n")
        w.writeheader()
        if filename in {"schedule.csv","authorizations.csv"}: f.write("\r\n")
        w.writerows(rows)
def refs(filename,labels):
    result={}
    with (fixture/filename).open(encoding="utf-8",newline="") as f:
        reader=csv.reader(f);next(reader);index=0
        for row in reader:
            if not row:continue
            result[labels[index]]=f"{filename}:row{reader.line_num}"
            index+=1
    assert index==len(labels)
    return result
auth_refs=refs("authorizations.csv",auth_labels)
visit_refs=refs("schedule.csv",visit_labels)
for v in manual.values():
    v["auth_evidence"]=auth_refs[v.pop("auth_label")]
    v["visit_evidence"]=visit_refs[v.pop("visit_label")]
save(ROOT/"fixture-authored.json",{"patients":patients,"payers":payers,"authorizations":auths,"visits":visits,
                                "auth_refs":auth_refs,"visit_refs":visit_refs,"manual_expected":manual,
                                "excluded_input_occurrences":excluded})
empty=ROOT/"empty-fixture";shutil.copytree(fixture,empty)
with (empty/"schedule.csv").open("w",encoding="utf-8",newline="") as f:
    csv.writer(f,lineterminator="\r\n").writerow(headers["schedule.csv"])
before={"source":snapshot(baseline),"fixture":snapshot(fixture),"empty_fixture":snapshot(empty)}
sys.path.insert(0,str(baseline/"pt_auth"))
from ptauth.data import load_visits,load_auths,load_payers,load_patients,resolve_clinic_timezone
from ptauth.engine import build_worklist
zone=resolve_clinic_timezone(ZONE)
native_visits=load_visits(fixture/"schedule.csv",clinic_tz=zone)
native_auths=load_auths(fixture/"authorizations.csv",clinic_tz=zone)
native_payers=load_payers(fixture/"payers.csv")
native_patients=load_patients(fixture/"patients.csv")
items,ledgers,uncovered=build_worklist(native_visits,native_auths,native_payers,native_patients,date.fromisoformat(AS_OF))
rows=[]
for ledger in ledgers.values():
    a=ledger.auth
    for allocation,members in (("used",ledger.used),("scheduled",ledger.scheduled)):
        for v in members:
            patient_value=native_patients.get(v.patient_id);payer_value=native_payers.get(v.payer_id)
            rows.append(dict(zip(FIELDS,[
                a.auth_no,a.patient_id,a.payer_id,a.start.isoformat(),a.end.isoformat(),a.visits_authorized,a.source_row,
                allocation,v.visit_id,v.visit_date.isoformat(),v.status,v.visit_type,v.patient_id,
                patient_value.display_name if patient_value else "",v.clinic,v.therapist,v.payer_id,
                payer_value.payer_name if payer_value else "",v.source_row,AS_OF,ZONE])))
assert len(rows)>=50 and len(rows)==len(manual),(len(rows),len(manual))
actual_by_id={r["visit_id"]:r for r in rows}
assert len(actual_by_id)==len(rows) and set(actual_by_id)==set(manual)
for vid,facts in manual.items():
    for key,value in facts.items():
        assert actual_by_id[vid][key]==value,(vid,key,actual_by_id[vid][key],value)
assert actual_by_id["B-OFFSET"]["visit_date"]=="2026-10-08"
assert actual_by_id["Dup id"]["status"]=="scheduled" and actual_by_id["Dup id"]["clinic"]==""
assert actual_by_id["AM-USED"]["auth_visits_authorized"]==3
assert actual_by_id["RE-EVAL-COUNTS"]["visit_type"]=="re-eval"
assert actual_by_id["UNKNOWN-C"]["patient_name"]==actual_by_id["UNKNOWN-C"]["payer_name"]==""
assert len({actual_by_id[x]["auth_no"] for x in ["SHARED-ONE","SHARED-TWO","SHARED-ALT"]})==3
assert {actual_by_id[x]["auth_no"] for x in ["R-OLD","R-NEW"]}=={
    "REUSED (2026-09-01..2026-09-30)","REUSED (2026-10-01..2026-10-31)"}
commands=[]
for name,data in [("baseline-reference",fixture),("baseline-empty-reference",empty)]:
    out=ROOT/name
    cmd=[sys.executable,"-m","ptauth","run","--data",str(data),"--out",str(out),
         "--as-of",AS_OF,"--clinic-timezone",ZONE]
    env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1","PYTHONPATH":str(baseline/"pt_auth")}
    result=subprocess.run(cmd,env=env,capture_output=True)
    (ROOT/(name+".stdout")).write_bytes(result.stdout);(ROOT/(name+".stderr")).write_bytes(result.stderr)
    commands.append({"argv":cmd,"exit_code":result.returncode,"stdout_sha256":sha(result.stdout),"stderr_sha256":sha(result.stderr)})
    assert result.returncode==0,(cmd,result.stderr.decode())
summary=json.loads((ROOT/"baseline-reference/summary.json").read_text())
assert "allocation_review" not in summary and not (ROOT/"baseline-reference/allocated_visits.csv").exists()
after={"source":snapshot(baseline),"fixture":snapshot(fixture),"empty_fixture":snapshot(empty)}
assert before==after
oracle={"fields":FIELDS,"as_of":AS_OF,"clinic_timezone":ZONE,"rows":rows,"manual_expected":manual,
        "loader_visits":len(native_visits),"loader_auths":len(native_auths),"ledger_count":len(ledgers),
        "ledger_memberships":len(rows),"unique_visit_ids":len(actual_by_id),"uncovered_visit_ids":[v.visit_id for v in uncovered],
        "auth_refs":auth_refs,"visit_refs":visit_refs,"hostile_visit_id":hostile_visit,
        "reference_counts":summary["counts"],"source_and_inputs":before}
save(ROOT/"oracle.json",oracle)
save(ROOT/"prepare-receipt.json",{"commands":commands,"manual_facts_checked":sum(len(x) for x in manual.values()),
    "allocated_rows":len(rows),"ledger_count":len(ledgers),"raw_visit_rows":len(native_visits),
    "input_source_unchanged":before==after,"source_pins":closure,"python":sys.version,
    "free_bytes":shutil.disk_usage(ROOT).free})
print(json.dumps({"prepared":True,"allocated_rows":len(rows),"manual_facts":sum(len(x) for x in manual.values()),
                  "raw_visits":len(native_visits),"auths":len(native_auths),"ledgers":len(ledgers),
                  "source_unchanged":before==after,"commands":commands}))
