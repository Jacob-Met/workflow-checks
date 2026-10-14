"""One exact composed-kit receiving command; no source imports in the oracle."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import signal
import stat
import subprocess
import sys
import time
import zipfile

PROTOCOL = 'e4a0ecb985e05bfe92fbbfa9ee965e2548b83ac3'
EXPECTED = '6a99d4d3a93981a03270418cd7de71b43e72cd4f'
SOURCE = '69f3c8e0577b579ee36256da0a075fccb201af8f'

def git(b):
    return hashlib.sha1(b'blob ' + str(len(b)).encode() + b'\0' + b).hexdigest()

def identity(p):
    assert stat.S_ISREG(p.lstat().st_mode), str(p)
    b = p.read_bytes()
    return {'path': str(p), 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest(),
            'git_blob': git(b), 'mtime_ns': str(p.stat().st_mtime_ns)}

def strict(raw):
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d:
                raise ValueError('duplicate key')
            d[k] = v
        return d
    def bad(value):
        raise ValueError('nonfinite value: ' + value)
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=bad)

def rows(p):
    with p.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))

def csv_equal(actual, expected):
    return actual == [{k: '' if v is None else str(v) for k, v in row.items()} for row in expected]

def inventory(p):
    return sorted(str(x.relative_to(p)) for x in p.rglob('*') if x.is_file() or x.is_symlink())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zip', required=True, type=Path)
    ap.add_argument('--zip-bytes', required=True, type=int)
    ap.add_argument('--zip-sha256', required=True)
    ap.add_argument('--zip-git', required=True)
    ap.add_argument('--output', required=True, type=Path)
    a = ap.parse_args()
    assert sys.platform == 'linux' and sys.version_info >= (3, 10)
    here = Path(__file__).resolve()
    protocol, expected_path = here.with_name('PROTOCOL.md'), here.with_name('expected.json')
    assert git(protocol.read_bytes()) == PROTOCOL and git(expected_path.read_bytes()) == EXPECTED
    expected = strict(expected_path.read_bytes())
    assert expected['source_commit'] == SOURCE
    pins = {r['path']: r for r in expected['source_files']}
    pins['START_HERE.md'] = expected['start']
    members = sorted([*pins, 'MANIFEST.json', 'SOURCE_MANIFEST.json'])
    assert len(pins) == 26 and len(members) == 28
    archive = a.zip.resolve(strict=True)
    raw = archive.read_bytes()
    assert len(raw) == a.zip_bytes and 0 < len(raw) <= 2 * 1024 * 1024
    assert hashlib.sha256(raw).hexdigest() == a.zip_sha256 and git(raw) == a.zip_git
    originals = [archive, here, protocol, expected_path]
    initial = [identity(p) for p in originals]
    output = a.output.absolute()
    output.mkdir(mode=0o700)
    receipt = {'schema': 'pt.composed-kit.independent-receiving/1', 'protocol_blob': PROTOCOL,
               'expected_blob': EXPECTED, 'source_commit': SOURCE, 'archive': identity(archive),
               'runtime': {'host': platform.node(), 'platform': platform.platform(),
                           'python': sys.version, 'executable': sys.executable},
               'initial': initial, 'checks': [], 'output': str(output),
               'scope': 'One ordinary extracted run command on existing seed21 fictional sample; no calendar, generate, tests, browser, server or installed copy.'}
    checks = receipt['checks']
    child = None
    watched = None
    before = None
    def check(name, condition, detail=None):
        checks.append({'name': name, 'passed': bool(condition), **({'detail': detail} if detail is not None else {})})
        if not condition:
            raise AssertionError(name)
    try:
        with zipfile.ZipFile(archive) as z:
            infos = z.infolist()
            check('exact_sorted_28_members', [x.filename for x in infos] == members)
            check('bounded_regular_fixed_metadata', sum(x.file_size for x in infos) <= 4 * 1024 * 1024 and
                  all(not x.is_dir() and not (x.flag_bits & 1) and x.create_system == 3 and
                      x.external_attr >> 16 == stat.S_IFREG | 0o644 and
                      x.date_time == (1980, 1, 1, 0, 0, 0) and
                      not PurePosixPath(x.filename).is_absolute() and '..' not in PurePosixPath(x.filename).parts and
                      '\\' not in x.filename for x in infos))
            payload = {x.filename: z.read(x) for x in infos}
        manifest = strict(payload['MANIFEST.json'])
        check('outer_manifest_shape', set(manifest) == {'schema', 'files'} and manifest['schema'] == 'hamon.delivery-zip/1')
        records = manifest['files']
        check('outer_manifest_27_payloads', isinstance(records, list) and [r['path'] for r in records] == [n for n in members if n != 'MANIFEST.json'])
        check('outer_manifest_complete_identities', all(set(r) == {'path', 'bytes', 'sha256'} and type(r['bytes']) is int and
              r['bytes'] == len(payload[r['path']]) and r['sha256'] == hashlib.sha256(payload[r['path']]).hexdigest() for r in records))
        sm = strict(payload['SOURCE_MANIFEST.json'])
        check('source_manifest_shape_status', set(sm) == {'schema', 'source_commit', 'publication_status', 'files', 'scope'} and
              sm['schema'] == 'pt.composed-portable.source/1' and sm['source_commit'] == SOURCE and
              sm['publication_status'] == 'reviewed-draft-not-main' and isinstance(sm['scope'], str))
        check('source_manifest_26_sorted_rows', isinstance(sm['files'], list) and [r['path'] for r in sm['files']] == sorted(pins))
        for r in sm['files']:
            name, b = r['path'], payload[r['path']]
            fixed = pins[name]
            check('independent_payload:' + name, type(r['bytes']) is int and r['bytes'] == len(b) == fixed['bytes'] and
                  r['sha256'] == hashlib.sha256(b).hexdigest() == fixed['sha256'] and r['git_blob'] == git(b) == fixed['git_blob'])
            if name == 'START_HERE.md':
                check('delivery_note_origin', set(r) == {'path', 'bytes', 'sha256', 'git_blob', 'origin'} and r['origin'] == 'delivery-note')
            else:
                check('source_lineage:' + name, set(r) == {'path', 'bytes', 'sha256', 'git_blob', 'origin', 'source_path', 'source_commit'} and
                      r['origin'] == 'reviewed-composed-draft-source' and r['source_path'] == name and r['source_commit'] == SOURCE)
        extracted = output / 'extracted'
        extracted.mkdir()
        for name in members:
            p = extracted / name
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open('xb') as f:
                f.write(payload[name])
        watched = originals + [extracted / name for name in members]
        before = [identity(p) for p in watched]
        receipt['before'] = before
        check('extraction_exact', all((extracted / n).read_bytes() == payload[n] for n in members))
        sample = extracted / 'pt_auth/sample_data'
        check('sample_declared_fixture_exact', strict((sample / 'expected.json').read_bytes()) == expected['sample_expected_original'])
        check('sample_csv_dimensions', [len(rows(sample / n)) for n in ['patients.csv', 'schedule.csv', 'authorizations.csv', 'payers.csv']] == [40, 842, 46, 5])
        report = output / 'new-report'
        check('requested_report_new', not report.exists())
        argv = [sys.executable, '-B', '-m', 'ptauth', 'run', '--data', 'sample_data', '--out', str(report),
                '--as-of', '2026-09-28', '--clinic-timezone', 'UTC']
        env = dict(os.environ)
        for key in ['PYTHONPATH', 'PYTHONHOME', 'PT_CALENDAR_SOURCE']:
            env.pop(key, None)
        env['PYTHONNOUSERSITE'] = '1'
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'
        start_ns, started = time.time_ns(), time.monotonic_ns()
        with (output / 'command.stdout').open('xb') as stdout, (output / 'command.stderr').open('xb') as stderr:
            child = subprocess.Popen(argv, cwd=extracted / 'pt_auth', env=env, stdin=subprocess.DEVNULL,
                                     stdout=stdout, stderr=stderr, start_new_session=True)
            timeout = False
            try:
                code = child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                timeout = True
                os.killpg(child.pid, signal.SIGKILL)
                code = child.wait(timeout=10)
        end_ns = time.time_ns()
        receipt['child'] = {'argv': argv, 'cwd': str(extracted / 'pt_auth'), 'pid': child.pid, 'returncode': code,
                            'timed_out': timeout, 'reaped': child.poll() is not None,
                            'start_utc_ns': str(start_ns), 'end_utc_ns': str(end_ns),
                            'elapsed_ns': str(time.monotonic_ns() - started)}
        check('one_command_exit0_reaped_no_timeout', code == 0 and not timeout and child.poll() is not None)
        out, err = (output / 'command.stdout').read_bytes(), (output / 'command.stderr').read_bytes()
        check('ordinary_stdout_stderr', err == b'' and b'[SYNTHETIC] as_of 2026-09-28: 40 patients, 842 visits, 46 auths' in out and b'clinic time zone: UTC' in out)
        check('seven_complete_report_outputs', inventory(report) == expected['expected_output_names'] and
              all(stat.S_ISREG(p.lstat().st_mode) for p in report.iterdir()))
        summary = strict((report / 'summary.json').read_bytes())
        c = summary['counts']
        check('explicit_date_zone_and_synthetic_scope', summary['as_of'] == '2026-09-28' and summary['clinic_timezone'] == 'UTC' and
              'SYNTHETIC DATA - NOT REAL PATIENTS' in summary['banner'])
        check('literal_sample_counts', [c[k] for k in ['patients', 'visits', 'auths']] == [40, 842, 46])
        check('literal_41_approved_auths', sorted(r['auth_no'] for r in summary['ledger']) == expected['approved_auths'])
        uncovered = summary['uncovered']
        check('literal_194_scheduled_uncovered_ids', sorted(r['visit_id'] for r in uncovered if r['status'] == 'scheduled') == expected['scheduled_uncovered_ids'] and c['uncovered_scheduled'] == 194)
        check('literal_two_completed_uncovered_ids', sorted(r['visit_id'] for r in uncovered if r['status'] == 'completed') == expected['completed_uncovered_ids'] and c['unauthorized_done'] == 2)
        check('uncovered_total_and_statuses', len(uncovered) == 196 and all(r['status'] in ['scheduled', 'completed'] for r in uncovered))
        wl = summary['worklist']
        check('worklist_owned_fictional_ids_counts', all(r['patient_id'] in expected['patient_ids'] for r in wl) and len(wl) == c['worklist'] and
              all(sum(r['priority'] == p for r in wl) == c[p.lower()] for p in ['P1', 'P2', 'P3']))
        wl_csv = rows(report / 'worklist.csv')
        check('worklist_csv_association', len(wl_csv) == len(wl) and all(
              [a['patient_id'], a['auth_no'], a['priority'], a['reasons'], a['payer']] ==
              [b['patient_id'], b['auth_no'], b['priority'], '|'.join(b['reasons']), b['payer_name']]
              for a, b in zip(wl_csv, wl)))
        check('ledger_csv_complete_association', csv_equal(rows(report / 'ledger.csv'), summary['ledger']))
        check('status_csv_complete_association', csv_equal(rows(report / 'visit_status_review.csv'), summary['visit_status_review']) and c['past_scheduled'] == len(summary['visit_status_review']))
        check('uncovered_csv_complete_association', csv_equal(rows(report / 'uncovered_visits.csv'), summary['uncovered_review']) and len(summary['uncovered_review']) == 196)
        html = (report / 'digest.html').read_text(encoding='utf-8')
        check('digest_scope_date_zone', summary['banner'] in html and '2026-09-28' in html and 'UTC' in html and '<html' in html)
        audit_lines = (report / 'audit.jsonl').read_bytes().splitlines()
        check('single_run_audit', len(audit_lines) == 1)
        audit = strict(audit_lines[0])
        check('audit_counts_date_zone', audit['action'] == 'run' and audit['run_by'] == 'cli' and audit['as_of'] == '2026-09-28' and
              audit['clinic_timezone'] == 'UTC' and all(audit[k] == v for k, v in c.items()))
        stamp = datetime.fromisoformat(audit['ts'])
        check('audit_utc_stamp_within_invocation', stamp.tzinfo is not None and stamp.utcoffset().total_seconds() == 0 and
              start_ns // 1_000_000_000 <= stamp.timestamp() <= (end_ns + 999_999_999) // 1_000_000_000)
        check('recorded_generated_at_parses', isinstance(datetime.fromisoformat(summary['generated_at']), datetime))
        receipt['report_files'] = [identity(p) for p in sorted(report.iterdir())]
        receipt['summary_counts'] = c
    except BaseException as exc:
        receipt['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=10)
            except BaseException as exc:
                receipt['cleanup_error'] = repr(exc)
        if child is not None:
            receipt['final_child_status'] = {'pid': child.pid, 'returncode': child.poll(), 'reaped': child.poll() is not None}
        try:
            receipt['original_after'] = [identity(p) for p in originals]
            check('four_original_inputs_exact', receipt['original_after'] == initial)
            if watched is not None:
                receipt['after'] = [identity(p) for p in watched]
                check('all32_byte_native_ns_custody_exact', receipt['after'] == before)
                check('extracted_inventory_exact_no_cache', inventory(extracted) == members)
        except BaseException as exc:
            receipt['custody_error'] = repr(exc)
        receipt['passed'] = not any(k in receipt for k in ['error', 'cleanup_error', 'custody_error']) and all(x['passed'] for x in checks)
        with (output / 'receiving.json').open('x', encoding='utf-8') as f:
            json.dump(receipt, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print(json.dumps({'output': str(output), 'passed': receipt['passed'], 'checks': len(checks), 'error': receipt.get('error')}))
    return 0 if receipt['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
