"""Rebuild the static sample-output site in docs/ by running each demo on its bundled synthetic data.

Usage (from the repo root):  python scripts/build_pages.py
Runs the three test suites first and stops if any fail. Standard library + pytest only.
"""
from __future__ import annotations
import csv, html, json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
AS_OF = "2026-09-28"  # fixed review date so the published outputs are reproducible
DEMOS = [
    ("freight_packets", ["-m", "freightpkt", "run", "--data", "sample_data", "--out", "../docs/freight"]),
    ("pt_auth", ["-m", "ptauth", "run", "--data", "sample_data", "--out", "../docs/pt", "--as-of", AS_OF]),
    ("utility_watch", ["-m", "uwatch", "run", "--data", "sample_data", "--out", "../docs/utility", "--as-of", AS_OF]),
]

def run(args, cwd):
    print("+", " ".join(args), f"(in {cwd.name})", flush=True)
    subprocess.run([sys.executable, *args], cwd=cwd, check=True)

def main() -> None:
    for folder, _ in DEMOS:
        run(["-m", "pytest", "-q"], ROOT / folder)
    for sub in ("freight", "pt", "utility"):
        shutil.rmtree(DOCS / sub, ignore_errors=True)
    DOCS.mkdir(exist_ok=True)
    for folder, args in DEMOS:
        run(args, ROOT / folder)
    (DOCS / ".nojekyll").write_text("")
    f = json.loads((DOCS / "freight" / "summary.json").read_text())["counts"]
    p = json.loads((DOCS / "pt" / "summary.json").read_text())["counts"]
    u = json.loads((DOCS / "utility" / "summary.json").read_text())
    write_index(f, p, u)
    print("freight", f, "\npt", p, "\nutility flags", u["flags"], "exceptions", u["exceptions"])

REPO = "https://github.com/Jacob-Met/workflow-checks"

def table(path: Path, cols: list[str], limit: int = 6) -> str:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(r.get(c, ''))}</td>" for c in cols) + "</tr>" for r in rows[:limit])
    more = f"<p class=m>Showing {min(limit, len(rows))} of {len(rows)} rows. <a href='{path.relative_to(DOCS).as_posix()}'>Full CSV</a></p>"
    return f"<table><tr>{head}</tr>{body}</table>{more}"

def write_index(f: dict, p: dict, u: dict) -> None:
    packets = sorted((DOCS / "freight" / "packets").glob("*.html"))
    plinks = " ".join(f"<a href='freight/packets/{x.name}'>{x.stem}</a>" for x in packets)
    out = f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>workflow-checks: sample outputs (synthetic data)</title>
<meta name=description content="Sample outputs from three back-office check demos: freight detention packets and carrier invoice audit, PT authorization worklist, utility bill exceptions. Synthetic data.">
<style>body{{font:15px/1.5 system-ui,Segoe UI,Arial,sans-serif;color:#1b1f24;max-width:1000px;margin:24px auto;padding:0 16px}}
.banner{{background:#fff4ce;border:1px solid #d8a800;padding:8px 12px;border-radius:6px;font-weight:600}}
table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border:1px solid #c9ced6;padding:4px 6px;text-align:left;vertical-align:top}}th{{background:#f1f3f5}}
h2{{border-bottom:2px solid #1b1f24;padding-bottom:4px;margin-top:36px}}.m{{color:#555;font-size:13px}}code{{background:#f1f3f5;padding:1px 4px}}</style></head><body>
<h1>workflow-checks: sample outputs</h1>
<p class=banner>Synthetic data, not deployed in any real operation. Every company, person, patient, account and amount here was invented by a seeded generator. Nothing was sent, paid or filed.</p>
<p>These pages are the actual output of running the three demos in <a href="{REPO}">the repository</a> on their bundled sample data (review date {AS_OF}), after their test suites passed. Rebuild them yourself with <code>python scripts/build_pages.py</code>.</p>
<ul><li><a href="#freight">Freight: detention packets and carrier invoice audit</a></li><li><a href="#pt">Physical therapy: authorization worklist</a></li><li><a href="#utility">Utilities: bill exceptions and payment queue</a></li></ul>

<h2 id=freight>Freight: detention packets and carrier invoice audit</h2>
<p>Input: a TMS load list, telematics or tracking stop events, rate confirmations and carrier invoices for {f['loads']} loads. Output: {f['packets']} draft detention/late-arrival packets, {f['invoice_flags']} invoice flags, {f['fines']} evidence-backed fines, {f['exceptions']} exceptions held for a person, and a settlement worksheet ({f['settlement_ready']} READY, {f['settlement_hold']} HOLD).</p>
<p><b>Draft packets</b> (one per load; calculation, evidence timeline, approval block): {plinks}</p>
<p><b>Invoice flags</b></p>{table(DOCS/'freight'/'invoice_flags.csv', ['invoice_no','load_id','flag','detail','variance','evidence'])}
<p><b>Settlement worksheet</b></p>{table(DOCS/'freight'/'settlement.csv', ['invoice_no','load_id','invoiced','approved','fines','net_payable','status','hold_reasons'])}
<p><b>Exceptions (never claimed, sent to a person)</b></p>{table(DOCS/'freight'/'exceptions.csv', ['load_id','stop','reason','evidence'])}

<h2 id=pt>Physical therapy: authorization worklist</h2>
<p>Input: a visit schedule, authorizations, a per-payer rules table and patients ({p['patients']} synthetic patients, {p['visits']} visits, {p['auths']} auths). Output: a prioritized daily worklist of {p['worklist']} items ({p['p1']} P1, {p['p2']} P2), each with a reason code, a submit-by date and the payer checklist. <a href="pt/digest.html">Open the printable daily digest</a>.</p>
{table(DOCS/'pt'/'worklist.csv', ['priority','patient_id','payer','auth_no','reasons','visits_remaining','submit_by','detail'])}

<h2 id=utility>Utilities: bill exceptions and payment queue</h2>
<p>Input: utility accounts, {u['bills']} bills, payments and unit occupancy for {u['accounts']} accounts. Output: {u['flags']} flags (spikes against the same month last year, rate changes, duplicates, overlaps, missing bills, late fees, payment mismatches, vacant-unit usage), {u['exceptions']} exceptions, and {u['payment_queue']} clean bills queued for approval (not paid). <a href="utility/report.html">Open the full report</a>.</p>
{table(DOCS/'utility'/'flags.csv', ['property','utility','account_no','code','detail','evidence'], 12)}

<h2>Want this on your own exports?</h2>
<p>A scoped pilot runs on your own redacted exports and is compared against a manual audit. See <a href="https://jacobmetoyer.com">jacobmetoyer.com</a>. Code: <a href="{REPO}">{REPO}</a> (MIT).</p>
</body></html>
"""
    (DOCS / "index.html").write_text(out, encoding="utf-8")

if __name__ == "__main__":
    main()
