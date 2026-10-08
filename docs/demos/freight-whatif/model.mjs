// Bounded browser projection of the pinned Python freight rules.
// Scope: one brokered stop, one same-row tracking pair, one invoice.
// tests/oracle.json is produced by the real Python rules, not this module.
import { data } from "./data.mjs";
export const CONTRACT = Object.freeze(data.contract);
export const FIELDS = Object.freeze([
  "appointment", "arrival", "departure", "free_minutes", "increment_minutes",
  "late_grace_minutes", "detention_rate_cents", "detention_cap_cents",
  "linehaul_cents", "fuel_cents", "detention_cents", "lumper_cents", "tonu_cents",
  "invoice_total_cents", "pod_received", "ratecon_complete",
]);
const MINUTE = 60000;
const MONEY_FIELDS = ["linehaul_cents", "fuel_cents", "detention_cents", "lumper_cents", "tonu_cents"];
export function parseCivil(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return null;
  const parts = value.match(/\d+/g).map(Number);
  const [year, month, day, hour, minute] = parts;
  if (year < 1900 || year > 2100 || month < 1 || month > 12 || day < 1 || hour > 23 || minute > 59) return null;
  const epoch = Date.UTC(year, month - 1, day, hour, minute);
  const d = new Date(epoch);
  if (d.getUTCFullYear() !== year || d.getUTCMonth() !== month - 1 || d.getUTCDate() !== day) return null;
  return epoch;
}
export function civilAt(epoch) {
  return new Date(epoch).toISOString().slice(0, 16);
}
export function validateScenario(s) {
  const errors = [];
  const add = (field, message) => errors.push({ field, message });
  if (!s || typeof s !== "object" || Array.isArray(s)) return [{ field: "scenario", message: "Use a scenario object." }];
  for (const field of ["appointment", "arrival", "departure"]) {
    if (field !== "appointment" && s[field] === null) continue;
    if (parseCivil(s[field]) === null) add(field, "Enter a valid date and time from 1900 through 2100.");
  }
  const integer = (field, min, max, nullable = false) => {
    if (nullable && s[field] === null) return;
    if (!Number.isSafeInteger(s[field]) || s[field] < min || s[field] > max) {
      add(field, "Use a whole number from " + min + " to " + max + ".");
    }
  };
  for (const f of MONEY_FIELDS) integer(f, 0, 100000000);
  integer("detention_rate_cents", 0, 100000);
  integer("detention_cap_cents", 0, 100000000, true);
  integer("invoice_total_cents", 0, 100000000, true);
  integer("free_minutes", 0, 1440);
  integer("increment_minutes", 1, 1440);
  integer("late_grace_minutes", 0, 1440);
  for (const f of ["pod_received", "ratecon_complete"]) if (typeof s[f] !== "boolean") add(f, "Choose yes or no.");
  for (const f of Object.keys(s)) if (!FIELDS.includes(f)) add(f, "This field is outside the single-stop demo.");
  return errors;
}
export function parseMoney(text) {
  if (typeof text !== "string" || !/^\d{1,7}(?:\.\d{1,2})?$/.test(text)) return null;
  const [whole, fraction = ""] = text.split(".");
  const cents = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  return Number.isSafeInteger(cents) && cents <= 100000000 ? cents : null;
}
export function money(cents) {
  if (cents === null || cents === undefined) return "—";
  const absolute = Math.abs(cents);
  return (cents < 0 ? "-" : "") + "$" + Math.floor(absolute / 100).toLocaleString("en-US")
    + "." + String(absolute % 100).padStart(2, "0");
}
export function signedMoney(cents) {
  return (cents > 0 ? "+" : "") + money(cents);
}
function stopResult(s) {
  const c = CONTRACT;
  const appt = parseCivil(s.appointment);
  const entry = s.arrival === null ? null : parseCivil(s.arrival);
  const exit = s.departure === null ? null : parseCivil(s.departure);
  const iso = stamp => stamp + ":00";
  const r = {
    load_id: c.load_id, stop_index: 1, kind: "delivery", facility: c.facility,
    appointment: iso(s.appointment), arrival: null, departure: null, arrival_src: "",
    departure_src: "", dwell_minutes: null, clock_start: null, free_minutes: s.free_minutes,
    over_free_minutes: 0, billable_minutes: 0, amount_cents: 0, capped: false, status: "ok", notes: [],
  };
  if (entry === null || entry < appt - 720 * MINUTE || entry > appt + 1440 * MINUTE) {
    r.status = "exception";
    r.notes.push("no geofence entry found for this stop in the appointment window");
    return r;
  }
  r.arrival = iso(s.arrival);
  r.arrival_src = "scenario:tracking";
  if (exit === null || exit <= entry || exit - entry > 1440 * MINUTE) {
    r.status = "exception";
    r.notes.push("geofence entry has no matching exit (export gap or still on site)");
    return r;
  }
  r.departure = iso(s.departure);
  r.departure_src = "scenario:tracking";
  r.dwell_minutes = Math.floor((exit - entry) / MINUTE);
  const lateBy = (entry - appt) / MINUTE;
  const warning = "rate-con parse warnings: " + c.warning;
  if (lateBy > s.late_grace_minutes) {
    r.status = "late_arrival";
    r.notes.push("arrived " + Math.trunc(lateBy) + " min after appointment (grace "
      + s.late_grace_minutes + " min): detention forfeited");
    if (!s.ratecon_complete) { r.status = "exception"; r.notes.push(warning); }
    return r;
  }
  const start = Math.max(entry, appt);
  r.clock_start = new Date(start).toISOString().slice(0, 19);
  if (entry < appt) r.notes.push("arrived " + Math.trunc(-lateBy) + " min early; free-time clock starts at appointment");
  const onClock = Math.floor((exit - start) / MINUTE);
  r.over_free_minutes = Math.max(0, onClock - s.free_minutes);
  const increment = Math.max(1, s.increment_minutes);
  r.billable_minutes = Math.floor(r.over_free_minutes / increment) * increment;
  let amount = Math.floor((s.detention_rate_cents * r.billable_minutes + 30) / 60);
  if (s.detention_cap_cents !== null && amount > s.detention_cap_cents) {
    amount = s.detention_cap_cents;
    r.capped = true;
    r.notes.push("capped at rate-con per-stop maximum");
  }
  r.amount_cents = amount;
  if (amount > 0) r.status = "detention";
  if (!s.ratecon_complete) {
    r.status = "exception"; r.billable_minutes = 0; r.amount_cents = 0; r.capped = false;
    r.notes.push(warning);
  }
  return r;
}
export function evaluate(s) {
  const errors = validateScenario(s);
  if (errors.length) {
    const error = new TypeError("Invalid freight scenario: " + errors.map(e => e.field).join(", "));
    error.errors = errors;
    throw error;
  }
  const c = CONTRACT, stop = stopResult(s), flags = [];
  const lineSum = MONEY_FIELDS.reduce((total, key) => total + s[key], 0);
  const total = s.invoice_total_cents === null ? lineSum : s.invoice_total_cents;
  const invEv = ["scenario:invoice"], rcEv = [...invEv, "scenario:ratecon"];
  const flag = (code, detail, invoiced = null, expected = null, evidence = rcEv) => flags.push({
    invoice_no: c.invoice_no, load_id: c.load_id, carrier: c.carrier,
    code, detail, invoiced_cents: invoiced, expected_cents: expected, evidence: [...evidence],
  });
  if (total !== lineSum) flag("TOTAL_MISMATCH", "header total " + money(total)
    + " != line sum " + money(lineSum), total, lineSum, invEv);
  if (!s.pod_received) flag("MISSING_POD", "no POD on file; hold payment until POD received",
    null, null, [...invEv, "scenario:load"]);
  for (const [field, code, label] of [
    ["linehaul_cents", "LINEHAUL_MISMATCH", "linehaul"],
    ["fuel_cents", "FUEL_MISMATCH", "fuel surcharge"],
  ]) {
    if (s[field] !== c[field]) flag(code, label + ": invoiced " + money(s[field])
      + " vs rate-con " + money(c[field]), s[field], c[field]);
  }
  if (s.detention_cents > stop.amount_cents) flag("DETENTION_UNSUPPORTED",
    "detention invoiced " + money(s.detention_cents) + " but telematics supports " + money(stop.amount_cents),
    s.detention_cents, stop.amount_cents);
  if (s.lumper_cents > c.lumper_cents) flag("ACCESSORIAL_OVER_RATECON",
    "LUMPER: invoiced " + money(s.lumper_cents) + " vs agreed " + money(c.lumper_cents),
    s.lumper_cents, c.lumper_cents);
  if (s.tonu_cents > 0) flag("ACCESSORIAL_NOT_ON_RATECON",
    "TONU " + money(s.tonu_cents) + " billed but not on rate-con", s.tonu_cents, 0);
  flags.sort((a, b) => a.code < b.code ? -1 : a.code > b.code ? 1 : 0);
  return { stop, flags, totals: { line_sum_cents: lineSum, invoice_total_cents: total,
    supported_detention_cents: stop.amount_cents } };
}
export function compareResults(baseline, current) {
  const before = new Set(baseline.flags.map(f => f.code));
  const after = new Set(current.flags.map(f => f.code));
  return {
    status_before: baseline.stop.status, status_after: current.stop.status,
    supported_detention_delta_cents: current.stop.amount_cents - baseline.stop.amount_cents,
    billable_minutes_delta: current.stop.billable_minutes - baseline.stop.billable_minutes,
    invoice_total_delta_cents: current.totals.invoice_total_cents - baseline.totals.invoice_total_cents,
    added_flags: [...after].filter(code => !before.has(code)),
    removed_flags: [...before].filter(code => !after.has(code)),
  };
}
