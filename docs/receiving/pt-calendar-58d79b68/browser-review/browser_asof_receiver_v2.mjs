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
const receipt={schema:'pt_calendar.independent_browser.v1',started_at:new Date().toISOString(),
  source_boundary:'Exact frozen PT native server/UI in an isolated synthetic fixture; actual completed Chrome downloads. No calendar importer, full repository build or later-parent execution claim.',
  driver_sha256:sha(await fs.readFile(fileURLToPath(import.meta.url))),
  contract_sha256:'0bc7fe83e5dc587e0a6734de50d42cd6f3d53a05ebb083a429d77a6c4a1ac037',
  specification_sha256:'17dbd8b0d7c729b1cb261e34375abc3dbbf266faeea0b6ebb7a07ab5a6668d7c',
  baseline_commit:'9e931fa9f42033bf2368f7149684fb5631345715',
  candidate_commit:'d75fb908a9893fd40b21112f62af16d32027bbe1',
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
 if(process.env.PT_REVIEW_CASE && name!==process.env.PT_REVIEW_CASE)return;
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
const eligible=expected.filter(r=>r.eligible);
receipt.selected_check=process.env.PT_REVIEW_CASE||null;
receipt.receiver_revision='v2: only the as-of expectation is corrected against independently executed original engine; v1 failures retained';
try{
 const st=await fs.statfs(here);receipt.free_bytes_before=st.bavail*st.bsize;
 assert(receipt.free_bytes_before>=128*1024*1024,'at least 128 MiB for one bounded Chrome profile');
 baseUrl=await serve(baseline,baselineFixture,'baseline');
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

 await check('original real worklist has no calendar handoff',async()=>{
  const before=await hashes(baselineFixture);
  page=await open(baseUrl+'/');
  await until(()=>evaluate(page.sessionId,'document.querySelector("#shown")?.textContent==="5 of 7 items"'),'baseline worklist');
  const state=await ui(page.sessionId);
  assert.equal(state.keys.length,5);assert.equal(state.summary,undefined);
  assert.equal(await evaluate(page.sessionId,'document.querySelectorAll("[data-calendar-download]").length'),0);
  const screenshot=await capture(page.sessionId,'baseline-worklist.png');
  assert.deepEqual(await hashes(baselineFixture),before);
  await closePage();return{state,screenshot,boundary:'Actual original UI, no handoff control, no file created'};
 });
 let defaultUids;
 await check('default review and actual keyboard download',async()=>{
  const sid=await reset(),state=await ui(sid);
  assert.equal(state.shown,'5 of 7 items');assert.match(state.summary,/3 all-day event\(s\).*2 excluded item\(s\)/);
  assert.match(state.context,/2 undated; 0 approved\/n\/a/);assert.match(state.context,/America\/Los_Angeles/);
  assert.deepEqual(new Set(state.keys),new Set(expected.filter(r=>!['approved','n/a'].includes(r.staff_state)).map(r=>r.key)));
  const focus=[];
  for(let i=0;i<40;i++){await key(sid,'Tab','Tab',9);const s=await ui(sid);focus.push(s.focused);if(s.focused.download)break;}
  assert.equal(focus.at(-1).download,true,'native Tab reaches download');
  const keyboardCapture=await capture(sid,'desktop-keyboard-focus.png');
  const d=await downloadCurrent(sid,'default-keyboard',eligible,()=>key(sid,'Enter','Enter',13));
  defaultUids=d.content.uids;assert(d.content.folded_lines>0,'long Unicode fixture exercised folding');
  return{state,focus_path:focus,screenshot:keyboardCapture,download:d.label};
 });
 await check('all-state exclusions and repeat identities',async()=>{
  const sid=await reset();await select(sid,'#fs','all');
  const state=await ui(sid);assert.equal(state.shown,'7 of 7 items');
  assert.match(state.summary,/3 all-day event\(s\).*4 excluded item\(s\)/);
  assert.match(state.context,/2 undated; 2 approved\/n\/a/);assert.equal(state.lines.length,7);
  assert(state.lines.some(x=>x.includes('staff state approved')));assert(state.lines.some(x=>x.includes('staff state n/a')));
  await click(sid,'[data-calendar-details] summary');
  const screenshot=await capture(sid,'desktop-reviewed-exclusions.png');
  const d=await downloadCurrent(sid,'all-states',eligible);
  if(defaultUids)assert.deepEqual(d.content.uids,defaultUids);
  return{state,screenshot,download:d.label};
 });
 await check('actual text and clinic filters preserve distinct same-name keys',async()=>{
  const sid=await reset();await query(sid,'Shared');
  let state=await ui(sid);assert.equal(state.shown,'2 of 7 items');
  const shared=eligible.filter(r=>r.patient_name.startsWith('Shared'));
  const both=await downloadCurrent(sid,'same-name-two-clinics',shared);
  assert.equal(Object.keys(both.content.uids).length,2);
  await select(sid,'#fc','East');state=await ui(sid);assert.equal(state.shown,'1 of 7 items');
  const east=await downloadCurrent(sid,'same-name-east',shared.filter(r=>r.clinic==='East'));
  assert.equal(east.content.uids[shared[0].key],both.content.uids[shared[0].key]);
  const retained=await ui(sid);assert.equal(retained.query,'Shared');assert.equal(retained.clinic,'East');
  return{state:retained,downloads:[both.label,east.label]};
 });
 await check('empty eligible selection refuses a misleading download',async()=>{
  const sid=await reset(),before=downloadSeen.size;await query(sid,'Undated');
  const state=await ui(sid);assert.equal(state.shown,'2 of 7 items');assert.equal(state.disabled,true);
  assert.match(state.summary,/0 all-day event\(s\).*2 excluded item\(s\)/);assert.match(state.status,/No calendar will be created/);
  await delay(150);assert.equal(downloadSeen.size,before);
  await query(sid,'');assert.equal((await ui(sid)).disabled,false);
  return{state,recovered:await ui(sid),unexpected_downloads:0};
 });
 await check('390px real panel and literal review text',async()=>{
  const sid=await reset();await click(sid,'[data-calendar-details] summary');
  const screenshot=await capture(sid,'narrow-390-review.png',390,844);
  const dimensions=await evaluate(sid,"(()=>{const p=document.querySelector('#calendar'),b=document.querySelector('[data-calendar-download]');const pr=p.getBoundingClientRect(),br=b.getBoundingClientRect();return{viewport:innerWidth,panel:{left:pr.left,right:pr.right,width:pr.width},button:{left:br.left,right:br.right,width:br.width},htmlInjected:p.querySelectorAll('literal').length,statusRole:document.querySelector('[data-calendar-status]').getAttribute('role'),statusLive:document.querySelector('[data-calendar-status]').getAttribute('aria-live'),text:p.innerText};})()");
  assert(dimensions.panel.left>=0&&dimensions.panel.right<=390);assert(dimensions.button.left>=0&&dimensions.button.right<=390);
  assert.equal(dimensions.htmlInjected,0);assert.equal(dimensions.statusRole,'status');assert.equal(dimensions.statusLive,'polite');
  assert(dimensions.text.includes(fixture.rows[0].payer_name),'literal Unicode/punctuation payer text');
  return{screenshot,dimensions,scope:'Panel at exact 390px viewport; not a full application accessibility audit'};
 });
 await check('edited as-of, revert and actual refreshed report',async()=>{
  const sid=await reset(),before=downloadSeen.size;
  await setDate(sid,'2026-11-02');let state=await ui(sid);assert.equal(state.disabled,true);assert.match(state.status,/as-of date has changed/);
  await setDate(sid,'2026-10-31');assert.equal((await ui(sid)).disabled,false);
  await setDate(sid,'2026-11-02');await click(sid,'#run');
  await until(async()=>{const s=await ui(sid);return s.asof==='2026-11-02'&&s.context.includes('report as of 2026-11-02')&&s.shown==='0 of 0 items';},'refreshed empty as-of');
  const empty=await ui(sid);
  assert.equal(empty.disabled,true);assert.match(empty.summary,/0 all-day event\(s\).*0 excluded item\(s\)/);
  assert.match(empty.status,/No calendar will be created/);assert.equal(downloadSeen.size,before);
  const emptySaved=JSON.parse(await fs.readFile(path.join(candidateFixture,'out/summary.json'),'utf8'));
  assert.equal(emptySaved.as_of,'2026-11-02');assert.equal(emptySaved.worklist.length,0);
  await setDate(sid,'2026-10-30');assert.equal((await ui(sid)).disabled,true);
  await click(sid,'#run');
  await until(async()=>{const s=await ui(sid);return !s.disabled&&s.asof==='2026-10-30'&&s.context.includes('report as of 2026-10-30');},'refreshed eligible as-of');
  state=await ui(sid);assert.equal(state.shown,'5 of 7 items');assert.equal(downloadSeen.size,before);
  const oracleBytes=await fs.readFile(path.join(here,'asof-original-engine-v2/before_appointments/summary.json'));
  const originalEngine=JSON.parse(oracleBytes);
  const rows=originalEngine.worklist.map(r=>({...r,staff_state:expected.find(e=>e.key===r.key).staff_state}))
   .filter(r=>r.submit_by!==null&&['open','submitted'].includes(r.staff_state));
  assert.equal(rows.length,3);
  const d=await downloadCurrent(sid,'fresh-reviewed-october-30',rows);
  const snapshotKeys=network.filter(n=>n.phase===phase&&n.event==='request'&&n.url.endsWith('/api/calendar')).map(n=>JSON.parse(n.postData));
  assert.equal(snapshotKeys.length,1);assert.deepEqual(new Set(snapshotKeys[0].keys),new Set(state.keys));
  const screenshot=await capture(sid,'fresh-asof-reviewed.png');
  return{empty_refreshed_report:empty,eligible_refreshed_report:state,original_engine_oracle_sha256:sha(oracleBytes),
   download:d.label,screenshot,no_download_during_edit_or_empty_review:true,
   v1_preserved_failure:'The original check expected an enabled export after all synthetic visits. The unchanged original engine independently confirms an empty worklist, now explicitly required.'};
 });
 await check('pending real refresh blocks export and accepts current filters',async()=>{
  const sid=await reset(),control=await intercept(sid,'/api/run','Request'),before=downloadSeen.size;
  await click(sid,'#run');const event=await held(control);assert.equal((await ui(sid)).disabled,true);
  await query(sid,'Shared');assert.equal((await ui(sid)).disabled,true);
  await release(control,event);await until(async()=>!(await ui(sid)).disabled,'current refresh');
  const state=await ui(sid);assert.equal(state.shown,'2 of 7 items');assert.equal(downloadSeen.size,before);
  const d=await downloadCurrent(sid,'after-pending-refresh',eligible.filter(r=>r.patient_name.startsWith('Shared')));
  return{state,held_status:event.responseStatusCode||'request not sent',download:d.label};
 });
 await check('pending real staff-state save blocks export then reviews new state',async()=>{
  const sid=await reset(),control=await intercept(sid,'/api/state','Request');
  const statePath=path.join(candidateFixture,'out/work_state.json'),before=await fs.readFile(statePath);
  const row=expected.find(r=>r.patient_id==='PT1007');
  await select(sid,'select[data-k="'+row.key+'"]','approved');const event=await held(control);
  assert.equal((await ui(sid)).disabled,true);assert.equal(sha(await fs.readFile(statePath)),sha(before));
  await release(control,event);await until(async()=>{const s=await ui(sid);return!s.disabled&&s.summary.startsWith('2 all-day');},'new state reviewed');
  const after=await fs.readFile(statePath);mutations.push({label:'explicit UI staff-state edit',before_sha256:sha(before),after_sha256:sha(after),key:row.key,state:'approved'});
  const state=await ui(sid),d=await downloadCurrent(sid,'after-reviewed-state',eligible.filter(r=>r.key!==row.key));
  return{state,download:d.label,legitimate_state_write:true};
 });
 await check('failed real refresh leaves calendar unavailable and next refresh recovers',async()=>{
  const sid=await reset(),control=await intercept(sid,'/api/run','Request'),before=downloadSeen.size;
  await click(sid,'#run');const event=await held(control);
  await send('Fetch.failRequest',{requestId:event.requestId,errorReason:'Failed'},sid);await send('Fetch.disable',{},sid);
  await until(async()=>{const s=await ui(sid);return s.disabled&&s.status.includes('Refresh the worklist');},'failed refresh refusal');
  const failed=await ui(sid);assert.equal(downloadSeen.size,before);
  await until(()=>evaluate(sid,'document.querySelector("#run").disabled===false'),'run button after handled failure');
  await click(sid,'#run');await until(async()=>!(await ui(sid)).disabled,'valid refresh recovers');
  return{failed,recovered:await ui(sid),intentional_transport_failure:true};
 });
 await check('saved-report drift rejects earlier snapshot and replacement must be reviewed',async()=>{
  const sid=await reset(),file=path.join(candidateFixture,'out/summary.json'),before=downloadSeen.size;
  await writeDrift(file,s=>{s.worklist.find(r=>r.patient_id==='PT1007').submit_by='2026-11-05';},'stale-report');
  await click(sid,'[data-calendar-download]');
  await until(async()=>{const s=await ui(sid);return s.disabled&&s.status.includes('changed');},'report drift refusal');
  const rejected=await ui(sid);assert.equal(downloadSeen.size,before);
  await send('Page.reload',{ignoreCache:true},sid);await until(async()=>!(await ui(sid)).disabled,'replacement saved report reviewed');
  const rows=eligible.map(r=>r.patient_id==='PT1007'?{...r,submit_by:'2026-11-05'}:r);
  const d=await downloadCurrent(sid,'after-reviewed-report-drift',rows);
  return{rejected,download:d.label};
 });
 await check('saved staff-state drift rejects snapshot until actual replacement review',async()=>{
  const sid=await reset(),file=path.join(candidateFixture,'out/work_state.json'),before=downloadSeen.size;
  const row=expected.find(r=>r.patient_id==='PT1001');
  await writeDrift(file,s=>{s[row.key]={state:'approved',note:'Independent stale-state control',at:'2026-10-01T12:00:00+00:00'};},'stale-staff-state');
  await click(sid,'[data-calendar-download]');
  await until(async()=>{const s=await ui(sid);return s.disabled&&s.status.includes('changed');},'state drift refusal');
  const rejected=await ui(sid);assert.equal(downloadSeen.size,before);
  await send('Page.reload',{ignoreCache:true},sid);await until(async()=>!(await ui(sid)).disabled,'replacement staff state reviewed');
  const d=await downloadCurrent(sid,'after-reviewed-state-drift',eligible.filter(r=>r.key!==row.key));
  return{rejected,download:d.label};
 });
 await check('late actual success retired by filter change cannot download or replace status',async()=>{
  const sid=await reset(),control=await intercept(sid,'/api/calendar','Response'),before=downloadSeen.size;
  await click(sid,'[data-calendar-download]');const event=await held(control);assert.equal(event.responseStatusCode,200);
  await query(sid,'Shared');const current=await ui(sid);assert.equal(current.disabled,false);
  const releaseResult=await release(control,event);await delay(150);
  assert.equal(downloadSeen.size,before);assert.equal((await ui(sid)).status,current.status);
  const d=await downloadCurrent(sid,'after-retired-success',eligible.filter(r=>r.patient_name.startsWith('Shared')));
  return{review_after_change:current,releaseResult,unexpected_downloads:0,download:d.label};
 });
 await check('late actual 409 retired by filter change cannot replace newer status',async()=>{
  const sid=await reset(),file=path.join(candidateFixture,'out/summary.json');
  const original=await writeDrift(file,s=>{s.worklist.find(r=>r.patient_id==='PT1007').submit_by='2026-11-05';},'late-failure-report');
  const control=await intercept(sid,'/api/calendar','Response'),before=downloadSeen.size;
  await click(sid,'[data-calendar-download]');const event=await held(control);assert.equal(event.responseStatusCode,409);
  await query(sid,'Shared');const current=await ui(sid);await fs.writeFile(file,original);
  const releaseResult=await release(control,event);await delay(150);
  assert.equal(downloadSeen.size,before);assert.equal((await ui(sid)).status,current.status);assert.equal((await ui(sid)).disabled,false);
  const d=await downloadCurrent(sid,'after-retired-failure',eligible.filter(r=>r.patient_name.startsWith('Shared')));
  return{review_after_change:current,releaseResult,unexpected_downloads:0,download:d.label};
 });
 await check('late actual success retired by as-of edit remains unavailable',async()=>{
  const sid=await reset(),control=await intercept(sid,'/api/calendar','Response'),before=downloadSeen.size;
  await click(sid,'[data-calendar-download]');const event=await held(control);assert.equal(event.responseStatusCode,200);
  await setDate(sid,'2026-11-02');const state=await ui(sid);assert.equal(state.disabled,true);
  await release(control,event);await delay(150);
  assert.equal(downloadSeen.size,before);assert.equal((await ui(sid)).status,state.status);assert.equal((await ui(sid)).disabled,true);
  await setDate(sid,'2026-10-31');assert.equal((await ui(sid)).disabled,false);
  return{retired_state:state,recovered:await ui(sid),unexpected_downloads:0};
 });
 await check('initial real summary pending is unavailable until exact report arrives',async()=>{
  await closePage();await copyFixture(candidateFixture);
  page=await open(candidateUrl+'/',true);
  const event=await held(page.marker),before=downloadSeen.size,state=await ui(page.sessionId);
  assert.equal(state.disabled,true);assert.equal(downloadSeen.size,before);
  await release(page.marker,event);await until(async()=>!(await ui(page.sessionId)).disabled,'initial summary accepted');
  return{pending:state,accepted:await ui(page.sessionId),actual_response_status:event.responseStatusCode};
 });
 if(process.env.PT_REVIEW_CASE)assert(checks.some(c=>c.name===process.env.PT_REVIEW_CASE),'selected case executed');
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
 receipt.status=!receipt.fatal_error&&receipt.failed===0&&exceptions.length===0?'pass':'fail';
 await fs.writeFile(path.join(output,'result.json'),JSON.stringify(receipt,null,2)+'\n');
 await fs.writeFile(path.join(output,'network.json'),JSON.stringify(network,null,2)+'\n');
 await fs.writeFile(path.join(output,'paused-http.json'),JSON.stringify(paused,null,2)+'\n');
 await fs.writeFile(path.join(output,'chrome.stderr.log'),chromeStderr);
 console.log(JSON.stringify({status:receipt.status,passed:receipt.passed,failed:receipt.failed,downloads:downloads.length,exceptions:exceptions.length,fatal:receipt.fatal_error?.split('\n')[0],output}));
 process.exitCode=receipt.status==='pass'?0:1;
}
