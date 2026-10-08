"""Local review worksheets for unchanged native findings; never changes eligibility."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import tempfile
import uuid
from collections import Counter
from dataclasses import asdict
from datetime import date
from pathlib import Path

from . import engine

SCHEMA = "uwatch-review-v1"
EDITABLE = ("review_status", "reviewer", "note")
COLUMNS = EDITABLE + (
    "row_state", "kind", "account_no", "finding_key", "code", "property", "utility",
    "detail", "evidence", "as_of", "eval_from", "data_mode", "row_id", "finding_id",
    "evidence_version", "record_sha256",
)
OBSERVED = ("kind", "account_no", "finding_key", "code", "property", "utility", "detail", "evidence")
DATA_FILES = ("accounts.csv", "bills.csv", "occupancy.csv", "payments.csv")
REPORT_FILES = ("summary.json", "flags.csv", "exceptions.csv", "payment_queue.csv", "report.html", "audit.jsonl")
STATUSES = ("open", "in_progress", "reviewed")
MANIFEST_NOTE = "Edit only review_status, reviewer and note on finding rows; keep this manifest."


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":"), default=lambda x: x.isoformat() if isinstance(x, date) else _unsupported(x))


def _unsupported(value):
    raise ValueError(f"unsupported evidence value: {type(value).__name__}")


def _digest(value) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _read_json(raw: bytes):
    def nonfinite(value):
        raise ValueError(f"nonfinite JSON value: {value}")
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            nonfinite(value)
        return number
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_pairs,
                      parse_constant=nonfinite, parse_float=finite_float)


def _day(value, field: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError(f"{field} must be an ISO date")
    return date.fromisoformat(value)


def _csv(raw: bytes, name: str):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    headers = reader.fieldnames or []
    if not headers or any(not h for h in headers) or len(set(headers)) != len(headers):
        raise ValueError(f"{name}: missing or duplicate CSV headers")
    result = []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"{name}:{reader.line_num}: wrong number of CSV columns")
        if any(value.strip() for value in row.values()):
            result.append((reader.line_num, row))
    return headers, result


def _seal(row: dict) -> dict:
    row = dict(row)
    row["record_sha256"] = _digest([SCHEMA, [[key, row[key]] for key in COLUMNS[3:-1]]])
    return row


def _identity(row: dict) -> str:
    return _digest([SCHEMA, row["kind"], row["account_no"], row["finding_key"], row["code"]])


def _manifest(rows: list[dict], report: dict) -> dict:
    row = dict.fromkeys(COLUMNS, "")
    row.update(row_state="manifest", kind="worksheet", finding_key=SCHEMA, code=str(len(rows)),
               detail=MANIFEST_NOTE, evidence="[]", row_id="manifest",
               finding_id=_digest([SCHEMA, "worksheet"]),
               evidence_version=_digest(sorted((r["row_id"], r["record_sha256"]) for r in rows)))
    for key in ("as_of", "eval_from", "data_mode"):
        row[key] = report[key]
    return _seal(row)


def _previous(raw: bytes) -> list[dict]:
    headers, incoming = _csv(raw, "previous worksheet")
    if set(headers) != set(COLUMNS):
        raise ValueError("previous worksheet: columns do not match uwatch-review-v1")
    rows, manifests, ids, current = [], [], set(), set()
    for line, original in incoming:
        row = dict(original)
        for key in ("as_of", "eval_from"):
            _day(row[key], f"worksheet:{line}:{key}")
        if row["data_mode"] not in ("synthetic", "client_csv"):
            raise ValueError(f"worksheet:{line}: unknown data mode")
        if row["record_sha256"] != _seal(row)["record_sha256"]:
            raise ValueError(f"worksheet:{line}: protected finding columns changed; edit only {', '.join(EDITABLE)}")
        if row["row_state"] == "manifest":
            manifests.append(row)
            continue
        if row["row_state"] not in ("current", "changed", "absent") or row["kind"] not in ("flag", "exception"):
            raise ValueError(f"worksheet:{line}: invalid finding kind or row state")
        if not all(row[key] for key in ("account_no", "finding_key", "code")):
            raise ValueError(f"worksheet:{line}: incomplete finding identity")
        if not re.fullmatch(r"[0-9a-f]{32}", row["row_id"]) or row["row_id"] in ids:
            raise ValueError(f"worksheet:{line}: invalid or duplicate row identity")
        ids.add(row["row_id"])
        if row["finding_id"] != _identity(row) or not re.fullmatch(r"[0-9a-f]{64}", row["evidence_version"]):
            raise ValueError(f"worksheet:{line}: invalid finding or evidence identity")
        evidence = _read_json(row["evidence"].encode("utf-8"))
        if (not isinstance(evidence, list) or not evidence or
                any(not isinstance(e, str) or not re.fullmatch(r"(?:accounts|bills|occupancy|payments)\.csv:[1-9][0-9]*", e)
                    for e in evidence)):
            raise ValueError(f"worksheet:{line}: invalid source evidence pointers")
        row["review_status"] = row["review_status"].strip()
        if row["review_status"] not in STATUSES:
            raise ValueError(f"worksheet:{line}: review_status must be open, in_progress or reviewed")
        if row["review_status"] != "open" and (not row["reviewer"].strip() or not row["note"].strip()):
            raise ValueError(f"worksheet:{line}: a non-open review needs both reviewer and note")
        if row["row_state"] == "current":
            if row["finding_id"] in current:
                raise ValueError(f"worksheet:{line}: more than one current row for a finding")
            current.add(row["finding_id"])
        rows.append(row)
    if len(manifests) != 1:
        raise ValueError("previous worksheet: exactly one integrity manifest is required")
    if manifests[0] != _manifest(rows, manifests[0]):
        raise ValueError("previous worksheet: manifest mismatch; a row was removed, added or changed")
    return rows


def _current(data: Path, report_path: Path):
    watched = {report_path: report_path.read_bytes()}
    report = _read_json(watched[report_path])
    if not isinstance(report, dict):
        raise ValueError("report must be the native summary.json object")
    as_of = _day(report.get("as_of"), "report as_of")
    eval_from = _day(report.get("eval_from"), "report eval_from")
    source = {}
    for name in DATA_FILES:
        source[name] = (data / name).read_bytes()
        watched[data / name] = source[name]
    marker = data / "expected.json"
    watched[marker] = marker.read_bytes() if marker.exists() else None
    mode = "synthetic" if watched[marker] is not None else "client_csv"
    if watched[marker] is not None and not isinstance(_read_json(watched[marker]), dict):
        raise ValueError("expected.json must be an object")
    raw_rows = {}
    for name, raw in source.items():
        _, rows = _csv(raw, name)
        raw_rows[name] = [{"row": line, "fields": {k: v.strip() for k, v in row.items()}} for line, row in rows]
    seen_accounts = set()
    for row in raw_rows["accounts.csv"]:
        account = row["fields"].get("account_no")
        if account in seen_accounts:
            raise ValueError(f"accounts.csv:{row['row']}: duplicate account identity is ambiguous for review")
        seen_accounts.add(account)
    # The existing loader/checker sees one fixed byte snapshot, never a partially reread export.
    with tempfile.TemporaryDirectory(prefix="uwatch-review-source-") as staging:
        snapshot = Path(staging)
        for name, raw in source.items():
            (snapshot / name).write_bytes(raw)
        accounts, bills, occupancy, payments = engine.load(snapshot)
        flags, exceptions, queue, naive = engine.check(accounts, bills, occupancy, payments, as_of, eval_from)
    flag_records = [asdict(flag) for flag in flags]
    expected = {
        "as_of": as_of.isoformat(), "eval_from": eval_from.isoformat(), "data_mode": mode,
        "accounts": len(accounts), "bills": len(bills), "flags": len(flags),
        "by_code": dict(Counter(f.code for f in flags)), "exceptions": len(exceptions),
        "payment_queue": len(queue), "payment_queue_total": round(sum(q["amount_due"] for q in queue), 2),
        "naive_trailing3_hits": naive, "flags_detail": flag_records,
        "exceptions_detail": exceptions, "payment_queue_detail": queue,
    }
    for key, value in expected.items():
        if key not in report or _json(report[key]) != _json(value):
            raise ValueError(f"report does not match the source export/current checks ({key}); regenerate it with uwatch run")
    common = {"schema": SCHEMA, "engine_sha256": hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest(),
              "rules": engine.DEFAULT_RULES, "data_mode": mode}
    contexts = {}
    result, identities = [], set()
    for kind, records in (("flag", flag_records), ("exception", exceptions)):
        for finding in records:
            account_no = finding["account_no"]
            account = accounts.get(account_no, {})
            if account_no not in contexts:
                context = {"checks": common}
                for name in ("accounts.csv", "bills.csv", "payments.csv"):
                    context[name] = [r for r in raw_rows[name] if r["fields"].get("account_no") == account_no]
                context["occupancy.csv"] = [r for r in raw_rows["occupancy.csv"]
                    if account.get("scope") == "unit" and r["fields"].get("property") == account.get("property")
                    and r["fields"].get("unit") == account.get("unit")]
                contexts[account_no] = context
            row = dict.fromkeys(COLUMNS, "")
            row.update(review_status="open", row_state="current", kind=kind, account_no=account_no,
                       finding_key=finding["key"], code=finding["code"] if kind == "flag" else finding["reason"],
                       property=account.get("property", ""), utility=account.get("utility", ""),
                       detail=finding.get("detail", ""), evidence=_json(finding["evidence"]),
                       as_of=as_of.isoformat(), eval_from=eval_from.isoformat(), data_mode=mode,
                       row_id=uuid.uuid4().hex)
            row["finding_id"] = _identity(row)
            if row["finding_id"] in identities:
                raise ValueError(f"ambiguous repeated finding for account {account_no!r}, key {finding['key']!r}, code {row['code']!r}")
            identities.add(row["finding_id"])
            row["evidence_version"] = _digest({"finding": {k: row[k] for k in OBSERVED}, "source": contexts[account_no]})
            result.append(_seal(row))
    result.sort(key=lambda r: tuple(r[k] for k in ("kind", "property", "account_no", "finding_key", "code")))
    return result, expected, watched


def _combine(current: list[dict], previous: list[dict]) -> list[dict]:
    old_current = {r["finding_id"]: r for r in previous if r["row_state"] == "current"}
    now = {r["finding_id"]: r for r in current}
    retained = set()
    for row in current:
        old = old_current.get(row["finding_id"])
        if old and old["evidence_version"] == row["evidence_version"]:
            if any(old[k] != row[k] for k in OBSERVED):
                raise ValueError("worksheet evidence identity disagrees with current finding fields")
            for key in ("row_id", *EDITABLE):
                row[key] = old[key]
            retained.add(old["row_id"])
    history = []
    for old in previous:
        if old["row_id"] in retained:
            continue
        row = dict(old)
        if row["row_state"] == "current":
            row["row_state"] = "changed" if row["finding_id"] in now else "absent"
        history.append(_seal(row))
    # Historical rows never supply a current annotation, even if their old evidence returns.
    return [_seal(r) for r in current] + history


def _publish(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".uwatch-review-", suffix=".csv", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            target.flush()
            os.fsync(target.fileno())
        # A new destination only: linking publishes the complete file and cannot overwrite a raced writer.
        os.link(temporary, path)
    finally:
        # Failure to remove a temporary name must not report a completed publication as failed,
        # or mask the original write/link error. The destination is already complete or absent.
        try:
            os.unlink(temporary)
        except OSError:
            pass


def reconcile(data: Path, report: Path, out: Path, previous: Path | None = None) -> dict:
    """Write one complete new worksheet, retaining only current exact-evidence annotations."""
    if Path(out).is_symlink():
        raise ValueError("--out must name a new worksheet, not a symbolic link")
    data, report, out = Path(data).resolve(), Path(report).resolve(), Path(out).resolve()
    previous = Path(previous).resolve() if previous is not None else None
    protected = {data / name for name in (*DATA_FILES, "expected.json")}
    protected.update(report.parent / name for name in REPORT_FILES)
    protected.add(report)
    if previous is not None:
        protected.add(previous)
    if out in protected or out.exists():
        raise ValueError("--out must name a new worksheet; source, reports and previous review cannot be replaced")
    try:
        current, source_report, watched = _current(data, report)
        prior = []
        if previous is not None:
            raw = previous.read_bytes()
            watched[previous] = raw
            prior = _previous(raw)
        rows = _combine(current, prior)
        rows.append(_manifest(rows, source_report))
        # Refuse a source/report/worksheet edit observed during the read/check operation.
        for path, original in watched.items():
            actual = path.read_bytes() if path.exists() else None
            if actual != original:
                raise ValueError(f"input changed during review: {path.name}; inspect and run again")
        _publish(out, rows)
    except csv.Error as exc:
        raise ValueError(f"malformed CSV: {exc}") from exc
    return {"current": len(current), "history": len(rows) - len(current) - 1,
            "statuses": dict(Counter(r["review_status"] for r in rows if r["row_state"] == "current")),
            "data_mode": source_report["data_mode"], "worksheet": str(out)}
