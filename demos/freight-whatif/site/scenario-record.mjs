// Reopen the existing synthetic export only; calculation authority stays in model.mjs.
import { data } from "./data.mjs";
import { CONTRACT, FIELDS, evaluate, validateScenario, compareResults } from "./model.mjs";

export const MAX_RECORD_BYTES = 1048576;
const SCHEMA = "workflow-checks.freight-whatif.v1";
const ROOT_FIELDS = ["schema", "synthetic", "exported_at", "loaded_preset",
  "provenance", "contract", "baseline", "current", "comparison"];

function refuse(message) {
  throw new TypeError("Cannot open saved record: " + message);
}
function objectFields(value, fields, label) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    refuse(label + " must be an object.");
  }
  const keys = Object.keys(value);
  if (keys.length !== fields.length || keys.some(key => !fields.includes(key))) {
    refuse(label + " has missing or unsupported fields.");
  }
}
function requireFinite(root) {
  const pending = [root];
  while (pending.length) {
    const value = pending.pop();
    if (typeof value === "number" && !Number.isFinite(value)) {
      refuse("all numbers must be finite.");
    }
    if (value !== null && typeof value === "object") {
      for (const child of Object.values(value)) pending.push(child);
    }
  }
}
// Parsed JSON has no cycles. Compare exact types/keysets, retaining array order.
function equal(left, right) {
  const pending = [[left, right]];
  while (pending.length) {
    const [a, b] = pending.pop();
    if (a === b) continue; // JSON -0 and 0 are equivalent.
    if (a === null || b === null || typeof a !== "object" || typeof b !== "object") return false;
    if (Array.isArray(a) !== Array.isArray(b)) return false;
    if (Array.isArray(a)) {
      if (a.length !== b.length) return false;
      for (let i = 0; i < a.length; i++) pending.push([a[i], b[i]]);
    } else {
      const keys = Object.keys(a);
      if (keys.length !== Object.keys(b).length) return false;
      for (const key of keys) {
        if (!Object.hasOwn(b, key)) return false;
        pending.push([a[key], b[key]]);
      }
    }
  }
  return true;
}
function freeze(value) {
  if (value !== null && typeof value === "object") {
    for (const child of Object.values(value)) freeze(child);
    Object.freeze(value);
  }
  return value;
}
function canonicalTimestamp(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value)) return false;
  const date = new Date(value);
  return Number.isFinite(date.getTime()) && date.toISOString() === value;
}

/**
 * Admit a complete existing v1 export, then return a frozen canonical record.
 * Saved calculations are checked against newly computed values, never installed
 * as live calculation state. No I/O, form mutation, persistence or clock cutoff.
 */
export function parseScenarioRecord(text) {
  if (typeof text !== "string") throw new TypeError("Saved record content must be a string.");
  if (text.length > MAX_RECORD_BYTES || new TextEncoder().encode(text).length > MAX_RECORD_BYTES) {
    throw new RangeError("Saved record exceeds the 1 MiB UTF-8 limit.");
  }
  let record;
  try {
    record = JSON.parse(text.startsWith("\uFEFF") ? text.slice(1) : text);
  } catch {
    refuse("choose a complete JSON record downloaded from this demo.");
  }
  requireFinite(record);
  objectFields(record, ROOT_FIELDS, "The record");
  if (record.schema !== SCHEMA || record.synthetic !== true) {
    refuse("the version or synthetic scenario marker is not supported.");
  }
  if (!canonicalTimestamp(record.exported_at)) refuse("the export timestamp is not canonical UTC ISO text.");
  if (!equal(record.provenance, data.provenance)) refuse("the rule source pins do not match this demo.");
  if (!equal(record.contract, CONTRACT)) refuse("the synthetic contract does not match this demo.");
  objectFields(record.loaded_preset, ["id", "title"], "The loaded preset");
  const preset = data.presets.find(item =>
    item.id === record.loaded_preset.id && item.title === record.loaded_preset.title);
  if (!preset) refuse("the loaded preset is not a current starting case.");
  objectFields(record.baseline, ["scenario", "result"], "The baseline");
  objectFields(record.current, ["scenario", "result"], "The current scenario record");
  if (!equal(record.baseline.scenario, preset.scenario)) refuse("the baseline differs from its canonical preset.");
  objectFields(record.current.scenario, FIELDS, "The sixteen scenario inputs");
  const errors = validateScenario(record.current.scenario);
  if (errors.length) refuse("scenario inputs are invalid: " + errors.map(error => error.field).join(", ") + ".");
  const baselineResult = evaluate(preset.scenario);
  const currentScenario = Object.fromEntries(FIELDS.map(field => [field, record.current.scenario[field]]));
  const currentResult = evaluate(currentScenario);
  const comparison = compareResults(baselineResult, currentResult);
  if (!equal(record.baseline.result, baselineResult)) refuse("the saved baseline result does not match a fresh calculation.");
  if (!equal(record.current.result, currentResult)) refuse("the saved current result does not match a fresh calculation.");
  if (!equal(record.comparison, comparison)) refuse("the saved comparison does not match a fresh calculation.");
  return freeze({
    schema: SCHEMA, synthetic: true, exported_at: record.exported_at,
    loaded_preset: { id: preset.id, title: preset.title },
    provenance: structuredClone(data.provenance), contract: structuredClone(CONTRACT),
    baseline: { scenario: structuredClone(preset.scenario), result: baselineResult },
    current: { scenario: currentScenario, result: currentResult },
    comparison,
  });
}
