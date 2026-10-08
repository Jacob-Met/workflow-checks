from pathlib import Path
import hashlib,json,subprocess,sys,platform
root=Path("/dev/shm/hamon-freight-source-cd1df0f1ee24")
candidate=root/"candidate"
evidence=root/"evidence"/"delivery-v1"
evidence.mkdir(exist_ok=False)
def pin(path):
 b=path.read_bytes()
 return {"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),"git_blob":hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()}
license_pin=pin(candidate/"LICENSE")
assert license_pin["git_blob"]=="edb188254288b40f2895833e3647b7e0be34c962",license_pin
demo=candidate/"demos/freight-whatif"
paths=sorted([p for p in (demo/"site").iterdir() if p.is_file()])+[demo/"tools/install.py",demo/"tools/package.py",demo/"tools/serve.py",demo/"tests/install.test.py",candidate/"LICENSE"]
before={str(p.relative_to(candidate)):pin(p) for p in paths}
steps={}
commands=[
("installer",[sys.executable,str(demo/"tests/install.test.py"),"--work-root",str(evidence/"install-work"),"--output",str(evidence/"installer-receipt.json")]),
("packager",[sys.executable,str(demo/"tools/package.py"),"--output",str(evidence/"freight-whatif.zip"),"--receipt",str(evidence/"package-receipt.json")])]
for name,cmd in commands:
 p=subprocess.run(cmd,cwd=candidate,capture_output=True,timeout=30)
 (evidence/(name+".stdout.txt")).write_bytes(p.stdout)
 (evidence/(name+".stderr.txt")).write_bytes(p.stderr)
 steps[name]={"command":cmd,"exit_code":p.returncode,"stdout":pin(evidence/(name+".stdout.txt")),"stderr":pin(evidence/(name+".stderr.txt"))}
after={str(p.relative_to(candidate)):pin(p) for p in paths}
receipt={"schema":"hamon.freight-delivery-receipt.v1","python":platform.python_version(),"before":before,"after":after,"source_unchanged":before==after,"steps":steps,"scope":"Existing install/verify/rollback checks plus actual deterministic six-runtime-file ZIP packaging; no browser, server or repeated model suite."}
(evidence/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps({"source_unchanged":before==after,"steps":steps,"receipt":pin(evidence/"receipt.json")}))
sys.exit(0 if before==after and all(x["exit_code"]==0 for x in steps.values()) else 1)
