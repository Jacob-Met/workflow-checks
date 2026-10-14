"""One maintained-packer invocation for the static PT review packet."""
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
SOURCE = ROOT / 'review'
OUTPUT = ROOT / 'PT-Portable-Browser-Review-69f3c8e0.zip'

def identity(path):
    raw = path.read_bytes()
    return {'path': str(path), 'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest(),
            'git_blob':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),
            'mtime_ns': str(path.stat().st_mtime_ns)}

def main():
    rows = json.loads(SELECTION.read_bytes())['files']
    assert len(rows) == 7
    watched = [PACKER, SELECTION] + [SOURCE/x['path'] for x in rows]
    before = [identity(p) for p in watched]
    assert before[0]['git_blob'] == '34e192096abed7216025e8141a9cf3106bb82dfd'
    assert not OUTPUT.exists()
    argv = [sys.executable,'-I','-B',str(PACKER),str(SOURCE),str(SELECTION),str(OUTPUT),
            '--manifest-sha256',before[1]['sha256']]
    started = time.monotonic_ns()
    run = subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    elapsed = time.monotonic_ns()-started
    (ROOT/'packer.stdout').write_bytes(run.stdout); (ROOT/'packer.stderr').write_bytes(run.stderr)
    assert run.returncode == 0 and run.stderr == b''
    with zipfile.ZipFile(OUTPUT) as z:
        assert z.namelist() == sorted(['MANIFEST.json']+[r['path'] for r in rows])
        assert z.testzip() is None and z.read('MANIFEST.json') == SELECTION.read_bytes()
        for r in rows:
            assert z.read(r['path']) == (SOURCE/r['path']).read_bytes()
        members = z.namelist()
    after = [identity(p) for p in watched]
    assert before == after
    receipt = {'schema':'pt.ui.review-packaging/1','argv':argv,'returncode':run.returncode,
        'elapsed_ns':str(elapsed),'reaped':True,'members':members,'crc_ok':True,
        'every_selected_body_exact':True,'before':before,'after':after,
        'inputs_unchanged':True,'archive':identity(OUTPUT),
        'scope':'One unchanged selected-file packer, complete ZIP byte/layout inspection; no PT/browser/server execution or new rendered-HTML claim.'}
    (ROOT/'packaging-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'archive':receipt['archive'],'members':len(members),'watched':len(before),'returncode':run.returncode}))

if __name__ == '__main__':
    main()
