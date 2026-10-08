"""Independent disposable fixture: native producer and original validator, no checker mocks."""
import csv,hashlib,io,json,os,pathlib,sys,traceback
from datetime import date
ROOT=pathlib.Path(__file__).parent
os.environ["TMPDIR"]=str(ROOT/"temp")
sys.path.insert(0,str(ROOT/"baseline"/"utility_watch"))
from uwatch import engine,review
FIX=ROOT/"fixture-v1"
FIX.mkdir()
A="UW-NORTH-001"
B="UW-SOUTH-001"
ACCOUNT_FIELDS=["account_no","property","utility","vendor","scope","unit","cycle"]
BILL_FIELDS=["bill_id","account_no","vendor_invoice_no","period_start","period_end","usage","usage_unit","amount","late_fee","prior_balance","due_date","received_date"]
def write_csv(path,fields,rows):
 with path.open("w",encoding="utf-8",newline="") as f:
  w=csv.writer(f,lineterminator="\n");w.writerow(fields);w.writerows(rows)
def data(root,a_fee):
 root.mkdir()
 write_csv(root/"accounts.csv",ACCOUNT_FIELDS,[
  [A,"North – 温室","electric","Disposable vendor","common","","irregular"],
  [B,"South & <annex>","electric","Disposable vendor","common","","irregular"]])
 bills=[]
 for acct,fee in ((A,a_fee),(B,"2.00")):
  bills.extend([
   ["baseline-2025",acct,"PRIOR-YEAR","2025-09-01","2025-09-30","100","kWh","50","0","0","2025-11-01","2025-10-01"],
   ["same-key",acct,"INVOICE-SHARED","2026-09-01","2026-09-30","100","kWh","50",fee,"0","2026-11-01","2026-10-01"]])
 write_csv(root/"bills.csv",BILL_FIELDS,bills)
 write_csv(root/"occupancy.csv",["property","unit","status","from","to"],[])
 write_csv(root/"payments.csv",["payment_id","account_no","vendor_invoice_no","amount","paid_date"],[])
 (root/"expected.json").write_text(json.dumps({"as_of":"2026-10-08","eval_from":"2026-09-01","fixture":"Independent command interoperability; all data invented"},ensure_ascii=False)+"\n",encoding="utf-8")
def serialize(rows):
 b=io.StringIO(newline="")
 w=csv.DictWriter(b,fieldnames=review.COLUMNS,lineterminator="\n")
 w.writeheader();w.writerows(rows)
 return b.getvalue().encode("utf-8")
def rows(path):
 return [row for _,row in review._csv(path.read_bytes(),"independent fixture")[1]]
def hashed(path):
 b=path.read_bytes();return {"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()}
receipt={"scope":"fixture creation only; current native loader/checker/reconciler used without mocks or product edits","checks":[]}
try:
 old=FIX/"source-initial";current=FIX/"source-current"
 data(old,"1.00");data(current,"7.00")
 oldreport=FIX/"report-initial";currentreport=FIX/"report-current"
 first=FIX/"00-original.csv";annotated=FIX/"01-earlier-annotated.csv";prepared=FIX/"02-current-with-history.csv"
 s1=engine.run(old,oldreport,date(2026,10,8),eval_from=date(2026,9,1))
 assert s1["flags"]==2 and s1["exceptions"]==0 and s1["payment_queue"]==0,s1
 r1=review.reconcile(old,oldreport/"summary.json",first)
 prior=rows(first)
 for row in prior:
  if row["row_state"]=="current":
   row.update(review_status="reviewed",reviewer="Earlier North reviewer" if row["account_no"]==A else "Earlier South reviewer",
              note="Earlier north fee: 1.00\nPreserve this as history." if row["account_no"]==A else "South annotation already reviewed – 保持.")
 annotated.write_bytes(serialize(prior));review._previous(annotated.read_bytes())
 s2=engine.run(current,currentreport,date(2026,10,8),eval_from=date(2026,9,1))
 assert s2["flags"]==2 and s2["exceptions"]==0 and s2["payment_queue"]==0,s2
 r2=review.reconcile(current,currentreport/"summary.json",prepared,annotated)
 final=rows(prepared);admitted=review._previous(prepared.read_bytes())
 current_rows=[r for r in final if r["row_state"]=="current"]
 history=[r for r in final if r["row_state"]=="changed"]
 assert len(current_rows)==2 and len(history)==1
 by_account={r["account_no"]:r for r in current_rows}
 assert set(by_account)=={A,B}
 assert all(r["finding_key"]=="same-key" and r["code"]=="LATE_FEE_OR_PAST_DUE" for r in current_rows)
 assert len({r["finding_id"] for r in current_rows})==2
 assert by_account[A]["row_id"]!=history[0]["row_id"] and by_account[A]["finding_id"]==history[0]["finding_id"]
 assert by_account[A]["review_status"]=="open" and by_account[A]["reviewer"]=="" and by_account[A]["note"]==""
 assert by_account[B]["review_status"]=="reviewed" and by_account[B]["reviewer"]=="Earlier South reviewer"
 assert history[0]["account_no"]==A and history[0]["review_status"]=="reviewed"
 assert history[0]["note"]=="Earlier north fee: 1.00\nPreserve this as history."
 original_map={r["account_no"]:r for r in prior if r["row_state"]=="current"}
 assert by_account[B]==original_map[B]
 assert history[0]["evidence_version"]!=by_account[A]["evidence_version"]
 receipt["checks"]=[{"name":x,"passed":True} for x in (
 "current original engine produces only two intended same-key account-scoped flags",
 "earlier allowed annotations admitted by the original validator",
 "changed north evidence creates a fresh open current row and one preserved historical row",
 "unchanged south account retains its exact prior identity and annotation",
 "complete current worksheet passes the unchanged native validator")]
 oracle={"schema":review.SCHEMA,"columns":review.COLUMNS,"editable":review.EDITABLE,"accounts":{"north":A,"south":B},
 "current_ids":{a:r["row_id"] for a,r in by_account.items()},"historical_id":history[0]["row_id"],
 "rows":final,"prepared":str(prepared),"data":str(current),"report":str(currentreport/"summary.json"),
 "engine_sha256":hashlib.sha256(pathlib.Path(engine.__file__).read_bytes()).hexdigest(),
 "review_sha256":hashlib.sha256(pathlib.Path(review.__file__).read_bytes()).hexdigest(),
 "fixture_files":{str(p.relative_to(FIX)):hashed(p) for p in sorted(FIX.rglob("*")) if p.is_file()}}
 (ROOT/"evidence"/"FIXTURE_ORACLE.json").write_text(json.dumps(oracle,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 receipt.update(passed=True,native_initial=r1,native_current=r2,prepared=hashed(prepared),current_ids=oracle["current_ids"],historical_id=oracle["historical_id"])
except BaseException:
 receipt.update(passed=False,traceback=traceback.format_exc())
 raise
finally:
 (ROOT/"evidence"/"FIXTURE_RESULT.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps(receipt,ensure_ascii=False))
