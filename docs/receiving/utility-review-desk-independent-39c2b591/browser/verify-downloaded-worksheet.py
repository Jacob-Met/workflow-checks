"""Independent complete-CSV verifier; import only the frozen original worksheet loader."""
from __future__ import annotations
import argparse,csv,hashlib,io,json,os,pathlib,subprocess,sys,traceback
sys.dont_write_bytecode=True
ap=argparse.ArgumentParser()
ap.add_argument("--fixture",type=pathlib.Path,required=True)
ap.add_argument("--baseline-source",type=pathlib.Path,required=True)
ap.add_argument("--download",type=pathlib.Path,required=True)
ap.add_argument("--expected-edits",type=pathlib.Path,required=True)
ap.add_argument("--output",type=pathlib.Path,required=True)
ap.add_argument("--reconcile-out",type=pathlib.Path)
args=ap.parse_args()
fixture=args.fixture.resolve();package=args.baseline_source.resolve()/"utility_watch"
sys.path.insert(0,str(package))
from uwatch import review
def digest(raw):return hashlib.sha256(raw).hexdigest()
def read_rows(raw):
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig"),newline=""),strict=True)
    assert reader.fieldnames and len(reader.fieldnames)==len(set(reader.fieldnames))
    assert set(reader.fieldnames)==set(review.COLUMNS),"Complete original worksheet columns required"
    rows=list(reader)
    assert all(None not in row and all(v is not None for v in row.values()) for row in rows)
    ids=[row["row_id"] for row in rows]
    assert len(ids)==len(set(ids)),"Row IDs must be unique, including exactly one manifest"
    return {row["row_id"]:row for row in rows}
checks=[];result={}
try:
    oracle=json.loads((fixture/"FIXTURE_ORACLE.json").read_text())
    source_meta=json.loads((fixture.parent/"BASELINE_SOURCE.json").read_text())
    module_hashes={name:digest((package/name).read_bytes()) for name in ("uwatch/review.py","uwatch/engine.py")}
    for name,value in module_hashes.items():
        expected=next(x["sha256"] for x in source_meta["leaves"] if x["path"]=="utility_watch/"+name)
        assert value==expected,"Original native loader/checker bytes changed"
    original=(fixture/"desk-current-with-history.csv").read_bytes()
    assert digest(original)==oracle["worksheet_sha256"]
    expected={row["row_id"]:dict(row) for row in oracle["all_rows"]}
    edits=json.loads(args.expected_edits.read_text())
    edited_ids=set()
    for edit in edits:
        assert set(edit)=={"row_id",*review.EDITABLE}
        key=edit["row_id"]
        assert key not in edited_ids and key in expected and expected[key]["row_state"]=="current"
        assert all(isinstance(edit[column],str) for column in review.EDITABLE)
        edited_ids.add(key)
        for column in review.EDITABLE:expected[key][column]=edit[column]
    raw=args.download.read_bytes();actual=read_rows(raw)
    assert set(actual)==set(expected),"A complete download must retain every current, historical and manifest row"
    checks.append("Every original row ID and every original column is present exactly once")
    for key,row in actual.items():
        assert row==expected[key],f"Complete row fields disagree for {key}: account {expected[key]['account_no']}, state {expected[key]['row_state']}"
    checks.append("Only the intended current row-ID annotations differ; protected fields, history and manifest are exact")
    decoded=review._previous(raw)
    assert len(decoded)==len(oracle["current"])+len(oracle["history"])
    checks.append("The original frozen native worksheet loader admits the actual browser-downloaded bytes")
    native=None
    if args.reconcile_out:
        assert not args.reconcile_out.exists(),"Reconciliation output must be new"
        protected=[p for folder in (fixture/"data-current",fixture/"report-current") for p in folder.iterdir() if p.is_file()]
        before={str(p):digest(p.read_bytes()) for p in protected}
        command=[sys.executable,"-B","-m","uwatch","review","--data",str(fixture/"data-current"),
         "--report",str(fixture/"report-current/summary.json"),"--previous",str(args.download),
         "--out",str(args.reconcile_out)]
        env=os.environ.copy();env["PYTHONDONTWRITEBYTECODE"]="1"
        run=subprocess.run(command,cwd=package,env=env,capture_output=True,timeout=30)
        native={"command":command,"cwd":str(package),"exit_code":run.returncode,
         "stdout":run.stdout.decode(),"stderr":run.stderr.decode()}
        assert run.returncode==0,native
        assert "annotations do not change payment eligibility" in native["stdout"]
        assert read_rows(args.reconcile_out.read_bytes())==expected
        assert {str(p):digest(p.read_bytes()) for p in protected}==before
        assert args.download.read_bytes()==raw
        checks.append("One actual original review reconciliation preserves the exact edited/current/history fields and leaves source/report/download bytes unchanged")
    assert (fixture/"desk-current-with-history.csv").read_bytes()==original
    assert {name:digest((package/name).read_bytes()) for name in module_hashes}==module_hashes
    result={"schema":"hamon.utility_desk.actual_csv_verification.v1","status":"pass","checks":checks,
     "download":str(args.download),"download_bytes":len(raw),"download_sha256":digest(raw),
     "original_fixture_sha256":digest(original),"original_native_module_sha256":module_hashes,
     "current_rows":len(oracle["current"]),"history_rows":len(oracle["history"]),"manifest_rows":1,
     "expected_current_edits":edits,"native_reconciliation":native,"source_fixture_unchanged":True}
except Exception as failure:
    result={"schema":"hamon.utility_desk.actual_csv_verification.v1","status":"fail","checks":checks,
     "download":str(args.download),"error":str(failure),"traceback":traceback.format_exc()}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    raise
args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({k:v for k,v in result.items() if k not in ("expected_current_edits","native_reconciliation")},ensure_ascii=False))
