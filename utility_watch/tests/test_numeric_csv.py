"""Reject non-finite imported values at the actual utility-review CLI boundary."""
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest


APP = Path(__file__).resolve().parents[1]
HEADERS = {
    "accounts": "account_no,property,utility,vendor,scope,unit,cycle",
    "bills": ("bill_id,account_no,vendor_invoice_no,period_start,period_end,usage,"
              "usage_unit,amount,late_fee,prior_balance,due_date,received_date"),
    "occupancy": "property,unit,status,from,to",
    "payments": "payment_id,account_no,vendor_invoice_no,amount,paid_date",
}


def _write_data(data):
    data.mkdir()
    rows = {
        "accounts": [["A1", "One", "electric", "Power", "common", "", "monthly"]],
        "bills": [
            ["BASE", "A1", "INV-BASE", "2023-01-01", "2023-01-31", "300", "kWh",
             "60", "0", "0", "2023-03-01", "2023-02-01"],
            ["B1", "A1", "INV-B1", "2024-01-01", "2024-01-31", "300", "kWh",
             "60", "0", "0", "2024-04-01", "2024-02-01"],
        ],
        "occupancy": [],
        "payments": [],
    }
    for name, values in rows.items():
        with (data / f"{name}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(HEADERS[name].split(","))
            writer.writerows(values)


def _run(data, out):
    return subprocess.run(
        [sys.executable, "-m", "uwatch", "run", "--data", str(data), "--out", str(out),
         "--as-of", "2024-03-15", "--eval-from", "2024-01-01"],
        cwd=APP, capture_output=True, text=True, check=False,
    )


@pytest.mark.parametrize("table,column,value", [
    ("bills", "amount", "NaN"),
    ("bills", "amount", "Infinity"),
    ("bills", "usage", "-inf"),
    ("bills", "late_fee", "nan"),
    ("bills", "prior_balance", "(Infinity)"),
    ("payments", "amount", "NaN"),
    ("payments", "amount", "1e309"),
])
def test_rejects_nonfinite_csv_without_replacing_previous_review(tmp_path, table, column, value):
    data, out = tmp_path / "input", tmp_path / "review"
    _write_data(data)
    initial = _run(data, out)
    assert initial.returncode == 0, initial.stderr
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert [(q["bill_id"], q["amount_due"]) for q in summary["payment_queue_detail"]] == [
        ("B1", 60.0)
    ]
    previous_review = {file.name: file.read_bytes() for file in out.iterdir()}

    path = data / f"{table}.csv"
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if table == "payments":
        rows.append({"payment_id": "P1", "account_no": "A1", "vendor_invoice_no": "INV-B1",
                     "amount": value, "paid_date": "2024-03-01"})
    else:
        rows[-1][column] = value
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=HEADERS[table].split(","))
        writer.writeheader()
        writer.writerows(rows)

    rejected = _run(data, out)
    assert rejected.returncode == 2, rejected.stdout
    row = 2 if table == "payments" else 3
    assert f"{table}.csv:{row}:" in rejected.stderr
    assert column in rejected.stderr
    assert "finite" in rejected.stderr
    assert "queued for approval" not in rejected.stdout
    assert {file.name: file.read_bytes() for file in out.iterdir()} == previous_review
