import contextlib, hashlib, importlib.abc, importlib.util, io, json, runpy, sys
from collections import Counter
bundle = json.loads(sys.stdin.read())
source_files = bundle["files"]
source_pins = {}
modules = {}
for path, entry in source_files.items():
    raw = entry["content"].encode("utf-8")
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + bytes([0]) + raw).hexdigest()
    assert blob == entry["sha"], (path, blob, entry["sha"])
    source_pins[path] = {"git_blob": blob, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    name = path.removeprefix("utility_watch/").removesuffix(".py").replace("/", ".")
    if name.endswith(".__init__"):
        name = name.removesuffix(".__init__")
    modules[name] = (path, entry["content"])
class NativeSourceLoader(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in modules:
            return importlib.util.spec_from_loader(fullname, self, is_package=fullname == "uwatch")
    def create_module(self, spec):
        return None
    def get_code(self, fullname):
        path, code = modules[fullname]
        return compile(code, path, "exec")
    def exec_module(self, module):
        module.__file__ = modules[module.__name__][0]
        exec(self.get_code(module.__name__), module.__dict__)
sys.meta_path.insert(0, NativeSourceLoader())
raw = bundle["worksheet"]["content"].encode("utf-8")
blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + bytes([0]) + raw).hexdigest()
assert blob == bundle["worksheet"]["sha"]
from uwatch.review import _previous
rows = _previous(raw)
states = dict(Counter(row["row_state"] for row in rows))
assert states == {"current": 14, "changed": 1}, states
history = [row for row in rows if row["row_state"] != "current"][0]
assert history["reviewer"] == "Zoë 李"
assert history["review_status"] == "reviewed"
assert "\n" in history["note"] and '"credit next month"' in history["note"]
current = next(row for row in rows if row["row_state"] == "current" and row["finding_id"] == history["finding_id"])
assert current["review_status"] == "open" and not current["reviewer"] and not current["note"]
stdout, stderr = io.StringIO(), io.StringIO()
sys.argv = ["uwatch", "review-report", "--worksheet", "review-3.csv", "--out", "review.html"]
with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
    try:
        runpy.run_module("uwatch", run_name="__main__")
    except SystemExit as exc:
        rc = exc.code
    else:
        rc = 0
assert rc == 2 and "invalid choice: 'review-report'" in stderr.getvalue(), (rc, stderr.getvalue())
assert stdout.getvalue() == ""
result = {
    "result": "MISSING_CAPABILITY_CONFIRMED",
    "source_ref": bundle["source_ref"],
    "method": "Exact current modules loaded from verified source bytes in one actual Python child; native package __main__ and argparse executed. Captured accepted PR22 worksheet validated by unchanged native _previous. No fresh generate/run/reconcile replay or filesystem input/output is claimed in this disk-full probe.",
    "source_pins": source_pins,
    "worksheet": {"git_blob": blob, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "native_row_states": states},
    "retained_history": {key: history[key] for key in ("row_state", "review_status", "reviewer", "note", "finding_key", "finding_id", "evidence_version")},
    "current_same_finding": {key: current[key] for key in ("row_state", "review_status", "reviewer", "note", "finding_key", "finding_id", "evidence_version")},
    "cli": {"argv": sys.argv, "rc": rc, "stdout": stdout.getvalue(), "stderr": stderr.getvalue()},
    "filesystem_and_external_effects": "none; source and captured CSV were passed through stdin and no uwatch writing command ran",
    "python": sys.version,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
