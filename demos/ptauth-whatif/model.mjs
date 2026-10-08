/** Browser projection of ptauth.engine.build_worklist, source blob 39c97f3.
 * The Python source remains authoritative. This module accepts normalized,
 * date-only records produced by the adjacent fixture builder; it is not a CSV
 * importer or a real payer-policy service. See tests/parity.py and README.md.
 */
const DAY = 86400000;
const ORDER = { P1: 0, P2: 1, P3: 2 };
const LAST_DATE = '9999-12-31';
const active = (v) => v.status === 'completed' || v.status === 'scheduled';
const compare = (a, b) => a < b ? -1 : a > b ? 1 : 0;
const pair = (a, b) => JSON.stringify([a, b]);
const covers = (a, d) => a.start <= d && d <= a.end;

export function dateNumber(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value < '0001-01-01') {
    throw new Error('Use a complete calendar date (YYYY-MM-DD).');
  }
  const ms = Date.parse(`${value}T00:00:00Z`);
  if (!Number.isFinite(ms) || new Date(ms).toISOString().slice(0, 10) !== value) {
    throw new Error('Use a valid calendar date (YYYY-MM-DD).');
  }
  return ms / DAY;
}

export function shiftDate(value, days) {
  if (!Number.isSafeInteger(days)) throw new Error('The day offset must be a whole number.');
  const result = new Date((dateNumber(value) + days) * DAY).toISOString().slice(0, 10);
  dateNumber(result);
  return result;
}

const daysBetween = (later, earlier) => dateNumber(later) - dateNumber(earlier);
const counts = (v, rule) => !(v.visit_type === 'eval' && rule && !rule.counts_evals);

function normalizedInput(input) {
  const result = structuredClone(input);
  dateNumber(result.as_of);
  if (!Array.isArray(result.visits) || !Array.isArray(result.auths) || !result.payers || !result.patients) {
    throw new Error('The synthetic scenario is incomplete.');
  }
  for (const v of result.visits) {
    dateNumber(v.visit_date);
    v.visit_type ??= 'treatment';
    v.source_row ??= '';
  }
  for (const a of result.auths) {
    dateNumber(a.start); dateNumber(a.end);
    if (a.end < a.start) throw new Error('Authorization expiry must be on or after its start.');
    if (!Number.isSafeInteger(a.visits_authorized) || a.visits_authorized < 0) {
      throw new Error('Authorized visits must be a whole number of zero or more.');
    }
    a.source_row ??= '';
  }
  return result;
}

function dedupeVisits(visits) {
  const last = new Map(visits.filter((v) => v.visit_id).map((v) => [v.visit_id, v]));
  return visits.filter((v) => !v.visit_id || last.get(v.visit_id) === v);
}

function resolveAuths(auths) {
  const result = [];
  for (const a of auths) {
    const index = result.findIndex((b) => b.auth_no === a.auth_no && b.patient_id === a.patient_id &&
      b.payer_id === a.payer_id && b.start <= a.end && a.start <= b.end);
    if (index < 0) result.push(a); else result[index] = a;
  }
  const frequencies = new Map();
  for (const a of result) frequencies.set(a.auth_no, (frequencies.get(a.auth_no) ?? 0) + 1);
  const seen = new Set();
  return result.map((a) => {
    let auth = a;
    if (frequencies.get(a.auth_no) > 1) {
      let label = `${a.auth_no} (${a.start}..${a.end})`;
      while (seen.has(label)) label += '*';
      auth = { ...a, auth_no: label };
    }
    seen.add(auth.auth_no);
    return auth;
  });
}

function allocate(visits, auths, payers) {
  const approved = new Map();
  for (const a of auths) {
    if (a.status !== 'approved') continue;
    const key = pair(a.patient_id, a.payer_id);
    if (!approved.has(key)) approved.set(key, []);
    approved.get(key).push(a);
  }
  for (const list of approved.values()) list.sort((a, b) => compare(a.end, b.end) || compare(a.start, b.start));
  const ledgers = new Map();
  for (const list of approved.values()) {
    for (const auth of list) ledgers.set(auth.auth_no, { auth, used: [], scheduled: [] });
  }
  const uncovered = [];
  const ordered = visits.filter(active).sort((a, b) =>
    Number(a.status !== 'completed') - Number(b.status !== 'completed') ||
    compare(a.visit_date, b.visit_date) || compare(a.visit_id, b.visit_id));
  for (const v of ordered) {
    const rule = payers[v.payer_id];
    if ((rule && !rule.requires_auth) || !counts(v, rule)) continue;
    let home;
    for (const a of approved.get(pair(v.patient_id, v.payer_id)) ?? []) {
      const ledger = ledgers.get(a.auth_no);
      if (covers(a, v.visit_date) && a.visits_authorized - ledger.used.length - ledger.scheduled.length > 0) {
        home = ledger; break;
      }
    }
    if (!home) uncovered.push(v);
    else home[v.status === 'completed' ? 'used' : 'scheduled'].push(v);
  }
  return { ledgers, uncovered };
}

