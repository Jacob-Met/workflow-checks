"""Read-only appointment detail from the tracker's existing uncovered visits."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from html import escape

from .data import Patient, PayerRule, Visit

UNCOVERED_NOTE = (
    "These appointments have no covering approved authorization in this report: "
    "scheduled visits on or after the as-of date, and visits recorded as completed. "
    "Check the referenced source rows and authorization worklist. "
    "Past appointments still marked scheduled remain in Visit status review. "
    "This view does not change attendance, authorization rules or staff work states."
)


@dataclass(frozen=True)
class UncoveredVisit:
    visit_id: str
    visit_date: date
    status: str
    patient_id: str
    patient_name: str
    clinic: str
    therapist: str
    payer_id: str
    payer_name: str
    payer_rules_known: bool
    visit_type: str
    evidence: str


def build_uncovered_review(
    uncovered: list[Visit],
    payers: dict[str, PayerRule],
    patients: dict[str, Patient],
    as_of: date,
) -> list[UncoveredVisit]:
    """Project, without recalculating, the visits counted by the existing report.

    Dates, statuses, identifiers and source rows are the existing loader/engine
    values. In particular, a completed row keeps its recorded date even if that
    date is in the future. Missing patient names or payer rules stay missing.
    """
    result = []
    for visit in uncovered:
        if not (
            visit.status == "completed"
            or (visit.status == "scheduled" and visit.visit_date >= as_of)
        ):
            continue
        patient = patients.get(visit.patient_id)
        payer = payers.get(visit.payer_id)
        result.append(UncoveredVisit(
            visit_id=visit.visit_id,
            visit_date=visit.visit_date,
            status=visit.status,
            patient_id=visit.patient_id,
            patient_name=patient.display_name if patient else "",
            clinic=visit.clinic,
            therapist=visit.therapist,
            payer_id=visit.payer_id,
            payer_name=payer.payer_name if payer else "",
            payer_rules_known=payer is not None,
            visit_type=visit.visit_type,
            evidence=visit.source_row,
        ))
    return sorted(result, key=lambda row: (
        row.visit_date, row.patient_id, row.payer_id, row.visit_id, row.evidence
    ))


def render_uncovered_section(summary: dict) -> str:
    """Render the complete saved review; an older summary is not an empty review."""
    review = summary.get("uncovered_review")
    heading = "<h2>Uncovered visits &mdash; scheduled and completed appointments</h2>"
    if not isinstance(review, list):
        return heading + "<p>Run worklist to build uncovered-visit details for this saved report.</p>"
    def e(value):
        return escape(str(value))

    note = "<p>" + escape(UNCOVERED_NOTE) + "</p>"
    if not review:
        return heading + note + "<p>No appointments are in this review for this report.</p>"
    rows = []
    for row in review:
        payer = e(row["payer_name"] or "Name unavailable")
        if not row["payer_rules_known"]:
            payer += "<br><small>Rules unavailable</small>"
        rows.append(
            f"<tr><td>{e(row['visit_id'])}<br><small>{e(row['visit_type'])}</small></td>"
            f"<td>{e(row['visit_date'])}</td><td>{e(row['status'])}</td>"
            f"<td>{e(row['patient_name'] or 'Name unavailable')}<br><small>{e(row['patient_id'])}</small></td>"
            f"<td>{e(row['clinic'] or 'Unrecorded')}</td><td>{e(row['therapist'] or 'Unrecorded')}</td>"
            f"<td>{payer}<br><small>{e(row['payer_id'])}</small></td>"
            f"<td>{e(row['evidence'] or 'Unrecorded')}</td></tr>"
        )
    return (heading + note + f"<p>{len(review)} appointments; complete review, ordered by date.</p>"
            + "<table><thead><tr><th scope='col'>Visit / type</th><th scope='col'>Date</th>"
              "<th scope='col'>Recorded status</th><th scope='col'>Patient</th>"
              "<th scope='col'>Visit clinic</th><th scope='col'>Therapist</th>"
              "<th scope='col'>Payer</th><th scope='col'>Source row</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>")
