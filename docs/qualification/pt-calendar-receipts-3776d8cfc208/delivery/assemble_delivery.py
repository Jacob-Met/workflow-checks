"""One packaging invocation of the unchanged maintained selected-file packer."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parent
PACKER = ROOT.parent / 'estate-tooling-adoption/make_delivery_zip.py'
SELECTION = ROOT / 'selection.json'
SOURCE = ROOT / 'source'
OUTPUT = ROOT / 'PT-Calendar-Receipts-1bd30de4.zip'
EVIDENCE = ROOT / 'delivery-received'

def ident(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(),
            'git_blob': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(),
            'mtime_ns': path.stat().st_mtime_ns}

def main():
    EVIDENCE.mkdir(exist_ok=False)
    selection = json.loads(SELECTION.read_bytes())
    rows = selection['files']
    watches = [PACKER, SELECTION] + [SOURCE / r['path'] for r in rows]
    before = [ident(p) for p in watches]
    assert before[0]['git_blob'] == '34e192096abed7216025e8141a9cf3106bb82dfd'
    assert not OUTPUT.exists()
    argv = [sys.executable, '-I', '-B', str(PACKER), str(SOURCE), str(SELECTION),
            str(OUTPUT), '--manifest-sha256', before[1]['sha256']]
    started = time.monotonic_ns()
    child = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    elapsed = time.monotonic_ns() - started
    (EVIDENCE / 'packer.stdout').write_bytes(child.stdout)
    (EVIDENCE / 'packer.stderr').write_bytes(child.stderr)
    assert child.returncode == 0 and child.stderr == b''
    receipt = json.loads(child.stdout)
    assert receipt['payloads'] == 7 and receipt['members'] == 8
    with zipfile.ZipFile(OUTPUT) as archive:
        assert archive.namelist() == sorted(['MANIFEST.json'] + [r['path'] for r in rows])
        assert archive.testzip() is None
        assert archive.read('MANIFEST.json') == SELECTION.read_bytes()
        for row in rows:
            assert archive.read(row['path']) == (SOURCE / row['path']).read_bytes()
        members = archive.namelist()
    after = [ident(p) for p in watches]
    assert before == after
    result = {'schema': 'pt.calendar-receipts.packaging-receiving/1',
              'reviewed_source_snapshot': '1bd30de4cecff7ee7564dccadf53561f3e21c284',
              'publication_status': 'reviewed-draft-not-main',
              'argv': argv, 'returncode': child.returncode, 'elapsed_ns': elapsed,
              'process_reaped': True, 'members': members, 'payloads_exact': True,
              'before': before, 'after': after, 'watched_files_unchanged': True,
              'archive': ident(OUTPUT),
              'scope': 'One maintained packer invocation and complete archive byte/member receiving. No application, browser, GUI or extracted runtime replay.'}
    (EVIDENCE / 'receiving.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'archive': result['archive'], 'members': len(members),
                      'watched_files': len(before), 'custody': before == after,
                      'returncode': child.returncode, 'elapsed_ns': elapsed}))

if __name__ == '__main__':
    main()
