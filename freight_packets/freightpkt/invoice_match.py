"""Carrier invoice vs rate-con vs POD match.

Flags (each carries a reason and the evidence pointers):
  LINEHAUL_MISMATCH   invoiced linehaul != rate-con linehaul
  FUEL_MISMATCH       invoiced fuel != rate-con fuel
  DETENTION_UNSUPPORTED  invoiced detention > detention supported by telematics
  ACCESSORIAL_NOT_ON_RATECON  e.g. TONU / lumper billed but not agreed
  ACCESSORIAL_OVER_RATECON    accessorial above agreed amount
  TOTAL_MISMATCH      header total != sum of lines
  MISSING_POD         no proof of delivery on file for the load
  DUPLICATE_INVOICE   same carrier + invoice number seen on more than one load/row
  NO_RATECON          invoice references a load with no rate-con
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .models import Invoice, Load, RateCon, money

TOLERANCE_CENTS = 0  # exact match by default; client can loosen (e.g. 100 = $1)


@dataclass
class Flag:
    invoice_no: str
    load_id: str
    carrier: str
    code: str
    detail: str
    invoiced_cents: int | None = None
    expected_cents: int | None = None
    evidence: list[str] = field(default_factory=list)

    @property
    def variance_cents(self) -> int | None:
        if self.invoiced_cents is None or self.expected_cents is None:
            return None
        return self.invoiced_cents - self.expected_cents


def match_invoices(invoices: list[Invoice], loads: dict[str, Load],
                   ratecons: dict[str, RateCon],
                   supported_detention: dict[str, int]) -> list[Flag]:
    flags: list[Flag] = []

    seen = defaultdict(list)
    for inv in invoices:
        seen[(inv.carrier.lower(), inv.invoice_no)].append(inv)
    for (_, no), invs in seen.items():
        if len(invs) > 1:
            for inv in invs:
                flags.append(Flag(inv.invoice_no, inv.load_id, inv.carrier, "DUPLICATE_INVOICE",
                                  f"invoice #{no} also billed on load(s) "
                                  + ", ".join(i.load_id for i in invs if i is not inv),
                                  inv.total_cents, 0, [i.source_row for i in invs]))

    for inv in invoices:
        ev = [inv.source_row]
        load = loads.get(inv.load_id)
        rc = ratecons.get(inv.load_id)
        by_code = defaultdict(int)
        for ln in inv.lines:
            by_code[ln.code] += ln.amount_cents

        line_sum = sum(by_code.values())
        if abs(line_sum - inv.total_cents) > TOLERANCE_CENTS:
            flags.append(Flag(inv.invoice_no, inv.load_id, inv.carrier, "TOTAL_MISMATCH",
                              f"header total {money(inv.total_cents)} != line sum {money(line_sum)}",
                              inv.total_cents, line_sum, ev))

        if load is not None and not load.pod_received:
            flags.append(Flag(inv.invoice_no, inv.load_id, inv.carrier, "MISSING_POD",
                              "no POD on file; hold payment until POD received",
                              evidence=ev + [load.source_row]))

        if rc is None:
            flags.append(Flag(inv.invoice_no, inv.load_id, inv.carrier, "NO_RATECON",
                              "no rate confirmation found for this load", evidence=ev))
            continue
        rc_ev = ev + [rc.source]

        def cmp(code, expected, flag_code, label):
            got = by_code.get(code, 0)
            if abs(got - expected) > TOLERANCE_CENTS:
                flags.append(Flag(inv.invoice_no, inv.load_id, inv.carrier, flag_code,
                                  f"{label}: invoiced {money(got)} vs rate-con {money(expected)}",
                                  got, expected, rc_ev))

        cmp("LINEHAUL", rc.linehaul_cents, "LINEHAUL_MISMATCH", "linehaul")
        cmp("FUEL", rc.fuel_cents, "FUEL_MISMATCH", "fuel surcharge")

        det_billed = by_code.get("DETENTION", 0)
        det_supported = supported_detention.get(inv.load_id, 0)
        if det_billed > det_supported + TOLERANCE_CENTS:
            flags.append(Flag(inv.invoice_no, inv.load_id, inv.carrier, "DETENTION_UNSUPPORTED",
                              f"detention invoiced {money(det_billed)} but telematics supports "
                              f"{money(det_supported)}", det_billed, det_supported, rc_ev))

        for code, amt in by_code.items():
            if code in ("LINEHAUL", "FUEL", "DETENTION"):
                continue
            agreed = rc.accessorials_cents.get(code)
            if agreed is None:
                flags.append(Flag(inv.invoice_no, inv.load_id, inv.carrier,
                                  "ACCESSORIAL_NOT_ON_RATECON",
                                  f"{code} {money(amt)} billed but not on rate-con", amt, 0, rc_ev))
            elif amt > agreed + TOLERANCE_CENTS:
                flags.append(Flag(inv.invoice_no, inv.load_id, inv.carrier,
                                  "ACCESSORIAL_OVER_RATECON",
                                  f"{code}: invoiced {money(amt)} vs agreed {money(agreed)}",
                                  amt, agreed, rc_ev))
    flags.sort(key=lambda f: (f.load_id, f.invoice_no, f.code))
    return flags
