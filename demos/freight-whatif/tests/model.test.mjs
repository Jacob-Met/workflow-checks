import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { evaluate, validateScenario, parseCivil, parseMoney, money, compareResults } from "../site/model.mjs";
import { data } from "../site/data.mjs";

const oracleBytes = await readFile(new URL("./oracle.json", import.meta.url));
const oracle = JSON.parse(oracleBytes);
const failures = [], checks = [];
function check(name, fn) {
  try { fn(); checks.push(name); }
  catch (error) { failures.push({ name, message: error.message }); }
}
for (const test of oracle.cases) {
  check("python-parity:" + test.id, () => {
    const frozen = Object.freeze(structuredClone(test.scenario));
    assert.deepEqual(evaluate(frozen), test.expected);
  });
}
const base = data.presets[0].scenario;
for (const [name, changes] of [
  ["missing appointment", { appointment: null }], ["empty appointment", { appointment: "" }],
  ["invalid leap day", { arrival: "2026-02-29T09:00" }], ["invalid month", { arrival: "2026-13-01T09:00" }],
  ["invalid day", { arrival: "2026-04-31T09:00" }], ["invalid hour", { arrival: "2026-09-07T24:00" }],
  ["invalid minute", { arrival: "2026-09-07T09:60" }], ["seconds out of scope", { arrival: "2026-09-07T09:00:00" }],
  ["offset out of scope", { arrival: "2026-09-07T09:00Z" }], ["year too early", { arrival: "1899-12-31T09:00" }],
  ["year too late", { arrival: "2101-01-01T09:00" }], ["numeric time", { arrival: 0 }],
  ["NaN money", { detention_cents: NaN }], ["infinite money", { detention_cents: Infinity }],
  ["boolean money", { detention_cents: true }], ["fractional cents", { detention_cents: 1.5 }],
  ["string money", { detention_cents: "100" }], ["negative money", { detention_cents: -1 }],
  ["unsafe money", { detention_cents: Number.MAX_SAFE_INTEGER + 1 }], ["too large money", { detention_cents: 100000001 }],
  ["rate limit", { detention_rate_cents: 100001 }], ["null required money", { linehaul_cents: null }],
  ["negative cap", { detention_cap_cents: -1 }], ["infinite header", { invoice_total_cents: Infinity }],
  ["zero increment", { increment_minutes: 0 }], ["fractional increment", { increment_minutes: 1.5 }],
  ["free limit", { free_minutes: 1441 }], ["negative grace", { late_grace_minutes: -1 }],
  ["boolean POD", { pod_received: "false" }], ["boolean rate con", { ratecon_complete: 0 }],
  ["out-of-scope field", { second_stop: {} }],
]) {
  check("validation:" + name, () => {
    const s = { ...base, ...changes };
    assert.ok(validateScenario(s).length > 0);
    assert.throws(() => evaluate(s), TypeError);
  });
}
check("validation:missing required field", () => {
  const s = { ...base }; delete s.pod_received;
  assert.ok(validateScenario(s).some(e => e.field === "pod_received"));
});
for (const input of ["", "-1", "+1", "1e3", "Infinity", "NaN", "1,000", "1.001", ".25", "1000000.01", "1."]) {
  check("money rejects " + JSON.stringify(input), () => assert.equal(parseMoney(input), null));
}
for (const [input, cents] of [["0", 0], ["0.01", 1], ["131.25", 13125], ["1450.5", 145050], ["1000000", 100000000]]) {
  check("money accepts " + input, () => assert.equal(parseMoney(input), cents));
}
check("integer half-cent tie", () => {
  const r = evaluate({ ...base, arrival: base.appointment, departure: "2026-09-07T09:01",
    free_minutes: 0, increment_minutes: 1, detention_rate_cents: 30 });
  assert.equal(r.stop.amount_cents, 1);
});
check("civil time is timezone independent", () => {
  assert.equal(parseCivil("2026-03-08T01:30"), Date.UTC(2026, 2, 8, 1, 30));
  assert.equal(parseCivil("2026-11-01T01:30"), Date.UTC(2026, 10, 1, 1, 30));
  assert.notEqual(parseCivil("2000-02-29T00:00"), null);
  assert.equal(parseCivil("1900-02-29T00:00"), null);
});
check("fixed cents formatting", () => {
  assert.equal(money(100000001), "$1,000,000.01");
  assert.equal(money(-1), "-$0.01");
});
check("baseline comparison preserves earlier result", () => {
  const before = evaluate(base), snapshot = structuredClone(before);
  const after = evaluate({ ...base, detention_cents: 13125, linehaul_cents: 145001 });
  const delta = compareResults(before, after);
  assert.deepEqual(before, snapshot);
  assert.deepEqual(delta.removed_flags, ["DETENTION_UNSUPPORTED"]);
  assert.deepEqual(delta.added_flags, ["LINEHAUL_MISMATCH"]);
  assert.equal(delta.invoice_total_delta_cents, -1874);
});
const files = ["site/model.mjs", "site/data.mjs", "tests/model.test.mjs", "tests/oracle.json"];
const hashes = {};
for (const path of files) hashes[path] = createHash("sha256").update(await readFile(new URL("../" + path, import.meta.url))).digest("hex");
const receipt = {
  schema: "freight-whatif.model-receipt.v1", runtime: process.version,
  timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  oracle_cases: oracle.cases.length, passed: checks.length, failed: failures.length,
  core_source_pins: oracle.provenance.source_sha256, artifact_sha256: hashes,
  failures, checks,
};
const output = process.argv[2];
if (output) await writeFile(output, JSON.stringify(receipt, null, 2) + "\n", { flag: "wx" });
console.log(JSON.stringify({ ...receipt, checks: undefined, artifact_sha256: hashes }));
if (failures.length) process.exitCode = 1;
