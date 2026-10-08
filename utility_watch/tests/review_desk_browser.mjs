// Optional actual Chromium consumer. Node 22+, stdlib only; no installed profile.
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import {spawn, spawnSync} from "node:child_process";
import {fileURLToPath} from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const packageRoot = path.dirname(here);
const python = process.env.PYTHON || "python3";
const profileRoot = process.env.REVIEW_DESK_PROFILE_ROOT || os.tmpdir();
const root = fs.mkdtempSync(path.join(profileRoot, "utility-review-desk-browser-"));
const profile = path.join(root, "profile");
const downloads = path.join(root, "downloads");
fs.mkdirSync(profile);
fs.mkdirSync(downloads);
const browserBin = process.env.BROWSER_BIN ||
  ["/snap/bin/chromium", "/usr/bin/chromium", "/usr/bin/google-chrome",
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"].find(fs.existsSync);
const checks = [];
const children = [];
const servers = [];
const requests = [];
const exceptions = [];
const downloadEvents = [];
const networkResponses = [];
let chrome, cdp, session, chromeStderr = "", failure = null;
const nativeEnv = {...process.env, PYTHONDONTWRITEBYTECODE: "1"};
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const hash = (raw) => crypto.createHash("sha256").update(raw).digest("hex");

function run(args) {
  const result = spawnSync(python, ["-B", ...args], {
    cwd: packageRoot, env: nativeEnv, encoding: "utf8", timeout: 30000, maxBuffer: 8 * 1024 * 1024,
  });
  children.push({args, status: result.status, signal: result.signal,
    error: result.error?.message, stdout: result.stdout, stderr: result.stderr});
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  return result.stdout;
}
function csvRows(filename) {
  return JSON.parse(run(["-c",
    "import csv,io,json,sys\nfrom pathlib import Path\nfrom uwatch import review\nraw=Path(sys.argv[1]).read_bytes()\nreview._previous(raw)\nprint(json.dumps(list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''))),ensure_ascii=True))",
    filename]));
}
function sourceHashes() {
  const names = spawnSync("git", ["ls-files", "-z", "--cached", "--others", "--exclude-standard"],
    {cwd: path.dirname(packageRoot), encoding: "utf8"});
  assert.equal(names.status, 0);
  return Object.fromEntries(names.stdout.split("\0").filter(Boolean).map(name =>
    [name, hash(fs.readFileSync(path.join(path.dirname(packageRoot), name)))]));
}
function fileHashes(directory) {
  const result = {};
  function visit(base) {
    for (const item of fs.readdirSync(base, {withFileTypes: true})) {
      const full = path.join(base, item.name);
      if (item.isDirectory()) visit(full);
      else if (item.isFile()) result[path.relative(directory, full)] = hash(fs.readFileSync(full));
    }
  }
  visit(directory);
  return result;
}
async function waitFor(fn, label, milliseconds = 15000) {
  const deadline = Date.now() + milliseconds;
  while (Date.now() < deadline) {
    if (await fn()) return;
    await sleep(40);
  }
  throw new Error("Timed out: " + label);
}
async function startDesk(filename, data, report) {
  const child = spawn(python, ["-B", "-m", "uwatch", "review-desk", "--worksheet", filename, "--port", "0",
    ...(data ? ["--data", data, "--report", report] : [])],
    {cwd: packageRoot, env: nativeEnv, stdio: ["ignore", "pipe", "pipe"]});
  const record = {child, filename, stdout: "", stderr: "", error: null};
  child.stdout.on("data", data => { record.stdout += data; });
  child.stderr.on("data", data => { record.stderr += data; });
  child.on("error", error => { record.error = error.message; });
  servers.push(record);
  await waitFor(() => {
    if (record.error || child.exitCode !== null) throw new Error(record.error || record.stderr || "desk exited");
    return /http:\/\/127\.0\.0\.1:\d+/.test(record.stdout);
  }, "native CLI desk startup");
  record.origin = record.stdout.match(/http:\/\/127\.0\.0\.1:\d+/)[0];
  return record.origin;
}
async function connect(url) {
  const ws = new WebSocket(url);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, {once: true});
    ws.addEventListener("error", reject, {once: true});
  });
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", event => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const {resolve, reject, timer} = pending.get(message.id);
      pending.delete(message.id);
      clearTimeout(timer);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolve(message.result);
    } else {
      if (message.method === "Runtime.exceptionThrown") exceptions.push(message.params);
      if (message.method === "Network.requestWillBeSent") requests.push(message.params.request.url);
      if (message.method === "Network.responseReceived") networkResponses.push({
        url: message.params.response.url, status: message.params.response.status,
      });
      if (message.method?.startsWith("Browser.download")) downloadEvents.push({
        method: message.method, ...message.params,
      });
    }
  });
  return {
    call(method, params = {}, sessionId) {
      return new Promise((resolve, reject) => {
        const next = ++id;
        const timer = setTimeout(() => {
          pending.delete(next);
          reject(new Error("CDP timeout: " + method));
        }, 15000);
        pending.set(next, {resolve, reject, timer});
        ws.send(JSON.stringify({id: next, method, params, ...(sessionId ? {sessionId} : {})}));
      });
    },
    close() { ws.close(); },
  };
}
async function evaluate(fn, ...args) {
  const expression = "(" + fn.toString() + ")(" + args.map(arg => JSON.stringify(arg)).join(",") + ")";
  const result = await cdp.call("Runtime.evaluate", {expression, returnByValue: true, awaitPromise: true}, session);
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function page(origin) {
  const {targetId} = await cdp.call("Target.createTarget", {url: "about:blank"});
  ({sessionId: session} = await cdp.call("Target.attachToTarget", {targetId, flatten: true}));
  for (const method of ["Page.enable", "Runtime.enable", "Network.enable"]) await cdp.call(method, {}, session);
  await cdp.call("Emulation.setDeviceMetricsOverride",
    {width: 1280, height: 1000, deviceScaleFactor: 1, mobile: false}, session);
  await cdp.call("Page.navigate", {url: origin}, session);
  await waitFor(() => evaluate(() => {
    const node = document.getElementById("desk");
    return node && !node.hidden;
  }), "worksheet UI ready");
}
async function click(selector) {
  const box = await evaluate(sel => {
    const node = document.querySelector(sel);
    if (!node) throw new Error("Missing control " + sel);
    node.scrollIntoView({block: "center"});
    const r = node.getBoundingClientRect();
    return {x: r.x + r.width / 2, y: r.y + r.height / 2, disabled: Boolean(node.disabled)};
  }, selector);
  assert.equal(box.disabled, false, selector + " is disabled");
  await cdp.call("Input.dispatchMouseEvent", {type: "mousePressed", x: box.x, y: box.y, button: "left", clickCount: 1}, session);
  await cdp.call("Input.dispatchMouseEvent", {type: "mouseReleased", x: box.x, y: box.y, button: "left", clickCount: 1}, session);
}
async function key(name, code, virtualKey, modifiers = 0) {
  const params = {key: name, code, windowsVirtualKeyCode: virtualKey, nativeVirtualKeyCode: virtualKey, modifiers};
  await cdp.call("Input.dispatchKeyEvent", {...params, type: "keyDown"}, session);
  await cdp.call("Input.dispatchKeyEvent", {...params, type: "keyUp"}, session);
}
async function fill(selector, text) {
  await click(selector);
  await key("a", "KeyA", 65, process.platform === "darwin" ? 4 : 2);
  await key("Backspace", "Backspace", 8);
  if (text) await cdp.call("Input.insertText", {text}, session);
}
async function selectOption(selector, index) {
  await evaluate(sel => document.querySelector(sel).focus(), selector);
  await key("Home", "Home", 36);
  for (let i = 0; i < index; i++) await key("ArrowDown", "ArrowDown", 40);
  await key("Tab", "Tab", 9);
}
async function screenshot(name) {
  const metrics = await cdp.call("Page.getLayoutMetrics", {}, session);
  const size = metrics.cssContentSize;
  const result = await cdp.call("Page.captureScreenshot", {
    format: "png", captureBeyondViewport: true,
    clip: {x: 0, y: 0, width: size.width, height: size.height, scale: 1},
  }, session);
  fs.writeFileSync(path.join(root, name), Buffer.from(result.data, "base64"));
}
async function download(name) {
  const before = downloadEvents.length;
  await click("#download");
  await waitFor(() => downloadEvents.slice(before).some(event =>
    event.method === "Browser.downloadProgress" && event.state === "completed"), "actual browser CSV download");
  const native = path.join(downloads, "utility-review-edited.csv");
  await waitFor(() => fs.existsSync(native), "downloaded file exists");
  const destination = path.join(downloads, name);
  fs.renameSync(native, destination);
  return {path: destination, rows: csvRows(destination), sha256: hash(fs.readFileSync(destination))};
}
function mark(name, detail = {}) {
  checks.push({name, ...detail});
  console.log(JSON.stringify({passed: name}));
}
function expectRows(actual, original, edits) {
  assert.deepEqual(actual, original.map(row => ({...row, ...(edits[row.row_id] || {})})));
}

const originalSource = sourceHashes();
let fixture, inputPins, sourceAfter, version;
try {
  assert.ok(browserBin, "Set BROWSER_BIN to an installed Chromium executable.");
  fixture = JSON.parse(run([path.join(here, "review_desk_fixture.py"), path.join(root, "fixture")]));
  inputPins = fileHashes(path.join(root, "fixture"));
  const originalBytes = fs.readFileSync(fixture.worksheet);
  const origin = await startDesk(fixture.worksheet);
  chrome = spawn(browserBin, [
    "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
    "--disable-background-networking", "--disable-component-update", "--disable-sync",
    "--disable-extensions", "--password-store=basic", "--remote-debugging-address=127.0.0.1",
    "--remote-debugging-port=0", "--user-data-dir=" + profile, "about:blank",
  ], {stdio: ["ignore", "ignore", "pipe"]});
  chrome.stderr.on("data", data => { chromeStderr += data; });
  let chromeError = null;
  chrome.on("error", error => { chromeError = error; });
  const portFile = path.join(profile, "DevToolsActivePort");
  await waitFor(() => {
    if (chromeError || chrome.exitCode !== null) throw chromeError || new Error(chromeStderr);
    return fs.existsSync(portFile);
  }, "exclusive Chromium startup", 25000);
  const [port, websocketPath] = fs.readFileSync(portFile, "utf8").trim().split("\n");
  cdp = await connect("ws://127.0.0.1:" + port + websocketPath);
  version = await cdp.call("Browser.getVersion");
  await cdp.call("Browser.setDownloadBehavior", {behavior: "allow", downloadPath: downloads, eventsEnabled: true});
  await page(origin);
  const nativeRows = fixture.rows;
  const currentRows = nativeRows.filter(row => row.row_state === "current");
  const historyRows = nativeRows.filter(row => ["changed", "absent"].includes(row.row_state));
  assert.ok(currentRows.length >= 3);
  assert.ok(historyRows.some(row => row.row_state === "changed"));
  assert.ok(historyRows.some(row => row.row_state === "absent"));
  assert.equal(await evaluate(() => document.querySelectorAll(".finding").length), currentRows.length);
  assert.equal(await evaluate(() => document.querySelectorAll(".history-row").length), historyRows.length);
  assert.match(await evaluate(() => document.getElementById("source").textContent), /Synthetic data/);
  await screenshot("desktop-initial.png");
  mark("actual native CLI opens the complete current and historical worksheet", {
    current: currentRows.length, historical: historyRows.length,
  });

  const a = currentRows.find(row => row.account_no === "A");
  const d = currentRows.find(row => row.account_no === "D");
  assert.equal(a.finding_key, d.finding_key);
  const rowSelector = row => '.finding[data-row-id="' + row.row_id + '"]';
  const reviewer = "Léa 李";
  const note = 'Literal <img src="https://never.invalid/image">, "quoted"\nSecond line =SUM(1,2) 🌿';
  await click(rowSelector(a));
  await fill("#reviewer", reviewer);
  await fill("#note", note);
  await selectOption("#review-status", 1);
  assert.equal(await evaluate(() => document.getElementById("review-status").value), "in_progress");
  await selectOption("#status-filter", 3);
  assert.equal(await evaluate(() => document.getElementById("status-filter").value), "reviewed");
  assert.equal(await evaluate(() => document.getElementById("selected-outside").hidden), false);
  assert.equal(await evaluate(() => document.getElementById("note").value), note);
  assert.equal(await evaluate(() => document.querySelectorAll("img").length), 0);
  mark("native input retains the selected row outside a changed filter and renders notes literally");

  await click(rowSelector(d));
  const secondNote = "Different account, same bill key. Preserve its own reviewer.";
  await fill("#note", secondNote);
  const edits = {
    [a.row_id]: {review_status: "in_progress", reviewer, note},
    [d.row_id]: {review_status: d.review_status, reviewer: d.reviewer, note: secondNote},
  };
  const first = await download("01-filtered-edits.csv");
  expectRows(first.rows, nativeRows, edits);
  assert.deepEqual(fileHashes(path.join(root, "fixture")), inputPins);
  mark("filtered browser download contains both accounts, every protected cell, history and manifest", {
    download: path.relative(root, first.path), sha256: first.sha256,
  });

  const reconciled = path.join(root, "reconciled.csv");
  run(["-m", "uwatch", "review", "--data", fixture.data, "--report", fixture.report,
    "--previous", first.path, "--out", reconciled]);
  expectRows(csvRows(reconciled), nativeRows, edits);
  assert.deepEqual(fileHashes(path.join(root, "fixture")), inputPins);
  mark("actual existing review CLI consumes the browser download and retains exact source-bound annotations");

  await fill("#reviewer", "");
  const requestCount = requests.filter(url => url.endsWith("/api/download")).length;
  const downloadCount = downloadEvents.filter(event => event.method === "Browser.downloadWillBegin").length;
  await click("#download");
  assert.equal(await evaluate(() => document.getElementById("validation").hidden), false);
  assert.equal(await evaluate(() => document.getElementById("note").value), secondNote);
  assert.equal(requests.filter(url => url.endsWith("/api/download")).length, requestCount);
  assert.equal(downloadEvents.filter(event => event.method === "Browser.downloadWillBegin").length, downloadCount);
  await fill("#reviewer", "Fixed reviewer");
  edits[d.row_id].reviewer = "Fixed reviewer";
  const second = await download("02-corrected-review.csv");
  expectRows(second.rows, nativeRows, edits);
  mark("incomplete human review is retained for correction and a corrected native download succeeds");

  const staleNote = "Retain this note after an actual on-disk source change.";
  await fill("#note", staleNote);
  edits[d.row_id].note = staleNote;
  fs.writeFileSync(fixture.worksheet, Buffer.concat([originalBytes, Buffer.from("\n")]));
  const beforeStale = downloadEvents.filter(event => event.method === "Browser.downloadWillBegin").length;
  await click("#download");
  await waitFor(() => evaluate(() => !document.getElementById("download-error").hidden), "stale worksheet refusal");
  assert.match(await evaluate(() => document.getElementById("download-error").textContent), /changed on disk/);
  assert.equal(await evaluate(() => document.getElementById("note").value), staleNote);
  assert.equal(await evaluate(() => document.getElementById("reviewer").value), "Fixed reviewer");
  assert.equal(downloadEvents.filter(event => event.method === "Browser.downloadWillBegin").length, beforeStale);
  assert.ok(networkResponses.some(response => response.url.endsWith("/api/download") && response.status === 409));
  fs.writeFileSync(fixture.worksheet, originalBytes);
  const third = await download("03-source-restored.csv");
  expectRows(third.rows, nativeRows, edits);
  assert.deepEqual(fileHashes(path.join(root, "fixture")), inputPins);
  mark("real source drift refuses the download without losing edits; exact-source retry succeeds");

  await fill("#search", "no matching fictional account");
  assert.equal(await evaluate(() => document.querySelectorAll(".finding").length), 0);
  assert.equal(await evaluate(() => document.getElementById("note").value), staleNote);
  await click("#clear-filters");
  assert.equal(await evaluate(() => document.querySelectorAll(".finding").length), currentRows.length);
  await click(rowSelector(a));
  assert.equal(await evaluate(() => document.getElementById("reviewer").value), reviewer);
  await click("#reset-row");
  assert.equal(await evaluate(() => document.getElementById("reviewer").value), a.reviewer);
  assert.equal(await evaluate(() => document.getElementById("note").value), a.note);
  assert.equal(await evaluate(() => document.getElementById("review-status").value), a.review_status.trim());
  await cdp.call("Emulation.setDeviceMetricsOverride",
    {width: 320, height: 900, deviceScaleFactor: 1, mobile: false}, session);
  assert.ok(await evaluate(() => document.documentElement.scrollWidth <= 321));
  await screenshot("narrow-current-editor.png");
  mark("no-match recovery, row-local reset and a 320-pixel native viewport preserve the editor");

  const emptyFile = path.join(root, "empty-current.csv");
  run(["-c",
    "import csv,sys\nfrom pathlib import Path\nfrom uwatch import review\nwith Path(sys.argv[1]).open(newline='',encoding='utf-8') as f:\n rows=list(csv.DictReader(f))\nmanifest=next(r for r in rows if r['row_state']=='manifest')\nwith Path(sys.argv[2]).open('w',newline='',encoding='utf-8') as f:\n w=csv.DictWriter(f,fieldnames=review.COLUMNS);w.writeheader();w.writerow(review._manifest([],manifest))",
    fixture.worksheet, emptyFile]);
  const emptyOrigin = await startDesk(emptyFile);
  await page(emptyOrigin);
  assert.equal(await evaluate(() => document.querySelectorAll(".finding").length), 0);
  assert.equal(await evaluate(() => document.getElementById("selected").hidden), true);
  const empty = await download("04-empty-current.csv");
  expectRows(empty.rows, csvRows(emptyFile), {});
  mark("a native-valid empty worksheet opens and downloads its unchanged manifest");


  // Optional source inspection uses the real CLI, unchanged native evidence
  // producer and genuine downloaded bytes. These records are all fictional.
  const sourceFixture = JSON.parse(run([path.join(here, "review_evidence_fixture.py"), path.join(root, "source-fixture")]));
  const sourceInputPins = fileHashes(path.join(root, "source-fixture"));
  const sourceOrigin = await startDesk(sourceFixture.worksheet, sourceFixture.data, sourceFixture.report);
  await page(sourceOrigin);
  const sourceRows = Object.fromEntries(["A", "D"].map(account => [account,
    sourceFixture.rows.find(row => row.row_state === "current" && row.account_no === account)]));
  const expectedEvidence = Object.fromEntries(["A", "D"].map(account =>
    [account, JSON.parse(fs.readFileSync(sourceFixture.evidence[account], "utf8"))]));
  async function chooseSource(account) {
    await click('[data-row-id="' + sourceRows[account].row_id + '"]');
  }
  async function checkedSource(account) {
    await click("#inspect-evidence");
    await waitFor(() => evaluate(() => !document.getElementById("source-record-result").hidden),
      "actual native source records for " + account);
    const visible = await evaluate(() => ({
      summary: document.getElementById("source-record-summary").textContent,
      fields: [...document.querySelectorAll(".source-record")].map(record => ({
        pointer: record.dataset.pointer,
        entries: [...record.querySelectorAll("dt")].map(dt => [dt.textContent, dt.nextElementSibling.textContent]),
      })),
      executed: window.utilityExecuted ?? null,
    }));
    assert.ok(visible.summary.includes(" · " + account + " · SHARED · "));
    assert.deepEqual(visible.fields, expectedEvidence[account].records.map(record => ({
      pointer: record.pointer, entries: record.columns.map(column => [column, record.fields[column]]),
    })));
    assert.equal(visible.executed, null);
    return visible;
  }
  async function evidenceDownload(account, name) {
    const before = downloadEvents.length;
    await click("#download-evidence");
    await waitFor(() => downloadEvents.slice(before).some(event =>
      event.method === "Browser.downloadProgress" && event.state === "completed"), "actual native JSON download");
    const filename = path.join(downloads, "utility-source-evidence.json");
    await waitFor(() => fs.existsSync(filename), "evidence download exists");
    const destination = path.join(downloads, name);
    fs.renameSync(filename, destination);
    const raw = fs.readFileSync(destination);
    assert.deepEqual(raw, fs.readFileSync(sourceFixture.evidence[account]));
    return {account, path: destination, bytes: raw.length, sha256: hash(raw)};
  }
  await chooseSource("A");
  await fill("#reviewer", "Source receiver Zoë");
  await fill("#note", "Keep this draft while inspecting.\n=literal");
  await fill("#search", "Keep this draft");
  const draftBefore = await evaluate(() => ({
    row: document.querySelector('.finding[aria-pressed="true"]').dataset.rowId,
    reviewer: document.getElementById("reviewer").value, note: document.getElementById("note").value,
    search: document.getElementById("search").value,
    status: document.getElementById("review-status").value,
    changes: document.getElementById("change-count").textContent,
  }));
  const requestsBefore = requests.length;
  const renderedA = await checkedSource("A");
  assert.ok(renderedA.fields.some(record => record.entries.some(([key, value]) => key === "memo" && value === sourceFixture.memo)));
  const draftAfter = await evaluate(() => ({
    row: document.querySelector('.finding[aria-pressed="true"]').dataset.rowId,
    reviewer: document.getElementById("reviewer").value, note: document.getElementById("note").value,
    search: document.getElementById("search").value,
    status: document.getElementById("review-status").value,
    changes: document.getElementById("change-count").textContent,
  }));
  assert.deepEqual(draftAfter, draftBefore);
  assert.deepEqual(requests.slice(requestsBefore).filter(url => url.includes("/api/")).map(url => new URL(url).pathname),
    ["/api/evidence"]);
  const downloadedA = await evidenceDownload("A", "05-source-A.json");
  await screenshot("source-records-desktop.png");
  mark("literal multiline source fields match the native producer and same-byte JSON download; notes and filters remain", downloadedA);

  await click("#clear-filters");
  await chooseSource("D");
  assert.equal(await evaluate(() => document.getElementById("source-record-result").hidden), true);
  assert.equal(await evaluate(() => document.getElementById("download-evidence").disabled), true);
  await checkedSource("D");
  const downloadedD = await evidenceDownload("D", "06-source-D.json");
  assert.notEqual(downloadedD.sha256, downloadedA.sha256);
  mark("identical bill keys on two accounts keep separate record identity and discard the previous download", downloadedD);

  // Delay delivery of one real completed native response, not its contents.
  await evaluate(rowId => {
    const nativeFetch = window.fetch.bind(window);
    window.fetch = async (input, options) => {
      const response = await nativeFetch(input, options);
      if (input === "/api/evidence" && JSON.parse(options.body).row_id === rowId && !window.evidenceDelayDone) {
        window.evidenceDelayDone = true;
        window.evidenceArrived = true;
        await new Promise(resolve => { window.releaseEvidence = resolve; });
        window.evidenceReleased = true;
      }
      return response;
    };
  }, sourceRows.A.row_id);
  await chooseSource("A");
  await click("#inspect-evidence");
  await waitFor(() => evaluate(() => window.evidenceArrived === true), "real A response held at the browser transport");
  await chooseSource("D");
  await fill("#note", "D stays selected while A finishes.");
  await checkedSource("D");
  const currentSummary = await evaluate(() => document.getElementById("source-record-summary").textContent);
  await evaluate(() => window.releaseEvidence());
  await waitFor(() => evaluate(() => window.evidenceReleased === true), "older response released");
  assert.equal(await evaluate(() => document.getElementById("source-record-summary").textContent), currentSummary);
  assert.equal(await evaluate(() => document.getElementById("note").value), "D stays selected while A finishes.");
  assert.equal(await evaluate(() => document.getElementById("download-evidence").disabled), false);
  mark("a late response for the former selection cannot replace the current account's records or draft");

  const billsPath = path.join(sourceFixture.data, "bills.csv");
  const billsBefore = fs.readFileSync(billsPath);
  run(["-c", "import csv,sys\nfrom pathlib import Path\np=Path(sys.argv[1])\nwith p.open(newline='',encoding='utf-8') as f:\n r=csv.DictReader(f);cols=r.fieldnames;rows=list(r)\nfor row in rows:\n if row['account_no']=='D': row['memo']+=' changed source context'\nwith p.open('w',newline='',encoding='utf-8') as f:\n w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)", billsPath]);
  try {
    await click("#inspect-evidence");
    await waitFor(() => evaluate(() => !document.getElementById("source-record-error").hidden), "changed source context refusal");
    assert.match(await evaluate(() => document.getElementById("source-record-error").textContent), /do not match this saved finding/);
    assert.equal(await evaluate(() => document.getElementById("source-record-result").hidden), true);
    assert.equal(await evaluate(() => document.getElementById("download-evidence").disabled), true);
    assert.equal(await evaluate(() => document.getElementById("note").value), "D stays selected while A finishes.");
  } finally {
    fs.writeFileSync(billsPath, billsBefore);
  }
  await checkedSource("D");
  assert.deepEqual(fileHashes(path.join(root, "source-fixture")), sourceInputPins);
  mark("a native-valid changed source context refuses without losing draft notes; the exact restored source can be rechecked");

  await cdp.call("Emulation.setDeviceMetricsOverride",
    {width: 320, height: 1000, deviceScaleFactor: 1, mobile: false}, session);
  assert.ok(await evaluate(() => document.documentElement.scrollWidth <= 321));
  await screenshot("source-records-narrow.png");
  mark("source record values remain readable in the existing 320-pixel desk without horizontal overflow");

  assert.deepEqual(exceptions, []);
  const allowed = new Set(servers.map(record => record.origin));
  assert.deepEqual(requests.filter(url => !url.startsWith("blob:") && !url.startsWith("about:") &&
    !allowed.has(new URL(url).origin)), []);
  sourceAfter = sourceHashes();
  assert.deepEqual(sourceAfter, originalSource);
  mark("no external page requests or JavaScript exceptions; every source byte remains frozen");
} catch (error) {
  failure = {message: error.message, stack: error.stack};
  process.exitCode = 1;
} finally {
  if (cdp) {
    try { await cdp.call("Browser.close"); } catch {}
    cdp.close();
  }
  if (chrome && chrome.exitCode === null) {
    try { await waitFor(() => chrome.exitCode !== null || chrome.signalCode !== null, "browser exit", 4000); }
    catch { chrome.kill("SIGTERM"); }
  }
  for (const record of servers) {
    if (record.child.exitCode === null && record.child.signalCode === null) record.child.kill("SIGINT");
    try { await waitFor(() => record.child.exitCode !== null || record.child.signalCode !== null, "desk exit", 5000); }
    catch { record.child.kill("SIGKILL"); }
  }
  let profileCleanup = false;
  try {
    fs.rmSync(profile, {recursive: true, force: true});
    profileCleanup = !fs.existsSync(profile);
  } catch {}
  fs.writeFileSync(path.join(root, "browser-stderr.log"), chromeStderr);
  fs.writeFileSync(path.join(root, "native-children.json"), JSON.stringify(children, null, 2));
  const receipt = {
    root, node: process.version, platform: process.platform, browserBin, browser: version,
    checks, failure, profileCleanup, requests, networkResponses, exceptions, downloadEvents,
    inputPins, sourceBefore: originalSource, sourceAfter,
    servers: servers.map(record => ({
      filename: record.filename, origin: record.origin, stdout: record.stdout, stderr: record.stderr,
      status: record.child.exitCode, signal: record.child.signalCode, error: record.error,
    })),
  };
  fs.writeFileSync(path.join(root, "browser-receipt.json"), JSON.stringify(receipt, null, 2));
  console.log(JSON.stringify({root, passed: checks.length, failure, profileCleanup}));
}
