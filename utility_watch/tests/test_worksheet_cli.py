"""Actual saved-worksheet CLI receiving with synthetic inputs and native reconciliation."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from uwatch import review, worksheet


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def cells(path):
    return list(csv.DictReader(io.StringIO(path.read_bytes().decode('utf-8-sig'), newline='')))


class WorksheetCLI(unittest.TestCase):
    calls = 0

    @classmethod
    def invoke(cls, *args):
        cls.calls += 1
        return subprocess.run([sys.executable, '-B', '-m', 'uwatch', *map(str, args)],
                              cwd=PACKAGE, env=dict(os.environ, PYTHONPATH=str(PACKAGE),
                                  PYTHONDONTWRITEBYTECODE='1'),
                              capture_output=True, text=True, timeout=20)

    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(prefix='uwatch-worksheet-fixture-')
        cls.base = Path(cls.fixture.name)
        commands = [
            ('generate', '--out', cls.base / 'data', '--seed', '11'),
            ('run', '--data', cls.base / 'data', '--out', cls.base / 'report'),
            ('review', '--data', cls.base / 'data', '--report', cls.base / 'report' / 'summary.json',
             '--out', cls.base / 'review.csv'),
        ]
        for args in commands:
            result = cls.invoke(*args)
            if result.returncode:
                raise RuntimeError((args, result.returncode, result.stdout, result.stderr))
        cls.base_hashes = hashes(cls.base)

    @classmethod
    def tearDownClass(cls):
        try:
            if hashes(cls.base) != cls.base_hashes:
                raise AssertionError('original synthetic data/report/worksheet changed')
        finally:
            cls.fixture.cleanup()
        print(f'Actual uwatch CLI children completed: {cls.calls}')

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='uwatch-worksheet-case-')
        self.root = Path(self.temporary.name)
        self.file = self.root / 'source.csv'
        shutil.copyfile(self.base / 'review.csv', self.file)
        self.source = self.file.read_bytes()
        self.rows = cells(self.file)
        self.target = next(row for row in self.rows if row['row_state'] == 'current')

    def tearDown(self):
        self.temporary.cleanup()

    def command(self, *args, status=0):
        result = self.invoke(*args)
        self.assertEqual(result.returncode, status, (args, result.stdout, result.stderr))
        return result

    def annotate(self, out='annotated.csv', *, source=None, row=None, status='reviewed',
                 reviewer=' Zoë, analyst ', note='Asked vendor, kept the evidence.\nFollow up Friday. ☃'):
        out = self.root / out
        self.command('worksheet', 'annotate', '--worksheet', source or self.file,
                     '--row-id', row or self.target['row_id'], '--status', status,
                     '--reviewer', reviewer, '--note', note, '--out', out)
        return out

    def assert_only_annotation(self, output, row_id, expected):
        before, after = cells(self.file), cells(output)
        self.assertEqual(len(before), len(after))
        for old, new in zip(before, after):
            for key in review.COLUMNS:
                self.assertEqual(new[key], expected[key] if old['row_id'] == row_id and key in expected else old[key],
                                 (old['row_id'], key))
        self.assertEqual(self.file.read_bytes(), self.source)
        self.assertEqual(len(review._previous(output.read_bytes())), len(before) - 1)

    def test_complete_list_filters_and_empty_results_are_saved_snapshots(self):
        result = self.command('worksheet', 'list', '--worksheet', self.file, '--json')
        data = json.loads(result.stdout)
        self.assertEqual(data['worksheet_sha256'], hashlib.sha256(self.source).hexdigest())
        self.assertEqual(data['as_of'], '2026-09-28')
        self.assertEqual(data['rows'], review._previous(self.source))
        self.assertEqual(data['shown'], data['current'])
        self.assertEqual(data['history'], 0)
        filtered = json.loads(self.command('worksheet', 'list', '--worksheet', self.file,
            '--account', self.target['account_no'], '--status', 'open', '--json').stdout)
        self.assertEqual(filtered['rows'], [r for r in data['rows'] if r['account_no'] == self.target['account_no']])
        empty = json.loads(self.command('worksheet', 'list', '--worksheet', self.file,
                                        '--account', 'not-an-account', '--json').stdout)
        self.assertEqual(empty['rows'], [])
        self.assertEqual(empty['current'], data['current'])
        self.assertEqual(self.file.read_bytes(), self.source)

    def test_annotation_round_trips_into_existing_native_reconciliation(self):
        reviewer = ' Zoë, analyst '
        note = 'Asked vendor, kept the evidence.\nFollow up Friday. ☃'
        out = self.annotate(reviewer=reviewer, note=note)
        self.assert_only_annotation(out, self.target['row_id'],
                                   {'review_status': 'reviewed', 'reviewer': reviewer, 'note': note})
        reconciled = self.root / 'reconciled.csv'
        self.command('review', '--data', self.base / 'data', '--report', self.base / 'report' / 'summary.json',
                     '--previous', out, '--out', reconciled)
        received = next(r for r in review._previous(reconciled.read_bytes()) if r['row_id'] == self.target['row_id'])
        self.assertEqual({k: received[k] for k in review.EDITABLE},
                         {'review_status': 'reviewed', 'reviewer': reviewer, 'note': note})
        self.assertEqual(received['row_state'], 'current')

    def test_reopen_requires_explicit_fields_and_preserves_literal_notes(self):
        reviewed = self.annotate()
        opened = self.annotate('reopened.csv', source=reviewed, status='open', reviewer='', note='')
        row = next(r for r in review._previous(opened.read_bytes()) if r['row_id'] == self.target['row_id'])
        self.assertEqual([row[k] for k in review.EDITABLE], ['open', '', ''])
        odd_note = '  =SUM(1,2)\r\n\nTab\there; ESC:\x1b[31m; ☃  '
        out = self.annotate('literal.csv', status='in_progress', note=odd_note)
        listed = json.loads(self.command('worksheet', 'list', '--worksheet', out,
                                         '--status', 'in_progress', '--json').stdout)
        self.assertEqual(listed['rows'][0]['note'], odd_note)
        text = self.command('worksheet', 'list', '--worksheet', out, '--status', 'in_progress').stdout
        self.assertIn('\\u001b[31m', text)
        self.assertNotIn('\x1b', text)
        self.assertIn(self.target['row_id'], text)

    def test_each_nonopen_state_requires_reviewer_and_note(self):
        for status in ('in_progress', 'reviewed'):
            for reviewer, note in (('', 'context'), ('Alice', ''), (' ', '\n')):
                with self.subTest(status=status, reviewer=reviewer, note=note):
                    out = self.root / 'refused.csv'
                    result = self.command('worksheet', 'annotate', '--worksheet', self.file,
                        '--row-id', self.target['row_id'], '--status', status,
                        '--reviewer', reviewer, '--note', note, '--out', out, status=2)
                    self.assertIn('both reviewer and note', result.stderr)
                    self.assertFalse(out.exists())
        self.assertEqual(self.file.read_bytes(), self.source)

    def test_unknown_manifest_and_partial_row_ids_are_not_selections(self):
        for row_id in ('missing', 'manifest', self.target['row_id'][:8], self.target['finding_id']):
            with self.subTest(row_id=row_id):
                out = self.root / 'refused.csv'
                self.command('worksheet', 'annotate', '--worksheet', self.file, '--row-id', row_id,
                             '--status', 'reviewed', '--reviewer', 'A', '--note', 'N', '--out', out, status=2)
                self.assertFalse(out.exists())
        self.assertEqual(self.file.read_bytes(), self.source)

    def test_history_keeps_its_note_and_cannot_supply_an_annotation_target(self):
        target = next(r for r in self.rows if r['code'] == 'LATE_FEE_OR_PAST_DUE')
        annotated = self.annotate(row=target['row_id'])
        changed_data = self.root / 'changed-data'
        shutil.copytree(self.base / 'data', changed_data)
        with (changed_data / 'bills.csv').open(newline='', encoding='utf-8') as source:
            reader = csv.DictReader(source)
            headers, records = reader.fieldnames, list(reader)
        changed = [r for r in records if r['account_no'] == target['account_no'] and r['bill_id'] == target['finding_key']]
        self.assertEqual(len(changed), 1)
        changed[0]['late_fee'] = str(float(changed[0]['late_fee']) + 10)
        with (changed_data / 'bills.csv').open('w', newline='', encoding='utf-8') as dest:
            writer = csv.DictWriter(dest, fieldnames=headers)
            writer.writeheader(); writer.writerows(records)
        report = self.root / 'changed-report'
        self.command('run', '--data', changed_data, '--out', report)
        reconciled = self.root / 'new-evidence.csv'
        self.command('review', '--data', changed_data, '--report', report / 'summary.json',
                     '--previous', annotated, '--out', reconciled)
        current = json.loads(self.command('worksheet', 'list', '--worksheet', reconciled, '--json').stdout)
        all_rows = json.loads(self.command('worksheet', 'list', '--worksheet', reconciled,
                                          '--include-history', '--json').stdout)
        historical = next(r for r in all_rows['rows'] if r['row_id'] == target['row_id'])
        self.assertEqual(historical['row_state'], 'changed')
        self.assertEqual(historical['review_status'], 'reviewed')
        self.assertNotIn(historical, current['rows'])
        renewed = next(r for r in current['rows'] if r['finding_id'] == target['finding_id'])
        self.assertEqual([renewed[k] for k in review.EDITABLE], ['open', '', ''])
        out = self.root / 'history-refused.csv'
        self.command('worksheet', 'annotate', '--worksheet', reconciled, '--row-id', historical['row_id'],
                     '--status', 'reviewed', '--reviewer', 'B', '--note', 'Changed', '--out', out, status=2)
        self.assertFalse(out.exists())

    def test_same_bill_id_in_two_native_accounts_keeps_exact_row_selection(self):
        data = self.root / 'two-accounts'
        data.mkdir()
        sources = {
            'accounts.csv': ('account_no,property,utility,vendor,scope,unit,cycle',
                [('A', 'Shared property', 'gas', 'Example vendor', 'common', '', 'monthly'),
                 ('B', 'Shared property', 'gas', 'Example vendor', 'common', '', 'monthly')]),
            'bills.csv': ('bill_id,account_no,vendor_invoice_no,period_start,period_end,usage,usage_unit,amount,late_fee,prior_balance,due_date,received_date',
                [('BASE', a, 'BASE', '2025-09-01', '2025-09-30', '100', 'therm', '100', '0', '0', '2025-10-20', '2025-10-01') for a in ('A', 'B')] +
                [('SHARED', a, 'INV', '2026-09-01', '2026-09-30', '100', 'therm', '100', '5', '0', '2026-10-20', '2026-10-01') for a in ('A', 'B')]),
            'occupancy.csv': ('property,unit,status,from,to', []),
            'payments.csv': ('payment_id,account_no,vendor_invoice_no,amount,paid_date', []),
        }
        for name, (header, rows) in sources.items():
            with (data / name).open('w', newline='', encoding='utf-8') as out:
                writer = csv.writer(out); writer.writerow(header.split(',')); writer.writerows(rows)
        report, source = self.root / 'two-report', self.root / 'two-review.csv'
        self.command('run', '--data', data, '--out', report, '--as-of', '2026-10-08', '--eval-from', '2026-09-01')
        self.command('review', '--data', data, '--report', report / 'summary.json', '--out', source)
        twins = [r for r in review._previous(source.read_bytes()) if r['finding_key'] == 'SHARED' and r['code'] == 'LATE_FEE_OR_PAST_DUE']
        self.assertEqual({r['account_no'] for r in twins}, {'A', 'B'})
        first = next(r for r in twins if r['account_no'] == 'A')
        out = self.annotate('two-annotated.csv', source=source, row=first['row_id'])
        after = review._previous(out.read_bytes())
        self.assertEqual(next(r for r in after if r['row_id'] == first['row_id'])['review_status'], 'reviewed')
        other_id = next(r['row_id'] for r in twins if r['account_no'] == 'B')
        other = next(r for r in after if r['row_id'] == other_id)
        self.assertEqual([other[k] for k in review.EDITABLE], ['open', '', ''])

    def test_noncanonical_csv_keeps_all_other_annotation_cells_exact(self):
        rows = list(reversed(self.rows))
        other = next(r for r in rows if r['row_state'] == 'current' and r['row_id'] != self.target['row_id'])
        other.update(review_status=' reviewed ', reviewer=' Older\r\nAnalyst ',
                     note=' Prior "decision", kept\r\nwith mixed\nnewlines. 雪 ')
        buffer = io.StringIO(newline='')
        writer = csv.DictWriter(buffer, fieldnames=list(reversed(review.COLUMNS)), lineterminator='\r\n')
        writer.writeheader(); writer.writerows(rows)
        self.source = b'\xef\xbb\xbf' + buffer.getvalue().encode('utf-8')
        self.file.write_bytes(self.source)
        review._previous(self.source)
        out = self.annotate(reviewer='New reviewer', note='New\r\nnote')
        self.assert_only_annotation(out, self.target['row_id'],
                                   {'review_status': 'reviewed', 'reviewer': 'New reviewer', 'note': 'New\r\nnote'})

    def test_full_validation_precedes_filtering_or_annotation(self):
        original_rows = cells(self.file)
        invalid = dict(original_rows[0]); invalid['account_no'] = 'changed identity'
        damaged = self.root / 'damaged.csv'
        damaged.write_bytes(worksheet._serialize([invalid, *original_rows[1:]]))
        frozen = damaged.read_bytes()
        for args in [
            ('worksheet', 'list', '--worksheet', damaged, '--account', 'no-match', '--json'),
            ('worksheet', 'annotate', '--worksheet', damaged, '--row-id', self.target['row_id'],
             '--status', 'reviewed', '--reviewer', 'A', '--note', 'N', '--out', self.root / 'invalid-out.csv'),
        ]:
            result = self.command(*args, status=2)
            self.assertEqual(result.stdout, '')
            self.assertIn('protected finding columns changed', result.stderr)
        self.assertEqual(damaged.read_bytes(), frozen)
        self.assertFalse((self.root / 'invalid-out.csv').exists())

    def test_missing_manifest_duplicate_rows_and_bad_csv_refuse_publication(self):
        for name, raw in [
            ('missing', worksheet._serialize(self.rows[:-1])),
            ('duplicate', worksheet._serialize([self.rows[0], *self.rows])),
            ('utf8', b'\xff'), ('csv', b'"unterminated'),
        ]:
            with self.subTest(name=name):
                source, out = self.root / (name + '.csv'), self.root / (name + '-out.csv')
                source.write_bytes(raw)
                self.command('worksheet', 'annotate', '--worksheet', source, '--row-id', self.target['row_id'],
                             '--status', 'reviewed', '--reviewer', 'A', '--note', 'N', '--out', out, status=2)
                self.assertEqual(source.read_bytes(), raw)
                self.assertFalse(out.exists())

    def test_existing_output_input_and_symlink_destinations_are_preserved(self):
        other = self.root / 'existing.csv'; other.write_bytes(b'previous result')
        link = self.root / 'link.csv'; link.symlink_to(other)
        dangling = self.root / 'dangling.csv'; dangling.symlink_to(self.root / 'absent.csv')
        for out in (self.file, other, link, dangling):
            with self.subTest(out=out.name):
                self.command('worksheet', 'annotate', '--worksheet', self.file,
                             '--row-id', self.target['row_id'], '--status', 'reviewed',
                             '--reviewer', 'A', '--note', 'N', '--out', out, status=2)
        self.assertEqual(self.file.read_bytes(), self.source)
        self.assertEqual(other.read_bytes(), b'previous result')
        self.assertTrue(link.is_symlink())
        self.assertTrue(dangling.is_symlink())
        self.assertFalse((self.root / 'absent.csv').exists())

    def test_input_change_during_validation_preserves_new_input_and_refuses_output(self):
        validate, count = review._previous, 0
        def replace_after_validation(raw):
            nonlocal count
            result = validate(raw)
            count += 1
            if count == 2:
                self.file.write_bytes(self.source + b'\n')
            return result
        out = self.root / 'stale.csv'
        with mock.patch.object(review, '_previous', side_effect=replace_after_validation):
            with self.assertRaisesRegex(ValueError, 'changed during annotation'):
                worksheet.annotate(self.file, out, row_id=self.target['row_id'],
                                   status='reviewed', reviewer='A', note='N')
        self.assertFalse(out.exists())
        self.assertEqual(self.file.read_bytes(), self.source + b'\n')

    def test_native_publisher_refuses_raced_destination_and_cleans_its_stage(self):
        out = self.root / 'raced.csv'
        link = review.os.link
        def race(source, dest):
            Path(dest).write_bytes(b'other writer result')
            return link(source, dest)
        with mock.patch.object(review.os, 'link', side_effect=race):
            with self.assertRaises(FileExistsError):
                worksheet.annotate(self.file, out, row_id=self.target['row_id'],
                                   status='reviewed', reviewer='A', note='N')
        self.assertEqual(out.read_bytes(), b'other writer result')
        self.assertEqual(self.file.read_bytes(), self.source)
        self.assertEqual(list(self.root.glob('.uwatch-review-*')), [])

    def test_native_flush_failure_leaves_output_absent_and_retry_works(self):
        out = self.root / 'retry.csv'
        with mock.patch.object(review.os, 'fsync', side_effect=OSError('authored flush failure')):
            with self.assertRaisesRegex(OSError, 'authored flush failure'):
                worksheet.annotate(self.file, out, row_id=self.target['row_id'],
                                   status='reviewed', reviewer='A', note='N')
        self.assertFalse(out.exists())
        self.assertEqual(list(self.root.glob('.uwatch-review-*')), [])
        worksheet.annotate(self.file, out, row_id=self.target['row_id'],
                           status='reviewed', reviewer='A', note='N')
        self.assert_only_annotation(out, self.target['row_id'],
                                   {'review_status': 'reviewed', 'reviewer': 'A', 'note': 'N'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
