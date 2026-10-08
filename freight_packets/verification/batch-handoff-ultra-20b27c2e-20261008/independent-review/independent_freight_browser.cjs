#!/usr/bin/env node
/* Independent real-Chrome Freight receiving. Candidate code/tests are not imported here. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const cp = require('node:child_process');
const assert = require('node:assert/strict');
const puppeteer = require('/Users/me/.npm/_npx/4b4c857f6efdfb61/node_modules/puppeteer/lib/puppeteer/puppeteer.js');
const [sourceArg, fixtureArg, outputArg] = process.argv.slice(2);
if (!sourceArg || !fixtureArg || !outputArg) throw new Error('source fixture output required');
const source = path.resolve(sourceArg), fixture = path.resolve(fixtureArg), output = path.resolve(outputArg);
const root = '/tmp/ultra-20b27c2e-runtime-freight-review';
const live = path.join(output, 'fixture');
fs.mkdirSync(output, {recursive:true});
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const json = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(fn, message, timeout = 7000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { const value = await fn(); if (value) return value; await sleep(25); }
  throw new Error(message);
}
function snapshot(dir) {
  const out = {};
  function walk(at) {
    for (const entry of fs.readdirSync(at, {withFileTypes:true}).sort((a,b)=>a.name.localeCompare(b.name))) {
      const p = path.join(at, entry.name);
      if (entry.isDirectory()) walk(p);
      else if (entry.isFile()) {
        const data = fs.readFileSync(p);
        out[path.relative(dir,p)] = {bytes:data.length,sha256:hash(data)};
      }
    }
  }
  walk(dir); return out;
}
const record = {source, fixture, browser:'installed Chrome', groups:[], requests:[],
                downloads:[], blocked:[], pageErrors:[], timing:[], custody:{}, sourcePins:null};
let browser, page, cdp, server, url, gate = null, currentGroup, downloadDir;
function custody(value) {
  const key = hash(Buffer.from(JSON.stringify(value)));
  record.custody[key] ??= value; return key;
}
async function group(name, fn) {
  currentGroup = name;
  const r = {name, started:new Date().toISOString()};
  record.groups.push(r);
  try { await reset(); await fn(r); r.status='pass'; }
  catch (error) { r.status='fail'; r.error=String(error.stack || error); }
  finally { if (gate) await releaseGate(gate); r.finished=new Date().toISOString(); }
  console.log(JSON.stringify({group:name,status:r.status,error:r.error?.split('\n')[0]}));
}
async function apiSummary() {
  const r = await fetch(url + '/api/summary');
  assert.equal(r.status, 200); return r.json();
}
function rows(view, indices) {
  return indices.map(i => {
    const load = view.packets[i].load_id;
    return {load_id:load,evidence_version:view.evidence_versions[load],
            review_version:view.review_versions[load]};
  });
}
async function button(text, scope='#freight-batch-panel') {
  const handles = await page.$$(scope + ' button');
  for (const handle of handles) {
    if ((await handle.evaluate(el => el.textContent.trim())) === text) return handle;
  }
  throw new Error('Public control missing: ' + text);
}
async function clickButton(text, scope) { await (await button(text,scope)).click(); }
async function feature() {
  await page.click('button[data-t="files"]');
  const handle = await page.$('#freight-batch-panel');
  assert.ok(handle, 'Baseline has no Freight batch panel');
  await page.waitForSelector('#freight-batch-panel input[type="checkbox"]',{timeout:2500});
}
async function selectedIndices() {
  return page.$$eval('#freight-batch-panel input[type="checkbox"]',
    els => els.map((el,i)=>el.checked?i:null).filter(i=>i!==null));
}
async function check(indices) {
  const els = await page.$$('#freight-batch-panel input[type="checkbox"]');
  for (const i of indices) {
    assert.ok(els[i], 'Displayed checkbox index missing: ' + i);
    assert.equal(await els[i].evaluate(el=>el.disabled), false);
    await els[i].click();
  }
}
async function reset() {
  if (gate) await releaseGate(gate);
  if (page) await page.goto('about:blank');
  if (fs.existsSync(live)) fs.rmSync(live,{recursive:true});
  fs.cpSync(fixture,live,{recursive:true});
  downloadDir = path.join(output,'downloads',currentGroup.replace(/[^a-zA-Z0-9_-]/g,'-'));
  fs.mkdirSync(downloadDir,{recursive:true});
  await cdp.send('Browser.setDownloadBehavior',
                 {behavior:'allow',downloadPath:downloadDir,eventsEnabled:true});
  await page.goto(url, {waitUntil:'networkidle0'});
  await page.waitForSelector('#download-review-bundle');
  const summary = await apiSummary();
  const load = summary.packets[6].load_id;
  await page.click('#t-packets tr[data-l="' + load.replace(/["\\]/g,'\\$&') + '"]');
}
function downloaded() {
  return fs.readdirSync(downloadDir).filter(f=>!f.endsWith('.crdownload')).map(f=>path.join(downloadDir,f));
}
async function actualDownload() {
  await until(()=>downloaded().length>0,'Chrome did not save a real download');
  await until(()=>!fs.readdirSync(downloadDir).some(f=>f.endsWith('.crdownload')),
              'Chrome download remained incomplete');
  const files=downloaded();
  assert.equal(files.length,1);
  const data=fs.readFileSync(files[0]);
  assert.ok(data.subarray(0,2).equals(Buffer.from('PK')));
  return {filename:path.basename(files[0]),bytes:data.length,sha256:hash(data),data};
}
async function noDownload() {
  await sleep(300);
  assert.deepEqual(downloaded(),[],'A retired or malformed response became a saved download');
}
function startGate(pathname='/api/review-batch', envelope=null) {
  assert.equal(gate,null);
  const g = {pathname,envelope,group:currentGroup,ready:false,released:false};
  g.promise = new Promise(resolve => {g.release=resolve;});
  g.finished = new Promise(resolve => {g.finish=resolve;});
  gate=g; return g;
}
async function releaseGate(g) {
  if (!g.released) {g.released=true;g.release();}
  if (g.ready) await Promise.race([g.finished,sleep(3000)]);
  if (gate===g) gate=null;
}
async function prepareHeld() {
  await feature(); await check([0,2,4]);
  const g=startGate();
  await clickButton('Download selected reviews');
  await until(()=>g.ready,'Browser did not submit selected native request');
  return g;
}
async function compareNativeBatch(download, requestBody, r) {
  const expected=await fetch(url+'/api/review-batch',{
    method:'POST',headers:{'Content-Type':'application/json'},body:requestBody});
  assert.equal(expected.status,200);
  const data=Buffer.from(await expected.arrayBuffer());
  assert.equal(download.sha256,hash(data),'Saved browser bytes differ from native API');
  r.download={filename:download.filename,bytes:download.bytes,sha256:download.sha256};
  r.request=JSON.parse(requestBody);
}
function lastBatchRequest() {
  return record.requests.filter(x=>x.group===currentGroup&&x.path==='/api/review-batch').at(-1);
}
async function saveReview(load, note) {
  const summary=await apiSummary();
  const r=await fetch(url+'/api/decision',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({load_id:load,decision:'adjust',note,
                         evidence_version:summary.evidence_versions[load]})});
  assert.equal(r.status,200); await r.arrayBuffer();
}
async function refreshNativeView() {
  await page.evaluate(async()=>{await load(api('/api/summary'));});
}
async function main() {
  fs.cpSync(fixture,live,{recursive:true});
  const log=fs.openSync(path.join(output,'server.stdout.log'),'w');
  const err=fs.openSync(path.join(output,'server.stderr.log'),'w');
  server=cp.spawn('/usr/local/bin/python3',[path.join(root,'independent_freight_review.py'),
    'serve','--source',source,'--fixture',live,'--output',path.join(output,'server')],
    {env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},stdio:['ignore',log,err]});
  await until(()=>fs.existsSync(path.join(output,'server','server.json')),'Native server startup failed');
  const info=JSON.parse(fs.readFileSync(path.join(output,'server','server.json'),'utf8'));
  url=info.url;record.sourcePins=info.source_pins;record.fixtureBefore=snapshot(fixture);
  browser=await puppeteer.launch({
    executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless:true,userDataDir:path.join(output,'chrome-profile'),
    args:['--disable-background-networking','--disable-sync','--disable-component-update',
          '--disable-default-apps','--no-first-run','--no-default-browser-check'],
  });
  record.browserVersion=await browser.version();
  cdp=await browser.target().createCDPSession();
  cdp.on('Browser.downloadWillBegin',x=>record.downloads.push({group:currentGroup,event:'begin',...x}));
  cdp.on('Browser.downloadProgress',x=>{
    if(x.state==='completed'||x.state==='canceled')
      record.downloads.push({group:currentGroup,event:'progress',...x});
  });
  page=await browser.newPage();
  await page.setViewport({width:1100,height:850});
  page.on('pageerror',e=>record.pageErrors.push({group:currentGroup,error:String(e)}));
  await page.setRequestInterception(true);
  page.on('request',async req=>{
    const u=new URL(req.url());
    if (['data:','blob:','about:'].includes(u.protocol)) {await req.continue();return;}
    if (u.origin!==url) {
      record.blocked.push({group:currentGroup,url:req.url()});
      await req.abort('blockedbyclient');return;
    }
    const body=req.postData();
    record.requests.push({group:currentGroup,path:u.pathname,method:req.method(),body,
                          bodySha256:hash(Buffer.from(body||''))});
    const g=gate;
    if (!g || u.pathname!==g.pathname || req.method()!=='POST') {await req.continue();return;}
    try {
      const before=snapshot(live);
      const response=await fetch(req.url(),{method:req.method(),
        headers:{'Content-Type':'application/json'},body});
      const data=Buffer.from(await response.arrayBuffer());
      const headers=Object.fromEntries(response.headers);
      const after=snapshot(live);
      g.ready=true;g.response={status:response.status,headers,bytes:data.length,sha256:hash(data)};
      g.requestBody=body;
      record.timing.push({group:g.group,path:u.pathname,before:custody(before),after:custody(after),
                          nativeResponse:g.response});
      if(u.pathname==='/api/review-batch') assert.deepEqual(before,after);
      await g.promise;
      const changed=g.envelope ? {...headers,...g.envelope} : headers;
      try {await req.respond({status:response.status,headers:changed,body:data});}
      catch(e){record.timing.push({group:g.group,retiredResponseTransport:String(e)});}
    } catch(e) {
      record.timing.push({group:g.group,interceptionError:String(e.stack||e)});
      g.error=String(e);g.ready=true;
      try{await req.abort('failed');}catch(_){}
    } finally {g.finish();}
  });
  await group('00-original-per-load-browser-control',async r=>{
    const summary=await apiSummary();const row=rows(summary,[6])[0];
    const query=new URLSearchParams(row);
    const expected=await fetch(url+'/api/review-bundle?'+query);
    assert.equal(expected.status,200);
    const bytes=Buffer.from(await expected.arrayBuffer());
    const before=snapshot(live);
    await page.click('#download-review-bundle');
    const d=await actualDownload();
    assert.equal(d.sha256,hash(bytes));
    assert.deepEqual(snapshot(live),before);
    r.download={filename:d.filename,bytes:d.bytes,sha256:d.sha256};
  });
  await group('10-visible-selection-and-real-batch-download',async r=>{
    await feature();
    const summary=await apiSummary();
    const labels=await page.$$eval('#freight-batch-panel input[type="checkbox"]',
      els=>els.map(e=>(e.closest('label')||e.parentElement).textContent));
    assert.equal(labels.length,summary.packets.length);
    summary.packets.forEach((p,i)=>assert.ok(labels[i].includes(p.load_id)));
    await check([4,0,2]);
    assert.deepEqual(await selectedIndices(),[0,2,4]);
    const before=snapshot(live);
    await clickButton('Download selected reviews');
    const d=await actualDownload(); const q=lastBatchRequest();
    assert.ok(q);
    const sent=JSON.parse(q.body).loads;
    assert.deepEqual([...sent.map(x=>x.load_id)].sort(),rows(summary,[0,2,4]).map(x=>x.load_id).sort());
    for(const row of sent) assert.deepEqual(row,rows(summary,
      [summary.packets.findIndex(p=>p.load_id===row.load_id)])[0]);
    await compareNativeBatch(d,q.body,r);
    assert.deepEqual(snapshot(live),before);
    await page.screenshot({path:path.join(output,'selected-batch.png'),fullPage:false});
  });
  await group('11-selection-change-retires-real-late-response',async r=>{
    const g=await prepareHeld();assert.equal(g.response.status,200);assert.ok(!g.error);
    await check([7]);
    await releaseGate(g);await noDownload();
    r.retired=g.response;
  });
  await group('12-cancel-retires-response-and-fresh-request-works',async r=>{
    const g=await prepareHeld();
    await clickButton('Cancel batch download');
    await releaseGate(g);await noDownload();
    await until(async()=>!(await (await button('Download selected reviews')).evaluate(e=>e.disabled)),
                'Download remained disabled after cancellation');
    await clickButton('Download selected reviews');
    const d=await actualDownload();await compareNativeBatch(d,lastBatchRequest().body,r);
  });
  await group('13-unsaved-note-prevents-and-retires-download',async r=>{
    const g=await prepareHeld();
    await page.click('button[data-t="packets"]');
    await page.click('#note');await page.type('#note',' changed unsaved');
    await page.click('button[data-t="files"]');
    await releaseGate(g);await noDownload();
    assert.equal(await (await button('Download selected reviews')).evaluate(e=>e.disabled),true);
    const count=record.requests.filter(x=>x.group===currentGroup&&x.path==='/api/review-batch').length;
    await clickButton('Download selected reviews');
    await sleep(100);
    assert.equal(record.requests.filter(x=>x.group===currentGroup&&x.path==='/api/review-batch').length,count);
    r.batchRequests=count;
  });
  await group('14-pending-native-review-prevents-batch',async r=>{
    await feature();await check([0,2,4]);
    await page.click('button[data-t="packets"]');
    const g=startGate('/api/decision');
    await page.click('button[data-d="adjust"]');
    await until(()=>g.ready,'Native review was not submitted');
    await page.click('button[data-t="files"]');
    assert.equal(await (await button('Download selected reviews')).evaluate(e=>e.disabled),true);
    await releaseGate(g);await noDownload();
    r.deliberateFixtureReview=g.response;
  });
  await group('15-selected-identity-refresh-clears-working-selection',async r=>{
    await feature();await check([0,2,4]);
    const summary=await apiSummary();
    await saveReview(summary.packets[2].load_id,'Independent selected review refresh');
    await refreshNativeView();
    assert.deepEqual(await selectedIndices(),[]);
    const text=await page.$eval('#freight-batch-panel',e=>e.textContent);
    assert.match(text,/chang|refresh|again|clear|select/i);
    await noDownload();
    r.visibleMessage=text;
  });
  await group('16-unselected-identity-refresh-retains-selection',async r=>{
    await feature();await check([0,2,4]);
    const summary=await apiSummary();
    await saveReview(summary.packets[7].load_id,'Independent unselected review refresh');
    await refreshNativeView();
    assert.deepEqual(await selectedIndices(),[0,2,4]);
    await clickButton('Download selected reviews');
    const d=await actualDownload();await compareNativeBatch(d,lastBatchRequest().body,r);
  });
  await group('17-malformed-response-type-does-not-download',async r=>{
    await feature();await check([0,2]);
    const g=startGate('/api/review-batch',{'content-type':'application/json'});
    await clickButton('Download selected reviews');
    await until(()=>g.ready,'Missing intercepted native response');
    await releaseGate(g);await noDownload();
    r.nativeResponse=g.response;
  });
  await group('18-unsafe-response-filename-does-not-download',async r=>{
    await feature();await check([0,2]);
    const g=startGate('/api/review-batch',
                     {'content-disposition':'attachment; filename="../../escape.zip"'});
    await clickButton('Download selected reviews');
    await until(()=>g.ready,'Missing intercepted native response');
    await releaseGate(g);await noDownload();
    r.nativeResponse=g.response;
  });
  await group('19-prototype-and-markup-labels-remain-exact-text',async r=>{
    const file=path.join(live,'out','summary.json');
    const summary=JSON.parse(fs.readFileSync(file,'utf8'));
    const oldA=summary.packets[1].load_id,oldB=summary.packets[2].load_id;
    const evil='"><img src="/injected" onerror="window.__freightInjection=7">';
    const map=new Map([[oldA,'__proto__'],[oldB,evil]]);
    for(const section of ['stops','flags','fines','settlements','exceptions','packets'])
      for(const row of summary[section]||[]) if(map.has(row.load_id))row.load_id=map.get(row.load_id);
    fs.writeFileSync(file,JSON.stringify(summary)+'\n');
    const decpath=path.join(live,'out','decisions.json');
    const oldDec=JSON.parse(fs.readFileSync(decpath,'utf8'));
    fs.writeFileSync(decpath,JSON.stringify(Object.fromEntries(
      Object.entries(oldDec).map(([k,v])=>[map.get(k)||k,v])))+'\n');
    await refreshNativeView();await feature();
    assert.equal(await page.$eval('#freight-batch-panel',e=>e.querySelectorAll('img,script,svg').length),0);
    assert.equal(await page.evaluate(()=>window.__freightInjection),undefined);
    const text=await page.$eval('#freight-batch-panel',e=>e.textContent);
    assert.ok(text.includes('__proto__'));assert.ok(text.includes(evil));
    await check([1,2]);await clickButton('Download selected reviews');
    const d=await actualDownload();const q=lastBatchRequest();
    assert.deepEqual(JSON.parse(q.body).loads.map(x=>x.load_id),['__proto__',evil]);
    await compareNativeBatch(d,q.body,r);
    assert.equal(record.requests.some(x=>x.group===currentGroup&&x.path==='/injected'),false);
  });
  record.fixtureAfter=snapshot(fixture);
  assert.deepEqual(record.fixtureAfter,record.fixtureBefore);
  record.failed=record.groups.filter(x=>x.status==='fail').length;
  record.passed=record.groups.filter(x=>x.status==='pass').length;
}
main().catch(e=>{record.infrastructureError=String(e.stack||e);console.error(record.infrastructureError);})
.finally(async()=>{
  if(gate)await releaseGate(gate);
  if(browser)try{await browser.close();}catch(e){record.browserCloseError=String(e);}
  if(server){server.kill('SIGTERM');await Promise.race([
    new Promise(resolve=>server.once('close',resolve)),sleep(3000)]);}
  if(fs.existsSync(live))record.finalLiveFixture=snapshot(live);
  json(path.join(output,'browser-result.json'),record);
  console.log(JSON.stringify({groups:record.groups.length,passed:record.passed,failed:record.failed,
    blocked:record.blocked.length,pageErrors:record.pageErrors.length,
    infrastructureError:record.infrastructureError||null}));
  process.exitCode=(record.infrastructureError||record.failed||record.pageErrors.length
                    ||record.blocked.length)?1:0;
});
