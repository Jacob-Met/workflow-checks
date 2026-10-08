"""Reproduce issue 46 from pinned Git blobs or independently received source directories."""
from __future__ import annotations
import argparse, ast, csv, datetime, hashlib, importlib.util, json, os
from pathlib import Path
import shutil, subprocess, sys, tempfile

HERE = Path(__file__).resolve().parent
PINS = json.loads((HERE / "source-pins.json").read_text(encoding="utf-8"))

def digest(content):
    return {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
            "git_blob": hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()}

def checked(content, expected, path):
    actual = digest(content)
    if any(actual[key] != expected[key] for key in ("bytes", "sha256", "git_blob")):
        raise RuntimeError("Source identity mismatch: " + path)
    return content

def command(args, **kwargs):
    return subprocess.run(args, capture_output=True, timeout=60, **kwargs)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--repo", type=Path, help="Git repository containing the pinned base and explicit candidate commit")
    source.add_argument("--baseline-dir", type=Path, help="Independently received original source, containing utility_watch/")
    parser.add_argument("--candidate-ref", help="Explicit full candidate commit in --repo")
    parser.add_argument("--candidate-dir", type=Path, help="Independently received candidate source, containing utility_watch/")
    parser.add_argument("--out", required=True, type=Path, help="New owned evidence directory; must not exist")
    parser.add_argument("--pytest-python", default=sys.executable, help="Existing interpreter with pytest; no installation is performed")
    args = parser.parse_args()
    if args.repo and (not args.candidate_ref or args.candidate_dir):
        parser.error("--repo requires --candidate-ref and excludes --candidate-dir")
    if args.baseline_dir and (not args.candidate_dir or args.candidate_ref):
        parser.error("--baseline-dir requires --candidate-dir and excludes --candidate-ref")
    if args.out.exists():
        parser.error("--out must be a new directory, to preserve prior evidence")
    candidate_commit = None
    if args.repo:
        if len(args.candidate_ref) != 40 or any(c not in "0123456789abcdef" for c in args.candidate_ref):
            parser.error("--candidate-ref must be an explicit full lowercase commit SHA")
        resolved = command(["git", "-C", str(args.repo), "rev-parse", args.candidate_ref + "^{commit}"])
        if resolved.returncode or resolved.stdout.decode().strip() != args.candidate_ref:
            raise RuntimeError("Candidate commit is unavailable; fetch it through your authorized Git workflow first")
        candidate_commit = args.candidate_ref
    received = {"baseline": {}, "candidate": {}}
    for variant in received:
        expected = dict(PINS["baseline_files"])
        if variant == "candidate":
            expected.update(PINS["candidate_files"])
        for path, record in expected.items():
            if args.repo:
                ref = PINS["base_commit"] if variant == "baseline" else candidate_commit
                got = command(["git", "-C", str(args.repo), "show", ref + ":" + path])
                if got.returncode:
                    raise RuntimeError("Pinned Git source unavailable: " + ref + ":" + path)
                content = got.stdout
            else:
                directory = args.baseline_dir if variant == "baseline" else args.candidate_dir
                content = (directory / path).read_bytes()
            received[variant][path] = checked(content, record, variant + "/" + path)
    regression = "utility_watch/tests/test_account_identity.py"
    received["baseline"][regression] = received["candidate"][regression]
    args.out.mkdir(parents=True)
    proof = args.out.resolve()
    temporary = proof / "temporary"
    temporary.mkdir()
    for variant, files in received.items():
        for path, content in files.items():
            target = proof / variant / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", TMPDIR=str(temporary))
    runs = []
    checks = [
        ("baseline", "new-regression", [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_account_identity.py", "-v"], 1),
        ("baseline", "inherited", [args.pytest_python, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests", "--ignore=tests/test_account_identity.py"], 0),
        ("candidate", "new-regression", [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_account_identity.py", "-v"], 0),
        ("candidate", "new-optimized", [sys.executable, "-B", "-O", "-m", "unittest", "discover", "-s", "tests", "-p", "test_account_identity.py", "-v"], 0),
        ("candidate", "all-utility", [args.pytest_python, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], 0),
    ]
    for variant, name, argv, expected_code in checks:
        result = command(argv, cwd=proof / variant / "utility_watch", env=env)
        stem = variant + "-" + name
        (proof / (stem + ".stdout.log")).write_bytes(result.stdout)
        (proof / (stem + ".stderr.log")).write_bytes(result.stderr)
        correct = result.returncode == expected_code
        if variant == "baseline" and name == "new-regression":
            correct = correct and b"Ran 9 tests" in result.stderr and b"FAILED (failures=4)" in result.stderr
        runs.append({"variant": variant, "suite": name, "actual_exit": result.returncode, "expected_exit": expected_code,
                     "passed": correct, "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                     "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
                     "tail": (result.stdout + result.stderr).decode(errors="replace").splitlines()[-5:]})
    spec = importlib.util.spec_from_file_location("frozen_regression", proof / "candidate" / regression)
    cases = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cases)

    def run_cli(variant, data, output, label):
        result = command([sys.executable, "-B", "-m", "uwatch", "run", "--data", str(data), "--out", str(output),
                          "--as-of", cases.AS_OF.isoformat(), "--eval-from", cases.EVAL_FROM.isoformat()],
                         cwd=proof / variant / "utility_watch", env=env)
        (proof / (label + ".stdout.log")).write_bytes(result.stdout)
        (proof / (label + ".stderr.log")).write_bytes(result.stderr)
        return result

    witness = proof / "row-order-witness"
    witness.mkdir()
    data = cases.fixture(witness)
    out = witness / "out"
    replacement = cases.account(property_name="Replacement property")
    replacement["vendor"] = "Replacement vendor"
    observed = []
    for name, rows, expected in [
        ("ordinary", [cases.account()], "Original property"),
        ("conflicting-duplicate", [cases.account(), replacement], "Replacement property"),
        ("reversed-duplicate", [replacement, cases.account()], "Original property"),
    ]:
        cases.write_csv(data / "accounts.csv", cases.ACCOUNT_FIELDS, rows)
        before = cases.snapshot(data)
        result = run_cli("baseline", data, out, name)
        with (out / "payment_queue.csv").open(newline="") as handle:
            properties = [r["property"] for r in csv.DictReader(handle)]
        passed = result.returncode == 0 and properties == [expected] and cases.snapshot(data) == before
        observed.append({"case": name, "returncode": result.returncode, "queue_properties": properties,
                         "source_csv_unchanged": cases.snapshot(data) == before, "passed": passed})
    parity_root = proof / "valid-parity"
    parity_root.mkdir()
    data = cases.fixture(parity_root, [cases.account("A1"), cases.account("a1", "Distinct case property")])
    before = cases.snapshot(data)
    outputs = []
    for variant in ("baseline", "candidate"):
        out = parity_root / variant
        result = run_cli(variant, data, out, "parity-" + variant)
        if result.returncode:
            raise RuntimeError("Valid parity CLI failed: " + variant)
        outputs.append(cases.snapshot(out))
    parity = [{"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
               "same": outputs[1].get(name) == content} for name, content in outputs[0].items()]
    parity_ok = outputs[0] == outputs[1] and len(outputs[0]) == 6 and cases.snapshot(data) == before
    engine_path = "utility_watch/uwatch/engine.py"
    def definitions(content):
        text = content.decode()
        lines = text.splitlines(keepends=True)
        return {n.name: "".join(lines[n.lineno-1:n.end_lineno]) for n in ast.parse(text).body
                if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    baseline_defs = definitions(received["baseline"][engine_path])
    candidate_defs = definitions(received["candidate"][engine_path])
    changed = [n for n in baseline_defs if baseline_defs[n] != candidate_defs.get(n)]
    scope_ok = changed == ["load"] and baseline_defs.keys() == candidate_defs.keys()
    source_unchanged = all((proof / variant / path).read_bytes() == content
                           for variant, files in received.items() for path, content in files.items())
    passed = all(r["passed"] for r in runs + observed) and parity_ok and scope_ok and source_unchanged
    receipt = {"schema": "workflow-checks.duplicate-account.git-replay.v1",
               "as_of": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "base_commit": PINS["base_commit"], "candidate_commit": candidate_commit,
               "source_mode": "git" if args.repo else "received-files-verified-by-Git-blob",
               "python": sys.version, "pytest_python": args.pytest_python,
               "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "pins_sha256": hashlib.sha256((HERE / "source-pins.json").read_bytes()).hexdigest(),
               "runs": runs, "baseline_row_order_witness": observed, "valid_cli_output_parity": parity,
               "engine_changed_definitions": changed, "all_staged_source_unchanged": source_unchanged, "passed": passed}
    (proof / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
