from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'evidence' / 'baseline'
OUT.mkdir(parents=True, exist_ok=False)
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
           PYTHONPATH=str(ROOT / 'base' / 'utility_watch'), TMPDIR=str(ROOT / 'tmp'))

def hashes():
    return {str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(OUT.rglob('*')) if p.is_file() and p.name not in ('receipt.json',)}

receipts = []
for name, args in [
    ('generate', ['generate', '--out', str(OUT / 'data'), '--seed', '11']),
    ('run', ['run', '--data', str(OUT / 'data'), '--out', str(OUT / 'report')]),
    ('review', ['review', '--data', str(OUT / 'data'), '--report', str(OUT / 'report' / 'summary.json'),
                '--out', str(OUT / 'review.csv')]),
    ('worksheet-list', ['worksheet', 'list', '--worksheet', str(OUT / 'review.csv'), '--json']),
]:
    before = hashes()
    command = [sys.executable, '-B', '-m', 'uwatch', *args]
    result = subprocess.run(command, cwd=ROOT / 'base' / 'utility_watch', env=env,
                            capture_output=True, text=True)
    after = hashes()
    receipts.append({'name': name, 'command': command, 'exit': result.returncode,
                     'stdout': result.stdout, 'stderr': result.stderr,
                     'existing_files_preserved': all(after.get(p) == h for p, h in before.items()),
                     'files_before': before, 'files_after': after})
    if name != 'worksheet-list' and result.returncode:
        raise RuntimeError(json.dumps(receipts[-1]))

result = {'source_commit': '9e931fa9f42033bf2368f7149684fb5631345715',
          'source_tree': '0b0c903801f432968e9cdfb1f1fa134cecc37217',
          'python': sys.version, 'commands': receipts,
          'missing_workflow_reproduced': receipts[-1]['exit'] == 2 and
              "invalid choice: 'worksheet'" in receipts[-1]['stderr'] and
              receipts[-1]['stdout'] == '' and receipts[-1]['files_before'] == receipts[-1]['files_after']}
(OUT / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'commands': [{k: r[k] for k in ('name', 'exit', 'existing_files_preserved')} for r in receipts],
                  'missing_workflow_reproduced': result['missing_workflow_reproduced']}))
if not result['missing_workflow_reproduced']:
    raise SystemExit(1)
