from __future__ import annotations
from pathlib import Path
import hashlib,json,os,subprocess,sys,threading,time,traceback
from http.server import ThreadingHTTPServer
root=Path('/dev/shm/hamon-b890f0b1bfcd-pt-receiving')
evidence=root/'receiving-v2'
evidence.mkdir()
original=root/'receiving-v1'
config_original=json.loads((original/'config.json').read_text())
config_original['evidence']=str(evidence)
(evidence/'config.json').write_text(json.dumps(config_original,indent=2)+'\n')
(evidence/'watched-before.json').write_bytes((original/'watched-before.json').read_bytes())
config=json.loads((evidence/'config.json').read_text())
source=Path(config['source'])
sys.path.insert(0,str(source/'pt_auth'))
from ptauth.web import App,make_handler
receipt={'source_head':'055c863a9484adb1f6f39f54bf6cce90825bf0ad','started_at':time.time(),'status':'starting','requests':[]}
receipt_path=evidence/'execution.json'
def save():receipt_path.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n')
servers=[];ports={}
try:
 for name in ['normal','legacy','empty']:
  data=config['empty_inputs'] if name=='empty' else config['inputs']
  app=App(Path(data),Path(config['outputs'][name]),clinic_timezone='UTC')
  app.summary()
  base=make_handler(app)
  def make_logging(base,name):
   class Logging(base):
    def do_GET(self):
     receipt['requests'].append({'fixture':name,'method':'GET','path':self.path})
     return super().do_GET()
    def do_POST(self):
     receipt['requests'].append({'fixture':name,'method':'POST','path':self.path})
     return super().do_POST()
   return Logging
  server=ThreadingHTTPServer(('127.0.0.1',0),make_logging(base,name));server.daemon_threads=True
  ports[name]=server.server_address[1];servers.append(server)
  threading.Thread(target=server.serve_forever,daemon=True).start()
 (evidence/'ports.json').write_text(json.dumps(ports,indent=2)+'\n')
 receipt['ports']=ports;receipt['status']='browser_running';save()
 with (evidence/'browser.stdout.txt').open('x') as stdout,(evidence/'browser.stderr.txt').open('x') as stderr:
  run=subprocess.run(['node',str(root/'receive_browser_v2.cjs'),str(evidence/'config.json'),str(evidence/'ports.json')],stdout=stdout,stderr=stderr,timeout=180)
 receipt['browser_returncode']=run.returncode
 browser_dir=evidence/'browser';pdf=browser_dir/'complete-digest.pdf'
 if pdf.exists():
  checks=[]
  for cmd in [['pdftotext','-layout',str(pdf),str(browser_dir/'complete-digest.txt')],['pdfinfo',str(pdf)],['pdftoppm','-f','1','-singlefile','-scale-to','1400','-png',str(pdf),str(browser_dir/'complete-digest-page1')]]:
   p=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
   checks.append({'command':cmd,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
  receipt['pdf_processes']=checks
  if (browser_dir/'complete-digest.txt').exists():
   expected=json.loads(Path(config['expect_path']).read_text())
   text=(browser_dir/'complete-digest.txt').read_text()
   folded=''.join(text.split())
   pdf_rows=[{'visit_id':r['visit_id'],'text_present':''.join(r['visit_id'].split()) in folded} for r in expected['expected_records']]
   receipt['pdf_record_text']=pdf_rows;receipt['pdf_all_thirteen_present']=all(r['text_present'] for r in pdf_rows)
 before=json.loads((evidence/'watched-before.json').read_text())
 changed=[];missing=[]
 for name,pin in before.items():
  p=Path(name)
  if not p.is_file():missing.append(name)
  elif hashlib.sha256(p.read_bytes()).hexdigest()!=pin['sha256']:changed.append(name)
 receipt['watched_files']=len(before);receipt['changed_files']=changed;receipt['missing_files']=missing
 receipt['source_status']=subprocess.check_output(['git','status','--porcelain'],cwd=source,text=True)
 receipt['baseline_status']=subprocess.check_output(['git','status','--porcelain'],cwd=root/'baseline',text=True)
 receipt['all_watched_inputs_outputs_unchanged']=not changed and not missing
 receipt['all_requests_get']=all(x['method']=='GET' for x in receipt['requests'])
 receipt['status']='complete'
except BaseException as e:
 receipt['status']='error';receipt['error']={'type':type(e).__name__,'text':str(e),'traceback':traceback.format_exc()}
finally:
 for server in servers:server.shutdown();server.server_close()
 receipt['all_private_servers_closed']=True;receipt['completed_at']=time.time();save()
 print(json.dumps({'status':receipt['status'],'browser_returncode':receipt.get('browser_returncode'),'pdf_all_thirteen_present':receipt.get('pdf_all_thirteen_present'),'unchanged':receipt.get('all_watched_inputs_outputs_unchanged'),'receipt':str(receipt_path),'sha256':hashlib.sha256(receipt_path.read_bytes()).hexdigest()}),flush=True)
