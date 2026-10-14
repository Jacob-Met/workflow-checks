"""Exclusive extraction plus one bounded Node/browser course; no app import."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import pwd
import signal
import stat
import subprocess
import sys
import time
import zipfile


def identity(p):
    b = p.read_bytes()
    s = p.stat()
    return dict(bytes=len(b), sha256=hashlib.sha256(b).hexdigest(),
                git_blob=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),
                mtime_ns=str(s.st_mtime_ns))


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--zip', required=True)
    a.add_argument('--output', required=True)
    args = a.parse_args()
    here = Path(__file__).resolve().parent
    bundle = Path(args.zip).resolve()
    output = Path(args.output).resolve()
    if platform.node().lower() != 'hamon-thinkpad' or pwd.getpwuid(os.getuid()).pw_name != 'jacob':
        raise ValueError('Unexpected receiving device')
    if sys.version_info[:3] != (3, 14, 4):
        raise ValueError('Unexpected Python')
    if not output.is_relative_to(Path(pwd.getpwuid(os.getuid()).pw_dir)):
        raise ValueError('Receiving output must be under the actual account home')
    expected = json.loads((here/'expected.json').read_text())
    assert identity(here/'expected.json')['git_blob'] == 'a072989cfab2f17e7c6b805a22e084b0c46ef703'
    assert all(identity(bundle)[k] == v for k, v in expected['zip'].items())
    output.mkdir(mode=0o700)
    extracted = output/'extracted'
    extracted.mkdir()
    with zipfile.ZipFile(bundle) as archive:
        records = archive.infolist()
        assert [r.filename for r in records] == [r['path'] for r in expected['files']]
        for info, record in zip(records, expected['files']):
            assert stat.S_ISREG(info.external_attr >> 16) and not info.is_dir()
            assert info.filename == str(Path(info.filename)) and '..' not in Path(info.filename).parts
            b = archive.read(info)
            assert len(b) == record['bytes'] and hashlib.sha256(b).hexdigest() == record['sha256']
            target = extracted/info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as f:
                f.write(b)
    watched = [bundle, here/'expected.json', here/'PROTOCOL.md', here/'receive_ui.js', Path(__file__).resolve()]
    watched += [extracted/r['path'] for r in expected['files']]
    before = {str(p): identity(p) for p in watched}
    receipt = dict(schema='pt.composed-ui.outer/1', output=str(output), before=before,
                   argv=['/usr/bin/node', str(here/'receive_ui.js'), str(extracted), str(output), str(here/'expected.json')],
                   timed_out=False, reaped=False)
    env = dict(os.environ)
    for key in ('PYTHONPATH', 'PYTHONHOME', 'NODE_OPTIONS'):
        env.pop(key, None)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    started = time.monotonic_ns()
    proc = None
    with (output/'outer.stdout').open('xb') as stdout, (output/'outer.stderr').open('xb') as stderr:
        try:
            proc = subprocess.Popen(receipt['argv'], stdout=stdout, stderr=stderr, env=env, start_new_session=True)
            receipt['child_pid'] = proc.pid
            try:
                receipt['returncode'] = proc.wait(timeout=180)
                receipt['reaped'] = True
            except subprocess.TimeoutExpired:
                receipt['timed_out'] = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError as exc:
                    receipt['group_kill_error'] = repr(exc)
                receipt['returncode'] = proc.wait(timeout=10)
                receipt['reaped'] = True
        except Exception as exc:
            receipt['error'] = repr(exc)
        finally:
            if proc is not None and receipt['reaped'] and receipt.get('returncode') != 0 and not receipt['timed_out']:
                cleanup = dict(process_group=proc.pid, signal='SIGKILL', attempted=True)
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                    cleanup['sent'] = True
                except ProcessLookupError:
                    cleanup['already_absent'] = True
                except OSError as exc:
                    cleanup['error'] = repr(exc)
                receipt['failed_exit_group_cleanup'] = cleanup
            receipt['elapsed_ns'] = time.monotonic_ns()-started
            try:
                receipt['after'] = {str(p): identity(p) for p in watched}
                receipt['sources_unchanged'] = before == receipt['after']
            except Exception as exc:
                receipt['custody_error'] = repr(exc)
                receipt['sources_unchanged'] = False
    receipt['passed'] = receipt.get('returncode') == 0 and receipt['reaped'] and not receipt['timed_out'] and receipt['sources_unchanged'] and 'error' not in receipt
    with (output/'outer.json').open('x') as f:
        json.dump(receipt, f, indent=2)
        f.write('\n')
    print(json.dumps({k: v for k, v in receipt.items() if k not in ('before', 'after')}), flush=True)
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
