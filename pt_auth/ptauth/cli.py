"""CLI: python -m ptauth <generate|run|calendar|serve> ..."""
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
    g.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 9, 28))
    r = sub.add_parser("run", help="build ledger + daily worklist")
    r.add_argument("--data", default="sample_data")
    r.add_argument("--out", default="out")
    r.add_argument("--as-of", type=date.fromisoformat, default=None, help="YYYY-MM-DD (default: sample's as_of, else today)")
    cal = sub.add_parser("calendar", help="export dated open/submitted items from a saved report")
    cal.add_argument("--report", default="out", help="existing report directory; never runs the engine")
    cal.add_argument("--output", required=True, help="new .ics file (existing paths are refused)")
    cal.add_argument("--priority", choices=("P1", "P2", "P3"))
    cal.add_argument("--clinic", help="exact recorded clinic name")
    cal.add_argument("--key", action="append", help="exact work-item key; repeat to select several")
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
        exp = generate(Path(a.out), a.patients, a.seed, a.as_of)
        print(f"SYNTHETIC data written to {a.out} ({a.patients} fake patients, as_of {a.as_of}); "
              f"seeded: {len(exp['uncovered_scheduled'])} uncovered visits, {len(exp['reauth_due'])} re-auths due")
        return 0
    if a.cmd == "run":
        from .data import InputError
        from .report import run
        try:
            s = run(Path(a.data), Path(a.out), a.as_of,
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
        print(f"{c['uncovered_scheduled'] + c['unauthorized_done']} uncovered visits to inspect: "
              f"{Path(a.out) / 'uncovered_visits.csv'}")
        print(f"digest: {Path(a.out) / 'digest.html'}")
        return 0
    if a.cmd == "calendar":
        import json
        from .worklist_calendar import (CalendarInputError, calendar_metadata, load_report,
                                        prepare_calendar, render_calendar, write_calendar)
        try:
            plan = prepare_calendar(load_report(Path(a.report)), a.key,
                                    priority=a.priority, clinic=a.clinic)
            content = render_calendar(plan)
            write_calendar(Path(a.output), content)
        except (CalendarInputError, OSError) as e:
            _calendar_error(f"ERROR: {e}")
            return 2
        try:
            print(json.dumps({**calendar_metadata(plan), "output": str(Path(a.output))},
                             ensure_ascii=True), flush=True)
        except (OSError, UnicodeError):
            _calendar_error("ERROR: The calendar was created, but its receipt could not be delivered. "
                            "Inspect the destination before retrying.")
            return 2
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


def _calendar_error(message: str) -> None:
    """Best-effort ASCII diagnostic; the operation retains its status."""
    try:
        print(message.encode("ascii", "backslashreplace").decode("ascii"),
              file=sys.stderr, flush=True)
    except (OSError, UnicodeError):
        pass


def _entrypoint() -> int:
    """Direct invocation alone owns failed stdout shutdown handling."""
    status = main()
    if status == 2:
        try:
            sys.stdout.flush()
        except (OSError, UnicodeError):
            sys.stdout = None
    return status


if __name__ == "__main__":
    sys.exit(_entrypoint())
