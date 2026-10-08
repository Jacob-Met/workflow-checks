// Independent actual-browser receiver for Utility Watch's editable review desk.
// Candidate execution requires the separately delivered frozen source pin.
// Baseline fixture/native checker controls are not rerun here.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {spawn,execFileSync} from 'node:child_process';

const [sourceArg,fixtureArg,baselineArg]=process.argv.slice(2);
if(!sourceArg||!fixtureArg||!baselineArg)throw new Error('Usage: node utility-desk-consumer.mjs FROZEN_SOURCE FIXTURE_DIRECTORY ORIGINAL_BASELINE_SOURCE');
const sourceRoot=path.resolve(sourceArg),fixture=path.resolve(fixtureArg),baselineSource=path.resolve(baselineArg);
const expectedTree=process.env.UTILITY_DESK_SOURCE_TREE;
const frozenNativeCommit=process.env.UTILITY_DESK_FROZEN_COMMIT;
assert.match(expectedTree??'',/^[0-9a-f]{40}$/,'Require the exact separately received candidate tree before execution');
assert.match(frozenNativeCommit??'',/^[0-9a-f]{40}$/,'Require the exact separately received native candidate commit');
assert.equal(execFileSync('git',['-C',sourceRoot,'rev-parse','HEAD^{tree}'],{encoding:'utf8'}).trim(),expectedTree);
assert.equal(execFileSync('git',['-C',sourceRoot,'status','--porcelain'],{encoding:'utf8'}),'');
const packageRoot=path.join(sourceRoot,'utility_watch');
const python=process.env.UTILITY_DESK_PYTHON??'python3';
const browserPath=process.env.UTILITY_DESK_CHROMIUM??'chromium';
const evidenceDir=process.env.UTILITY_DESK_EVIDENCE_DIR??await fs.mkdtemp(path.join(os.tmpdir(),'utility-desk-receiving-'));
await fs.mkdir(evidenceDir,{recursive:true});
const downloadDir=path.join(evidenceDir,'downloads');await fs.mkdir(downloadDir,{recursive:true});
const originalSource=await fs.readFile(path.join(fixture,'desk-current-with-history.csv'));
const oracle=JSON.parse(await fs.readFile(path.join(fixture,'FIXTURE_ORACLE.json'),'utf8'));
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
assert.equal(hash(originalSource),oracle.worksheet_sha256);
const sourceWorkingPath=path.join(evidenceDir,'selected-source.csv');
await fs.writeFile(sourceWorkingPath,originalSource,{flag:'wx'});
const profileRoot=process.env.UTILITY_DESK_PROFILE_ROOT??os.tmpdir();
await fs.mkdir(profileRoot,{recursive:true});
const profile=await fs.mkdtemp(path.join(profileRoot,'hamon-utility-desk-39c2b591-'));
const sourceFiles=['uwatch/__init__.py','uwatch/__main__.py','uwatch/cli.py','uwatch/engine.py','uwatch/review.py',
 'uwatch/review_desk.py','uwatch/review_desk.html','uwatch/review_desk.js','uwatch/review_desk.css'];
const hashSources=async()=>Object.fromEntries(await Promise.all(sourceFiles.map(async name=>[name,hash(await fs.readFile(path.join(packageRoot,name)))])));
const before=await hashSources();
for(const name of ['uwatch/review.py','uwatch/engine.py'])
 assert.equal(before[name],hash(await fs.readFile(path.join(baselineSource,'utility_watch',name))),'Original native worksheet and checker must remain exact');
