"""Owned loopback fixture receiver using unchanged ptauth.web.make_handler."""
from __future__ import annotations
import argparse, hashlib, json, shutil, signal, sys, threading
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def snap(p):return {str(x.relative_to(p)):sha(x.read_bytes()) for x in sorted(p.rglob("*")) if x.is_file()}
p=argparse.ArgumentParser();p.add_argument("--source",required=True);p.add_argument("--native",required=True);p.add_argument("--out",required=True)
a=p.parse_args();source=Path(a.source).resolve();native=Path(a.native).resolve();out=Path(a.out).resolve();out.mkdir(parents=True)
sys.path.insert(0,str(source/"pt_auth"))
from ptauth.report import render_digest
from ptauth.web import App,make_handler
oracle=json.loads((ROOT/"oracle.json").read_text())
servers=[];threads=[];records=[];origins={};variants={}
for name in ["modern","missing","nonlist","empty"]:
    report=out/name
    shutil.copytree(native/("empty" if name=="empty" else "mixed"),report)
    summary=json.loads((report/"summary.json").read_text())
    if name=="missing":summary.pop("allocation_review",None)
    if name=="nonlist":summary["allocation_review"]={"legacy":"not a completed allocation list"}
    if name in {"missing","nonlist"}:
        save(report/"summary.json",summary)
        (report/"digest.html").write_text(render_digest(summary),encoding="utf-8")
        (report/"allocated_visits.csv").unlink(missing_ok=True)
    app=App(ROOT/("empty-fixture" if name=="empty" else "fixture"),report,clinic_timezone=oracle["clinic_timezone"])
    handler=make_handler(app)
    def recorded(base,variant):
        class H(base):
            def _send(self,code,body,ctype="application/json"):
                records.append({"variant":variant,"method":self.command,"path":self.path,
                                "status":code,"bytes":len(body),"sha256":sha(body),"content_type":ctype})
                return super()._send(code,body,ctype)
        return H
    server=ThreadingHTTPServer(("127.0.0.1",0),recorded(handler,name))
    servers.append(server);origins[name]=f"http://127.0.0.1:{server.server_port}"
    t=threading.Thread(target=server.serve_forever,daemon=True);t.start();threads.append(t)
    variants[name]={"report":str(report),"before":snap(report)}
source_before=snap(source);fixture_before=snap(ROOT/"fixture");empty_before=snap(ROOT/"empty-fixture")
stop=threading.Event()
def stopped(*args):stop.set()
signal.signal(signal.SIGTERM,stopped);signal.signal(signal.SIGINT,stopped)
save(out/"server-ready.json",{"origins":origins,"source":str(source),"source_before":source_before,"variants":variants,
                            "python":sys.version,"server_probe_sha256":sha(Path(__file__).read_bytes())})
print(json.dumps({"ready":True,"origins":origins}),flush=True)
stop.wait()
for s in servers:s.shutdown();s.server_close()
for t in threads:t.join()
for name,v in variants.items():v["after"]=snap(Path(v["report"]));v["unchanged"]=v["before"]==v["after"]
receipt={"origins":origins,"records":records,"variants":variants,
         "source_before":source_before,"source_after":snap(source),"source_unchanged":source_before==snap(source),
         "fixture_unchanged":fixture_before==snap(ROOT/"fixture") and empty_before==snap(ROOT/"empty-fixture"),
         "all_reports_unchanged":all(v["unchanged"] for v in variants.values()),"stopped_cleanly":True}
save(out/"server-receipt.json",receipt)
print(json.dumps({"stopped":True,"responses":len(records),"all_reports_unchanged":receipt["all_reports_unchanged"]}),flush=True)
