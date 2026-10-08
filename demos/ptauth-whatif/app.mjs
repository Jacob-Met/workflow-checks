/** UI for the self-contained synthetic demonstration. No storage or I/O. */
export function mount(fixture, model) {
  const $ = (id) => document.getElementById(id);
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const clone = (value) => structuredClone(value);
  const canonical = (value) => JSON.stringify(value, (_, v) => v && typeof v === 'object' && !Array.isArray(v)
    ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, v[k]])) : v);
  const names = {
    UNCOVERED_VISIT: 'Scheduled visits without approved capacity',
    UNAUTHORIZED_DONE: 'Completed visit without covering approval',
    REAUTH_BY_VISITS: 'Visits-left threshold reached',
    REAUTH_BY_DATE: 'Expiry threshold reached',
    PENDING_FOLLOWUP: 'Upcoming visits rely on pending approval',
    ANNUAL_LIMIT: 'Calendar-year limit', UNKNOWN_PAYER: 'Payer rules missing',
  };
  let input = clone(fixture.input), output;
  let selectedPatient = 'SYN-1002', selectedAuth = -1, selectedVisit = -1, dirty = false;
  let changedSources = new Set();

  function option(select, value, text) {
    const node = el('option', '', text); node.value = String(value); select.append(node);
  }
  function earliestScheduled(pid) {
    const candidates = input.visits.map((v, index) => ({ v, index })).filter(({ v }) =>
      v.patient_id === pid && v.status === 'scheduled');
    candidates.sort((a, b) => a.v.visit_date.localeCompare(b.v.visit_date) || a.v.visit_id.localeCompare(b.v.visit_id));
    return (candidates.find(({ v }) => v.visit_date >= input.as_of) ?? candidates[0])?.index ?? -1;
  }
  function syncEditors() {
    $('as-of').value = input.as_of;
    $('patient').value = selectedPatient;
    const patient = input.patients[selectedPatient], rule = input.payers[patient.primary_payer];
    $('patient-context').textContent = `${patient.clinic} · ${rule?.payer_name ?? patient.primary_payer}`;
    const authIndices = input.auths.map((a, i) => a.patient_id === selectedPatient ? i : -1).filter((i) => i >= 0);
    if (!authIndices.includes(selectedAuth)) selectedAuth = authIndices[0] ?? -1;
    $('authorization').replaceChildren();
    if (!authIndices.length) option($('authorization'), -1, 'No authorization record');
    for (const i of authIndices) option($('authorization'), i, `${input.auths[i].auth_no} · ${input.auths[i].status}`);
    $('authorization').value = String(selectedAuth);
    const auth = input.auths[selectedAuth];
    $('capacity').value = auth ? auth.visits_authorized : '';
    $('expiry').value = auth ? auth.end : '';
    $('expiry').min = auth?.start ?? '2026-01-01';
    $('capacity').disabled = !auth; $('expiry').disabled = !auth;
    $('auth-context').textContent = auth
      ? `${auth.status.toUpperCase()} · starts ${auth.start} · ${auth.source_row}${auth.status === 'pending' ? '. Pending records do not supply approved capacity.' : ''}`
      : rule && !rule.requires_auth ? 'This placeholder payer does not require authorization.' : 'No approved capacity is available from an authorization record.';
    const visitIndices = input.visits.map((v, i) => v.patient_id === selectedPatient && v.status === 'scheduled' ? i : -1).filter((i) => i >= 0);
    if (!visitIndices.includes(selectedVisit)) selectedVisit = earliestScheduled(selectedPatient);
    $('visit').replaceChildren();
    if (!visitIndices.length) option($('visit'), -1, 'No scheduled visits');
    for (const i of visitIndices) option($('visit'), i, `${input.visits[i].visit_id} · ${input.visits[i].visit_date}`);
    $('visit').value = String(selectedVisit);
    $('visit-date').value = input.visits[selectedVisit]?.visit_date ?? '';
    $('visit-date').disabled = selectedVisit < 0;
    $('patient').disabled = false;
    $('authorization').disabled = authIndices.length === 0;
    $('visit').disabled = visitIndices.length === 0;
    for (const control of [$('as-of'), $('capacity'), $('expiry'), $('visit-date')]) control.removeAttribute('aria-invalid');
    dirty = false;
    $('draft-state').textContent = 'Showing the applied scenario.';
  }
  function markDirty() {
    dirty = true;
    $('results').hidden = true;
    $('error').hidden = true;
    $('patient').disabled = true; $('authorization').disabled = true; $('visit').disabled = true;
    $('draft-state').textContent = 'Edits are waiting. Apply or reset before changing records.';
    $('result-announcement').textContent = 'Worklist hidden while changes are waiting. Apply changes to calculate this scenario.';
  }
  function dateFrom(control) {
    const value = control.value;
    try { model.dateNumber(value); } catch { throw { control, message: `Enter a valid ${control.id === 'as-of' ? 'worklist as-of' : control.id === 'expiry' ? 'authorization expiry' : 'scheduled visit'} date.` }; }
    if ((control.min && value < control.min) || (control.max && value > control.max)) {
      throw { control, message: `Use a date from ${control.min} through ${control.max}. Authorization expiry cannot precede its start.` };
    }
    return value;
  }
  function applyEditors(event) {
    event.preventDefault();
    try {
      const candidate = clone(input);
      candidate.as_of = dateFrom($('as-of'));
      if (selectedAuth >= 0) {
        const raw = $('capacity').value;
        const count = raw.trim() ? Number(raw) : NaN;
        if (!Number.isSafeInteger(count) || count < 0 || count > 200) {
          throw { control: $('capacity'), message: 'Authorized visits must be a whole number from 0 through 200 in this demonstration.' };
        }
        candidate.auths[selectedAuth].visits_authorized = count;
        candidate.auths[selectedAuth].end = dateFrom($('expiry'));
      }
      if (selectedVisit >= 0) candidate.visits[selectedVisit].visit_date = dateFrom($('visit-date'));
      const result = model.evaluate(candidate);
      input = candidate; output = result;
      $('error').hidden = true;
      syncEditors(); render();
    } catch (error) {
      $('results').hidden = true;
      $('error').textContent = error.message ?? 'The scenario could not be calculated. Correct the controls or reset all changes.';
      $('error').hidden = false;
      if (error.control) { error.control.setAttribute('aria-invalid', 'true'); error.control.focus(); }
      $('result-announcement').textContent = 'No calculated worklist is displayed for the invalid scenario.';
      $('draft-state').textContent = 'Correct the marked field, then apply the changes. The last valid scenario is retained in memory.';
    }
  }
  function changes() {
    const result = [];
    if (input.as_of !== fixture.input.as_of) result.push({ source: '', text: `Worklist as of: ${fixture.input.as_of} → ${input.as_of}` });
    input.auths.forEach((a, i) => {
      const original = fixture.input.auths[i];
      if (a.visits_authorized !== original.visits_authorized) result.push({ source: a.source_row, text: `${a.auth_no} authorized visits: ${original.visits_authorized} → ${a.visits_authorized}` });
      if (a.end !== original.end) result.push({ source: a.source_row, text: `${a.auth_no} expiry: ${original.end} → ${a.end}` });
    });
    input.visits.forEach((v, i) => {
      const original = fixture.input.visits[i];
      if (v.visit_date !== original.visit_date) result.push({ source: v.source_row, text: `${v.visit_id} scheduled date: ${original.visit_date} → ${v.visit_date}` });
    });
    return result;
  }
  function sourceReference(source) {
    const node = el('span', 'source-ref', source);
    if (changedSources.has(source)) node.append(el('span', 'edited', 'scenario edited'));
    return node;
  }
  function highest(result, pid) {
    const priorities = result.items.filter((i) => i.patient_id === pid).map((i) => i.priority);
    return ['P1', 'P2', 'P3'].find((p) => priorities.includes(p)) ?? 'No item';
  }
  function renderWorklist() {
    $('worklist').replaceChildren();
    const list = $('view').value === 'selected' ? output.items.filter((i) => i.patient_id === selectedPatient) : output.items;
    if (!list.length) {
      const blank = el('div', 'empty');
      blank.append(el('strong', '', 'No work item in this view.'), el('p', '', 'The encoded rules produced no item for these inputs. This is not a coverage confirmation.'));
      $('worklist').append(blank); return;
    }
    for (const item of list) {
      const card = el('article', `work-item${item.patient_id === selectedPatient ? ' selected' : ''}`);
      card.dataset.key = item.key; card.dataset.priority = item.priority; card.dataset.patient = item.patient_id;
      const top = el('div', 'card-top'), title = el('div');
      title.append(el('h3', 'card-title', item.patient_name), el('p', 'card-context', `${item.patient_id} · ${item.clinic} · ${item.auth_no || 'No authorization anchor'}`));
      top.append(title, el('span', `priority ${item.priority}`, item.priority)); card.append(top);
      const reasons = el('ul', 'reason-list');
      for (const reason of item.reasons) {
        const node = el('li', '', names[reason] ?? reason); node.dataset.reason = reason; reasons.append(node);
      }
      if (!item.reasons.length) reasons.append(el('li', '', 'Source work item has no actionable reason'));
      card.append(reasons);
      const dates = el('div', 'card-dates');
      for (const [label, value] of [['Submit by', item.submit_by], ['Next scheduled', item.next_visit], ['Auth expires', item.auth_end]]) {
        if (value) { const part = el('div'); part.append(el('span', '', label), el('strong', '', value)); dates.append(part); }
      }
      card.append(dates);
      const inspect = el('button', 'inspect', item.patient_id === selectedPatient ? 'Inspecting this patient' : 'Explore this patient');
      inspect.type = 'button';
      inspect.addEventListener('click', () => {
        selectedPatient = item.patient_id;
        selectedAuth = input.auths.findIndex((a) => a.auth_no === item.auth_no && a.patient_id === selectedPatient);
        selectedVisit = -1; syncEditors(); render(); $('patient').focus();
      });
      card.append(inspect);
      const evidence = el('details'); evidence.append(el('summary', '', 'Why this item appears'));
      const detail = el('ul');
      for (const text of item.detail) detail.append(el('li', 'detail', text));
      if (item.reasons.length) detail.append(el('li', 'source-ref', `Rule codes: ${item.reasons.join(', ')}`));
      evidence.append(detail);
      const sources = el('ul', 'source-list');
      for (const source of item.evidence) { const row = el('li'); row.append(sourceReference(source)); sources.append(row); }
      if (sources.childNodes.length) evidence.append(sources);
      card.append(evidence);
      if (item.checklist.length) {
        const checklist = el('details'); checklist.append(el('summary', '', 'Placeholder reauthorization checklist'));
        const entries = el('ul'); for (const text of item.checklist) entries.append(el('li', '', text));
        checklist.append(entries); card.append(checklist);
      }
      $('worklist').append(card);
    }
  }
  function renderAllocation() {
    const patient = input.patients[selectedPatient], rule = input.payers[patient.primary_payer];
    $('selected-label').textContent = `${patient.display_name} · ${selectedPatient} · ${patient.clinic}`;
    $('ledger').replaceChildren();
    const ledgers = Object.values(output.ledgers).filter((l) => l.auth.patient_id === selectedPatient);
    if (!ledgers.length) $('ledger').append(el('p', 'help', rule && !rule.requires_auth
      ? 'This placeholder payer does not require authorization, so these visits do not enter the authorization ledger.'
      : 'There is no approved authorization ledger for this patient. Pending records do not supply approved capacity.'));
    for (const ledger of ledgers) {
      const a = ledger.auth, card = el('div', 'ledger-card'); card.dataset.auth = a.auth_no;
      const heading = el('div', 'ledger-title', a.auth_no);
      heading.append(el('span', '', `${a.start} – ${a.end} · ${a.visits_authorized} authorized`)); card.append(heading);
      const meter = el('div', 'ledger-meter'); meter.setAttribute('aria-hidden', 'true');
      for (const [name, value] of [['used', ledger.used.length], ['reserved', ledger.scheduled.length]]) {
        const segment = el('span', name); segment.style.width = `${a.visits_authorized ? value / a.visits_authorized * 100 : 0}%`; meter.append(segment);
      }
      card.append(meter);
      const counts = el('div', 'ledger-counts');
      for (const [name, value] of [['Completed', ledger.used.length], ['Scheduled reserved', ledger.scheduled.length], ['Unallocated left', ledger.remaining_after_scheduled]]) {
        const count = el('div', '', name); count.prepend(el('strong', '', String(value))); counts.append(count);
      }
      card.append(counts);
      const source = el('p', 'ledger-source'); source.append(sourceReference(a.source_row)); card.append(source);
      $('ledger').append(card);
    }
    const assigned = new Map();
    for (const ledger of Object.values(output.ledgers)) {
      for (const visit of [...ledger.used, ...ledger.scheduled]) assigned.set(visit.visit_id, ledger.auth.auth_no);
    }
    const uncovered = new Set(output.uncovered.map((v) => v.visit_id));
    const visits = input.visits.filter((v) => v.patient_id === selectedPatient).sort((a, b) => a.visit_date.localeCompare(b.visit_date) || a.visit_id.localeCompare(b.visit_id));
    $('visit-summary').textContent = `Inspect all ${visits.length} recorded visits and their allocation`;
    $('visit-allocations').replaceChildren();
    for (const visit of visits) {
      const row = el('li'); row.dataset.visit = visit.visit_id;
      const line = el('div', 'visit-line'), left = el('div');
      left.append(el('strong', '', visit.visit_date), el('small', '', visit.visit_id));
      const right = el('div');
      let allocation = assigned.get(visit.visit_id) ? `Assigned to ${assigned.get(visit.visit_id)}`
        : uncovered.has(visit.visit_id) ? 'No covering approved capacity'
          : !['completed', 'scheduled'].includes(visit.status) ? 'This status does not consume capacity'
            : rule && !rule.requires_auth ? 'Authorization not required by placeholder rule'
              : visit.visit_type === 'eval' && rule && !rule.counts_evals ? 'Evaluation excluded by placeholder rule' : 'Not assigned';
      right.append(el('span', uncovered.has(visit.visit_id) ? 'visit-uncovered' : '', allocation));
      const past = visit.status === 'scheduled' && visit.visit_date < input.as_of;
      right.append(el('small', '', `${visit.status}${past ? ' (past; status not inferred)' : ''} · ${visit.visit_type}`));
      line.append(left, right); row.append(line, sourceReference(visit.source_row)); $('visit-allocations').append(row);
    }
    $('payer-rules').replaceChildren();
    if (rule) {
      const list = el('ul', 'payer-rules');
      const values = [rule.payer_name, `Authorization required: ${rule.requires_auth ? 'yes' : 'no'}`,
        `Reauthorization visits-left threshold: ${rule.reauth_visits_before}`,
        `Reauthorization days-left threshold: ${rule.reauth_days_before}`,
        `Turnaround: ${rule.turnaround_days} calendar days`,
        `Calendar-year visit limit: ${rule.annual_visit_limit ?? 'none in the sample'}`,
        `Evaluations consume authorization capacity: ${rule.counts_evals ? 'yes' : 'no'}`];
      for (const value of values) list.append(el('li', '', value)); $('payer-rules').append(list);
    } else $('payer-rules').append(el('p', '', 'No payer rule exists for this ID. The worklist must preserve that uncertainty.'));
  }
  function render() {
    if (dirty) return;
    const edited = changes(); changedSources = new Set(edited.map((c) => c.source).filter(Boolean));
    const p1 = output.items.filter((i) => i.priority === 'P1').length;
    const p2 = output.items.filter((i) => i.priority === 'P2').length;
    const futureUncovered = output.uncovered.filter((v) => v.status === 'scheduled' && v.visit_date >= input.as_of).length;
    $('metrics').replaceChildren();
    for (const [kind, value, label] of [['p1', p1, 'P1 work items'], ['p2', p2, 'P2 work items'], ['uncovered', futureUncovered, 'Future visits without approved capacity']]) {
      const card = el('div', `metric ${kind}`); card.dataset.metric = kind;
      card.append(el('strong', '', String(value)), el('span', '', label)); $('metrics').append(card);
    }
    $('priority-change').textContent = `${highest(fixture.baseline, selectedPatient)} → ${highest(output, selectedPatient)}`;
    $('edit-count').textContent = `${edited.length} ${edited.length === 1 ? 'field changed' : 'fields changed'}`;
    $('changes').replaceChildren();
    if (!edited.length) $('changes').append(el('li', '', 'Original synthetic sample; no scenario changes.'));
    for (const change of edited) {
      const li = el('li', '', change.text + ' '); if (change.source) li.append(sourceReference(change.source)); $('changes').append(li);
    }
    const past = input.visits.filter((v) => v.status === 'scheduled' && v.visit_date < input.as_of).length;
    $('past-scheduled').hidden = past === 0;
    $('past-scheduled').textContent = `${past} recorded scheduled visit${past === 1 ? ' is' : 's are'} now in the past. These rows can still reserve capacity under the source engine; their attendance is not inferred.`;
    $('result-announcement').textContent = `Applied scenario as of ${input.as_of}: ${output.items.length} work items, ${p1} P1, ${p2} P2. ${futureUncovered} future visits lack approved capacity, including any visits relying on pending records.`;
    renderWorklist(); renderAllocation(); $('results').hidden = false;
  }
  function reset(preset = '') {
    input = clone(fixture.input); selectedPatient = preset === 'capacity' || !preset ? 'SYN-1002' : 'SYN-1001';
    selectedAuth = input.auths.findIndex((a) => a.patient_id === selectedPatient && a.status === 'approved');
    selectedVisit = earliestScheduled(selectedPatient);
    const auth = input.auths[selectedAuth], visit = input.visits[selectedVisit];
    if (preset === 'capacity') auth.visits_authorized = fixture.baseline.ledgers[auth.auth_no].used.length;
    if (preset === 'expiry') auth.end = model.shiftDate(visit.visit_date, -1);
    if (preset === 'date') visit.visit_date = model.shiftDate(auth.end, 1);
    output = model.evaluate(input); $('error').hidden = true; syncEditors(); render();
  }
  try {
    output = model.evaluate(input);
    if (canonical(output) !== canonical(fixture.baseline)) throw new Error('The bundled scenario does not match its Python baseline. Rebuild and qualify this artifact before use.');
    for (const patient of Object.values(input.patients)) option($('patient'), patient.patient_id, `${patient.display_name} · ${patient.patient_id}`);
    $('editor-fields').disabled = false;
    for (const id of ['try-capacity', 'try-expiry', 'try-date', 'reset']) $(id).disabled = false;
    $('editor-form').addEventListener('submit', applyEditors);
    for (const id of ['as-of', 'capacity', 'expiry', 'visit-date']) $(id).addEventListener('input', markDirty);
    $('patient').addEventListener('change', () => { selectedPatient = $('patient').value; selectedAuth = -1; selectedVisit = -1; syncEditors(); render(); });
    $('authorization').addEventListener('change', () => { selectedAuth = Number($('authorization').value); syncEditors(); });
    $('visit').addEventListener('change', () => { selectedVisit = Number($('visit').value); syncEditors(); });
    $('view').addEventListener('change', renderWorklist);
    $('try-capacity').addEventListener('click', () => reset('capacity'));
    $('try-expiry').addEventListener('click', () => reset('expiry'));
    $('try-date').addEventListener('click', () => reset('date'));
    $('reset').addEventListener('click', () => reset());
    syncEditors(); render();
  } catch (error) {
    $('editor-fields').disabled = true;
    for (const id of ['try-capacity', 'try-expiry', 'try-date', 'reset']) $(id).disabled = true;
    $('results').hidden = true; $('error').textContent = error.message; $('error').hidden = false;
    $('result-announcement').textContent = 'The demo did not initialize. No worklist is being presented.';
  }
}
