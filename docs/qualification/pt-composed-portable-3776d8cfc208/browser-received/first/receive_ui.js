"use strict";
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),cp=require('node:child_process'),crypto=require('node:crypto'),net=require('node:net');
const {isDeepStrictEqual}=require('node:util');
if(os.hostname().toLowerCase()!=='hamon-thinkpad'||os.userInfo().username!=='jacob'||process.platform!=='linux'||process.versions.node!=='22.22.1')throw Error('Unexpected native receiver');
const extracted=path.resolve(process.argv[2]),stage=path.resolve(process.argv[3]),expectedPath=path.resolve(process.argv[4]);
const git=b=>crypto.createHash('sha1').update(Buffer.from('blob '+b.length+'\0')).update(b).digest('hex');
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
const fingerprint=p=>{const raw=fs.readFileSync(p),s=fs.statSync(p,{bigint:true});return{bytes:raw.length,sha256:digest(raw),git_blob:git(raw),mtime_ns:s.mtimeNs.toString()};};
if(git(fs.readFileSync(expectedPath))!=='a072989cfab2f17e7c6b805a22e084b0c46ef703')throw Error('Oracle identity refused');
const expected=JSON.parse(fs.readFileSync(expectedPath,'utf8'));
for(const r of expected.files){const p=path.join(extracted,r.path),a=fingerprint(p);if(!['bytes','sha256','git_blob'].every(k=>a[k]===r[k]))throw Error('Source identity refused '+r.path);}
const profile=path.join(stage,'profile'),downloads=path.join(stage,'downloads'),reportDir=path.join(stage,'new-report');fs.mkdirSync(profile);fs.mkdirSync(downloads);
let origin,server,serverClosed=false,serverExit=null,serverOut='',serverErr='';const networkErrors=[];
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const browserPath='/snap/bin/chromium';
const browserArgs=['--headless=new','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-sync','--disable-component-update','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'];
const child=cp.spawn(browserPath,browserArgs,{stdio:['ignore','pipe','pipe'],windowsHide:true});
let stderr='',stdout='',ws,seq=0,session,closed=false,closeResult=null,ownedBrowserPid=null,launcherError=null;
const pending=new Map(),events=[];child.stdout.on('data',b=>stdout+=b.toString());child.stderr.on('data',b=>stderr+=b.toString());child.on('exit',(code,signal)=>{closed=true;closeResult={code,signal};});child.on('error',e=>{launcherError=String(e);});
function send(method,params={},sessionId){
  return new Promise((resolve,reject)=>{
    const id=++seq;
    const timer=setTimeout(()=>{pending.delete(id);reject(Error("CDP timeout: "+method));},8000);
    pending.set(id,{resolve,reject,timer});
    ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));
  });
}
async function evaluate(expression){
 const r=await send("Runtime.evaluate",{expression,awaitPromise:true,returnByValue:true,userGesture:true},session);
 if(r.exceptionDetails)throw Error("Page evaluation: "+JSON.stringify(r.exceptionDetails));
 return r.result.value;
}
async function setup(){
 const active=path.join(profile,"DevToolsActivePort");
 const deadline=Date.now()+10000;
 while(!fs.existsSync(active)&&Date.now()<deadline)await delay(50);
 if(!fs.existsSync(active))throw Error("Owned browser did not publish DevToolsActivePort");
 const lines=fs.readFileSync(active,"utf8").trim().split(/\r?\n/);
 if(!/^\d+$/.test(lines[0])||!/^[\/]devtools[\/]browser[\/][A-Za-z0-9-]+$/.test(lines[1]))throw Error("Unexpected owned browser endpoint");
 ws=new WebSocket("ws://127.0.0.1:"+lines[0]+lines[1]);
 await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error("Owned WebSocket connection timed out")),8000);ws.addEventListener("open",()=>{clearTimeout(t);resolve();},{once:true});ws.addEventListener("error",e=>{clearTimeout(t);reject(e);},{once:true});});
 ws.addEventListener("message",event=>{
   const msg=JSON.parse(String(event.data));
   if(msg.id&&pending.has(msg.id)){const p=pending.get(msg.id);clearTimeout(p.timer);pending.delete(msg.id);msg.error?p.reject(Error(JSON.stringify(msg.error))):p.resolve(msg.result);}
   else if(msg.method){events.push(msg);if(msg.method==='Fetch.requestPaused'){
     const url=msg.params.request.url;
     const allowed=url.startsWith(origin+'/')&&msg.params.request.method==='GET';
     send(allowed?'Fetch.continueRequest':'Fetch.failRequest',{requestId:msg.params.requestId,...(allowed?{}:{errorReason:'BlockedByClient'})},msg.sessionId).catch(e=>networkErrors.push(String(e)));
   }}
 });
 const version=await send("Browser.getVersion");
 const processInfo=await send("SystemInfo.getProcessInfo");
 const browsers=processInfo.processInfo.filter(p=>p.type==="browser");
 if(browsers.length!==1||!Number.isInteger(browsers[0].id)||browsers[0].id<=0)throw Error("Owned browser process identity unavailable");
 ownedBrowserPid=browsers[0].id;
 await send("Browser.setDownloadBehavior",{behavior:"allowAndName",downloadPath:downloads,eventsEnabled:true});
 const target=await send("Target.createTarget",{url:"about:blank"});
 const attached=await send("Target.attachToTarget",{targetId:target.targetId,flatten:true});
 session=attached.sessionId;
 await send("Page.enable",{},session);
 await send("Runtime.enable",{},session);
 await send("Network.enable",{},session);
 await send("Fetch.enable",{patterns:[{urlPattern:"*"}]},session);
 await send("Emulation.setDeviceMetricsOverride",{width:1280,height:900,deviceScaleFactor:1,mobile:false},session);
 return version;
}
async function navigate(){
 await send('Page.setLifecycleEventsEnabled',{enabled:true},session);
 const cursor=events.length;
 const nav=await send('Page.navigate',{url:origin+'/'},session);
 if(nav.errorText||!nav.loaderId)throw Error('Navigation refused '+JSON.stringify(nav));
 const end=Date.now()+8000;
 while(Date.now()<end){
   if(events.slice(cursor).some(e=>e.sessionId===session&&e.method==='Page.lifecycleEvent'&&e.params.name==='load'&&e.params.frameId===nav.frameId&&e.params.loaderId===nav.loaderId)){
     const tree=await send('Page.getFrameTree',{},session);
     if(tree.frameTree.frame.url===origin+'/'&&tree.frameTree.frame.loaderId===nav.loaderId)return;
   }
   await delay(40);
 }
 throw Error('Intended navigation did not finish');
}
async function screenshot(name){
 const r=await send("Page.captureScreenshot",{format:"png",captureBeyondViewport:false},session);
 fs.writeFileSync(path.join(stage,name),Buffer.from(r.data,"base64"));
 return fingerprint(path.join(stage,name));
}
async function cleanup(){
 let acknowledged=false;
 if(ws&&ws.readyState===WebSocket.OPEN){try{await send("Browser.close");acknowledged=true;}catch(e){}}
 let browserGone=false;
 if(ownedBrowserPid){
   const alive=()=>{try{process.kill(ownedBrowserPid,0);return true;}catch(e){if(e.code==="ESRCH")return false;throw e;}};
   const deadline=Date.now()+20000;
   while(alive()&&Date.now()<deadline)await delay(50);
   browserGone=!alive();
 }
 if(ws)ws.close();
 fs.writeFileSync(path.join(stage,"browser.stdout"),stdout);
 fs.writeFileSync(path.join(stage,"browser.stderr"),stderr);
 return {browserCloseAcknowledged:acknowledged,ownedBrowserPid,ownedBrowserNoLongerRunning:browserGone,launcherExit:closeResult};
}

