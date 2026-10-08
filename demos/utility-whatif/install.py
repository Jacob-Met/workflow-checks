"""Install/read back/roll back only this new static artifact. No service changes."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = ("index.html", "styles.css", "app.mjs", "model.mjs", "fixture.json")
MARKER = "installed-manifest.json"
SCHEMA = "utility-watch.whatif-install.v1"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_manifest(target):
    if target.is_symlink() or not target.is_dir():
        raise ValueError("The target must be this artifact's real installation directory")
    marker = target / MARKER
    if marker.is_symlink():
        raise ValueError("Refusing a redirected installation manifest")
    manifest = json.loads(marker.read_text())
    if manifest.get("schema") != SCHEMA or manifest.get("priorState") != "absent" or set(manifest.get("files", {})) != set(FILES):
        raise ValueError("This target has no recognized new-artifact installation manifest")
    actual = {p.name for p in target.iterdir()}
    if actual - set(FILES) - {MARKER}:
        raise ValueError("Unexpected files are present; preserve them and use another target")
    for name, expected in manifest["files"].items():
        path = target / name
        if path.is_symlink() or (path.exists() and (not path.is_file() or digest(path.read_bytes()) != expected)):
            raise ValueError("Installed file changed; refusing to remove or accept it: " + name)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("install", "readback", "rollback"))
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    target = args.target.absolute()
    if args.action == "install":
        if target.exists() or target.is_symlink():
            raise ValueError("Choose an absent, dedicated target; existing files are never overwritten")
        source = {name: (HERE / name).read_bytes() for name in FILES}
        fixture = json.loads(source["fixture.json"])
        manifest = {"schema": SCHEMA, "priorState": "absent", "sourceCommit": fixture["source"]["commit"], "files": {name: digest(raw) for name, raw in source.items()}}
        target.mkdir(parents=True, exist_ok=False)
        (target / MARKER).write_text(json.dumps(manifest, indent=2) + "\n")
        for name, raw in source.items():
            (target / name).write_bytes(raw)
        read_manifest(target)
    else:
        manifest = read_manifest(target)
    if args.action == "readback":
        if any(not (target / name).exists() for name in FILES):
            raise ValueError("The installation is incomplete; it can be rolled back")
    if args.action == "rollback":
        for name in FILES:
            (target / name).unlink(missing_ok=True)
        (target / MARKER).unlink()
        target.rmdir()
    print(json.dumps({"action": args.action, "target": str(target), "exists": target.exists(), "manifest": manifest}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit("Installation refused: " + str(error))
