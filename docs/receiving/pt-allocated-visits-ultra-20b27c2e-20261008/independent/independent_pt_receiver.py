"""Independent stdlib/CLI/HTTP PT allocation receiver. No authored-test imports."""
from __future__ import annotations
import argparse, copy, csv, hashlib, io, json, os, re, subprocess, sys, threading, unittest
from collections import Counter
from contextlib import contextmanager
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parent
ORACLE=json.loads((ROOT/"oracle.json").read_text())
FIELDS=ORACLE["fields"]
OLD_CSV=["worklist.csv","ledger.csv","uncovered_visits.csv","visit_status_review.csv"]
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def snap(p):return {str(x.relative_to(p)):sha(x.read_bytes()) for x in sorted(p.rglob("*")) if x.is_file()}
def normal(s):return re.sub(r"\s+"," ",str(s)).strip()
def canonical(rows):return Counter(json.dumps(r,sort_keys=True,ensure_ascii=False) for r in rows)
def summary_old(s):return {k:v for k,v in s.items() if k not in {"generated_at","allocation_review","allocation_review_note"}}
def audit_old(p):
    return [{k:v for k,v in json.loads(line).items() if k!="ts"} for line in p.read_text().splitlines()]
def fragment(digest):
    match=re.search(r"<h2\b[^>]*>\s*Allocated visits[\s\S]*?(?=<h2\b|</body>)",digest,re.I)
    return match.group(0) if match else None

class Fragment(HTMLParser):
    def __init__(self,text):
        super().__init__(convert_charrefs=True);self.text=[];self.rows=[];self.current=None;self.dangerous=[]
        self.feed(text)
    def handle_starttag(self,tag,attrs):
        if tag=="tr":self.current=[]
        for k,v in attrs:
            if k.lower().startswith("on") or (k.lower() in {"src","href"} and str(v).lower().startswith(("javascript:","data:"))):
                self.dangerous.append((tag,k,v))
        if tag in {"script","img","svg","iframe","object","embed","math","style"}:self.dangerous.append((tag,attrs))
    def handle_endtag(self,tag):
        if tag=="tr" and self.current is not None:
            self.rows.append(normal(" ".join(self.current)));self.current=None
    def handle_data(self,text):
        self.text.append(text)
        if self.current is not None:self.current.append(text)

@contextmanager
def server(app,records):
    base=make_handler(app)
    class Recorded(base):
        def _send(self,code,body,ctype="application/json"):
            records.append({"method":self.command,"path":self.path,"status":code,"bytes":len(body),
                            "sha256":sha(body),"content_type":ctype})
            return super()._send(code,body,ctype)
    srv=ThreadingHTTPServer(("127.0.0.1",0),Recorded)
    thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    try:yield f"http://127.0.0.1:{srv.server_port}"
    finally:srv.shutdown();srv.server_close();thread.join()

def get(origin,path):
    try:
        with urlopen(origin+path,timeout=10) as r:return r.status,r.read(),r.headers.get("Content-Type")
    except HTTPError as e:return e.code,e.read(),e.headers.get("Content-Type")

