"""Build the self-contained synthetic demo from the actual PT CSV loaders/rules.

Run from any working directory with Python 3.10+. No package installation,
network call, source CSV mutation, or outside output path is required.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "pt_auth"))
from ptauth.data import load_auths, load_patients, load_payers, load_visits
from ptauth.engine import build_worklist

SOURCE_BASE = "2f1e5f777197eedd69d51a4d81c0da744b65ad88"
ENGINE_BLOB = "39c97f35d61ff949b5c2381f0ad60d7af8d74226"
SELECTED = tuple(f"SYN-{i}" for i in range(1001, 1009))
EXPECTED_INPUTS = {
    "pt_auth/ptauth/engine.py": ENGINE_BLOB,
    "pt_auth/ptauth/data.py": "19a2a1b79eff6d2753507eebf3bf78011ddaaa87",
    "pt_auth/sample_data/schedule.csv": "24a395250f5318004bab4f168c3ca237189ab354",
    "pt_auth/sample_data/authorizations.csv": "036f7b276e3e09252afb886ad451531f51ada844",
    "pt_auth/sample_data/payers.csv": "1853837e82048ac11698b4ad5bb6eeb055d56038",
    "pt_auth/sample_data/patients.csv": "e67323b68d1ac9ee4a901dc3ef70a95384ba5000",
}


def digest(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "git_blob": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()}


def main() -> None:
    data = ROOT / "pt_auth/sample_data"
    visits = [v for v in load_visits(data / "schedule.csv") if v.patient_id in SELECTED]
    auths = [a for a in load_auths(data / "authorizations.csv") if a.patient_id in SELECTED]
    payers = load_payers(data / "payers.csv")
    patients = {k: p for k, p in load_patients(data / "patients.csv").items() if k in SELECTED}
    as_of = date(2026, 9, 28)
    source = [digest(ROOT / p) for p in (
        "pt_auth/ptauth/engine.py", "pt_auth/ptauth/data.py",
        "pt_auth/sample_data/schedule.csv", "pt_auth/sample_data/authorizations.csv",
        "pt_auth/sample_data/payers.csv", "pt_auth/sample_data/patients.csv",
    )]
    for record in source:
        if record["git_blob"] != EXPECTED_INPUTS[record["path"]]:
            raise SystemExit(f"Pinned PT input changed: {record['path']}. Reconcile and qualify before rebuilding.")
    if not all(k.startswith("SYN-") and p.display_name.startswith("Test ") and
               "synthetic" in p.clinic for k, p in patients.items()):
        raise SystemExit("This demo requires the repository's synthetic sample patients.")
    items, ledgers, uncovered = build_worklist(visits, auths, payers, patients, as_of)
    fixture = {
        "schema": "ptauth-whatif/1", "source_base": SOURCE_BASE,
        "notice": "SYNTHETIC DATA ONLY. Placeholder payer rules; no medical advice or payer submission.",
        "source": source,
        "input": {"as_of": as_of, "visits": [asdict(v) for v in visits],
                  "auths": [asdict(a) for a in auths], "payers": {k: asdict(p) for k, p in payers.items()},
                  "patients": {k: asdict(p) for k, p in patients.items()}},
        "baseline": {"items": [{**asdict(i), "key": i.key} for i in items],
                     "ledgers": {k: {**asdict(l), "remaining": l.remaining,
                                      "remaining_after_scheduled": l.remaining_after_scheduled}
                                 for k, l in ledgers.items()},
                     "uncovered": [asdict(v) for v in uncovered]},
    }
    encoded = json.dumps(fixture, ensure_ascii=False, separators=(",", ":"), default=str)
    (HERE / "fixture.json").write_text(encoded + "\n", encoding="utf-8")
    # These are narrowly authored function exports, not arbitrary module input.
    model = (HERE / "model.mjs").read_text(encoding="utf-8").replace("export function ", "function ")
    app = (HERE / "app.mjs").read_text(encoding="utf-8").replace("export function ", "function ")
    safe_fixture = encoded.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    script = f"{model}\n{app}\nmount({safe_fixture}, {{ evaluate, dateNumber, shiftDate }});\n"
    if "</script" in script.lower():
        raise SystemExit("Unexpected script closing tag in authored source.")
    html = (HERE / "page.html").read_text(encoding="utf-8")
    html = html.replace("__STYLE__", (HERE / "style.css").read_text(encoding="utf-8"))
    html = html.replace("__SCRIPT__", script).replace("__SOURCE_BASE__", SOURCE_BASE)
    artifact = html.encode("utf-8")
    (HERE / "index.html").write_bytes(artifact)
    served = ROOT / "docs/demos/ptauth-whatif/index.html"
    served.parent.mkdir(parents=True, exist_ok=True)
    served.write_bytes(artifact)
    print(json.dumps({"artifact": "demos/ptauth-whatif/index.html", "patients": len(patients),
                      "visits": len(visits), "auths": len(auths), "work_items": len(items),
                      "artifact_sha256": hashlib.sha256(artifact).hexdigest(),
                      "artifact_bytes": len(artifact), "engine_blob": ENGINE_BLOB,
                      "served_artifact": served.relative_to(ROOT).as_posix(),
                      "served_bytes_equal": served.read_bytes() == artifact}))


if __name__ == "__main__":
    main()
