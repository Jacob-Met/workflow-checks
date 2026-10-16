import fs from "node:fs";
import path from "node:path";
import http from "node:http";
import crypto from "node:crypto";
import assert from "node:assert/strict";
import { pathToFileURL, fileURLToPath } from "node:url";

const configPath = path.resolve(process.argv[2]);
const configBytes = fs.readFileSync(configPath);
const config = JSON.parse(configBytes.toString("utf8"));
assert.equal(config.authorizedCandidateFreeze, true, "Candidate freeze and runtime authorization required");
assert.ok(path.isAbsolute(config.runRoot) && path.resolve(config.runRoot) === config.runRoot, "Output must be an absolute normalized path");
assert.notEqual(config.runRoot, path.parse(config.runRoot).root, "Output cannot be a filesystem root");
assert.ok(!fs.existsSync(config.runRoot), "Never reuse a browser profile or run directory");
fs.mkdirSync(config.runRoot, { recursive: true });
const output = config.runRoot;
const inputDir = path.join(output, "inputs");
fs.mkdirSync(inputDir);
const hash = b => crypto.createHash("sha256").update(b).digest("hex");
const clone = x => JSON.parse(JSON.stringify(x));
const FIELDS = ["appointment", "arrival", "departure", "free_minutes", "increment_minutes", "late_grace_minutes", "detention_rate_cents", "detention_cap_cents", "linehaul_cents", "fuel_cents", "detention_cents", "lumper_cents", "tonu_cents", "invoice_total_cents", "pod_received", "ratecon_complete"];
const report = { format: "estate-freight-browser-receiving/1", started: new Date().toISOString(), config, groups: [], downloads: [], captures: [], pageErrors: [], externalRequests: [], consoleErrors: [], storageWrites: [], delivery: [], completed: false };
let browser, server, page, cdp, origin, originalDownload, latestDownload;
const sourceRows = config.sourcePins.map(pin => {
  const b = fs.readFileSync(pin.path);
  assert.equal(hash(b), pin.sha256, "Preflight source: " + pin.path);
  return { ...pin, bytes: b.length };
});
const selfPath = fileURLToPath(import.meta.url);
const selfHash = hash(fs.readFileSync(selfPath));
const configHash = hash(configBytes);
function save(name, value) { fs.writeFileSync(path.join(output, name), JSON.stringify(value, null, 2) + "\n"); }
function copyFixture(name) {
  const pin = config.fixturePins.find(x => x.name === name);
  assert.ok(pin, "Missing frozen fixture " + name);
  const b = fs.readFileSync(pin.path); assert.equal(hash(b), pin.sha256);
  const dst = path.join(inputDir, name); fs.writeFileSync(dst, b);
  return dst;
}
const fixture = Object.fromEntries(config.fixturePins.map(x => [x.name, copyFixture(x.name)]));
const readRecord = name => JSON.parse(fs.readFileSync(fixture[name], "utf8"));
const preparedOversize = path.join(inputDir, "oversized.json");
fs.writeFileSync(preparedOversize, " ".repeat(1048577));
const literalPath = path.join(inputDir, "<b> invoice & café .json");
fs.copyFileSync(fixture["accept-literal-filename.json"], literalPath);
const downloadEvents = [];
let intentionalDownloads = 0;
const elapsed = () => new Promise(resolve => setTimeout(resolve, 50));
async function group(id, fn) {
  const start = Date.now(), row = { id, started: new Date().toISOString() };
  report.groups.push(row);
  try { row.evidence = await fn(); row.pass = true; }
  catch (error) { row.pass = false; row.error = { name: error.name, message: error.message, stack: error.stack }; }
  row.durationMs = Date.now() - start;
  save("browser-receipt.partial.json", report);
  console.log(JSON.stringify(row));
}
async function activate(selector, keyboard = false) {
  if (keyboard) { await page.focus(selector); await page.keyboard.press("Enter"); }
  else await page.click(selector);
}
async function edit(id, value) {
  await page.evaluate(id => { const d = document.getElementById(id).closest("details"); if (d) d.open = true; }, id);
  await page.focus("#" + id);
  await page.keyboard.down("Control"); await page.keyboard.press("A"); await page.keyboard.up("Control");
  await page.keyboard.press("Backspace");
  if (value) await page.keyboard.type(value);
  assert.equal(await page.$eval("#" + id, n => n.value), value, "Keyboard delivered exact raw value");
}
async function raw(id, value) { await page.$eval("#" + id, (n, v) => { n.value = v; }, value); }
async function snapshot() {
  return page.evaluate(fields => {
    const q = id => document.getElementById(id);
    return {
      fields: Object.fromEntries(fields.map(f => [f, q(f).type === "checkbox" ? q(f).checked : q(f).value])),
      presets: [...document.querySelectorAll("[data-preset]")].map(n => [n.dataset.preset, n.getAttribute("aria-pressed")]),
      baseline: q("baseline-label").textContent,
      baselineSummary: q("baseline-summary").textContent,
      resultText: q("result-content").textContent,
      resultHidden: q("result-content").hidden,
      invalidText: q("invalid-state").textContent,
      invalidHidden: q("invalid-state").hidden,
      downloadDisabled: q("download").disabled,
    };
  }, FIELDS);
}
function fieldsOf(s) {
  return Object.fromEntries(FIELDS.map(f => [f, typeof s[f] === "boolean" ? s[f] : s[f] === null ? "" : f.endsWith("_cents") ? (s[f] / 100).toFixed(2) : String(s[f])]));
}
async function expectState(before) { assert.deepEqual(await snapshot(), before, "Entire scenario state remains unchanged"); }
async function refusal() {
  await page.waitForFunction(() => /cannot|could not|refus|invalid|large|limit|incompatible|not opened/i.test(document.getElementById("record-status").textContent), { timeout: 5000 });
}
async function visiblePreview() { return page.$eval("#record-preview", n => !n.hidden && n.getClientRects().length > 0); }
async function noPreview() {
  assert.equal(await visiblePreview(), false);
  const usable = await page.$eval("#replace-record", n => !n.disabled && !n.hidden && n.getClientRects().length > 0);
  assert.equal(usable, false, "No actionable stale Replace");
}
async function flush() { await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))); }
async function candidate() {
  await page.goto(origin + "/candidate/index.html", { waitUntil: "networkidle0", timeout: 15000 });
  await page.waitForSelector("#open-record", { visible: true });
  await page.waitForFunction(() => document.querySelector('[data-preset="long-dwell"]')?.getAttribute("aria-pressed") === "true");
  assert.equal(await page.$eval("#record-status", n => n.getAttribute("role")), "status");
}
async function choose(file, { during, keyboard = false, cancel = false } = {}) {
  const beforeChange = await page.evaluate(() => window.__freightReceiver.changeCount);
  const waiting = page.waitForFileChooser({ timeout: 5000 });
  await activate("#open-record", keyboard);
  const chooser = await waiting;
  if (during) await during();
  if (cancel) await chooser.cancel();
  else {
    await chooser.accept([file]);
    await page.waitForFunction(previous => window.__freightReceiver.changeCount > previous, { timeout: 5000 }, beforeChange);
    await page.waitForFunction(() => window.__freightReceiver.hold || window.__freightReceiver.activeReads === 0, { timeout: 5000 });
  }
  await flush();
  report.delivery.push(await page.evaluate(({ file, cancel }) => ({ file, cancel, changeCount: window.__freightReceiver.changeCount, activeReads: window.__freightReceiver.activeReads, controlledHold: window.__freightReceiver.hold }), { file, cancel }));
}
async function preview(record) {
  await page.waitForSelector("#record-preview", { visible: true, timeout: 5000 });
  const values = await page.$$eval("#record-preview [data-record-field]", nodes => nodes.map(n => ({ field: n.dataset.recordField, canonical: n.dataset.recordValue, value: n.textContent.trim(), label: n.previousElementSibling?.textContent.trim() || "" })));
  assert.deepEqual(values.map(x => x.field).sort(), [...FIELDS].sort(), "All sixteen preview values");
  assert.ok(values.every(x => x.label), "Every preview value has a visible label");
  const nullText = { detention_cap_cents: "No cap (blank field)", invoice_total_cents: "Automatic sum (blank field)", arrival: "Missing (blank field)", departure: "Missing (blank field)" };
  for (const row of values) {
    const v = record.current.scenario[row.field];
    let rendered;
    assert.equal(row.canonical, JSON.stringify(v), "Canonical preview value " + row.field);
    if (v === null) rendered = nullText[row.field];
    else if (typeof v === "boolean") rendered = v ? "Yes" : "No";
    else if (row.field.endsWith("_cents")) rendered = "$" + (v / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    else if (row.field.endsWith("_minutes")) rendered = String(v) + " min";
    else rendered = String(v).replace("T", " ");
    assert.equal(row.value, rendered, "Preview " + row.field);
  }
  assert.equal(await page.$$eval("#record-preview input, #record-preview textarea, #record-preview select", x => x.length), 0, "Read-only preview");
  const text = await page.$eval("#record-preview", n => n.textContent);
  assert.ok(text.includes(record.loaded_preset.title), "Canonical baseline identity");
  assert.ok(text.includes(record.provenance.baseline_commit.slice(0, 12)), "Source identity");
  return { values, text };
}
async function download(label) {
  const directory = path.join(output, "downloads", label);
  fs.mkdirSync(directory, { recursive: true });
  await cdp.send("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: directory, eventsEnabled: true });
  const start = downloadEvents.length; intentionalDownloads++;
  await page.click("#download");
  const until = Date.now() + 8000;
  let begin, done;
  while (Date.now() < until) {
    begin = downloadEvents.slice(start).find(x => x.kind === "begin");
    done = begin && downloadEvents.slice(start).find(x => x.guid === begin.guid && x.state === "completed");
    if (done) break;
    await elapsed();
  }
  assert.ok(begin && done, "Actual browser download completed");
  const file = path.join(directory, begin.suggestedFilename);
  const bytes = fs.readFileSync(file);
  const row = { label, path: file, bytes: bytes.length, sha256: hash(bytes), filename: begin.suggestedFilename, guid: begin.guid };
  report.downloads.push(row);
  return { file, record: JSON.parse(bytes), ...row };
}
function withoutTimestamp(record) { const next = clone(record); delete next.exported_at; return next; }
async function holdReads() { await page.evaluate(() => { window.__freightReceiver.hold = true; }); }
async function readQueue() { return page.evaluate(() => window.__freightReceiver.queue.map(x => ({ id: x.id, name: x.name, settled: x.settled }))); }
async function queued(count) { await page.waitForFunction(n => window.__freightReceiver.queue.length >= n, { timeout: 5000 }, count); return readQueue(); }
async function settle(id, reject = false) {
  await page.evaluate(({ id, reject }) => window.__freightReceiver.settle(id, reject), { id, reject });
  await flush();
}
async function capture(name) {
  const file = path.join(output, name + ".png");
  await page.screenshot({ path: file, fullPage: true });
  const b = fs.readFileSync(file);
  const meta = { name, path: file, bytes: b.length, sha256: hash(b), viewport: page.viewport(), visuallyInspected: false };
  report.captures.push(meta); return meta;
}

const safetyTimer = setTimeout(async () => {
  report.fatal = "Receiver total bound exceeded";
  try { await browser?.close(); } catch {}
  try { server?.close(); save("browser-receipt.json", report); } catch {}
  process.exit(2);
}, config.totalTimeoutMs || 240000);

try {
  const routes = new Map();
  for (const [prefix, root] of [["baseline", config.baselineRoot], ["candidate", config.candidateRoot]]) {
    for (const pin of sourceRows.filter(x => x.route === prefix)) {
      const name = path.basename(pin.path);
      assert.ok(["index.html", "app.mjs", "model.mjs", "data.mjs", "styles.css", "scenario-record.mjs"].includes(name));
      routes.set("/" + prefix + "/" + name, { bytes: fs.readFileSync(pin.path), type: name.endsWith(".mjs") ? "text/javascript" : name.endsWith(".css") ? "text/css" : "text/html" });
    }
    assert.ok(routes.has("/" + prefix + "/index.html"));
  }
  const served = [];
  server = http.createServer((request, response) => {
    served.push({ method: request.method, url: request.url });
    const route = routes.get(request.url);
    if (!route) { response.writeHead(404); response.end("Not found"); return; }
    response.writeHead(200, { "Content-Type": route.type + "; charset=utf-8", "Cache-Control": "no-store" });
    response.end(route.bytes);
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  origin = "http://127.0.0.1:" + server.address().port;
  const puppeteer = (await import(pathToFileURL(config.puppeteerPath))).default;
  browser = await puppeteer.launch({
    executablePath: config.chromiumPath, headless: true,
    userDataDir: path.join(output, "profile"), timeout: config.launchTimeoutMs || 45000,
    dumpio: true, args: ["--no-first-run", "--no-default-browser-check"],
  });
  report.runtime = { version: await browser.version(), node: process.version, platform: process.platform, sandboxDisabled: false };
  report.deliveryBoundary = "Puppeteer intercepts the browser file chooser and supplies actual file bytes. Installed Puppeteer25 FileChooser.cancel dispatches an untrusted bubbling DOM cancel event on the file input; this exercises the application cancel listener and is not an OS-picker cancel gesture or OS-focus qualification.";
  cdp = await browser.target().createCDPSession();
  cdp.on("Browser.downloadWillBegin", e => downloadEvents.push({ kind: "begin", ...e }));
  cdp.on("Browser.downloadProgress", e => downloadEvents.push({ kind: "progress", ...e }));
  page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1 });
  page.on("pageerror", error => report.pageErrors.push(String(error)));
  page.on("console", message => { if (message.type() === "error") report.consoleErrors.push(message.text()); });
  await page.setRequestInterception(true);
  page.on("request", request => {
    const url = request.url();
    if (url.startsWith(origin + "/") || url.startsWith("blob:" + origin + "/") || url.startsWith("data:")) void request.continue();
    else { report.externalRequests.push({ url, method: request.method() }); void request.abort(); }
  });
  await page.exposeFunction("__freightRecordStorage", event => report.storageWrites.push(event));
  await page.evaluateOnNewDocument(() => {
    const original = File.prototype.text;
    const state = { hold: false, queue: [], storageWrites: [], changeCount: 0, activeReads: 0 };
    document.addEventListener("change", event => { if (event.target?.id === "record-file") state.changeCount++; }, true);
    state.settle = async (id, fail) => {
      const row = state.queue.find(x => x.id === id);
      if (!row || row.settled) throw Error("Unknown or already settled controlled read");
      row.settled = true;
      if (fail) row.reject(new Error("Independent receiver controlled read error"));
      else row.resolve(await row.bytes);
    };
    Object.defineProperty(window, "__freightReceiver", { value: state });
    File.prototype.text = function () {
      state.activeReads++;
      const bytes = original.call(this);
      const result = state.hold
        ? new Promise((resolve, reject) => state.queue.push({ id: state.queue.length + 1, name: this.name, bytes, resolve, reject, settled: false }))
        : bytes;
      return result.finally(() => { state.activeReads--; });
    };
    for (const key of ["setItem", "removeItem", "clear"]) {
      const fn = Storage.prototype[key];
      Storage.prototype[key] = function (...args) { const event = { method: key, args }; state.storageWrites.push(event); void window.__freightRecordStorage(event); return fn.apply(this, args); };
    }
  });
  await group("original-download", async () => {
    await page.goto(origin + "/baseline/index.html", { waitUntil: "networkidle0" });
    assert.equal(await page.$("#open-record"), null, "Original capability absent");
    await page.click('[data-preset="within-free"]'); await edit("fuel_cents", "300.00");
    originalDownload = await download("original-within-free-fuel300");
    const r = originalDownload.record;
    assert.equal(r.loaded_preset.id, "within-free");
    assert.equal(r.current.scenario.fuel_cents, 30000);
    assert.equal(r.current.result.totals.invoice_total_cents, 190000);
    assert.equal(r.current.result.stop.amount_cents, 0);
    assert.deepEqual((await snapshot()).fields, fieldsOf(r.current.scenario));
    return originalDownload;
  });
  await group("preview-read-only", async () => {
    assert.ok(originalDownload); await candidate(); const before = await snapshot();
    await choose(originalDownload.file); const observed = await preview(originalDownload.record);
    await expectState(before);
    return { before, observed };
  });
  await group("cancel-and-chooser-cancel", async () => {
    await candidate(); const before = await snapshot();
    await choose(originalDownload.file); await preview(originalDownload.record);
    await page.click("#cancel-record"); await noPreview(); await expectState(before);
    await choose(null, { cancel: true }); await noPreview(); await expectState(before);
    return { preserved: before };
  });
  await group("explicit-replace", async () => {
    await candidate(); await choose(originalDownload.file); await preview(originalDownload.record);
    await page.click("#replace-record"); await noPreview();
    assert.deepEqual((await snapshot()).fields, fieldsOf(originalDownload.record.current.scenario));
    assert.equal(await page.$eval('[data-preset="within-free"]', n => n.getAttribute("aria-pressed")), "true");
    assert.equal(await page.$eval("#supported-amount", n => n.textContent), "$0.00");
    assert.ok((await page.$eval("#invoice-total", n => n.textContent)).includes("$1,900.00"));
    const received = await download("received-original");
    assert.deepEqual(withoutTimestamp(received.record), withoutTimestamp(originalDownload.record));
    return received;
  });
  await group("reset-and-current-export", async () => {
    await candidate(); await choose(originalDownload.file); await preview(originalDownload.record); await page.click("#replace-record");
    await page.click("#reset");
    const canonical = readRecord("accept-preset-within-free.json");
    assert.deepEqual((await snapshot()).fields, fieldsOf(canonical.current.scenario));
    await edit("fuel_cents", "310.00"); latestDownload = await download("latest-within-free-fuel310");
    assert.equal(latestDownload.record.current.scenario.fuel_cents, 31000);
    assert.equal(latestDownload.record.current.result.totals.invoice_total_cents, 191000);
    assert.equal(latestDownload.record.current.result.stop.amount_cents, 0);
    await page.click('[data-preset="long-dwell"]');
    await choose(latestDownload.file); await preview(latestDownload.record); await page.click("#replace-record");
    assert.deepEqual((await snapshot()).fields, fieldsOf(latestDownload.record.current.scenario));
    return latestDownload;
  });
  await group("invalid-raw-draft", async () => {
    await candidate(); await edit("fuel_cents", " 12x. ");
    const before = await snapshot(); assert.equal(before.fields.fuel_cents, " 12x. "); assert.equal(before.downloadDisabled, true); assert.equal(before.invalidHidden, false);
    await choose(originalDownload.file); await preview(originalDownload.record); await expectState(before);
    await page.click("#cancel-record"); await noPreview(); await expectState(before);
    await choose(fixture["reject-truncated-json.json"]); await refusal(); await noPreview(); await expectState(before);
    assert.ok(await page.$eval("#record-status", n => n.textContent.trim()));
    return before;
  });
  await group("whole-file-refusal", async () => {
    const rows = [];
    for (const file of [fixture["reject-truncated-json.json"], fixture["reject-current-amount.json"], preparedOversize]) {
      await candidate(); const before = await snapshot(); await choose(file); await refusal(); await noPreview(); await expectState(before);
      const message = await page.$eval("#record-status", n => n.textContent.trim());
      assert.ok(message && /cannot|could not|refus|invalid|large|limit|incompatible|not opened/i.test(message), "Explicit refusal");
      rows.push({ file, message });
    }
    return rows;
  });
  await group("null-zero-false", async () => {
    const rows = [];
    for (const name of ["accept-null-cap.json", "accept-zero-header.json", "accept-missing-pod.json", "accept-incomplete-ratecon.json"]) {
      await candidate(); const record = readRecord(name); await choose(fixture[name]); await preview(record);
      await page.click("#replace-record"); const state = await snapshot();
      assert.deepEqual(state.fields, fieldsOf(record.current.scenario)); rows.push({ name, fields: state.fields });
    }
    return rows;
  });
  await group("chooser-intent", async () => {
    const rows = [];
    for (const mode of ["raw", "reset", "preset"]) {
      await candidate(); let expected;
      await choose(originalDownload.file, { during: async () => {
        if (mode === "raw") await raw("fuel_cents", "271.13");
        else if (mode === "reset") await page.$eval("#reset", n => n.click());
        else await page.$eval('[data-preset="within-free"]', n => n.click());
        expected = await snapshot();
      } });
      await noPreview(); await expectState(expected); rows.push({ mode, expected });
    }
    return rows;
  });
  await group("read-intent", async () => {
    const rows = [];
    for (const mode of ["raw", "typing", "reset", "preset"]) {
      await candidate(); await holdReads(); await choose(originalDownload.file); const queue = await queued(1);
      if (mode === "raw") await raw("fuel_cents", "271.13");
      else if (mode === "typing") await edit("fuel_cents", "271.13");
      else if (mode === "reset") await page.click("#reset");
      else await page.click('[data-preset="within-free"]');
      const expected = await snapshot(); await settle(queue[0].id); await noPreview(); await expectState(expected);
      rows.push({ mode, expected });
    }
    return rows;
  });
  await group("preview-stale", async () => {
    const rows = [];
    for (const mode of ["raw", "typing", "reset", "preset"]) {
      await candidate(); await choose(originalDownload.file); await preview(originalDownload.record);
      if (mode === "raw") { await raw("fuel_cents", "271.13"); }
      else if (mode === "typing") await edit("fuel_cents", "271.13");
      else if (mode === "reset") await page.click("#reset");
      else await page.click('[data-preset="within-free"]');
      const expected = await snapshot();
      if (mode === "raw") await page.click("#replace-record");
      await noPreview(); await expectState(expected); rows.push({ mode, expected });
    }
    return rows;
  });
  await group("latest-selection", async () => {
    const rows = [];
    for (const rejectOld of [false, true]) {
      await candidate(); const before = await snapshot(); await holdReads();
      await choose(originalDownload.file); await queued(1);
      await choose(latestDownload.file); const queue = await queued(2);
      await settle(queue[1].id); const newest = await preview(latestDownload.record); await expectState(before);
      const newestStatus = await page.$eval("#record-status", n => n.textContent);
      await settle(queue[0].id, rejectOld); await preview(latestDownload.record);
      assert.equal(await page.$eval("#record-status", n => n.textContent), newestStatus);
      await expectState(before); rows.push({ rejectOld, queue, newest });
    }
    return rows;
  });
  await group("pending-cancel-and-new-open", async () => {
    await candidate(); const before = await snapshot(); await holdReads();
    await choose(originalDownload.file); const queue = await queued(1);
    await page.click("#cancel-record"); await settle(queue[0].id); await noPreview(); await expectState(before);
    await page.evaluate(() => { window.__freightReceiver.hold = false; });
    await choose(originalDownload.file); await preview(originalDownload.record);
    const waiting = page.waitForFileChooser({ timeout: 5000 }); await page.click("#open-record");
    const chooser = await waiting; await noPreview(); await chooser.cancel(); await flush(); await noPreview(); await expectState(before);
    return { queue, preserved: before };
  });
  await group("literal-text", async () => {
    await candidate(); await choose(literalPath); await preview(readRecord("accept-literal-filename.json"));
    const seen = await page.evaluate(() => {
      const nodes = [document.getElementById("record-preview"), document.getElementById("record-status")];
      return { text: nodes.map(n => n.textContent).join("\n"), unsafe: nodes.reduce((n, p) => n + p.querySelectorAll("b,script,iframe,img").length, 0) };
    });
    assert.ok(seen.text.includes("<b> invoice & café .json"));
    assert.equal(seen.unsafe, 0);
    return seen;
  });
  await group("keyboard-desktop", async () => {
    await candidate(); await choose(originalDownload.file, { keyboard: true }); await preview(originalDownload.record);
    const before = await snapshot();
    const focusTrace = [];
    for (let i = 0; i < 40; i++) {
      const active = await page.evaluate(() => document.activeElement?.id || document.activeElement?.tagName);
      focusTrace.push(active); if (active === "cancel-record") break; await page.keyboard.press("Tab");
    }
    assert.ok(focusTrace.includes("cancel-record"), "Keyboard path reaches Cancel");
    await page.keyboard.press("Enter"); await noPreview(); await expectState(before);
    await choose(originalDownload.file, { keyboard: true }); await preview(originalDownload.record);
    assert.equal(await page.$eval("#replace-record", n => n.textContent.trim()), "Replace current scenario");
    const captureMeta = await capture("desktop-preview");
    await activate("#replace-record", true); assert.deepEqual((await snapshot()).fields, fieldsOf(originalDownload.record.current.scenario));
    return { focusTrace, capture: captureMeta };
  });
  await group("narrow", async () => {
    await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 1 });
    await candidate(); await choose(originalDownload.file); await preview(originalDownload.record);
    const geometry = await page.evaluate(() => ({ width: innerWidth, documentWidth: document.documentElement.scrollWidth, preview: document.getElementById("record-preview").getBoundingClientRect().toJSON(), controls: ["replace-record", "cancel-record"].map(id => ({ id, rect: document.getElementById(id).getBoundingClientRect().toJSON() })) }));
    assert.ok(geometry.documentWidth <= geometry.width + 1, "No horizontal overflow requirement");
    assert.ok(geometry.controls.every(x => x.rect.width > 0 && x.rect.left >= 0 && x.rect.right <= geometry.width + 1));
    const captureMeta = await capture("narrow-preview");
    await page.click("#cancel-record"); await noPreview();
    return { geometry, capture: captureMeta };
  });
  await group("no-automatic-effects", async () => {
    const state = await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage), writes: window.__freightReceiver.storageWrites, cookies: document.cookie }));
    assert.deepEqual(state, { local: [], session: [], writes: [], cookies: "" });
    assert.deepEqual(report.storageWrites, []);
    assert.deepEqual(report.externalRequests, []);
    assert.deepEqual(report.pageErrors, []);
    assert.deepEqual(report.consoleErrors, []);
    assert.equal(downloadEvents.filter(x => x.kind === "begin").length, intentionalDownloads, "No unsolicited downloads");
    return { state, intentionalDownloads, served };
  });
  report.completed = true;
} catch (error) {
  report.fatal = { name: error.name, message: error.message, stack: error.stack };
} finally {
  clearTimeout(safetyTimer);
  try { if (browser) { await browser.close(); report.browserClosed = true; } } catch (error) { report.closeError = String(error); }
  if (server) await new Promise(resolve => server.close(resolve));
  report.sourceUnchanged = sourceRows.every(pin => hash(fs.readFileSync(pin.path)) === pin.sha256)
    && config.fixturePins.every(pin => hash(fs.readFileSync(pin.path)) === pin.sha256)
    && hash(fs.readFileSync(selfPath)) === selfHash
    && hash(fs.readFileSync(configPath)) === configHash;
  report.sourcePins = sourceRows;
  report.receiver = { path: selfPath, sha256: selfHash, configPath, configSha256: configHash };
  report.downloadEvents = downloadEvents;
  report.ended = new Date().toISOString();
  report.pass = report.completed && report.groups.length === 17 && report.groups.every(x => x.pass) && report.sourceUnchanged && report.browserClosed === true && !report.closeError && !report.fatal;
  save("browser-receipt.json", report);
  console.log(JSON.stringify({ pass: report.pass, groups: report.groups.length, passed: report.groups.filter(x => x.pass).length, sourceUnchanged: report.sourceUnchanged, receipt: path.join(output, "browser-receipt.json") }));
  process.exitCode = report.pass ? 0 : 1;
}
