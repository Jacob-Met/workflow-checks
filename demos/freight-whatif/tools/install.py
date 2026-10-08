"""Install this static demo into a new directory; verify or roll it back safely.

No shared webroot is assumed. Rollback refuses modified files, extra files and
symlinks. Run a server separately and stop it before rollback.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil

SITE_FILES = ("app.mjs", "data.mjs", "index.html", "model.mjs", "styles.css")
MARKER = ".freight-whatif-install.json"
SCHEMA = "workflow-checks.freight-whatif.install.v1"

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def inventory(source):
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Source must be a real directory")
    names = sorted(p.name for p in source.iterdir())
    if names != list(SITE_FILES):
        raise ValueError("Source must contain exactly the five static site files")
    if any((source / name).is_symlink() or not (source / name).is_file() for name in SITE_FILES):
        raise ValueError("Source files must be regular files, not symlinks")
    return {name: digest(source / name) for name in SITE_FILES}

def verify(target):
    if target.is_symlink() or not target.is_dir():
        raise ValueError("Target must be an installed directory, not a symlink")
    marker = target / MARKER
    if marker.is_symlink() or not marker.is_file():
        raise ValueError("No regular installation receipt at target")
    receipt = json.loads(marker.read_text())
    if receipt.get("schema") != SCHEMA or sorted(receipt.get("files", {})) != list(SITE_FILES):
        raise ValueError("Installation receipt is outside this demo scope")
    if sorted(p.name for p in target.iterdir()) != sorted([*SITE_FILES, MARKER]):
        raise ValueError("Target has additional or missing files; leave it intact")
    for name, expected in receipt["files"].items():
        p = target / name
        if p.is_symlink() or not p.is_file() or digest(p) != expected:
            raise ValueError("Installed content changed; leave it intact: " + name)
    return receipt

def install(source, target):
    files = inventory(source)
    if target.exists() or target.is_symlink():
        raise FileExistsError("Choose a new target directory; existing targets are never overwritten")
    if not target.parent.is_dir() or target.parent.is_symlink():
        raise ValueError("Target parent must already be a real directory")
    target.mkdir()  # Exclusive creation; no existing directory is replaced.
    written = []
    try:
        for name, expected in files.items():
            payload = (source / name).read_bytes()
            if hashlib.sha256(payload).hexdigest() != expected:
                raise ValueError("Source changed during install: " + name)
            with (target / name).open("xb") as stream:
                stream.write(payload)
            written.append(name)
        receipt = {"schema": SCHEMA, "files": files}
        with (target / MARKER).open("x") as stream:
            stream.write(json.dumps(receipt, indent=2) + "\n")
        written.append(MARKER)
        verify(target)
    except Exception:
        # Remove only paths this invocation created; leave unexpected data intact.
        for name in reversed(written):
            (target / name).unlink()
        target.rmdir()
        raise
    return receipt

def rollback(target):
    receipt = verify(target)
    for name in [*SITE_FILES, MARKER]:
        (target / name).unlink()
    target.rmdir()
    return {"removed": str(target), "verified_files": receipt["files"]}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "verify", "rollback"])
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "site")
    args = parser.parse_args()
    target = args.target.absolute()
    try:
        result = install(args.source.absolute(), target) if args.action == "install" else verify(target) if args.action == "verify" else rollback(target)
    except (ValueError, FileExistsError) as error:
        parser.exit(2, str(error) + "\n")
    print(json.dumps({"action": args.action, "target": str(target), "result": result}, sort_keys=True))
if __name__ == "__main__":
    main()
