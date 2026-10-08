// Optional native browser check. Requires an installed Playwright and Chromium.
// Run from freight_packets: node tests/review_browser_smoke.cjs
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const {spawn, execFileSync} = require("node:child_process");
const {once} = require("node:events");
const {chromium} = require("playwright");

const root = fs.mkdtempSync(path.join(os.tmpdir(), "freight-review-browser-"));
const python = process.env.PYTHON || "python3";
const server = spawn(python, ["-u", "-c", `
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from freightpkt.synth import generate
from freightpkt.pipeline import run
from freightpkt.web import App, make_handler
root = Path(sys.argv[1])
generate(root / "data", n_loads=24, seed=7)
run(root / "data", root / "out")
server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(root / "data", root / "out")))
print(server.server_address[1], flush=True)
server.serve_forever()
`, root], {cwd: path.resolve(__dirname, ".."), stdio: ["ignore", "pipe", "pipe"]});
let browser, stderr = "";
server.stderr.on("data", data => stderr += data);
const checks = [];
function mark(message) { checks.push(message); console.log(message); }
function changeCarrier(loadId, remove = false) {
  execFileSync(python, ["-c", `
import csv, sys
from pathlib import Path
p = Path(sys.argv[1]) / "data" / "loads.csv"
with p.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fields, rows = reader.fieldnames, list(reader)
if sys.argv[3] == "remove":
    rows = [r for r in rows if r["load_id"] != sys.argv[2]]
else:
    for r in rows:
        if r["load_id"] == sys.argv[2]:
            r["carrier"] = "Revised browser fixture carrier"
with p.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
`, root, loadId, remove ? "remove" : "edit"]);
}

(async () => {
  const firstOutput = await Promise.race([
    once(server.stdout, "data").then(([data]) => String(data).trim()),
    once(server, "exit").then(([code]) => { throw new Error("server exited: " + code + " " + stderr); }),
    new Promise((_, reject) => { setTimeout(() => reject(new Error("server startup timeout")), 15000).unref(); }),
  ]);
  const base = "http://127.0.0.1:" + Number(firstOutput);
  browser = await chromium.launch({
    headless: true,
    ...(process.env.BROWSER_BIN ? {executablePath: process.env.BROWSER_BIN} : {}),
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  console.log("browser launched");
  const page = await browser.newPage();
  await page.setViewportSize({width: 1280, height: 900});
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(base, {waitUntil: "networkidle"});
  await page.waitForSelector("#t-packets tr[data-l]");
  console.log("initial review page ready");
  const initial = await fetch(base + "/api/summary").then(r => r.json());
  const packet = initial.packets.find(p => p.detention_cents > 0);
  const loadId = packet.load_id;
  await page.click('tr[data-l="' + loadId + '"]');
  console.log("selected packet");
  await page.type("#note", "Original native browser review");
  await page.click('[data-d="approve"]');
  await page.waitForFunction(id => document.querySelector('tr[data-l="' + id + '"] .approve'), loadId);
  const approvedCard = await page.$eval("#cards .card:nth-child(4) b", el => el.textContent);
  assert.notEqual(approvedCard, "$0.00");
  mark("reviewed packet counted as approved");

  const stalePage = await browser.newPage();
  stalePage.on("pageerror", error => errors.push(error.message));
  await stalePage.goto(base, {waitUntil: "networkidle"});
  await stalePage.click('tr[data-l="' + loadId + '"]');
  changeCarrier(loadId);
  assert.equal((await fetch(base + "/api/run", {method: "POST", body: "{}"})).status, 200);
  let conflict = false;
  stalePage.on("response", response => {
    if (response.url().endsWith("/api/decision") && response.status() === 409) conflict = true;
  });
  await stalePage.$eval("#note", el => el.value = "Stale browser note must not overwrite");
  await stalePage.click('[data-d="approve"]');
  await stalePage.waitForFunction(() => document.querySelector("#review-status")?.textContent.includes("reload"));
  assert.equal(conflict, true);
  const refused = await fetch(base + "/api/summary").then(r => r.json());
  assert.equal(refused.decisions[loadId].note, "Original native browser review");
  assert.equal(refused.decisions[loadId].review_state, "stale");
  assert.equal(await stalePage.$eval("#note", el => el.value), "Stale browser note must not overwrite");
  mark("stale browser received 409; original review and draft note retained");

  await page.reload({waitUntil: "networkidle"});
  await page.click('tr[data-l="' + loadId + '"]');
  assert.equal(await page.$eval("#cards .card:nth-child(4) b", el => el.textContent), "$0.00");
  assert.match(await page.$eval('tr[data-l="' + loadId + '"]', el => el.textContent), /review again/);
  assert.match(await page.$eval("#review-status", el => el.textContent), /changed/);
  await page.screenshot({path: path.join(root, "changed-evidence-desktop.png"), fullPage: true});
  mark("changed evidence removed from approved total and visibly requires review");

  await page.$eval("#note", el => el.value = "Reviewed revised packet");
  await page.click('[data-d="approve"]');
  await page.waitForFunction(id => document.querySelector('tr[data-l="' + id + '"] .approve'), loadId);
  await page.click(".review-history summary");
  assert.match(await page.$eval(".review-history", el => el.textContent), /Original native browser review/);
  const saved = await fetch(base + "/api/summary").then(r => r.json());
  assert.equal(saved.decisions[loadId].note, "Reviewed revised packet");
  assert.equal(saved.decisions[loadId].review_state, "current");
  mark("explicit re-review accepted and previous note available in history");

  await page.setViewportSize({width: 390, height: 844});
  await page.screenshot({path: path.join(root, "review-mobile.png"), fullPage: true});
  const layout = await page.evaluate(() => ({width: innerWidth, scroll: document.documentElement.scrollWidth}));
  assert.ok(layout.scroll <= layout.width, JSON.stringify(layout));
  mark("390px mobile view fits without page overflow");

  changeCarrier(loadId, true);
  await page.click("#run");
  await page.waitForFunction(id => !document.querySelector('tr[data-l="' + id + '"]'), loadId);
  assert.notEqual(await page.$eval("tr.sel", el => el.dataset.l), loadId);
  const missing = await fetch(base + "/api/summary").then(r => r.json());
  assert.equal(missing.decisions[loadId].review_state, "missing");
  assert.equal(missing.decisions[loadId].note, "Reviewed revised packet");
  mark("removed packet clears selection and preserves its historical decision");

  assert.deepEqual(errors, []);
  const receipt = {checks, browser: await browser.version(), evidenceRoot: root};
  fs.writeFileSync(path.join(root, "receipt.json"), JSON.stringify(receipt, null, 2) + "\n");
  console.log(JSON.stringify(receipt, null, 2));
})().catch(error => {
  console.error(error.stack);
  console.error("Evidence retained at " + root);
  process.exitCode = 1;
}).finally(async () => {
  try {
    if (browser) await browser.close();
  } finally {
    server.kill("SIGTERM");
  }
});
