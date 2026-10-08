/**
 * Independent PT calendar browser receiver.
 * Uses exact app/server modules, native Chrome/CDP, independent original-engine CSVs,
 * completed native downloads, and no producer test or formatter as an oracle.
 * Usage: node browser_receiver.mjs BASELINE_PT_AUTH CANDIDATE_PT_AUTH FIXTURE_TEMPLATE NEW_OUTPUT
 */
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const here=path.dirname(fileURLToPath(import.meta.url));
const [baseline,candidate,template,output]=process.argv.slice(2);
for(const p of [baseline,candidate,template,output])assert(p&&path.isAbsolute(p),'absolute required paths');
const python=process.env.PT_REVIEW_PYTHON||'/opt/homebrew/bin/python3';
const chrome=process.env.PT_REVIEW_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
await fs.mkdir(output);
const profile=path.join(output,'profile'),downloadsPath=path.join(output,'downloads');
await fs.mkdir(profile);await fs.mkdir(downloadsPath);
const fixture=JSON.parse(await fs.readFile(path.join(template,'fixture-description.json'),'utf8'));
const expected=fixture.rows;
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const checks=[],exceptions=[],dialogs=[],network=[],paused=[],downloadSeen=new Map(),pending=new Map(),servers=[];
let socket,browser,browserContextId,currentId=0,phase='startup',chromeStderr='',page,baseUrl,candidateUrl;
const candidateFixture=path.join(output,'candidate-fixture');
const baselineFixture=path.join(output,'baseline-fixture');
const downloads=[],mutations=[],transport=[],childExits=[];
const receipt={schema:'pt_calendar.independent_current_composition_browser.v1',started_at:new Date().toISOString(),
  source_boundary:'Exact current-parent 33432db PT native server/UI in an isolated synthetic fixture; five focused combined calendar/uncovered boundaries and actual completed Chromium downloads. Historical full suite remains separate; no other parent, calendar importer or full repository build claim.',
  driver_sha256:sha(await fs.readFile(fileURLToPath(import.meta.url))),
  contract_sha256:'0bc7fe83e5dc587e0a6734de50d42cd6f3d53a05ebb083a429d77a6c4a1ac037',
  historical_specification_sha256:'17dbd8b0d7c729b1cb261e34375abc3dbbf266faeea0b6ebb7a07ab5a6668d7c',receiving_scope:'Five fresh combined current-parent browser cases; original historical suite not repeated',
  baseline_commit:'9e931fa9f42033bf2368f7149684fb5631345715',
  candidate_commit:'33432db05b9def1a249650c79571402400c18d15',candidate_tree:'92f2df0d4bf1f6955f46449b04f2fb191e0bd2ea',candidate_parent:'ea6ff4da45c038dd7440f83dc34d61ab245e1e52',
  control_method:'Actual Chrome DOM/control events and pointer actions; genuine Tab/Enter export activation. Race controls pause actual HTTP requests/responses through CDP Fetch. Date/select setup uses DOM values plus input/change events. Author test bodies and calendar formatter are not imported.'};
