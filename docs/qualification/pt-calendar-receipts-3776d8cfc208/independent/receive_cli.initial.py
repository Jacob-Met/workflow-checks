#!/usr/bin/env python3
"""Frozen independent real-descriptor PT calendar CLI receiver."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def identity(path):
    b = path.read_bytes()
    return {'path': str(path), 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest(),
            'git_blob': hashlib.sha1(b'blob ' + str(len(b)).encode() + b'\0' + b).hexdigest(),
            'mtime_ns': path.stat().st_mtime_ns}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--cli-git', required=True)
    parser.add_argument('--main-git', required=True)
    args = parser.parse_args()
    source = args.source_dir.resolve(strict=True)
    stage = args.output_dir.absolute()
    stage.mkdir(mode=0o700)
    files = [source/'ptauth'/name for name in ['__init__.py','__main__.py','cli.py','worklist_calendar.py']]
    expected = [None, args.main_git, args.cli_git, 'e125f9ed77343fcc3d82e6d6f25a7296b0463aa7']
    for p, pin in zip(files, expected):
        if pin is not None and identity(p)['git_blob'] != pin:
            raise ValueError('source admission differs: '+str(p))
    row = {'key':'SYN-009|PAYER-雪|AUTH-7','patient_id':'SYN-009','patient_name':'Test Élodie 雪',
           'clinic':'Clinic Côte 雪 (synthetic)','payer_id':'PAYER-雪','payer_name':'Fictional payer 雪',
           'auth_no':'AUTH-7','priority':'P1','submit_by':'2026-10-20','auth_end':'2026-11-30',
           'next_visit':'2026-10-22','reasons':['AUTHORED_REVIEW'],'detail':['Literal <b>review</b>'],
           'checklist':['Authored résumé; not sent'],'evidence':['fictional.csv:row2']}
    excluded = dict(row, key='SYN-010|PAYER-雪|AUTH-8',patient_id='SYN-010',auth_no='AUTH-8',submit_by=None)
    summary = {'banner':'SYNTHETIC authored receipt control','generated_at':'2026-10-14T01:02:03Z',
               'clinic_timezone':'Europe/Paris','as_of':'2026-10-14','worklist':[row,excluded]}
    states = {row['key']:{'state':'submitted','note':'Résumé, café; 雪\nSecond line'},
              excluded['key']:{'state':'approved','note':'Excluded authored item'}}
    report = stage/'saved-report';report.mkdir()
    for name, value in [('summary.json',summary),('work_state.json',states)]:
        (report/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    token = hashlib.sha256(json.dumps(dict(summary,states=states),ensure_ascii=False,sort_keys=True,
                          separators=(',',':'),allow_nan=False).encode()).hexdigest()
    uid = hashlib.sha256(json.dumps(['ptauth-submit-by-v1',row['key'],row['clinic'],row['auth_end'],
                                    summary['clinic_timezone']],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    watched = files + [Path(__file__).resolve(), Path(__file__).with_name('PROTOCOL.md').resolve(),
                       report/'summary.json',report/'work_state.json']
    before = [identity(p) for p in watched]
    checks = []; children = []
    def check(name, result):
        checks.append({'name':name,'passed':bool(result)})
        if not result: raise AssertionError(name)
    def inspect_ics(name, output):
        raw=output.read_bytes(); lines=raw.split(b'\r\n')
        check(name+'.CRLF_complete',raw.endswith(b'END:VCALENDAR\r\n') and all(b'\n' not in s and b'\r' not in s for s in lines))
        check(name+'.UTF8_fold_bounds',all(len(line)<=75 for line in lines))
        logical=raw.replace(b'\r\n ',b'').decode('utf-8')
        check(name+'.one_event',logical.count('BEGIN:VEVENT\r\n')==1 and logical.count('END:VEVENT\r\n')==1)
        check(name+'.manual_UID',f'UID:{uid}@ptauth.workflow-checks.invalid\r\n' in logical)
        check(name+'.manual_date','DTSTART;VALUE=DATE:20261020\r\n' in logical)
        check(name+'.literal_UTF8','Test Élodie 雪' in logical and 'Résumé\\, café\\; 雪\\nSecond line' in logical)
        check(name+'.excluded_absent','SYN-010' not in logical and 'AUTH-8' not in logical)
        return identity(output)
    def run(name, entry, encoding, closed=False, occupied=False):
        output=stage/(name+'-雪.ics')
        if occupied: output.write_bytes(b'authored existing calendar\n')
        old=identity(output) if occupied else None
        env=os.environ.copy();env['PYTHONIOENCODING']=encoding+':strict';env['PYTHONDONTWRITEBYTECODE']='1'
        cmd=[sys.executable,'-B','-m',entry,'calendar','--report',str(report),'--output',str(output)]
        fd=None
        if closed:
            read_fd,fd=os.pipe();os.close(read_fd)
        start=time.monotonic_ns(); process=None;timed_out=False
        try:
            process=subprocess.Popen(cmd,cwd=source,env=env,stdout=fd if closed else subprocess.PIPE,stderr=subprocess.PIPE)
        finally:
            if fd is not None: os.close(fd)
        try: stdout,stderr=process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            timed_out=True;process.kill();stdout,stderr=process.communicate(timeout=5)
        stdout=stdout or b''
        (stage/(name+'.stdout')).write_bytes(stdout);(stage/(name+'.stderr')).write_bytes(stderr)
        record={'name':name,'command':cmd,'pid':process.pid,'exit_code':process.returncode,
                'elapsed_ns':time.monotonic_ns()-start,'timed_out':timed_out,'reaped':process.poll() is not None}
        children.append(record)
        check(name+'.bounded_reaped',not timed_out and record['reaped'])
        check(name+'.exit',process.returncode==(2 if closed or occupied else 0))
        check(name+'.no_traceback',b'Traceback' not in stderr and b'Exception ignored' not in stderr)
        if closed:
            check(name+'.retained_message',stderr.isascii() and b'calendar' in stderr.lower() and b'created' in stderr.lower() and b'receipt' in stderr.lower())
            record['output']=inspect_ics(name,output)
        elif occupied:
            check(name+'.no_success',stdout==b'')
            check(name+'.ascii_error',stderr.isascii() and len(stderr)>0)
            check(name+'.existing_exact',identity(output)==old)
        else:
            check(name+'.one_JSON_LF',stdout.endswith(b'\n') and stdout.count(b'\n')==1)
            if encoding=='ascii': check(name+'.actual_ASCII_stdout',stdout.isascii())
            result=json.loads(stdout)
            expected_result={'format':'ptauth-submit-by-v1','snapshot':token,'as_of':'2026-10-14',
                'clinic_timezone':'Europe/Paris','selected':2,'events':1,
                'excluded':[{'key':excluded['key'],'patient_id':'SYN-010','state':'approved','reasons':['undated','completed_state']}],
                'undated':1,'completed_state':1,'output':str(output)}
            check(name+'.exact_decoded_receipt',result==expected_result)
            check(name+'.stderr_empty',stderr==b'')
            record['output']=inspect_ics(name,output)
    failure=None
    try:
        run('canonical-utf8','ptauth','utf-8')
        run('direct-ascii','ptauth.cli','ascii')
        run('canonical-closed','ptauth','ascii',closed=True)
        run('direct-closed','ptauth.cli','ascii',closed=True)
        run('occupied-ascii','ptauth','ascii',occupied=True)
        check('no_temp_files',not list(stage.glob('.ptauth-calendar-*')))
    except Exception as error: failure=f'{type(error).__name__}: {error}'
    after=[identity(p) for p in watched]
    checks.append({'name':'eight_source_input_byte_ns_records_preserved','passed':before==after})
    receipt={'schema':'ptauth.calendar.receipt-independent/1','scope':'Five real CLI processes; authored saved report, no engine/browser',
             'children':children,'checks':checks,'failure':failure,'source_before':before,'source_after':after,
             'passed':failure is None and all(x['passed'] for x in checks)}
    (stage/'receiving.json').write_text(json.dumps(receipt,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':receipt['passed'],'checks':len(checks),'children':len(children),'receipt':str(stage/'receiving.json')}))
    return 0 if receipt['passed'] else 1


if __name__=='__main__': raise SystemExit(main())
