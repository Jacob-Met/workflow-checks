// Exact inline UI script with authored DOM/API boundaries; no browser/layout claim.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const {test} = require("node:test");

const uiPath = process.env.PTAUTH_UI_SOURCE || path.join(__dirname, "../../ptauth/ui.html");
const html = fs.readFileSync(uiPath, "utf8");
const script = html.slice(html.indexOf("<script>") + 8, html.lastIndexOf("</script>"));
const calendarPath = path.join(path.dirname(uiPath), "calendar_ui.js");
const calendarScript = html.includes('<script src="/calendar_ui.js"></script>')
  ? fs.readFileSync(calendarPath, "utf8") : null;
if (!process.env.PTAUTH_UI_SUMMARY) throw new Error("PTAUTH_UI_SUMMARY must name an authored report");
const original = JSON.parse(fs.readFileSync(process.env.PTAUTH_UI_SUMMARY, "utf8"));
const clone = value => JSON.parse(JSON.stringify(value));
const ids = ["V-DONE-1", "V-DONE-2", ...Array.from({length: 6}, (_, i) => "V-UPCOMING-" + (i + 1))];

async function boot(input = original) {
  const elements = new Map();
  const element = selector => {
    if (!elements.has(selector)) elements.set(selector, {
      value: "", innerHTML: "", textContent: "", disabled: false, dataset: {},
      addEventListener(name, handler) { this["on" + name] = handler; },
      querySelector(child) { return element(selector + " " + child); },
      replaceChildren(...nodes) { this.children = nodes; },
      append(node) { (this.children ||= []).push(node); },
      classList: {states: {}, toggle(name, on) { this.states[name] = on; }}
    });
    return elements.get(selector);
  };
  const buttons = [...html.matchAll(/<button data-t="([^"]+)"/g)].map(match => ({
    dataset: {t: match[1]}, classList: {states: {}, toggle(name, on) { this.states[name] = on; }}
  }));
  const sections = [...html.matchAll(/<section id="([^"]+)"/g)].map(match => ({
    id: match[1], classList: {states: {}, toggle(name, on) { this.states[name] = on; }}
  }));
  const calls = [];
  const context = vm.createContext({
    document: {
      querySelector: element,
      createElement() { return {textContent: ""}; },
      querySelectorAll(selector) {
        if (selector === "#tabs button") return buttons;
        if (selector === "main > section") return sections;
        return [];
      }
    },
    fetch: async (url, options) => {
      calls.push({url, method: options?.method || "GET"});
      assert.equal(url, "/api/summary", "view requested an additional API operation");
      assert.equal(options?.method, undefined, "view attempted a mutation");
      return {ok: true, json: async () => clone(input)};
    },
    alert(message) { throw new Error(message); }
  });
  context.window = context;
  if (calendarScript !== null) {
    vm.runInContext(calendarScript, context, {filename: calendarPath, timeout: 1000});
  }
  vm.runInContext(script, context, {filename: uiPath, timeout: 1000});
  await new Promise(setImmediate);
  return {element, buttons, sections, calls, context};
}

function change(app, id, value, event = "onchange") {
  app.element(id).value = value;
  assert.equal(typeof app.element(id)[event], "function", id + " has no handler");
  app.element(id)[event]();
}

function displayed(app) {
  return app.element("#uc-rows").innerHTML;
}

test("the complete review is reachable and contains all eight appointments", async () => {
  const app = await boot();
  const button = app.buttons.find(item => item.dataset.t === "uncovered");
  assert.ok(button, "missing Uncovered visits navigation");
  button.onclick();
  assert.equal(app.sections.find(item => item.id === "t-uncovered").classList.states.hidden, false);
  assert.equal(app.sections.find(item => item.id === "t-work").classList.states.hidden, true);
  for (const id of ids) assert.ok(displayed(app).includes(id), "missing " + id);
  for (const id of ["V-PAST-SCHEDULED", "V-COVERED-FUTURE", "V-EXEMPT", "V-CANCELLED"]) {
    assert.ok(!displayed(app).includes(id), "unrelated visit appeared: " + id);
  }
  assert.match(app.element("#uc-shown").textContent, /^8 of 8 appointments/);
  assert.match(displayed(app), /schedule.csv:row11/);
  assert.match(displayed(app), /role="region" aria-label="Uncovered appointments"/);
});

test("recorded-status filtering keeps complete scheduled and completed groups", async () => {
  const app = await boot();
  change(app, "#uc-status", "scheduled");
  assert.match(app.element("#uc-shown").textContent, /^6 of 8 appointments/);
  for (const id of ids.slice(2)) assert.ok(displayed(app).includes(id), id);
  assert.ok(!displayed(app).includes("V-DONE-1"));
  change(app, "#uc-status", "completed");
  assert.match(app.element("#uc-shown").textContent, /^2 of 8 appointments/);
  assert.ok(displayed(app).includes("V-DONE-1") && displayed(app).includes("V-DONE-2"));
  assert.ok(!displayed(app).includes("V-UPCOMING-1"));
});

