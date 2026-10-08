"""Inspect and annotate the existing saved review worksheet; never recomputes findings."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import sys


def add_parser(subparsers) -> None:
    parser = subparsers.add_parser("worksheet", help="inspect or annotate a saved review worksheet")
    commands = parser.add_subparsers(dest="worksheet_command", required=True)
    show = commands.add_parser("list", help="list saved findings and their exact row IDs")
    show.add_argument("--worksheet", type=Path, required=True)
    show.add_argument("--include-history", action="store_true", help="also show changed and absent rows")
    show.add_argument("--account", help="show only this exact account number")
    show.add_argument("--status", choices=("open", "in_progress", "reviewed"))
    show.add_argument("--json", action="store_true", help="write the complete selected rows as JSON")
    edit = commands.add_parser("annotate", help="write new notes for one current row to a new worksheet")
    edit.add_argument("--worksheet", type=Path, required=True)
    edit.add_argument("--row-id", required=True, help="exact current row ID from worksheet list")
    edit.add_argument("--status", choices=("open", "in_progress", "reviewed"), required=True)
    edit.add_argument("--reviewer", required=True, help="reviewer text; may be empty only for open rows")
    edit.add_argument("--note", required=True, help="review note; may be empty only for open rows")
    edit.add_argument("--out", type=Path, required=True, help="new worksheet path; never replaces a file")


def _read(path: Path):
    from . import review

    path = Path(path).resolve()
    raw = path.read_bytes()
    try:
        validated = review._previous(raw)
        # Keep the original cell values and row order for publication. The validator
        # normalizes status whitespace in its returned dictionaries for comparison.
        _, incoming = review._csv(raw, "worksheet")
    except csv.Error as exc:
        raise ValueError(f"malformed worksheet CSV: {exc}") from exc
    rows = [dict(row) for _, row in incoming]
    manifest = next(row for row in rows if row["row_state"] == "manifest")
    return path, raw, rows, validated, manifest


def list_rows(path: Path, *, include_history: bool = False,
              account: str | None = None, status: str | None = None) -> dict:
    """Return selected saved rows after validating the entire worksheet."""
    from . import review

    if status is not None and status not in review.STATUSES:
        raise ValueError("unknown review status")
    path, raw, _, validated, manifest = _read(path)
    selected = [row for row in validated
                if (include_history or row["row_state"] == "current")
                and (account is None or row["account_no"] == account)
                and (status is None or row["review_status"] == status)]
    current = sum(row["row_state"] == "current" for row in validated)
    return {
        "worksheet": str(path), "worksheet_schema": review.SCHEMA,
        "worksheet_sha256": hashlib.sha256(raw).hexdigest(),
        "as_of": manifest["as_of"], "eval_from": manifest["eval_from"],
        "data_mode": manifest["data_mode"],
        "current": current, "history": len(validated) - current,
        "shown": len(selected),
        "filters": {"include_history": include_history, "account": account, "status": status},
        "rows": selected,
    }


def _serialize(rows: list[dict]) -> bytes:
    from . import review

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=review.COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def annotate(path: Path, out: Path, *, row_id: str, status: str,
             reviewer: str, note: str) -> dict:
    """Change only three annotation cells on one current saved row; publish a new file."""
    from . import review

    out = Path(out)
    if out.is_symlink():
        raise ValueError("--out must name a new worksheet, not a symbolic link")
    out = out.resolve()
    if out.exists() or out == Path(path).resolve():
        raise ValueError("--out must name a new worksheet; no existing file can be replaced")
    if not all(isinstance(value, str) for value in (row_id, status, reviewer, note)):
        raise ValueError("row ID, status, reviewer and note must be text")
    if status not in review.STATUSES:
        raise ValueError("review status must be open, in_progress or reviewed")
    path, raw, rows, _, manifest = _read(path)
    selected = next((row for row in rows if row["row_id"] == row_id), None)
    if selected is None or selected["row_state"] != "current":
        raise ValueError("--row-id must identify one current finding in this worksheet; history cannot be annotated")
    selected.update(review_status=status, reviewer=reviewer, note=note)
    # The native validator owns allowed annotations and every protected-field seal.
    # Annotation cells are outside those seals, so the original manifest stays exact.
    try:
        review._previous(_serialize(rows))
    except csv.Error as exc:
        raise ValueError(f"malformed worksheet CSV: {exc}") from exc
    if path.read_bytes() != raw:
        raise ValueError("worksheet changed during annotation; inspect it and run again")
    review._publish(out, rows)
    return {"worksheet": str(out), "row_id": row_id, "review_status": status,
            "as_of": manifest["as_of"], "data_mode": manifest["data_mode"]}


def _quoted(value) -> str:
    # A multiline note or terminal control stays visible as text, not terminal input.
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _print_rows(result: dict) -> None:
    print(f"Saved worksheet: {_quoted(result['worksheet'])}")
    print(f"Recorded report: {result['as_of']} (from {result['eval_from']}; {result['data_mode']})")
    print(f"Rows shown: {result['shown']}; complete worksheet: {result['current']} current, {result['history']} historical")
    print("Annotations record human review; they do not change payment eligibility.")
    for row in result["rows"]:
        print(f"\n{row['row_id']}  {row['row_state']} / {row['review_status']}  {row['kind']}")
        for label, keys in (("identity", ("account_no", "finding_key", "code")),
                            ("location", ("property", "utility")),
                            ("detail", ("detail",)), ("evidence", ("evidence",)),
                            ("reviewer", ("reviewer",)), ("note", ("note",))):
            print(f"  {label}: " + " | ".join(_quoted(row[key]) for key in keys))
    if not result["rows"]:
        print("No saved findings match these filters.")


def run(args) -> int:
    try:
        if args.worksheet_command == "list":
            result = list_rows(args.worksheet, include_history=args.include_history,
                               account=args.account, status=args.status)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
            else:
                _print_rows(result)
        else:
            result = annotate(args.worksheet, args.out, row_id=args.row_id,
                              status=args.status, reviewer=args.reviewer, note=args.note)
            print(f"Saved {result['review_status']} annotation for {result['row_id']}")
            print(f"worksheet: {_quoted(result['worksheet'])}")
            print("Recorded findings and payment eligibility are unchanged. Use review --previous for source reconciliation.")
    except (OSError, ValueError, KeyError) as exc:
        print(f"uwatch: worksheet error: {exc}", file=sys.stderr)
        return 2
    return 0
