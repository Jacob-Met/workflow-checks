from pathlib import Path
import csv,datetime,hashlib,json,subprocess,sys,platform
root=Path('/home/jacob/hamon-estate-discovery-713adaab-20261008')
source=root/'1258-freight-closure/source/freight_packets'
p=root/'1306-freight-header-baseline'
p.mkdir(mode=0o700,exist_ok=False)
def write_csv(path,fields,rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def hashes(base):
    return {str(x.relative_to(base)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(base.rglob('*')) if x.is_file()}
before=hashes(source)
variants=[('coherent',None,None,False),
 ('carrier-first-A','carrier','Fictional Carrier B',False),
 ('carrier-first-B','carrier','Fictional Carrier B',True),
 ('date-first-01','invoice_date','2026-09-10',False),
 ('date-first-10','invoice_date','2026-09-10',True),
 ('total-first-1100','invoice_total','999.00',False),
 ('total-first-999','invoice_total','999.00',True)]
report={'source_commit':'9e931fa9f42033bf2368f7149684fb5631345715','source_path':str(source),
 'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'host':platform.node(),'python':sys.version,
 'kind':'authored synthetic CLI reproduction; no owner source edit','cases':[]}
for name,field,value,reverse in variants:
    work=p/name;data=work/'data';out=work/'out';data.mkdir(parents=True);(data/'ratecons').mkdir()
    write_csv(data/'loads.csv',['load_id','customer','carrier','tractor','trailer','pod_received','ratecon_file','mode'],
      [dict(load_id='SYN-L1',customer='Fictional Shipper',carrier='Fictional Carrier A',tractor='',trailer='',pod_received='yes',ratecon_file='RC-SYN.txt',mode='brokered')])
    (data/'ratecons/RC-SYN.txt').write_text('Rate Con # RC-SYN\nLoad # SYN-L1\nCustomer: Fictional Shipper\nCarrier: Fictional Carrier A\nLinehaul: $1000.00\nFuel: $100.00\nDetention: $50.00 per hour\n2 hours free\nbilled in 15 minute increments\n15 minute late grace\nPICKUP: Fictional Dock | Appt: 2026-09-01 10:00\n',encoding='utf-8')
    write_csv(data/'tracking.csv',['load number','stop name','actual arrival','actual departure'],
      [{'load number':'SYN-L1','stop name':'Fictional Dock','actual arrival':'2026-09-01 10:00','actual departure':'2026-09-01 11:00'}])
    write_csv(data/'fines_schedule.csv',['code','description','amount','applies_to'],
      [dict(code='MISSING_PICKUP_PHOTOS',description='Authored fixture only',amount='100.00',applies_to='brokered')])
    write_csv(data/'documents.csv',['load_id','doc_type','received_at'],[])
    write_csv(data/'disputes.csv',['load_id','fine_code','received_at','reason'],
      [dict(load_id='SYN-L1',fine_code='MISSING_PICKUP_PHOTOS',received_at='2026-09-10 12:00',reason='Authored fixture only')])
    fields=['invoice_no','load_id','carrier','invoice_date','invoice_total','line_code','line_amount']
    common=dict(invoice_no='SYN-INV',load_id='SYN-L1',carrier='Fictional Carrier A',invoice_date='2026-09-01',invoice_total='1100.00')
    rows=[dict(common,line_code='LINEHAUL',line_amount='1000.00'),dict(common,line_code='FUEL',line_amount='100.00')]
    if field:rows[1][field]=value
    if reverse:rows.reverse()
    write_csv(data/'carrier_invoices.csv',fields,rows)
    (data/'README_SYNTHETIC.txt').write_text('Every entity and amount is invented for this reproduction.\n')
    ih=hashes(data)
    cmd=[sys.executable,'-B','-m','freightpkt','run','--data',str(data),'--out',str(out)]
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    proc=subprocess.run(cmd,cwd=source,capture_output=True,timeout=30)
    (work/'stdout.txt').write_bytes(proc.stdout);(work/'stderr.txt').write_bytes(proc.stderr)
    result=json.loads((out/'summary.json').read_text()) if (out/'summary.json').exists() else None
    rec={'name':name,'argv':cmd,'cwd':str(source),'started_utc':started,'returncode':proc.returncode,
      'stdout_sha256':hashlib.sha256(proc.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(proc.stderr).hexdigest(),
      'input_hashes':ih,'input_unchanged':ih==hashes(data),'output_hashes':hashes(out) if out.exists() else {},
      'settlements':result['settlements'] if result else None,'fines':result['fines'] if result else None,
      'flags':result['flags'] if result else None}
    (work/'process.json').write_text(json.dumps(rec,indent=2)+'\n')
    report['cases'].append(rec)
report['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
report['source_hashes_before']=before;report['source_hashes_after']=hashes(source)
report['source_unchanged']=report['source_hashes_before']==report['source_hashes_after']
(p/'baseline-report.json').write_text(json.dumps(report,indent=2)+'\n')
assert report['source_unchanged']
print(json.dumps({'report_path':str(p/'baseline-report.json'),'report_sha256':hashlib.sha256((p/'baseline-report.json').read_bytes()).hexdigest(),'source_unchanged':True,
 'cases':[{'name':x['name'],'returncode':x['returncode'],'input_unchanged':x['input_unchanged'],'settlements':x['settlements'],
 'fine_notice':[{'notice_date':f['notice_date'],'deadline':f['dispute_deadline'],'status':f['status'],'deducted_cents':f['deducted_cents']} for f in (x['fines'] or [])],
 'flag_codes':[f['code'] for f in (x['flags'] or [])]} for x in report['cases']]},indent=2))
