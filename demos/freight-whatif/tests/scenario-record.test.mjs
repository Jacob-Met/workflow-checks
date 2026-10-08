import test from "node:test";
import assert from "node:assert/strict";
import { data } from "../site/data.mjs";
import { CONTRACT, FIELDS, evaluate, compareResults } from "../site/model.mjs";
import { MAX_RECORD_BYTES, parseScenarioRecord } from "../site/scenario-record.mjs";

function exported(index = 1, edits = {}) {
  const preset = data.presets[index];
  const original = structuredClone(preset.scenario);
  const current = { ...original, ...edits };
  const baselineResult = evaluate(original), currentResult = evaluate(current);
  return {
    schema: "workflow-checks.freight-whatif.v1", synthetic: true,
    exported_at: "2026-10-08T12:34:56.789Z",
    loaded_preset: { id: preset.id, title: preset.title },
    provenance: structuredClone(data.provenance), contract: structuredClone(CONTRACT),
    baseline: { scenario: original, result: baselineResult },
    current: { scenario: current, result: currentResult },
    comparison: compareResults(baselineResult, currentResult),
  };
}
const parse = record => parseScenarioRecord(JSON.stringify(record));

test("all four existing exported presets reopen without altering the model results", () => {
  for (let i = 0; i < data.presets.length; i++) {
    const record = exported(i);
    assert.deepEqual(parse(record), record);
  }
});

test("authored invoice inputs survive a coherent current record and retain its original baseline", () => {
  const record = exported(1, { fuel_cents: 30000, detention_cap_cents: null, invoice_total_cents: 0, pod_received: false });
  const admitted = parse(record);
  assert.equal(admitted.loaded_preset.id, "within-free");
  assert.equal(admitted.current.scenario.fuel_cents, 30000);
  assert.equal(admitted.current.scenario.detention_cap_cents, null);
  assert.equal(admitted.current.scenario.invoice_total_cents, 0);
  assert.equal(admitted.current.scenario.pod_received, false);
  assert.equal(admitted.current.result.totals.line_sum_cents, 190000);
  assert.equal(admitted.current.result.totals.invoice_total_cents, 0);
  assert.equal(admitted.baseline.result.totals.invoice_total_cents, 184500);
  assert.equal(admitted.comparison.invoice_total_delta_cents, -184500);
});

test("business exceptions remain valid saved scenarios rather than new admission rules", () => {
  for (const edits of [
    { arrival: null }, { departure: null }, { departure: "2026-09-07T08:00" },
    { departure: "2026-09-09T09:00" }, { ratecon_complete: false },
    { arrival: "2026-09-07T09:16", departure: "2026-09-07T13:00" },
  ]) {
    const record = exported(1, edits);
    assert.deepEqual(parse(record).current.result, evaluate(record.current.scenario));
  }
});

test("format, source, preset and canonical baseline are required as one envelope", () => {
  const mutations = [
    r => { r.schema = "workflow-checks.freight-whatif.v2"; },
    r => { r.synthetic = "true"; },
    r => { r.extra = true; },
    r => { delete r.comparison; },
    r => { r.provenance.baseline_commit = "other"; },
    r => { r.provenance.source_sha256.extra = "invented"; },
    r => { r.contract.load_id = "CUSTOMER-REAL"; },
    r => { r.loaded_preset.title = "Renamed"; },
    r => { r.loaded_preset.extra = true; },
    r => { r.baseline.scenario.fuel_cents = 30000; },
    r => { r.current.extra = true; },
  ];
  for (const mutate of mutations) {
    const record = exported(); mutate(record);
    assert.throws(() => parse(record), TypeError);
  }
});

test("all sixteen fields use the unchanged input validator and derived claims must match freshly", () => {
  for (const field of FIELDS) {
    const record = exported();
    delete record.current.scenario[field];
    assert.throws(() => parse(record), TypeError, field);
  }
  const mutations = [
    r => { r.current.scenario.free_minutes = "120"; },
    r => { r.current.scenario.pod_received = 1; },
    r => { r.current.scenario.linehaul_cents = 0.5; },
    r => { r.current.scenario.unknown = true; },
    r => { r.baseline.result.stop.amount_cents = 1; },
    r => { r.current.result.totals.invoice_total_cents += 1; },
    r => { r.current.result.extra = true; },
    r => { r.comparison.added_flags.push("INVENTED"); },
  ];
  for (const mutate of mutations) {
    const record = exported(); mutate(record);
    assert.throws(() => parse(record), TypeError);
  }
});

test("object order and JSON whitespace are irrelevant while array order remains meaningful", () => {
  const record = exported(0, { fuel_cents: 30000, pod_received: false });
  const reverse = value => Array.isArray(value) ? value.map(reverse) :
    value && typeof value === "object" ? Object.fromEntries(Object.entries(value).reverse().map(([k, v]) => [k, reverse(v)])) : value;
  assert.deepEqual(parse(reverse(record)), record);
  assert.deepEqual(parseScenarioRecord("\uFEFF" + JSON.stringify(record, null, 2).replaceAll("\n", "\r\n")), record);
  record.current.result.flags.reverse();
  assert.throws(() => parse(record), TypeError);
  assert.throws(() => parseScenarioRecord("\uFEFF\uFEFF" + JSON.stringify(exported())), TypeError);
});

test("timestamps are exact canonical four-digit UTC metadata without an age policy", () => {
  for (const stamp of ["0000-01-01T00:00:00.000Z", "9999-12-31T23:59:59.999Z"]) {
    const record = exported(); record.exported_at = stamp;
    assert.equal(parse(record).exported_at, stamp);
  }
  for (const stamp of ["2026-10-08T12:34:56Z", "2026-02-30T12:34:56.789Z", "2026-10-08T12:34:56.789+00:00", "+010000-01-01T00:00:00.000Z", 0]) {
    const record = exported(); record.exported_at = stamp;
    assert.throws(() => parse(record), TypeError);
  }
});

test("UTF-8 file budget and recursively nonfinite values refuse before record use", () => {
  const text = JSON.stringify(exported());
  const size = new TextEncoder().encode(text).length;
  assert.equal(MAX_RECORD_BYTES, 1048576);
  assert.deepEqual(parseScenarioRecord(" ".repeat(MAX_RECORD_BYTES - size) + text), exported());
  assert.throws(() => parseScenarioRecord(" ".repeat(MAX_RECORD_BYTES - size + 1) + text), RangeError);
  assert.throws(() => parseScenarioRecord("é".repeat(MAX_RECORD_BYTES / 2 + 1)), RangeError);
  assert.throws(() => parseScenarioRecord(text.replace('"amount_cents":0', '"amount_cents":1e999')), /finite/);
  for (const value of ["", "{", "[]", "null", "true"]) assert.throws(() => parseScenarioRecord(value), TypeError);
  for (const value of [null, {}, 1, new String(text)]) assert.throws(() => parseScenarioRecord(value), TypeError);
});

test("admitted snapshots detach and freeze every stored context and calculated result", () => {
  const record = exported();
  const result = parse(record);
  record.current.scenario.fuel_cents = 999;
  assert.equal(result.current.scenario.fuel_cents, 24500);
  assert.throws(() => { result.current.scenario.fuel_cents = 1; }, TypeError);
  assert.throws(() => result.current.result.flags.push({}), TypeError);
  assert.throws(() => { result.provenance.source_sha256.extra = "bad"; }, TypeError);
  assert.throws(() => { result.baseline.scenario.free_minutes = 0; }, TypeError);
  assert.deepEqual(JSON.parse(JSON.stringify(result)), exported());
});
