from pathlib import Path
import csv,hashlib,io,json,os,shutil,subprocess,sys,datetime
root=Path(__file__).parent
source=root/'baseline'
out=root/'baseline-witness'
out.mkdir(exist_ok=False)
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
cases=[
 ('schedule.csv','status','Status','cancelled'),
 ('authorizations.csv','visits_authorized','Visits-Authorized','100'),
 ('payers.csv','requires_auth',' Requires Auth ','N'),
 ('patients.csv','patient_id','patient_id','SYN-ALIAS'),
]
results=[]
for n,(filename,original,duplicate,value) in enumerate(cases):
 case=out/str(n+1); inputs=case/'data'; output=case/'out'
 shutil.copytree(source/'pt_auth/sample_data',inputs);output.mkdir()
 path=inputs/filename
 rows=list(csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig'),newline='')))
 assert original in rows[0]
 rows[0].append(duplicate)
 for row in rows[1:]:
  if any(row):row.append(value)
 stream=io.StringIO(newline='');csv.writer(stream,lineterminator='\r\n').writerows(rows);path.write_bytes(stream.getvalue().encode())
 for name in ['summary.json','digest.html','audit.jsonl','sentinel.bin']:(output/name).write_bytes(b'previous-report-do-not-replace\n')
 before={p.name:digest(p) for p in output.iterdir()}
 input_before={p.name:digest(p) for p in inputs.iterdir() if p.is_file()}
 command=[sys.executable,'-B','-m','ptauth','run','--data',str(inputs),'--out',str(output),'--as-of','2026-09-28']
 r=subprocess.run(command,cwd=source/'pt_auth',capture_output=True,text=True,timeout=20)
 (case/'stdout.txt').write_text(r.stdout);(case/'stderr.txt').write_text(r.stderr)
 after={p.name:digest(p) for p in output.iterdir()}
 input_after={p.name:digest(p) for p in inputs.iterdir() if p.is_file()}
 item={'file':filename,'original_header':original,'duplicate_header':duplicate,'replacement_value':value,'command':command,'exit_code':r.returncode,'expected_exit':2,'refused':r.returncode==2,'outputs_unchanged':before==after,'prior_report_replaced':[k for k,v in before.items() if after.get(k)!=v],'new_outputs':sorted(set(after)-set(before)),'inputs_unchanged':input_before==input_after,'stdout_sha256':digest(case/'stdout.txt'),'stderr_sha256':digest(case/'stderr.txt')}
 results.append(item)
receipt={'source_commit':'8fe2c9270f487729af9e88f40894e1c4530f2c20','native_capture':'177f440894067ed7af69b6a5467302f4235898de','source_data_sha256':digest(source/'pt_auth/ptauth/data.py'),'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'python':sys.version,'cases':results,'refused':sum(x['refused'] for x in results),'accepted_ambiguous':sum(not x['refused'] for x in results),'all_inputs_unchanged':all(x['inputs_unchanged'] for x in results)}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt),flush=True)
