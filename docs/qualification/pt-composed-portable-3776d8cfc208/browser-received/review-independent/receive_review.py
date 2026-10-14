"""Inspect the actual downloaded PT review ZIP against accepted external bytes."""
from pathlib import Path
import csv
import hashlib
from html.parser import HTMLParser
import io
import json
import stat
import struct
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ZIP = ROOT / "pt-ui-delivery/actual-drive.zip"
PINS = {
    "OPEN_REVIEW.html": "c3938f462743e105653fede171e7de8a72444292",
    "START_HERE.md": "571fb30d08b5da343827fe055fdea37302c1ea4f",
    "uncovered-narrow.png": "b89ba0b65e193ae12ed0f9f07fe0bfec6ae8ded9",
    "uncovered_visits.csv": "e750ad287278f3857be3684c8009d0afe7dd2a35",
    "worklist-desktop.png": "4b1a9b728ac0a299e69e2c2616ba4b47622b785f",
}
RECEIPTS = {"receiving-first.json": ROOT / "pt-ui-independent/first-native/received-course/receiving.json",
            "receiving-final.json": ROOT / "pt-ui-independent/final-native/received-course/receiving.json"}
ORACLE = ROOT / "pt-ui-independent/expected.json"

def identity(path):
    b = path.read_bytes()
    return {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(),
            "git_blob": git(b), "mtime_ns": str(path.stat().st_mtime_ns)}

def git(b):
    return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.sources=[]; self.scripts=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag == "script": self.scripts.append(attrs)
        if "href" in attrs: self.links.append((tag,attrs["href"]))
        if "src" in attrs: self.sources.append((tag,attrs["src"]))

def main():
    watched = [ZIP, ORACLE, *RECEIPTS.values(), Path(__file__).resolve()]
    before = {str(p):identity(p) for p in watched}
    receipt={"schema":"pt.review-zip.independent/1", "scope":"Retrospective byte/layout receiving of one actual Drive download against previously accepted notes, native captures/receipts and frozen visit IDs; no extraction, browser, server or product execution.", "checks":[], "before":before}
    def check(name,condition):
        receipt["checks"].append({"name":name,"passed":bool(condition)})
        if not condition: raise ValueError(name)
    try:
        check("exact_downloaded_zip", before[str(ZIP)]["bytes"]==215029 and before[str(ZIP)]["sha256"]=="ce91c36b2577a1d83e90730216aa09081fa3c4ba9c2089ecee855263ff7c5223" and before[str(ZIP)]["git_blob"]=="8128e03eb534fec539d432613091c6fd32355e95")
        check("frozen_ui_oracle",before[str(ORACLE)]["git_blob"]=="a072989cfab2f17e7c6b805a22e084b0c46ef703")
        with zipfile.ZipFile(ZIP) as archive:
            names=sorted([*PINS,*RECEIPTS,"MANIFEST.json"])
            check("exact_eight_sorted_members", archive.namelist()==names)
            check("all_crcs_valid",archive.testzip() is None)
            check("regular_fixed_zip_metadata",all(stat.S_ISREG(i.external_attr>>16) and (i.external_attr>>16)&0o777==0o644 and i.date_time==(1980,1,1,0,0,0) and i.compress_type==zipfile.ZIP_DEFLATED for i in archive.infolist()))
            bodies={n:archive.read(n) for n in names}
        for name,pin in PINS.items(): check("accepted_external_identity_"+name,git(bodies[name])==pin)
        for name,path in RECEIPTS.items(): check("original_native_receipt_"+name,bodies[name]==path.read_bytes())
        manifest=json.loads(bodies["MANIFEST.json"])
        check("manifest_exact_seven_payloads",manifest=={"schema":"hamon.delivery-zip/1","files":[{"path":n,"bytes":len(bodies[n]),"sha256":hashlib.sha256(bodies[n]).hexdigest()} for n in names if n!="MANIFEST.json"]})
        parser=Links();parser.feed(bodies["OPEN_REVIEW.html"].decode())
        check("no_script_or_automatic_external_resource",not parser.scripts and set(parser.sources)=={("img","worklist-desktop.png"),("img","uncovered-narrow.png")} and b"url(" not in bodies["OPEN_REVIEW.html"])
        check("relative_links_present_and_online_links_explicit",all((tag=="a" and url in ("https://drive.google.com/file/d/1uuBHZynhfWRfFyLYoAi9GrZvIFbtf8Ti/view","https://github.com/Jacob-Met/workflow-checks/tree/69f3c8e0577b579ee36256da0a075fccb201af8f")) if url.startswith("https:") else url in names for tag,url in parser.links))
        for n,size in (("worklist-desktop.png",(1280,900)),("uncovered-narrow.png",(390,844))): check("original_viewport_dimensions_"+n,bodies[n][:8]==b"\x89PNG\r\n\x1a\n" and struct.unpack(">II",bodies[n][16:24])==size)
        rows=list(csv.DictReader(io.StringIO(bodies["uncovered_visits.csv"].decode())))
        oracle=json.loads(ORACLE.read_bytes())
        check("all_196_frozen_visit_ids",len(rows)==196 and [r["visit_id"] for r in rows]==oracle["all_uncovered_ids"])
        first=json.loads(bodies["receiving-first.json"]);final=json.loads(bodies["receiving-final.json"])
        check("original_failure_preserved",first["passed"] is False and len(first["checks"])==17 and sum(x["passed"] for x in first["checks"])==16 and [x["name"] for x in first["checks"] if not x["passed"]]==["onlyOwnLoopbackGETRequests"])
        check("separate_successor_21_pass",final["passed"] is True and len(final["checks"])==21 and all(x["passed"] for x in final["checks"]))
    except Exception as exc:
        receipt["error"]={"type":type(exc).__name__,"message":str(exc)}
    finally:
        receipt["after"]={str(p):identity(p) for p in watched}
        receipt["checks"].append({"name":"five_input_byte_and_native_mtime_records_unchanged","passed":receipt["after"]==before})
        receipt["passed"]="error" not in receipt and all(x["passed"] for x in receipt["checks"])
        with (HERE/"receiving.json").open("x") as f: json.dump(receipt,f,indent=2); f.write("\n")
    print(json.dumps({"passed":receipt["passed"],"checks":len(receipt["checks"]),"error":receipt.get("error")}))
    return 0 if receipt["passed"] else 1

if __name__ == "__main__": raise SystemExit(main())