const receipt={schema:'pt.composed-ui.browser/1',at:new Date().toISOString(),stage,source_commit:expected.source_commit,checks:[],downloads:[],screenshots:[],scope:'One actual Drive kit UI. Necessary server-startup report generation, then read-only filtering, checklist and full CSV export. No staff write, calendar/generator/run action, physical input or clinical decision.'};
function check(name,ok,detail){receipt.checks.push({name,passed:!!ok,...(detail===undefined?{}:{detail})});if(!ok)throw Error('Failed '+name+': '+JSON.stringify(detail));}
async function waitFor(expression){const end=Date.now()+8000;while(Date.now()<end){if(await evaluate(expression))return;await delay(30);}throw Error('UI wait expired '+expression);}
async function key(key,code,virtual){for(const type of ['keyDown','keyUp'])await send('Input.dispatchKeyEvent',{type,key,code,windowsVirtualKeyCode:virtual,nativeVirtualKeyCode:virtual,...(type==='keyDown'&&key==='Enter'?{text:'\r',unmodifiedText:'\r'}:{})},session);}
async function click(selector,keyboard=false){
 if(keyboard){await evaluate('document.querySelector('+JSON.stringify(selector)+').focus()');await key('Enter','Enter',13);}
 else{const pt=await evaluate('(()=>{const e=document.querySelector('+JSON.stringify(selector)+');e.scrollIntoView({block:"center"});const r=e.getBoundingClientRect();if(!r.width||!r.height||e.disabled)throw Error("Control unavailable");return{x:r.x+r.width/2,y:r.y+r.height/2};})()');for(const type of ['mouseMoved','mousePressed','mouseReleased'])await send('Input.dispatchMouseEvent',{type,x:pt.x,y:pt.y,...(type==='mouseMoved'?{}:{button:'left',clickCount:1})},session);}
}
async function chooseFirstOption(selector){await evaluate('document.querySelector('+JSON.stringify(selector)+').focus()');await key('Home','Home',36);await key('ArrowDown','ArrowDown',40);await key('Enter','Enter',13);}
async function type(selector,text){await click(selector);await send('Input.insertText',{text},session);}
async function capture(name){const geometry=await evaluate('({innerWidth,innerHeight,clientWidth:document.documentElement.clientWidth,contentWidth:document.documentElement.scrollWidth,scrollX,scrollY})');const id=await screenshot(name);receipt.screenshots.push({file:name,geometry,...id});return geometry;}
const watchReport=()=>Object.fromEntries(fs.readdirSync(reportDir).sort().map(n=>[n,fingerprint(path.join(reportDir,n))]));
const ucRows=()=>evaluate(`Array.from(document.querySelectorAll('#uc-rows tbody tr'),r=>Array.from(r.cells,c=>c.innerText))`);
async function startServer(){
 const reservation=net.createServer();await new Promise((resolve,reject)=>{reservation.once('error',reject);reservation.listen(0,'127.0.0.1',resolve);});
 const port=reservation.address().port;await new Promise(resolve=>reservation.close(resolve));origin='http://127.0.0.1:'+port;
 const env={...process.env,PYTHONDONTWRITEBYTECODE:'1',PYTHONUNBUFFERED:'1'};delete env.PYTHONPATH;delete env.PYTHONHOME;
 const argv=['-B','-m','ptauth','serve','--data','sample_data','--out',reportDir,'--clinic-timezone','UTC','--port',String(port)];
 server=cp.spawn('/usr/bin/python3',argv,{cwd:path.join(extracted,'pt_auth'),env,stdio:['ignore','pipe','pipe']});
 receipt.server={pid:server.pid,argv:['/usr/bin/python3',...argv],origin};
 server.stdout.on('data',b=>serverOut+=b.toString());server.stderr.on('data',b=>serverErr+=b.toString());server.on('exit',(code,signal)=>{serverClosed=true;serverExit={code,signal};});server.on('error',e=>{receipt.server.error=String(e);});
 const end=Date.now()+15000;
 while(Date.now()<end){if(serverClosed||receipt.server.error)throw Error('Owned server exited during startup');const open=await new Promise(resolve=>{const s=net.connect({host:'127.0.0.1',port});s.setTimeout(400);s.once('connect',()=>{s.destroy();resolve(true);});s.once('error',()=>resolve(false));s.once('timeout',()=>{s.destroy();resolve(false);});});if(open)return;await delay(40);}
 throw Error('Owned server did not start');
}
async function stopServer(){
 if(server&&!serverClosed){server.kill('SIGTERM');let end=Date.now()+5000;while(!serverClosed&&Date.now()<end)await delay(30);if(!serverClosed){server.kill('SIGKILL');end=Date.now()+5000;while(!serverClosed&&Date.now()<end)await delay(30);}}
 fs.writeFileSync(path.join(stage,'server.stdout'),serverOut,{flag:'wx'});fs.writeFileSync(path.join(stage,'server.stderr'),serverErr,{flag:'wx'});
 let absent=false;if(server?.pid){try{process.kill(server.pid,0);}catch(e){if(e.code==='ESRCH')absent=true;else throw e;}}
 return{pid:server?.pid,waited:serverClosed,exit:serverExit,absent};
}
function noCaches(dir){return fs.readdirSync(dir,{withFileTypes:true}).every(e=>e.name!=='__pycache__'&&!e.name.endsWith('.pyc')&&(!e.isDirectory()||noCaches(path.join(dir,e.name))));}
(async()=>{
 try{
  await startServer();receipt.browserVersion=await setup();await navigate();await waitFor('document.querySelectorAll("#cards .card").length===9&&document.querySelector("#shown").textContent==="26 of 26 items"');
  receipt.report_before=watchReport();
  check('startupReportHasOnlySevenExpectedFiles',isDeepStrictEqual(Object.keys(receipt.report_before),['audit.jsonl','digest.html','ledger.csv','summary.json','uncovered_visits.csv','visit_status_review.csv','worklist.csv']));
  const initial=await evaluate('({warning:document.querySelector(".syn").textContent,date:document.querySelector("#asof").value,zone:document.querySelector("#timezone").textContent,cards:Array.from(document.querySelectorAll("#cards .card"),x=>[x.querySelector("b").textContent,x.querySelector("span").textContent]),rows:document.querySelectorAll("#work tr").length-1})');
  check('syntheticScopeAndRecordedDateZone',initial.warning.includes('NOT REAL PATIENTS')&&initial.warning.includes('nothing is sent to any payer')&&initial.date===expected.as_of&&initial.zone==='Clinic time zone: UTC');
  check('sampleCountCardsAnd26WorkItems',isDeepStrictEqual(initial.cards.map(x=>x[0]),['11','15','0','194','2','0','0/26','40','46'])&&initial.rows===26,initial);
  await chooseFirstOption('#fp');await waitFor('document.querySelector("#fp").value==="P1"&&document.querySelector("#shown").textContent==="11 of 26 items"');
  check('nativePrioritySelectionShowsElevenP1',await evaluate('Array.from(document.querySelectorAll("#work .p")).every(x=>x.textContent==="P1")'));
  await type('#q',expected.work_item.patient_id);await waitFor('document.querySelector("#shown").textContent==="1 of 26 items"');
  const row=await evaluate('Array.from(document.querySelectorAll("#work tr")[1].cells,c=>c.innerText)');const w=expected.work_item;
  check('literalPatientFilterKeepsOneExactWorkItem',row[0]==='P1'&&row[1].includes(w.patient_name)&&row[1].includes(w.patient_id)&&row[1].includes(w.clinic)&&row[2].includes(w.payer_name)&&row[2].includes(w.auth_no)&&row[5].startsWith(w.auth_end)&&row[6]===w.next_visit&&row[7]===w.submit_by,row);
  await click('#work details summary',true);
  check('enterOpensExactFiveItemChecklist',await evaluate('document.querySelector("#work details").open')&&isDeepStrictEqual(await evaluate('Array.from(document.querySelectorAll("#work details li"),x=>x.textContent.replace(/^☐ /,""))'),w.checklist));
  await evaluate('document.querySelector("#work").scrollIntoView({block:"center"})');await capture('worklist-desktop.png');
  await click('#tabs button[data-t="uncovered"]');await waitFor('!document.querySelector("#t-uncovered").classList.contains("hidden")');
  const all=await ucRows();check('uncoveredTabShowsAll196OriginalVisitIDs',isDeepStrictEqual(all.map(r=>r[0].split('\n')[0]),expected.all_uncovered_ids)&&await evaluate('document.querySelector("#uc-shown").textContent==="196 of 196 appointments · as of 2026-09-28"'));
  await chooseFirstOption('#uc-status');await waitFor('document.querySelector("#uc-status").value==="scheduled"&&document.querySelectorAll("#uc-rows tbody tr").length===194');
  check('scheduledFilterHas194Rows',await evaluate('Array.from(document.querySelectorAll("#uc-rows tbody tr"),r=>r.cells[2].textContent).every(x=>x==="scheduled")'));
  await type('#uc-search',w.patient_id);await waitFor('document.querySelectorAll("#uc-rows tbody tr").length===8');
  const selected=await ucRows();const want=expected.selected_uncovered.map(r=>[r.visit_id+'\n'+r.visit_type,r.visit_date,r.status,r.patient_name+'\n'+r.patient_id,r.clinic,r.therapist,r.payer_name+'\n'+r.payer_id,r.evidence]);
  check('eightSelectedVisitsMatchFrozenOriginalFields',isDeepStrictEqual(selected,want),selected);
  check('completeExportLabelStatesFilterIndependence',await evaluate('document.querySelector("#uc-export").textContent.includes("Complete review; independent of these filters.")'));
  const eventStart=events.length;await click('#uc-export a');const end=Date.now()+15000;let begin;
  while(Date.now()<end){begin=events.slice(eventStart).find(e=>e.method==='Browser.downloadWillBegin');if(begin&&events.slice(eventStart).some(e=>e.method==='Browser.downloadProgress'&&e.params.guid===begin.params.guid&&e.params.state==='completed'))break;await delay(30);}
  if(!begin||!events.slice(eventStart).some(e=>e.method==='Browser.downloadProgress'&&e.params.guid===begin.params.guid&&e.params.state==='completed'))throw Error('CSV download did not complete');
  const downloaded=fs.readFileSync(path.join(downloads,begin.params.guid)),saved=path.join(stage,'downloaded-uncovered-visits.csv');fs.writeFileSync(saved,downloaded,{flag:'wx'});receipt.downloads.push({guid:begin.params.guid,suggestedFilename:begin.params.suggestedFilename,...fingerprint(saved)});
  check('oneDownloadedCompleteCSVExactBytesAndName',begin.params.suggestedFilename==='uncovered_visits.csv'&&downloaded.equals(fs.readFileSync(path.join(reportDir,'uncovered_visits.csv')))&&git(downloaded)===expected.uncovered_csv.git_blob&&digest(downloaded)===expected.uncovered_csv.sha256&&downloaded.length===expected.uncovered_csv.bytes);
  check('downloadPreservesEightRowFilter',isDeepStrictEqual(await ucRows(),selected)&&await evaluate('document.querySelector("#uc-search").value==="SYN-1014"&&document.querySelector("#uc-status").value==="scheduled"'));
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false},session);await evaluate('document.querySelector("#uc-filters").scrollIntoView({block:"start"})');const narrow=await capture('uncovered-narrow.png');
  check('390StimulusFitsAvailablePageWidth',narrow.innerWidth===390&&narrow.clientWidth>0&&narrow.clientWidth<=390&&narrow.contentWidth<=narrow.clientWidth,narrow);
  check('narrowRetainsEightRowsAndScrollableReviewRegion',isDeepStrictEqual(await ucRows(),selected)&&await evaluate('document.querySelector("#uc-rows .review-table").getAttribute("tabindex")==="0"&&getComputedStyle(document.querySelector("#uc-rows .review-table")).overflowX==="auto"'));
  receipt.requests=events.filter(e=>e.method==='Network.requestWillBeSent').map(e=>({url:e.params.request.url,method:e.params.request.method}));
  check('onlyOwnLoopbackGETRequests',receipt.requests.length>0&&receipt.requests.every(r=>r.url.startsWith(origin+'/')&&r.method==='GET')&&networkErrors.length===0,receipt.requests);
  receipt.javascriptExceptions=events.filter(e=>e.method==='Runtime.exceptionThrown').map(e=>e.params);
  check('noUncaughtJavaScriptExceptions',receipt.javascriptExceptions.length===0);
  check('exactlyOneExplicitDownload',events.filter(e=>e.method==='Browser.downloadWillBegin').length===1&&receipt.downloads.length===1);
  receipt.report_after=watchReport();check('allSevenGeneratedOutputsUnchangedByUI',isDeepStrictEqual(receipt.report_before,receipt.report_after));
  check('noStaffStateOrBytecodeCacheCreated',!fs.existsSync(path.join(reportDir,'work_state.json'))&&noCaches(extracted));
 }catch(e){receipt.error=String(e.stack||e);}
 finally{
  try{receipt.browserClose=await cleanup();}catch(e){receipt.browserClose={cleanupError:String(e),ownedBrowserPid,launcherExit:closeResult};}
  try{receipt.serverClose=await stopServer();}catch(e){receipt.serverClose={cleanupError:String(e),exit:serverExit};}
  receipt.checks.push({name:'ownedBrowserCloseAcknowledgedAndAbsent',passed:!!(receipt.browserClose.browserCloseAcknowledged&&receipt.browserClose.ownedBrowserNoLongerRunning)});
  receipt.checks.push({name:'ownedServerTerminatedAndReaped',passed:!!(receipt.serverClose.waited&&receipt.serverClose.absent)});
  receipt.launcherError=launcherError;receipt.networkErrors=networkErrors;
  receipt.passed=!receipt.error&&!launcherError&&receipt.checks.every(c=>c.passed);
  fs.writeFileSync(path.join(stage,'receiving.json'),JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({stage,passed:receipt.passed,checks:receipt.checks.length,error:receipt.error,browserClose:receipt.browserClose,serverClose:receipt.serverClose}));process.exitCode=receipt.passed?0:1;
 }
})();
