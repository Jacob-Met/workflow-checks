from pathlib import Path
import hashlib,json,subprocess,time,xml.etree.ElementTree as ET
root=Path('/dev/shm/hamon-b890f0b1bfcd-pt-receiving')
original=root/'receiving-v1'
out=root/'print-addendum-v1'
out.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={str(p.relative_to(original)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(original.rglob('*')) if p.is_file()}
(out/'original-v1-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
pdf=original/'browser/complete-digest.pdf'
assert sha(pdf)=='0dd860d2e5b04511fa8771932536e9c48ee22c6982b73320e33e9c5f5a0384d3'
report={'source_pin':'055c863a9484adb1f6f39f54bf6cce90825bf0ad','pdf_sha256':sha(pdf),'original_layout_scan_all_thirteen':False,'reason_for_addendum':'The preserved -layout scan interleaves neighboring columns between wrapped words. Raw PDF reading order and word geometry test the same exact literal identifiers without changing the generated PDF.','processes':[]}
for cmd in [
 ['pdftotext','-raw',str(pdf),str(out/'complete-digest-raw.txt')],
 ['pdftotext','-bbox',str(pdf),str(out/'complete-digest-bbox.html')],
 ['pdftoppm','-f','2','-l','3','-scale-to','1400','-png',str(pdf),str(out/'complete-digest-page')]]:
 p=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
 report['processes'].append({'command':cmd,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
 assert p.returncode==0
config=json.loads((original/'config.json').read_text())
expected=json.loads(Path(config['expect_path']).read_text())
raw=(out/'complete-digest-raw.txt').read_text()
fold=''.join(raw.split())
rows=[{'visit_id':r['visit_id'],'present_in_raw_reading_order':''.join(r['visit_id'].split()) in fold} for r in expected['expected_records']]
report['records']=rows
report['all_thirteen_exact_ids_present']=all(r['present_in_raw_reading_order'] for r in rows)
rootxml=ET.parse(out/'complete-digest-bbox.html').getroot()
ns={'h':'http://www.w3.org/1999/xhtml'}
pages=rootxml.findall('.//h:page',ns)
geometry=[]
for i,page in enumerate(pages,1):
 w=float(page.attrib['width']);h=float(page.attrib['height']);words=page.findall('.//h:word',ns)
 outside=[]
 for word in words:
  a=word.attrib
  if float(a['xMin'])<0 or float(a['yMin'])<0 or float(a['xMax'])>w or float(a['yMax'])>h:outside.append({'text':word.text,'bbox':a})
 geometry.append({'page':i,'width_pt':w,'height_pt':h,'words':len(words),'outside_page':outside,'leftmost_pt':min(float(x.attrib['xMin']) for x in words),'rightmost_pt':max(float(x.attrib['xMax']) for x in words),'smallest_word_height_pt':min(float(x.attrib['yMax'])-float(x.attrib['yMin']) for x in words)})
report['pdf_geometry']=geometry
report['all_words_inside_page']=all(not p['outside_page'] for p in geometry)
report['pdf_unchanged']=sha(pdf)==report['pdf_sha256']
report['created_at']=time.time()
report['status']='pass' if report['all_thirteen_exact_ids_present'] and report['all_words_inside_page'] and report['pdf_unchanged'] else 'fail'
(out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':report['status'],'all_thirteen':report['all_thirteen_exact_ids_present'],'all_words_inside_page':report['all_words_inside_page'],'report':str(out/'report.json'),'sha256':sha(out/'report.json')}),flush=True)
