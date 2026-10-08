# Freight what-if

A standalone workbench for freight billing reviewers: edit an invented stop and invoice, inspect the detention calculation and invoice findings, compare with the loaded case, and download the exact evidence record.

**All scenarios are synthetic.** This route checks one brokered stop, one same-row tracking pair, one known rate confirmation and one invoice. It does not approve payment, calculate settlement or connect to live carrier data.

Source scope is [workflow-checks #17](https://github.com/Jacob-Met/workflow-checks/issues/17). Everything for this contribution is under `demos/freight-whatif/`; the canonical freight engine and shared sample site are unchanged.

## Run it

From the repository root, with Python 3.10 or later:

```sh
python3 demos/freight-whatif/tools/serve.py
```

Open **http://127.0.0.1:8765/**. Stop with Ctrl-C. Use `--port 8877` if needed.

The release ZIP under `dist/` is self-contained. Extract it into a new directory and run `python3 tools/serve.py` there. Runtime uses browser modules and the Python standard library; no package installation, external font, API key or network service is needed. A local HTTP server is required because browsers restrict module loading from `file://`.

## Use the workbench

Choose Long dwell, Within free time, Late arrival or Missing departure. Loading a case establishes a fresh baseline. Change arrival/departure or invoice charges to see the review update; expand Rate confirmation to adjust free time, late grace, increments, hourly rate or cap.

The default scenario arrives at 08:45 for a 09:00 appointment and leaves at 12:45. The free-time clock begins at 09:00, giving 225 minutes on the clock, 105 after the 120 free minutes and 105 billable minutes after rounding down in 15-minute increments. At $75/hour, the engine supports **$131.25**. A $150 detention invoice line produces an **$18.75** unsupported difference. These are authored demonstration amounts, not actual charges or savings.

Blank arrival/departure means missing tracking evidence. A missing, reversed or more-than-24-hour tracking pair becomes an exception. An incomplete rate confirmation prevents an automatic detention claim. The headline explicitly says **No automatic claim** while the exported raw rule result preserves the engine's zero supported amount.

Invalid dates, negative or malformed charges, fractional cents and out-of-range terms pause both the review and download until corrected. Blank invoice header means the line sum; a supplied header is compared exactly with that sum. Blank cap means no cap; an explicit zero is a zero cap. Zero truck-ordered-not-used omits that optional line.

Download record exports the current valid inputs/results, the loaded baseline, comparison, synthetic contract and exact canonical source pins. Edits stay in page memory and reset on refresh. Use **Open saved record** to resume a downloaded record through the review described below.

## Resume a saved record

Choose **Open saved record**, select a JSON record previously downloaded from this Freight demo, and review the filename, export timestamp, matched rule source, starting case and all sixteen inputs. The preview shows a fresh calculation while leaving the current scenario, its baseline and its download state intact. **Replace current scenario** discards the current draft and commits the complete admitted replacement. **Cancel** preserves the draft, including incomplete or invalid text. Reset case then returns to the imported record's canonical starting case.

Opening a file does not save it to browser storage, send it to a service or approve any payment. Keep a downloaded record if you want to resume it after closing the page. A table preview or saved result is not a signature or evidence of live source freshness.

Only the existing `workflow-checks.freight-whatif.v1` envelope is supported. Its synthetic marker, exact rule provenance and contract, canonical loaded preset and baseline, and all sixteen current input fields must match this demo's contract. Both baseline and current results and their comparison are recomputed with the unchanged model; any inconsistent stored result, flag, evidence field, total or comparison refuses the entire file. The importer does not salvage fields from an incompatible record.

The file limit is **1 MiB (1,048,576 UTF-8 bytes)**, including JSON whitespace and an optional single leading BOM. JSON object-key order and CRLF formatting are accepted; array order matters. MIME type and extension are hints, not record identity. Unknown fields and nonfinite numbers are refused. The export timestamp must be the canonical four-digit-year UTC ISO form emitted by the exporter, with no age or future-time cutoff. Ordinary JSON parsing semantics apply to repeated member names.

Null and zero remain distinct: a blank stop cap means no cap, a zero cap remains zero, and a blank invoice header means automatic line sum. Whole cents, civil-minute times and booleans use the existing model's validation. Missing tracking, incomplete rate confirmation, late arrival and invoice disagreements remain valid demo scenarios when their saved calculations are coherent; opening does not impose a new business rule.

Editing the scenario, resetting or changing its starting case retires an open preview or pending read. Inputs are checked again before preview and replacement, including raw value changes while the file chooser is open. A newer selection supersedes an earlier read; an old success or error cannot revive or clear the newer review.

Saved-record resume is the additive source contribution [#60](https://github.com/Jacob-Met/workflow-checks/issues/60). Its maintained admission checks run with:

```sh
node --test demos/freight-whatif/tests/scenario-record.test.mjs
```

The original engine, model parity, layout, installer and delivery qualification below retain their original authorship and source boundaries. New receiving evidence is reported separately; these historical results are not relabeled as an importer run.

## Boundaries

- Civil timestamps have minute precision, with years 1900–2100. No timezone conversion or daylight-saving interpretation is claimed.
- Dollar values are exact integer cents. Charges/caps/header are $0–$1,000,000; the hourly rate is $0–$1,000. Free time and grace are 0–1440 minutes; increments are 1–1440 minutes. These are explicit demo input limits.
- The fixed rate confirmation agrees to $1,450 linehaul, $245 fuel and $150 lumper. Detention terms are editable; other invoice agreements are fixed.
- Invoice tolerance is exactly zero. Both higher and lower linehaul/fuel values differ from the rate con. Detention and agreed accessorial checks flag overcharges; this page does not create a charge for underbilling.
- Duplicate invoices, missing rate confirmations, multi-stop/facility/asset matching, fines and settlement are outside this projection. It does not claim complete coverage of the entire freight engine.
- Evidence pointers such as `scenario:tracking` refer to authored fields in the downloaded scenario, not documents or tracking exports supplied by a customer.

## Rule custody

The browser projection in `site/model.mjs` is bounded to the scenario described above. `tools/build_fixtures.py` constructs actual freight dataclasses and calls the unchanged Python engine; its serialized results are the oracle for full result comparison, including status, notes, amounts and evidence pointers.

Baseline: `2f1e5f777197eedd69d51a4d81c0da744b65ad88`.

| Canonical source | SHA-256 |
| --- | --- |
| `freight_packets/freightpkt/models.py` | `8a24ed2cca6f45aa8a47d793620b0e2e4d573ec92209954d3f3156795e3f0e05` |
| `freight_packets/freightpkt/detention.py` | `31ca31fd3210ff680bc83291916e39ea19b82580c3a090720556afd4ef0cd76b` |
| `freight_packets/freightpkt/invoice_match.py` | `37a9e0801de948c3b558ca7c9846b3d0eb76ec062703ee3e5132df273ff569ab` |

The builder refuses different core bytes. Updating those pins requires explicit rule review and refreshed qualification, not a silent fixture rewrite.

## Verify

From the repository root:

```sh
python3 demos/freight-whatif/tools/build_fixtures.py --check
node demos/freight-whatif/tests/model.test.mjs
```

The frozen oracle has 185 actual-Python scenarios. The model receiver compares all 185 full results and adds 52 validation, money, civil-time and baseline-custody controls. Its native receipt records 237 passes.

The browser receiver needs Playwright and a Chromium executable supplied by the caller. It installs neither. Set explicit paths and a **new** owned output directory:

```sh
FREIGHT_PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs \
FREIGHT_CHROMIUM_EXECUTABLE=/absolute/path/to/chromium \
FREIGHT_BROWSER_OUTPUT=/absolute/path/to/new-receiving-output \
node demos/freight-whatif/tests/browser.mjs
```

It uses an ephemeral loopback server and fresh context, blocks external requests, checks interactions/downloads/keyboard/mobile widths, records runtime/source pins, then closes the browser and server and verifies the port is closed. Optional `FREIGHT_SITE_ROOT` points to an installed copy. Supplied module and executable are read-only dependencies.

Primary native qualification used Python 3.12.8, Node 26.3.0, Playwright 1.62.1 and Chromium 153.0.8010.12. The initial browser receipt records 11 passed scenarios, zero page/console errors, zero external requests, 320/390-pixel layouts and completed cleanup. The author inspected the desktop and mobile screenshots. Independent receiving is recorded separately so that its cases and authorship stay distinguishable.

An independent receiver evaluated 39 additional authored cases directly through the real Python rules, all matching the browser projection. Its separate browser challenge initially passed 15 of 16 groups and found a concrete 320-pixel card defect: a supported amount of $24,000.00 pushed the invoiced amount beyond a clipped card edge while document width still appeared correct. The original negative geometry, screenshot and receipt are preserved.

The corrected card wraps its two amount blocks when they cannot fit. Focused receiving passed 13 checks, including 12 layout states across desktop, 390 and 320 pixels, including the original failing case, maximum invoice charges and evidence exceptions. This receipt pins functional CSS `2173b69ce20fd22fa8b92f14305aa9d2fc57fbda5e3e6a3ea19eea0059c215e9`. Final CSS `0709487053ebc7e028577d46b6447847e7bfc4343027b7d1ecfab2c70c692a31` adds only the exact root MIT license in a closed comment; independent byte custody verifies that the entire preceding CSS is unchanged. App, model, data and HTML bytes are unchanged across this correction. No failed original run is relabeled green.

The independent portable layout receiver and its explicit path arguments are retained with the independent evidence packet. It supplies a regression check for clipping inside cards, which a document-overflow assertion alone did not catch.

Actual installer exercise:

```sh
python3 demos/freight-whatif/tests/install.test.py \
  --work-root /absolute/path/to/new-owned-install-receiving \
  --output /absolute/path/to/new-install-receipt.json
```

This creates its own controls, exercises install, refuses overwrite and rollback of changed/extra files, performs rollback, verifies its sibling is untouched, then leaves a final exact installation. The native receipt records six passed controls.

## Install and rollback

Install only into a new path whose parent already exists:

```sh
python3 demos/freight-whatif/tools/install.py install --target /your/new/freight-site
python3 demos/freight-whatif/tools/install.py verify --target /your/new/freight-site
python3 demos/freight-whatif/tools/serve.py --site /your/new/freight-site
```

After stopping the server:

```sh
python3 demos/freight-whatif/tools/install.py rollback --target /your/new/freight-site
```

The installation manifest pins all six files. Rollback refuses edited content, unexpected files and symlinks. It removes only a matching installation; it does not overwrite, restore or clean other application directories. No shared webroot or background service is activated by these commands.

## Package

Create a new output directory, then:

```sh
python3 demos/freight-whatif/tools/package.py \
  --output /absolute/path/to/new-output/freight-whatif.zip \
  --receipt /absolute/path/to/new-output/bundle-receipt.json
```

The deterministic ZIP contains the six site files, loopback server, installer, usage instructions, original MIT LICENSE and manifest. The stylesheet also carries the exact license notice so an installed static copy retains it. Every archived file is read back and checked against the bytes used to build it.

## Contribution provenance

The original #17 contribution was made under Jacob's HAMON mandate. The historical native `build-demo-freight-whatif` attempt (`goal_8c6afc4d23d24dceb103`) was reconciled failed after read-only activity. It was not resumed, requeued or represented as successful. All new project writes and tests took place in an exclusive Mac checkout, respecting that objective's no-ThinkPad-project-writes boundary. Native coordination is a contributor record, not a worker registration or goal lease.
