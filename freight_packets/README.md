# Freight detention / chargeback packet builder (PoC)

> **Proof of concept on SYNTHETIC data.** All companies, facilities, drivers, units and amounts are fictional. Nothing is sent, filed or invoiced. Every packet is a **DRAFT pending human approval**.

Built for asset-based carriers and brokers whose billing staff validate detention claims, verify fines against tracking data and proofs of delivery, and reconcile carrier invoices against rate confirmations. It works for any carrier or broker with a tracking export (FourKites-style stop events for brokered loads, or a Samsara-style ELD geofence export for its own fleet), a TMS load list, rate cons and carrier invoices.

## What it does

1. **Ingests**
   - The telematics geofence export. Two formats are accepted:
     - A Samsara-style CSV (`Vehicle Name, Driver Name, Address Name, Event, Time, Lat, Lon`). Header aliases are tolerated.
     - A Samsara-API-like JSON (`{"data":[{"vehicle":{"name"},"address":{"name"},"eventType":"GeofenceEntry",...}]}`).
   - A stop-level tracking export (`tracking*.csv`, FourKites-style): one row per load stop with `Load Number, Stop Name, Actual Arrival, Actual Departure` (aliases tolerated). Events are keyed by load number, so brokered loads need no tractor ID. A blank departure becomes an exception, never a guess. *The column names are generic; a pilot maps them to the client's actual report.*
   - `loads.csv`, the TMS export: load, customer, carrier, tractor, trailer, POD flag, rate-con file and `mode` (`asset` or `brokered`).
   - Rate confirmations, as the text layer of the PDF. Two broker layouts are parsed by regex: free time, detention $/hr, billing increment, per-stop cap, late grace, lumper, linehaul, fuel, and stops with appointments. If a term is missing, the parser records a **parse warning** and routes the load to the exception queue instead of guessing.
   - `carrier_invoices.csv`, with one row per invoice line (LINEHAUL, FUEL, DETENTION, LUMPER, TONU, ...).
2. **Detects detention.** For each rate-con stop, it finds the tractor's geofence entry and exit near the appointment, ignoring pass-through geofences on the route. It then applies these rules:
   - The free-time clock starts at **max(arrival, appointment)**, so arriving early doesn't earn detention.
   - Arriving after appointment + grace **forfeits detention** and is flagged as a late-arrival or service-failure chargeback candidate.
   - Billable time is rounded **down** to the rate-con increment and capped per stop if the rate con says so.
   - An entry with no exit, a stop with no entry, or a rate con with warnings goes to the **exception queue** and is never claimed.
3. **Matches carrier invoices against the rate con, the POD and telematics.** It flags `LINEHAUL_MISMATCH`, `FUEL_MISMATCH`, `DETENTION_UNSUPPORTED` (invoiced detention above what telematics supports), `ACCESSORIAL_NOT_ON_RATECON`, `ACCESSORIAL_OVER_RATECON`, `TOTAL_MISMATCH`, `DUPLICATE_INVOICE` and `MISSING_POD`.
4. **Drafts packets.** It writes one HTML packet per load with detention or a late arrival. Each packet has:
   - a header and the rate-con terms
   - a stop table with a dwell bar (free vs. over)
   - the calculation shown step by step
   - the geofence **evidence timeline**, with a file:row pointer for every event
   - the invoice flags
   - an approval block

   Use `--pdf` to render PDFs with a locally installed Edge or Chrome, in headless mode with no network. Any browser can also "Print → Save as PDF".
