"""Independent receiving of the bounded demo through the unchanged freight engine."""
from pathlib import Path
from datetime import datetime, timedelta
import hashlib, json, platform, subprocess, sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
REPO = Path(sys.argv[1]).resolve()
CORE = {
 "freight_packets/freightpkt/models.py":"8a24ed2cca6f45aa8a47d793620b0e2e4d573ec92209954d3f3156795e3f0e05",
 "freight_packets/freightpkt/detention.py":"31ca31fd3210ff680bc83291916e39ea19b82580c3a090720556afd4ef0cd76b",
 "freight_packets/freightpkt/invoice_match.py":"37a9e0801de948c3b558ca7c9846b3d0eb76ec062703ee3e5132df273ff569ab",
}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
assert {p:sha(REPO/p) for p in CORE} == CORE
site = REPO/"demos/freight-whatif/site"
model_before = {p.name:sha(p) for p in site.iterdir() if p.is_file()}
sys.path.insert(0, str(REPO/"freight_packets"))
from freightpkt.models import Load, RateCon, RateConStop, StopEvent, Invoice, InvoiceLine, to_dict
from freightpkt.detention import evaluate_load
from freightpkt.invoice_match import match_invoices, TOLERANCE_CENTS
assert TOLERANCE_CENTS == 0
B = dict(appointment="2026-11-01T01:30",arrival="2026-11-01T01:30",departure="2026-11-01T04:30",
 free_minutes=61,increment_minutes=17,late_grace_minutes=15,detention_rate_cents=31,
 detention_cap_cents=None,linehaul_cents=145000,fuel_cents=24500,detention_cents=0,
 lumper_cents=15000,tonu_cents=0,invoice_total_cents=None,pod_received=True,ratecon_complete=True)
A=datetime.fromisoformat(B["appointment"])
def at(minutes): return (A+timedelta(minutes=minutes)).isoformat(timespec="minutes")
cases=[]
def add(name, **kw): cases.append({"id":name,"scenario":dict(B,**kw)})
add("odd-increment-baseline")
add("early-exit-before-appointment",arrival=at(-45),departure=at(-1))
add("early-exit-at-appointment",arrival=at(-1),departure=at(0))
add("earliest-entry-inclusive",arrival=at(-720),departure=at(-719))
add("earliest-entry-excluded",arrival=at(-721),departure=at(-720))
add("latest-entry-inclusive",arrival=at(1440),departure=at(1441),late_grace_minutes=1440,free_minutes=0,increment_minutes=1)
add("latest-entry-excluded",arrival=at(1441),departure=at(1442),late_grace_minutes=1440)
add("exit-24h-inclusive",departure=at(1440),free_minutes=0,detention_rate_cents=100000,increment_minutes=1)
add("exit-24h-excluded",departure=at(1441))
add("arrival-missing-exit-present",arrival=None)
add("exit-missing",departure=None)
add("both-tracking-values-missing",arrival=None,departure=None,ratecon_complete=False)
add("zero-length-pair",departure=at(0))
add("reversed-pair",departure=at(-1))
add("exact-grace-odd-clock",arrival=at(15),departure=at(194))
add("past-grace-odd-clock",arrival=at(16),departure=at(195))
add("past-grace-parse-warning",arrival=at(16),departure=at(195),ratecon_complete=False)
add("capped-then-parse-warning",detention_cap_cents=1,ratecon_complete=False)
add("zero-cap-positive-calculation",detention_cap_cents=0)
add("zero-rate-positive-billable",detention_rate_cents=0)
add("exact-free-threshold",departure=at(61))
add("one-minute-after-free",departure=at(62))
add("one-minute-before-increment",departure=at(77))
add("exact-odd-increment",departure=at(78))
add("one-minute-after-increment",departure=at(79))
add("half-cent-rounds-up-2point5",departure=at(150),free_minutes=0,increment_minutes=1,detention_rate_cents=1)
add("cap-exact-rounded-amount",departure=at(150),free_minutes=0,increment_minutes=1,detention_rate_cents=1,detention_cap_cents=3)
add("cap-below-rounded-amount",departure=at(150),free_minutes=0,increment_minutes=1,detention_rate_cents=1,detention_cap_cents=2)
add("cap-above-rounded-amount",departure=at(150),free_minutes=0,increment_minutes=1,detention_rate_cents=1,detention_cap_cents=4)
add("all-findings-with-underbilled-base-lines",linehaul_cents=144999,fuel_cents=24499,detention_cents=62,
 lumper_cents=15001,tonu_cents=1,invoice_total_cents=0,pod_received=False)
add("underbilled-allowed-accessorial",lumper_cents=14999,detention_cents=1)
add("header-one-cent-above-sum",invoice_total_cents=184501)
add("header-one-cent-below-sum",invoice_total_cents=184499)
add("maximum-independent-lines-automatic-sum",linehaul_cents=100000000,fuel_cents=100000000,
 detention_cents=100000000,lumper_cents=100000000,tonu_cents=100000000)
