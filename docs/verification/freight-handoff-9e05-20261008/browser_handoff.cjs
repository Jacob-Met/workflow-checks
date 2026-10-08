// Real native freight UI and Blob-download receiving. No provider/network dependency.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn, spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.FREIGHT_TEST_PLAYWRIGHT);
const root = path.resolve(process.argv[2]);
const python = process.env.FREIGHT_TEST_PYTHON;
const source = path.join(root, 'candidate', 'freight_packets');
const evidence = path.join(root, 'browser-evidence');
const state = path.join(root, 'browser-state');
fs.mkdirSync(evidence, { recursive: true });
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const child = spawn(python, [path.join(root, 'qa_server.py'), source, state], {
  env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }, stdio: ['ignore', 'pipe', 'pipe']
});
let childLog = '', childError = '';
child.stderr.on('data', b => { childError += b; });
const ready = new Promise((resolve, reject) => {
  child.stdout.on('data', b => {
    childLog += b;
    const line = childLog.split('\n')[0];
    if (childLog.includes('\n')) {
      try { resolve(JSON.parse(line)); } catch (error) { reject(error); }
    }
  });
  child.on('error', reject);
  child.on('exit', code => reject(new Error('Native fixture server exited: ' + code + ': ' + childError)));
});
let browser, context, page, base, serverReceipt;
const checks = [], downloads = [], pageErrors = [], requests = [];
function treeHashes(dir) {
  const out = {};
  function walk(at) { for (const e of fs.readdirSync(at, { withFileTypes: true })) {
    const p = path.join(at, e.name);
    if (e.isDirectory()) walk(p);
    else if (e.isFile()) out[path.relative(dir, p)] = hash(fs.readFileSync(p));
  }}
  walk(dir); return out;
}
async function summary() {
  const r = await context.request.get(base + '/api/summary');
  assert.equal(r.status(), 200);
  return r.json();
}
async function loaded() {
  await page.locator('#t-packets tr[data-l]').first().waitFor();
  await page.waitForFunction(() => document.querySelector('#download-review-bundle') &&
    !document.querySelector('#download-review-bundle').disabled);
}
async function reload() { await page.goto(base); await loaded(); }
async function selected() { return page.locator('#t-packets tr.sel').getAttribute('data-l'); }
async function waitStatus(pattern) {
  await page.waitForFunction(source => new RegExp(source).test(document.querySelector('#bundle-status')?.textContent || ''), pattern.source);
}
async function saveDecision(load, decision, note) {
  const s = await summary();
  const r = await context.request.post(base + '/api/decision', { data: {
    load_id: load, decision, note, evidence_version: s.evidence_versions[load]
  }});
  assert.equal(r.status(), 200, await r.text());
  return summary();
}
async function download(name) {
  const s = await summary(), load = await selected();
  const prior = treeHashes(state);
  const event = page.waitForEvent('download');
  await page.locator('#download-review-bundle').click();
  const d = await event;
  assert.match(d.suggestedFilename(), /^freight-review-[A-Za-z0-9_.-]+\.zip$/);
  const file = path.join(evidence, name + '.zip');
  await d.saveAs(file);
  assert.equal(await d.failure(), null);
  await waitStatus(/Saved review downloaded/);
  assert.deepEqual(treeHashes(state), prior, 'Downloading changed native input/output files');
  const snap = path.join(evidence, name + '-summary.json');
  fs.writeFileSync(snap, JSON.stringify(s, null, 2) + '\n');
  const inspected = spawnSync(python, [path.join(root, 'inspect_bundle.py'), file, snap,
    path.join(evidence, name), path.join(evidence, name + '-receipt.json')], { encoding: 'utf8' });
  assert.equal(inspected.status, 0, inspected.stderr);
  const receipt = JSON.parse(inspected.stdout.trim());
  assert.equal(receipt.load_id, load);
  const packet = s.packets.find(p => p.load_id === load);
  assert.deepEqual(fs.readFileSync(path.join(evidence, name, 'packet.html')),
    fs.readFileSync(path.join(state, 'out', packet.file)), 'Downloaded packet differs from native output');
  return { receipt, summary: s, load, file, folder: path.join(evidence, name) };
}
async function delayedBundle() {
  let release, resolveSeen;
  const seen = new Promise(resolve => { resolveSeen = resolve; });
  const hold = new Promise(resolve => { release = resolve; });
  const record = { actual_native_status: null, attempted_delivery: false, delivery_error: null };
  await page.route('**/api/review-bundle?*', async route => {
    try {
      const response = await route.fetch();
      record.actual_native_status = response.status();
      const body = await response.body();
      resolveSeen();
      await hold;
      record.attempted_delivery = true;
      try { await route.fulfill({ status: response.status(), headers: response.headers(), body }); }
      catch (e) { record.delivery_error = String(e); }
    } catch (e) { record.delivery_error = String(e); resolveSeen(); }
  });
  await page.locator('#download-review-bundle').click();
  await seen;
  assert.equal(record.actual_native_status, 200);
  return { release, record };
}
async function runCheck(name, fn) {
  const start = Date.now(), beforeDownloads = downloads.length;
  try {
    await reload();
    const detail = await fn();
    checks.push({ name, passed: true, milliseconds: Date.now() - start, downloads: downloads.length - beforeDownloads, detail });
    console.log('PASS ' + name);
  } catch (error) {
    const screenshot = name.replace(/[^A-Za-z0-9_-]/g, '-') + '-failure.png';
    await page.screenshot({ path: path.join(evidence, screenshot), fullPage: true }).catch(() => {});
    checks.push({ name, passed: false, milliseconds: Date.now() - start, error: String(error), stack: error.stack, screenshot });
    console.log('FAIL ' + name + ': ' + error);
  } finally { await page.unrouteAll({ behavior: 'ignoreErrors' }); }
}
(async () => {
  try {
    serverReceipt = await ready;
    base = serverReceipt.base_url;
    browser = await chromium.launch({ executablePath: process.env.FREIGHT_TEST_CHROMIUM, headless: true });
    context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, acceptDownloads: true });
    page = await context.newPage();
    page.setDefaultTimeout(8000);
    page.on('pageerror', e => pageErrors.push(String(e)));
    page.on('download', d => downloads.push({ filename: d.suggestedFilename(), at: new Date().toISOString() }));
    page.on('request', r => { if (r.url().includes('/api/review-bundle')) requests.push({ method: r.method(), url: r.url() }); });
    await runCheck('01 unreviewed native ZIP and read-only state', async () => {
      const d = await download('unreviewed');
      assert.equal(d.summary.decisions[d.load], undefined);
      assert.match(fs.readFileSync(path.join(d.folder, 'index.html'), 'utf8'), /Not reviewed/);
      return d.receipt;
    });
    await runCheck('02 unsaved note gate, undo, save and readable offline cover', async () => {
      const note = 'Receiver reviewed this load — <script>window.noteExecuted=1</script> café';
      await page.locator('#note').fill(note);
      assert.equal(await page.locator('#download-review-bundle').isDisabled(), true);
      await waitStatus(/Save or undo/);
      await page.locator('#note').fill('');
      assert.equal(await page.locator('#download-review-bundle').isEnabled(), true);
      await page.locator('#note').fill(note);
      const accepted = page.waitForResponse(r => r.url().endsWith('/api/decision') && r.status() === 200);
      await page.locator('button[data-d="approve"]').click();
      await accepted; await loaded();
      const d = await download('saved-review');
      assert.equal(d.summary.decisions[d.load].note, note);
      const cover = await context.newPage();
      await cover.goto(pathToFileURL(path.join(d.folder, 'index.html')).href);
      assert.equal(await cover.locator('h2').filter({ hasText: 'Current saved review: Approve' }).count(), 1);
      assert.equal(await cover.locator('.note').first().textContent(), note);
      assert.equal(await cover.evaluate(() => window.noteExecuted), undefined);
      assert.equal(await cover.locator('a[href="packet.html"]').count(), 1);
      await cover.screenshot({ path: path.join(evidence, 'offline-cover.png'), fullPage: true });
      await cover.locator('a[href="packet.html"]').click();
      assert.match(await cover.locator('body').innerText(), new RegExp(d.load));
      await cover.close();
      await page.screenshot({ path: path.join(evidence, 'native-review.png'), fullPage: true });
      return d.receipt;
    });
    await runCheck('03 same accepted snapshot gives identical ZIP bytes', async () => {
      const first = await download('stable-a'), second = await download('stable-b');
      assert.deepEqual(fs.readFileSync(first.file), fs.readFileSync(second.file));
      return { first: first.receipt.sha256, second: second.receipt.sha256 };
    });
    await runCheck('04 selected history retained and other load excluded', async () => {
      const s = await summary(), load = await selected(), other = s.packets.find(p => p.load_id !== load).load_id;
      await saveDecision(other, 'reject', 'OTHER_LOAD_PRIVATE_NOTE_DO_NOT_EXPORT');
      await saveDecision(load, 'adjust', 'Selected-load follow-up: check supporting documents.');
      await reload();
      const d = await download('history');
      const review = JSON.parse(fs.readFileSync(path.join(d.folder, 'review.json'))).review;
      assert.equal(review.history.length, 1);
      assert.equal(review.decision, 'adjust');
      for (const member of ['index.html', 'review.json', 'evidence.json']) {
        assert.doesNotMatch(fs.readFileSync(path.join(d.folder, member), 'utf8'), /OTHER_LOAD_PRIVATE_NOTE_DO_NOT_EXPORT/);
      }
      return d.receipt;
    });
    await runCheck('05 newer saved review rejects old visible download and reload recovers', async () => {
      const load = await selected(), count = downloads.length;
      await saveDecision(load, 'approve', 'Saved after the displayed snapshot');
      const response = page.waitForResponse(r => r.url().includes('/api/review-bundle'));
      await page.locator('#download-review-bundle').click();
      assert.equal((await response).status(), 409);
      await waitStatus(/saved review changed/);
      assert.equal(downloads.length, count);
      await reload();
      const d = await download('newer-review');
      assert.equal(d.summary.decisions[load].note, 'Saved after the displayed snapshot');
      return d.receipt;
    });
    await runCheck('06 cancel suppresses delayed genuine response and recovers', async () => {
      const count = downloads.length, delayed = await delayedBundle();
      assert.equal(await page.locator('#cancel-review-bundle').isVisible(), true);
      await page.locator('#cancel-review-bundle').click();
      delayed.release();
      await waitStatus(/Download canceled/);
      await pause(120);
      assert.equal(downloads.length, count);
      assert.equal(await page.locator('#download-review-bundle').isEnabled(), true);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      const d = await download('cancel-recovery');
      return { delayed: delayed.record, recovered: d.receipt };
    });
    await runCheck('07 selection change suppresses late old-load response', async () => {
      const s = await summary(), old = await selected(), next = s.packets.find(p => p.load_id !== old).load_id;
      const count = downloads.length, delayed = await delayedBundle();
      await page.locator('#t-packets tr[data-l="' + next + '"]').click();
      delayed.release(); await pause(160);
      assert.equal(await selected(), next);
      assert.equal(downloads.length, count);
      assert.equal(await page.locator('#download-review-bundle').isEnabled(), true);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      const d = await download('other-selected');
      assert.equal(d.load, next);
      return { delayed: delayed.record, recovered: d.receipt };
    });
    await runCheck('08 note edit cancels delayed response and undo re-enables', async () => {
      const saved = await page.locator('#note').inputValue(), count = downloads.length;
      const delayed = await delayedBundle();
      await page.locator('#note').fill(saved + ' UNSAVED');
      delayed.release(); await waitStatus(/Save or undo/); await pause(160);
      assert.equal(downloads.length, count);
      assert.equal(await page.locator('#download-review-bundle').isDisabled(), true);
      await page.locator('#note').fill(saved);
      await page.waitForFunction(() => !document.querySelector('#download-review-bundle').disabled);
      return delayed.record;
    });
    await runCheck('09 pipeline rerun cancels pending prior gesture', async () => {
      const count = downloads.length, delayed = await delayedBundle();
      const rerun = page.waitForResponse(r => r.url().endsWith('/api/run') && r.status() === 200);
      await page.locator('#run').click();
      await rerun; delayed.release(); await loaded(); await pause(160);
      assert.equal(downloads.length, count);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      return (await download('rerun-current')).receipt;
    });
    await runCheck('10 failed decision preserves unsaved note and keeps download held', async () => {
      const load = await selected(), note = 'Unsaved note retained after genuine evidence conflict';
      const old = (await summary()).evidence_versions[load];
      await page.locator('#note').fill(note);
      const generated = await context.request.post(base + '/api/generate', { data: { seed: 8 } });
      assert.equal(generated.status(), 200);
      assert.notEqual((await generated.json()).evidence_versions[load], old);
      const rejected = page.waitForResponse(r => r.url().endsWith('/api/decision') && r.status() === 409);
      await page.locator('button[data-d="approve"]').click();
      await rejected;
      await page.waitForFunction(expected => document.querySelector('#note')?.value === expected &&
        !document.querySelector('button[data-d="approve"]')?.disabled, note);
      assert.equal(await page.locator('#note').inputValue(), note);
      assert.equal(await page.locator('#download-review-bundle').isDisabled(), true,
        'Restored unsaved note must leave the displayed download control disabled');
      await waitStatus(/Save or undo/);
      const saved = (await summary()).decisions[load]?.note || '';
      await page.locator('#note').fill(saved);
      await page.waitForFunction(() => !document.querySelector('#download-review-bundle').disabled);
      return (await download('stale-saved-review')).receipt;
    });
    await runCheck('11 native missing-packet response produces no download', async () => {
      const load = await selected(), s = await summary(), row = s.packets.find(p => p.load_id === load);
      const file = path.join(state, 'out', row.file), original = fs.readFileSync(file), count = downloads.length;
      fs.unlinkSync(file);
      try {
        const rejected = page.waitForResponse(r => r.url().includes('/api/review-bundle'));
        await page.locator('#download-review-bundle').click();
        assert.equal((await rejected).status(), 404);
        await waitStatus(/no download was made/);
        assert.equal(downloads.length, count);
      } finally { fs.writeFileSync(file, original); }
      return { status: 404, downloads: 0 };
    });
    assert.deepEqual(pageErrors, [], 'Uncaught page errors');
  } catch (error) {
    checks.push({ name: 'carrier', passed: false, error: String(error), stack: error.stack });
  } finally {
    await browser?.close().catch(() => {});
    child.kill('SIGTERM');
    await new Promise(resolve => { if (child.exitCode !== null) resolve(); else { child.once('exit', resolve); setTimeout(resolve, 2000); } });
    const result = { schema: 'freight-handoff-browser.v1', source, captured_at: new Date().toISOString(),
      server: serverReceipt, chromium: process.env.FREIGHT_TEST_CHROMIUM, node: process.version,
      passed: checks.length === 11 && checks.every(c => c.passed) && !pageErrors.length,
      checks, page_errors: pageErrors, downloads, bundle_requests: requests,
      server_stderr: childError, limits: [
        'Synthetic native seed7 fixture; seed8 change is through native API.',
        'Disposable local server and fresh headless browser context; no external provider or user browser.',
        'Delayed-response cases receive genuine native ZIP bytes through a browser route before holding delivery.',
        'No assertion of distributed writers, remote sending, payment, or any change to freight calculation rules.'
      ] };
    fs.writeFileSync(path.join(evidence, 'result.json'), JSON.stringify(result, null, 2) + '\n');
    fs.writeFileSync(path.join(evidence, 'server.log'), childLog + '\nSTDERR:\n' + childError);
    console.log(JSON.stringify({ passed: result.passed, checks: checks.length, passing: checks.filter(c => c.passed).length,
      downloads: downloads.length, result: path.join(evidence, 'result.json') }));
    process.exitCode = result.passed ? 0 : 1;
  }
})();
