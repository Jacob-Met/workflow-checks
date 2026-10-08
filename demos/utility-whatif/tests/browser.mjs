// Optional native receiving. Existing Chrome/Playwright only; fresh profiles.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, dirname, sep, extname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(process.env.UTILITY_INSTALL_DIR || resolve(here, '..'));
const out = resolve(process.env.UTILITY_EVIDENCE || resolve(here, '../out/browser'));
const fixture = JSON.parse(await readFile(resolve(root, 'fixture.json')));
const original = fixture.bills.find(b => b.bill_id === fixture.selectedBill);
const { chromium } = await import(process.env.UTILITY_PLAYWRIGHT ? pathToFileURL(process.env.UTILITY_PLAYWRIGHT).href : 'playwright');
const served = new Map(), checks = [], failures = [], errors = [], external = [];
const types = { '.html': 'text/html', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json' };
const server = createServer(async (req, res) => {
  try {
    const pathname = new URL(req.url, 'http://localhost').pathname;
    const file = resolve(root, '.' + (pathname === '/' ? '/index.html' : decodeURIComponent(pathname)));
    if (!file.startsWith(root + sep)) throw new Error('outside root');
    const bytes = await readFile(file);
    served.set(file.slice(root.length + 1), createHash('sha256').update(bytes).digest('hex'));
    res.writeHead(200, { 'content-type': types[extname(file)] || 'application/octet-stream', 'cache-control': 'no-store' }); res.end(bytes);
  } catch { res.writeHead(404); res.end('Not found'); }
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
const origin = `http://127.0.0.1:${server.address().port}`;
async function check(name, run) { try { await run(); checks.push({ name, passed: true }); } catch (error) { const failure = { name, passed: false, error: error.message }; checks.push(failure); failures.push(failure); } }
let browser;
try {
  browser = await chromium.launch({ headless: true, ...(process.env.UTILITY_CHROME ? { executablePath: process.env.UTILITY_CHROME } : {}) });
  for (const [label, viewport] of [['desktop', { width: 1440, height: 1000 }], ['phone', { width: 390, height: 844 }]]) {
    const context = await browser.newContext({ viewport });
    await context.route('**/*', route => { if (new URL(route.request().url()).origin === origin) return route.continue(); external.push(route.request().url()); return route.abort(); });
    const page = await context.newPage(); page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin, { waitUntil: 'networkidle' }); await page.locator('#explorer').waitFor({ state: 'visible' });
    await check(label + ': actual synthetic baseline and source rows render', async () => {
      assert.equal(await page.locator('#usage-status').innerText(), 'USAGE SPIKE');
      assert.equal(await page.locator('#rate-status').innerText(), 'WITHIN RATE RULE');
      assert.equal(await page.locator('#result-count').innerText(), '1 of 2 checks flagged');
      assert.match(await page.locator('#evidence-body').innerText(), /bills\.csv:33/);
      assert.match(await page.locator('#evidence-body').innerText(), /bills\.csv:21/);
      assert.match(await page.locator('.synthetic').innerText(), /Synthetic/i);
      assert.match(await page.locator('footer').innerText(), /do not approve a bill/);
    });
    await check(label + ': actual presets change comparisons and restore independently', async () => {
      await page.locator('[data-preset="typical"]').click();
      assert.equal(await page.locator('#result-count').innerText(), '0 of 2 checks flagged');
      await page.locator('[data-preset="rate"]').click();
      assert.equal(await page.locator('#usage-status').innerText(), 'WITHIN USAGE RULE');
      assert.equal(await page.locator('#rate-status').innerText(), 'RATE CHANGE');
      await page.locator('[data-preset="period"]').click();
      assert.match(await page.locator('#period-summary').innerText(), /30 inclusive days.*May 2026/);
      await page.locator('[data-preset="typical"]').click();
      assert.equal(await page.locator('#ps').inputValue(), original.ps);
      assert.equal(await page.locator('#pe').inputValue(), original.pe);
      assert.equal(await page.locator('#result-count').innerText(), '0 of 2 checks flagged');
    });
    await check(label + ': draft and invalid period retain and label the previous result', async () => {
      const previous = await page.locator('#usage-value').innerText();
      await page.locator('#usage').fill('5000');
      assert.match(await page.locator('#freshness').innerText(), /not checked yet/);
      assert.equal(await page.locator('#usage-value').innerText(), previous);
      await page.locator('#ps').fill('2026-05-01'); await page.locator('#pe').fill('2026-04-30');
      await page.locator('button[type="submit"]').click();
      assert.match(await page.locator('#input-error').innerText(), /end date/);
      assert.match(await page.locator('#freshness').innerText(), /previous checked values/);
      assert.equal(await page.locator('#usage-value').innerText(), previous);
      assert.equal(await page.locator('#usage').inputValue(), '5000');
    });
    await check(label + ': exact amount validation and keyboard recovery work', async () => {
      await page.locator('#ps').fill(original.ps); await page.locator('#pe').fill(original.pe);
      await page.locator('#amount').fill('12.345'); await page.locator('button[type="submit"]').click();
      assert.match(await page.locator('#input-error').innerText(), /two decimal places/);
      await page.locator('#amount').fill('5500');
      await page.locator('#usage').focus(); await page.keyboard.press('Tab');
      assert.equal(await page.evaluate(() => document.activeElement.id), 'amount');
      await page.locator('button[type="submit"]').focus(); await page.keyboard.press('Enter');
      assert.equal(await page.locator('#input-error').innerText(), '');
      assert.equal(await page.locator('#usage-status').innerText(), 'USAGE SPIKE');
      assert.match(await page.locator('#freshness').innerText(), /currently shown/);
    });
    await check(label + ': leap dates and unevaluated history do not become a clean bill', async () => {
      await page.locator('#ps').fill('2026-01-01'); await page.locator('#pe').fill('2026-04-15');
      await page.locator('button[type="submit"]').click();
      assert.match(await page.locator('#period-summary').innerText(), /105 inclusive days.*March 2026/);
      assert.match(await page.locator('.field-help').last().innerText(), /latest month wins a tie for the most days/);
      await page.locator('#ps').fill('2024-02-01'); await page.locator('#pe').fill('2024-02-29');
      await page.locator('button[type="submit"]').click();
      assert.match(await page.locator('#period-summary').innerText(), /29 inclusive days.*February 2024/);
      assert.equal(await page.locator('#result-title').innerText(), 'Comparison unavailable');
      assert.match(await page.locator('#review-notes').innerText(), /precedes the fixed evaluation start/);
      assert.equal(await page.locator('#usage-status').innerText(), 'NOT JUDGED');
    });
    await check(label + ': a duplicated fixture interval is withheld before comparison', async () => {
      const b = fixture.bills.find(b => b.bill_id !== original.bill_id && b.ps >= fixture.evalFrom && b.received < original.received);
      assert(b, 'prior evaluated fixture bill');
      await page.locator('#ps').fill(b.ps); await page.locator('#pe').fill(b.pe); await page.locator('#amount').fill(String(b.amount));
      await page.locator('button[type="submit"]').click();
      assert.equal(await page.locator('#result-title').innerText(), 'Comparison unavailable');
      assert.match(await page.locator('#review-notes').innerText(), new RegExp(b.bill_id));
      assert.equal(await page.locator('#rate-status').innerText(), 'NOT JUDGED');
    });
    await page.locator('[data-preset="original"]').click();
    await check(label + ': viewport and form remain usable', async () => {
      const size = await page.evaluate(() => ({ window: innerWidth, body: document.documentElement.scrollWidth }));
      assert(size.body <= size.window + 1, JSON.stringify(size));
      for (const id of ['usage', 'amount', 'ps', 'pe']) assert.equal(await page.locator('#' + id).isVisible(), true);
    });
    await mkdir(out, { recursive: true }); await page.screenshot({ path: resolve(out, label + '.png'), fullPage: true });
    await context.close();
  }
  const context = await browser.newContext();
  const page = await context.newPage(); page.on('pageerror', error => errors.push(error.message));
  await context.route('**/*', route => { if (new URL(route.request().url()).origin === origin) return route.continue(); external.push(route.request().url()); return route.abort(); });
  await check('a mixed fixture source version refuses to show stale results', async () => {
    const bad = structuredClone(fixture); bad.source.files['utility_watch/uwatch/engine.py'].gitBlob = 'injected-wrong-source';
    await context.route('**/fixture.json', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify(bad) }));
    await page.goto(origin, { waitUntil: 'networkidle' });
    assert.match(await page.locator('#loading').innerText(), /fixture and checked rule version differ/);
    assert.equal(await page.locator('#explorer').isVisible(), false);
    await context.unroute('**/fixture.json');
  });
  await check('failed sample loading supports an explicit fresh reload', async () => {
    await context.route('**/fixture.json', route => route.fulfill({ status: 503, body: 'synthetic loading refusal' }));
    await page.reload({ waitUntil: 'networkidle' });
    assert.match(await page.locator('#loading').innerText(), /could not be loaded/);
    assert.equal(await page.locator('#explorer').isVisible(), false);
    await context.unroute('**/fixture.json');
    await page.reload({ waitUntil: 'networkidle' });
    assert.equal(await page.locator('#explorer').isVisible(), true);
    assert.equal(await page.locator('#usage-status').innerText(), 'USAGE SPIKE');
  });
  await context.close();
  await check('served bytes match the five installed assets and no external calls occur', async () => {
    for (const name of ['index.html', 'styles.css', 'app.mjs', 'model.mjs', 'fixture.json']) assert.equal(served.get(name), createHash('sha256').update(await readFile(resolve(root, name))).digest('hex'), name);
    assert.deepEqual(errors, []); assert.deepEqual(external, []);
  });
} catch (error) { failures.push({ name: 'native receiving setup', passed: false, error: error.stack }); }
finally {
  const receipt = { schema: 'utility-watch.whatif-browser-receiving.v1', at: new Date().toISOString(), node: process.version, browser: browser?.version() || null, source: root, sourceCommit: fixture.source.commit, engineBlob: fixture.source.files['utility_watch/uwatch/engine.py'].gitBlob, origin, servedSha256: Object.fromEntries([...served].sort()), checks, failures, pageErrors: errors, externalRequests: external, passed: failures.length === 0 };
  await mkdir(out, { recursive: true }); await writeFile(resolve(out, 'receipt.json'), JSON.stringify(receipt, null, 2) + '\n'); console.log(JSON.stringify(receipt, null, 2));
  await browser?.close(); await new Promise(done => server.close(done));
}
if (failures.length) process.exitCode = 1;
