"""Historical independent, authored-data receiving review; no live data or routes."""
import csv
import hashlib
import io
import json
import shutil
import subprocess
import sys
import traceback
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AUTHOR = Path('/dev/shm/pt-uncovered-visits-dc13ebf4687f')
BASE = AUTHOR / 'baseline'
CAND = AUTHOR / 'candidate'
HEAD = '9676a5a20f3adab0ccf46e31e3052de04f50d267'
PRE = 'd67c6087ab5fae717be2eec08f131d2c80b539f6'
PYTHON = '/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3'
receipt = {'kind': 'independent authored report/CLI comparison', 'checks': [], 'cli': []}


def require(ok, label):
    if not ok:
        raise RuntimeError(label)
    receipt['checks'].append(label)


def pin(path):
    raw = path.read_bytes()
    return {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
            'git_blob': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=CAND)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def write_csv(path, columns, rows):
    with path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.table, self.row, self.cell = [], None, None, None
        self.canaries = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if any(k == 'data-pt-canary' for k, v in attrs):
            self.canaries.append([tag, attrs])
        if tag == 'table': self.table = []
        elif tag == 'tr' and self.table is not None: self.row = []
        elif tag in ('td', 'th') and self.row is not None: self.cell = []
        elif tag == 'br' and self.cell is not None: self.cell.append('\n')

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(''.join(self.cell)); self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.table.append(self.row); self.row = None
        elif tag == 'table' and self.table is not None:
            self.tables.append(self.table); self.table = None

    def handle_data(self, text):
        self.text.append(text)
        if self.cell is not None: self.cell.append(text)


