"""Read-only iCalendar handoff from a saved synthetic PT worklist.

Dates are already calculated by the report. This module does not run its rules,
write staff state, or promise how a calendar application handles later imports.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

FORMAT = "ptauth-submit-by-v1"
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_ITEMS = 20000
MAX_TEXT = 20000
STATES = ("open", "submitted", "approved", "n/a")


class CalendarInputError(ValueError):
    """The saved report or selected handoff cannot be admitted."""


class CalendarStaleError(CalendarInputError):
    """The report/state pair differs from the reviewed snapshot."""


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CalendarInputError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def decode_json(raw: bytes):
    def nonfinite(value):
        raise CalendarInputError(f"Non-finite JSON value: {value}")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                          parse_constant=nonfinite)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise CalendarInputError("Expected a complete UTF-8 JSON document") from exc


def _read(path: Path, *, optional=False) -> bytes:
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise CalendarInputError(f"Expected a regular file: {path.name}")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(path, flags), "rb") as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                raise CalendarInputError(f"Expected a regular file: {path.name}")
            raw = f.read(MAX_FILE_BYTES + 1)
    except FileNotFoundError:
        if optional:
            return b"{}"
        raise CalendarInputError(f"Saved report is missing: {path.name}") from None
    if len(raw) > MAX_FILE_BYTES:
        raise CalendarInputError(f"{path.name} exceeds the 16 MiB handoff limit")
    return raw


def load_report(report_dir: Path) -> dict:
    """Read existing files only; never generate a report or staff-state file."""
    report_dir = Path(report_dir)
    summary_path, state_path = report_dir / "summary.json", report_dir / "work_state.json"
    summary_raw, state_raw = _read(summary_path), _read(state_path, optional=True)
    if summary_raw != _read(summary_path) or state_raw != _read(state_path, optional=True):
        raise CalendarStaleError("Report or staff state changed while reading; refresh and try again")
    summary, states = decode_json(summary_raw), decode_json(state_raw)
    if not isinstance(summary, dict) or not isinstance(states, dict):
        raise CalendarInputError("Saved summary and staff state must be JSON objects")
    if "states" in summary or "calendar_snapshot" in summary:
        raise CalendarInputError("Use the generated summary.json, not a UI response")
    return {**summary, "states": states}


def snapshot_token(summary: dict) -> str:
    """Bind the reviewed report and staff state; this is not authentication."""
    try:
        raw = json.dumps({k: v for k, v in summary.items() if k != "calendar_snapshot"},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise CalendarInputError("Report contains unsupported JSON values") from exc
    return hashlib.sha256(raw).hexdigest()


def _text(value, label, *, empty=True) -> str:
    if not isinstance(value, str) or len(value) > MAX_TEXT or (not empty and not value):
        raise CalendarInputError(f"{label} must be {'nonempty ' if not empty else ''}text (up to {MAX_TEXT} characters)")
    if any((ord(c) < 32 and c not in "\r\n\t") or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise CalendarInputError(f"{label} contains unsupported control characters")
    return value


def _date(value, label, *, optional=False):
    if optional and value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise CalendarInputError(f"{label} must be a recorded YYYY-MM-DD date")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise CalendarInputError(f"{label} is not a valid calendar date") from exc
    return value


def prepare_calendar(summary: dict, keys=None, *, priority=None, clinic=None) -> dict:
    """Validate the whole report, then select existing rows without mutation."""
    if not isinstance(summary, dict):
        raise CalendarInputError("Expected a report object")
    token = snapshot_token(summary)
    for field in ("banner", "generated_at", "clinic_timezone"):
        _text(summary.get(field), field, empty=False)
    _date(summary.get("as_of"), "as_of")
    rows, states = summary.get("worklist"), summary.get("states", {})
    if not isinstance(rows, list) or len(rows) > MAX_ITEMS or not isinstance(states, dict):
        raise CalendarInputError("Expected a worklist array (up to 20000 items) and staff-state object")
    if priority is not None and priority not in ("P1", "P2", "P3"):
        raise CalendarInputError("Priority must be P1, P2 or P3")
    if clinic is not None:
        _text(clinic, "clinic filter")
    seen = set()
    admitted = []
    for row in rows:
        if not isinstance(row, dict):
            raise CalendarInputError("Every work item must be an object")
        for field in ("key", "patient_id", "patient_name", "clinic", "payer_id", "payer_name", "auth_no", "priority"):
            _text(row.get(field), field, empty=field in ("auth_no", "patient_name", "clinic"))
        key = row["key"]
        if key in seen:
            raise CalendarInputError(f"Duplicate work-item key: {key}")
        seen.add(key)
        if key != f"{row['patient_id']}|{row['payer_id']}|{row['auth_no']}":
            raise CalendarInputError("Work-item key disagrees with its recorded patient/payer/auth identity")
        if row["priority"] not in ("P1", "P2", "P3"):
            raise CalendarInputError(f"Unsupported priority for {key}")
        for field in ("submit_by", "auth_end", "next_visit"):
            if field not in row:
                raise CalendarInputError(f"Missing recorded {field} for {key}")
            _date(row[field], field, optional=True)
        for field in ("reasons", "detail", "checklist", "evidence"):
            values = row.get(field)
            if not isinstance(values, list) or len(values) > MAX_ITEMS:
                raise CalendarInputError(f"{field} must be an array of text")
            for value in values:
                _text(value, field)
        state = states.get(key, {"state": "open", "note": ""})
        if not isinstance(state, dict) or state.get("state") not in STATES:
            raise CalendarInputError(f"Unsupported staff state for {key}")
        _text(state.get("note", ""), "staff note")
        if "at" in state:
            _text(state["at"], "staff-state recorded time")
        admitted.append((row, state))

    if keys is not None:
        if not isinstance(keys, list) or len(keys) > MAX_ITEMS:
            raise CalendarInputError("Selected keys must be an array (up to 20000 items)")
        for key in keys:
            _text(key, "selected key", empty=False)
        if len(set(keys)) != len(keys) or set(keys) - seen:
            raise CalendarInputError("Selected keys must be unique and belong to this report")
        chosen = set(keys)
    else:
        chosen = seen

    included, excluded = [], []
    for row, state in admitted:
        if row["key"] not in chosen or (priority and row["priority"] != priority) or (clinic is not None and row["clinic"] != clinic):
            continue
        why = []
        if row["submit_by"] is None:
            why.append("undated")
        if state["state"] in ("approved", "n/a"):
            why.append("completed_state")
        if why:
            excluded.append({"key": row["key"], "patient_id": row["patient_id"],
                             "state": state["state"], "reasons": why})
        else:
            # Copy exact JSON values so a later caller mutation cannot alter this plan.
            included.append(json.loads(json.dumps({"item": row, "staff": state}, ensure_ascii=False)))
    context = {k: summary[k] for k in ("banner", "as_of", "generated_at", "clinic_timezone")}
    return {"format": FORMAT, "snapshot": token, "context": context,
            "selected": len(included) + len(excluded), "included": included,
            "excluded": excluded}


def calendar_metadata(plan: dict) -> dict:
    return {"format": FORMAT, "snapshot": plan["snapshot"], "as_of": plan["context"]["as_of"],
            "clinic_timezone": plan["context"]["clinic_timezone"], "selected": plan["selected"],
            "events": len(plan["included"]), "excluded": plan["excluded"],
            "undated": sum("undated" in x["reasons"] for x in plan["excluded"]),
            "completed_state": sum("completed_state" in x["reasons"] for x in plan["excluded"])}


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def _fold(line: str) -> bytes:
    # RFC 5545 3.1 counts octets, including the continuation's leading space.
    chunks, current, size = [], [], 0
    for char in line:
        length = len(char.encode("utf-8"))
        if size + length > 75:
            chunks.append("".join(current))
            current, size = [" "], 1
        current.append(char)
        size += length
    chunks.append("".join(current))
    return ("\r\n".join(chunks) + "\r\n").encode("utf-8")


def render_calendar(plan: dict, *, now: datetime | None = None) -> bytes:
    if not plan["included"]:
        raise CalendarInputError("No dated open/submitted items in this selection; no calendar was created")
    instant = now if now is not None else datetime.now(timezone.utc)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise CalendarInputError("Export time must be timezone-aware")
    stamp = instant.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result = bytearray()

    def emit(lines):
        for line in lines:
            encoded = _fold(line)
            if len(result) + len(encoded) > MAX_FILE_BYTES:
                raise CalendarInputError("Calendar exceeds the 16 MiB handoff limit; narrow the selection")
            result.extend(encoded)

    emit(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Workflow Checks//Synthetic PT handoff v1//EN",
          "CALSCALE:GREGORIAN"])
    ctx = plan["context"]
    for entry in plan["included"]:
        row, staff = entry["item"], entry["staff"]
        identity = [FORMAT, row["key"], row["clinic"], row["auth_end"], ctx["clinic_timezone"]]
        uid = hashlib.sha256(json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
        description = [
            ctx["banner"], "Administrative submit-by review; no payer submission or staff-state change.",
            f"Work-item key: {row['key']}", f"Patient: {row['patient_id']} — {row['patient_name']}",
            f"Payer: {row['payer_id']} — {row['payer_name']}", f"Authorization: {row['auth_no']}",
            f"Clinic: {row['clinic']}", f"Priority: {row['priority']}",
            f"Recorded submit-by: {row['submit_by']}", f"Authorization end: {row['auth_end'] or 'unrecorded'}",
            f"Next visit: {row['next_visit'] or 'unrecorded'}",
            f"Staff state: {staff['state']}", f"Staff note: {staff.get('note', '')}",
            f"Staff state recorded at: {staff.get('at', 'unrecorded')}",
            f"Report as of: {ctx['as_of']}", f"Report generated at (as recorded): {ctx['generated_at']}",
            f"Clinic time zone (context; all-day date unchanged): {ctx['clinic_timezone']}",
        ]
        for label, field in (("Reasons", "reasons"), ("Details", "detail"), ("Checklist", "checklist"), ("Source evidence", "evidence")):
            description.append(label + ":")
            description.extend(row[field])
        emit(["BEGIN:VEVENT", f"UID:{uid}@ptauth.workflow-checks.invalid", f"DTSTAMP:{stamp}",
                      "DTSTART;VALUE=DATE:" + row["submit_by"].replace("-", ""),
                      "SUMMARY:" + _escape(f"[SYNTHETIC] {row['priority']} authorization review — {row['patient_id']}"),
                      "DESCRIPTION:" + _escape("\n".join(description)),
                      "TRANSP:TRANSPARENT", "END:VEVENT"])
    emit(["END:VCALENDAR"])
    return bytes(result)


def write_calendar(output: Path, content: bytes) -> None:
    """Publish complete bytes without replacing an existing file or symlink."""
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise CalendarInputError(f"Output already exists: {output}")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".ptauth-calendar-", suffix=".tmp",
                                         dir=output.parent, delete=False) as f:
            temporary = Path(f.name)
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        # Same-directory hard link is exclusive even if another writer races us.
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
