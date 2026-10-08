import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { comparison, day, evaluate, originalInput, serviceMonth } from '../model.mjs';
const fixture = JSON.parse(await readFile(new URL('../fixture.json', import.meta.url)));
const oracle = JSON.parse(await readFile(new URL('./parity.json', import.meta.url)));

test('all 91 native Python engine cases match browser decisions and exact evidence', () => {
  assert.equal(oracle.cases.length, 91);
  assert.deepEqual(oracle.source, fixture.source);
  for (const example of oracle.cases) assert.deepEqual(comparison(evaluate(fixture, example.input)), example.expected, example.name);
});
test('a check keeps the immutable source bill history intact', () => {
  const before = structuredClone(fixture), input = originalInput(fixture);
  evaluate(fixture, { ...input, usage: 1000, amount: 2500 });
  assert.deepEqual(fixture, before);
  assert.deepEqual(originalInput(fixture), input);
});
test('invalid or unsupported values refuse the calculation', () => {
  const input = originalInput(fixture);
  for (const usage of [NaN, Infinity, -Infinity, 1e10, '100', null]) assert.throws(() => evaluate(fixture, { ...input, usage }));
  for (const amount of [NaN, Infinity, 12.345, '100']) assert.throws(() => evaluate(fixture, { ...input, amount }));
  for (const dates of [{ ps: '2026-02-29', pe: '2026-03-02' }, { ps: '2026-05-01', pe: '2026-04-30' }, { ps: '2026-01-01', pe: '2027-01-02' }, { ps: '', pe: input.pe }]) assert.throws(() => evaluate(fixture, { ...input, ...dates }));
});
test('calendar arithmetic is inclusive, leap-aware and selects the latest tied maximum month', () => {
  assert.equal(day('2024-03-01') - day('2024-02-01'), 29);
  assert.equal(serviceMonth('2026-04-16', '2026-05-15'), '2026-05-01');
  assert.equal(serviceMonth('2026-01-01', '2026-02-01'), '2026-01-01');
  assert.equal(serviceMonth('2026-12-20', '2027-01-10'), '2026-12-01');
  assert.equal(serviceMonth('2100-12-31', '2100-12-31'), '2100-12-01');
  assert.equal(serviceMonth('2026-01-01', '2026-04-15'), '2026-03-01');
});
test('mixed or unsupported source versions fail closed', () => {
  const input = originalInput(fixture);
  for (const bad of [{ ...fixture, version: 2 }, { ...fixture, synthetic: false }, { ...fixture, source: { files: {} } }]) assert.throws(() => evaluate(bad, input));
});