const edits=oracle.planned_ui_edits.map(({row_id,review_status,reviewer,note})=>({row_id,review_status,reviewer,note}));
const firstRow=oracle.current.find(row=>row.row_id===edits[0].row_id);
const secondRow=oracle.current.find(row=>row.row_id===edits[1].row_id);
const untouched=oracle.current.find(row=>!edits.some(edit=>edit.row_id===row.row_id));
assert.equal(firstRow.finding_key,secondRow.finding_key);assert.notEqual(firstRow.account_no,secondRow.account_no);
assert.ok(untouched&&oracle.history.length===2);
const checks=[],observations=[],exceptions=[],requests=[],responses=[],downloadEvents=[],artifacts=[],fileChanges=[];
let browser,server,socket,receipt,url,browserVersion,nextId=0;
let serverStdout='',serverStderr='',chromiumStderr='';
const pending=new Map(),delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function check(description){checks.push(description);console.log('PASS '+description);}
function send(method, params = {}, sessionId) {
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 15000);
    pending.set(id, { resolve, reject, timer });
    socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
  });
}
async function evaluate(sessionId, expression) {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }, sessionId);
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
  return result.result.value;
}
async function waitFor(predicate, description) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) { if (await predicate()) return; await delay(80); }
  throw new Error(`Did not reach expected state: ${description}`);
}
async function openPage(targetUrl = url) {
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  await send('Runtime.enable', {}, sessionId);
  await send('Page.enable', {}, sessionId);
  await send('Network.enable', {}, sessionId);
  // Keep screenshots at the same layout width before and during a full-page
  // capture. Chromium otherwise removes the scrollbar while expanding the
  // capture surface and can crop the newly widened layout at the old bounds.
  await send('Emulation.setScrollbarsHidden', { hidden: true }, sessionId);
  // A reader in another timezone must still see the recorded Los Angeles day.
  if (targetUrl.startsWith('file:')) await send('Emulation.setTimezoneOverride', { timezoneId: 'Pacific/Auckland' }, sessionId);
  await send('Page.navigate', { url: targetUrl }, sessionId);
  return { targetId, sessionId };
}
async function edit(sessionId, selector, value, type = 'change') {
  await evaluate(sessionId, `(() => {
    const e = document.querySelector(${JSON.stringify(selector)});
    e.value = ${JSON.stringify(value)};
    e.dispatchEvent(new Event(${JSON.stringify(type)}, {bubbles: true}));
  })()`);
}
async function click(sessionId, selector) {
  const point = await evaluate(sessionId, `(() => {
    const e = document.querySelector(${JSON.stringify(selector)});
    e.scrollIntoView({block: 'center'});
    const r = e.getBoundingClientRect();
    return {x: r.x + r.width / 2, y: r.y + r.height / 2};
  })()`);
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', button: 'left', clickCount: 1, ...point }, sessionId);
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', button: 'left', clickCount: 1, ...point }, sessionId);
}

async function screenshot(sessionId, name, selector) {
  await evaluate(sessionId, 'window.scrollTo(0, 0)');
  let clip;
  if (selector) clip = await evaluate(sessionId, `(() => {
    const r = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();
    return {x: r.x, y: r.y + scrollY, width: r.width, height: r.height, scale: 1};
  })()`);
  else {
    const { cssContentSize } = await send('Page.getLayoutMetrics', {}, sessionId);
    clip = { x: 0, y: 0, width: cssContentSize.width, height: cssContentSize.height, scale: 1 };
  }
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip }, sessionId);
  await fs.writeFile(path.join(evidenceDir, name), Buffer.from(shot.data, 'base64'));
}