def main():
    require(pin(AUTHOR / 'baseline-manifest.json')['sha256'] ==
            '6390ba36accd23bd14edb6dbd1b943f1fb4a6fae2ce1a3786d5ddce3c80b761c',
            'exact 14-source baseline manifest')
    require(pin(AUTHOR / 'candidate-manifest.json')['sha256'] ==
            '46a503ccdd0c793cc1ad4ec1759e6d615c12c67e7aec8fad93cff2f55e8dadab',
            'exact seven-path candidate manifest')
    old = json.loads((AUTHOR / 'baseline-manifest.json').read_text())
    new = json.loads((AUTHOR / 'candidate-manifest.json').read_text())
    require(git('rev-parse', 'HEAD').decode().strip() == HEAD, 'frozen candidate HEAD')
    changed = {x['path']: x for x in new['changed_paths']}
    require(set(git('diff', '--name-only', PRE, HEAD).decode().splitlines()) == set(changed),
            'only seven declared paths changed')
    for row in old['files']:
        require(pin(BASE / row['path']) == {k: row[k] for k in ('size', 'sha256', 'git_blob')},
                'baseline exact: ' + row['path'])
    for rel, row in changed.items():
        require(pin(CAND / rel) == {k: row[k] for k in ('size', 'sha256', 'git_blob')},
                'candidate exact: ' + rel)
        if row['expected_old_git_blob']:
            require(git('rev-parse', PRE + ':' + rel).decode().strip() == row['expected_old_git_blob'],
                    'expected preimage: ' + rel)
        else:
            require(rel not in git('ls-tree', '-r', '--name-only', PRE).decode().splitlines(),
                    'new path absent: ' + rel)
    untouched = [x for x in old['files'] if x['path'] not in changed]
    for row in untouched:
        require((BASE / row['path']).read_bytes() == (CAND / row['path']).read_bytes(),
                'unchanged package/sample bytes: ' + row['path'])
    tracked = git('ls-tree', '-r', '--name-only', HEAD).decode().splitlines()
    source_before = {r: pin(CAND / r) for r in tracked}
    receipt['source'] = {'repository': old['repository'], 'upstream': old['head'],
        'tree': new['upstream_tree'], 'candidate': HEAD, 'partial_baseline': PRE,
        'changed': new['changed_paths'], 'unchanged': untouched,
        'instruction_tree_lookup': {'tree': new['upstream_tree'], 'truncated': False,
                                    'AGENTS_or_SKILL_files': []}}

    data = ROOT / 'authored-input'
    data.mkdir()
    patient_name = 'Zoë <b data-pt-canary="patient">雪</b> & "A"'
    payer_name = 'Known & <i data-pt-canary="payer">Plan</i>'
    u5 = 'U5-<b data-pt-canary="visit">雪</b>'
    u6 = 'U6,"quoted"'
    special_clinic = 'Visit-only & 雪\nFloor 2'
    therapist = 'Therapist "Q", Ω'
    patients = [dict(patient_id='PT-A', display_name=patient_name, clinic='Home clinic not visit', primary_payer='PAY-A'),
                dict(patient_id='PT-B', display_name='Covered control', clinic='Home control', primary_payer='PAY-A'),
                dict(patient_id='PT-C', display_name='', clinic='Home C', primary_payer='PAY-A')]
    payers = [dict(payer_id='PAY-A', payer_name=payer_name, requires_auth='Y', reauth_visits_before='0',
                  reauth_days_before='0', turnaround_days='0', annual_visit_limit='', counts_evals='Y', checklist='Auth record|Visit record'),
              dict(payer_id='PAY-FREE', payer_name='No-auth control', requires_auth='N', reauth_visits_before='0',
                  reauth_days_before='0', turnaround_days='0', annual_visit_limit='', counts_evals='Y', checklist='')]
    auths = [dict(auth_no='OLD-A', patient_id='PT-A', payer_id='PAY-A', visits_authorized='2', start_date='2026-09-01', end_date='2026-09-30', status='approved'),
             dict(auth_no='COVER-B', patient_id='PT-B', payer_id='PAY-A', visits_authorized='2', start_date='2026-10-01', end_date='2026-11-30', status='approved')]
    def v(visit_id, date, clinic='Satellite', status='scheduled', patient='PT-A', payer='PAY-A', kind='treatment'):
        return dict(visit_id=visit_id, patient_id=patient, visit_date=date, clinic=clinic,
                    therapist=therapist, payer_id=payer, status=status, visit_type=kind)
    visits = [v(u6, '2026-10-13', special_clinic, kind='re-eval'),
              v('D-FUTURE', '2026-10-22', 'South', status='completed'),
              v('U3', '2026-10-10', ''),
              v('P-PAST', '2026-10-08T00:30:00+02:00', 'Status-only'),
              v('U1', '2026-10-08'),
              v('FREE', '2026-10-12', 'No-auth clinic', patient='PT-C', payer='PAY-FREE'),
              v(u5, '2026-10-12', 'South'),
              v('D-PAST', '2026-10-01', 'Satellite', status='completed'),
              v('U4', '2026-10-11', 'South'),
              v('CANCELLED', '2026-10-09', status='cancelled'),
              v('U2', '2026-10-09', 'South'),
              v('UNKNOWN', '2026-10-14', 'Unknown clinic', patient='PT-C', payer='PAY-MISSING'),
              v('COVERED', '2026-10-10', 'Covered clinic', patient='PT-B'),
              v('NO-SHOW', '2026-10-11', status='no_show')]
    datasets = {'patients.csv': patients, 'payers.csv': payers, 'authorizations.csv': auths, 'schedule.csv': visits}
    for name, rows in datasets.items(): write_csv(data / name, list(rows[0]), rows)
    fixture_pins = {name: pin(data / name) for name in datasets}
    raw_rows = []
    with (data / 'schedule.csv').open(newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader: raw_rows.append((row, reader.line_num))
    require(raw_rows[0][1] == 3 and raw_rows[-1][1] == 16,
            'embedded source newline has physical line evidence 3 through 16')
    include = {u6, u5, 'U1', 'U2', 'U3', 'U4', 'D-FUTURE', 'D-PAST', 'UNKNOWN'}
    expected = []
    for row, physical_line in raw_rows:
        if row['visit_id'] not in include: continue
        expected.append(dict(visit_id=row['visit_id'], visit_date=row['visit_date'], status=row['status'],
            patient_id=row['patient_id'], patient_name=patient_name if row['patient_id'] == 'PT-A' else '',
            clinic=row['clinic'], therapist=row['therapist'], payer_id=row['payer_id'],
            payer_name=payer_name if row['payer_id'] == 'PAY-A' else '',
            payer_rules_known=row['payer_id'] == 'PAY-A', visit_type=row['visit_type'],
            evidence='schedule.csv:row' + str(physical_line)))
    expected.sort(key=lambda x: (x['visit_date'], x['patient_id'], x['payer_id'], x['visit_id'], x['evidence']))
    write_json(ROOT / 'expected-rows.json', expected)
    state = {'PT-A|PAY-A|OLD-A': {'state': 'approved', 'note': 'Authored staff note: 雪 & "unchanged"', 'at': '2026-10-07T09:00:00+00:00'}}
    state_bytes = (json.dumps(state, indent=2, ensure_ascii=False) + '\n').encode()

    def run_cli(label, source, data_dir):
        out = ROOT / (label + '-output'); out.mkdir()
        (out / 'work_state.json').write_bytes(state_bytes)
        cmd = [PYTHON, '-B', '-m', 'ptauth', 'run', '--data', str(data_dir), '--out', str(out),
               '--as-of', '2026-10-08', '--clinic-timezone', 'UTC']
        result = subprocess.run(cmd, cwd=source / 'pt_auth', capture_output=True, text=True, timeout=10)
        receipt['cli'].append({'label': label, 'argv': cmd, 'cwd': str(source / 'pt_auth'),
                               'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
        require(result.returncode == 0, label + ' actual CLI succeeds')
        require((out / 'work_state.json').read_bytes() == state_bytes, label + ' staff state bytes survive report run')
        return out, json.loads((out / 'summary.json').read_text())

    base_out, before = run_cli('baseline', BASE, data)
    cand_out, after = run_cli('candidate', CAND, data)
    require(before['counts']['visits'] == 14 and before['counts']['uncovered_scheduled'] == 7
            and before['counts']['unauthorized_done'] == 2 and before['counts']['past_scheduled'] == 1,
            'authored independent matrix is 14 visits, 7 scheduled + 2 completed + 1 separate status review')
    require(len(before['uncovered']) == 10, 'raw uncovered retains separate past-scheduled tenth row')
    require(after['uncovered_review'] == expected, 'all twelve fields of all nine review rows match independent CSV expectations')
    require(len(before['visit_status_review']) == 1 and before['visit_status_review'][0]['visit_id'] == 'P-PAST'
            and before['visit_status_review'][0]['visit_date'] == '2026-10-07', 'offset timestamp remains UTC past-status review only')
    require({k: v for k, v in after.items() if k not in ('generated_at', 'uncovered_review', 'uncovered_review_note')} ==
            {k: v for k, v in before.items() if k != 'generated_at'}, 'all existing summary fields and counts unchanged')
    preserved_outputs = {}
    for filename in ('worklist.csv', 'ledger.csv', 'visit_status_review.csv'):
        require((base_out / filename).read_bytes() == (cand_out / filename).read_bytes(), 'existing output bytes unchanged: ' + filename)
        preserved_outputs[filename] = pin(cand_out / filename)
    old_audit = json.loads((base_out / 'audit.jsonl').read_text()); new_audit = json.loads((cand_out / 'audit.jsonl').read_text())
    require({k:v for k,v in old_audit.items() if k != 'ts'} == {k:v for k,v in new_audit.items() if k != 'ts'},
            'existing audit run facts unchanged except clock timestamp')
    with (cand_out / 'uncovered_visits.csv').open(newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh); csv_rows = list(reader); columns = reader.fieldnames
    require(columns == list(expected[0]), 'documented twelve CSV columns in exact order')
    require(csv_rows == [{k:str(v) for k,v in row.items()} for row in expected],
            'full CSV roundtrip preserves Unicode/HTML/commas/quotes/newline/blank names/False')
    require('9 uncovered visits to inspect: ' + str(cand_out / 'uncovered_visits.csv') in receipt['cli'][1]['stdout'],
            'actual CLI exposes new complete CSV path and count')
    old_digest = (base_out / 'digest.html').read_text(); new_digest = (cand_out / 'digest.html').read_text()
    a = new_digest.index('<h2>Uncovered visits'); b = new_digest.index('<h2>Visit status review', a)
    require(new_digest[:a] + new_digest[b:] == old_digest, 'all original printable HTML bytes remain after removing additive review section')
    old_html = Tables(); old_html.feed(old_digest)
    new_html = Tables(); new_html.feed(new_digest)
    missing = [x for x in include if x not in ''.join(old_html.text)]
    require(set(missing) == {u5, u6}, 'baseline printable digest omits exactly later upcoming U5/U6')
    review_table = [t for t in new_html.tables if t and t[0] and t[0][0] == 'Visit / type']
    require(len(review_table) == 1 and [r[0].split('\n')[0] for r in review_table[0][1:]] == [x['visit_id'] for x in expected],
            'actual digest contains every ordered visit once in complete review table')
    require(not old_html.canaries and not new_html.canaries, 'literal HTML fields create no canary elements in either digest')
    empty_data = ROOT / 'empty-input'; empty_data.mkdir()
    for filename in ('patients.csv', 'payers.csv', 'authorizations.csv'): shutil.copyfile(data / filename, empty_data / filename)
    controls = [row for row in visits if row['visit_id'] in ('P-PAST', 'FREE', 'COVERED', 'CANCELLED', 'NO-SHOW')]
    write_csv(empty_data / 'schedule.csv', list(controls[0]), controls)
    empty_out, empty = run_cli('empty', CAND, empty_data)
    require(empty['uncovered_review'] == [] and empty['counts']['past_scheduled'] == 1,
            'real control-only CLI yields explicit empty review and separate status row')
    with (empty_out / 'uncovered_visits.csv').open(newline='', encoding='utf-8') as fh:
        require(list(csv.reader(fh)) == [columns], 'empty CSV retains full header only')
    require('No appointments are in this review for this report.' in (empty_out / 'digest.html').read_text(),
            'empty digest explicitly reports no review appointments')
    legacy_out = ROOT / 'legacy-output'; shutil.copytree(base_out, legacy_out)
    legacy_digest = ROOT / 'legacy-candidate-digest.html'
    render = "from pathlib import Path; import json,sys; from ptauth.report import render_digest; Path(sys.argv[2]).write_text(render_digest(json.loads(Path(sys.argv[1]).read_text())),encoding='utf-8')"
    result = subprocess.run([PYTHON, '-B', '-c', render, str(legacy_out / 'summary.json'), str(legacy_digest)],
                            cwd=CAND / 'pt_auth', capture_output=True, text=True, timeout=10)
    require(result.returncode == 0, 'candidate pure renderer reads authored legacy saved report')
    require('Run worklist to build uncovered-visit details for this saved report.' in legacy_digest.read_text()
            and 'No appointments are in this review for this report.' not in legacy_digest.read_text(),
            'legacy digest requests rerun instead of claiming empty review')
    require(source_before == {r: pin(CAND / r) for r in tracked}, 'every tracked candidate source byte unchanged after review')
    require(fixture_pins == {name: pin(data / name) for name in datasets}, 'authored input bytes unchanged')
    receipt.update({'accepted': True, 'baseline_missing_ids': sorted(missing), 'counts': after['counts'],
                    'raw_uncovered_count': 10, 'complete_review_count': 9, 'fixture_files': fixture_pins,
                    'expected_rows': expected, 'unchanged_csv': preserved_outputs,
                    'new_csv': pin(cand_out / 'uncovered_visits.csv'), 'source_after': source_before,
                    'limits': ['Authored inputs only; no clinical/provider/account data.',
                               'No clinical decision, payer compliance, or browser-layout qualification in this script.',
                               'Three actual CLI invocations and one pure legacy-renderer process; no inherited suite.']})
    write_json(ROOT / 'browser-input.json', {'baseline': str(BASE / 'pt_auth'), 'candidate': str(CAND / 'pt_auth'),
        'data': str(data), 'empty_data': str(empty_data), 'outputs': {k:str(ROOT / (k + '-output')) for k in ('baseline','candidate','empty','legacy')},
        'expected': expected, 'state': state, 'special_clinic': special_clinic, 'u5': u5, 'u6': u6,
        'patient_name': patient_name, 'payer_name': payer_name, 'therapist': therapist})


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        receipt.update(accepted=False, error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        write_json(ROOT / 'report-receipt.json', receipt)
        print(json.dumps({'accepted': receipt.get('accepted'), 'checks': len(receipt['checks']),
                          'cli_processes': len(receipt['cli']), 'receipt': str(ROOT / 'report-receipt.json')}))