async function hashes(root){
 const entries=[];
 async function walk(dir){
  for(const entry of (await fs.readdir(dir,{withFileTypes:true})).sort((a,b)=>a.name.localeCompare(b.name))){
   const p=path.join(dir,entry.name);
   if(entry.isDirectory())await walk(p);
   else if(entry.isFile()){
    const b=await fs.readFile(p),s=await fs.stat(p);
    entries.push({path:path.relative(root,p),bytes:b.length,sha256:sha(b),mode:s.mode&0o777});
   }else throw Error('Unexpected non-file source: '+p);
  }
 }
 await walk(root);return entries;
}
const sourceBefore={baseline:await hashes(baseline),candidate:await hashes(candidate)};
const templateBefore=await hashes(template);
async function copyFixture(dest){
 await fs.mkdir(dest,{recursive:true});
 for(const n of ['data','out'])await fs.cp(path.join(template,n),path.join(dest,n),{recursive:true,force:true});
}
async function until(fn,label,timeout=15000){
 const end=Date.now()+timeout;
 while(Date.now()<end){const r=await fn();if(r)return r;await delay(50);}
 throw Error('Timed out: '+label);
}
function send(method,params={},sessionId){
 const id=++currentId;
 return new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout: '+method));},method==='Page.navigate'?40000:15000);
  pending.set(id,{resolve,reject,timer});
  socket.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));
 });
}
async function evaluate(sid,expression){
 const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true},sid);
 if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);
 return r.result.value;
}
async function serve(source,dir,label){
 await copyFixture(dir);
 const child=spawn(python,['-B',path.join(here,'serve_receiver.py'),'--source',source,'--fixture',dir],
  {env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},stdio:['ignore','pipe','pipe']});
 let stdout='',stderr='';
 child.stdout.on('data',b=>{stdout+=b;});
 child.stderr.on('data',b=>{stderr+=b;});
 child.on('exit',(code,signal)=>childExits.push({label,pid:child.pid,code,signal}));
 servers.push({child,label,read:()=>({stdout,stderr})});
 const first=await until(()=>stdout.split('\n').find(x=>x.startsWith('{"url":')),'server '+label);
 const data=JSON.parse(first);
 receipt[label+'_server']={pid:child.pid,...data};
 return data.url;
}
async function open(url,holdSummary=false){
 const {targetId}=await send('Target.createTarget',{url:'about:blank',browserContextId});
 const {sessionId}=await send('Target.attachToTarget',{targetId,flatten:true});
 await send('Runtime.enable',{},sessionId);await send('Network.enable',{},sessionId);await send('Page.enable',{},sessionId);
 await send('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},sessionId);
 let marker;
 if(holdSummary)marker=await intercept(sessionId,'/api/summary','Response');
 await send('Page.navigate',{url},sessionId);
 return{targetId,sessionId,marker};
}
async function closePage(){
 if(page){await send('Target.closeTarget',{targetId:page.targetId}).catch(()=>{});page=null;}
}
async function reset(){
 await closePage();await copyFixture(candidateFixture);
 page=await open(candidateUrl+'/');
 await until(()=>evaluate(page.sessionId,'document.querySelector("[data-calendar-download]")?.disabled===false'),'candidate ready');
 return page.sessionId;
}
async function ui(sid){
 return evaluate(sid,`(()=>({summary:document.querySelector('[data-calendar-summary]')?.textContent,
  context:document.querySelector('[data-calendar-context]')?.textContent,
  status:document.querySelector('[data-calendar-status]')?.textContent,
  disabled:document.querySelector('[data-calendar-download]')?.disabled,
  button:document.querySelector('[data-calendar-download]')?.textContent,
  shown:document.querySelector('#shown')?.textContent,
  asof:document.querySelector('#asof')?.value,
  query:document.querySelector('#q')?.value,clinic:document.querySelector('#fc')?.value,
  states:document.querySelector('#fs')?.value,
  keys:[...document.querySelectorAll('#work select[data-k]')].map(e=>e.dataset.k),
  lines:[...document.querySelectorAll('[data-calendar-list] li')].map(e=>e.textContent),
  focused:{id:document.activeElement?.id,text:document.activeElement?.textContent?.slice(0,90),
    download:document.activeElement?.hasAttribute('data-calendar-download')}}))()`);
}
async function click(sid,selector){
 const point=await evaluate(sid,'(()=>{const e=document.querySelector('+JSON.stringify(selector)+');if(!e)throw Error("Missing control");e.scrollIntoView({block:"center"});const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2,disabled:e.disabled};})()');
 assert.notEqual(point.disabled,true,selector+' enabled');
 await send('Input.dispatchMouseEvent',{type:'mousePressed',x:point.x,y:point.y,button:'left',clickCount:1},sid);
 await send('Input.dispatchMouseEvent',{type:'mouseReleased',x:point.x,y:point.y,button:'left',clickCount:1},sid);
}
async function key(sid,key,code,virtual){
 await send('Input.dispatchKeyEvent',{type:'keyDown',key,code,windowsVirtualKeyCode:virtual,...(key==='Enter'?{text:'\r',unmodifiedText:'\r'}:{})},sid);
 await send('Input.dispatchKeyEvent',{type:'keyUp',key,code,windowsVirtualKeyCode:virtual},sid);
}
async function query(sid,value){
 await evaluate(sid,"document.querySelector('#q').focus();document.querySelector('#q').select()");
 await send('Input.insertText',{text:value},sid);
 if(value==='')await evaluate(sid,"document.querySelector('#q').value='';document.querySelector('#q').dispatchEvent(new Event('input',{bubbles:true}))");
}
async function select(sid,selector,value){
 await evaluate(sid,'(()=>{const e=document.querySelector('+JSON.stringify(selector)+');e.value='+JSON.stringify(value)+';e.dispatchEvent(new Event("change",{bubbles:true}));})()');
}
async function setDate(sid,value){
 await evaluate(sid,'document.querySelector("#asof").value='+JSON.stringify(value)+';document.querySelector("#asof").dispatchEvent(new Event("input",{bubbles:true}))');
}
async function capture(sid,name,width=1280,height=900){
 await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false},sid);
 await evaluate(sid,"document.querySelector('#calendar')?.scrollIntoView({block:'start'})");
 await delay(40);
 const {data}=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},sid);
 const b=Buffer.from(data,'base64');await fs.writeFile(path.join(output,name),b);
 return{path:name,bytes:b.length,sha256:sha(b),width,height};
}
async function intercept(sid,pathname,stage){
 const marker=paused.length;
 await send('Fetch.enable',{patterns:[{urlPattern:'*'+pathname,requestStage:stage}]},sid);
 return{marker,sid,pathname,stage};
}
async function held(control){
 return until(()=>paused.slice(control.marker).find(p=>p.sessionId===control.sid&&new URL(p.request.url).pathname===control.pathname),'held '+control.pathname);
}
async function release(control,event){
 let result='continued';
 try{await send('Fetch.continueRequest',{requestId:event.requestId},control.sid);}
 catch(e){result='already aborted or retired: '+e.message;}
 await send('Fetch.disable',{},control.sid);
 transport.push({phase,path:control.pathname,stage:control.stage,status:event.responseStatusCode,result});
 await delay(100);
 return result;
}
function unescapeText(value){
 return value.replace(/\\([nN\\,;])/g,(_,c)=>c==='n'||c==='N'?'\n':c);
}
function readCalendar(bytes,rows,begin,end){
 const text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);
 assert(text.startsWith('BEGIN:VCALENDAR\r\n')&&text.endsWith('END:VCALENDAR\r\n'),'calendar envelope/CRLF');
 assert(!text.replaceAll('\r\n','').includes('\n')&&!text.replaceAll('\r\n','').includes('\r'),'CRLF only');
 const physical=text.split('\r\n').slice(0,-1);
 assert(physical.every(line=>Buffer.byteLength(line)<=75),'all physical lines at most 75 UTF-8 octets');
 const logical=[];
 for(const line of physical){if(/^[ \t]/.test(line)){assert(logical.length);logical[logical.length-1]+=line.slice(1);}else logical.push(line);}
 const events=[];let active=null;
 for(const line of logical){
  if(line==='BEGIN:VEVENT'){assert.equal(active,null);active=[];}
  else if(line==='END:VEVENT'){assert(active);events.push(active);active=null;}
  else if(active)active.push(line);
 }
 assert.equal(active,null);assert.equal(events.length,rows.length,'selected eligible event count');
 const seen=new Set(),uids={};
 const decodedEvents=events.map(lines=>{
  const entries=lines.map(line=>{const i=line.indexOf(':');assert(i>0);return{name:line.slice(0,i),value:line.slice(i+1)};});
  const content=entries.map(e=>unescapeText(e.value)).join('\n');
  const row=rows.find(r=>content.includes(r.key));
  assert(row,'event retains a selected work-item key');assert(!seen.has(row.key),'no duplicate key');seen.add(row.key);
  assert.equal(entries.find(e=>e.name==='DTSTART;VALUE=DATE')?.value,row.submit_by.replaceAll('-',''),'exact submit-by DATE');
  for(const name of ['RRULE','RDATE','EXDATE','ATTENDEE','ORGANIZER','TRIGGER','RECURRENCE-ID'])
   assert(!entries.some(e=>e.name.split(';')[0]===name),'no '+name);
  assert(!lines.includes('BEGIN:VALARM'),'no alarm');
  const stamp=entries.find(e=>e.name==='DTSTAMP')?.value;assert.match(stamp||'',/^\d{8}T\d{6}Z$/);
  const t=Date.parse(stamp.slice(0,4)+'-'+stamp.slice(4,6)+'-'+stamp.slice(6,8)+'T'+stamp.slice(9,11)+':'+stamp.slice(11,13)+':'+stamp.slice(13,15)+'Z');
  assert(t>=begin-1000&&t<=end+1000,'actual UTC export timestamp inside observed interval');
  const uid=entries.find(e=>e.name==='UID')?.value;assert(uid&&uid.length>10,'stable nonempty event identity');uids[row.key]=uid;
  for(const required of [row.key,row.patient_id,row.patient_name,row.payer_id,row.payer_name,row.auth_no,row.clinic,row.staff_state,
    fixture.clinic_timezone,...row.detail,...row.reasons,...row.evidence,...row.checklist].filter(Boolean))
   assert(content.includes(required),'literal context retained: '+required);
  return{key:row.key,uid,date:row.submit_by,staff_state:row.staff_state,stamp,properties:entries.map(e=>e.name)};
 });
 assert.equal(new Set(Object.values(uids)).size,rows.length,'distinct identities');
 return{events:decodedEvents,uids,physical_lines:physical.length,folded_lines:physical.filter(l=>/^[ \t]/.test(l)).length,
  max_line_octets:Math.max(...physical.map(l=>Buffer.byteLength(l)))};
}
async function downloadCurrent(sid,label,rows,trigger){
 const prior=new Set(downloadSeen.keys()),before=await hashes(candidateFixture),begin=Date.now();
 if(trigger)await trigger();else await click(sid,'[data-calendar-download]');
 const d=await until(()=>[...downloadSeen.values()].find(x=>!prior.has(x.guid)&&x.state==='completed'),'completed native download '+label);
 const end=Date.now(),nativePath=path.join(downloadsPath,d.guid),bytes=await fs.readFile(nativePath);
 assert.match(d.suggestedFilename,/\.ics$/i);
 const named=label+'.ics';await fs.writeFile(path.join(output,named),bytes);
 const record={label,guid:d.guid,suggested_filename:d.suggestedFilename,state:d.state,native_path:nativePath,
  received_bytes:d.receivedBytes,bytes:bytes.length,sha256:sha(bytes),artifact:named,begin_utc:new Date(begin).toISOString(),end_utc:new Date(end).toISOString()};
 downloads.push(record);
 assert.deepEqual(await hashes(candidateFixture),before,'export preserves every input/report/state/audit file');
 record.content=readCalendar(bytes,rows,begin,end);
 return record;
}
async function check(name,fn){
 phase=name;
 try{const result=await fn();checks.push({name,status:'pass',...result});console.log(JSON.stringify({check:name,status:'pass'}));}
 catch(e){checks.push({name,status:'fail',error:e.stack||String(e)});if(page)await capture(page.sessionId,'failure-'+checks.length+'.png').catch(()=>{});console.log(JSON.stringify({check:name,status:'fail',error:e.message}));}
 await fs.writeFile(path.join(output,'checks-progress.json'),JSON.stringify(checks,null,2)+'\n');
}
async function writeDrift(file,mutator,label){
 const bytes=await fs.readFile(file),obj=JSON.parse(bytes);
 mutator(obj);const revised=Buffer.from(JSON.stringify(obj,null,2)+'\n');
 await fs.writeFile(path.join(output,label+'-before.json'),bytes);
 await fs.writeFile(path.join(output,label+'-after.json'),revised);
 await fs.writeFile(file,revised);
 mutations.push({label,path:file,before_sha256:sha(bytes),after_sha256:sha(revised),purpose:'Explicit independent stale-input control; not an export side effect'});
 return bytes;
}