class Receiving(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference=json.loads((ROOT/"baseline-reference/summary.json").read_text())
        cls.reference_empty=json.loads((ROOT/"baseline-empty-reference/summary.json").read_text())
        cls.commands=[];cls.http=[]
        cls.before={"source":snap(SOURCE),"fixture":snap(ROOT/"fixture"),"empty_fixture":snap(ROOT/"empty-fixture")}
        cls.run_results={}
        for label,fixture in [("mixed","fixture"),("empty","empty-fixture")]:
            out=OUT/label
            cmd=[sys.executable,"-m","ptauth","run","--data",str(ROOT/fixture),"--out",str(out),
                 "--as-of",ORACLE["as_of"],"--clinic-timezone",ORACLE["clinic_timezone"]]
            env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1","PYTHONPATH":str(SOURCE/"pt_auth")}
            r=subprocess.run(cmd,env=env,capture_output=True,timeout=30)
            (OUT/(label+".stdout")).write_bytes(r.stdout);(OUT/(label+".stderr")).write_bytes(r.stderr)
            cls.commands.append({"argv":cmd,"exit_code":r.returncode,"stdout_sha256":sha(r.stdout),"stderr_sha256":sha(r.stderr)})
            cls.run_results[label]=r
        cls.summary=json.loads((OUT/"mixed/summary.json").read_text())
        cls.empty_summary=json.loads((OUT/"empty/summary.json").read_text())
        cls.digest=(OUT/"mixed/digest.html").read_text()
        cls.empty_digest=(OUT/"empty/digest.html").read_text()
        cls.variants={}
        for name,value in [("missing","__MISSING__"),("null",None),("object",{}),("text","legacy unavailable"),("number",17)]:
            summary=copy.deepcopy(cls.summary)
            if name=="missing":summary.pop("allocation_review",None)
            else:summary["allocation_review"]=value
            before=copy.deepcopy(summary)
            html=render_digest(summary)
            (OUT/(name+"-digest.html")).write_text(html,encoding="utf-8")
            cls.variants[name]={"summary":summary,"html":html,"unchanged":summary==before}
        # Synthetic saved staff decisions are setup data, never submitted through the UI/API.
        states={}
        for index,w in enumerate(cls.summary["worklist"][:2]):
            states[w["key"]]={"state":"submitted" if index==0 else "approved",
                              "note":"Independent synthetic preserved state","at":"2026-10-08T12:00:00Z"}
        save(OUT/"mixed/work_state.json",states);cls.states=states
        cls.read_before=snap(OUT/"mixed")
        app=App(ROOT/"fixture",OUT/"mixed",clinic_timezone=ORACLE["clinic_timezone"])
        with server(app,cls.http) as origin:
            cls.responses={}
            for path in ["/","/calendar_ui.js","/api/summary"]+["/out/"+x for x in OLD_CSV]+[
                         "/out/summary.json","/out/digest.html","/out/allocated_visits.csv"]:
                cls.responses[path]=get(origin,path)
        cls.read_after=snap(OUT/"mixed")
        save(OUT/"http-records.json",cls.http)
    @classmethod
    def tearDownClass(cls):
        after={"source":snap(SOURCE),"fixture":snap(ROOT/"fixture"),"empty_fixture":snap(ROOT/"empty-fixture")}
        save(OUT/"custody.json",{"before":cls.before,"after":after,"unchanged":cls.before==after,
             "read_before":cls.read_before,"read_after":cls.read_after,"reads_unchanged":cls.read_before==cls.read_after,
             "commands":cls.commands,"oracle_sha256":sha((ROOT/"oracle.json").read_bytes())})
    def rows(self):
        rows=self.summary.get("allocation_review")
        self.assertIsInstance(rows,list,"Native summary lacks the allocation_review list")
        return rows
    def by_id(self):return {r["visit_id"]:r for r in self.rows()}
    def frag(self,text=None):
        f=fragment(self.digest if text is None else text)
        self.assertIsNotNone(f,"Printable digest lacks the Allocated visits section")
        return Fragment(f)

    def test_01_cli_ordinary_zone_and_input_controls(self):
        for label,r in self.run_results.items():
            self.assertEqual(r.returncode,0,(label,r.stderr.decode()))
            self.assertIn(ORACLE["clinic_timezone"].encode(),r.stdout)
        self.assertEqual(self.summary["as_of"],ORACLE["as_of"])
        self.assertEqual(self.summary["clinic_timezone"],ORACLE["clinic_timezone"])
        self.assertEqual(self.summary["counts"],ORACLE["reference_counts"])
        self.assertEqual(len(ORACLE["rows"]),52);self.assertEqual(len(ORACLE["manual_expected"]),52)

    def test_02_existing_csv_exact_preservation(self):
        for label,ref in [("mixed","baseline-reference"),("empty","baseline-empty-reference")]:
            for filename in OLD_CSV:
                with self.subTest(label=label,file=filename):
                    self.assertEqual((OUT/label/filename).read_bytes(),(ROOT/ref/filename).read_bytes())

    def test_03_existing_summary_and_audit_meanings(self):
        self.assertEqual(summary_old(self.summary),summary_old(self.reference))
        self.assertEqual(summary_old(self.empty_summary),summary_old(self.reference_empty))
        for label,ref in [("mixed","baseline-reference"),("empty","baseline-empty-reference")]:
            self.assertEqual(audit_old(OUT/label/"audit.jsonl"),audit_old(ROOT/ref/"audit.jsonl"))

    def test_04_exact_one_complete_row_per_native_membership(self):
        rows=self.rows()
        self.assertEqual(canonical(rows),canonical(ORACLE["rows"]))
        for r in rows:self.assertEqual(set(r),set(FIELDS))

    def test_05_bucket_is_membership_not_report_date(self):
        r=self.by_id()
        for vid,allocation in [("A-S0","scheduled"),("R-NEW","scheduled"),("A-CFUTURE","used")]:
            self.assertEqual(r[vid]["allocation"],allocation)
        self.assertLess(r["A-S0"]["visit_date"],self.summary["as_of"])
        self.assertGreater(r["A-CFUTURE"]["visit_date"],self.summary["as_of"])

    def test_06_capacity_boundaries_and_exclusions(self):
        ids=set(self.by_id())
        self.assertTrue({"A-C1","A-C2","A-CFUTURE","A-S0","A-S1","B-SAME-DAY","B-OFFSET"}<=ids)
        self.assertFalse(ids & {"A-OVER","A-OUT","A-CANCEL","A-NO-SHOW","B-BEFORE","B-AFTER",
                               "EV-EXCLUDED","EV-CANCELLED","EX-C","EX-S","PEND-C","PEND-S","DENY-S","AM-OLD-WINDOW"})
        for vid in ["A-C1","A-C2"]:self.assertEqual(self.by_id()[vid]["auth_no"],"EARLY")

    def test_07_exact_amendment_and_distinct_authorization_occurrences(self):
        r=self.by_id()
        self.assertEqual(r["AM-USED"]["auth_evidence"],ORACLE["auth_refs"]["amend-new"])
        self.assertEqual(r["AM-SCHED"]["auth_visits_authorized"],3)
        self.assertNotEqual(r["R-OLD"]["auth_no"],r["R-NEW"]["auth_no"])
        shared=[r[i] for i in ["SHARED-ONE","SHARED-TWO","SHARED-ALT"]]
        self.assertEqual(len({x["auth_evidence"] for x in shared}),3)
        self.assertEqual(len({x["auth_no"] for x in shared}),3)
        self.assertEqual({x["auth_patient_id"] for x in shared},{"P-SAME1","P-SAME2"})
        self.assertEqual({x["auth_payer_id"] for x in shared},{"RULE","ALT"})

    def test_08_duplicate_visit_last_row_and_physical_source_lines(self):
        rows=self.rows();dups=[r for r in rows if r["visit_id"]=="Dup id"]
        self.assertEqual(len(dups),1)
        self.assertEqual(dups[0]["visit_evidence"],ORACLE["visit_refs"]["dup-new"])
        self.assertNotEqual(dups[0]["visit_evidence"],ORACLE["visit_refs"]["dup-old"])
        self.assertEqual(dups[0]["status"],"scheduled")
        self.assertEqual(dups[0]["therapist"],'Dr "Q",\nSecond line')

    def test_09_raw_blank_clinic_and_missing_display_names(self):
        r=self.by_id()
        self.assertEqual(r["Dup id"]["clinic"],"")
        for vid in ["UNKNOWN-C","UNKNOWN-S"]:
            self.assertEqual(r[vid]["clinic"],"");self.assertEqual(r[vid]["patient_name"],"")
            self.assertEqual(r[vid]["payer_name"],"");self.assertEqual(r[vid]["payer_id"],"MISSING")

    def test_10_named_zone_date_and_recorded_type(self):
        r=self.by_id()
        self.assertEqual(r["B-OFFSET"]["visit_date"],"2026-10-08")
        self.assertEqual(r["B-OFFSET"]["auth_start"],"2026-10-08")
        self.assertEqual(r["B-OFFSET"]["auth_end"],"2026-10-08")
        self.assertEqual(r["RE-EVAL-COUNTS"]["visit_type"],"re-eval")
        self.assertTrue(all(x["as_of"]==ORACLE["as_of"] and x["clinic_timezone"]==ORACLE["clinic_timezone"] for x in r.values()))

    def test_11_csv_header_and_complete_semantic_rows(self):
        path=OUT/"mixed/allocated_visits.csv"
        self.assertTrue(path.is_file(),"Native CLI did not write allocated_visits.csv")
        with path.open(encoding="utf-8",newline="") as f:
            reader=csv.DictReader(f);rows=list(reader);self.assertEqual(reader.fieldnames,FIELDS)
        self.assertEqual(canonical(rows),canonical([{k:str(v) for k,v in r.items()} for r in ORACLE["rows"]]))

    def test_12_csv_unicode_delimiter_newline_and_sources(self):
        path=OUT/"mixed/allocated_visits.csv";self.assertTrue(path.is_file())
        with path.open(encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
        r=next(x for x in rows if x["visit_id"]==ORACLE["hostile_visit_id"])
        expected=next(x for x in ORACLE["rows"] if x["visit_id"]==ORACLE["hostile_visit_id"])
        self.assertEqual(r,{k:str(v) for k,v in expected.items()})
        self.assertIn("\n",r["auth_no"]);self.assertIn("\n",r["clinic"])
        self.assertTrue(r["auth_evidence"].startswith("authorizations.csv:row"))
        self.assertTrue(r["visit_evidence"].startswith("schedule.csv:row"))

    def test_13_digest_every_allocation_and_provenance(self):
        parsed=self.frag()
        for row in ORACLE["rows"]:
            matches=[r for r in parsed.rows if normal(row["visit_id"]) in r]
            self.assertEqual(len(matches),1,row["visit_id"])
            for field in ["auth_no","auth_evidence","visit_evidence","visit_date"]:
                self.assertIn(normal(row[field]),matches[0],(row["visit_id"],field))
            self.assertRegex(matches[0].lower(),r"used|scheduled|reserved")
        self.assertGreaterEqual(len(parsed.rows),52)

    def test_14_digest_escapes_hostile_allocated_text(self):
        parsed=self.frag()
        self.assertEqual(parsed.dangerous,[])
        self.assertIn(normal(ORACLE["hostile_visit_id"]),normal(" ".join(parsed.text)))
        self.assertIn('<svg onload="window.__alloc_xss=18">',normal(" ".join(parsed.text)))

    def test_15_existing_digest_tables_unchanged(self):
        original=(ROOT/"baseline-reference/digest.html").read_text()
        tables=re.findall(r"<table\b[\s\S]*?</table>",original)
        self.assertGreaterEqual(len(tables),3)
        for table in tables:self.assertIn(table,self.digest)
        self.assertIn("SYNTHETIC",self.digest)

    def test_16_legacy_missing_and_nonlist_are_unavailable(self):
        for name,value in self.variants.items():
            with self.subTest(variant=name):
                text=normal(" ".join(self.frag(value["html"]).text))
                self.assertRegex(text.lower(),r"run worklist|unavailable|not available|build")
                self.assertNotRegex(text.lower(),r"no (?:allocated )?visits|0 (?:visits|allocations)")
                self.assertTrue(value["unchanged"])

    def test_17_actual_empty_run_has_header_and_empty_projection(self):
        self.assertIn("allocation_review",self.empty_summary)
        self.assertEqual(self.empty_summary["allocation_review"],[])
        path=OUT/"empty/allocated_visits.csv";self.assertTrue(path.is_file())
        with path.open(encoding="utf-8",newline="") as f:
            r=csv.DictReader(f);self.assertEqual(r.fieldnames,FIELDS);self.assertEqual(list(r),[])

    def test_18_empty_digest_distinguishes_completed_empty(self):
        parsed=self.frag(self.empty_digest)
        text=normal(" ".join(parsed.text)).lower()
        self.assertRegex(text,r"no (?:allocated )?visits|no .*allocat|0 (?:visits|allocations)")
        self.assertNotRegex(text,r"run worklist to build|unavailable")
        self.assertEqual(parsed.dangerous,[])

    def test_19_real_http_existing_paths_and_staff_state_preservation(self):
        response=self.responses["/api/summary"];self.assertEqual(response[0],200)
        payload=json.loads(response[1]);self.assertEqual(payload["states"],self.states)
        for path in ["/","/calendar_ui.js"]+["/out/"+x for x in OLD_CSV]+["/out/digest.html"]:
            self.assertEqual(self.responses[path][0],200,path)
        for filename in OLD_CSV:
            self.assertEqual(self.responses["/out/"+filename][1],(ROOT/"baseline-reference"/filename).read_bytes())
        self.assertEqual(self.read_before,self.read_after)
        self.assertTrue(all(r["method"]=="GET" for r in self.http))

    def test_20_real_http_new_projection_and_csv(self):
        payload=json.loads(self.responses["/api/summary"][1])
        self.assertIsInstance(payload.get("allocation_review"),list)
        self.assertEqual(canonical(payload["allocation_review"]),canonical(ORACLE["rows"]))
        response=self.responses["/out/allocated_visits.csv"];self.assertEqual(response[0],200)
        self.assertEqual(response[1],(OUT/"mixed/allocated_visits.csv").read_bytes())

    def test_21_render_is_detached_and_inputs_source_unchanged(self):
        original=copy.deepcopy(self.summary);render_digest(self.summary)
        self.assertEqual(self.summary,original)
        self.assertTrue(all(v["unchanged"] for v in self.variants.values()))
        after={"source":snap(SOURCE),"fixture":snap(ROOT/"fixture"),"empty_fixture":snap(ROOT/"empty-fixture")}
        self.assertEqual(self.before,after)

class Recording(unittest.TextTestResult):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.events=[]
    def addSuccess(self,test):super().addSuccess(test);self.events.append({"test":test.id(),"outcome":"passed"})
    def addFailure(self,test,err):
        super().addFailure(test,err);self.events.append({"test":test.id(),"outcome":"failed","trace":self._exc_info_to_string(err,test)})
    def addError(self,test,err):
        super().addError(test,err);self.events.append({"test":test.id(),"outcome":"error","trace":self._exc_info_to_string(err,test)})
    def addSubTest(self,test,subtest,err):
        super().addSubTest(test,subtest,err)
        if err:self.events.append({"test":test.id(),"subtest":str(subtest),"outcome":"failed" if issubclass(err[0],test.failureException) else "error",
                                   "trace":self._exc_info_to_string(err,test)})

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--source",required=True);p.add_argument("--out",required=True)
    args=p.parse_args();SOURCE=Path(args.source).resolve();OUT=Path(args.out).resolve();OUT.mkdir(parents=True)
    sys.path.insert(0,str(SOURCE/"pt_auth"))
    from ptauth.report import render_digest
    from ptauth.web import App,make_handler
    result=unittest.TextTestRunner(verbosity=2,resultclass=Recording).run(unittest.defaultTestLoader.loadTestsFromTestCase(Receiving))
    save(OUT/"result.json",{"tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),
         "skips":len(result.skipped),"successful":result.wasSuccessful(),"events":result.events,
         "source":str(SOURCE),"python":sys.version,"probe_sha256":sha(Path(__file__).read_bytes()),
         "oracle_sha256":sha((ROOT/"oracle.json").read_bytes())})
    sys.exit(0 if result.wasSuccessful() else 1)
