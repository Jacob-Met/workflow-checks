"""Fictional native source/worksheet producer used only by review-desk receiving."""
from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from uwatch import engine, review  # noqa: E402

HEADERS = {
    "accounts.csv": "account_no,property,utility,vendor,scope,unit,cycle".split(","),
    "bills.csv": ("bill_id,account_no,vendor_invoice_no,period_start,period_end,usage,"
                  "usage_unit,amount,late_fee,prior_balance,due_date,received_date").split(","),
    "occupancy.csv": "property,unit,status,from,to".split(","),
    "payments.csv": "payment_id,account_no,vendor_invoice_no,amount,paid_date".split(","),
}
AS_OF, EVAL_FROM = date(2024, 2, 5), date(2024, 1, 1)


def write_csv(path: Path, rows: list[dict], columns) -> None:
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def build(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    data, report = root / "data", root / "report"
    data.mkdir()
    accounts = [dict(zip(HEADERS["accounts.csv"], [
        account, 'Fictional <Courtyard> & "East"' if account == "A" else f"Fictional {account}",
        "electric", "Placeholder vendor", "common", "", "irregular",
    ])) for account in "ABCD"]
    bills = []
    for account in "ABCD":
        for year in (2023, 2024):
            bills.append(dict(zip(HEADERS["bills.csv"], [
                "SHARED" if account in "AD" and year == 2024 else f"{account}-{year}",
                account, f"INV-{account}-{year}", f"{year}-01-01", f"{year}-01-31",
                "600" if account == "C" and year == 2024 else "300", "kWh",
                "120" if account == "C" and year == 2024 else "60",
                "5" if account in "ABD" and year == 2024 else "0", "0",
                "2024-03-01", "2024-02-01",
            ])))
    for name, rows in {
        "accounts.csv": accounts, "bills.csv": bills, "occupancy.csv": [], "payments.csv": [],
    }.items():
        write_csv(data / name, rows, HEADERS[name])
    (data / "expected.json").write_text(
        json.dumps({"as_of": AS_OF.isoformat(), "eval_from": EVAL_FROM.isoformat()}), encoding="utf-8")
    engine.run(data, report, AS_OF, eval_from=EVAL_FROM)
    original = root / "original.csv"
    review.reconcile(data, report / "summary.json", original)
    rows = read_csv(original)
    for row in rows:
        if row["row_state"] == "current" and row["account_no"] in "ABD":
            row.update(review_status="reviewed", reviewer="Fictional Zoë 李",
                       note='Retained note: "before", =literal\nSecond line <script>never execute</script>')
    write_csv(original, rows, review.COLUMNS)
    # Two real source changes create genuine changed and absent history.
    for bill in bills:
        if bill["period_start"].startswith("2024"):
            if bill["account_no"] == "A":
                bill["late_fee"] = "8"
            if bill["account_no"] == "B":
                bill["late_fee"] = "0"
    write_csv(data / "bills.csv", bills, HEADERS["bills.csv"])
    engine.run(data, report, AS_OF, eval_from=EVAL_FROM)
    selected = root / "selected.csv"
    review.reconcile(data, report / "summary.json", selected, original)
    result = {"data": str(data), "report": str(report / "summary.json"),
              "worksheet": str(selected), "rows": read_csv(selected)}
    (root / "fixture.json").write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(build(Path(sys.argv[1])), ensure_ascii=True))