async function uncovered(sid){
 return evaluate(sid,`({shown:document.querySelector('#uc-shown').textContent,note:document.querySelector('#uc-note').textContent,
 rows:[...document.querySelectorAll('#uc-rows tbody tr')].map(e=>e.textContent),status:document.querySelector('#uc-status').value,
 clinic:document.querySelector('#uc-clinic').value,query:document.querySelector('#uc-search').value,
 exportText:document.querySelector('#uc-export').textContent,hidden:document.querySelector('#t-uncovered').classList.contains('hidden')})`);
}
function parseCsv(text){
 const rows=[];let row=[],field='',quoted=false;
 for(let i=0;i<text.length;i++){const c=text[i];
  if(quoted){if(c==='"'&&text[i+1]==='"'){field+='"';i++;}else if(c==='"')quoted=false;else field+=c;}
  else if(c==='"'){assert.equal(field,'');quoted=true;}
  else if(c===','){row.push(field);field='';}
  else if(c==='\n'){row.push(field.replace(/\r$/,''));rows.push(row);row=[];field='';}
  else field+=c;
 }
 assert.equal(quoted,false);if(field||row.length){row.push(field);rows.push(row);}
 const [header,...data]=rows;
 return data.filter(r=>r.some(Boolean)).map(r=>{assert.equal(r.length,header.length);return Object.fromEntries(header.map((h,i)=>[h,r[i]]));});
}
async function downloadCsv(sid,label){
 const prior=new Set(downloadSeen.keys()),before=await hashes(candidateFixture);
 await click(sid,'#uc-export a[download]');
 const d=await until(()=>[...downloadSeen.values()].find(x=>!prior.has(x.guid)&&x.state==='completed'),'completed CSV');
 const bytes=await fs.readFile(path.join(downloadsPath,d.guid)),saved=await fs.readFile(path.join(candidateFixture,'out/uncovered_visits.csv'));
 assert.match(d.suggestedFilename,/uncovered_visits\.csv$/);assert.deepEqual(bytes,saved);
 const rows=parseCsv(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
 assert.equal(rows.length,2);assert.deepEqual(rows.map(r=>r.visit_id).sort(),['VISIT-PT1005','VISIT-PT1006']);
 assert(rows.every(r=>r.status==='scheduled'));assert.deepEqual(await hashes(candidateFixture),before,'CSV preserves every fixture file');
 const artifact=label+'.csv';await fs.writeFile(path.join(output,artifact),bytes);
 const record={label,type:'csv',guid:d.guid,suggested_filename:d.suggestedFilename,state:d.state,bytes:bytes.length,sha256:sha(bytes),artifact,rows};
 downloads.push(record);return record;
}
async function captureUncovered(sid,name,width,height){
 await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:false},sid);
 await evaluate(sid,"document.querySelector('#t-uncovered').scrollIntoView({block:'start'})");await delay(40);
 const {data}=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},sid);
 const b=Buffer.from(data,'base64');await fs.writeFile(path.join(output,name),b);
 return{path:name,bytes:b.length,sha256:sha(b),width,height};
}