add("upper-date-range-missing-exit",appointment="2100-12-31T23:59",arrival="2100-12-31T23:59",departure=None)
add("lower-date-range-missing-entry",appointment="1900-01-01T00:00",arrival=None,departure="1900-01-01T00:01")
add("leap-day-crosses-month",appointment="2000-02-29T23:59",arrival="2000-02-29T23:59",departure="2000-03-01T03:00")
add("spring-civil-time-no-zone-conversion",appointment="2026-03-08T01:30",arrival="2026-03-08T01:30",departure="2026-03-08T04:30")
add("parse-warning-with-no-invoice-mismatch",ratecon_complete=False)
def authority(s):
 load=Load(load_id="DEMO-104",customer="Example Distribution",carrier="Example Freight",tractor="",trailer="",
  pod_received=s["pod_received"],ratecon_file="scenario:ratecon",source_row="scenario:load",mode="brokered")
 rc=RateCon(load_id=load.load_id,ratecon_no="DEMO-RC-104",customer=load.customer,carrier=load.carrier,
  linehaul_cents=145000,fuel_cents=24500,detention_rate_cents=s["detention_rate_cents"],
  free_minutes=s["free_minutes"],increment_minutes=s["increment_minutes"],detention_cap_cents=s["detention_cap_cents"],
  late_grace_minutes=s["late_grace_minutes"],accessorials_cents={"LUMPER":15000},
  stops=[RateConStop("delivery","Sample receiving dock",datetime.fromisoformat(s["appointment"]))],
  source="scenario:ratecon",parse_warnings=[] if s["ratecon_complete"] else ["synthetic rate confirmation marked incomplete"])
 events=[]
 for key,event in (("arrival","entry"),("departure","exit")):
  if s[key] is not None:
   events.append(StopEvent(asset=load.load_id,location="Sample receiving dock",event=event,time=datetime.fromisoformat(s[key]),
    source_row="scenario:tracking",source_kind="tracking"))
 stops=evaluate_load(load,rc,events)
 assert len(stops)==1
 stop=stops[0]
 lines=[InvoiceLine(code,s[field]) for code,field in (("LINEHAUL","linehaul_cents"),("FUEL","fuel_cents"),
  ("DETENTION","detention_cents"),("LUMPER","lumper_cents"))]
 # UI contract: a zero TONU value means no TONU line, rather than a present zero-value line.
 if s["tonu_cents"]!=0:lines.append(InvoiceLine("TONU",s["tonu_cents"]))
 total=sum(line.amount_cents for line in lines)
 inv=Invoice(invoice_no="DEMO-INV-104",load_id=load.load_id,carrier=load.carrier,invoice_date=s["appointment"][:10],
  total_cents=total if s["invoice_total_cents"] is None else s["invoice_total_cents"],lines=lines,source_row="scenario:invoice")
 findings=match_invoices([inv],{load.load_id:load},{load.load_id:rc},{load.load_id:stop.amount_cents})
 return {"stop":to_dict(stop),"flags":[to_dict(flag) for flag in findings],"totals":{
  "line_sum_cents":total,"invoice_total_cents":inv.total_cents,"supported_detention_cents":stop.amount_cents}}
for c in cases:c["expected"]=authority(c["scenario"])
by={c["id"]:c["expected"] for c in cases}
assert (by["odd-increment-baseline"]["stop"]["billable_minutes"],by["odd-increment-baseline"]["stop"]["amount_cents"])==(119,61)
assert by["early-exit-before-appointment"]["stop"]["status"]=="ok"
assert by["half-cent-rounds-up-2point5"]["stop"]["amount_cents"]==3
assert by["cap-exact-rounded-amount"]["stop"]["capped"] is False
assert by["cap-below-rounded-amount"]["stop"]["capped"] is True
assert by["capped-then-parse-warning"]["stop"]["capped"] is False
assert by["capped-then-parse-warning"]["stop"]["amount_cents"]==0
assert by["parse-warning-with-no-invoice-mismatch"]["flags"]==[]
assert len(by["all-findings-with-underbilled-base-lines"]["flags"])==7
assert by["maximum-independent-lines-automatic-sum"]["totals"]["line_sum_cents"]==500000000
payload={"scope":"Independent curated input cases evaluated directly by pinned freight Python functions; no author fixture generator reused.",
 "core_sha256":CORE,"candidate_files_before":model_before,"cases":cases}
oracle=ROOT/"independent-oracle.json"
oracle.write_text(json.dumps(payload,indent=2)+"\n")
p=subprocess.run(["/opt/homebrew/bin/node",str(ROOT/"probe_model.mjs"),str(site/"model.mjs"),str(oracle),str(ROOT/"independent-model-result.json")],text=True,capture_output=True)
(ROOT/"independent-model-execution.log").write_text(p.stdout+p.stderr)
after={p.name:sha(p) for p in site.iterdir() if p.is_file()}
assert {p:sha(REPO/p) for p in CORE}==CORE
assert after["model.mjs"]==model_before["model.mjs"]
assert after["data.mjs"]==model_before["data.mjs"]
result=json.loads((ROOT/"independent-model-result.json").read_text())
receipt={"status":"pass" if p.returncode==0 else "fail","independent_cases":len(cases),"source_unchanged":True,
 "model_and_data_unchanged_during_run":True,"python":platform.python_version(),"node_result":result,
 "oracle_sha256":sha(oracle),"scripts_sha256":{p.name:sha(p) for p in [ROOT/"independent_parity.py",ROOT/"probe_model.mjs"]},
 "core_sha256":CORE,"candidate_files_before":model_before,"candidate_files_after":after,
 "limits":"Bounded synthetic projection parity. No carrier, contractual entitlement, legal, payment, settlement, or live-data outcome claim."}
out=ROOT/"independent-parity-receipt.json";out.write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps({"status":receipt["status"],"cases":len(cases),"passed":result["passed"],"failed":result["failed"],
 "receipt":str(out),"receipt_sha256":sha(out),"oracle_sha256":sha(oracle),"model_sha256":after["model.mjs"],"data_sha256":after["data.mjs"]}))
raise SystemExit(p.returncode)
