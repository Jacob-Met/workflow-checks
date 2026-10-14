"""Focused public output-channel controls; authored saved JSON, no report engine."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(os.environ.get('PT_CALENDAR_SOURCE', Path(__file__).resolve().parents[1])).resolve()
sys.path.insert(0, str(SOURCE))
from ptauth import cli


class FailedStream:
    def __init__(self, operation):
        self.operation = operation
        self.parts = []
    def write(self, value):
        if self.operation == 'write':
            raise OSError('Authored unavailable output')
        self.parts.append(value)
        return len(value)
    def flush(self):
        if self.operation == 'flush':
            raise OSError('Authored failed flush')


class CalendarReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pt-calendar-receipt-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report = self.root / 'saved'
        self.report.mkdir()
        def row(patient, day):
            return {'key': patient + '|DEMO|AUTH', 'patient_id': patient,
                    'patient_name': 'Fictional test', 'payer_id': 'DEMO', 'payer_name': 'Fictional',
                    'auth_no': 'AUTH', 'clinic': 'Test clinic 雪', 'priority': 'P2',
                    'submit_by': day, 'auth_end': None, 'next_visit': None,
                    'reasons': ['Authored test'], 'detail': [], 'checklist': [], 'evidence': []}
        self.rows = [row('DEMO-ONE', '2026-10-21'), row('DEMO-雪', None)]
        summary = {'banner': 'SYNTHETIC fixture only', 'as_of': '2026-10-14',
                   'generated_at': '2026-10-14T00:00:00Z', 'clinic_timezone': 'UTC', 'worklist': self.rows}
        states = {self.rows[1]['key']: {'state': 'n/a', 'note': 'Authored excluded item'}}
        for name, doc in [('summary.json', summary), ('work_state.json', states)]:
            (self.report / name).write_bytes((json.dumps(doc, ensure_ascii=False) + '\n').encode('utf-8'))
        self.inputs = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.report.iterdir()}

    def tearDown(self):
        self.assertEqual(self.inputs, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.report.iterdir()})
        self.assertFalse(list(self.root.glob('.ptauth-calendar-*')))

    def args(self, output, *extra):
        return ['calendar', '--report', str(self.report), '--output', str(output), *extra]

    def process(self, module, output, encoding='utf-8', closed=False, extra=()):
        env = {**os.environ, 'PYTHONIOENCODING': encoding + ':strict', 'PYTHONDONTWRITEBYTECODE': '1'}
        env.pop('PYTHONUNBUFFERED', None)
        write_fd = None
        if closed:
            read_fd, write_fd = os.pipe()
            os.close(read_fd)
        try:
            child = subprocess.Popen([sys.executable, '-B', '-m', module, *self.args(output, *extra)],
                                     cwd=SOURCE, env=env, stdin=subprocess.DEVNULL,
                                     stdout=write_fd if closed else subprocess.PIPE, stderr=subprocess.PIPE)
        finally:
            if write_fd is not None:
                os.close(write_fd)
        try:
            out, err = child.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate()
            self.fail('Owned calendar subprocess exceeded ten seconds')
        return child.returncode, out or b'', err

    def calendar(self, output):
        raw = output.read_bytes()
        self.assertTrue(raw.startswith(b'BEGIN:VCALENDAR\r\n'))
        self.assertTrue(raw.endswith(b'END:VCALENDAR\r\n'))
        self.assertNotIn(b'\n', raw.replace(b'\r\n', b''))
        physical = raw[:-2].split(b'\r\n')
        for line in physical:
            self.assertLessEqual(len(line), 75)
            line.decode('utf-8')
        logical = raw.replace(b'\r\n ', b'').decode('utf-8')
        self.assertEqual(logical.count('BEGIN:VEVENT\r\n'), 1)
        self.assertIn('DTSTART;VALUE=DATE:20261021\r\n', logical)
        self.assertIn('Test clinic 雪', logical)
        self.assertNotIn('DEMO-雪', logical)

    def receipt(self, raw, output):
        self.assertEqual(raw.count(b'\n'), 1)
        self.assertTrue(raw.endswith(b'\n'))
        value = json.loads(raw)
        self.assertEqual([value[k] for k in ('selected', 'events', 'undated', 'completed_state')], [2, 1, 1, 1])
        self.assertEqual(value['output'], str(output))
        self.assertEqual(value['excluded'], [{'key': self.rows[1]['key'], 'patient_id': 'DEMO-雪',
                                             'state': 'n/a', 'reasons': ['undated', 'completed_state']}])

    def test_ordinary_unicode_receipt_and_complete_calendar(self):
        output = self.root / 'ordinary-雪.ics'
        code, out, err = self.process('ptauth', output)
        self.assertEqual((code, err), (0, b''))
        self.receipt(out, output)
        self.calendar(output)

    def test_real_ascii_receipts_on_both_entrypoints(self):
        for module in ('ptauth', 'ptauth.cli'):
            with self.subTest(module=module):
                output = self.root / (module + '-雪.ics')
                code, out, err = self.process(module, output, 'ascii')
                self.assertEqual((code, err), (0, b''))
                self.assertTrue(out.isascii())
                self.receipt(out, output)
                self.calendar(output)

    @unittest.skipUnless(os.name == 'posix', 'real inherited preclosed pipe control is POSIX')
    def test_real_closed_stdout_returns_two_without_shutdown_retry(self):
        for module in ('ptauth', 'ptauth.cli'):
            with self.subTest(module=module):
                output = self.root / (module + '-closed.ics')
                code, out, err = self.process(module, output, 'ascii', closed=True)
                self.assertEqual(code, 2)
                self.assertNotIn(b'Exception ignored', err)
                self.assertNotIn(b'Traceback', err)
                self.assertTrue(err.isascii())
                self.assertIn(b'created', err.lower())
                self.assertIn(b'receipt', err.lower())
                self.calendar(output)

    def test_existing_unicode_destination_ascii_refusal_preserves_it(self):
        output = self.root / 'occupied-雪.ics'
        output.write_bytes(b'previous authored artifact')
        before = (output.read_bytes(), output.stat().st_mtime_ns)
        code, out, err = self.process('ptauth', output, 'ascii')
        self.assertEqual((code, out), (2, b''))
        self.assertTrue(err and err.isascii())
        self.assertNotIn(b'Traceback', err)
        self.assertEqual((output.read_bytes(), output.stat().st_mtime_ns), before)

    def test_unmatched_selection_refuses_without_output(self):
        output = self.root / 'absent.ics'
        code, out, err = self.process('ptauth', output, extra=('--clinic', 'No such fictional clinic'))
        self.assertEqual((code, out, output.exists()), (2, b'', False))
        self.assertIn(b'No dated', err)

    def test_imported_main_write_failure_keeps_caller_stdout_and_calendar(self):
        output = self.root / 'write-failure.ics'
        stream, errors = FailedStream('write'), io.StringIO()
        policy = sys.dont_write_bytecode
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(errors):
            code = cli.main(self.args(output))
            self.assertIs(sys.stdout, stream)
            self.assertEqual(sys.dont_write_bytecode, policy)
        self.assertEqual(code, 2)
        self.assertIn('created', errors.getvalue())
        self.calendar(output)

    def test_imported_main_flush_failure_keeps_caller_stdout_and_calendar(self):
        output = self.root / 'flush-failure.ics'
        stream, errors = FailedStream('flush'), io.StringIO()
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(errors):
            code = cli.main(self.args(output))
            self.assertIs(sys.stdout, stream)
        self.assertEqual(code, 2)
        self.assertIn('receipt', errors.getvalue())
        self.calendar(output)

    def test_failed_stderr_does_not_obscure_output_failure_status(self):
        output = self.root / 'both-fail.ics'
        stream, errors = FailedStream('write'), FailedStream('write')
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(errors):
            code = cli.main(self.args(output))
            self.assertIs(sys.stdout, stream)
            self.assertIs(sys.stderr, errors)
        self.assertEqual(code, 2)
        self.calendar(output)


if __name__ == '__main__':
    unittest.main()