const eligible=expected.filter(r=>r.eligible);
try{
 const st=await fs.statfs(here);receipt.free_bytes_before=st.bavail*st.bsize;
 assert(receipt.free_bytes_before>=128*1024*1024,'at least 128 MiB for one bounded Chrome profile');
 candidateUrl=await serve(candidate,candidateFixture,'candidate');
 browser=spawn(chrome,['--headless=new','--incognito','--disable-gpu','--disable-extensions','--password-store=basic',
  '--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','--user-data-dir='+profile,
  '--disk-cache-size=1048576','--media-cache-size=1048576','--disable-background-networking','--disable-component-update',
  '--disable-default-apps','--disable-sync','--no-first-run','--no-default-browser-check','--metrics-recording-only','about:blank'],
  {stdio:['ignore','ignore','pipe']});
 browser.stderr.on('data',b=>{chromeStderr+=b;});
 browser.on('exit',(code,signal)=>childExits.push({label:'chrome',pid:browser.pid,code,signal}));
 const endpoint=await until(()=>/DevTools listening on (ws:\/\/[^\s]+)/.exec(chromeStderr)?.[1],'Chrome endpoint');
 socket=new WebSocket(endpoint);
 await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
 socket.addEventListener('message',event=>{
  const m=JSON.parse(event.data);
  if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}}
  else if(m.method==='Runtime.exceptionThrown')exceptions.push({phase,sessionId:m.sessionId,...m.params.exceptionDetails});
  else if(m.method==='Page.javascriptDialogOpening'){
   dialogs.push({phase,...m.params});
   send('Page.handleJavaScriptDialog',{accept:true},m.sessionId).catch(e=>transport.push({phase,dialogError:e.message}));
  }else if(m.method==='Network.requestWillBeSent')network.push({phase,event:'request',sessionId:m.sessionId,requestId:m.params.requestId,
   method:m.params.request.method,url:m.params.request.url,postData:m.params.request.postData});
  else if(m.method==='Network.responseReceived')network.push({phase,event:'response',sessionId:m.sessionId,requestId:m.params.requestId,
   url:m.params.response.url,status:m.params.response.status,mimeType:m.params.response.mimeType});
  else if(m.method==='Fetch.requestPaused')paused.push({phase,sessionId:m.sessionId,...m.params});
  else if(m.method==='Browser.downloadWillBegin')downloadSeen.set(m.params.guid,{...m.params,state:'started'});
  else if(m.method==='Browser.downloadProgress'){const d=downloadSeen.get(m.params.guid);if(d)Object.assign(d,m.params);}
 });
 receipt.browser=await send('Browser.getVersion');receipt.browser_pid=browser.pid;
 ({browserContextId}=await send('Target.createBrowserContext',{disposeOnDetach:true}));
 await send('Browser.setDownloadBehavior',{behavior:'allowAndName',downloadPath:downloadsPath,eventsEnabled:true,browserContextId});


 let sid, newReport, defaultUids;
 await check('legacy report to real combined Run while calendar stays pending',async()=>{
  sid=await reset();
  const legacy=await evaluate(sid,"({uc:document.querySelector('#uc-note').textContent,disabled:document.querySelector('#uc-status').disabled})");
  assert(legacy.disabled);assert.match(legacy.uc,/Run worklist/);
  const control=await intercept(sid,'/api/run','Request'),before=downloadSeen.size;
  await click(sid,'#run');const event=await held(control);
  assert.equal((await ui(sid)).disabled,true);
  await query(sid,'Shared');await select(sid,'#fc','East');
  assert.equal((await ui(sid)).disabled,true);
  await release(control,event);
  await until(async()=>{const s=await ui(sid);return !s.disabled&&s.shown==='1 of 7 items';},'combined fresh filtered report');
  newReport=JSON.parse(await fs.readFile(path.join(candidateFixture,'out/summary.json'),'utf8'));
  assert.equal(newReport.as_of,'2026-10-31');
  assert.deepEqual(newReport.uncovered_review.map(r=>r.visit_id).sort(),['VISIT-PT1005','VISIT-PT1006']);
  assert(newReport.uncovered_review.every(r=>r.status==='scheduled'));
  assert.equal(downloadSeen.size,before);
  const screenshot=await capture(sid,'combined-calendar-desktop.png');
  return{legacy,current:await ui(sid),uncovered_ids:newReport.uncovered_review.map(r=>r.visit_id),screenshot};
 });
 await check('uncovered filters and actual all-CSV ignore calendar worklist filters',async()=>{
  const workBefore=await ui(sid);
  await click(sid,'#tabs button[data-t="uncovered"]');
  const defaultReview=await uncovered(sid);
  assert.equal(defaultReview.rows.length,2);assert.match(defaultReview.shown,/2 of 2 appointments/);
  await select(sid,'#uc-clinic',JSON.stringify('West'));
  assert.equal((await uncovered(sid)).rows.length,1);assert((await uncovered(sid)).rows[0].includes('VISIT-PT1006'));
  await select(sid,'#uc-status','completed');
  assert.equal((await uncovered(sid)).rows.length,0);
  await select(sid,'#uc-status','');
  await evaluate(sid,"document.querySelector('#uc-search').focus()");
  await send('Input.insertText',{text:'Undated'},sid);
  const filtered=await uncovered(sid);assert.equal(filtered.rows.length,1);
  assert.match(filtered.exportText,/all uncovered visits CSV.*independent of these filters/i);
  const unchanged=await ui(sid);assert.equal(unchanged.query,workBefore.query);assert.equal(unchanged.clinic,workBefore.clinic);assert.equal(unchanged.shown,workBefore.shown);
  const csv=await downloadCsv(sid,'all-uncovered-from-filtered-view');
  const screenshot=await captureUncovered(sid,'combined-uncovered-390.png',390,844);
  const dims=await evaluate(sid,"(()=>{const f=document.querySelector('#uc-filters').getBoundingClientRect();return{viewport:innerWidth,left:f.left,right:f.right,tabVisible:!document.querySelector('#t-uncovered').classList.contains('hidden'),injected:document.querySelectorAll('#t-uncovered literal').length};})()");
  assert(dims.left>=0&&dims.right<=390);assert(dims.tabVisible);assert.equal(dims.injected,0);
  return{defaultReview,filtered,csv,screenshot,dimensions:dims,worklist_preserved:unchanged};
 });
 await check('staff work state does not hide an uncovered appointment or change its all-CSV',async()=>{
  await send('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},sid);
  await click(sid,'#tabs button[data-t="work"]');
  await query(sid,'');await select(sid,'#fc','');
  const row=expected.find(r=>r.patient_id==='PT1005');
  const before=await fs.readFile(path.join(candidateFixture,'out/uncovered_visits.csv'));
  await select(sid,'select[data-k="'+row.key+'"]','approved');
  await until(async()=>{const s=await ui(sid);return !s.disabled&&s.shown==='4 of 7 items';},'approved work item hidden independently');
  await click(sid,'#tabs button[data-t="uncovered"]');
  const review=await uncovered(sid);
  assert.equal(review.clinic,JSON.stringify('West'));assert.equal(review.query,'Undated');assert.equal(review.rows.length,1);
  await select(sid,'#uc-clinic','');
  assert.equal((await uncovered(sid)).rows.length,2);
  assert((await uncovered(sid)).rows.some(r=>r.includes('VISIT-PT1005')));
  assert.equal(sha(await fs.readFile(path.join(candidateFixture,'out/uncovered_visits.csv'))),sha(before));
  return{work:await ui(sid),uncovered:await uncovered(sid),staff_state:JSON.parse(await fs.readFile(path.join(candidateFixture,'out/work_state.json'),'utf8'))[row.key],csv_unchanged:true};
 });
 await check('return to calendar completes exact current filtered ICS with new report fields',async()=>{
  await click(sid,'#tabs button[data-t="work"]');await query(sid,'Shared');await select(sid,'#fc','East');
  const state=await ui(sid);assert.equal(state.shown,'1 of 7 items');assert.equal(state.disabled,false);
  const chosen=eligible.filter(r=>r.patient_id==='PT1001');
  const d=await downloadCurrent(sid,'combined-filtered-calendar',chosen);
  const screenshot=await capture(sid,'combined-calendar-390.png',390,844);
  return{state,download:d.label,screenshot,new_uncovered_fields_present:Array.isArray(newReport.uncovered_review)};
 });
 await check('combined report drift refuses stale calendar and real Run restores current export',async()=>{
  await send('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},sid);
  const file=path.join(candidateFixture,'out/summary.json'),before=downloadSeen.size;
  await writeDrift(file,s=>{s.worklist.find(r=>r.patient_id==='PT1001').submit_by='2026-11-05';},'combined-stale-report');
  await click(sid,'[data-calendar-download]');
  await until(async()=>{const s=await ui(sid);return s.disabled&&s.status.includes('changed');},'combined snapshot drift refusal');
  const rejected=await ui(sid);assert.equal(downloadSeen.size,before);
  assert(network.some(e=>e.phase===phase&&e.event==='response'&&new URL(e.url).pathname==='/api/calendar'&&e.status===409));
  await click(sid,'#run');await until(async()=>!(await ui(sid)).disabled,'combined real refresh');
  await query(sid,'');await select(sid,'#fc','');
  const current=await ui(sid);assert.equal(current.shown,'4 of 7 items');
  const d=await downloadCurrent(sid,'combined-current-after-refusal',eligible);
  await click(sid,'#tabs button[data-t="uncovered"]');
  const uc=await uncovered(sid);assert.equal(uc.rows.length,2);
  assert(uc.rows.some(r=>r.includes('VISIT-PT1005')));assert(uc.rows.some(r=>r.includes('VISIT-PT1006')));
  return{rejected,current,download:d.label,uncovered:uc,actual_stale_status:409};
 });
 receipt.source_after={baseline:await hashes(baseline),candidate:await hashes(candidate)};
 assert.deepEqual(receipt.source_after,sourceBefore,'all source bytes/modes preserved');
 assert.deepEqual(await hashes(template),templateBefore,'independent fixture template preserved');
 receipt.source_preserved=true;receipt.fixture_template_preserved=true;
}catch(e){receipt.fatal_error=e.stack||String(e);console.log(JSON.stringify({fatal:e.message}));}
finally{
 await closePage().catch(()=>{});
 if(socket?.readyState===WebSocket.OPEN){
  await send('Target.disposeBrowserContext',{browserContextId}).catch(()=>{});
  await send('Browser.close').catch(()=>{});socket.close();
 }
 for(const s of servers){s.child.kill('SIGTERM');const logs=s.read();await fs.writeFile(path.join(output,s.label+'-server.stdout.log'),logs.stdout);await fs.writeFile(path.join(output,s.label+'-server.stderr.log'),logs.stderr);}
 if(browser&&browser.exitCode===null&&!browser.killed)browser.kill('SIGTERM');
 await delay(150);
 for(const p of pending.values())clearTimeout(p.timer);pending.clear();
 receipt.ended_at=new Date().toISOString();receipt.checks=checks;receipt.downloads=downloads;receipt.mutations=mutations;
 receipt.exceptions=exceptions;receipt.dialogs=dialogs;receipt.transport=transport;receipt.child_exits=childExits;
 receipt.source_before=sourceBefore;receipt.fixture_template=templateBefore;
 const st=await fs.statfs(here);receipt.free_bytes_after=st.bavail*st.bsize;
 receipt.passed=checks.filter(c=>c.status==='pass').length;receipt.failed=checks.filter(c=>c.status==='fail').length;
 receipt.status=!receipt.fatal_error&&receipt.failed===0&&receipt.passed===5&&exceptions.length===0?'pass':'fail';
 await fs.writeFile(path.join(output,'result.json'),JSON.stringify(receipt,null,2)+'\n');
 await fs.writeFile(path.join(output,'network.json'),JSON.stringify(network,null,2)+'\n');
 await fs.writeFile(path.join(output,'paused-http.json'),JSON.stringify(paused,null,2)+'\n');
 await fs.writeFile(path.join(output,'chrome.stderr.log'),chromeStderr);
 console.log(JSON.stringify({status:receipt.status,passed:receipt.passed,failed:receipt.failed,downloads:downloads.length,exceptions:exceptions.length,fatal:receipt.fatal_error?.split('\n')[0],output}));
 process.exitCode=receipt.status==='pass'?0:1;
}
