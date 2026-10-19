from pathlib import Path
import subprocess,json,hashlib
root=Path("/dev/shm/hamon-freight-source-cd1df0f1ee24")
candidate=root/"candidate"; out=root/"evidence"/"module-v1";out.mkdir()
paths=["demos/freight-whatif/site/scenario-record.mjs","demos/freight-whatif/tests/scenario-record.test.mjs","demos/freight-whatif/site/model.mjs","demos/freight-whatif/site/data.mjs"]
def pins():
 result=[]
 for name in paths:
  b=(candidate/name).read_bytes();result.append({"path":name,"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),"git_blob":hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()})
 return result
before=pins();cmd=["/usr/bin/node","--test","demos/freight-whatif/tests/scenario-record.test.mjs"]
r=subprocess.run(cmd,cwd=candidate,capture_output=True)
(out/"stdout.txt").write_bytes(r.stdout);(out/"stderr.txt").write_bytes(r.stderr)
after=pins();assert before==after
receipt={"command":cmd,"exit_code":r.returncode,"node":subprocess.check_output(["/usr/bin/node","--version"]).decode().strip(),"stdout_bytes":len(r.stdout),"stderr_bytes":len(r.stderr),"source":before,"source_unchanged":True}
(out/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
print(r.stdout.decode());print(r.stderr.decode());print(json.dumps(receipt,indent=2));raise SystemExit(r.returncode)
