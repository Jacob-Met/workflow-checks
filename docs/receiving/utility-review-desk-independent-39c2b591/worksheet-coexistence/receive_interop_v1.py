"""Bounded independent current CLI/HTTP interoperability; no browser or native-suite replay."""
import argparse,csv,hashlib,http.client,io,json,os,pathlib,signal,subprocess,sys,time,traceback
from copy import deepcopy
from html.parser import HTMLParser
ROOT=pathlib.Path(__file__).parent
sys.path.insert(0,str(ROOT/"baseline"/"utility_watch"))
from uwatch import review as ORIGINAL
def digest(b):return hashlib.sha256(b).hexdigest()
def metadata(p):
 b=p.read_bytes();return {"bytes":len(b),"sha256":digest(b)}
class PrintedRows(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True);self.rows={};self.row=None;self.capture=None;self.parts=[];self.label=None;self.scripts=0
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=="script":self.scripts+=1
  if tag=="article":
   self.row={"state":a.get("data-row-state"),"fields":{}}
   self.rows[a["id"].removeprefix("row-")]=self.row
  if self.row is not None and tag in ("dt","dd"):
   self.capture=tag;self.parts=[]
 def handle_data(self,data):
  if self.capture is not None:self.parts.append(data)
 def handle_endtag(self,tag):
  if tag==self.capture:
   v="".join(self.parts)
   if tag=="dt":self.label=v
   else:self.row["fields"][self.label]=v
   self.capture=None
  if tag=="article":self.row=None
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--source",type=pathlib.Path,required=True);ap.add_argument("--out",type=pathlib.Path,required=True)
 a=ap.parse_args();a.source=a.source.resolve();a.out.mkdir()
 oracle=json.loads((ROOT/"evidence"/"FIXTURE_ORACLE.json").read_text())
 evidence=a.out;env=os.environ.copy();env.update(PYTHONPATH=str(a.source/"utility_watch"),PYTHONDONTWRITEBYTECODE="1",TMPDIR=str(ROOT/"temp"),PYTHONUNBUFFERED="1")
 receipt={"scope":"new review-desk / worksheet shared-command interoperability only","source":str(a.source),
 "python":sys.version,"original_validator":str(pathlib.Path(ORIGINAL.__file__)),"checks":[],"children":[],"http":[],"artifacts":{}}
 paths=[]
 base=deepcopy(oracle["rows"]);north=oracle["current_ids"][oracle["accounts"]["north"]];south=oracle["current_ids"][oracle["accounts"]["south"]]
 current_ids={north,south};manifest=next(r for r in base if r["row_state"]=="manifest")
 source_before={str(p.relative_to(a.source)):metadata(p) for p in sorted((a.source/"utility_watch"/"uwatch").glob("*")) if p.is_file()}
 fixture_before={str(p.relative_to(ROOT/"fixture-v1")):metadata(p) for p in sorted((ROOT/"fixture-v1").rglob("*")) if p.is_file()}
 servers=[]
 def check(name,condition,detail=None):
  entry={"name":name,"passed":bool(condition)}
  if detail is not None:entry["detail"]=detail
  receipt["checks"].append(entry)
  if not condition:raise AssertionError(name)
 def cli(name,args):
  command=[sys.executable,"-m","uwatch",*map(str,args)]
  r=subprocess.run(command,env=env,cwd=a.source,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
  (evidence/(name+".stdout")).write_bytes(r.stdout);(evidence/(name+".stderr")).write_bytes(r.stderr)
  receipt["children"].append({"name":name,"command":command,"returncode":r.returncode,"stdout":metadata(evidence/(name+".stdout")),"stderr":metadata(evidence/(name+".stderr"))})
  assert r.returncode==0,(name,r.returncode,r.stderr.decode("utf-8",errors="replace"))
  return r.stdout
 def start(name,path):
  command=[sys.executable,"-m","uwatch","review-desk","--worksheet",str(path),"--port","0"]
  out=(evidence/(name+".stdout")).open("wb");err=(evidence/(name+".stderr")).open("wb")
  p=subprocess.Popen(command,env=env,cwd=a.source,stdout=out,stderr=err)
  entry={"name":name,"command":command,"pid":p.pid}
  servers.append((p,out,err,entry))
  deadline=time.monotonic()+10;prefix="Utility Watch review desk: http://127.0.0.1:"
  while time.monotonic()<deadline:
   raw=(evidence/(name+".stdout")).read_text()
   lines=raw.splitlines()
   if lines and lines[0].startswith(prefix):
    port=int(lines[0][len(prefix):]);entry["origin"]="http://127.0.0.1:"+str(port);return port
   if p.poll() is not None:raise RuntimeError("desk exited before URL: "+(evidence/(name+".stderr")).read_text())
   time.sleep(.05)
  raise RuntimeError("desk startup deadline")
 def request(name,port,method,path,payload=None,token=None):
  body=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None
  headers={"Origin":"http://127.0.0.1:"+str(port)}
  if body is not None:headers["Content-Type"]="application/json"
  if token is not None:headers["X-Review-Token"]=token
  c=http.client.HTTPConnection("127.0.0.1",port,timeout=10);c.request(method,path,body,headers)
  r=c.getresponse();raw=r.read();hs=dict(r.getheaders());status=r.status;c.close()
  (evidence/(name+".response")).write_bytes(raw)
  receipt["http"].append({"name":name,"method":method,"path":path,"status":status,"headers":hs,"response":metadata(evidence/(name+".response"))})
  if payload is not None:(evidence/(name+".request.json")).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
  return status,raw,hs
 def expected_rows(previous,row_id,status,reviewer,note):
  after=deepcopy(previous)
  row=next(r for r in after if r["row_id"]==row_id)
  assert row_id in current_ids and row["row_state"]=="current"
  row.update(review_status=status,reviewer=reviewer,note=note);return after
 def admitted(raw,expected):
  assert len(ORIGINAL._previous(raw))==3
  rows=[r for _,r in ORIGINAL._csv(raw,"actual interoperable output")[1]]
  assert rows==expected,"Complete cell oracle differs"
  assert next(r for r in rows if r["row_state"]=="manifest")==manifest
  return rows
 def view(name,port,expected,path):
  status,raw,_=request(name,port,"GET","/api/worksheet");assert status==200
  v=json.loads(raw)
  assert v["snapshot"]==digest(path.read_bytes()) and v["filename"]==path.name
  assert v["schema"]==oracle["schema"] and v["metadata"]=={k:manifest[k] for k in ("as_of","eval_from","data_mode")}
  assert v["rows"]==[r for r in expected if r["row_state"]!="manifest"]
  return v
 try:
  input_path=pathlib.Path(oracle["prepared"])
  p1=start("01-desk-current",input_path);v1=view("01-current-view",p1,base,input_path)
  change1={"row_id":north,"review_status":"in_progress","reviewer":"Desk reviewer 北","note":"First desk annotation\nLiteral <b>saved only</b>."}
  e1=expected_rows(base,north,change1["review_status"],change1["reviewer"],change1["note"])
  st,b1,h1=request("02-first-download",p1,"POST","/api/download",{"snapshot":v1["snapshot"],"changes":[change1]},v1["token"])
  assert st==200 and "utility-review-edited.csv" in h1.get("Content-Disposition","")
  admitted(b1,e1);f1=evidence/"03-desk-export.csv";f1.write_bytes(b1);paths.append(f1)
  check("current desk exports only the exact North current annotation and preserves all other cells",True)
  listing=json.loads(cli("04-worksheet-list",["worksheet","list","--worksheet",f1,"--include-history","--json"]))
  assert listing["rows"]==[r for r in e1 if r["row_state"]!="manifest"] and listing["current"]==2 and listing["history"]==1 and listing["shown"]==3
  assert listing["worksheet_sha256"]==digest(b1)
  change2={"row_id":south,"review_status":"in_progress","reviewer":"CLI reviewer 南","note":"CLI note, exact South account\r\nLiteral <script>never code</script> & Ω."}
  e2=expected_rows(e1,south,change2["review_status"],change2["reviewer"],change2["note"])
  f2=evidence/"05-worksheet-annotated.csv"
  cli("05-worksheet-annotate",["worksheet","annotate","--worksheet",f1,"--row-id",south,"--status",change2["review_status"],"--reviewer",change2["reviewer"],"--note",change2["note"],"--out",f2])
  admitted(f2.read_bytes(),e2);paths.append(f2);assert f1.read_bytes()==b1
  check("new worksheet list and annotate consume the real desk CSV using exact account/row identity",True)
  p2=start("06-desk-annotated",f2);v2=view("06-annotated-view",p2,e2,f2)
  change3={"row_id":north,"review_status":"reviewed","reviewer":"Final desk reviewer","note":"Reopened command output checked – 完了.\nOriginal historical note stays separate."}
  e3=expected_rows(e2,north,change3["review_status"],change3["reviewer"],change3["note"])
  stale,_,_=request("07-old-snapshot-refused",p2,"POST","/api/download",{"snapshot":v1["snapshot"],"changes":[change3]},v2["token"])
  assert stale==409
  status,b3,_=request("08-current-download",p2,"POST","/api/download",{"snapshot":v2["snapshot"],"changes":[change3]},v2["token"])
  assert status==200;admitted(b3,e3)
  f3=evidence/"09-reopened-desk-export.csv";f3.write_bytes(b3);paths.append(f3)
  v2_after=view("10-view-remains-admitted",p2,e2,f2)
  assert v2_after==v2
  check("desk reopens the new CLI file, refuses the old snapshot, exports both edits and retains immutable source view",True)
  printed=evidence/"11-review-report.html"
  cli("11-printable-command",["review-report","--worksheet",f3,"--out",printed])
  html=printed.read_text(encoding="utf-8");parsed=PrintedRows();parsed.feed(html)
  assert set(parsed.rows)=={r["row_id"] for r in e3 if r["row_state"]!="manifest"} and parsed.scripts==0
  labels={"Account":"account_no","Bill or period":"finding_key","Property":"property","Utility":"utility","Report as of":"as_of","Evaluation from":"eval_from","Data mode":"data_mode","Reviewer":"reviewer","Note":"note","Worksheet row ID":"row_id","Finding ID":"finding_id","Evidence version":"evidence_version","Protected record SHA256":"record_sha256"}
  statuslabels={"open":"Open","in_progress":"In progress","reviewed":"Reviewed"}
  for r in e3:
   if r["row_state"]=="manifest":continue
   shown=parsed.rows[r["row_id"]];assert shown["state"]==r["row_state"]
   assert all(shown["fields"][label]==r[key] for label,key in labels.items())
   assert shown["fields"]["Review status"]==statuslabels[r["review_status"]]
  assert digest(b3) in html
  paths.append(printed);check("existing printable CLI preserves every displayed row identity, historical state and literal annotation",True)
  reconciled=evidence/"12-reconciled.csv"
  cli("12-reconciliation-command",["review","--data",oracle["data"],"--report",oracle["report"],"--previous",f3,"--out",reconciled])
  admitted(reconciled.read_bytes(),e3);paths.append(reconciled)
  check("current native source reconciliation retains all exact current edits, original history and manifest cells",True)
  after={str(p.relative_to(a.source)):metadata(p) for p in sorted((a.source/"utility_watch"/"uwatch").glob("*")) if p.is_file()}
  fixture_after={str(p.relative_to(ROOT/"fixture-v1")):metadata(p) for p in sorted((ROOT/"fixture-v1").rglob("*")) if p.is_file()}
  assert after==source_before and fixture_after==fixture_before
  assert f1.read_bytes()==b1 and admitted(f2.read_bytes(),e2)==e2 and f3.read_bytes()==b3
  check("all admitted originals, source/report fixtures, prior exports and executed package bytes remain unchanged",True)
  (evidence/"EXPECTED_FINAL_ROWS.json").write_text(json.dumps(e3,ensure_ascii=False,indent=2)+"\n")
  receipt["passed"]=True
 except BaseException:
  receipt.update(passed=False,traceback=traceback.format_exc())
 finally:
  for p,out,err,entry in servers:
   if p.poll() is None:p.send_signal(signal.SIGINT)
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=5);entry["termination_fallback"]=True
   out.close();err.close();entry.update(returncode=p.returncode,stdout=metadata(evidence/(entry["name"]+".stdout")),stderr=metadata(evidence/(entry["name"]+".stderr")))
   receipt["children"].append(entry)
  receipt.update(artifacts={p.name:metadata(p) for p in paths},fixture_before=fixture_before,source_before=source_before)
  (evidence/"RECEIPT.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
  print(json.dumps({"passed":receipt.get("passed"),"checks":receipt["checks"],"cli_children":len(receipt["children"]),"http_statuses":[h["status"] for h in receipt["http"]],"artifacts":receipt["artifacts"],"traceback":receipt.get("traceback")},ensure_ascii=False))
 return 0 if receipt.get("passed") else 1
if __name__=="__main__":raise SystemExit(main())
