# SPDX-License-Identifier: MIT
"""Read-only visit assignments from the existing authorization ledger."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from html import escape

from .data import Patient, PayerRule
from .engine import AuthLedger

ALLOCATION_NOTE = (
    "These are the visits the existing ledger assigned to approved authorization periods. "
    "Used means recorded completed; reserved means recorded scheduled, including past dates "
    "still marked scheduled. Review both source rows against the input exports. "
    "This assignment is not confirmation from a payer."
)


@dataclass(frozen=True)
class AllocatedVisit:
    auth_no: str
    auth_patient_id: str
    auth_payer_id: str
    auth_start: date
    auth_end: date
    auth_visits_authorized: int
    auth_evidence: str
    allocation: str
    visit_id: str
    visit_date: date
    status: str
    visit_type: str
    patient_id: str
    patient_name: str
    clinic: str
    therapist: str
    payer_id: str
    payer_name: str
    visit_evidence: str
    as_of: date
    clinic_timezone: str


def build_allocation_review(
    ledgers: dict[str, AuthLedger],
    payers: dict[str, PayerRule],
    patients: dict[str, Patient],
    as_of: date,
    clinic_timezone: str,
) -> list[AllocatedVisit]:
    """Copy actual ledger membership without recalculating eligibility or capacity.

    Authorization labels already contain the engine's resolved occurrence labels.
    Keep the associated patient, payer, window and source row as well: a visible
    authorization number alone is not an occurrence identity. Preserve the
    engine's visit order within each used/scheduled list.
    """
    result = []
    ordered = sorted(
        ledgers.values(),
        key=lambda led: (
            led.auth.patient_id, led.auth.payer_id, led.auth.start, led.auth.end,
            led.auth.auth_no, led.auth.source_row,
        ),
    )
    for led in ordered:
        auth = led.auth
        for allocation, visits in (("used", led.used), ("scheduled", led.scheduled)):
            for visit in visits:
                patient = patients.get(visit.patient_id)
                payer = payers.get(visit.payer_id)
                result.append(AllocatedVisit(
                    auth_no=auth.auth_no,
                    auth_patient_id=auth.patient_id,
                    auth_payer_id=auth.payer_id,
                    auth_start=auth.start,
                    auth_end=auth.end,
                    auth_visits_authorized=auth.visits_authorized,
                    auth_evidence=auth.source_row,
                    allocation=allocation,
                    visit_id=visit.visit_id,
                    visit_date=visit.visit_date,
                    status=visit.status,
                    visit_type=visit.visit_type,
                    patient_id=visit.patient_id,
                    patient_name=patient.display_name if patient else "",
                    clinic=visit.clinic,
                    therapist=visit.therapist,
                    payer_id=visit.payer_id,
                    payer_name=payer.payer_name if payer else "",
                    visit_evidence=visit.source_row,
                    as_of=as_of,
                    clinic_timezone=clinic_timezone,
                ))
    return result


def render_allocation_section(summary: dict) -> str:
    """Render the complete projection; browser filters never change this output."""
    rows = summary.get("allocation_review")
    e = lambda value: escape(str(value), quote=True)
    start = '<section id="allocated-visits" style="overflow-wrap:anywhere"><h2>Allocated visits</h2>'
    if not isinstance(rows, list):
        return (
            start + "<p>Allocation details are unavailable in this saved report. "
            "Run the worklist to build them.</p></section>"
        )
    context = (
        f"<p>{e(summary.get('allocation_review_note', ALLOCATION_NOTE))}</p>"
        f"<p>Complete review: {len(rows)} allocated visit(s). "
        f"As of {e(summary.get('as_of', 'unrecorded'))}; clinic time zone: "
        f"{e(summary.get('clinic_timezone', 'unrecorded'))}.</p>"
    )
    if not rows:
        return start + context + "<p>No visits were allocated in this report.</p></section>"
    body = []
    for row in rows:
        bucket = {"used": "Used", "scheduled": "Reserved"}.get(row["allocation"], row["allocation"])
        body.append(
            "<tr>"
            f"<td>{e(row['visit_id'])}<br><small>{e(row['visit_type'])}</small></td>"
            f"<td>{e(row['visit_date'])}</td>"
            f"<td>{e(bucket)}<br><small>Recorded {e(row['status'])}</small></td>"
            f"<td>{e(row['patient_name'] or 'Name unavailable')}<br>"
            f"<small>{e(row['patient_id'])}</small></td>"
            f"<td>{e(row['clinic'] or 'Unrecorded')}<br>"
            f"<small>{e(row['therapist'] or 'Therapist unrecorded')}</small></td>"
            f"<td>{e(row['payer_name'] or 'Name unavailable')}<br>"
            f"<small>{e(row['payer_id'])}</small></td>"
            f"<td>{e(row['auth_no'])}<br><small>{e(row['auth_start'])} to {e(row['auth_end'])}; "
            f"{e(row['auth_visits_authorized'])} authorized<br>"
            f"Patient {e(row['auth_patient_id'])}; payer {e(row['auth_payer_id'])}</small></td>"
            f"<td>Visit: {e(row['visit_evidence'] or 'Unrecorded')}<br>"
            f"Authorization: {e(row['auth_evidence'] or 'Unrecorded')}</td>"
            "</tr>"
        )
    table = (
        '<table style="table-layout:fixed"><thead><tr><th scope="col">Visit / type</th><th scope="col">Date</th>'
        '<th scope="col">Allocation / recorded status</th><th scope="col">Patient</th>'
        '<th scope="col">Visit clinic / therapist</th><th scope="col">Payer</th>'
        '<th scope="col">Authorization period</th><th scope="col">Source rows</th>'
        "</tr></thead><tbody>" + "".join(body) + "</tbody></table>"
    )
    return start + context + table + "</section>"
