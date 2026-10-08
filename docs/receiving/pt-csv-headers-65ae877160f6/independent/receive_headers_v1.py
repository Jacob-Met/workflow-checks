"""Frozen receiving of PT CSV-header admission through the actual report command."""
from __future__ import annotations
import argparse,csv,hashlib,io,json,os,re,shutil,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
p=argparse.ArgumentParser()
p.add_argument("--source",type=Path,required=True)
p.add_argument("--label",required=True)
p.add_argument("--data-sha",required=True)
p.add_argument("--reference",type=Path)
a=p.parse_args()
assert re.fullmatch("[a-z0-9-]+",a.label)
root=Path(__file__).resolve().parent
run=root/a.label
run.mkdir(exist_ok=False)
digest=lambda b:hashlib.sha256(b).hexdigest()
original=a.source/"ptauth"
source=run/"source"
package=source/"ptauth"
manifest={}
for item in sorted(original.rglob("*")):
    if not item.is_file() or "__pycache__" in item.parts: continue
    relative=item.relative_to(original)
    raw=item.read_bytes()
    dest=package/relative
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("xb") as stream:stream.write(raw)
    manifest[relative.as_posix()]=digest(raw)
assert manifest["data.py"]==a.data_sha
reference=json.loads(a.reference.read_text()) if a.reference else None
if reference:
    assert set(manifest)==set(reference["source_files"])
    assert all(v==reference["source_files"][n] for n,v in manifest.items() if n!="data.py")
sys.path.insert(0,str(source))
from ptauth import data as api
assert Path(api.__file__).resolve()==(package/"data.py").resolve()
headers={
 "schedule.csv":["visit_id","patient_id","visit_date","clinic","therapist","payer_id","status","visit_type"],
 "authorizations.csv":["auth_no","patient_id","payer_id","visits_authorized","start_date","end_date","status"],
 "payers.csv":["payer_id","payer_name","requires_auth","reauth_visits_before","reauth_days_before","turnaround_days","annual_visit_limit","counts_evals","checklist"],
 "patients.csv":["patient_id","display_name","clinic","primary_payer"],
}
values={
 "schedule.csv":["V1","P1","2026-09-28","Receiver Clinic","T1","PAY1","scheduled","treatment"],
 "authorizations.csv":["A1","P1","PAY1","8","2026-09-01","2026-10-31","approved"],
 "payers.csv":["PAY1","Receiver Plan","yes","2","7","3","","yes","form|dates"],
 "patients.csv":["P1","Receiver Synthetic","Receiver Clinic","PAY1"],
}
groups=[];cases=[]
def snapshot(directory):
 return {x.relative_to(directory).as_posix():digest(x.read_bytes()) for x in sorted(directory.rglob("*")) if x.is_file()}
def require(c,message):
 if not c:raise AssertionError(message)
