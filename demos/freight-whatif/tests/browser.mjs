// Run against a fresh loopback static server and an isolated browser context.
// Required: FREIGHT_PLAYWRIGHT_MODULE, FREIGHT_CHROMIUM_EXECUTABLE.
// Optional: FREIGHT_SITE_ROOT, FREIGHT_BROWSER_OUTPUT; both must be explicit owned paths.
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, writeFile, mkdir, stat, mkdtemp, rm } from "node:fs/promises";
import { createHash } from "node:crypto";
import { join, resolve, relative, extname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createConnection } from "node:net";
import { evaluate } from "../site/model.mjs";
import { data } from "../site/data.mjs";

const demo = fileURLToPath(new URL("../", import.meta.url));
const site = resolve(process.env.FREIGHT_SITE_ROOT || join(demo, "site"));
const output = process.env.FREIGHT_BROWSER_OUTPUT;
if (!output || !process.env.FREIGHT_PLAYWRIGHT_MODULE || !process.env.FREIGHT_CHROMIUM_EXECUTABLE) {
  throw new Error("Set explicit browser module, executable and a new output directory.");
}
await mkdir(output, { recursive: false });
const temporary = await mkdtemp(join(output, "owned-browser-"));
const modulePath = process.env.FREIGHT_PLAYWRIGHT_MODULE;
const executablePath = process.env.FREIGHT_CHROMIUM_EXECUTABLE;
const { chromium } = await import(pathToFileURL(modulePath).href);
const mime = { ".html": "text/html; charset=utf-8", ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8" };
const requests = [], blockedRequests = [], pageErrors = [], consoleErrors = [];
const server = createServer(async (req, res) => {
  try {
    const pathname = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
    const file = resolve(site, "." + (pathname === "/" ? "/index.html" : pathname));
    if (!file.startsWith(site + "/")) { res.writeHead(403); res.end(); return; }
    const bytes = await readFile(file);
    res.writeHead(200, { "Content-Type": mime[extname(file)] || "application/octet-stream", "Cache-Control": "no-store" });
    res.end(bytes);
  } catch { res.writeHead(404); res.end("Not found"); }
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port, origin = "http://127.0.0.1:" + port;
const checks = [], failures = [];
let browser, context, browserVersion, exited = false, serverClosed = false;
const pins = {};
for (const name of ["index.html", "styles.css", "app.mjs", "model.mjs", "data.mjs"]) {
  pins[name] = createHash("sha256").update(await readFile(join(site, name))).digest("hex");
}
async function check(name, fn) {
  try { await fn(); checks.push(name); console.log("PASS " + name); }
  catch (error) { failures.push({ name, message: error.stack || error.message }); console.log("FAIL " + name + ": " + error.message); }
}
try {
  browser = await chromium.launch({
    executablePath, headless: true, downloadsPath: temporary,
    env: { ...process.env, TMPDIR: temporary },
  });
  browserVersion = browser.version();
  context = await browser.newContext({ viewport: { width: 1365, height: 1000 }, deviceScaleFactor: 1,
    acceptDownloads: true, timezoneId: "Pacific/Auckland", locale: "en-US", reducedMotion: "reduce" });
  await context.route("**/*", route => {
    const url = route.request().url();
    if (url.startsWith(origin + "/")) { requests.push(new URL(url).pathname); return route.continue(); }
    blockedRequests.push(url); return route.abort();
  });
  const page = await context.newPage();
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await page.goto(origin, { waitUntil: "networkidle" });
  await check("default exact decision, evidence, baseline", async () => {
    assert.equal(await page.locator("#supported-amount").textContent(), "$131.25");
    assert.equal(await page.locator("#status-chip").textContent(), "Detention supported");
    assert.equal(await page.locator(".finding[data-code=DETENTION_UNSUPPORTED]").count(), 1);
    assert.match(await page.locator("#engine-notes").textContent(), /arrived 15 min early/);
    assert.match(await page.locator("#baseline-summary").textContent(), /unchanged/);
    assert.equal(await page.locator("#edited-badge").isVisible(), false);
    assert.equal(await page.locator("#download").isEnabled(), true);
    await page.screenshot({ path: join(output, "desktop-default.png"), fullPage: true });
  });
  await check("edit resolves charge and reset restores loaded baseline", async () => {
    await page.locator("#detention_cents").fill("131.25");
    assert.equal(await page.locator(".finding").count(), 0);
    assert.match(await page.locator("#baseline-summary").textContent(), /1 resolved finding/);
    assert.equal(await page.locator("#supported-amount").textContent(), "$131.25");
    await page.locator("#reset").click();
    assert.equal(await page.locator("#detention_cents").inputValue(), "150.00");
    assert.equal(await page.locator(".finding").count(), 1);
    assert.match(await page.locator("#baseline-summary").textContent(), /unchanged/);
  });
  await check("all presets set independent baselines", async () => {
    for (const preset of data.presets) {
      await page.locator('[data-preset="' + preset.id + '"]').click();
      const expected = evaluate(preset.scenario);
      assert.equal(await page.locator(".finding").count(), expected.flags.length);
      assert.match(await page.locator("#baseline-label").textContent(), new RegExp(preset.title));
      assert.match(await page.locator("#baseline-summary").textContent(), /unchanged/);
      assert.equal(await page.locator("#edited-badge").isVisible(), false);
      if (expected.stop.status === "exception") assert.equal(await page.locator("#supported-amount").textContent(), "No automatic claim");
    }
  });
  await check("invalid cents pause output/download; recovery uses edited value", async () => {
    await page.locator('[data-preset="long-dwell"]').click();
    for (const bad of ["NaN", "Infinity", "1e3", "10.001", "-1"]) {
      await page.locator("#detention_cents").fill(bad);
      assert.equal(await page.locator("#result-content").isVisible(), false);
      assert.equal(await page.locator("#invalid-state").isVisible(), true);
      assert.equal(await page.locator("#download").isDisabled(), true);
      assert.equal(await page.locator("#detention_cents").getAttribute("aria-invalid"), "true");
    }
    await page.locator("#focus-error").click();
    assert.equal(await page.locator("#detention_cents").evaluate(el => document.activeElement === el), true);
    await page.locator("#detention_cents").fill("131.25");
    assert.equal(await page.locator("#result-content").isVisible(), true);
    assert.equal(await page.locator("#download").isEnabled(), true);
    assert.equal(await page.locator(".finding").count(), 0);
  });
  await check("empty appointment pauses; missing departure needs human review", async () => {
    await page.locator("#appointment").fill("");
    assert.equal(await page.locator("#download").isDisabled(), true);
    await page.locator("#appointment").fill("2026-09-07T09:00");
    await page.locator("#departure").fill("");
    assert.equal(await page.locator("#supported-amount").textContent(), "No automatic claim");
    assert.equal(await page.locator("#download").isEnabled(), true);
    assert.match(await page.locator("#engine-notes").textContent(), /no matching exit/);
  });
  await check("proof of delivery and incomplete rate con update live findings", async () => {
    await page.locator("#reset").click();
    await page.locator("#pod_received").uncheck();
    assert.equal(await page.locator(".finding[data-code=MISSING_POD]").count(), 1);
    await page.locator(".terms summary").click();
    await page.locator("#ratecon_complete").uncheck();
    assert.equal(await page.locator("#supported-amount").textContent(), "No automatic claim");
    assert.match(await page.locator("#engine-notes").textContent(), /rate-con parse warnings/);
    await page.locator("#ratecon_complete").check();
    await page.locator("#pod_received").check();
  });
  await check("manual invoice header mismatch is exact; blank returns automatic", async () => {
    await page.locator("#invoice_total_cents").fill("1994.99");
    assert.equal(await page.locator(".finding[data-code=TOTAL_MISMATCH]").count(), 1);
    assert.match(await page.locator(".finding[data-code=TOTAL_MISMATCH]").textContent(), /-\$0.01/);
    await page.locator("#invoice_total_cents").fill("");
    assert.equal(await page.locator(".finding[data-code=TOTAL_MISMATCH]").count(), 0);
  });
  await check("download freezes current inputs/results and original baseline", async () => {
    await page.locator("#departure").fill("2026-09-07T13:00");
    await page.locator("#detention_cents").fill("150.00");
    const current = { ...data.presets[0].scenario, departure: "2026-09-07T13:00" };
    const downloadWait = page.waitForEvent("download");
    await page.locator("#download").click();
    const download = await downloadWait;
    const record = JSON.parse(await readFile(await download.path(), "utf8"));
    assert.equal(record.schema, "workflow-checks.freight-whatif.v1");
    assert.equal(record.synthetic, true);
    assert.deepEqual(record.current.scenario, current);
    assert.deepEqual(record.current.result, evaluate(current));
    assert.deepEqual(record.baseline.scenario, data.presets[0].scenario);
    assert.deepEqual(record.baseline.result, evaluate(data.presets[0].scenario));
    assert.deepEqual(record.provenance, data.provenance);
    assert.equal(record.current.result.stop.amount_cents, 15000);
    assert.equal(await page.locator("#supported-amount").textContent(), "$150.00");
    await writeFile(join(output, "download-record.json"), JSON.stringify(record, null, 2) + "\n", { flag: "wx" });
  });
  await check("keyboard skip, native details, preset and field navigation", async () => {
    await page.goto(origin, { waitUntil: "networkidle" });
    await page.keyboard.press("Tab");
    assert.equal(await page.locator(".skip-link").evaluate(el => document.activeElement === el), true);
    await page.keyboard.press("Enter");
    assert.equal(await page.locator("#results-heading").evaluate(el => document.activeElement === el), true);
    await page.locator(".terms summary").focus();
    await page.keyboard.press("Enter");
    assert.equal(await page.locator(".terms").evaluate(el => el.open), true);
    await page.locator('[data-preset="within-free"]').focus();
    await page.keyboard.press("Space");
    assert.equal(await page.locator("#supported-amount").textContent(), "$0.00");
    await page.locator("#appointment").focus();
    await page.keyboard.press("Tab");
    // Chromium may move between the date/time subfields; focus must remain within the timing input group.
    assert.ok(["appointment", "arrival", "departure"].includes(await page.evaluate(() => document.activeElement.id)));
  });
  await check("mobile 390px and 320px have no horizontal overflow", async () => {
    await page.locator('[data-preset="long-dwell"]').click();
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
      assert.equal(await page.locator("#download").isVisible(), true);
      await page.locator("#detention_cents").fill("131.25");
      assert.equal(await page.locator(".finding").count(), 0);
      await page.locator("#reset").click();
      await page.screenshot({ path: join(output, "mobile-" + width + ".png"), fullPage: true });
    }
  });
  await check("no runtime errors or external requests", async () => {
    assert.deepEqual(pageErrors, []);
    assert.deepEqual(consoleErrors, []);
    assert.deepEqual(blockedRequests, []);
  });
} catch (error) {
  failures.push({ name: "runner", message: error.stack || error.message });
} finally {
  if (context) await context.close();
  if (browser) { await browser.close(); exited = !browser.isConnected(); }
  await new Promise(resolve => server.close(() => { serverClosed = true; resolve(); }));
  await rm(temporary, { recursive: true });
}
const portClosed = await new Promise(resolve => {
  const socket = createConnection({ host: "127.0.0.1", port });
  socket.once("connect", () => { socket.destroy(); resolve(false); });
  socket.once("error", () => resolve(true));
});
if (!exited || !serverClosed || !portClosed) failures.push({ name: "cleanup", message: "Owned browser/server did not terminate cleanly" });
for (const name of Object.keys(pins)) {
  assert.equal(createHash("sha256").update(await readFile(join(site, name))).digest("hex"), pins[name], "Source changed during receiving: " + name);
}
const receipt = {
  schema: "freight-whatif.browser-receipt.v1", runtime: process.version,
  browser_version: browserVersion, browser_module_sha256: createHash("sha256").update(await readFile(modulePath)).digest("hex"),
  browser_executable_sha256: createHash("sha256").update(await readFile(executablePath)).digest("hex"),
  site_sha256: pins, runner_sha256: createHash("sha256").update(await readFile(fileURLToPath(import.meta.url))).digest("hex"),
  test_timezone: "Pacific/Auckland", site_root: site, origin,
  passed: checks.length, failed: failures.length, checks, failures,
  page_errors: pageErrors, console_errors: consoleErrors, blocked_requests: blockedRequests,
  requested_paths: [...new Set(requests)].sort(),
  cleanup: { browser_disconnected: exited, server_closed: serverClosed, loopback_port_closed: portClosed, temporary_profile_removed: true },
};
await writeFile(join(output, "browser-receipt.json"), JSON.stringify(receipt, null, 2) + "\n", { flag: "wx" });
console.log(JSON.stringify({ passed: checks.length, failed: failures.length, cleanup: receipt.cleanup, output }));
if (failures.length) process.exitCode = 1;
