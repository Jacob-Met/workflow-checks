import { data } from "./data.mjs";
import { MAX_RECORD_BYTES, parseScenarioRecord } from "./scenario-record.mjs";
import { CONTRACT, FIELDS, evaluate, validateScenario, parseMoney, money, signedMoney, parseCivil, civilAt, compareResults } from "./model.mjs";
const $ = id => document.getElementById(id);
const form = $("scenario-form");
const moneyFields = new Set(FIELDS.filter(f => f.endsWith("_cents")));
const integerFields = new Set(["free_minutes", "increment_minutes", "late_grace_minutes"]);
const nullableMoney = new Set(["detention_cap_cents", "invoice_total_cents"]);
const labels = {
  detention: "Detention supported", ok: "Within the agreed terms",
  late_arrival: "Late arrival", exception: "Evidence needs review",
};
const findingLabels = {
  DETENTION_UNSUPPORTED: "Detention exceeds the evidence",
  LINEHAUL_MISMATCH: "Linehaul differs from the rate con",
  FUEL_MISMATCH: "Fuel surcharge differs from the rate con",
  ACCESSORIAL_OVER_RATECON: "Lumper exceeds the agreement",
  ACCESSORIAL_NOT_ON_RATECON: "An accessorial was not agreed",
  TOTAL_MISMATCH: "Invoice total does not match its lines",
  MISSING_POD: "Proof of delivery is missing",
};
let preset, baseline, currentScenario, currentResult, inputErrors = [];
let draftRevision = 0, importSerial = 0, recordIntent = null, recordPreview = null;
function element(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function formatTime(value) {
  if (!value) return { time: "Missing", date: "No tracking time" };
  const [date, time] = value.split("T");
  const [year, month, day] = date.split("-");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return { time: time.slice(0, 5), date: Number(day) + " " + months[Number(month) - 1] + " " + year };
}
function writeScenario(scenario) {
  for (const f of FIELDS) {
    const control = $(f), value = scenario[f];
    if (control.type === "checkbox") control.checked = value;
    else control.value = value === null ? "" : moneyFields.has(f) ? (value / 100).toFixed(2) : String(value);
  }
}
function loadPreset(id) {
  invalidateRecordDraft();
  preset = data.presets.find(p => p.id === id);
  baseline = { scenario: structuredClone(preset.scenario), result: evaluate(preset.scenario) };
  writeScenario(preset.scenario);
  for (const button of $("presets").children) button.setAttribute("aria-pressed", String(button.dataset.preset === id));
  render();
}
function readInputs() {
  const s = {}, parseErrors = [];
  for (const f of FIELDS) {
    const control = $(f), raw = control.value.trim();
    if (control.type === "checkbox") s[f] = control.checked;
    else if (moneyFields.has(f)) {
      if (raw === "" && nullableMoney.has(f)) s[f] = null;
      else {
        s[f] = parseMoney(raw);
        if (s[f] === null) parseErrors.push({ field: f, message: "Enter $0–$1,000,000 using at most two decimal places." });
        else if (f === "detention_rate_cents" && s[f] > 100000) parseErrors.push({ field: f, message: "Enter an hourly rate from $0 to $1,000." });
      }
    } else if (integerFields.has(f)) {
      s[f] = /^\d{1,4}$/.test(raw) ? Number(raw) : NaN;
    } else s[f] = raw === "" && f !== "appointment" ? null : raw;
  }
  const blocked = new Set(parseErrors.map(e => e.field));
  return { scenario: s, errors: [...parseErrors, ...validateScenario(s).filter(e => !blocked.has(e.field))] };
}
function showValidation(errors) {
  inputErrors = errors;
  for (const f of FIELDS) {
    const error = errors.find(e => e.field === f);
    $(f).setAttribute("aria-invalid", String(Boolean(error)));
    const note = $(f + "-error");
    if (note) {
      note.textContent = error?.message || "";
      if (error) $(f).setAttribute("aria-describedby", note.id);
      else $(f).removeAttribute("aria-describedby");
    }
  }
  $("invalid-state").hidden = !errors.length;
  $("result-content").hidden = Boolean(errors.length);
  $("download").disabled = Boolean(errors.length);
  if (errors.length) {
    $("validation-summary").textContent = errors.length + (errors.length === 1 ? " field needs" : " fields need")
      + " a valid value. The review and download will return when the inputs are valid.";
    $("live-status").textContent = "Review paused. " + errors.length + " invalid field" + (errors.length === 1 ? "." : "s.");
  }
}
function renderTiming(s, r) {
  const stop = r.stop;
  $("dwell-label").textContent = stop.dwell_minutes === null ? "Tracking pair incomplete" : stop.dwell_minutes + " min on site";
  $("timing-bar").replaceChildren();
  $("timing-key").replaceChildren();
  const entry = stop.arrival ? parseCivil(stop.arrival.slice(0, 16)) : null;
  const exit = stop.departure ? parseCivil(stop.departure.slice(0, 16)) : null;
  const clock = stop.clock_start ? parseCivil(stop.clock_start.slice(0, 16)) : null;
  if (entry !== null && exit !== null && clock !== null) {
    const dwell = (exit - entry) / 60000;
    const wait = Math.min(dwell, Math.max(0, (clock - entry) / 60000));
    const free = Math.min(Math.max(0, dwell - wait), s.free_minutes);
    const beyond = Math.max(0, dwell - wait - free);
    for (const [key, label, minutes] of [["wait", "Early wait", wait], ["free", "Free time", free], ["billable", "Beyond free", beyond]]) {
      if (minutes > 0) {
        const segment = element("div", undefined, "timing-segment " + key);
        segment.style.width = (minutes / dwell * 100) + "%";
        $("timing-bar").append(segment);
      }
      const legend = element("span");
      legend.append(element("i", undefined, "key-dot " + key), document.createTextNode(label + " · " + minutes + " min"));
      $("timing-key").append(legend);
    }
  } else {
    $("timing-key").append(element("span", stop.status === "late_arrival"
      ? "Arrival is outside the agreed grace period; the detention clock is not applied."
      : "A complete, eligible tracking pair is needed to show a detention clock."));
  }
  $("time-grid").replaceChildren();
  const freeEnd = clock === null ? null : civilAt(clock + s.free_minutes * 60000);
  for (const [title, stamp, empty] of [
    ["Arrival", s.arrival, "No entry"], ["Appointment", s.appointment, "Required"],
    ["Free time ends", freeEnd, "Not established"], ["Departure", s.departure, "No exit"],
  ]) {
    const tile = element("div", undefined, "time-item");
    const formatted = formatTime(stamp);
    tile.append(element("span", title), element("strong", stamp ? formatted.time : "—"),
      element("small", stamp ? formatted.date : empty));
    $("time-grid").append(tile);
  }
  let calculation;
  if (stop.status === "exception") calculation = "No automatic claim. Resolve the missing or ambiguous evidence before using a detention amount.";
  else if (stop.status === "late_arrival") calculation = "Arrival after the " + s.late_grace_minutes + "-minute grace period forfeits detention under these terms.";
  else calculation = stop.over_free_minutes + " min beyond free time → " + stop.billable_minutes + " min after rounding down in "
    + s.increment_minutes + "-min increments × " + money(s.detention_rate_cents) + "/hour"
    + (stop.capped ? " → stop cap " + money(s.detention_cap_cents) : "") + " = " + money(stop.amount_cents) + ".";
  $("calculation").textContent = calculation;
  $("engine-notes").replaceChildren(...stop.notes.map(note => element("li", note)));
}
function renderFindings(s, r) {
  $("finding-count").textContent = String(r.flags.length);
  $("invoice-total").textContent = "Invoice " + money(r.totals.invoice_total_cents);
  const findings = $("findings");
  findings.replaceChildren();
  for (const f of r.flags) {
    const card = element("article", undefined, "finding");
    card.dataset.code = f.code;
    const head = element("div", undefined, "finding-header");
    head.append(element("h4", findingLabels[f.code] || f.code));
    if (f.invoiced_cents !== null && f.expected_cents !== null) head.append(element("span",
      signedMoney(f.invoiced_cents - f.expected_cents), "finding-variance"));
    card.append(head, element("p", f.detail));
    const pointers = element("div", undefined, "evidence-pointers");
    for (const source of f.evidence) pointers.append(element("span", source));
    card.append(pointers);
    findings.append(card);
  }
  if (!r.flags.length) {
    const clean = element("div", undefined, "clean-card");
    clean.append(element("strong", "No invoice mismatches in this scenario"),
      element("p", "The displayed invoice checks match the supplied terms and evidence. The demo covers a single invoice, not a full payment review."));
    findings.append(clean);
  }
  const record = $("evidence-record");
  record.replaceChildren();
  const date = value => value ? value.replace("T", " ") : "missing";
  for (const [pointer, description] of [
    ["scenario:tracking", "One authored tracking row for " + CONTRACT.load_id + " at " + CONTRACT.facility
      + ". Arrival " + date(s.arrival) + "; departure " + date(s.departure) + "."],
    ["scenario:ratecon", CONTRACT.ratecon_no + ": appointment " + date(s.appointment) + "; " + s.free_minutes
      + " free minutes; " + s.increment_minutes + "-minute increments; " + s.late_grace_minutes + "-minute late grace; "
      + money(s.detention_rate_cents) + "/hour; " + (s.detention_cap_cents === null ? "no stop cap" : money(s.detention_cap_cents) + " stop cap")
      + ". Fixed agreements: " + money(CONTRACT.linehaul_cents) + " linehaul, " + money(CONTRACT.fuel_cents) + " fuel, "
      + money(CONTRACT.lumper_cents) + " lumper. " + (s.ratecon_complete ? "Marked complete." : CONTRACT.warning + ".")],
    ["scenario:invoice", CONTRACT.invoice_no + ": " + money(s.linehaul_cents) + " linehaul; " + money(s.fuel_cents) + " fuel; "
      + money(s.detention_cents) + " detention; " + money(s.lumper_cents) + " lumper; " + money(s.tonu_cents) + " truck ordered, not used. Line sum "
      + money(r.totals.line_sum_cents) + "; header " + money(r.totals.invoice_total_cents) + (s.invoice_total_cents === null ? " (automatic)." : " (entered).")],
    ["scenario:load", CONTRACT.load_id + ", " + CONTRACT.carrier + " for " + CONTRACT.customer
      + ", brokered mode. Proof of delivery " + (s.pod_received ? "on file." : "missing.")],
  ]) record.append(element("dt", pointer), element("dd", description));
}
function render() {
  const input = readInputs();
  showValidation(input.errors);
  if (input.errors.length) { currentScenario = null; currentResult = null; return; }
  const s = input.scenario, r = evaluate(s), stop = r.stop;
  currentScenario = s; currentResult = r;
  const edited = JSON.stringify(s) !== JSON.stringify(baseline.scenario);
  const comparison = compareResults(baseline.result, r);
  $("status-chip").className = "status-chip " + stop.status;
  $("status-chip").textContent = labels[stop.status];
  $("supported-amount").textContent = stop.status === "exception" ? "No automatic claim" : money(stop.amount_cents);
  $("supported-amount").className = "amount" + (stop.status === "exception" ? " no-claim" : "");
  $("amount-caption").textContent = stop.status === "exception" ? "A person needs to resolve the evidence."
    : stop.billable_minutes + " billable minutes" + (stop.capped ? " · capped" : "");
  $("billed-amount").textContent = money(s.detention_cents);
  $("variance-caption").textContent = s.detention_cents > stop.amount_cents
    ? money(s.detention_cents - stop.amount_cents) + (stop.status === "exception" ? " has no supported claim" : " above supported detention")
    : "At or below supported detention";
  const explanations = {
    detention: "The tracking pair supports a detention amount. Compare the invoice charge with the supported amount and its evidence below.",
    ok: "The supplied tracking and terms produce no positive detention amount. Review any invoice differences below.",
    late_arrival: "A long stop can still be ineligible: this arrival is later than the agreed grace period.",
    exception: "Missing or ambiguous evidence prevents an automatic detention claim. The rule records zero supported detention until the gap is resolved.",
  };
  $("decision-explanation").textContent = explanations[stop.status];
  $("baseline-label").textContent = "Compared with " + preset.title;
  $("edited-badge").hidden = !edited;
  if (!edited) $("baseline-summary").textContent = "Starting case unchanged. Try adjusting a time or charge.";
  else {
    const parts = [
      signedMoney(comparison.supported_detention_delta_cents) + " supported detention",
      (comparison.billable_minutes_delta > 0 ? "+" : "") + comparison.billable_minutes_delta + " billable min",
    ];
    if (comparison.added_flags.length) parts.push(comparison.added_flags.length + " new finding" + (comparison.added_flags.length === 1 ? "" : "s"));
    if (comparison.removed_flags.length) parts.push(comparison.removed_flags.length + " resolved finding" + (comparison.removed_flags.length === 1 ? "" : "s"));
    if (!comparison.added_flags.length && !comparison.removed_flags.length) parts.push("same finding types");
    if (comparison.status_before !== comparison.status_after) parts.push(labels[comparison.status_before] + " → " + labels[comparison.status_after]);
    $("baseline-summary").textContent = parts.join(" · ");
  }
  $("terms-preview").textContent = s.free_minutes + " min free · " + money(s.detention_rate_cents) + "/hr";
  $("invoice_total_cents").placeholder = money(r.totals.line_sum_cents) + " automatic";
  renderTiming(s, r);
  renderFindings(s, r);
  $("live-status").textContent = labels[stop.status] + ". "
    + (stop.status === "exception" ? "No automatic claim. " : money(stop.amount_cents) + " supported detention. ")
    + r.flags.length + " invoice finding" + (r.flags.length === 1 ? "." : "s.");
}

// Saved-record review is separate from the live form until explicit replacement.
const recordFile = $("record-file"), recordPanel = $("record-preview");
const recordStatus = $("record-status"), recordCancel = $("cancel-record");
const recordFieldLabels = {
  appointment: "Appointment", arrival: "Arrival", departure: "Departure",
  free_minutes: "Free time", increment_minutes: "Billing increment",
  late_grace_minutes: "Late-arrival grace", detention_rate_cents: "Detention hourly rate",
  detention_cap_cents: "Stop cap", linehaul_cents: "Linehaul", fuel_cents: "Fuel surcharge",
  detention_cents: "Invoiced detention", lumper_cents: "Lumper",
  tonu_cents: "Truck ordered, not used", invoice_total_cents: "Invoice header total",
  pod_received: "Proof of delivery on file", ratecon_complete: "Rate confirmation complete",
};
function rawDraft() {
  return JSON.stringify({
    preset: preset.id, baseline: baseline.scenario,
    fields: FIELDS.map(field => $(field).type === "checkbox" ? $(field).checked : $(field).value),
  });
}
function recordMessage(message, error = false) {
  recordStatus.textContent = message;
  recordStatus.classList.toggle("record-error", error);
}
function discardRecord(message = "", error = false) {
  importSerial++;
  recordIntent = null; recordPreview = null;
  recordPanel.hidden = true;
  $("record-fields").replaceChildren();
  $("replace-record").disabled = true;
  recordCancel.hidden = true;
  recordFile.value = "";
  recordMessage(message, error);
}
function invalidateRecordDraft() {
  draftRevision++;
  if (recordIntent || recordPreview) {
    discardRecord("The scenario changed. Open the record again to review its replacement.");
  }
}
function ownsIntent(intent) {
  return recordIntent === intent && intent.serial === importSerial;
}
function freshIntent(intent) {
  return ownsIntent(intent) && intent.revision === draftRevision && intent.draft === rawDraft();
}
function staleRecord() {
  discardRecord("The scenario changed while opening or reviewing this record. Nothing was replaced; open it again.", true);
}
function previewValue(field, value) {
  if (value === null) {
    return field === "detention_cap_cents" ? "No cap (blank field)"
      : field === "invoice_total_cents" ? "Automatic sum (blank field)" : "Missing (blank field)";
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (moneyFields.has(field)) return money(value);
  if (integerFields.has(field)) return String(value) + " min";
  return value.replace("T", " ");
}
function showRecordPreview(record, intent, filename) {
  recordPreview = { record, intent };
  $("record-filename").textContent = filename;
  $("record-preset").textContent = record.loaded_preset.title;
  $("record-exported").textContent = record.exported_at;
  $("record-source").textContent = record.provenance.baseline_commit;
  const rows = FIELDS.map(field => {
    const row = element("div", undefined, "record-field-row");
    const value = record.current.scenario[field];
    const cell = element("dd", previewValue(field, value));
    cell.dataset.recordField = field;
    cell.dataset.recordValue = JSON.stringify(value);
    row.append(element("dt", recordFieldLabels[field]), cell);
    return row;
  });
  $("record-fields").replaceChildren(...rows);
  const result = record.current.result;
  $("record-calculated").textContent = result.stop.status === "exception"
    ? "Fresh calculation: evidence needs review; no automatic detention claim. "
      + result.flags.length + " invoice findings."
    : "Fresh calculation: " + money(result.stop.amount_cents) + " supported detention; "
      + result.flags.length + " invoice findings.";
  recordPanel.hidden = false;
  $("replace-record").disabled = false;
  recordCancel.hidden = false;
  recordMessage("Record checked. Review all sixteen inputs; the current scenario has not changed.");
  $("record-preview-heading").focus();
}
$("open-record").addEventListener("click", () => {
  discardRecord();
  recordIntent = { serial: importSerial, revision: draftRevision, draft: rawDraft() };
  recordCancel.hidden = false;
  recordMessage("Choose a saved record. Cancel leaves the current scenario unchanged.");
  recordFile.click();
});
recordFile.addEventListener("cancel", () => {
  if (recordIntent) discardRecord("Opening cancelled. The current scenario is unchanged.");
});
recordFile.addEventListener("change", async () => {
  const opening = recordIntent;
  if (!opening) {
    recordMessage("Use Open saved record to begin a new review.", true);
    return;
  }
  if (!freshIntent(opening)) { staleRecord(); return; }
  const selected = [...recordFile.files];
  if (!selected.length) { discardRecord("Opening cancelled. The current scenario is unchanged."); return; }
  if (selected.length !== 1) { discardRecord("Choose one saved record at a time.", true); return; }
  // Each selection supersedes every earlier read, even when the form is unchanged.
  const intent = { ...opening, serial: ++importSerial };
  recordIntent = intent; recordPreview = null;
  recordPanel.hidden = true; $("replace-record").disabled = true;
  recordCancel.hidden = false;
  const file = selected[0];
  if (file.size > MAX_RECORD_BYTES) {
    discardRecord("Saved record exceeds the 1 MiB UTF-8 limit. Nothing was replaced.", true);
    return;
  }
  recordMessage("Reading the saved record; the current scenario is unchanged.");
  try {
    const source = await file.text();
    if (!ownsIntent(intent)) return;
    if (!freshIntent(intent)) { staleRecord(); return; }
    const record = parseScenarioRecord(source);
    if (!freshIntent(intent)) { staleRecord(); return; }
    showRecordPreview(record, intent, file.name);
  } catch (error) {
    if (!ownsIntent(intent)) return;
    if (!freshIntent(intent)) { staleRecord(); return; }
    discardRecord((error instanceof Error ? error.message : "The saved record could not be read.")
      + " Nothing was replaced.", true);
  }
});
recordCancel.addEventListener("click", () => {
  discardRecord("Opening cancelled. The current scenario is unchanged.");
  $("open-record").focus();
});
$("record-import").addEventListener("keydown", event => {
  if (event.key === "Escape" && (recordIntent || recordPreview)) {
    event.preventDefault();
    discardRecord("Opening cancelled. The current scenario is unchanged.");
    $("open-record").focus();
  }
});
$("replace-record").addEventListener("click", () => {
  if (!recordPreview) return;
  const { record, intent } = recordPreview;
  if (!freshIntent(intent)) { staleRecord(); return; }
  const replacementPreset = data.presets.find(item => item.id === record.loaded_preset.id);
  const replacementBaseline = {
    scenario: structuredClone(replacementPreset.scenario),
    result: evaluate(replacementPreset.scenario),
  };
  // All admission and freshness checks precede this synchronous, complete commit.
  preset = replacementPreset; baseline = replacementBaseline;
  writeScenario(record.current.scenario);
  for (const button of $("presets").children) {
    button.setAttribute("aria-pressed", String(button.dataset.preset === preset.id));
  }
  draftRevision++;
  discardRecord("Saved inputs replaced the scenario. Results were recalculated; Reset case restores "
    + preset.title + ".");
  render();
  $("results-heading").focus();
});

for (const p of data.presets) {
  const button = element("button", undefined, "preset");
  button.type = "button"; button.dataset.preset = p.id; button.title = p.description;
  button.append(element("span", undefined, "preset-dot"), document.createTextNode(p.title));
  button.addEventListener("click", () => loadPreset(p.id));
  $("presets").append(button);
}
form.addEventListener("submit", event => event.preventDefault());
function onScenarioEdit() { invalidateRecordDraft(); render(); }
form.addEventListener("input", onScenarioEdit);
form.addEventListener("change", onScenarioEdit);
$("reset").addEventListener("click", () => loadPreset(preset.id));
$("focus-error").addEventListener("click", () => {
  const control = $(inputErrors[0]?.field);
  if (!control) return;
  const details = control.closest("details"); if (details) details.open = true;
  control.focus();
});
$("download").addEventListener("click", () => {
  if (!currentScenario || !currentResult) return;
  const record = {
    schema: "workflow-checks.freight-whatif.v1", synthetic: true,
    exported_at: new Date().toISOString(), loaded_preset: { id: preset.id, title: preset.title },
    provenance: data.provenance, contract: CONTRACT,
    baseline: structuredClone(baseline),
    current: { scenario: structuredClone(currentScenario), result: structuredClone(currentResult) },
    comparison: compareResults(baseline.result, currentResult),
  };
  const blob = new Blob([JSON.stringify(record, null, 2) + "\n"], { type: "application/json" });
  const url = URL.createObjectURL(blob), link = document.createElement("a");
  link.href = url; link.download = "freight-whatif-" + preset.id + ".json";
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  $("live-status").textContent = "Downloaded the current scenario, baseline, results and rule source pins.";
});
$("source-summary").textContent = "Bounded projection of the freight rules at source commit "
  + data.provenance.baseline_commit.slice(0, 12) + ". Checked against 185 scenarios evaluated by the actual Python engine. Qualification details travel with the source.";
for (const path of Object.keys(data.provenance.source_sha256)) {
  const item = element("li"), link = element("a", path.split("/").at(-1));
  link.href = "https://github.com/Jacob-Met/workflow-checks/blob/" + data.provenance.baseline_commit + "/" + path;
  item.append(link); $("source-links").append(item);
}
loadPreset(data.presets[0].id);
