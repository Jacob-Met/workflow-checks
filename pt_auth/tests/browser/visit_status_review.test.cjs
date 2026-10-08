'use strict';

// Actual stdlib HTTP app + Chromium; no API/DOM replacement or browser download.
// Optional: PTAUTH_TEST_PYTHON, PTAUTH_BROWSER_EXECUTABLE, PTAUTH_BROWSER_SOURCE.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const { test, before, after } = require('node:test');
const { chromium } = require('playwright');

const source = process.env.PTAUTH_BROWSER_SOURCE || path.resolve(__dirname, '../..');
const python = process.env.PTAUTH_TEST_PYTHON || 'python';
const literalName = 'Test <script>unsafe()</script> & "literal"';
let browser;

const serverSource = `
import json, sys
from datetime import date
from pathlib import Path
from http.server import ThreadingHTTPServer
from ptauth.web import App, make_handler
kwargs = {'clinic_timezone': sys.argv[3]} if len(sys.argv) > 3 and sys.argv[3] else {}
app = App(Path(sys.argv[1]), Path(sys.argv[2]), **kwargs)
app.as_of = date(2026, 10, 8)
app.run()
server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(app))
print(json.dumps({'port': server.server_address[1]}), flush=True)
server.serve_forever()
`;

before(async () => {
  browser = await chromium.launch({ headless: true,
    ...(process.env.PTAUTH_BROWSER_EXECUTABLE ? { executablePath: process.env.PTAUTH_BROWSER_EXECUTABLE } : {}) });
  console.log(`Chromium ${browser.version()}`);
});
after(async () => { if (browser) await browser.close(); });

function csv(rows) {
  return rows.map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(',')).join('\r\n') + '\r\n';
}
function visit(id, date, status = 'scheduled') {
  return [id, 'SYN-1', date, 'Visit clinic (synthetic)', 'Test PT', 'P', status, 'treatment'];
}

async function harness(t, { authorizationItem = false, legacy = false, clinicTimezone = '', coveredDate = '2026-09-20' } = {}) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'ptauth-browser-'));
  const data = path.join(root, 'data'), out = path.join(root, 'out');
  let child, context;
  const errors = [];
  t.after(async () => {
    if (context) await context.close();
    if (child && child.exitCode == null && child.signalCode == null) {
      const exited = once(child, 'exit');
      child.kill('SIGTERM');
      await exited;
    }
    await fs.rm(root, { recursive: true, force: true });
    assert.deepEqual(errors, []);
  });
  await fs.mkdir(data);
  const files = {
    'patients.csv': [['patient_id', 'display_name', 'clinic', 'primary_payer'], ['SYN-1', literalName, 'Home clinic', 'P']],
    'payers.csv': [['payer_id', 'payer_name', 'requires_auth', 'reauth_visits_before', 'reauth_days_before',
      'turnaround_days', 'annual_visit_limit', 'counts_evals', 'checklist'], ['P', 'Plan (placeholder)', 'Y', 0, 0, 0, '', 'Y', '']],
    'authorizations.csv': [['auth_no', 'patient_id', 'payer_id', 'visits_authorized', 'start_date', 'end_date', 'status'],
      ['A1', 'SYN-1', 'P', 10, '2026-09-01', '2026-11-30', 'approved']],
    'schedule.csv': [['visit_id', 'patient_id', 'visit_date', 'clinic', 'therapist', 'payer_id', 'status', 'visit_type'],
      visit('V-PAST-COVERED', coveredDate), visit('V-PAST-UNCOVERED', '2026-08-20'), visit('V-FUTURE', '2026-10-10'),
      ...(authorizationItem ? [visit('V-AFTER-AUTH', '2026-12-10')] : [])],
  };
  await Promise.all(Object.entries(files).map(([name, rows]) => fs.writeFile(path.join(data, name), csv(rows))));
  child = spawn(python, ['-u', '-c', serverSource, data, out, clinicTimezone], { cwd: source, stdio: ['ignore', 'pipe', 'pipe'] });
  let stderr = '';
  child.stderr.on('data', (chunk) => { stderr += chunk; });
  const port = await new Promise((resolve, reject) => {
    let buffer = '';
    const timer = setTimeout(() => reject(new Error(`Local app did not start: ${stderr}`)), 10000);
    child.once('error', (error) => { clearTimeout(timer); reject(error); });
    child.once('exit', (code) => { clearTimeout(timer); reject(new Error(`Local app exited ${code}: ${stderr}`)); });
    child.stdout.on('data', (chunk) => {
      buffer += chunk;
      if (buffer.includes('\n')) {
        clearTimeout(timer);
        try { resolve(JSON.parse(buffer.slice(0, buffer.indexOf('\n'))).port); }
        catch (error) { reject(error); }
      }
    });
  });
  if (legacy) {
    const saved = JSON.parse(await fs.readFile(path.join(out, 'summary.json'), 'utf8'));
    delete saved.visit_status_review;
    delete saved.visit_status_review_note;
    delete saved.counts.past_scheduled;
    await fs.writeFile(path.join(out, 'summary.json'), JSON.stringify(saved));
    await fs.rm(path.join(out, 'visit_status_review.csv'), { force: true });
  }
  const url = `http://127.0.0.1:${port}`;
  context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  page.on('pageerror', (error) => errors.push(error.message));
  page.setDefaultTimeout(4000);
  await page.goto(url);
  await page.locator('#cards .card').first().waitFor();
  assert.equal(await page.getByRole('button', { name: 'Visit status review', exact: true }).count(), 1);
  async function openReview() {
    const button = page.getByRole('button', { name: 'Visit status review', exact: true });
    await button.focus();
    await page.keyboard.press('Enter');
    await page.locator('#t-review').waitFor({ state: 'visible' });
  }
  async function rerun() {
    const response = page.waitForResponse((r) => r.url() === `${url}/api/run`);
    await page.getByRole('button', { name: 'Run worklist', exact: true }).click();
    assert.equal((await response).status(), 200);
    await page.waitForFunction(() => !document.getElementById('run').disabled);
  }
  return { page, context, data, out, url, openReview, rerun };
}

