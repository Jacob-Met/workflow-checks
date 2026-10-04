"""CLI: python -m freightpkt <generate|run|pdf|serve> ..."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="freightpkt", description="Detention/chargeback packet builder (PoC)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="write synthetic sample data")
    g.add_argument("--out", default="sample_data")
    g.add_argument("--loads", type=int, default=24)
    g.add_argument("--seed", type=int, default=7)

    r = sub.add_parser("run", help="process a data dir into packets + reports")
    r.add_argument("--data", default="sample_data")
    r.add_argument("--out", default="out")
    r.add_argument("--pdf", action="store_true", help="also render packets to PDF via local Edge/Chrome")

    s = sub.add_parser("serve", help="local review UI on 127.0.0.1")
    s.add_argument("--data", default="sample_data")
    s.add_argument("--out", default="out")
    s.add_argument("--port", type=int, default=8765)

    a = ap.parse_args(argv)
    if a.cmd == "generate":
        from .synth import generate
        exp = generate(Path(a.out), a.loads, a.seed)
        print(f"wrote synthetic data to {a.out}: {a.loads} loads, "
              f"{len(exp['invoice_defects'])} seeded invoice defects, "
              f"expected detention ${exp['detention_total_cents'] / 100:,.2f}")
        return 0
    if a.cmd == "run":
        from .pipeline import run
        from .models import money
        s = run(Path(a.data), Path(a.out))
        c = s["counts"]
        print(f"events={c['events']} loads={c['loads']} stops={c['stops']}")
        print(f"detention stops={c['detention_stops']}  total={s['detention_total']}  "
              f"late arrivals={c['late_arrivals']}  exceptions={c['exceptions']}")
        print(f"invoice flags={c['invoice_flags']}  packets={c['packets']}  -> {a.out}")
        for f in s["flags"]:
            print(f"  [{f['code']}] {f['load_id']} inv {f['invoice_no']}: {f['detail']}")
        if a.pdf:
            from .pdf import html_to_pdf
            ok = 0
            for p in s["packets"]:
                html = Path(a.out) / p["file"]
                ok += html_to_pdf(html, html.with_suffix(".pdf"))
            print(f"PDF: {ok}/{len(s['packets'])} rendered" + ("" if ok else " (no Edge/Chrome found; HTML kept)"))
        return 0
    if a.cmd == "serve":
        from .web import serve
        serve(Path(a.data), Path(a.out), a.port)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
