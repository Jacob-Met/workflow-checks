import { data } from "./data.mjs";
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
function loadPreset(id) {
  preset = data.presets.find(p => p.id === id);
  baseline = { scenario: structuredClone(preset.scenario), result: evaluate(preset.scenario) };
  for (const f of FIELDS) {
    const control = $(f), value = preset.scenario[f];
    if (control.type === "checkbox") control.checked = value;
    else control.value = value === null ? "" : moneyFields.has(f) ? (value / 100).toFixed(2) : String(value);
  }
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
for (const p of data.presets) {
  const button = element("button", undefined, "preset");
  button.type = "button"; button.dataset.preset = p.id; button.title = p.description;
  button.append(element("span", undefined, "preset-dot"), document.createTextNode(p.title));
  button.addEventListener("click", () => loadPreset(p.id));
  $("presets").append(button);
}
form.addEventListener("submit", event => event.preventDefault());
form.addEventListener("input", render);
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
