"""CLI: python -m uwatch <generate|run|review|review-report> ..."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="uwatch", description="Utility bill exception checker (review only; never pays)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="write SYNTHETIC sample data + answer key")
    g.add_argument("--out", default="sample_data")
    g.add_argument("--seed", type=int, default=11)
    g.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 9, 28))
    r = sub.add_parser("run", help="check bills, write flags/exceptions/payment queue/report")
    r.add_argument("--data", default="sample_data")
    r.add_argument("--out", default="out")
    r.add_argument("--as-of", type=date.fromisoformat, default=None,
                   help="review date in YYYY-MM-DD form (default: today or synthetic answer key)")
    r.add_argument("--eval-from", type=date.fromisoformat, default=None,
                   help="first service month to review, YYYY-MM-DD (default: about six months ago)")
    review = sub.add_parser("review", help="export/reconcile source-bound exception review notes")
    review.add_argument("--data", type=Path, required=True, help="source CSV export used by the report")
    review.add_argument("--report", type=Path, required=True, help="native summary.json from uwatch run")
    review.add_argument("--previous", type=Path, help="completed prior review worksheet (optional)")
    review.add_argument("--out", type=Path, required=True, help="new review CSV path; never replaces an existing file")
    review_report = sub.add_parser("review-report", help="read or print a saved review worksheet as HTML")
    review_report.add_argument("--worksheet", type=Path, required=True, help="saved uwatch-review-v1 CSV worksheet")
    review_report.add_argument("--out", type=Path, required=True, help="new HTML path in an existing directory; never replaces a file")
    desk = sub.add_parser("review-desk", help="edit current review notes in a local browser desk")
    desk.add_argument("--worksheet", type=Path, required=True, help="saved native review CSV; read-only")
    desk.add_argument("--port", type=int, default=0, help="loopback port; 0 selects an available port")
    a = ap.parse_args(argv)
    if a.cmd == "review-desk":
        from .review_desk import serve
        try:
            serve(a.worksheet, a.port)
        except (OSError, ValueError, KeyError) as exc:
            print(f"uwatch: review desk error: {exc}", file=sys.stderr)
            return 2
        return 0
    if a.cmd == "review-report":
        from .review_report import export_html
        try:
            result = export_html(a.worksheet, a.out)
        except (OSError, ValueError, KeyError) as exc:
            print(f"uwatch: review report error: {exc}", file=sys.stderr)
            return 2
        print(f"review report: {result['current']} current findings; {result['history']} prior findings")
        print(f"worksheet SHA256: {result['worksheet_sha256']}")
        print(f"report: {a.out}")
        return 0
    if a.cmd == "generate":
        from .synth import generate
        exp = generate(Path(a.out), a.seed, a.as_of)
        print(f"SYNTHETIC data written to {a.out}: {len(exp['flags'])} seeded anomalies, "
              f"{len(exp['decoys'])} seasonal decoys, answer key in expected.json")
        return 0
    if a.cmd == "review":
        from .review import reconcile
        try:
            result = reconcile(a.data, a.report, a.out, a.previous)
        except (OSError, ValueError, KeyError) as exc:
            print(f"uwatch: review error: {exc}", file=sys.stderr)
            return 2
        print(f"review: {result['current']} current findings {result['statuses']}; "
              f"{result['history']} historical rows; annotations do not change payment eligibility")
        print(f"worksheet: {result['worksheet']}")
        return 0
    from .engine import run
    try:
        s = run(Path(a.data), Path(a.out), a.as_of, eval_from=a.eval_from)
    except (OSError, ValueError, KeyError) as exc:
        print(f"uwatch: input error: {exc}", file=sys.stderr)
        return 2
    label = "[SYNTHETIC] " if s["data_mode"] == "synthetic" else ""
    print(f"{label}as_of {s['as_of']}: {s['accounts']} accounts, {s['bills']} bills; "
          f"{s['flags']} flags {s['by_code']}; {s['exceptions']} exceptions; "
          f"{s['payment_queue']} bills (${s['payment_queue_total']:,.2f}) queued for approval (not paid)")
    print(f"naive trailing-3 rule would add {len(s['naive_trailing3_hits'])} seasonal false flags")
    print(f"report: {Path(a.out) / 'report.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
