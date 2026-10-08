import { evaluate, originalInput } from './model.mjs';
const $ = id => document.getElementById(id);
const form = $('bill-form');
const numeric = (value, digits = 2) => Number(value).toLocaleString('en-US', { maximumFractionDigits: digits });
const money = value => '$' + Number(value).toFixed(4);
const monthName = value => new Date(value + 'T12:00:00Z').toLocaleDateString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' });
const labels = { NO_BASELINE: 'There is no compatible bill for the same service month last year. Usage has not been judged.', USAGE_UNIT_CHANGED: 'The usage units differ from last year. No unit conversion is assumed.', ZERO_USAGE: 'Zero consumption needs review for fixed or minimum charges.', NEGATIVE_USAGE: 'Negative consumption may be a meter adjustment. It needs review.', CREDIT_OR_NEGATIVE_BILL: 'This is a credit or zero-balance amount. It needs review.' };
let fixture;
function readInput() { return { usage: $('usage').valueAsNumber, amount: $('amount').valueAsNumber, ps: $('ps').value, pe: $('pe').value }; }
function setInput(input) { for (const name of ['usage', 'amount', 'ps', 'pe']) $(name).value = input[name]; }
function status(which, state, text) {
  $(which + '-status').textContent = text;
  $(which + '-status').className = 'status' + (state === 'flag' ? ' flag' : state === 'clear' ? '' : ' unknown');
  $(which + '-card').classList.toggle('flagged', state === 'flag');
}
function metric(id, value, unit) {
  const target = $(id); target.replaceChildren(document.createTextNode(value));
  const small = document.createElement('small'); small.textContent = unit; target.append(small);
}
function paragraph(target, text) { const p = document.createElement('p'); p.textContent = text; target.append(p); return p; }
function render(result) {
  const blocked = !result.inEvaluation || result.duplicate;
  $('result-title').textContent = blocked ? 'Comparison unavailable' : result.exceptions.length ? 'Some inputs need review' : result.flags.length ? 'Worth a closer look' : 'No usage or rate flags';
  $('result-count').textContent = `${result.flags.length} of 2 checks flagged`;
  $('freshness').textContent = 'Results describe the values currently shown.';
  $('freshness').className = 'freshness';
  $('period-summary').textContent = `${result.current.ps} to ${result.current.pe} · ${result.days} inclusive day${result.days === 1 ? '' : 's'} · Service month: ${monthName(result.serviceMonth)}`;
  const notes = [];
  if (!result.inEvaluation) notes.push(`This service month precedes the fixed evaluation start ${fixture.evalFrom}. The sample checker does not evaluate it.`);
  if (result.duplicate) notes.push(`This period and amount duplicates ${result.duplicateOf.bill} (${result.duplicateOf.evidence}). The full checker holds the duplicate before usage/rate comparison.`);
  notes.push(...result.exceptions.map(e => labels[e.reason]));
  $('review-notes').textContent = notes.join(' '); $('review-notes').hidden = !notes.length;
  const usage = result.usage;
  metric('usage-value', numeric(result.perDay, 1), 'therm / day');
  $('usage-comparison').hidden = !usage.baseline;
  if (usage.baseline) {
    status('usage', usage.status, usage.status === 'flag' ? 'Usage spike' : 'Within usage rule');
    const ratio = usage.ratio === null ? 'The prior-year baseline is zero.' : `This is ${numeric(usage.ratio, 6)}× the prior-year daily usage.`;
    $('usage-description').textContent = `${numeric(usage.baseline.perDay, 1)} therm/day in ${monthName(usage.baseline.month)}. ${ratio}`;
    const max = Math.max(result.perDay, usage.baseline.perDay, 1);
    $('baseline-bar').style.setProperty('--bar', `${Math.max(0, usage.baseline.perDay / max) * 72}%`);
    $('current-bar').style.setProperty('--bar', `${Math.max(0, result.perDay / max) * 72}%`);
  } else {
    status('usage', usage.status, 'Not judged');
    $('usage-description').textContent = blocked ? 'The checker does not run this comparison for the selected period.' : 'A compatible same-month bill from last year is required.';
  }
  $('usage-rule').textContent = `USAGE_SPIKE · Flags above ${fixture.rules.spike_ratio}× the same service month last year, after dividing both bills by their inclusive days. A positive reading above a zero baseline is also flagged.`;
  const rate = result.rate;
  if (rate.median !== undefined) {
    status('rate', rate.status, rate.status === 'flag' ? 'Rate change' : 'Within rate rule');
    metric('rate-value', money(rate.effectiveRate), '/ therm');
    $('rate-description').textContent = `${money(rate.median)}/therm trailing median from ${rate.count} compatible bills. This copy is ${numeric(rate.ratio, 6)}× the median.`;
  } else {
    status('rate', rate.status, 'Not judged');
    metric('rate-value', result.current.usage > 0 ? money(result.current.amount / result.current.usage) : '—', '/ therm');
    $('rate-description').textContent = rate.status === 'small-amount' ? `Amounts below $${fixture.rules.rate_min_amount} are excluded because fixed charges can dominate.` : rate.status === 'nonpositive-usage' ? 'A positive consumption value is required to compare effective rates.' : rate.status === 'short-history' ? `Only ${rate.count} compatible historical bills are available; at least 6 are required.` : 'The checker does not run this comparison for the selected period.';
  }
  $('rate-rule').textContent = `RATE_CHANGE · Flags above ${fixture.rules.rate_ratio}× the trailing 12-month median. Minimum bill $${fixture.rules.rate_min_amount}; at least 6 positive, compatible historical rates.`;
  const evidence = $('evidence-body'); evidence.replaceChildren();
  paragraph(evidence, `This is an edited copy of ${result.current.bill_id}, from bills.csv:${result.current.row}. The original fixture and its ${fixture.bills.length} account bills have not changed. Dates, consumption and amount shown above replace only this copy's values.`);
  if (usage.baseline) paragraph(evidence, `Usage baseline: ${usage.baseline.bill}, ${usage.baseline.evidence}; ${usage.baseline.ps} to ${usage.baseline.pe}, ${numeric(usage.baseline.usage)} therm. The latest month wins a tie for the most service days.`);
  if (rate.evidence) paragraph(evidence, `Rate baseline rows: ${rate.evidence.join(', ')}. Positive amounts and consumption only, with matching units, in the 12 service months before this copy.`);
  paragraph(evidence, 'Only USAGE_SPIKE and RATE_CHANGE are summarized here. No result here means the whole bill is clean, approved or paid. The rules use full precision; displayed figures are rounded.');
  const source = paragraph(evidence, 'Checked source: '); const link = document.createElement('a'); link.href = `https://github.com/${fixture.source.repository}/blob/${fixture.source.commit}/utility_watch/uwatch/engine.py`; link.textContent = `Utility Watch ${fixture.source.commit.slice(0, 10)}`; link.rel = 'noreferrer'; source.append(link);
}
function recalculate() {
  try { const result = evaluate(fixture, readInput()); $('input-error').textContent = ''; render(result); return true; }
  catch (error) {
    $('input-error').textContent = error.message;
    $('freshness').textContent = 'Not updated. The results below still describe the previous checked values.';
    $('freshness').className = 'freshness pending'; return false;
  }
}
form.addEventListener('input', () => { $('freshness').textContent = 'Edited values are not checked yet. Choose Recheck bill.'; $('freshness').className = 'freshness pending'; });
form.addEventListener('submit', event => { event.preventDefault(); recalculate(); });
for (const button of document.querySelectorAll('[data-preset]')) button.addEventListener('click', () => {
  if (!fixture) return;
  const input = originalInput(fixture), original = evaluate(fixture, input), baseline = original.usage.baseline;
  if (['typical', 'rate'].includes(button.dataset.preset) && baseline) {
    input.usage = Math.round(baseline.perDay * original.days * 100) / 100;
    input.amount = Math.round(input.usage * original.rate.median * (button.dataset.preset === 'rate' ? 1.35 : 1) * 100) / 100;
  }
  if (button.dataset.preset === 'period') { input.ps = '2026-04-16'; input.pe = '2026-05-15'; }
  setInput(input); recalculate();
});
try {
  const response = await fetch('./fixture.json', { cache: 'no-store' });
  if (!response.ok) throw new Error('The checked sample could not be loaded. Reload this page to try again.');
  fixture = await response.json();
  const input = originalInput(fixture), result = evaluate(fixture, input);
  $('account').textContent = `${fixture.account.property} / ${result.current.account_no}`;
  $('bill-id').textContent = fixture.selectedBill; $('as-of').textContent = fixture.asOf;
  setInput(input); render(result); $('loading').hidden = true; $('explorer').hidden = false;
} catch (error) { $('loading').textContent = `Explorer unavailable. ${error.message}`; $('loading').setAttribute('role', 'alert'); }
