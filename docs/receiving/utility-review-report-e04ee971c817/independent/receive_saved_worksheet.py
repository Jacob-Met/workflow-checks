"""Independent actual-CLI receiving for the saved worksheet HTML consumer."""
from __future__ import annotations
import argparse
import base64
import collections
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
from html.parser import HTMLParser

HOOK = r'''
import base64,json,os,runpy,sys
from pathlib import Path
config=json.loads(sys.argv[1])
worksheet=Path(config["worksheet"])
out=Path(config["out"])
receipt={"input_reads":0,"publication_link_calls":0,"simulated_external_saves":0,"competing_creates":0}
original_read=Path.read_bytes
original_link=os.link
def read_once(self):
    raw=original_read(self)
    if self == worksheet:
        receipt["input_reads"] += 1
        if config["mode"] == "later-save":
            worksheet.write_bytes(base64.b64decode(config["replacement"]))
            receipt["simulated_external_saves"] += 1
    return raw
def publish(source,destination,*args,**kwargs):
    receipt["publication_link_calls"] += 1
    if config["mode"] == "competing-create" and Path(destination) == out:
        fd=os.open(out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as stream:
            stream.write(base64.b64decode(config["sentinel"]))
        receipt["competing_creates"] += 1
    return original_link(source,destination,*args,**kwargs)
Path.read_bytes=read_once
os.link=publish
sys.argv=["uwatch","review-report","--worksheet",str(worksheet),"--out",str(out)]
code=0
try:
    runpy.run_module("uwatch",run_name="__main__")
except SystemExit as exc:
    code=exc.code
finally:
    Path(config["receipt"]).write_text(json.dumps(receipt,sort_keys=True)+"\n")
raise SystemExit(code)
'''

class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.section = None
        self.article = None
        self.articles = []
        self.tags = []
        self.links = []
        self.text = []
        self.field = None
        self.label = None
        self.parts = []
        self.feed(text)
        self.close()
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs); self.tags.append(tag)
        self.links.extend(v for k,v in attrs.items() if k in ("src", "href"))
        if tag == "section": self.section = attrs.get("id")
        if tag == "article":
            self.article = {"id":attrs.get("id"),"state":attrs.get("data-row-state"),
                            "section":self.section,"fields":{},"text":[]}
        if self.article and tag in ("dt", "dd"):
            self.field=tag; self.parts=[]
    def handle_data(self, data):
        self.text.append(data)
        if self.article:
            self.article["text"].append(data)
            if self.field: self.parts.append(data)
    def handle_endtag(self, tag):
        if self.article and tag == self.field:
            if tag == "dt": self.label="".join(self.parts)
            else: self.article["fields"][self.label]="".join(self.parts)
            self.field=None; self.parts=[]
        if tag == "article":
            self.articles.append(self.article); self.article=None
        if tag == "section": self.section=None


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(raw):
    return {"git_blob":hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest(),
            "sha256":digest(raw),"bytes":len(raw)}


