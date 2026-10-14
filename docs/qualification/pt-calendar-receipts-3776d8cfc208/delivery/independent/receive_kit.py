"""One independent ordinary CLI receiving of the actual delivered calendar kit."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import signal
import stat
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone

SOURCE = '1bd30de4cecff7ee7564dccadf53561f3e21c284'
PROTOCOL = '2dd96e8350f4582296056a5d7c3513ceb0e72579'
PINS = {
    'ptauth/__init__.py': 'a6f4545ac17e2578317ef694f7bb548489f6c71c',
    'ptauth/__main__.py': '07cf8abb5a559054d4487c65a3f9f7c992067cf5',
    'ptauth/cli.py': 'b1b7a60de7b470ea59de6313bfcde336f1c5dfe1',
    'ptauth/worklist_calendar.py': 'e125f9ed77343fcc3d82e6d6f25a7296b0463aa7',
    'CALENDAR_RECEIPTS.md': 'a4a55efba02796069bbd974ab2d9de3060da5428',
}
ORACLES = {
    'summary.json': 'a78876985055972f122725366a19ba8c9735ee1d',
    'work_state.json': '091cf6cf96601fd5988e2f78dc119844a97343d0',
    'prior-calendar.ics': 'e6c6dd73e470ab29d8f6baa9c8d032e4f41fae8e',
    'prior-receipt.json': 'ae5ca5f2557d7505045ac71c23ddb85f33b9f9ee',
}
MEMBERS = sorted(['MANIFEST.json', 'pt_auth/SOURCE_MANIFEST.json',
                  'pt_auth/START_HERE.md'] + ['pt_auth/' + p for p in PINS])
STAMP = re.compile(rb'(?m)^DTSTAMP:([0-9]{8}T[0-9]{6}Z)\r\n')

def git(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()

def identity(path):
    raw = path.read_bytes()
    st = path.stat()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
            'git_blob': git(raw), 'mtime_ns': str(st.st_mtime_ns)}

def snapshot(paths):
    return [identity(p) for p in paths]

def strict_json(raw):
    def pairs(values):
        result = {}
        for k, v in values:
            if k in result:
                raise ValueError('Duplicate JSON key: ' + k)
            result[k] = v
        return result
    def bad(value):
        raise ValueError('Non-finite JSON: ' + value)
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=bad)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zip', required=True, type=Path)
    ap.add_argument('--zip-bytes', required=True, type=int)
    ap.add_argument('--zip-sha256', required=True)
    ap.add_argument('--zip-git', required=True)
    ap.add_argument('--output', required=True, type=Path)
    a = ap.parse_args()
    here = Path(__file__).resolve().parent
    archive = a.zip.resolve()
    output = a.output.absolute()
    protocol = here / 'PROTOCOL.md'
    oracle_paths = [here / 'oracle' / n for n in ORACLES]
    assert sys.version_info >= (3, 10) and sys.platform == 'linux'
    assert git(protocol.read_bytes()) == PROTOCOL
    for name, pin in ORACLES.items():
        assert git((here / 'oracle' / name).read_bytes()) == pin, name
    raw = archive.read_bytes()
    assert 0 < len(raw) <= 1024 * 1024 and len(raw) == a.zip_bytes
    assert hashlib.sha256(raw).hexdigest() == a.zip_sha256 and git(raw) == a.zip_git
    original_paths = [archive, Path(__file__).resolve(), protocol, *oracle_paths]
    original_before = snapshot(original_paths)
    output.mkdir(mode=0o700)
    receipt = {
        'schema': 'pt.calendar-kit.independent-receiving/1',
        'source_commit': SOURCE, 'protocol_blob': PROTOCOL,
        'runtime': {'executable': sys.executable, 'version': sys.version,
                    'platform': platform.platform(), 'host': platform.node()},
        'archive': identity(archive), 'output': str(output),
        'checks': [], 'original_before': original_before,
        'scope': 'One ordinary extracted calendar command from fictional saved input. No installer, engine generation, web server, five-process matrix or external calendar invocation.',
    }
    child = None
    watched = None
    before = None
    def check(name, condition, detail=None):
        receipt['checks'].append({'name': name, 'passed': bool(condition),
                                  **({'detail': detail} if detail is not None else {})})
        if not condition:
            raise AssertionError(name)
    try:
        with zipfile.ZipFile(archive) as z:
            infos = z.infolist()
            check('exact_eight_unique_members', sorted(i.filename for i in infos) == MEMBERS)
            check('bounded_regular_members', sum(i.file_size for i in infos) <= 2 * 1024 * 1024 and
                  all(not i.is_dir() and not i.flag_bits & 1 and
                      not PurePosixPath(i.filename).is_absolute() and
                      '..' not in PurePosixPath(i.filename).parts and '\\' not in i.filename and
                      not stat.S_ISLNK(i.external_attr >> 16) and
                      stat.S_IFMT(i.external_attr >> 16) in (0, stat.S_IFREG) for i in infos))
            payload = {i.filename: z.read(i) for i in infos}
        manifest = strict_json(payload['MANIFEST.json'])
        check('root_manifest_schema', set(manifest) == {'schema', 'files'} and
              manifest['schema'] == 'hamon.delivery-zip/1')
        records = manifest['files']
        check('root_manifest_inventory', isinstance(records, list) and
              [r['path'] for r in records] == [n for n in MEMBERS if n != 'MANIFEST.json'])
        check('root_manifest_payload_bytes', all(set(r) == {'path', 'bytes', 'sha256'} and
              type(r['bytes']) is int and r['bytes'] == len(payload[r['path']]) and
              r['sha256'] == hashlib.sha256(payload[r['path']]).hexdigest() for r in records))
        sm = strict_json(payload['pt_auth/SOURCE_MANIFEST.json'])
        check('source_manifest_schema_and_draft', set(sm) == {'schema', 'source_commit', 'publication_status', 'files', 'scope'} and
              sm['schema'] == 'pt.calendar-receipts.source/1' and sm['source_commit'] == SOURCE and
              sm['publication_status'] == 'reviewed-draft-not-main')
        sf = sm['files']
        check('source_manifest_inventory', isinstance(sf, list) and
              [r['path'] for r in sf] == sorted([*PINS, 'START_HERE.md']))
        for r in sf:
            b = payload['pt_auth/' + r['path']]
            check('source_payload_' + r['path'], type(r['bytes']) is int and
                  r['bytes'] == len(b) and r['sha256'] == hashlib.sha256(b).hexdigest() and r['git_blob'] == git(b))
            if r['path'] in PINS:
                check('independent_lineage_' + r['path'], set(r) == {'path', 'bytes', 'sha256', 'git_blob', 'origin', 'source_commit', 'source_path'} and
                      r['origin'] == 'reviewed-draft-source' and r['source_commit'] == SOURCE and
                      r['source_path'] == 'pt_auth/' + r['path'] and git(b) == PINS[r['path']])
            else:
                check('delivery_note_identity', set(r) == {'path', 'bytes', 'sha256', 'git_blob', 'origin'} and
                      r['origin'] == 'delivery-note' and bool(b.strip()))
        extracted = output / 'extracted'
        extracted.mkdir()
        for name in MEMBERS:
            target = extracted / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as f:
                f.write(payload[name])
        report = output / 'saved-report'
        report.mkdir()
        for name in ['summary.json', 'work_state.json']:
            with (report / name).open('xb') as f:
                f.write((here / 'oracle' / name).read_bytes())
        extracted_paths = [extracted / n for n in MEMBERS]
        watched = [*original_paths, *extracted_paths, report / 'summary.json', report / 'work_state.json']
        before = snapshot(watched)
        receipt['before'] = before
        destination = output / 'calendar-雪.ics'
        argv = [sys.executable, '-B', '-m', 'ptauth', 'calendar', '--report', str(report), '--output', str(destination)]
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
        env['PYTHONNOUSERSITE'] = '1'
        start_ns = time.time_ns()
        with (output / 'calendar.stdout').open('xb') as out, (output / 'calendar.stderr').open('xb') as err:
            child = subprocess.Popen(argv, cwd=extracted / 'pt_auth', env=env,
                                     stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                     start_new_session=True)
            timed_out = False
            try:
                returncode = child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(child.pid, signal.SIGKILL)
                returncode = child.wait(timeout=10)
        end_ns = time.time_ns()
        receipt['child'] = {'argv': argv, 'cwd': str(extracted / 'pt_auth'), 'pid': child.pid,
                            'returncode': returncode, 'timed_out': timed_out, 'reaped': child.poll() is not None,
                            'start_utc_ns': str(start_ns), 'end_utc_ns': str(end_ns)}
        stdout = (output / 'calendar.stdout').read_bytes()
        stderr = (output / 'calendar.stderr').read_bytes()
        check('one_child_normal_success', returncode == 0 and not timed_out and child.poll() is not None)
        check('empty_stderr', stderr == b'')
        check('one_ascii_json_receipt_with_lf', stdout.endswith(b'\n') and stdout.count(b'\n') == 1 and stdout.isascii())
        expected = strict_json((here / 'oracle/prior-receipt.json').read_bytes())
        expected['output'] = str(destination)
        actual = strict_json(stdout)
        check('receipt_exact_except_intentional_output_path', actual == expected)
        check('literal_counts_dates_and_exclusion', actual['selected'] == 2 and actual['events'] == 1 and
              actual['undated'] == 1 and actual['completed_state'] == 1 and
              actual['as_of'] == '2026-10-14' and actual['clinic_timezone'] == 'Europe/Paris' and
              actual['excluded'] == [{'key': 'SYN-010|PAYER-雪|AUTH-8', 'patient_id': 'SYN-010', 'state': 'approved', 'reasons': ['undated', 'completed_state']}])
        calendar = destination.read_bytes()
        prior = (here / 'oracle/prior-calendar.ics').read_bytes()
        stamps = STAMP.findall(calendar)
        check('one_valid_utc_export_stamp', len(stamps) == 1 and len(STAMP.findall(prior)) == 1)
        when = datetime.strptime(stamps[0].decode('ascii'), '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        check('export_stamp_in_invocation_interval', math.floor(start_ns / 1e9) <= when.timestamp() <= math.ceil(end_ns / 1e9))
        check('all_other_calendar_wire_bytes_exact', STAMP.sub(b'DTSTAMP:<dynamic-UTC>\r\n', calendar) == STAMP.sub(b'DTSTAMP:<dynamic-UTC>\r\n', prior))
        check('literal_single_event_date_and_transparency', calendar.count(b'BEGIN:VEVENT\r\n') == 1 and
              calendar.count(b'END:VEVENT\r\n') == 1 and b'DTSTART;VALUE=DATE:20261020\r\n' in calendar and
              b'TRANSP:TRANSPARENT\r\n' in calendar and calendar.endswith(b'END:VCALENDAR\r\n'))
        check('utf8_crlf_and_octet_folding', len(calendar.decode('utf-8')) > 0 and
              b'\n' not in calendar.replace(b'\r\n', b'') and
              all(len(line) <= 75 for line in calendar.split(b'\r\n')))
        receipt['calendar'] = {**identity(destination), 'dtstamp': stamps[0].decode('ascii')}
        receipt['receipt_document'] = actual
        check('extracted_members_unchanged_inventory', sorted(str(p.relative_to(extracted)) for p in extracted.rglob('*') if p.is_file()) == MEMBERS)
        check('report_directory_only_two_original_files', sorted(p.name for p in report.iterdir()) == ['summary.json', 'work_state.json'])
        check('one_application_output_only', sorted(p.name for p in output.iterdir()) == ['calendar-雪.ics', 'calendar.stderr', 'calendar.stdout', 'extracted', 'saved-report'])
    except BaseException as exc:
        receipt['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=10)
            except BaseException as exc:
                receipt['cleanup_error'] = repr(exc)
        try:
            after = snapshot(watched if watched is not None else original_paths)
            receipt['after'] = after
            receipt['checks'].append({'name': 'all_watched_bytes_and_native_ns_exact',
                                      'passed': after == (before if before is not None else original_before)})
        except BaseException as exc:
            receipt['custody_error'] = repr(exc)
        receipt['passed'] = not any(k in receipt for k in ['error', 'cleanup_error', 'custody_error']) and all(c['passed'] for c in receipt['checks'])
        with (output / 'receiving.json').open('x', encoding='utf-8') as f:
            json.dump(receipt, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print(json.dumps({'output': str(output), 'passed': receipt['passed'], 'checks': len(receipt['checks']), 'error': receipt.get('error')}))
    return 0 if receipt['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
