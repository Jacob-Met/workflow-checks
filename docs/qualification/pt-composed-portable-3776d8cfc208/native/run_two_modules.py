"""Bounded native receiving of two unchanged existing PT test modules."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import pwd
import re
import signal
import stat
import subprocess
import sys
import time

PROTOCOL = '7a008247568434649badafca5f50a62696ddbccc'
NAMES = sorted(['LICENSE', 'pt_auth/README.md', 'pt_auth/CALENDAR_RECEIPTS.md',
                'pt_auth/tests/test_cli_date_admission.py',
                'pt_auth/tests/test_calendar_receipt_output.py'] +
               ['pt_auth/ptauth/' + n for n in ['__init__.py', '__main__.py',
                'calendar_ui.js', 'cli.py', 'data.py', 'engine.py', 'report.py',
                'synth.py', 'ui.html', 'uncovered.py', 'web.py', 'worklist_calendar.py']])

def git(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()

def identity(p):
    if not stat.S_ISREG(p.lstat().st_mode):
        raise ValueError('Expected regular file: ' + str(p))
    b = p.read_bytes()
    return {'path': str(p), 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest(),
            'git_blob': git(b), 'mtime_ns': str(p.stat().st_mtime_ns)}

def inventory(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() or p.is_symlink())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source-root', required=True, type=Path)
    ap.add_argument('--manifest', required=True, type=Path)
    ap.add_argument('--manifest-sha256', required=True)
    ap.add_argument('--output', required=True, type=Path)
    a = ap.parse_args()
    account = pwd.getpwuid(os.getuid())
    assert platform.node() == 'hamon-thinkpad' and account.pw_name == 'jacob'
    assert sys.platform == 'linux' and sys.version_info[:3] == (3, 14, 4)
    assert Path(sys.executable).absolute() == Path('/usr/bin/python3')
    assert sys.dont_write_bytecode and sys.flags.isolated
    assert importlib.metadata.version('pytest') == '9.0.2'
    pytest_spec = importlib.util.find_spec('pytest')
    assert pytest_spec is not None and pytest_spec.origin == '/usr/lib/python3/dist-packages/pytest/__init__.py'
    source = a.source_root.resolve(strict=True)
    output = a.output.absolute()
    home = Path(account.pw_dir).resolve()
    assert source.is_relative_to(home) and output.parent.resolve(strict=True).is_relative_to(home)
    assert not output.is_relative_to(source) and not source.is_relative_to(output)
    here = Path(__file__).resolve()
    protocol = here.with_name('PROTOCOL.md')
    assert git(protocol.read_bytes()) == PROTOCOL
    manifest_path = a.manifest.resolve(strict=True)
    manifest_before = identity(manifest_path)
    assert re.fullmatch(r'[0-9a-f]{64}', a.manifest_sha256)
    assert manifest_before['sha256'] == a.manifest_sha256
    manifest = json.loads(manifest_path.read_bytes())
    assert set(manifest) == {'files'} and len(manifest['files']) == 17
    assert [r['path'] for r in manifest['files']] == NAMES
    assert inventory(source) == NAMES
    for r in manifest['files']:
        assert set(r) == {'path', 'bytes', 'git_blob', 'sha256'}
        got = identity(source / r['path'])
        assert type(r['bytes']) is int and all(got[k] == r[k] for k in ['bytes', 'git_blob', 'sha256'])
    watched = [source / n for n in NAMES] + [here, protocol]
    before = [identity(p) for p in watched]
    output.mkdir(mode=0o700)
    receipt = {'schema': 'pt.composition.two-module.native/1',
               'protocol_blob': PROTOCOL, 'source_manifest': manifest_before,
               'source_root': str(source), 'output': str(output), 'before': before,
               'runtime': {'host': platform.node(), 'account': account.pw_name,
                           'python': sys.version, 'executable': sys.executable,
                           'pytest_version': '9.0.2', 'pytest_origin': pytest_spec.origin},
               'checks': [], 'scope': 'Exactly two unchanged existing test modules; no ordinary composition course, install, full suite, Windows or deployment claim.'}
    child = None
    checks = receipt['checks']
    try:
        argv = ['/usr/bin/python3', '-I', '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                '--basetemp', str(output / 'pytest-temp'),
                'tests/test_cli_date_admission.py', 'tests/test_calendar_receipt_output.py']
        env = dict(os.environ)
        for key in ['PYTEST_ADDOPTS', 'PYTHONPATH', 'PYTHONHOME', 'PT_CALENDAR_SOURCE']:
            env.pop(key, None)
        env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        started = time.monotonic_ns()
        with (output / 'pytest.stdout').open('xb') as out, (output / 'pytest.stderr').open('xb') as err:
            child = subprocess.Popen(argv, cwd=source / 'pt_auth', env=env,
                                     stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                     start_new_session=True)
            timed_out = False
            try:
                returncode = child.wait(timeout=60)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(child.pid, signal.SIGKILL)
                returncode = child.wait(timeout=10)
        receipt['child'] = {'argv': argv, 'cwd': str(source / 'pt_auth'), 'pid': child.pid,
                            'returncode': returncode, 'timed_out': timed_out,
                            'reaped': child.poll() is not None,
                            'outer_elapsed_ns': str(time.monotonic_ns() - started)}
        stdout = (output / 'pytest.stdout').read_bytes()
        text = stdout.decode('utf-8', errors='strict')
        receipt['stdout'] = identity(output / 'pytest.stdout')
        receipt['stderr'] = identity(output / 'pytest.stderr')
        checks.append({'name': 'one_owned_child_exit0_reaped_no_timeout',
                       'passed': returncode == 0 and not timed_out and child.poll() is not None})
        checks.append({'name': 'nineteen_existing_tests_passed',
                       'passed': bool(re.search(r'(^|\n)19 passed(?:, [^\n]*)? in [0-9.]+s', text))})
        checks.append({'name': 'no_failure_error_skip_or_xfail_summary',
                       'passed': re.search(r'\b[1-9][0-9]* (?:failed|errors?|skipped|xfailed|xpassed)\b', text) is None})
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
            receipt['after'] = [identity(p) for p in watched]
            receipt['manifest_after'] = identity(manifest_path)
            checks.append({'name': 'nineteen_source_receiver_protocol_records_exact', 'passed': receipt['after'] == before})
            checks.append({'name': 'manifest_record_exact', 'passed': receipt['manifest_after'] == manifest_before})
            checks.append({'name': 'source_inventory_exact_no_cache', 'passed': inventory(source) == NAMES})
        except BaseException as exc:
            receipt['custody_error'] = repr(exc)
        receipt['passed'] = not any(k in receipt for k in ['error', 'cleanup_error', 'custody_error']) and all(c['passed'] for c in checks)
        with (output / 'receiving.json').open('x', encoding='utf-8') as f:
            json.dump(receipt, f, indent=2)
            f.write('\n')
        print(json.dumps({'output': str(output), 'passed': receipt['passed'], 'checks': checks, 'error': receipt.get('error')}))
    return 0 if receipt['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