def run_case(name, *, bad_file=None, duplicate=None, value=None, first=None, header_line=1,
             header_only=False, quirks=False, empty=False):
 case=run/"cases"/name
 inputs=case/"inputs";out=case/"reports"
 inputs.mkdir(parents=True);out.mkdir()
 for filename in headers:
  hs=list(headers[filename]);vs=list(values[filename])
  if quirks:
   hs=[s.replace("_"," ").title() for s in hs]+["","  "]
   vs+=["",""]
   if filename=="schedule.csv":vs[3]="North\nWing"
   if filename=="payers.csv":vs[1]="Receiver Caf\u00e9"
  if filename==bad_file:
   hs.append(duplicate);vs.append(value)
  text=io.StringIO(newline="")
  writer=csv.writer(text,lineterminator="\r\n")
  writer.writerow(hs)
  if quirks:writer.writerow([])
  if not(header_only and filename==bad_file):writer.writerow(vs)
  if quirks:writer.writerow([""]*len(hs))
  content=text.getvalue().encode("cp1252" if quirks and filename=="payers.csv" else "utf-8")
  if quirks and filename=="schedule.csv":content=b"\xef\xbb\xbf"+content
  if empty:content=b""
  (inputs/filename).write_bytes(content)
 for filename in ("digest.html","summary.json","audit.jsonl","worklist.csv","ledger.csv","visit_status_review.csv","uncovered_visits.csv"):
  (out/filename).write_bytes(("Existing receiver-owned artifact "+filename+"\n").encode())
 before=snapshot(out);input_before=snapshot(inputs)
 command=[sys.executable,"-B","-m","ptauth","run","--data",str(inputs),"--out",str(out),
          "--as-of","2026-09-28","--clinic-timezone","UTC"]
 env={"PATH":os.defpath,"PYTHONPATH":str(source),"PYTHONDONTWRITEBYTECODE":"1","LANG":"C.UTF-8","TZ":"UTC"}
 result=subprocess.run(command,cwd=source,env=env,capture_output=True,timeout=20)
 (case/"stdout.bin").write_bytes(result.stdout);(case/"stderr.bin").write_bytes(result.stderr)
 after=snapshot(out)
 row={"name":name,"argv":command,"returncode":result.returncode,"stdout":result.stdout.decode("utf-8","replace"),
      "stderr":result.stderr.decode("utf-8","replace"),"inputs_before":input_before,"inputs_after":snapshot(inputs),
      "reports_before":before,"reports_after":after,"expected_refusal":bad_file is not None}
 cases.append(row)
 try:
  require(row["inputs_before"]==row["inputs_after"],"input contents changed")
  if bad_file:
   require(result.returncode==2,"ambiguous header accepted or refusal did not use existing exit2")
   require(result.stdout==b"","refusal printed a success summary")
   message=row["stderr"]
   require(message.startswith("ERROR: "),"existing user-facing InputError route missing")
   require(bad_file in message,"input filename missing")
   require(re.search(r"\bline\s+"+str(header_line)+r"\b",message),"physical header-end line missing")
   key=re.sub(r"[\s\-]+","_",duplicate.strip().lower())
   require(key in message,"ambiguous normalized header name missing")
   last=len(headers[bad_file])+1
   require(re.search(r"\bcolumns?\b[^\n]*\b"+str(first)+r"\b[^\n]*\b"+str(last)+r"\b",message,re.I),
           "both one-based header columns missing")
   require(before==after,"pre-existing report or audit bytes/directory membership changed")
  else:
   require(result.returncode==0,"accepted-input control failed: "+row["stderr"])
   require(result.stderr==b"","accepted-input control wrote stderr")
   summary=json.loads((out/"summary.json").read_text(encoding="utf-8"))
   expected=0 if empty else 1
   require(all(summary["counts"][k]==expected for k in ("visits","auths","patients")),"accepted row counts changed")
   require((out/"digest.html").read_bytes().startswith(b"<!doctype html>"),"actual report missing")
   require(summary["clinic_timezone"]=="UTC","existing explicit timezone lost")
   if quirks:
    visits=api.load_visits(inputs/"schedule.csv")
    require(len(visits)==1 and visits[0].clinic=="North\nWing","quoted multiline field changed")
    require(visits[0].source_row=="schedule.csv:row4","physical source row shifted")
    require(api.load_payers(inputs/"payers.csv")["PAY1"].payer_name=="Receiver Caf\u00e9","cp1252 value changed")
  groups.append({"name":name,"passed":True})
 except Exception as exc:groups.append({"name":name,"passed":False,"error":type(exc).__name__+": "+str(exc)})
run_case("schedule-normalized",bad_file="schedule.csv",duplicate="Visit-ID",value="V-shadow",first=1)
run_case("authorization-normalized",bad_file="authorizations.csv",duplicate="Visits Authorized",value="99",first=4)
run_case("payer-normalized",bad_file="payers.csv",duplicate="Payer Name",value="Shadow Plan",first=2)
run_case("patient-exact",bad_file="patients.csv",duplicate="display_name",value="Shadow Person",first=2)
run_case("header-only-ambiguity",bad_file="schedule.csv",duplicate="Visit ID",value="unused",first=1,header_only=True)
run_case("quoted-header-physical-line",bad_file="schedule.csv",duplicate="Visit\nID",value="V-shadow",first=1,header_line=2)
run_case("accepted-export-quirks",quirks=True)
run_case("accepted-empty-files",empty=True)
actual={x.relative_to(package).as_posix():digest(x.read_bytes()) for x in sorted(package.rglob("*")) if x.is_file()}
groups.append({"name":"isolated-source-preserved","passed":actual==manifest})
receipt={"schema":"hamon.pt-header.independent-receiving.v1","actor":"estate-65ae877160f6/root",
 "recorded_at":datetime.now(timezone.utc).isoformat(),"source_origin":str(a.source),"source_files":manifest,
 "data_sha256":a.data_sha,"receiver_sha256":digest(Path(__file__).read_bytes()),"python":sys.version,
 "reference_receipt":str(a.reference) if a.reference else None,
 "reference_receipt_sha256":digest(a.reference.read_bytes()) if a.reference else None,
 "groups":groups,"cases":cases,"passed":sum(x["passed"] for x in groups),"failed":sum(not x["passed"] for x in groups),
 "scope":"Eight actual native report CLI processes on newly authored synthetic inputs and root-owned prior reports; no clinical/rule/payer validity or browser qualification is claimed. Exact isolated executable package; source/data unchanged."}
receipt_path=run/"receipt.json"
receipt_path.write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps({"receipt":str(receipt_path),"sha256":digest(receipt_path.read_bytes()),"receiver_sha256":receipt["receiver_sha256"],
                  "passed":receipt["passed"],"failed":receipt["failed"],"groups":groups}))
raise SystemExit(1 if receipt["failed"] else 0)
