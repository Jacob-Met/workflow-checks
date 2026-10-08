"""CLI: python -m ptauth <generate|run|serve> ..."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ptauth", description="PT authorization tracker (PoC, synthetic data)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="write SYNTHETIC sample data")
    g.add_argument("--out", default="sample_data")
    g.add_argument("--patients", type=int, default=40)
    g.add_argument("--seed", type=int, default=21)
    g.add_argument("--as-of", default="2026-09-28")
    r = sub.add_parser("run", help="build ledger + daily worklist")
    r.add_argument("--data", default="sample_data")
    r.add_argument("--out", default="out")
    r.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: sample's as_of, else today)")
    s = sub.add_parser("serve", help="local UI on 127.0.0.1")
    s.add_argument("--data", default="sample_data")
    s.add_argument("--out", default="out")
    s.add_argument("--port", type=int, default=8766)
    for command in (r, s):
        command.add_argument("--clinic-timezone", default=None, metavar="IANA_ZONE",
                             help="clinic zone for offset-bearing timestamps (default: system local)")
    a = ap.parse_args(argv)

    if a.cmd == "generate":
        from .synth import generate
        exp = generate(Path(a.out), a.patients, a.seed, date.fromisoformat(a.as_of))
        print(f"SYNTHETIC data written to {a.out} ({a.patients} fake patients, as_of {a.as_of}); "
              f"seeded: {len(exp['uncovered_scheduled'])} uncovered visits, {len(exp['reauth_due'])} re-auths due")
        return 0
    if a.cmd == "run":
        from .data import InputError
        from .report import run
        try:
            s = run(Path(a.data), Path(a.out), date.fromisoformat(a.as_of) if a.as_of else None,
                    clinic_timezone=a.clinic_timezone)
        except (InputError, FileNotFoundError) as e:
            print(f"ERROR: {e}\nCheck the input settings and files and run again; no outputs were written.", file=sys.stderr)
            return 2
        c = s["counts"]
        print(f"[SYNTHETIC] as_of {s['as_of']}: {c['patients']} patients, {c['visits']} visits, {c['auths']} auths")
        print(f"clinic time zone: {s['clinic_timezone']}")
        print(f"worklist: {c['worklist']} items (P1 {c['p1']}, P2 {c['p2']}, P3 {c['p3']}); "
              f"{c['uncovered_scheduled']} scheduled visits uncovered; {c['unauthorized_done']} completed w/o auth")
        for x in s["worklist"][:12]:
            print(f"  {x['priority']} {x['patient_id']} {x['payer_id']:<9} {x['auth_no'] or '-':<11} "
                  f"{','.join(x['reasons']):<34} submit_by={x['submit_by'] or '-'}")
        if len(s["worklist"]) > 12:
            print(f"  ... {len(s['worklist']) - 12} more in {a.out}/worklist.csv")
        print(f"{c['past_scheduled']} past scheduled visits need status review: "
              f"{Path(a.out) / 'visit_status_review.csv'}")
        print(f"digest: {Path(a.out) / 'digest.html'}")
        return 0
    if a.cmd == "serve":
        from .data import InputError
        from .web import serve
        try:
            serve(Path(a.data), Path(a.out), a.port, clinic_timezone=a.clinic_timezone)
        except InputError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