export function evaluate(input) {
  const data = normalizedInput(input);
  const { as_of: asOf, payers, patients } = data;
  const visits = dedupeVisits(data.visits);
  const auths = resolveAuths(data.auths);
  const { ledgers, uncovered } = allocate(visits, auths, payers);
  const items = new Map();
  function item(pid, payerId, authNo = '') {
    const key = `${pid}|${payerId}|${authNo}`;
    if (!items.has(key)) {
      const patient = patients[pid], rule = payers[payerId];
      items.set(key, {
        patient_id: pid, patient_name: patient ? patient.display_name : pid,
        clinic: patient ? patient.clinic : '', payer_id: payerId,
        payer_name: rule ? rule.payer_name : payerId, auth_no: authNo,
        priority: 'P3', reasons: [], detail: [], visits_used: null,
        visits_authorized: null, visits_remaining: null, scheduled_in_window: null,
        auth_end: null, days_left: null, next_visit: null, submit_by: null,
        checklist: [...(rule?.checklist ?? [])], evidence: [], key,
      });
    }
    return items.get(key);
  }
  const bump = (it, priority) => { if (ORDER[priority] < ORDER[it.priority]) it.priority = priority; };
  const future = new Map();
  for (const v of visits) {
    if (v.status === 'scheduled' && v.visit_date >= asOf) {
      const key = pair(v.patient_id, v.payer_id);
      if (!future.has(key)) future.set(key, []);
      future.get(key).push(v);
    }
  }
  const latestApproved = (pid, payerId) => {
    let latest;
    for (const a of auths) {
      if (a.status === 'approved' && a.patient_id === pid && a.payer_id === payerId &&
          (!latest || a.end > latest.end)) latest = a;
    }
    return latest;
  };
  const uncoveredByItem = new Map();
  for (const v of uncovered) {
    const pending = auths.find((a) => a.status === 'pending' && a.patient_id === v.patient_id &&
      a.payer_id === v.payer_id && covers(a, v.visit_date));
    const anchor = pending ?? latestApproved(v.patient_id, v.payer_id);
    const it = item(v.patient_id, v.payer_id, anchor?.auth_no ?? '');
    it.evidence.push(v.source_row);
    if (v.status === 'completed') {
      if (!it.reasons.includes('UNAUTHORIZED_DONE')) it.reasons.push('UNAUTHORIZED_DONE');
      it.detail.push(`completed visit ${v.visit_date} (${v.visit_id}) had no covering approved auth`);
      bump(it, 'P1'); continue;
    }
    // Past scheduled rows may anchor later annual-limit alerts. Keep their
    // context until all rules finish, then omit placeholders without a reason.
    if (v.visit_date < asOf) continue;
    const code = pending ? 'PENDING_FOLLOWUP' : 'UNCOVERED_VISIT';
    if (!it.reasons.includes(code)) it.reasons.push(code);
    if (pending) {
      it.detail.push(`visit ${v.visit_date} relies on PENDING auth ${pending.auth_no}; follow up with payer`);
      bump(it, daysBetween(v.visit_date, asOf) <= 2 ? 'P1' : 'P2');
    } else {
      if (!uncoveredByItem.has(it.key)) uncoveredByItem.set(it.key, []);
      uncoveredByItem.get(it.key).push(v);
      bump(it, daysBetween(v.visit_date, asOf) <= 7 ? 'P1' : 'P2');
    }
    it.next_visit = it.next_visit && it.next_visit < v.visit_date ? it.next_visit : v.visit_date;
  }
  for (const [key, list] of uncoveredByItem) {
    list.sort((a, b) => compare(a.visit_date, b.visit_date));
    const ids = list.slice(0, 4).map((v) => v.visit_id).join(', ') + (list.length > 4 ? ' ...' : '');
    items.get(key).detail.unshift(`${list.length} scheduled visit(s) outside any approved auth, first ${list[0].visit_date} (${ids})`);
  }
  for (const led of ledgers.values()) {
    const a = led.auth, rule = payers[a.payer_id];
    if (!rule || a.end < asOf || a.start > shiftDate(asOf, 30)) continue;
    const successor = auths.find((b) => ['approved', 'pending'].includes(b.status) &&
      b.patient_id === a.patient_id && b.payer_id === a.payer_id && b.auth_no !== a.auth_no &&
      b.start >= a.start && b.end > a.end);
    const remaining = a.visits_authorized - led.used.length;
    const daysLeft = daysBetween(a.end, asOf);
    const continuing = future.get(pair(a.patient_id, a.payer_id)) ?? [];
    const reasons = [], detail = [];
    if (remaining <= rule.reauth_visits_before && continuing.length) {
      reasons.push('REAUTH_BY_VISITS');
      detail.push(`${remaining} of ${a.visits_authorized} visits left (payer threshold ${rule.reauth_visits_before})`);
    }
    if (daysLeft <= rule.reauth_days_before && continuing.length) {
      reasons.push('REAUTH_BY_DATE');
      detail.push(`auth ends ${a.end} (${daysLeft} days); ${continuing.length} visit(s) still scheduled`);
    }
    if (remaining - led.scheduled.length < 0) detail.push(`scheduled visits exceed remaining by ${led.scheduled.length - remaining}`);
    if (!reasons.length || successor) continue;
    const it = item(a.patient_id, a.payer_id, a.auth_no);
    it.reasons.push(...reasons.filter((r) => !it.reasons.includes(r)));
    it.detail.push(...detail); it.evidence.push(a.source_row);
    const exhaust = remaining > 0 && remaining <= led.scheduled.length ? led.scheduled[remaining - 1].visit_date : null;
    const cutoff = exhaust && exhaust < a.end ? exhaust : a.end;
    it.submit_by = shiftDate(cutoff, -rule.turnaround_days);
    bump(it, it.submit_by <= asOf || remaining <= 0 ? 'P1' : 'P2');
  }
  const unknown = new Map();
  for (const v of visits) {
    if (!payers[v.payer_id] && v.status === 'scheduled' && v.visit_date >= asOf) {
      unknown.set(pair(v.patient_id, v.payer_id), [v.patient_id, v.payer_id]);
    }
  }
  for (const a of auths) {
    if (!payers[a.payer_id] && ['approved', 'pending'].includes(a.status) && a.end >= asOf) {
      unknown.set(pair(a.patient_id, a.payer_id), [a.patient_id, a.payer_id]);
    }
  }
  for (const [pid, payerId] of [...unknown.values()].sort((a, b) => compare(a[0], b[0]) || compare(a[1], b[1]))) {
    const it = item(pid, payerId, latestApproved(pid, payerId)?.auth_no ?? '');
    it.reasons.push('UNKNOWN_PAYER');
    it.detail.push(`payer ${payerId} is not in payers.csv; add its rules - re-auth thresholds and turnaround were not checked`);
    bump(it, 'P2');
  }
  for (const it of items.values()) {
    const led = ledgers.get(it.auth_no);
    if (led) {
      const a = led.auth;
      it.visits_used = led.used.length; it.visits_authorized = a.visits_authorized;
      it.visits_remaining = a.visits_authorized - led.used.length;
      it.scheduled_in_window = led.scheduled.length;
      it.auth_end = a.end; it.days_left = daysBetween(a.end, asOf);
    }
    const next = (future.get(pair(it.patient_id, it.payer_id)) ?? []).map((v) => v.visit_date).sort(compare);
    if (next.length) it.next_visit = next[0];
  }
  const year = new Map();
  for (const v of visits) {
    if (v.visit_date.slice(0, 4) !== asOf.slice(0, 4) || !active(v)) continue;
    const key = pair(v.patient_id, v.payer_id);
    if (!year.has(key)) year.set(key, { pid: v.patient_id, payerId: v.payer_id, done: 0, scheduled: 0 });
    year.get(key)[v.status === 'completed' ? 'done' : 'scheduled'] += 1;
  }
  for (const { pid, payerId, done, scheduled } of year.values()) {
    const rule = payers[payerId], limit = rule?.annual_visit_limit;
    if (!limit) continue;
    if (done + scheduled > limit || limit - done <= 3) {
      const it = [...items.values()].find((x) => x.patient_id === pid && x.payer_id === payerId) ?? item(pid, payerId);
      it.reasons.push('ANNUAL_LIMIT');
      it.detail.push(`${done} visits used of ${limit}/yr payer limit; ${scheduled} more scheduled`);
      bump(it, done + scheduled > limit ? 'P2' : 'P3');
    }
  }
  const ordered = [...items.values()].filter((it) => it.reasons.length).sort((a, b) => ORDER[a.priority] - ORDER[b.priority] ||
    compare(a.submit_by ?? LAST_DATE, b.submit_by ?? LAST_DATE) ||
    compare(a.next_visit ?? LAST_DATE, b.next_visit ?? LAST_DATE) || compare(a.patient_id, b.patient_id));
  const serializedLedgers = Object.fromEntries([...ledgers].map(([key, led]) => [key, {
    ...led, remaining: led.auth.visits_authorized - led.used.length,
    remaining_after_scheduled: led.auth.visits_authorized - led.used.length - led.scheduled.length,
  }]));
  return { items: ordered, ledgers: serializedLedgers, uncovered };
}