5. **Assesses carrier fines and builds a settlement worksheet** (brokered loads; only when `fines_schedule.csv` is present).
   - Fines come **only from evidence on file**: late pickup/delivery (from the detention engine), tracking gaps (arrival without departure), missing pickup/delivery compliance photos and late POD (from `documents.csv`, 48h after final departure).
   - If the evidence needed to judge a rule is missing (e.g. no final departure, so POD lateness can't be measured), the load goes to the exception queue instead of being fined. Own-fleet (`asset`) loads are never fined.
   - Each fine gets a notice date (carrier invoice date) and a **7-day dispute deadline**. A dispute in `disputes.csv` received inside the window holds the fine (not deducted); a late dispute is recorded but the fine stands.
   - The settlement worksheet (`settlement.csv`) gives, per carrier invoice: approved amount (lines capped at rate-con terms and telematics-supported detention), fines deducted, **net payable**, and **READY / HOLD** for finance and factoring. Holds: duplicate invoice, missing POD, missing rate con, and detention billed on a load with an unresolved stop exception.
   - The fines schedule in the sample is a placeholder; a pilot loads the client's own matrix.
6. **Writes CSVs and a log.** It also writes `detention_claims.csv`, `invoice_flags.csv`, `fines.csv`, `settlement.csv`, `exceptions.csv` and `summary.json`, plus `audit.jsonl`, an append-only log of every decision with evidence pointers. Each claim has an idempotent `claim_id` (a hash of the evidence), so re-runs never mint duplicate claims.

Only the Python 3.10+ standard library is needed at runtime. Tests use `pytest`.

## Run it

```powershell
cd freight_packets
python -m freightpkt generate --out sample_data --loads 24 --seed 7   # synthetic data + answer key
python -m freightpkt run --data sample_data --out out [--pdf]         # packets + CSVs
python -m freightpkt serve --data sample_data --out out               # http://127.0.0.1:8765/
python -m pytest -q
```

The review UI is a single page with no CDN or external requests, and it binds to 127.0.0.1 only. It has these parts:
- summary cards
- a packet list with the packet preview
- **Approve / Needs adjust / Reject** buttons with a note, recorded to `decisions.json` and `audit.jsonl`
- tabs for Invoice flags, the Exception queue, All stops, and Downloads
- a "Regenerate sample" button that takes a seed

### Reviewing a changed packet

A saved review applies to the generated packet and its per-load stops, invoice flags, fines, settlement and exceptions. The app records a deterministic evidence version covering those records and the actual packet bytes. Re-running unchanged data retains the review; a changed packet or supporting report shows **review again** and its earlier approval is excluded from the approved total. Changes to another load and the run timestamp do not invalidate an unchanged packet. Re-run the pipeline after editing source inputs so the new results can be reviewed.

The browser submits the evidence version it displayed. A stale browser receives HTTP 409 and refreshes the packet for a new review; it never repeats the decision automatically. A missing or unreadable current packet cannot be approved. Older decisions without an evidence version require one new review. Previous decisions and notes remain in `decisions.json` history, including after Clear or sample regeneration; each saved update is also appended to `audit.jsonl` with its evidence version. A storage error asks the reviewer to reload and inspect the saved decision rather than assume the update succeeded or retry it.

The local server serializes its own pipeline runs and review updates, and replaces the decision file atomically. Run one server per output directory; do not run the CLI or another writer against that directory while reviewing. This is local draft review, not payment approval or a multi-user production service.

### Downloading one saved review

In the Packets tab, choose a load and use **Download saved review**. Unzip the
file and open `index.html` for a readable cover with the saved decision, note,
previous reviews and links to the original packet. Save or undo a note edit
before downloading; text that has not been saved is not silently exported.
**Cancel download** stops a pending browser download without changing a review.

The ZIP contains exactly one load's generated packet, its six supporting report
sections, and its saved decision/history. The JSON retains the original
file:row references and the same packet/report evidence version used by the
review app. A separate identity binds the exact saved review that was displayed,
including its history. `manifest.json` records the member sizes and SHA-256
checksums. Other loads, global decisions/audit files and original input files
are not included.

The server takes the snapshot under its existing review lock. If either the
shown evidence or saved review changes before export, it refuses the download;
reload and inspect the current record before trying again. A missing or
unreadable packet cannot be bundled. The browser also discards a pending reply
when the selected view or note changes. A refused, canceled or failed download
does not write a decision or automatically retry.

Unreviewed, cleared, stale and older unbound reviews remain distinct on the
cover. An earlier approval is not presented as approval of changed evidence.
The original packet remains a draft, and the bundle is a snapshot: later app
changes do not update it. Nothing is sent, filed, invoiced or paid.

## Verification

The freight test suite includes real local HTTP checks for unchanged and changed evidence, stale clients, missing packets, legacy decisions, history, concurrent reviews and failed writes. An optional browser check runs with an installed Playwright and Chromium: `node tests/review_browser_smoke.cjs` from `freight_packets`. Set `BROWSER_BIN` for an existing Chromium executable and `PYTHON` if the interpreter is not named `python3`. It uses a disposable synthetic fixture and local server, and retains its screenshots and receipt under the process temporary directory.

`sample_data/expected.json` is an answer key that the generator computes **independently** of the pipeline, from the seeded arrival and departure times. The tests assert three things:
- The detention total and **every per-stop amount and status** match the answer key.
- **100% of seeded invoice defects** are flagged, and clean invoices are not.
- Every missing-exit stop lands in the exception queue.
- Every seeded fine (code, amount and dispute status), every settlement hold and every "POD timeliness not measurable" exception matches the answer key, and detention totals are unchanged when half the loads come in through the tracking export instead of geofences.

This was checked on seeds 7 and 11 in the tests, and on 1, 2, 3, 99 and 1234 manually. The fines/settlement answer key is tested on seeds 3, 7 and 99, and was checked on 1, 2, 3, 7, 11, 99, 1234 and 2026 at 24 and 40 loads (16/16 exact).

## 2-minute demo script (screen-record)

1. **(0:00) Terminal.** Run `python -m freightpkt generate` and then `python -m freightpkt run`.
   - Say: *"24 synthetic loads: a Samsara-style geofence export, rate cons from two broker layouts, and carrier invoices."*
   - Point at the output: detention total, late arrivals, exceptions, and the list of invoice flags.
2. **(0:25) Start the UI.** Run `python -m freightpkt serve` and open http://127.0.0.1:8765.
   - Point at the cards: *"$2,251 in detention supported by telematics, 15 draft packets, 11 invoice flags, and 5 items that need a human."*
3. **(0:40) Packets tab.** Click a load and scroll the packet.
   - Say: *"Rate-con terms parsed from the PDF text. Geofence in and out for each stop. Free time starts at the appointment, not at early arrival. Rounded down to the 15-minute increment. Here's the evidence timeline, with a row pointer back to the Samsara export."*
4. **(1:05) Approve it.** Type a note and click **Approve**.
   - Say: *"Nothing is sent. Approval is logged to an append-only audit file."* The "approved" card updates.
5. **(1:15) Invoice flags tab.**
   - Say: *"The carrier billed $200 detention and telematics supports $75. Here's a duplicate invoice number on two loads, a TONU that isn't on the rate con, and a load with no POD, so payment is held."*
6. **(1:35) Exception queue.**
   - Say: *"A geofence entry with no exit is never guessed. It comes to a person."*
7. **(1:45) Carrier fines → Settlement tabs.**
   - Say: *"Fines only where the evidence is on file: no delivery photos, POD 60 hours late. This one was disputed inside the 7-day window, so it's held, not deducted. The settlement sheet is what goes to finance and factoring: approved, fines, net, READY or HOLD."*
8. **(2:05) Downloads.** Show `detention_claims.csv` and the PDF packet (`run --pdf`).
   - Say: *"On your real data, this is a one-week PoC. Send a redacted Samsara export, 10 rate cons and the matching loads."*

## What a real pilot needs from the client

- **Tracking for brokered loads.** A FourKites (or similar) stop-level report for 2–4 weeks, with actual arrival/departure per stop, so the column mapping can be confirmed.
- **Fines matrix and dispute policy.** The client's carrier fines schedule, what counts as notice (invoice date? email?), the dispute window, and where compliance photos and PODs are logged.
- **Telematics (own fleet).** A Samsara geofence/address event export for 2–4 weeks, or read-only API access through a scoped API token (`addresses` and `vehicle locations/stops` read). We also need the list of geofenced customer facilities, and trailer IDs if trailer-level tracking (late trailer returns) is in scope.
- **TMS load export** (McLeod, Revenova, Aljex, Turvo, ...): load, customer, carrier, equipment, appointment times, POD status, invoice status.
- **Rate confirmations.** 10–20 PDFs across their main customers and brokers, used to extend the layout parsers. For scanned PDFs, OCR or an LLM fallback (off by default) would be added behind the exception queue.
- **Detention policy per customer.** Free time, rate, increments, caps, grace, whether early arrival counts, and "appointment vs. check-in" rules. There is also the question of whether detention stops at the geofence exit or at a BOL signed-out time.
- **Late-return and damage chargeback schedules.** These cover the Trailer Ops Analyst's other chargeback types, which the PoC flags without assuming a fee.
- **Carrier invoice feed.** An AP export or an invoices inbox. Also a tolerance policy for mismatches (for example, ±$1).
- **Output target.** The packet template the customer or broker accepts (their claim form or email format). Also where approved packets go: a TMS accessorial line, the customer portal, or email drafts. The PoC never sends.
- **Access and ops.** Where it runs (their VM or M365 tenant), who approves, retention for the audit log, and a weekly accuracy check against their analyst's manual totals for the first month.


## Consistent headers for multiline invoices

Every line with the same trimmed `invoice_no` and `load_id` must repeat the
same `carrier`, `invoice_date`, and `invoice_total`. Carrier and date strings
are compared after the loader's existing surrounding-whitespace trim. Totals
are compared in cents using the existing money parser, so `$1,100.00` and
`1100` still agree. Carrier aliases, case changes and different date spellings
are not inferred to be equivalent.

A conflicting repeated header stops the run with a `ValueError` naming the
fields, invoice/load and first/conflicting CSV record references. Correct
those source records before running again. The conflict is detected during
input loading, before any audit append or replacement of existing packet and
report files. Valid nonadjacent invoice lines still combine, and different
invoice/load groups retain their existing behavior.
