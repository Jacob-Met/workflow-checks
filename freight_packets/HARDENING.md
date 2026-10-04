# Freight packet rule audit

This audit compares the promises in `README.md` with the code after the hardening changes. A packet and a settlement row remain drafts for human review.

| README rule | Code match | Evidence and boundary |
| --- | --- | --- |
| Match each stop to an arrival near its appointment and its departure; missing entry or exit is an exception. | Yes | `detention.evaluate_load` uses a 12-hour-before/24-hour-after appointment window and requires a later exit within 24 hours from the same asset. Tracking arrivals and departures must also come from the same source row. Missing arrival, missing departure, and departure before arrival do not create a claim. |
| Free-time clock starts at `max(arrival, appointment)`. | Yes | Early arrival cannot start free time early; `test_early_arrival_clock_starts_at_appointment` and the midnight regression cover this. |
| Arrival later than appointment plus grace forfeits detention and is a service-failure candidate. | Yes | `evaluate_load` uses a strict `>` comparison. A rate-con parse warning overrides the candidate and sends it to review. |
| Billable time is rounded down to the rate-con increment, multiplied by the hourly rate, then capped per stop. | Yes | Minutes are floored to the increment. Fractional cents are rounded half up. The cap is applied after multiplication. |
| Missing or unparsed rate-con terms go to the exception queue rather than being guessed. | Yes | The parser records warnings, including an hourly detention rate missing because the rate uses another unit. Warning stops have zero claim amount; settlement is held with zero approved amount. |
| Invoice lines are compared to rate-con, POD flag, and supported detention; duplicate invoices are flagged. | Yes | `invoice_match` emits the documented flags. Every copy of an ambiguous carrier/invoice number is now flagged and held. |
| Carrier fines use only the supplied matrix and evidence; asset loads are never fined. | Yes | `assess_fines` only considers brokered loads and configured rules. Late arrival, tracking gaps, missing photos, and late POD each use evidence pointers. The sample matrix is illustrative. |
| POD is late only after 48 hours from final departure; missing final departure is an exception. | Yes, when a POD document exists | The comparison is strict `> 48 hours`, so exactly 48 hours is on time. Unknown final departure creates a POD-timeliness exception, not a fine. Missing POD is handled by the TMS POD flag and settlement hold; the document feed itself is not a complete POD inventory. |
| Each fine uses carrier invoice date as notice and has a 7-day dispute window; timely disputes suspend deduction. | Yes, by calendar date | The notice field is a date, so the seventh calendar day is inclusive through 23:59. The earliest dispute row for a load/fine controls, even if a later follow-up row exists. A dispute on the eighth day is late. This is a calendar-day policy, not an exact 168-hour window. |
| Settlement is approved lines capped at rate-con/telematics support, less undisputed fines, with READY or HOLD. | Yes | Holds cover duplicate invoice, missing TMS POD flag, missing rate con, rate-con parse warnings, and billed detention with unresolved stop exceptions. Rate-con warnings have zero provisional approved amount. |
| Claims have stable IDs and all decisions have source pointers in an append-only audit. | Yes for generated decisions | Claim IDs hash load, stop, timestamps, and amount. Pipeline appends decision records to `audit.jsonl`; source pointers appear in claims, flags, and fines. |

## Regressions added

The following tests failed against the original code and now pass:

- `test_dst_fallback_stop_uses_elapsed_time_across_offset_change`: offset timestamps were stripped without conversion, turning a 45-minute stop into an exception.
- `test_duplicate_load_number_is_rejected_with_both_source_rows`: a duplicate TMS load silently replaced the first row.
- `test_ratecon_warning_never_exposes_provisional_claim_amount`: an exception still exposed a billable amount.
- `test_detention_fractional_cent_rounds_half_up`: Python's ties-to-even rounding underpaid half-cent cases.
- `test_earliest_dispute_within_inclusive_seventh_day_wins`: a later follow-up dispute overwrote a timely dispute.
- `test_all_copies_of_duplicate_invoice_are_held`: the first copy of a duplicate invoice was still READY.
- `test_partial_ratecon_parse_holds_settlement`: an incomplete rate con produced a READY settlement and provisional approved amount.
- `test_orphan_tracking_departure_cannot_close_different_row`: an orphan departure closed an unrelated arrival.
- `test_brokered_load_ignores_tractor_geofence_from_other_load`: a brokered load could claim another load's tractor events.
- `test_asset_arrival_cannot_be_closed_by_trailer_exit`: a tractor arrival could be closed by a trailer exit.
- `test_packet_for_real_input_does_not_label_it_synthetic`: real-input packets carried the synthetic-data banner.

Additional boundary tests cover an appointment crossing midnight, missing arrival, departure before arrival, an unsupported detention unit, and POD received exactly 48 hours after departure.

## Live-feed limits to resolve with the dispatcher

- A timestamp with an explicit UTC offset is converted to UTC for calculation and packet display. A timestamp without an offset remains as exported. A feed that mixes offset timestamps with facility-local timestamps can be miscompared; all timestamps for a stop should use explicit offsets if it can cross a time-zone or daylight-saving change.
- The parser handles two text rate-con layouts. Scanned PDFs and unfamiliar clauses still need human review; the client's rate confirmations and fine/dispute policy must be mapped before using READY rows for payment.
- `pod_received` comes from the TMS load export. A missing `POD` row in `documents.csv` by itself is not treated as proof that the POD is missing. The pilot should reconcile these sources.
