"""Independent native CLI receiving of exact evidence after a finding becomes absent.
No production imports, mocks, source edits, browser, account access or installations.
"""
import argparse, csv, hashlib, io, json, os
from pathlib import Path
import subprocess, sys, traceback

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def hashes(root):
    return {str(p.relative_to(root)): digest(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file()}

def cells(path):
    return list(csv.DictReader(io.StringIO(path.read_bytes().decode('utf-8-sig'), newline='')))

def csv_bytes(header, rows):
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerow(header.split(',')); writer.writerows(rows)
    return buffer.getvalue().encode('utf-8')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    package, out = args.package.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=False); (out / 'tmp').mkdir()
    env = dict(os.environ, PYTHONPATH=str(package), PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(out / 'tmp'))
    receipt = {'schema': 'utility-worksheet-absent-returned-independent-v1', 'reviewer': 'engine_state',
               'python': sys.version, 'package': str(package), 'source_before': hashes(package),
               'boundary': 'Actual stdlib CLI children and native checker, reconciler, worksheet and publisher on independently authored synthetic CSV. No mocks or author-suite invocation. No browser, financial account, installation or production edits.',
               'commands': [], 'checks': [], 'success': False}
    def check(label, value):
        if not value: raise AssertionError(label)
        receipt['checks'].append(label)
    def cli(*args, expected=0):
        argv = [sys.executable, '-B', '-m', 'uwatch', *map(str, args)]
        run = subprocess.run(argv, cwd=package, env=env, capture_output=True, text=True, timeout=20)
        receipt['commands'].append({'argv': argv, 'expected_exit': expected, 'exit': run.returncode,
                                    'stdout': run.stdout, 'stderr': run.stderr})
        if run.returncode != expected: raise AssertionError(receipt['commands'][-1])
        return run
    def annotate(before, after, row_id, fields, expected=0):
        return cli('worksheet', 'annotate', '--worksheet', before, '--row-id', row_id,
                   '--status', fields['review_status'], '--reviewer', fields['reviewer'],
                   '--note', fields['note'], '--out', after, expected=expected)
    def exact(before, after, row_id, fields):
        check('annotation changes exactly three selected cells; row order, protected fields, manifest, history and other reviewer cells exact',
              cells(after) == [dict(row, **fields) if row['row_id'] == row_id else row for row in cells(before)])
    try:
        data, absent_data = out / 'source-initial', out / 'source-absent'
        data.mkdir(); absent_data.mkdir()
        accounts = [('RECV-A','Authored A','gas','Example A','common','','monthly'),
                    ('RECV-B','Authored B','gas','Example B','common','','monthly')]
        header = 'bill_id,account_no,vendor_invoice_no,period_start,period_end,usage,usage_unit,amount,late_fee,prior_balance,due_date,received_date'
        bills = [[a+'-BASE','RECV-'+a,a+'-BASE-INV','2025-09-01','2025-09-30','100','therm','100','0','0','2025-10-20','2025-10-01'] for a in ('A','B')]
        bills += [[a+'-SEP','RECV-'+a,a+'-SEP-INV','2026-09-01','2026-09-30','100','therm','100','5','0','2026-10-20','2026-10-01'] for a in ('A','B')]
        raw = {'accounts.csv': csv_bytes('account_no,property,utility,vendor,scope,unit,cycle', accounts),
               'bills.csv': csv_bytes(header, bills),
               'occupancy.csv': csv_bytes('property,unit,status,from,to', []),
               'payments.csv': csv_bytes('payment_id,account_no,vendor_invoice_no,amount,paid_date', []),
               'expected.json': b'{"fixture":"independently authored synthetic receiver"}\n'}
        for name, content in raw.items():
            (data/name).write_bytes(content); (absent_data/name).write_bytes(content)
        absent_bills = [list(row) for row in bills]; absent_bills[2][8] = '0'
        (absent_data/'bills.csv').write_bytes(csv_bytes(header, absent_bills))
        report, absent_report = out/'report-initial', out/'report-absent'
        cli('run', '--data', data, '--out', report, '--as-of', '2026-10-08', '--eval-from', '2026-09-01')
        first = out/'01-initial.csv'
        cli('review', '--data', data, '--report', report/'summary.json', '--out', first)
        initial = json.loads(cli('worksheet','list','--worksheet',first,'--json').stdout)
        check('fixture has exactly two current late-fee rows with recorded synthetic context',
              initial['current']==2 and initial['history']==0 and initial['data_mode']=='synthetic'
              and {r['code'] for r in initial['rows']}=={'LATE_FEE_OR_PAST_DUE'})
        original = next(r for r in initial['rows'] if r['account_no']=='RECV-A')
        other = next(r for r in initial['rows'] if r['account_no']=='RECV-B')
        b_fields = {'review_status':'in_progress','reviewer':'  Bea, receiving analyst  ','note':' Keep this other account.\nSecond line: 雪 '}
        b_file = out/'02-other-reviewed.csv'; annotate(first,b_file,other['row_id'],b_fields); exact(first,b_file,other['row_id'],b_fields)
        old_fields = {'review_status':'reviewed','reviewer':'Original reviewer','note':'Original evidence only.\nDo not revive this decision.'}
        reviewed = out/'03-original-reviewed.csv'; annotate(b_file,reviewed,original['row_id'],old_fields); exact(b_file,reviewed,original['row_id'],old_fields)
        old_row = next(r for r in cells(reviewed) if r['row_id']==original['row_id'])
        b_row = next(r for r in cells(reviewed) if r['row_id']==other['row_id'])
        frozen = {str(p.relative_to(out)): digest(p.read_bytes()) for p in out.rglob('*') if p.is_file()}
        cli('run','--data',absent_data,'--out',absent_report,'--as-of','2026-10-08','--eval-from','2026-09-01')
        absent = out/'04-absent.csv'
        cli('review','--data',absent_data,'--report',absent_report/'summary.json','--previous',reviewed,'--out',absent)
        historic = next(r for r in cells(absent) if r['row_id']==original['row_id'])
        check('old reviewed finding becomes absent while retaining every annotation and observed evidence cell',
              historic['row_state']=='absent' and all(historic[k]==old_row[k] for k in old_row if k not in ('row_state','record_sha256')))
        check('other current account and raw reviewer cells stay exact through absence',next(r for r in cells(absent) if r['row_id']==other['row_id'])==b_row)
        absent_bytes = absent.read_bytes()
        returned = out/'05-returned.csv'
        cli('review','--data',data,'--report',report/'summary.json','--previous',absent,'--out',returned)
        current = json.loads(cli('worksheet','list','--worksheet',returned,'--account','RECV-A','--json').stdout)
        all_rows = json.loads(cli('worksheet','list','--worksheet',returned,'--include-history','--json').stdout)
        check('filtered current listing excludes history but keeps whole worksheet counts',current['shown']==1 and current['current']==2 and current['history']==1 and all_rows['shown']==3)
        renewed = current['rows'][0]
        check('identical finding and exact evidence return with a fresh current row ID',renewed['finding_id']==original['finding_id'] and renewed['evidence_version']==original['evidence_version'] and renewed['row_id']!=original['row_id'] and renewed['row_state']=='current')
        check('returned evidence starts open with no inherited reviewer or note',[renewed[k] for k in ('review_status','reviewer','note')]==['open','',''])
        check('original historical row remains cell-exact after return',next(r for r in all_rows['rows'] if r['row_id']==original['row_id'])==historic)
        check('unaffected reviewed account remains cell-exact after return',next(r for r in all_rows['rows'] if r['row_id']==other['row_id'])==b_row)
        returned_bytes = returned.read_bytes(); refused = out/'historical-must-not-publish.csv'
        failure = annotate(returned,refused,original['row_id'],old_fields,expected=2)
        check('old historical ID refuses without output or input mutation','history cannot be annotated' in failure.stderr and failure.stdout=='' and not refused.exists() and returned.read_bytes()==returned_bytes)
        new_fields = {'review_status':'reviewed','reviewer':' New current reviewer ','note':' Reviewed the returned current evidence.\nA distinct deliberate annotation. '}
        new = out/'06-returned-reviewed.csv'; annotate(returned,new,renewed['row_id'],new_fields); exact(returned,new,renewed['row_id'],new_fields)
        next_file = out/'07-reconciled-current.csv'
        cli('review','--data',data,'--report',report/'summary.json','--previous',new,'--out',next_file)
        received = json.loads(cli('worksheet','list','--worksheet',next_file,'--include-history','--json').stdout)
        received_row = next(r for r in received['rows'] if r['row_id']==renewed['row_id'])
        check('real review --previous retains the new row ID and deliberate current annotation',received_row['row_state']=='current' and all(received_row[k]==v for k,v in new_fields.items()))
        check('same-report reconciliation retains all worksheet bytes including manifest, history and other annotations',next_file.read_bytes()==new.read_bytes())
        check('original source exports, report artifacts and all earlier input worksheets remain byte-exact',all(digest((out/name).read_bytes())==pin for name,pin in frozen.items()) and absent.read_bytes()==absent_bytes and returned.read_bytes()==returned_bytes)
        check('native publisher and reconciliation leave no temporary files',not list(out.rglob('.uwatch-review-*')) and not list((out/'tmp').iterdir()))
        receipt['identities']={'original_historical_row_id':original['row_id'],'returned_current_row_id':renewed['row_id'],'finding_id':renewed['finding_id'],'equal_evidence_version':renewed['evidence_version'],'other_row_id':other['row_id']}
        receipt['success']=True
    except BaseException as error:
        receipt['failure']={'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()}
    finally:
        receipt['source_after']=hashes(package)
        if receipt['source_before']!=receipt['source_after']:
            receipt['success']=False; receipt['source_changed']=True
        receipt['command_count']=len(receipt['commands']); receipt['check_count']=len(receipt['checks'])
        receipt['artifact_sha256']=hashes(out); receipt['harness_sha256']=digest(Path(__file__).read_bytes())
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')
        print(json.dumps({'success':receipt['success'],'commands':receipt['command_count'],'checks':receipt['check_count'],'receipt':str(out/'receipt.json'),'sha256':digest((out/'receipt.json').read_bytes()),'failure':receipt.get('failure')},indent=2))
    return 0 if receipt['success'] else 1

if __name__=='__main__':
    raise SystemExit(main())