def csv_bytes(rows, fields, bom=False):
    stream=io.StringIO(newline="")
    writer=csv.DictWriter(stream,fieldnames=fields,lineterminator="\r\n")
    writer.writeheader(); writer.writerows(rows)
    return (b"\xef\xbb\xbf" if bom else b"")+stream.getvalue().encode("utf-8")


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--author-freeze",type=Path,required=True)
    ap.add_argument("--native-tree",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    author=a.author_freeze.resolve()
    base=author/"baseline"/"utility_watch"
    candidate=author/"candidate"/"utility_watch"
    pins=json.loads((author/"candidate-pins.json").read_text())
    tree=json.loads(a.native_tree.read_text())
    checks=[]; cases=[]; children=[]
    def check(name, passed):
        checks.append({"name":name,"pass":bool(passed)})
        if not passed: raise AssertionError(name)
    native={e["path"]:e for e in tree["tree"] if e["type"]!="tree"}
    check("complete primary native tree pin",tree["sha"]==pins["source_tree"] and not tree.get("truncated"))
    check("frozen author manifest identity",pin((author/"candidate-pins.json").read_bytes())["git_blob"]=="4dc7f45a8f8cd790bee3538dbcdd050bf910932e")
    before={}
    for group in ("candidate_files","native_unchanged_files"):
        for rel, expected in pins[group].items():
            raw=(author/"candidate"/rel).read_bytes()
            check("frozen candidate pin: "+rel,pin(raw)==expected)
            before[rel]=pin(raw)
            if group=="native_unchanged_files":
                check("native support bound to primary tree: "+rel,native[rel]["sha"]==expected["git_blob"] and native[rel]["mode"]=="100644")
    baseline_cli=(base/"uwatch/cli.py").read_bytes()
    check("baseline CLI bound to primary tree",pin(baseline_cli)["git_blob"]==native["utility_watch/uwatch/cli.py"]["sha"])
    original=(candidate/"uwatch/cli.py").read_bytes()
    stripped=original.replace(b"<generate|run|review|review-report>",b"<generate|run|review>",1)
    start=stripped.index(b'    review_report = sub.add_parser("review-report"')
    end=stripped.index(b"    a = ap.parse_args(argv)",start)
    stripped=stripped[:start]+stripped[end:]
    start=stripped.index(b'    if a.cmd == "review-report":')
    end=stripped.index(b'    if a.cmd == "generate":',start)
    stripped=stripped[:start]+stripped[end:]
    check("remove only new parser/dispatch and doc label recovers exact native CRLF CLI",stripped==baseline_cli)
    check("native CRLF CLI retained",b"\r\n" in original and original.count(b"\n")==original.count(b"\r\n"))

    fixture=author/"evidence/native-review-with-history.csv"
    native_raw=fixture.read_bytes()
    check("actual captured native worksheet pin",digest(native_raw)=="d9305edacc7e94a7ac076809a9e0c7cab1ce0ba557616be9afd8a86b8b783ddd")
    parsed=list(csv.DictReader(io.StringIO(native_raw.decode("utf-8-sig"),newline="")))
    fields=list(parsed[0])
    working=[dict(r) for r in parsed]
    prior=next(r for r in working if r["row_state"]=="changed")
    current=next(r for r in working if r["row_state"]=="current" and r["finding_id"]==prior["finding_id"])
    prior.update(review_status="reviewed",reviewer='Priör <reviewer> & 李\r\nSecond line',
                 note='Unique prior evidence only.\r\n<script src="https://invalid.example/x"></script> & "quoted"')
    current.update(review_status="  in_progress  ",reviewer="Current operator",note="Current evidence note remains separate.")
    manifest=next(r for r in working if r["row_state"]=="manifest")
    records=list(reversed([r for r in working if r["row_state"]!="manifest"]))
    reordered=records[:7]+[manifest]+records[7:]
    variant=csv_bytes(reordered,list(reversed(fields)),bom=True)
    statuses=collections.Counter(r["review_status"].strip() for r in working if r["row_state"]=="current")
    summaries={"native_input":pin(native_raw),"reordered_bom_input":pin(variant),"prior_row_id":prior["row_id"],"current_row_id":current["row_id"]}

    def invoke(package, worksheet, out, mode=None, replacement=None, sentinel=None):
        env=os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"]="1"
        env["PYTHONPATH"]=str(package)
        env["PYTHONUTF8"]="1"
        args=[sys.executable,"-B","-m","uwatch","review-report","--worksheet",str(worksheet),"--out",str(out)]
        receipt=None
        if mode:
            receipt=worksheet.parent/(mode+"-hook.json")
            config={"mode":mode,"worksheet":str(worksheet),"out":str(out),"receipt":str(receipt),
                    "replacement":base64.b64encode(replacement or b"").decode(),
                    "sentinel":base64.b64encode(sentinel or b"").decode()}
            args=[sys.executable,"-B","-c",HOOK,json.dumps(config)]
        run=subprocess.run(args,cwd=package,env=env,text=True,capture_output=True,timeout=30)
        child={"mode":mode or "direct package CLI","package":"baseline" if package==base else "candidate",
               "returncode":run.returncode,"stdout":run.stdout,"stderr":run.stderr}
        if receipt and receipt.exists(): child["hook"]=json.loads(receipt.read_text())
        children.append(child)
        return run, child.get("hook")

    with tempfile.TemporaryDirectory(prefix="utility-independent-",dir=a.out.parent) as scratch:
        scratch=Path(scratch)
        def case(name, fn):
            folder=scratch/name;folder.mkdir()
            first=len(checks)
            try:
                fn(folder)
                cases.append({"name":name,"result":"PASS","conditions":len(checks)-first})
            except Exception as exc:
                cases.append({"name":name,"result":"FAIL","conditions":len(checks)-first,
                              "error":str(exc),"traceback":traceback.format_exc()})

        def saved_attribution(folder):
            worksheet=folder/'révision <Q&A>.csv';worksheet.write_bytes(variant)
            old_out=folder/"baseline.html"
            old,_=invoke(base,worksheet,old_out)
            check("before-image actual CLI refuses missing saved-view capability",old.returncode==2 and not old_out.exists() and "invalid choice" in old.stderr)
            out=folder/"saved.html";run,_=invoke(candidate,worksheet,out)
            check("actual native CLI accepts BOM/reordered columns and mid-file manifest",run.returncode==0 and out.is_file())
            raw=out.read_bytes();page=Page(raw.decode("utf-8"));text="".join(page.text)
            articles={article["id"]:article for article in page.articles}
            expected_records=[r for r in working if r["row_state"]!="manifest"]
            check("all saved current/history row identities appear once",len(page.articles)==len(expected_records) and set(articles)=={"row-"+r["row_id"] for r in expected_records})
            check("every record stays in its actual current/history section",all(articles["row-"+r["row_id"]]["section"]==("current" if r["row_state"]=="current" else "history") and articles["row-"+r["row_id"]]["state"]==r["row_state"] for r in expected_records))
            saved_prior=articles["row-"+prior["row_id"]]["fields"]
            saved_current=articles["row-"+current["row_id"]]["fields"]
            check("prior Unicode/HTML-like quoted CRLF annotations remain exact text",saved_prior["Reviewer"]==prior["reviewer"] and saved_prior["Note"]==prior["note"])
            check("current finding keeps its own status/reviewer/note",saved_current["Review status"]=="In progress" and saved_current["Reviewer"]==current["reviewer"] and saved_current["Note"]==current["note"])
            check("prior reviewed annotation is not counted as current reviewed",all(label+": "+str(statuses[status]) in text for status,label in [("open","Open"),("in_progress","In progress"),("reviewed","Reviewed")]))
            check("protected identity/evidence version matches each saved row",all(articles["row-"+r["row_id"]]["fields"]["Finding ID"]==r["finding_id"] and articles["row-"+r["row_id"]]["fields"]["Evidence version"]==r["evidence_version"] and articles["row-"+r["row_id"]]["fields"]["Protected record SHA256"]==r["record_sha256"] for r in expected_records))
            check("raw BOM/reordered bytes identity appears in page and CLI",digest(variant) in text and digest(variant) in run.stdout)
            check("escaped worksheet basename remains visible",worksheet.name in text)
            check("HTML-like annotation creates no active element or external resource",not set(page.tags).intersection({"script","iframe","object","img","form"}) and page.links==["#current","#history"] and "url(" not in raw.decode().lower() and "@import" not in raw.decode().lower())
            check("saved worksheet remains byte-identical",worksheet.read_bytes()==variant)
            check("successful publication leaves only the intended HTML",sorted(p.name for p in folder.iterdir())==sorted([worksheet.name,out.name]))
            summaries["saved_html"]=pin(raw)

        def saved_during_read(folder):
            worksheet=folder/"during-save.csv";worksheet.write_bytes(native_raw)
            rows=[dict(r) for r in parsed]
            changed=next(r for r in rows if r["row_state"]=="changed")
            changed["reviewer"]="Later editor";changed["note"]="LATER SAVE must not enter the already-read view"
            later=csv_bytes(rows,fields)
            out=folder/"earlier-snapshot.html"
            run,hook=invoke(candidate,worksheet,out,mode="later-save",replacement=later)
            check("one-read race still succeeds",run.returncode==0 and out.is_file())
            check("exactly one input read and one simulated external save",hook["input_reads"]==1 and hook["simulated_external_saves"]==1)
            page=Page(out.read_text());text="".join(page.text)
            check("report and CLI bind the original exact bytes, not a later save",digest(native_raw) in text and digest(native_raw) in run.stdout and digest(later) not in text and "LATER SAVE must not enter" not in text)
            check("original saved reviewer/note remains in the completed snapshot",all(value in text for value in [next(r for r in parsed if r["row_state"]=="changed")["reviewer"],next(r for r in parsed if r["row_state"]=="changed")["note"]]))
            check("later fixture save remains intact on disk",worksheet.read_bytes()==later)
            check("only one exclusive publication was attempted",hook["publication_link_calls"]==1)

        def exclusive_publication(folder):
            worksheet=folder/"saved.csv";worksheet.write_bytes(native_raw)
            out=folder/"competing.html";sentinel=b"COMPETING CREATOR owns this destination\\x00\\xff"
            run,hook=invoke(candidate,worksheet,out,mode="competing-create",sentinel=sentinel)
            check("actual exclusive link refuses a real late competing creator",run.returncode==2 and hook["publication_link_calls"]==1 and hook["competing_creates"]==1)
            check("late creator bytes are not overwritten by partial or completed HTML",out.read_bytes()==sentinel)
            check("refused publication reports no success",not run.stdout and "review report error" in run.stderr)
            check("late collision cleans its temporary output and preserves input",not list(folder.glob(".uwatch-review-report-*")) and worksheet.read_bytes()==native_raw)
            alias=folder/"input-hardlink.html";os.link(worksheet,alias)
            alias_inode=alias.stat().st_ino
            alias_run,_=invoke(candidate,worksheet,alias)
            check("input hardlink destination is refused through actual CLI",alias_run.returncode==2 and not alias_run.stdout)
            check("input hardlink identity and bytes stay unchanged",alias.stat().st_ino==alias_inode==worksheet.stat().st_ino and alias.read_bytes()==native_raw and worksheet.read_bytes()==native_raw)
            check("alias refusal leaves no temporary sidefile",not list(folder.glob(".uwatch-review-report-*")))

        def late_invalid_row(folder):
            rows=[dict(r) for r in parsed]
            late=next(r for r in rows if r["row_state"]=="changed")
            late["review_status"]="paid"
            invalid=csv_bytes(rows,fields)
            worksheet=folder/"late-invalid.csv";worksheet.write_bytes(invalid)
            previous=folder/"earlier-complete.html";previous.write_bytes(b"PREEXISTING COMPLETE REVIEW")
            out=folder/"new.html";before_names=sorted(p.name for p in folder.iterdir())
            run,_=invoke(candidate,worksheet,out)
            check("invalid late history status is refused",run.returncode==2 and not run.stdout)
            check("no partial current-only report or temporary output is published",not out.exists() and not list(folder.glob(".uwatch-review-report-*")) and sorted(p.name for p in folder.iterdir())==before_names)
            check("invalid worksheet and preexisting output are preserved exactly",worksheet.read_bytes()==invalid and previous.read_bytes()==b"PREEXISTING COMPLETE REVIEW")

        case("saved_attribution",saved_attribution)
        case("one_read_snapshot",saved_during_read)
        case("exclusive_publication",exclusive_publication)
        case("late_invalid_history",late_invalid_row)

    for rel,expected in before.items():
        check("author source/support unchanged after receiving: "+rel,pin((author/"candidate"/rel).read_bytes())==expected)
    check("captured native fixture unchanged",fixture.read_bytes()==native_raw)
    report={"result":"PASS" if all(c["result"]=="PASS" for c in cases) else "FAIL",
            "python":sys.version,"conditions":len(checks),"failed_conditions":sum(not c["pass"] for c in checks),
            "actual_cli_children":len(children),"families":cases,"source_pins":before,
            "fixtures":summaries,"hook_sha256":digest(HOOK.encode()),"children":children,"checks":checks,
            "limits":["No author test or browser/print suite was imported or rerun.",
                      "The snapshot and collision children execute the actual module entry with explicitly described local race hooks.",
                      "Source and captured worksheet are frozen inputs. Temporary case files are disposable and removed.",
                      "This receives the frozen HTML/CLI source. Accepted current-engine composition is separately qualified by the author."]}
    a.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:report[k] for k in ("result","conditions","failed_conditions","actual_cli_children","families")},indent=2))
    return 0 if report["result"]=="PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
