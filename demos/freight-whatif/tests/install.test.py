"""Exercise the actual installer, rollback refusal and final installed readback."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

DEMO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("freight_install", DEMO / "tools/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
parser = argparse.ArgumentParser()
parser.add_argument("--work-root", type=Path, required=True, help="New exclusively owned directory")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
work = args.work_root.absolute()
work.mkdir()
sibling = work / "unrelated-control.txt"
sibling.write_bytes(b"Owned control: installation must leave this sibling byte-identical.\n")
sibling_hash = installer.digest(sibling)
target = work / "installed-site"
checks = []
source_pins = installer.inventory(DEMO / "site")
first = installer.install(DEMO / "site", target)
assert first["files"] == source_pins
assert installer.verify(target)["files"] == source_pins
checks.append("new installation and every file read back exact")

try:
    installer.install(DEMO / "site", target)
except FileExistsError:
    pass
else:
    raise AssertionError("Existing installation was overwritten")
assert installer.verify(target)["files"] == source_pins
checks.append("existing target refused without changing bytes")

index = target / "index.html"
original = index.read_bytes()
index.write_bytes(original + b"\n<!-- owned receiver edit -->\n")
try:
    installer.rollback(target)
except ValueError:
    pass
else:
    raise AssertionError("Rollback removed an edited installation")
assert index.read_bytes() == original + b"\n<!-- owned receiver edit -->\n"
assert installer.digest(sibling) == sibling_hash
checks.append("edited install refused by rollback; edit and sibling retained")
index.write_bytes(original)  # Restore only the receiver's own deliberate edit.

extra = target / "receiver-extra.txt"
extra.write_bytes(b"Receiver's own additional file.")
try:
    installer.rollback(target)
except ValueError:
    pass
else:
    raise AssertionError("Rollback removed unexpected content")
assert extra.read_bytes() == b"Receiver's own additional file."
checks.append("unexpected file refused by rollback and retained")
extra.unlink()  # Remove only the file this test created.

installer.rollback(target)
assert not target.exists()
assert installer.digest(sibling) == sibling_hash
checks.append("verified rollback removes only the installation")

final = installer.install(DEMO / "site", target)
assert final == first
assert installer.verify(target)["files"] == source_pins
assert installer.inventory(DEMO / "site") == source_pins
assert installer.digest(sibling) == sibling_hash
assert sorted(p.name for p in work.iterdir()) == ["installed-site", "unrelated-control.txt"]
checks.append("final reinstallation retained with exact source and sibling readback")
receipt = {
    "schema": "freight-whatif.install-receipt.v1", "python": sys.version.split()[0],
    "passed": len(checks), "failed": 0, "checks": checks,
    "source_sha256": source_pins, "installed_site": str(target),
    "installer_sha256": installer.digest(DEMO / "tools/install.py"),
    "test_sha256": installer.digest(Path(__file__)),
    "sibling_control_sha256": sibling_hash,
    "disposition": "Final static installation retained; no server activated.",
}
with args.output.open("x") as stream:
    stream.write(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt))