async function key(sid,name,code,keyCode,modifiers=0,text){
 await send('Input.dispatchKeyEvent',{type:'keyDown',key:name,code,windowsVirtualKeyCode:keyCode,modifiers,...(text?{text}:{})},sid);
 await send('Input.dispatchKeyEvent',{type:'keyUp',key:name,code,windowsVirtualKeyCode:keyCode,modifiers},sid);
}
async function typeText(sid,selector,value){
 await click(sid,selector);
 assert.equal(await evaluate(sid,'document.activeElement===document.querySelector('+JSON.stringify(selector)+')'),true,'Native click must focus the intended form input');
 await key(sid,'a','KeyA',65,2);
 await send('Input.insertText',{text:value},sid);
 await key(sid,'Tab','Tab',9);
 assert.equal(await evaluate(sid,'document.querySelector('+JSON.stringify(selector)+').value'),value);
}
async function allStatuses(sid){
 const value=await evaluate(sid,'Array.from(document.querySelector("#status-filter").options).find(o=>/^all\\b/i.test(o.textContent.trim()))?.value');
 assert.equal(typeof value,'string','The current-finding filter must offer its declared all-status view');
 await edit(sid,'#status-filter',value,'change');
}
async function inspect(sid,name){
 const state=await evaluate(sid,'('+(()=>{
  const q=s=>document.querySelector(s),all=s=>Array.from(document.querySelectorAll(s));
  const pairs=selector=>Object.fromEntries(all(selector+' dt').map(dt=>[dt.textContent.trim().replace(/:$/,''),dt.nextElementSibling?.textContent.trim()??'']));
  const err=q('#download-error'),status=q('#download-status');
  return{
   visibleRows:all('.finding[data-row-id]').filter(e=>e.getClientRects().length).map(e=>({row_id:e.dataset.rowId,text:e.textContent})),
   selectedIdentity:pairs('#selected-identity'),selectedEvidence:q('#selected-evidence')?.textContent??'',
   form:{status:q('#review-status')?.value,reviewer:q('#reviewer')?.value,note:q('#note')?.value},
   selectedHidden:q('#selected')?.hidden,search:q('#search').value,statusFilter:q('#status-filter').value,
   history:all('#history-list article.history-row[data-row-id]').map(e=>({row_id:e.dataset.rowId,text:e.textContent,html:e.innerHTML,visible:e.getClientRects().length>0})),
   historyEditableInputs:all('#history-list input,#history-list textarea,#history-list select,#history-list [contenteditable="true"]').filter(e=>!e.disabled&&!e.readOnly).length,
   downloadDisabled:q('#download').disabled,
   errorVisible:!!err&&!err.hidden&&getComputedStyle(err).display!=='none',errorText:err?.textContent??'',downloadStatus:status?.textContent??'',
   noteValidation:q('#note')?.validationMessage??'',reviewerValidation:q('#reviewer')?.validationMessage??'',
   validationVisible:!q('#validation').hidden,validationText:q('#validation-text').textContent,
   scriptProbePresent:!!q('#desk-probe'),scriptProbeValue:globalThis.deskProbe??null,
   viewport:{width:innerWidth,pageWidth:document.documentElement.scrollWidth},
   focus:document.activeElement?.id??'',ids:all('[id]').map(e=>e.id)
  };
 }).toString()+')()');
 observations.push({name,...state});return state;
}
function assertRow(state,row){
 assert.equal(state.selectedIdentity.Account,row.account_no);
 assert.equal(state.selectedIdentity['Bill / period'],row.finding_key);
 assert.ok(state.selectedEvidence.includes(row.row_id),'Selected evidence must expose this exact row ID');
 assert.ok(state.selectedEvidence.includes(row.finding_id),'Selected evidence must expose this finding identity');
 assert.equal(state.selectedHidden,false);
}
function assertForm(state,values){
 assert.deepEqual(state.form,{status:values.review_status,reviewer:values.reviewer,note:values.note});
 assert.equal(state.scriptProbePresent,false);assert.equal(state.scriptProbeValue,null);
}
async function selectRow(sid,row){
 await click(sid,'.finding[data-row-id="'+row.row_id+'"]');
 const state=await inspect(sid,'select exact row '+row.account_no);
 assertRow(state,row);return state;
}
const downloadCount=()=>downloadEvents.filter(e=>e.method==='Browser.downloadWillBegin').length;
const downloadResponses=()=>responses.filter(e=>new URL(e.url).pathname==='/api/download');
async function verifyFile(filename,expectedEdits,label,reconcile){
 const expectedPath=path.join(evidenceDir,label+'-expected-edits.json');
 const output=path.join(evidenceDir,label+'-native-validation.json');
 await fs.writeFile(expectedPath,JSON.stringify(expectedEdits,null,2)+'\n',{flag:'wx'});
 const validator=fileURLToPath(new URL('./verify-downloaded-worksheet.py',import.meta.url));
 const args=['-B',validator,'--fixture',fixture,'--baseline-source',baselineSource,'--download',path.join(downloadDir,filename),
  '--expected-edits',expectedPath,'--output',output];
 if(reconcile)args.push('--reconcile-out',path.join(evidenceDir,'native-reconciled.csv'));
 const child=spawn(python,args,{stdio:['ignore','pipe','pipe'],env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
 let stdout='',stderr='';
 child.stdout.on('data',b=>{stdout+=b;});child.stderr.on('data',b=>{stderr+=b;});
 const code=await new Promise((resolve,reject)=>{child.once('error',reject);child.once('close',resolve);});
 await fs.writeFile(path.join(evidenceDir,label+'-validator.stdout'),stdout);
 await fs.writeFile(path.join(evidenceDir,label+'-validator.stderr'),stderr);
 assert.equal(code,0,stderr||stdout);
 const validation=JSON.parse(await fs.readFile(output,'utf8'));assert.equal(validation.status,'pass');
 return validation;
}
async function actualDownload(sid,expectedEdits,label,reconcile=false){
 const n=downloadCount();
 const prior=await inspect(sid,label+' before native download');
 assert.equal(prior.downloadDisabled,false);
 await click(sid,'#download');
 await waitFor(()=>downloadCount()===n+1,label+' actual browser download begins');
 const started=downloadEvents.filter(e=>e.method==='Browser.downloadWillBegin').at(-1).params;
 assert.equal(started.suggestedFilename,'utility-review-edited.csv');
 await waitFor(()=>downloadEvents.some(e=>e.params.guid===started.guid&&e.params.state==='completed'),label+' actual browser download completes');
 const completed=downloadEvents.find(e=>e.params.guid===started.guid&&e.params.state==='completed').params;
 assert.equal(path.dirname(completed.filePath),downloadDir,'The actual browser completion must name this receiver’s download directory');
 const filename=path.basename(completed.filePath);
 assert.equal(filename,started.suggestedFilename);
 const bytes=await fs.readFile(completed.filePath);
 assert.equal(bytes.length,completed.totalBytes);
 // CDP allow mode may reuse the fixed filename. Preserve each completed artifact before another download.
 const archivePath=path.join(evidenceDir,label+'-actual-download.csv');
 await fs.writeFile(archivePath,bytes,{flag:'wx'});
 const validation=await verifyFile(filename,expectedEdits,label,reconcile);
 assert.equal(hash(bytes),validation.download_sha256);
 assert.equal(hash(await fs.readFile(archivePath)),hash(bytes));
 artifacts.push({filename,suggestedFilename:started.suggestedFilename,archivePath,downloadGuid:started.guid,bytes:bytes.length,sha256:hash(bytes),validation,label});
 assert.equal(hash(await fs.readFile(sourceWorkingPath)),oracle.worksheet_sha256,'Download must not write the selected source file');
 return artifacts.at(-1);
}
async function stopChild(child){
 if(!child||child.exitCode!==null)return;
 child.kill('SIGTERM');await Promise.race([new Promise(resolve=>child.once('exit',resolve)),delay(3000)]);
 if(child.exitCode===null)child.kill('SIGKILL');
}


try{
 const command=['-B','-m','uwatch','review-desk','--worksheet',sourceWorkingPath,'--port','0'];
 server=spawn(python,command,{cwd:packageRoot,stdio:['ignore','pipe','pipe'],env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
 server.stderr.on('data',b=>{serverStderr+=b.toString();});
 url=await new Promise((resolve,reject)=>{
  const timeout=setTimeout(()=>reject(new Error('Desk CLI did not report a loopback ready URL: '+serverStderr)),20000);
  server.on('error',e=>{clearTimeout(timeout);reject(e);});
  server.on('exit',code=>{clearTimeout(timeout);reject(new Error('Desk CLI exited before receiving: '+code+' '+serverStderr));});
  server.stdout.on('data',b=>{
   serverStdout+=b.toString();
   const match=serverStdout.match(/Utility Watch review desk: (http:\/\/127\.0\.0\.1:\d+)/);
   if(match){clearTimeout(timeout);resolve(match[1]+'/');}
  });
 });

  browserVersion = execFileSync(browserPath, ['--version'], { encoding: 'utf8', timeout: 45000 }).trim();
  browser = spawn(browserPath, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--disable-background-networking', '--disable-component-update', '--disable-sync', '--disable-extensions',
    '--password-store=basic', '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0',
    `--user-data-dir=${profile}`, 'about:blank'], { stdio: ['ignore', 'ignore', 'pipe'] });
  const endpoint = await new Promise((resolve, reject) => {
    let errors = '';
    const timer = setTimeout(() => reject(new Error(`Chromium did not start: ${errors.slice(-2000)}`)), 45000);
    browser.on('error', error => { clearTimeout(timer); reject(error); });
    browser.on('exit', code => { clearTimeout(timer); reject(new Error(`Chromium exited: ${code} ${errors.slice(-2000)}`)); });
    browser.stderr.on('data', bytes => {
      errors += bytes.toString(); chromiumStderr += bytes.toString();
      const found = errors.match(/DevTools listening on (ws:\/\/127\.0\.0\.1:[^\s]+)/);
      if (found) { clearTimeout(timer); resolve(found[1]); }
    });
  });
  socket = new WebSocket(endpoint);
  await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }); });


 socket.addEventListener('message',event=>{
  const message=JSON.parse(event.data);
  if(message.id&&pending.has(message.id)){
   const task=pending.get(message.id);pending.delete(message.id);clearTimeout(task.timer);
   if(message.error)task.reject(new Error(JSON.stringify(message.error)));else task.resolve(message.result);
  }
  if(message.method==='Runtime.exceptionThrown')exceptions.push(message.params.exceptionDetails);
  if(message.method==='Network.requestWillBeSent')requests.push({sessionId:message.sessionId,url:message.params.request.url,method:message.params.request.method});
  if(message.method==='Network.responseReceived')responses.push({sessionId:message.sessionId,url:message.params.response.url,status:message.params.response.status});
  if(message.method?.startsWith('Browser.download'))downloadEvents.push({method:message.method,params:message.params});
 });
 await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloadDir,eventsEnabled:true});
 const page=await openPage();const sid=page.sessionId;
 await send('Emulation.setDeviceMetricsOverride',{width:1280,height:1000,deviceScaleFactor:1,mobile:false},sid);
 await waitFor(()=>evaluate(sid,'document.querySelectorAll("#history-list article.history-row[data-row-id]").length===2&&!!document.querySelector("#download")'),'admitted worksheet renders history and current controls');
 await allStatuses(sid);
 await click(sid,'#history > summary');
 const initial=await inspect(sid,'initial admitted fictional current/history worksheet');
 assert.deepEqual(initial.visibleRows.map(r=>r.row_id).sort(),oracle.current.map(r=>r.row_id).sort());
 assert.deepEqual(initial.history.map(r=>r.row_id).sort(),oracle.history.map(r=>r.row_id).sort());
 assert.equal(initial.historyEditableInputs,0);assert.ok(initial.history.every(row=>row.visible),'Native history expansion must make both saved records inspectable');
 for(const row of oracle.history){
  const history=initial.history.find(r=>r.row_id===row.row_id);
  assert.ok(history.text.includes(row.account_no)&&history.text.includes(row.reviewer)&&history.text.includes(row.note));
  assert.match(history.text,new RegExp('\\b'+row.row_state+'\\b','i'));
 }
 const historyHTML=initial.history.map(r=>({row_id:r.row_id,html:r.html}));
 check('The independently produced worksheet exposes all three current row identities and both inspectable, read-only historical rows');

 await typeText(sid,'#search',firstRow.account_no);
 let current=await selectRow(sid,firstRow);assertForm(current,firstRow);
 assert.deepEqual(current.visibleRows.map(r=>r.row_id),[firstRow.row_id]);
 await typeText(sid,'#reviewer',edits[0].reviewer);
 await edit(sid,'#review-status','reviewed','change');
 const invalidBefore=await inspect(sid,'non-open status with a deliberately missing note');
 assertForm(invalidBefore,{...edits[0],note:''});
 const rejectedCount=downloadCount(),responsesBefore=downloadResponses().length;
 if(!invalidBefore.downloadDisabled)await click(sid,'#download');
 await waitFor(async()=>{
  const s=await inspect(sid,'invalid annotation refusal status');
  return s.downloadDisabled||(s.errorVisible&&s.errorText.trim())||s.noteValidation||s.reviewerValidation
   ||(s.validationVisible&&s.validationText.includes('needs both a reviewer and a note')&&s.downloadStatus.includes('Complete the highlighted review before downloading.'));
 },'invalid non-open annotation is visibly refused');
 const invalidAfter=await inspect(sid,'invalid note retains current edit values');
 assertForm(invalidAfter,{...edits[0],note:''});assert.equal(downloadCount(),rejectedCount);
 assert.deepEqual(invalidAfter.history.map(r=>({row_id:r.row_id,html:r.html})),historyHTML);
 if(downloadResponses().length>responsesBefore)assert.ok(downloadResponses().at(-1).status>=400);
 assert.equal(hash(await fs.readFile(sourceWorkingPath)),oracle.worksheet_sha256);
 check('A non-open status without its note refuses delivery and preserves the in-page current-row edits and all history');

 await typeText(sid,'#note',edits[0].note);
 current=await inspect(sid,'literal multiline Unicode annotation entered');
 assertRow(current,firstRow);assertForm(current,edits[0]);
 await screenshot(sid,'literal-note-desktop.png','#selected');
 await typeText(sid,'#search',firstRow.finding_key);
 current=await inspect(sid,'two accounts sharing the same finding key');
 assert.deepEqual(current.visibleRows.map(r=>r.row_id).sort(),[firstRow.row_id,secondRow.row_id].sort());
 current=await selectRow(sid,secondRow);assertForm(current,secondRow);
 await typeText(sid,'#reviewer',edits[1].reviewer);await typeText(sid,'#note',edits[1].note);
 await edit(sid,'#review-status',edits[1].review_status,'change');
 current=await inspect(sid,'second same-key account receives its own different annotation');
 assertRow(current,secondRow);assertForm(current,edits[1]);
 await typeText(sid,'#search',firstRow.account_no);
 current=await selectRow(sid,firstRow);assertForm(current,edits[0]);
 assert.deepEqual(current.history.map(r=>({row_id:r.row_id,html:r.html})),historyHTML);
 check('Exact row/account identity survives filtering: two same-key accounts retain distinct edits and literal markup stays textarea text');

 await typeText(sid,'#search',untouched.account_no);
 current=await selectRow(sid,untouched);assertForm(current,untouched);
 assert.deepEqual(current.visibleRows.map(r=>r.row_id),[untouched.row_id]);
 const first=await actualDownload(sid,edits,'filtered-complete');
 assert.equal(first.validation.current_rows,3);assert.equal(first.validation.history_rows,2);assert.equal(first.validation.manifest_rows,1);
 current=await inspect(sid,'complete download while both edited accounts remain filtered out');
 assertForm(current,untouched);assert.deepEqual(current.history.map(r=>({row_id:r.row_id,html:r.html})),historyHTML);
 check('The real filtered-view download contains every current/history/manifest row and passes the unchanged original native worksheet loader');

 await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false},sid);
 await typeText(sid,'#search',firstRow.account_no);current=await selectRow(sid,firstRow);assertForm(current,edits[0]);
 const recoveredEdits=edits.map(e=>({...e}));
 recoveredEdits[0].note+='\nAfter download: retain this pending amendment.';
 await typeText(sid,'#note',recoveredEdits[0].note);
 const beforeStale=await inspect(sid,'phone pending amendment before external source-byte change');
 assertForm(beforeStale,recoveredEdits[0]);assert.ok(beforeStale.viewport.pageWidth<=391);
 await fs.appendFile(sourceWorkingPath,'\n');
 const changedSha=hash(await fs.readFile(sourceWorkingPath));assert.notEqual(changedSha,oracle.worksheet_sha256);
 fileChanges.push({action:'append one LF to this receiver’s disposable selected-file copy',before:oracle.worksheet_sha256,after:changedSha});
 const staleDownloads=downloadCount(),staleResponseCount=downloadResponses().length;
 assert.equal(beforeStale.downloadDisabled,false);
 await click(sid,'#download');
 await waitFor(()=>downloadResponses().length>staleResponseCount,'observed stale-source HTTP response');
 assert.equal(downloadResponses().at(-1).status,409);
 await waitFor(()=>evaluate(sid,'!document.querySelector("#download-error").hidden&&document.querySelector("#download-error").textContent.trim().length>0'),'visible stale-source refusal');
 const stale=await inspect(sid,'observed 409 retains the pending current-row amendment');
 assertForm(stale,recoveredEdits[0]);assert.equal(downloadCount(),staleDownloads);
 assert.deepEqual(stale.history.map(r=>({row_id:r.row_id,html:r.html})),historyHTML);
 assert.equal(hash(await fs.readFile(sourceWorkingPath)),changedSha,'Refusal must not overwrite the externally changed selected file');
 await screenshot(sid,'stale-source-mobile.png','#selected');
 check('An observed change to the disposable selected source produces HTTP 409, saves no file and retains the pending in-page amendment');

 await fs.writeFile(sourceWorkingPath,originalSource);
 fileChanges.push({action:'restore exact admitted bytes in the same disposable copy',before:changedSha,after:hash(await fs.readFile(sourceWorkingPath))});
 const recovered=await actualDownload(sid,recoveredEdits,'restored-source',true);
 assert.notEqual(recovered.sha256,first.sha256);
 assert.ok(recovered.validation.native_reconciliation?.exit_code===0);
 current=await inspect(sid,'restored-source retry preserves amended fields and history');
 assertRow(current,firstRow);assertForm(current,recoveredEdits[0]);
 assert.deepEqual(current.history.map(r=>({row_id:r.row_id,html:r.html})),historyHTML);
 assert.ok(current.viewport.pageWidth<=391);assert.equal(current.historyEditableInputs,0);
 assert.equal(new Set(current.ids).size,current.ids.length);
 await screenshot(sid,'recovered-edit-mobile.png','#selected');
 assert.deepEqual(exceptions,[]);
 assert.ok(requests.every(request=>new URL(request.url).origin===new URL(url).origin),'Observed application page requests stay on its loopback service');
 assert.deepEqual(await hashSources(),before);
 assert.equal(execFileSync('git',['-C',sourceRoot,'status','--porcelain'],{encoding:'utf8'}),'');
 assert.equal(hash(await fs.readFile(path.join(fixture,'desk-current-with-history.csv'))),oracle.worksheet_sha256);
 assert.equal(hash(await fs.readFile(sourceWorkingPath)),oracle.worksheet_sha256);
 check('Restoring admitted source bytes permits retry; the amended real download reconciles through the original native command without changing source, history or report');
 receipt={schema:'hamon.utility_desk.independent_browser.v1',status:'pass',checks,node:process.version,browser:browserVersion,
  frozenNativeCommit,sourceTree:expectedTree,sourceSha256:before,fixtureSha256:oracle.worksheet_sha256,
  actualBrowser:true,actualDownloads:artifacts,observations,downloadEvents,fileChanges,requests,responses,exceptions,
  viewports:[[1280,1000],[390,844]],sourceModified:false,selectedSourceFileRestored:true,
  exactFixtureNeverModified:true,productStateInjected:false,
  inputMethod:'Native pointer buttons and native Ctrl+A/insertText/Tab for text; actual HTML select values dispatch change events.',
  scope:'Only new editable-desk consumer. No baseline/native checker suite replay; original native review command runs once on the recovered actual download.',
  nativeServer:{command:[python,...command],cwd:packageRoot,url}};
}catch(error){
 await fs.writeFile(path.join(evidenceDir,'browser-failure.json'),JSON.stringify({status:'fail',checks,error:String(error.stack??error),
  frozenNativeCommit,sourceTree:expectedTree,fixtureSha256:oracle.worksheet_sha256,sourceSha256:before,
  observations,exceptions,requests,responses,downloadEvents,artifacts,fileChanges},null,2)+'\n');
 throw error;
}finally{
 if(socket?.readyState===WebSocket.OPEN)await Promise.race([send('Browser.close').catch(()=>{}),delay(3000)]);
 socket?.close();await stopChild(browser);await stopChild(server);
 await fs.rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:100});
 for(const task of pending.values())clearTimeout(task.timer);
 await fs.writeFile(path.join(evidenceDir,'server.stdout'),serverStdout);
 await fs.writeFile(path.join(evidenceDir,'server.stderr'),serverStderr);
 await fs.writeFile(path.join(evidenceDir,'chromium-stderr.log'),chromiumStderr);
}
await fs.writeFile(path.join(evidenceDir,'browser-receipt.json'),JSON.stringify(receipt,null,2)+'\n');
console.log(JSON.stringify({status:receipt.status,checks:checks.length,sourceTree:expectedTree,actualDownloads:artifacts.map(a=>({filename:a.filename,sha256:a.sha256,bytes:a.bytes})),evidenceDir}));
