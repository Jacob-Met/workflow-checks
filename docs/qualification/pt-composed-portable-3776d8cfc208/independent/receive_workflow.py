#!/usr/bin/env python3
"""Independent five-child composed CLI receiving; no product imports."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

PINS = {
    '__init__.py': 'a6f4545ac17e2578317ef694f7bb548489f6c71c',
    '__main__.py': '07cf8abb5a559054d4487c65a3f9f7c992067cf5',
    'data.py': '886b2d75050f302acb101ab4f5bf8473b7573b8f',
    'engine.py': '39c97f35d61ff949b5c2381f0ad60d7af8d74226',
    'report.py': '2ce82b1712e5c6fc03374d38996eceddf31782f0',
    'synth.py': '2ff6a2548bf55a812cfa62e397442a0d3f7debbb',
    'uncovered.py': '9ab21781c4116dd0b9b76ac0116868898f3ee7d4',
    'web.py': '7e5d38f4cf8c33f4b9c91bd3c3d929fcfa0f80b3',
    'worklist_calendar.py': 'e125f9ed77343fcc3d82e6d6f25a7296b0463aa7',
}
AS_OF = '2026-10-14'
IDS = ['SYN-' + str(n) for n in range(1001, 1007)]


def identity(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(),
            'git_blob': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(),
            'mtime_ns': path.stat().st_mtime_ns}


def inventory(root):
    return [dict(identity(p), relative_path=p.relative_to(root).as_posix())
            for p in sorted(root.rglob('*')) if p.is_file()]


def text_value(value):
    """Decode the iCalendar TEXT escape grammar, rejecting unknown escapes."""
    out = []
    i = 0
    while i < len(value):
        c = value[i]
        i += 1
        if c == '\\':
            if i == len(value) or value[i] not in '\\,;nN':
                raise ValueError('Unexpected iCalendar TEXT escape')
            c = '\n' if value[i] in 'nN' else value[i]
            i += 1
        out.append(c)
    return ''.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source-dir', type=Path, required=True)
    ap.add_argument('--cli-git', required=True)
    ap.add_argument('--output-dir', type=Path, required=True)
    args = ap.parse_args()
    source = args.source_dir.resolve(strict=True)
    pins = dict(PINS, **{'cli.py': args.cli_git})
    if not re.fullmatch('[0-9a-f]{40}', args.cli_git):
        raise ValueError('Exact resolved CLI identity required')
    paths = [source / 'ptauth' / n for n in sorted(pins)]
    for p in paths:
        if identity(p)['git_blob'] != pins[p.name]:
            raise ValueError('Source identity refused: ' + p.name)
    stage = args.output_dir.absolute()
    stage.mkdir(mode=0o700)
    watched = paths + [Path(__file__).resolve(), Path(__file__).with_name('PROTOCOL.md').resolve()]
    before = [identity(p) for p in watched]
    checks, children, expectations = [], [], {}
    data, report = stage / 'generated-data', stage / 'saved-report'
    data_before = report_before = ordinary_before = None
    ordinary = stage / 'ordinary-雪.ics'

    def check(name, ok):
        checks.append({'name': name, 'passed': bool(ok)})
        if not ok:
            raise AssertionError(name)

    def run(name, argv, closed=False):
        env = os.environ.copy()
        env.pop('PYTHONUNBUFFERED', None)
        env.pop('PYTHONPATH', None)
        env['PYTHONIOENCODING'] = 'utf-8:strict'
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        command = [sys.executable, '-B', '-m', 'ptauth', *argv]
        fd = None
        if closed:
            read_fd, fd = os.pipe()
            os.close(read_fd)
        wall_before = datetime.now(timezone.utc).replace(microsecond=0)
        started = time.monotonic_ns()
        try:
            child = subprocess.Popen(command, cwd=source, env=env, stdin=subprocess.DEVNULL,
                                     stdout=fd if closed else subprocess.PIPE, stderr=subprocess.PIPE)
        finally:
            if fd is not None:
                os.close(fd)
        timed_out = False
        try:
            out, err = child.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            timed_out = True
            child.kill()
            out, err = child.communicate(timeout=5)
        wall_after = datetime.now(timezone.utc).replace(microsecond=0)
        out = out or b''
        (stage / (name + '.stdout')).write_bytes(out)
        (stage / (name + '.stderr')).write_bytes(err)
        rec = {'name': name, 'command': command, 'pid': child.pid,
               'exit': child.returncode, 'timed_out': timed_out, 'reaped': child.poll() is not None,
               'elapsed_ns': time.monotonic_ns() - started,
               'utc_before': wall_before.isoformat(), 'utc_after': wall_after.isoformat()}
        children.append(rec)
        check(name + '.bounded_reaped', not timed_out and rec['reaped'])
        return rec, out, err

    def calendar(name, output, expected_rows, context, rec):
        raw = output.read_bytes()
        check(name + '.complete_envelope', raw.startswith(b'BEGIN:VCALENDAR\r\n') and
              raw.endswith(b'END:VCALENDAR\r\n'))
        physical = raw[:-2].split(b'\r\n')
        check(name + '.CRLF_and_fold_bounds', all(b'\n' not in p and b'\r' not in p and len(p) <= 75 for p in physical))
        for p in physical:
            p.decode('utf-8')
        logical = raw.replace(b'\r\n ', b'').decode('utf-8').split('\r\n')
        events = []
        event = None
        for line in logical:
            if line == 'BEGIN:VEVENT':
                if event is not None:
                    raise ValueError('Nested event')
                event = {}
            elif line == 'END:VEVENT':
                if event is None:
                    raise ValueError('Unmatched event end')
                events.append(event)
                event = None
            elif event is not None:
                field, value = line.split(':', 1)
                if field in event:
                    raise ValueError('Duplicate event field')
                event[field] = value
        check(name + '.event_count_order', event is None and len(events) == len(expected_rows))
        required = {'UID', 'DTSTAMP', 'DTSTART;VALUE=DATE', 'SUMMARY', 'DESCRIPTION', 'TRANSP'}
        for i, (ev, row) in enumerate(zip(events, expected_rows)):
            key = name + '.event' + str(i)
            check(key + '.fields', set(ev) == required and ev['TRANSP'] == 'TRANSPARENT')
            uid_payload = ['ptauth-submit-by-v1', row['key'], row['clinic'], row['auth_end'], 'UTC']
            uid = hashlib.sha256(json.dumps(uid_payload, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
            check(key + '.identity_date', ev['UID'] == uid + '@ptauth.workflow-checks.invalid' and
                  ev['DTSTART;VALUE=DATE'] == row['submit_by'].replace('-', ''))
            check(key + '.literal_summary', text_value(ev['SUMMARY']) ==
                  f"[SYNTHETIC] {row['priority']} authorization review — {row['patient_id']}")
            description = text_value(ev['DESCRIPTION']).split('\n')
            expected_lines = [context['banner'], 'Work-item key: ' + row['key'],
                f"Patient: {row['patient_id']} — {row['patient_name']}",
                f"Payer: {row['payer_id']} — {row['payer_name']}",
                'Authorization: ' + row['auth_no'], 'Clinic: ' + row['clinic'],
                'Priority: ' + row['priority'], 'Recorded submit-by: ' + row['submit_by'],
                'Staff state: open', 'Report as of: ' + AS_OF,
                'Report generated at (as recorded): ' + context['generated_at'],
                'Clinic time zone (context; all-day date unchanged): UTC',
                *row['reasons'], *row['detail'], *row['checklist'], *row['evidence']]
            check(key + '.literal_saved_values', all(x in description for x in expected_lines))
            check(key + '.runtime_stamp_syntax', bool(re.fullmatch(r'\d{8}T\d{6}Z', ev['DTSTAMP'])))
            stamp = datetime.strptime(ev['DTSTAMP'], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
            check(key + '.runtime_stamp_interval', datetime.fromisoformat(rec['utc_before']) <= stamp <= datetime.fromisoformat(rec['utc_after']))
        return events

    failure = None
    try:
        rec, out, err = run('generate', ['generate', '--out', str(data), '--patients', '6', '--seed', '53', '--as-of', AS_OF])
        check('generate.exit_and_marker', rec['exit'] == 0 and err == b'' and b'SYNTHETIC' in out)
        with (data / 'patients.csv').open(newline='', encoding='utf-8') as stream:
            patients = list(csv.DictReader(stream))
        check('generate.six_literal_ids', [p['patient_id'] for p in patients] == IDS)
        patient_by_id = {p['patient_id']: p for p in patients}
        data_before = inventory(data)
        rec, out, err = run('run', ['run', '--data', str(data), '--out', str(report), '--as-of', AS_OF, '--clinic-timezone', 'UTC'])
        check('run.exit', rec['exit'] == 0 and err == b'')
        summary = json.loads((report / 'summary.json').read_bytes())
        rows = summary['worklist']
        check('run.fixed_context', summary['as_of'] == AS_OF and summary['clinic_timezone'] == 'UTC' and summary['counts']['patients'] == 6)
        check('run.report_shape', bool(rows) and summary['counts']['worklist'] == len(rows) and len({x['key'] for x in rows}) == len(rows))
        check('run.CSV_identity_mapping', all(x['patient_id'] in patient_by_id and x['patient_name'] == patient_by_id[x['patient_id']]['display_name'] and x['clinic'] == patient_by_id[x['patient_id']]['clinic'] for x in rows))
        check('run.no_staff_state_created', not (report / 'work_state.json').exists())
        included = [x for x in rows if x['submit_by'] is not None]
        excluded = [{'key': x['key'], 'patient_id': x['patient_id'], 'state': 'open', 'reasons': ['undated']}
                    for x in rows if x['submit_by'] is None]
        check('run.at_least_one_dated_item', bool(included))
        snapshot = hashlib.sha256(json.dumps(dict(summary, states={}), ensure_ascii=False, sort_keys=True,
                                            separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        expectations.update({'source_report': identity(report / 'summary.json'),
            'selected_keys': [x['key'] for x in rows], 'included_keys': [x['key'] for x in included],
            'excluded': excluded, 'snapshot': snapshot, 'as_of': AS_OF, 'clinic_timezone': 'UTC'})
        report_before = inventory(report)
        rec, out, err = run('calendar', ['calendar', '--report', str(report), '--output', str(ordinary)])
        check('calendar.exit', rec['exit'] == 0 and err == b'')
        check('calendar.one_JSON_LF', out.endswith(b'\n') and out.count(b'\n') == 1)
        expected = {'format': 'ptauth-submit-by-v1', 'snapshot': snapshot, 'as_of': AS_OF,
            'clinic_timezone': 'UTC', 'selected': len(rows), 'events': len(included), 'excluded': excluded,
            'undated': len(excluded), 'completed_state': 0, 'output': str(ordinary)}
        check('calendar.exact_receipt', json.loads(out) == expected)
        ordinary_events = calendar('calendar', ordinary, included, summary, rec)
        ordinary_before = identity(ordinary)
        check('calendar.report_unchanged', inventory(report) == report_before)
        rec, out, err = run('invalid-date', ['run', '--data', str(data), '--out', str(report), '--as-of', 'not-a-date', '--clinic-timezone', 'UTC'])
        check('invalid-date.handled_refusal', rec['exit'] == 2 and out == b'' and err and b'Traceback' not in err)
        check('invalid-date.entire_report_preserved', inventory(report) == report_before)
        closed_output = stage / 'closed-receipt-雪.ics'
        rec, out, err = run('closed-calendar', ['calendar', '--report', str(report), '--output', str(closed_output)], closed=True)
        check('closed-calendar.handled_receipt_failure', rec['exit'] == 2 and out == b'' and
              b'created' in err.lower() and b'receipt' in err.lower() and b'Traceback' not in err and b'Exception ignored' not in err)
        closed_events = calendar('closed-calendar', closed_output, included, summary, rec)
        without_stamp = lambda events: [{k: v for k, v in e.items() if k != 'DTSTAMP'} for e in events]
        check('closed-calendar.same_event_values', without_stamp(closed_events) == without_stamp(ordinary_events))
        check('no_calendar_staging_files', not list(stage.rglob('.ptauth-calendar-*')))
    except Exception as error:
        failure = type(error).__name__ + ': ' + str(error)
    after = [identity(p) for p in watched]
    checks.append({'name': 'twelve_source_receiver_records_preserved', 'passed': before == after})
    if data_before is not None:
        checks.append({'name': 'generated_inputs_preserved_after_generation', 'passed': data_before == inventory(data)})
    if report_before is not None:
        checks.append({'name': 'complete_report_preserved_after_single_run', 'passed': report_before == inventory(report)})
    if ordinary_before is not None:
        checks.append({'name': 'ordinary_calendar_preserved', 'passed': ordinary_before == identity(ordinary)})
    receipt = {'schema': 'ptauth.composed-workflow.independent/1', 'scope': 'One five-child fictional generated-data/report/calendar workflow, no product/helper oracle imports or prior matrix rerun',
        'source_before': before, 'source_after': after, 'generated_before': data_before,
        'generated_after': inventory(data) if data.exists() else [], 'report_before': report_before,
        'report_after': inventory(report) if report.exists() else [], 'expectations': expectations,
        'children': children, 'checks': checks, 'failure': failure,
        'passed': failure is None and len(children) == 5 and all(x['passed'] for x in checks)}
    (stage / 'receiving.json').write_text(json.dumps(receipt, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': receipt['passed'], 'checks': len(checks), 'children': len(children), 'receipt': str(stage / 'receiving.json')}))
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
