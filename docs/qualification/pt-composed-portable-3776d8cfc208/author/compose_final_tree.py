"""Admit final parent and assemble one reviewed CLI resolution plus exact leaves."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
helper = ROOT.parent / 'estate-tooling-adoption/verify_tree_union.py'
raw = helper.read_bytes()
assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == 'f6f3585033d393ce9f496336e4626db649f2711f'
spec = importlib.util.spec_from_file_location('admitted_tree_union', helper)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
pins = {'base': 'e21f607e62158b7f02c46a18e6104e7c8c5131b6',
        'date': '1e5c3ed889faa0b941eb86d71f5e7424d6cbc080',
        'calendar': '1981f4b9bc022b4d5ffbb9fee7cf4ff81143a150'}
files = {'base': 'base-tree.json', 'date': 'date-tree.json',
         'calendar': 'final-calendar-tree.json'}
trees = {k: v.read_snapshot(ROOT / files[k], pin, k) for k, pin in pins.items()}
base, date, calendar = (trees[k] for k in ('base', 'date', 'calendar'))
resolved_path = 'pt_auth/ptauth/cli.py'
resolved_sha = '8d6b43649bc6c142c28f71646485a31f6a6bbf55'
cli = (ROOT / 'composed-source' / resolved_path).read_bytes()
assert hashlib.sha1(b'blob ' + str(len(cli)).encode() + b'\0' + cli).hexdigest() == resolved_sha
expected, conflicts = {}, []
for p in sorted(set(base) | set(date) | set(calendar)):
    b, d, c = base.get(p), date.get(p), calendar.get(p)
    if d == b:
        chosen = c
    elif c == b or d == c:
        chosen = d
    else:
        conflicts.append(p)
        assert p == resolved_path
        assert b == ('100644', 'blob', '559c0a76effa2204041e9318e9869a6c7389f50d')
        assert d == ('100644', 'blob', '7250a3d64b6bf30932c36280f1c2f829974ef7bc')
        assert c == ('100644', 'blob', 'b1b7a60de7b470ea59de6313bfcde336f1c5dfe1')
        chosen = ('100644', 'blob', resolved_sha)
    if chosen is not None:
        expected[p] = chosen
assert conflicts == [resolved_path]
for p in expected:
    parts = p.split('/')
    assert not any('/'.join(parts[:i]) in expected for i in range(1, len(parts)))
changed = sorted(p for p in set(calendar) | set(expected) if calendar.get(p) != expected.get(p))
added = [p for p in changed if p not in calendar]
modified = [p for p in changed if p in calendar]
assert modified == ['pt_auth/README.md', resolved_path] and len(added) == 28
assert len(calendar) == 1583 and len(expected) == 1611
manifest = json.loads((ROOT / 'native-source-manifest.json').read_bytes())
assert all(expected[r['path']] == ('100644', 'blob', r['git_blob']) for r in manifest['files'])
entries = [{'path': p, **v.identity_json(expected[p])} for p in changed]
report = {'schema': 'ptauth.final-source-tree-composition/1', 'input_trees': pins,
          'parent_commits': ['c95c3eaec22fd5bbafeb210a2ae99a470dc2e84a',
                             '58305dd238db2b660bbfe6e0091f7d8806d9a74d'],
          'terminal_counts': {k: len(t) for k, t in trees.items()},
          'expected_terminal_count': len(expected), 'preserved_calendar_leaves': len(calendar) - len(modified),
          'only_conflict': resolved_path, 'resolved_cli': resolved_sha,
          'resolution_proof': 'composition-proof.json', 'modified': modified, 'added': added,
          'source_manifest_all_17_match': True, 'tree_entries': entries,
          'expected_leaves': [{'path': p, **v.identity_json(identity)} for p, identity in sorted(expected.items())]}
with (ROOT / 'final-tree-plan.json').open('x', encoding='utf-8') as f:
    json.dump(report, f, indent=2)
    f.write('\n')
print(json.dumps({k: report[k] for k in ('terminal_counts', 'expected_terminal_count', 'preserved_calendar_leaves', 'only_conflict', 'modified', 'source_manifest_all_17_match')}))
