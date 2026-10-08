"""Fictional source records for the actual review-desk browser receiver."""
from __future__ import annotations
import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE), str(Path(__file__).parent)]
from review_desk_fixture import AS_OF, EVAL_FROM, build, read_csv, write_csv  # noqa: E402
from uwatch import engine, evidence, review  # noqa: E402


def build_evidence(root: Path) -> dict:
    fixture = build(root)
    data, report = Path(fixture["data"]), Path(fixture["report"])
    rows = read_csv(data / "bills.csv")
    columns = [*rows[0], "memo"]
    memo = '  =SUM(1,2)\r\n<script>window.utilityExecuted=1</script>\nZoë 李 "quoted" & literal  '
    for row in rows:
        row["memo"] = memo if row["account_no"] == "A" else "Other account: " + row["account_no"]
    write_csv(data / "bills.csv", rows, columns)
    engine.run(data, report.parent, AS_OF, eval_from=EVAL_FROM)
    worksheet = root / "source-selected.csv"
    review.reconcile(data, report, worksheet, Path(fixture["worksheet"]))
    fixture.update(worksheet=str(worksheet), rows=read_csv(worksheet), memo=memo, evidence={})
    for account in ("A", "D"):
        row = next(row for row in fixture["rows"]
                   if row["row_state"] == "current" and row["account_no"] == account)
        out = root / f"native-evidence-{account}.json"
        evidence.write_evidence(data, report, out, kind=row["kind"], account=account,
                                key=row["finding_key"], code=row["code"])
        fixture["evidence"][account] = str(out)
    (root / "source-fixture.json").write_text(json.dumps(fixture, ensure_ascii=True, indent=2)+"\n", encoding="utf-8")
    return fixture


if __name__ == "__main__":
    print(json.dumps(build_evidence(Path(sys.argv[1])), ensure_ascii=True))
