// Browser projection of the two advertised uwatch checks. The unchanged Python
// engine generates the independent parity oracle; it remains the source authority.
const DAY = 86400000;
export const QUALIFIED_ENGINE_BLOB = '9deb205ad468381ffc91716f0d7ae6ab88d76f2a';
export function day(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error('Use a complete date in YYYY-MM-DD form.');
  const [y, m, d] = value.split('-').map(Number);
  const result = new Date(Date.UTC(y, m - 1, d));
  if (y < 1900 || y > 2100 || result.toISOString().slice(0, 10) !== value) throw new Error('Choose a real date between 1900 and 2100.');
  return result.getTime() / DAY;
}
const iso = value => new Date(value * DAY).toISOString().slice(0, 10);
const firstMonth = value => value.slice(0, 7) + '-01';
function nextMonth(value) {
  const [y, m] = value.split('-').map(Number);
  return `${y + (m === 12 ? 1 : 0)}-${String(m % 12 + 1).padStart(2, '0')}-01`;
}
export function serviceMonth(ps, pe) {
  const start = day(ps), end = day(pe);
  if (end < start) throw new Error('The service end date must be on or after its start date.');
  if (end - start >= 366) throw new Error('This explorer supports periods of up to 366 days.');
  let selected, largest = -1;
  for (let month = firstMonth(ps); month <= firstMonth(pe); month = nextMonth(month)) {
    const [year, number] = month.split('-').map(Number);
    const followingStart = Date.UTC(year, number, 1) / DAY;
    const count = Math.min(end + 1, followingStart) - Math.max(start, day(month));
    if (count >= largest) { largest = count; selected = month; }
  }
  return selected;
}
const unitKey = unit => unit.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
const evidence = bill => `bills.csv:${bill.row}`;
const median = values => { const v = [...values].sort((a, b) => a - b); const n = v.length; return n % 2 ? v[(n - 1) / 2] : (v[n / 2 - 1] + v[n / 2]) / 2; };
function decorate(bill) {
  const days = day(bill.pe) - day(bill.ps) + 1;
  return { ...bill, days, perDay: bill.usage / days, month: serviceMonth(bill.ps, bill.pe) };
}
export function originalInput(fixture) {
  const b = fixture.bills.find(b => b.bill_id === fixture.selectedBill);
  return { usage: b.usage, amount: b.amount, ps: b.ps, pe: b.pe };
}
export function evaluate(fixture, input) {
  if (fixture.schema !== 'utility-watch.whatif-fixture.v1' || fixture.version !== 1 || !fixture.synthetic) throw new Error('This fixture version is unavailable.');
  if (fixture.source?.files?.['utility_watch/uwatch/engine.py']?.gitBlob !== QUALIFIED_ENGINE_BLOB) throw new Error('The fixture and checked rule version differ. Reload a complete installation.');
  for (const key of ['usage', 'amount']) if (typeof input[key] !== 'number' || !Number.isFinite(input[key]) || Math.abs(input[key]) > 1e9) throw new Error('Enter finite consumption and amount values between −1 billion and 1 billion.');
  if (Number(input.amount.toFixed(2)) !== input.amount) throw new Error('Enter the bill amount with at most two decimal places.');
  serviceMonth(input.ps, input.pe);
  const original = fixture.bills.find(b => b.bill_id === fixture.selectedBill);
  if (!original) throw new Error('The selected synthetic bill is missing.');
  const current = decorate({ ...original, ...input });
  const bills = fixture.bills.map(b => b.bill_id === current.bill_id ? current : decorate(b)).sort((a, b) => a.ps.localeCompare(b.ps) || a.received.localeCompare(b.received));
  const seenInvoice = new Map(), seenPeriod = new Map(), duplicateIds = new Set();
  let duplicateOf = null;
  for (const b of bills) {
    // Inputs and source amounts are monetary cents in the UI. toFixed also keeps
    // the period/amount key stable when identical numeric values have different text.
    const key = `${b.ps}|${b.pe}|${b.amount.toFixed(2)}`;
    const first = (b.invoice && seenInvoice.get(b.invoice)) || seenPeriod.get(key);
    if (first) { duplicateIds.add(b.bill_id); if (b.bill_id === current.bill_id) duplicateOf = first; }
    else { if (b.invoice) seenInvoice.set(b.invoice, b); seenPeriod.set(key, b); }
    if (b.bill_id === current.bill_id) break;
  }
  const result = { flags: [], exceptions: [], duplicate: false, inEvaluation: current.month >= fixture.evalFrom, days: current.days, serviceMonth: current.month, perDay: current.perDay, current, usage: { status: 'not-evaluated' }, rate: { status: 'not-evaluated' } };
  if (!result.inEvaluation) return result;
  if (duplicateOf) { result.duplicate = true; result.duplicateOf = { bill: duplicateOf.bill_id, evidence: evidence(duplicateOf) }; return result; }
  const except = reason => result.exceptions.push({ reason, evidence: [evidence(current)] });
  if (current.amount < 0 || Number((current.amount + current.late_fee + current.prior_balance).toFixed(2)) <= 0) except('CREDIT_OR_NEGATIVE_BILL');
  if (current.usage < 0) except('NEGATIVE_USAGE'); else if (current.usage === 0) except('ZERO_USAGE');
  const previousYearMonth = `${Number(current.month.slice(0, 4)) - 1}${current.month.slice(4)}`;
  const priorAll = bills.filter(b => b.month === previousYearMonth && !duplicateIds.has(b.bill_id));
  const prior = priorAll.filter(b => unitKey(b.unit) === unitKey(current.unit));
  if (priorAll.length && !prior.length) { except('USAGE_UNIT_CHANGED'); result.usage = { status: 'unit-changed' }; }
  else if (!prior.length) { except('NO_BASELINE'); result.usage = { status: 'no-baseline' }; }
  else {
    const baseline = prior[0], ratio = baseline.perDay ? current.perDay / baseline.perDay : null;
    const flagged = (ratio !== null && ratio > fixture.rules.spike_ratio) || (baseline.perDay === 0 && current.perDay > 0);
    result.usage = { status: flagged ? 'flag' : 'clear', baseline: { bill: baseline.bill_id, month: baseline.month, perDay: baseline.perDay, ps: baseline.ps, pe: baseline.pe, usage: baseline.usage, evidence: evidence(baseline) }, ratio };
    if (flagged) result.flags.push({ code: 'USAGE_SPIKE', evidence: [evidence(current), evidence(baseline)] });
  }
  if (current.amount < fixture.rules.rate_min_amount) result.rate = { status: 'small-amount' };
  else if (current.usage <= 0) result.rate = { status: 'nonpositive-usage' };
  else {
    const history = bills.filter(b => b.usage > 0 && b.amount > 0 && !duplicateIds.has(b.bill_id) && unitKey(b.unit) === unitKey(current.unit) && b.month < current.month && b.month >= previousYearMonth);
    if (history.length < 6) result.rate = { status: 'short-history', count: history.length };
    else {
      const historicalMedian = median(history.map(b => b.amount / b.usage));
      const effectiveRate = current.amount / current.usage, ratio = effectiveRate / historicalMedian;
      const flagged = ratio > fixture.rules.rate_ratio;
      result.rate = { status: flagged ? 'flag' : 'clear', median: historicalMedian, effectiveRate, ratio, count: history.length, evidence: history.map(evidence) };
      if (flagged) result.flags.push({ code: 'RATE_CHANGE', evidence: [evidence(current)] });
    }
  }
  return result;
}
export function comparison(result) {
  return Object.fromEntries(['flags', 'exceptions', 'duplicate', 'inEvaluation', 'days', 'serviceMonth', 'perDay'].map(key => [key, result[key]]));
}