test('staff can inspect complete source rows with keyboard and download the review at narrow width', async (t) => {
  const h = await harness(t);
  await h.openReview();
  const rows = h.page.locator('#t-review tbody tr');
  assert.equal(await rows.count(), 2);
  assert.match(await rows.nth(0).textContent(), /V-PAST-UNCOVERED[\s\S]+schedule\.csv:row3/);
  assert.match(await rows.nth(1).textContent(), /V-PAST-COVERED[\s\S]+A1[\s\S]*Reserves one authorized visit[\s\S]+schedule\.csv:row2/);
  assert.ok((await rows.first().textContent()).includes(literalName));
  assert.equal(await h.page.locator('#t-review script').count(), 0);
  assert.equal(await h.page.locator('#cards .card').filter({ hasText: 'past scheduled visits' }).locator('b').textContent(), '2');
  assert.equal(await h.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  const region = h.page.getByRole('region', { name: 'Past scheduled appointments' });
  await region.focus();
  await h.page.keyboard.press('ArrowRight');
  await h.page.waitForFunction(() => document.querySelector('.review-table').scrollLeft > 0);
  const downloadReady = h.page.waitForEvent('download');
  await h.page.getByRole('link', { name: 'Download visit status review CSV' }).click();
  const download = await downloadReady;
  assert.equal(download.suggestedFilename(), 'visit_status_review.csv');
  const exported = await fs.readFile(await download.path(), 'utf8');
  assert.match(exported, /V-PAST-UNCOVERED[\s\S]*schedule\.csv:row3/);
  assert.match(exported, /V-PAST-COVERED[\s\S]*schedule\.csv:row2/);
  await h.page.getByRole('button', { name: 'Digest & exports' }).click();
  const popupReady = h.page.waitForEvent('popup');
  await h.page.getByRole('link', { name: 'Daily digest (printable HTML)' }).click();
  const digest = await popupReady;
  await digest.waitForLoadState();
  await digest.emulateMedia({ media: 'print' });
  const text = await digest.locator('body').textContent();
  assert.ok(text.includes('V-PAST-COVERED') && text.includes('V-PAST-UNCOVERED'));
  assert.ok(text.includes('schedule.csv:row2') && text.includes('schedule.csv:row3'));
});

test('approving an authorization item never hides its separate visit-status review', async (t) => {
  const h = await harness(t, { authorizationItem: true });
  const response = h.page.waitForResponse((r) => r.url() === `${h.url}/api/state`);
  await h.page.locator('#work select[data-k]').selectOption('approved');
  assert.equal((await response).status(), 200);
  await h.page.waitForFunction(() => document.querySelectorAll('#work select[data-k]').length === 0);
  await h.openReview();
  assert.equal(await h.page.locator('#t-review tbody tr').count(), 2);
  await h.page.reload();
  await h.openReview();
  assert.equal(await h.page.locator('#t-review tbody tr').count(), 2);
  const saved = JSON.parse(await fs.readFile(path.join(h.out, 'work_state.json'), 'utf8'));
  assert.equal(saved['SYN-1|P|A1'].state, 'approved');
});

test('correcting the source export and rerunning clears review while preserving the real ledger and auth alert', async (t) => {
  const h = await harness(t);
  await h.openReview();
  await fs.appendFile(path.join(h.data, 'schedule.csv'), csv([
    visit('V-PAST-COVERED', '2026-09-20', 'cancelled'),
    visit('V-PAST-UNCOVERED', '2026-08-20', 'completed'),
  ]));
  await h.rerun();
  assert.equal(await h.page.locator('#t-review tbody tr').count(), 0);
  assert.ok((await h.page.locator('#t-review').textContent()).includes('No past appointments remain marked scheduled.'));
  assert.equal(await h.page.locator('#cards .card').filter({ hasText: 'past scheduled visits' }).locator('b').textContent(), '0');
  const s = await (await fetch(`${h.url}/api/summary`)).json();
  assert.equal(s.ledger[0].scheduled, 1);
  assert.equal(s.ledger[0].remaining_after_scheduled, 9);
  await h.page.getByRole('button', { name: 'Daily worklist', exact: true }).click();
  assert.ok((await h.page.locator('#work').textContent()).includes('UNAUTHORIZED_DONE'));
  assert.equal(s.counts.unauthorized_done, 1);
  const csvText = await (await fetch(`${h.url}/out/visit_status_review.csv`)).text();
  assert.equal(csvText.trim().split(/\r?\n/).length, 1);
});

test('a saved pre-feature summary asks for a rerun and then exposes the actual review', async (t) => {
  const h = await harness(t, { legacy: true });
  await h.openReview();
  assert.ok((await h.page.locator('#t-review').textContent()).includes('Run worklist to build the visit-status review'));
  assert.equal(await h.page.getByRole('link', { name: 'Download visit status review CSV' }).count(), 0);
  assert.equal(await h.page.locator('#cards .card').filter({ hasText: 'past scheduled visits' }).locator('b').textContent(), '—');
  await h.rerun();
  assert.equal(await h.page.locator('#t-review tbody tr').count(), 2);
  assert.equal(await h.page.getByRole('link', { name: 'Download visit status review CSV' }).count(), 1);
});

test('the selected clinic zone determines which timestamped appointments need review and survives rerun', async (t) => {
  for (const [clinicTimezone, count] of [['America/Los_Angeles', 2], ['UTC', 1]]) {
    const h = await harness(t, { clinicTimezone, coveredDate: '2026-10-08T06:30:00Z' });
    await h.openReview();
    assert.equal(await h.page.locator('#timezone').textContent(), `Clinic time zone: ${clinicTimezone}`);
    assert.equal(await h.page.locator('#t-review tbody tr').count(), count);
    const current = await (await fetch(`${h.url}/api/summary`)).json();
    assert.equal(current.ledger[0].scheduled, 2);
    if (clinicTimezone === 'America/Los_Angeles') {
      const row = current.visit_status_review.find((r) => r.visit_id === 'V-PAST-COVERED');
      assert.equal(row.visit_date, '2026-10-07');
      assert.equal(row.days_since, 1);
      assert.equal(row.auth_no, 'A1');
    }
    await h.page.locator('#asof').fill('2026-10-09');
    await h.rerun();
    assert.equal(await h.page.locator('#t-review tbody tr').count(), 2);
    assert.equal(await h.page.locator('#timezone').textContent(), `Clinic time zone: ${clinicTimezone}`);
  }
});
