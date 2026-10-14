"""Compose two admitted CLI changes without executing product source."""
from pathlib import Path
import difflib
import hashlib
import json

ROOT = Path(__file__).resolve().parent

def git(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()

def replacements(before, after):
    a, b = before.splitlines(keepends=True), after.splitlines(keepends=True)
    return [(b''.join(a[i:j]), b''.join(b[k:l]))
            for op, i, j, k, l in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
            if op != 'equal']

def replace_exact(raw, edits):
    for old, new in edits:
        if not old or raw.count(old) != 1:
            raise ValueError('An edit does not have one exact nonempty source span')
        raw = raw.replace(old, new, 1)
    return raw

base = (ROOT.parent / 'pt-calendar-stdout-author/original/ptauth/cli.py').read_bytes()
calendar = (ROOT / 'current-source/pt_auth/ptauth/cli.py').read_bytes()
date = json.loads((ROOT / 'date-cli.json').read_text())['content'].encode('utf-8')
assert [git(x) for x in (base, date, calendar)] == [
    '559c0a76effa2204041e9318e9869a6c7389f50d',
    '7250a3d64b6bf30932c36280f1c2f829974ef7bc',
    'b1b7a60de7b470ea59de6313bfcde336f1c5dfe1']
date_edits = replacements(base, date)
assert len(date_edits) == 4 and all(len(a.splitlines()) == len(b.splitlines()) == 1 for a,b in date_edits)
composed = replace_exact(calendar, date_edits)
assert replace_exact(composed, [(b,a) for a,b in date_edits]) == calendar

# Reverse the date-only lines in the composed result, and remove the exact
# calendar contribution using the two full unified-diff context regions.
# SequenceMatcher inserts can have empty before spans, so retain explicit
# original/candidate replacement regions with a surrounding unchanged anchor.
calendar_edits = [
    (base[base.index(b'        except (CalendarInputError, OSError)'):base.index(b'    if a.cmd == "serve":')],
     calendar[calendar.index(b'        except (CalendarInputError, OSError)'):calendar.index(b'    if a.cmd == "serve":')]),
    (base[base.index(b'if __name__ == "__main__":'):],
     calendar[calendar.index(b'def _calendar_error'):]),
]
assert replace_exact(base, calendar_edits) == calendar
assert replace_exact(date, calendar_edits) == composed
assert replace_exact(composed, [(b,a) for a,b in calendar_edits]) == date
assert b'\n' not in composed.replace(b'\r\n', b'')

admitted = json.loads((ROOT / 'admitted-files.json').read_text())
files = {f['path']: (f['content'].encode('utf-8'), f['sha']) for f in admitted['files']}
files['pt_auth/README.md'] = (admitted['dateREADME']['content'].encode('utf-8'), admitted['dateREADME']['sha'])
files['pt_auth/tests/test_cli_date_admission.py'] = (admitted['dateTest']['content'].encode('utf-8'), admitted['dateTest']['sha'])
files['pt_auth/tests/test_calendar_receipt_output.py'] = (admitted['calendarTest']['content'].encode('utf-8'), admitted['calendarTest']['sha'])
files['pt_auth/ptauth/cli.py'] = (composed, git(composed))
guide = (ROOT.parent / 'pt-calendar-stdout-author/CALENDAR_RECEIPTS.md').read_bytes()
files['pt_auth/CALENDAR_RECEIPTS.md'] = (guide, 'a4a55efba02796069bbd974ab2d9de3060da5428')
records = []
for name, (raw, expected) in files.items():
    assert git(raw) == expected, name
    p = ROOT / 'composed-source' / name
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('xb') as f:
        f.write(raw)
    records.append({'path': name, 'bytes': len(raw), 'git_blob': git(raw),
                    'sha256': hashlib.sha256(raw).hexdigest(), 'mtime_ns': p.stat().st_mtime_ns})
record = {'schema':'ptauth.date-calendar.composition/1',
          'base_cli':git(base),'date_cli':git(date),'calendar_cli':git(calendar),
          'composed_cli':git(composed),'four_exact_date_lines':True,
          'two_calendar_regions_exact':True,'both_application_orders_identical':True,
          'both_reversals_recover_exact_other_parent':True,'crlf_preserved':True,
          'files':records,'runtime_executed':False}
(ROOT / 'composition-proof.json').write_text(json.dumps(record,indent=2)+'\n')
(ROOT / 'composed-vs-calendar.diff').write_text(''.join(difflib.unified_diff(
    calendar.decode().splitlines(keepends=True),composed.decode().splitlines(keepends=True),
    fromfile='calendar-cli.py',tofile='composed-cli.py')),newline='')
print(json.dumps({'composed_cli':git(composed),'files':len(files),'both_reversals_exact':True,'runtime_executed':False}))
