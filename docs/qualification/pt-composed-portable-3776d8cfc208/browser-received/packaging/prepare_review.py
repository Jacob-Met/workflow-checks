"""Materialize exact retained review payloads; no application execution."""
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NATIVE = ROOT.parent / 'pt-ui-independent'

def identity(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(),
            'git_blob': hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()}

def main():
    source = ROOT / 'review'
    source.mkdir(exist_ok=False)
    maps = {
        'worklist-desktop.png': ('final-native/received-course/worklist-desktop.png', '4b1a9b728ac0a299e69e2c2616ba4b47622b785f'),
        'uncovered-narrow.png': ('final-native/received-course/uncovered-narrow.png', 'b89ba0b65e193ae12ed0f9f07fe0bfec6ae8ded9'),
        'uncovered_visits.csv': ('final-native/received-course/downloaded-uncovered-visits.csv', 'e750ad287278f3857be3684c8009d0afe7dd2a35'),
        'receiving-first.json': ('first-native/received-course/receiving.json', 'bcd9446cdf3e5e8246fe062e6e7198524ef9af34'),
        'receiving-final.json': ('final-native/received-course/receiving.json', 'ca19af9ad0a16db698ce493e3638a90d1c27786a')}
    provenance = []
    for name, (relative, expected) in maps.items():
        path = NATIVE / relative
        raw = path.read_bytes(); ident = identity(raw)
        assert ident['git_blob'] == expected
        (source / name).write_bytes(raw)
        provenance.append({'path': name, 'origin': str(path), **ident})
    assert len(list(csv.DictReader(io.StringIO((source/'uncovered_visits.csv').read_bytes().decode('utf-8'))))) == 196
    final = json.loads((source/'receiving-final.json').read_bytes())
    assert final['passed'] is True and len(final['checks']) == 21 and all(x['passed'] for x in final['checks'])
    first = json.loads((source/'receiving-first.json').read_bytes())
    assert first['passed'] is False and len(first['checks']) == 17
    assert sum(x['passed'] is True for x in first['checks']) == 16
    assert final['report_before'] == final['report_after']
    for name in ('START_HERE.md', 'OPEN_REVIEW.html'):
        raw = (ROOT/name).read_bytes(); (source/name).write_bytes(raw)
        provenance.append({'path': name, 'origin': 'new practical review prose', **identity(raw)})
    html = (source/'OPEN_REVIEW.html').read_text()
    assert '<script' not in html.lower() and 'src="http' not in html.lower()
    manifest = {'schema': 'hamon.delivery-zip/1', 'files': [
        {k:r[k] for k in ('path','bytes','sha256')} for r in sorted(provenance,key=lambda r:r['path'])]}
    (ROOT/'selection.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (ROOT/'review-provenance.json').write_text(json.dumps({'schema':'pt.ui.review-selection/1',
        'source_commit':'69f3c8e0577b579ee36256da0a075fccb201af8f','files':provenance,
        'scope':'Exact original evidence selected with new static explanatory prose; no application/browser/server execution.'},indent=2)+'\n')
    print(json.dumps({'payloads':len(provenance),'bytes':sum(x['bytes'] for x in provenance),'source':str(source)}))

if __name__ == '__main__':
    main()
