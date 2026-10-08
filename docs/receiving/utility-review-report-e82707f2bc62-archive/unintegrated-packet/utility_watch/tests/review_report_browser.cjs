'use strict';

// Real Chrome receiving for the saved review report. Requires installed Chrome
// and Node's built-in WebSocket; there is no browser download or DOM substitute.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync, spawn, spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');

const repo = path.resolve(__dirname, '../..');
const out = process.argv[2] ? path.resolve(process.argv[2]) : fs.mkdtempSync(path.join(os.tmpdir(), 'uwatch-browser-'));
fs.mkdirSync(out, { recursive: true });
assert.equal(fs.readdirSync(out).length, 0, 'receiving output must be a new empty directory');
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const git = args => execFileSync('git', args, { cwd: repo, encoding: 'utf8' }).trim();
const receipt = { schema: 'uwatch-review-report-browser/1', accepted: false, groups: [], artifacts: [] };
let chrome;
let socket;
let profile;
let chromeLog = '';
let serial = 0;
const pending = new Map();
const pageErrors = [];
const externalRequests = [];

function save(name, value) {
  const bytes = Buffer.isBuffer(value) ? value : Buffer.from(value);
  fs.writeFileSync(path.join(out, name), bytes, { flag: 'wx' });
  receipt.artifacts.push({ name, bytes: bytes.length, sha256: sha(bytes) });
}
function sourceHashes() {
  const names = git(['ls-files', '-z']).split('\0').filter(Boolean);
  return Object.fromEntries(names.map(name => [name, sha(fs.readFileSync(path.join(repo, name)))]));
}
function installedChrome() {
  const explicit = process.env.UWATCH_CHROME;
  if (explicit) {
    assert.ok(fs.statSync(explicit).isFile(), 'UWATCH_CHROME must be an installed browser file');
    return path.resolve(explicit);
  }
  for (const name of ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser']) {
    const result = spawnSync('which', [name], { encoding: 'utf8' });
    if (result.status === 0 && result.stdout.trim()) return result.stdout.trim();
  }
  throw new Error('No installed Chrome/Chromium executable; real browser receiving is required');
}
async function until(check, message, timeout = 10000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    if (await check()) return;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw new Error(message);
}
async function command(method, params = {}) {
  const id = ++serial;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('CDP timeout: ' + method)); }, 10000);
    pending.set(id, { resolve, reject, timer, method });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(fn, arg) {
  const expression = '(' + fn.toString() + ')(' + JSON.stringify(arg ?? null) + ')';
  const result = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function key(name, code, virtualKey, modifiers = 0) {
  const fields = { key: name, code, windowsVirtualKeyCode: virtualKey, nativeVirtualKeyCode: virtualKey, modifiers };
  await command('Input.dispatchKeyEvent', { type: 'keyDown', ...fields });
  await command('Input.dispatchKeyEvent', { type: 'keyUp', ...fields });
}
async function click(id) {
  const box = await evaluate(value => {
    const element = document.getElementById(value);
    element.scrollIntoView({ block: 'center' });
    const rect = element.getBoundingClientRect();
    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
  }, id);
  await command('Input.dispatchMouseEvent', { type: 'mousePressed', ...box, button: 'left', buttons: 1, clickCount: 1 });
  await command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...box, button: 'left', buttons: 0, clickCount: 1 });
}
async function select(id, value) {
  const index = await evaluate(({ id, value }) => {
    const element = document.getElementById(id);
    element.focus();
    return Array.from(element.options).findIndex(option => option.value === value);
  }, { id, value });
  assert.ok(index >= 0, 'select option exists: ' + id + '/' + value);
  await key('Home', 'Home', 36);
  for (let i = 0; i < index; i += 1) await key('ArrowDown', 'ArrowDown', 40);
  await key('Tab', 'Tab', 9);
  assert.equal(await evaluate(id => document.getElementById(id).value, id), value);
}
async function search(value) {
  await evaluate(() => document.getElementById('search').focus());
  await key('a', 'KeyA', 65, 2);
  if (value) await command('Input.insertText', { text: value });
  else await key('Backspace', 'Backspace', 8);
  assert.equal(await evaluate(() => document.getElementById('search').value), value);
}
async function shown() {
  return evaluate(() => ({
    records: Array.from(document.querySelectorAll('article')).filter(element => element.getClientRects().length > 0).map(element => ({
      state: element.dataset.state, status: element.dataset.status,
      text: element.innerText,
    })),
    showing: document.getElementById('showing').innerText,
    noMatches: document.getElementById('no-matches').getClientRects().length > 0,
  }));
}
async function screenshot(name) {
  await evaluate(() => window.scrollTo(0, 0));
  const result = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
  save(name, Buffer.from(result.data, 'base64'));
}
async function noOverflow(width) {
  await command('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false });
  const dimensions = await evaluate(() => ({
    viewport: innerWidth, document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  assert.ok(dimensions.document <= dimensions.viewport + 1 && dimensions.body <= dimensions.viewport + 1,
    'horizontal overflow: ' + JSON.stringify(dimensions));
  return dimensions;
}

async function main() {
  assert.equal(typeof WebSocket, 'function', 'Node built-in WebSocket is required (Node 22.4+)');
  const executable = installedChrome();
  receipt.runtime = {
    node: process.version, chromePath: executable,
    chromeVersion: execFileSync(executable, ['--version'], { encoding: 'utf8' }).trim(),
    imageOS: process.env.ImageOS || null, imageVersion: process.env.ImageVersion || null,
  };
  assert.match(receipt.runtime.chromeVersion, /Chrom(e|ium)/);
  receipt.checkout = { commit: git(['rev-parse', 'HEAD']), tree: git(['rev-parse', 'HEAD^{tree}']),
    parents: git(['show', '-s', '--format=%P', 'HEAD']).split(' ').filter(Boolean),
    githubSHA: process.env.GITHUB_SHA || null, event: process.env.GITHUB_EVENT_NAME || null,
    run: process.env.GITHUB_RUN_ID || null, attempt: process.env.GITHUB_RUN_ATTEMPT || null };
  if (receipt.checkout.githubSHA) assert.equal(receipt.checkout.commit, receipt.checkout.githubSHA);
  assert.equal(git(['status', '--porcelain=v1']), '', 'checkout is clean before receiving');
  const before = sourceHashes();
  save('source-before.json', JSON.stringify(before, null, 2) + '\n');

  const python = [
    'import hashlib,json,os,runpy,subprocess,sys',
    'from pathlib import Path',
    'repo,out=map(Path,sys.argv[1:])',
    'source=repo/"utility_watch"',
    'sys.path.insert(0,str(source))',
    'ns=runpy.run_path(str(source/"tests/test_review_report.py"))',
    'worksheet,commands=ns["create_fixture"](out/"fixture",source)',
    'output=out/"review.html"',
    'command=[sys.executable,"-B","-m","uwatch","review-report","--worksheet",str(worksheet),"--out",str(output)]',
    'result=subprocess.run(command,cwd=source,env=dict(os.environ,PYTHONPATH=str(source),PYTHONDONTWRITEBYTECODE="1"),capture_output=True,text=True,timeout=30)',
    'commands.append({"args":command,"returncode":result.returncode,"stdout":result.stdout,"stderr":result.stderr})',
    '(out/"native-commands.json").write_text(json.dumps(commands,indent=2)+"\\n")',
    'assert result.returncode==0,commands[-1]',
    'print(json.dumps({"worksheet":str(worksheet),"worksheet_sha256":hashlib.sha256(worksheet.read_bytes()).hexdigest(),"report_sha256":hashlib.sha256(output.read_bytes()).hexdigest()}))',
  ].join('\n');
  const fixture = execFileSync(process.env.UWATCH_PYTHON || 'python3', ['-B', '-c', python, repo, out],
    { cwd: repo, encoding: 'utf8', env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }, timeout: 60000 });
  receipt.fixture = JSON.parse(fixture.trim());
  profile = fs.mkdtempSync(path.join(os.tmpdir(), 'uwatch-browser-profile-'));
  chrome = spawn(executable, [
    '--headless=new', '--no-sandbox', '--no-first-run', '--no-default-browser-check',
    '--disable-background-networking', '--disable-component-update', '--disable-sync', '--disable-default-apps',
    '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0', '--user-data-dir=' + profile, 'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] });
  chrome.on('error', error => { chromeLog += String(error); });
  chrome.stderr.on('data', bytes => { if (chromeLog.length < 2 * 1024 * 1024) chromeLog += bytes.toString(); });
  const portFile = path.join(profile, 'DevToolsActivePort');
  await until(() => fs.existsSync(portFile), 'Chrome did not create its real DevTools endpoint');
  const port = Number(fs.readFileSync(portFile, 'utf8').split('\n')[0]);
  assert.ok(Number.isSafeInteger(port) && port > 0);
  const pages = await (await fetch('http://127.0.0.1:' + port + '/json/list')).json();
  const page = pages.find(value => value.type === 'page');
  assert.ok(page && page.webSocketDebuggerUrl, 'fresh Chrome page exists');
  socket = new WebSocket(page.webSocketDebuggerUrl);
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id) {
      const request = pending.get(message.id);
      if (!request) return;
      pending.delete(message.id); clearTimeout(request.timer);
      if (message.error) request.reject(new Error(request.method + ': ' + JSON.stringify(message.error)));
      else request.resolve(message.result);
    } else if (message.method === 'Runtime.exceptionThrown') pageErrors.push(message.params);
    else if (message.method === 'Network.requestWillBeSent' && /^https?:/i.test(message.params.request.url)) {
      externalRequests.push(message.params.request.url);
    }
  });
  await until(() => socket.readyState === WebSocket.OPEN, 'Chrome WebSocket did not open');
  await command('Page.enable');
  await command('Runtime.enable');
  await command('Network.enable');
  receipt.browser = await command('Browser.getVersion');
  assert.match(receipt.browser.product, /Chrom(e|ium)/);
  await noOverflow(1280);
  const navigation = await command('Page.navigate', { url: pathToFileURL(path.join(out, 'review.html')).href });
  assert.ok(!navigation.errorText, navigation.errorText);
  await until(() => evaluate(() => document.readyState === 'complete' && document.getElementById('controls')
    && !document.getElementById('controls').hidden), 'real report did not initialize');
  let state = await shown();
  assert.equal(state.records.length, 2);
  assert.ok(state.records.every(record => record.state === 'current'));
  assert.match(state.showing, /Showing 2 of 4/);
  receipt.groups.push({ name: 'native report and initial current view', records: state.records.length });
  receipt.desktop = await noOverflow(1280);
  await screenshot('desktop-current.png');

  await evaluate(() => document.getElementById('search').focus());
  const focus = [];
  for (const expected of ['state', 'status', 'reviewer', 'reset', 'print']) {
    await key('Tab', 'Tab', 9);
    const actual = await evaluate(() => ({ id: document.activeElement.id,
      focusVisible: document.activeElement.matches(':focus-visible') }));
    assert.equal(actual.id, expected);
    assert.equal(actual.focusVisible, true);
    focus.push(actual.id);
  }
  receipt.groups.push({ name: 'real keyboard tab order and visible focus', focus });

  await select('state', 'all');
  assert.equal((await shown()).records.length, 4);
  await search('SYN-B');
  state = await shown();
  assert.equal(state.records.length, 2);
  assert.ok(state.records.every(record => record.text.includes('SYN-B')));
  await select('status', 'reviewed');
  state = await shown();
  assert.equal(state.records.length, 1);
  assert.equal(state.records[0].state, 'changed');
  const alex = await evaluate(() => Array.from(document.getElementById('reviewer').options)
    .find(option => option.text === 'Assigned: Alex & Co').value);
  await select('reviewer', alex);
  state = await shown();
  assert.equal(state.records.length, 0);
  assert.equal(state.noMatches, true);
  await click('reset');
  assert.equal((await shown()).records.length, 2);
  assert.deepEqual(await evaluate(() => ['search', 'state', 'status', 'reviewer']
    .map(id => document.getElementById(id).value)), ['', 'current', 'all', 'all']);
  receipt.groups.push({ name: 'real combined state/search/status/reviewer controls and reset', accepted: true });

  await select('state', 'history');
  const blair = await evaluate(() => Array.from(document.getElementById('reviewer').options)
    .find(option => option.text === 'Assigned: Blair').value);
  await select('reviewer', blair);
  assert.equal((await shown()).records.length, 2);
  await select('status', 'in_progress');
  await search('literal only');
  state = await shown();
  assert.equal(state.records.length, 1);
  assert.equal(state.records[0].state, 'absent');
  assert.match(state.records[0].text, /SYN-C/);
  assert.match(state.records[0].text, /<b>literal only<\/b>/);
  assert.equal(await evaluate(() => document.querySelectorAll('.annotation b, img, svg, iframe').length), 0);
  receipt.groups.push({ name: 'historical annotation remains literal and correctly paired', recordState: 'absent' });
  receipt.narrow = await noOverflow(390);
  await screenshot('narrow-filtered.png');

  await noOverflow(1280);
  await evaluate(() => { window.__beforePrint = 0; window.addEventListener('beforeprint', () => { window.__beforePrint += 1; }); });
  await click('print');
  await until(() => evaluate(() => window.__beforePrint > 0), 'real print button did not invoke browser printing');
  await command('Emulation.setEmulatedMedia', { media: 'print' });
  state = await shown();
  assert.equal(state.records.length, 1);
  assert.equal(state.records[0].state, 'absent');
  assert.equal(await evaluate(() => getComputedStyle(document.getElementById('controls')).display), 'none');
  assert.match(state.showing, /Historical records.*In progress.*Assigned: Blair.*Search: literal only/);
  await screenshot('print-media.png');
  const printed = await command('Page.printToPDF', { printBackground: true, displayHeaderFooter: false,
    paperWidth: 8.5, paperHeight: 11, marginTop: 0.4, marginBottom: 0.4, marginLeft: 0.4, marginRight: 0.4 });
  const pdf = Buffer.from(printed.data, 'base64');
  assert.ok(pdf.length > 1000 && pdf.subarray(0, 5).toString() === '%PDF-', 'Chrome produced a real PDF');
  save('filtered-review.pdf', pdf);
  receipt.groups.push({ name: 'real print button, selected print media and Page.printToPDF', pdfBytes: pdf.length });

  await command('Emulation.setEmulatedMedia', { media: 'screen' });
  await command('Emulation.setScriptExecutionDisabled', { value: true });
  await command('Page.reload');
  await until(() => evaluate(() => document.readyState === 'complete' && document.querySelectorAll('article').length === 4),
    'no-JavaScript report did not load');
  state = await shown();
  assert.equal(state.records.length, 4);
  assert.deepEqual(state.records.map(record => record.state), ['current', 'current', 'changed', 'absent']);
  assert.equal(await evaluate(() => document.getElementById('controls').hidden), true);
  receipt.noScriptNarrow = await noOverflow(390);
  await screenshot('narrow-no-javascript.png');
  receipt.groups.push({ name: 'real JavaScript-disabled view retains all current and historical records', records: 4 });

  assert.deepEqual(pageErrors, [], 'no browser JavaScript exceptions');
  assert.deepEqual(externalRequests, [], 'standalone report makes no external requests');
  assert.equal(sha(fs.readFileSync(receipt.fixture.worksheet)), receipt.fixture.worksheet_sha256);
  assert.equal(sha(fs.readFileSync(path.join(out, 'review.html'))), receipt.fixture.report_sha256);
  const after = sourceHashes();
  assert.deepEqual(after, before, 'every tracked source byte is unchanged');
  assert.equal(git(['status', '--porcelain=v1']), '', 'checkout stays clean');
  save('source-after.json', JSON.stringify(after, null, 2) + '\n');
  receipt.groups.push({ name: 'source, worksheet, report and no-network preservation', trackedFiles: Object.keys(after).length });
  receipt.accepted = true;
}

main().catch(error => {
  receipt.error = { name: error.name, message: error.message, stack: error.stack };
  process.exitCode = 1;
}).finally(async () => {
  for (const request of pending.values()) { clearTimeout(request.timer); request.reject(new Error('browser closing')); }
  pending.clear();
  if (socket) socket.close();
  if (chrome) {
    chrome.kill('SIGTERM');
    await new Promise(resolve => {
      if (chrome.exitCode !== null) return resolve();
      const timer = setTimeout(() => { chrome.kill('SIGKILL'); resolve(); }, 2000);
      chrome.once('exit', () => { clearTimeout(timer); resolve(); });
    });
  }
  if (profile) fs.rmSync(profile, { recursive: true, force: true });
  save('chrome-stderr.log', chromeLog);
  receipt.pageErrors = pageErrors;
  receipt.externalRequests = externalRequests;
  receipt.protocolCommands = serial;
  fs.writeFileSync(path.join(out, 'receiving.json'), JSON.stringify(receipt, null, 2) + '\n', { flag: 'wx' });
  process.stdout.write(JSON.stringify(receipt, null, 2) + '\n');
});