test("actual blank clinic and literal search combine without colliding with All", async () => {
  const input = clone(original);
  input.uncovered_review.at(-1).clinic = "";
  const app = await boot(input);
  change(app, "#uc-clinic", JSON.stringify(""));
  assert.match(app.element("#uc-shown").textContent, /^1 of 8 appointments/);
  assert.ok(displayed(app).includes("V-UPCOMING-6"));
  assert.ok(!displayed(app).includes("V-UPCOMING-5"));
  change(app, "#uc-search", "v-upcoming-6", "oninput");
  assert.match(app.element("#uc-shown").textContent, /^1 of 8 appointments/);
  change(app, "#uc-search", "missing literal [.*]", "oninput");
  assert.match(app.element("#uc-shown").textContent, /^0 of 8 appointments/);
  assert.match(displayed(app), /No appointments match these filters/);
  change(app, "#uc-clinic", "");
  change(app, "#uc-search", "CAFÉ", "oninput");
  assert.match(app.element("#uc-shown").textContent, /^8 of 8 appointments/);
});

test("field text stays escaped in rows and clinic option attributes", async () => {
  const input = clone(original);
  const row = input.uncovered_review[0];
  row.clinic = 'Clinic "quoted" <script>fixture</script> & café';
  row.therapist = "<img src=x onerror=fixture>";
  row.evidence = 'schedule.csv:row3 "quoted" & more';
  row.payer_rules_known = false;
  row.payer_name = "";
  const app = await boot(input);
  assert.match(displayed(app), /Test &lt;A&gt; &amp; &quot;café&quot;/);
  assert.match(displayed(app), /&lt;img src=x onerror=fixture&gt;/);
  assert.match(displayed(app), /Rules unavailable/);
  assert.ok(!displayed(app).includes("<script>fixture"));
  assert.ok(!displayed(app).includes("<img src=x"));
  assert.match(app.element("#uc-clinic").innerHTML, /&lt;script&gt;fixture&lt;\/script&gt;/);
  change(app, "#uc-clinic", JSON.stringify(row.clinic));
  assert.match(app.element("#uc-shown").textContent, /^1 of 8 appointments/);
});

test("CSV link stays explicitly complete and independent of filters", async () => {
  const app = await boot();
  const before = app.element("#uc-export").innerHTML;
  assert.match(before, /href="\/out\/uncovered_visits.csv" download/);
  assert.match(before, /Download all uncovered visits CSV/);
  assert.match(before, /independent of these filters/);
  change(app, "#uc-status", "completed");
  change(app, "#uc-search", "no match", "oninput");
  assert.equal(app.element("#uc-export").innerHTML, before);
  assert.deepEqual(app.calls, [{url: "/api/summary", method: "GET"}]);
});

test("old saved summaries require a rerun while a recorded empty review is zero", async () => {
  const legacy = clone(original);
  delete legacy.uncovered_review;
  delete legacy.uncovered_review_note;
  const old = await boot(legacy);
  assert.match(old.element("#uc-note").textContent, /Run worklist/);
  assert.equal(old.element("#uc-shown").textContent, "");
  assert.equal(old.element("#uc-export").innerHTML, "");
  for (const id of ["#uc-status", "#uc-clinic", "#uc-search"]) assert.equal(old.element(id).disabled, true);
  const empty = clone(original);
  empty.uncovered_review = [];
  const current = await boot(empty);
  assert.match(current.element("#uc-shown").textContent, /^0 of 0 appointments/);
  assert.match(displayed(current), /No appointments are in this review/);
  assert.match(current.element("#uc-export").innerHTML, /uncovered_visits.csv/);
  assert.equal(current.element("#uc-status").disabled, false);
});

test("staff approval and worklist filters do not hide or mutate the visit review", async () => {
  const input = clone(original);
  input.states = Object.fromEntries(input.worklist.map(row => [row.key, {state: "approved"}]));
  const frozen = JSON.stringify(input);
  const app = await boot(input);
  const before = displayed(app);
  change(app, "#fp", "P3");
  change(app, "#q", "no work item", "oninput");
  assert.equal(displayed(app), before);
  assert.match(app.element("#uc-shown").textContent, /^8 of 8 appointments/);
  assert.equal(JSON.stringify(input), frozen);
  assert.equal(vm.runInContext("JSON.stringify(S)", app.context), frozen);
  assert.deepEqual(app.calls, [{url: "/api/summary", method: "GET"}]);
});
