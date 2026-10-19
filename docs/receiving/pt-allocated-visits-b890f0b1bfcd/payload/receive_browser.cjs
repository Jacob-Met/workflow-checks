const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const { chromium } = require('/home/jacob/hamon-b890f0b1bfcd/browser-tools/node_modules/playwright');
const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const ports = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const out = path.join(config.evidence, 'browser');
fs.mkdirSync(out);
const expected = JSON.parse(fs.readFileSync(config.expect_path, 'utf8'));
const normal = JSON.parse(fs.readFileSync(path.join(config.outputs.normal, 'summary.json'), 'utf8'));
const records = normal.allocation_review;
const sha = b => crypto.createHash('sha256').update(b).digest('hex');
const report = {source_pin:'055c863a9484adb1f6f39f54bf6cce90825bf0ad',driver_sha256:sha(fs.readFileSync(__filename)),contract_sha256:'1bd70cbf71076e9621d0453aef0890b147034d8e91352fbcefd4e207cfba2630',fixture_sha256:'da5f0b3dcfcc3b2d80bcbf84a3edaa17e917ef4a6e4864f80506332bee9ca53b',groups:[],page_errors:[],console_errors:[],external_requests:[],requests:[],dialogs:[],downloads:[],captures:[],started_at:new Date().toISOString()};
const reportPath = path.join(out, 'report.json');
function save(){fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');}
function free(p){const s=fs.statfsSync(p);return s.bavail*s.bsize;}
async function group(name,fn){try{const value=await fn();report.groups.push({name,status:'pass',value:value??null});}catch(e){report.groups.push({name,status:'fail',error:{name:e.name,message:e.message,stack:e.stack}});}save();}
let context;
let profile;
let page;
let printPage;
const allowed = new Set(Object.values(ports).map(p=>'http://127.0.0.1:'+p));
async function wire(p){p.on('pageerror',e=>report.page_errors.push(String(e)));p.on('console',m=>{if(m.type()==='error')report.console_errors.push(m.text());});p.on('dialog',async d=>{report.dialogs.push({type:d.type(),message:d.message()});await d.dismiss();});}
async function ids(p=page){return p.locator('#alloc-rows tbody tr').evaluateAll(rs=>rs.map(r=>r.getAttribute('data-visit-id')));}
async function assertIds(wanted,p=page){assert.deepEqual(await ids(p),wanted);}
async function clear(){await page.locator('#alloc-status').selectOption('');await page.locator('#alloc-auth').selectOption('');await page.locator('#alloc-clinic').selectOption('');await page.locator('#alloc-search').fill('');}
function authKey(r){return JSON.stringify([r.auth_patient_id,r.auth_payer_id,r.auth_no,r.auth_start,r.auth_end,r.auth_evidence]);}
async function capture(name,p=page){const file=path.join(out,name+'.png');await p.screenshot({path:file,fullPage:true});const bytes=fs.readFileSync(file);report.captures.push({name,file:path.basename(file),bytes:bytes.length,sha256:sha(bytes)});}
(async()=>{
 try{
  report.capacity_before={tmp_free:free('/tmp'),shm_free:free('/dev/shm')};
  assert(report.capacity_before.tmp_free>=768*1024*1024,'Private browser profile guard: /tmp needs 768 MiB free (profile budget plus reserve)');
  assert(report.capacity_before.shm_free>=512*1024*1024,'Receiving output guard: /dev/shm needs 512 MiB free');
  profile=fs.mkdtempSync('/tmp/hamon-b890f0b1bfcd-pt-profile-v1-');
  report.profile=profile;save();
  context=await chromium.launchPersistentContext(profile,{executablePath:'/snap/bin/chromium',headless:true,chromiumSandbox:true,args:['--disable-dev-shm-usage','--no-first-run','--no-default-browser-check'],timeout:45000,viewport:{width:1280,height:900},acceptDownloads:true});
  report.browser_version=context.browser()?.version()??null;
  const session=await context.newCDPSession(context.pages()[0]);report.browser_version_protocol=await session.send('Browser.getVersion');
  context.on('page',wire);
  context.on('request',r=>report.requests.push({url:r.url(),method:r.method(),resource:r.resourceType()}));
  await context.route('**/*',async route=>{const u=new URL(route.request().url());if(allowed.has(u.origin)||['data:','blob:','about:'].includes(u.protocol))await route.continue();else{report.external_requests.push(route.request().url());await route.abort();}});
  page=context.pages()[0];await wire(page);page.setDefaultTimeout(10000);
  await page.goto('http://127.0.0.1:'+ports.normal+'/');
  await page.waitForFunction(()=>document.querySelector('#alloc-count')?.textContent.startsWith('13 of 13'));
  await page.getByRole('button',{name:'Auth ledger',exact:true}).click();

  await group('all-thirteen-exact-visible-records',async()=>{
   const actual=await page.locator('#alloc-rows tbody tr').evaluateAll(rs=>rs.map(r=>({id:r.getAttribute('data-visit-id'),auth:JSON.parse(r.getAttribute('data-authorization')),cells:[...r.querySelectorAll('td')].map(td=>({primary:td.childNodes[0]?.textContent??'',detail:td.querySelector('small')?.textContent??null}))})));
   assert.equal(actual.length,13);
   for(let i=0;i<records.length;i++){const r=records[i],a=actual[i];assert.equal(a.id,r.visit_id);assert.deepEqual(a.auth,JSON.parse(authKey(r)));assert.deepEqual(a.cells,[
    {primary:r.visit_id,detail:r.visit_type},{primary:r.visit_date,detail:null},
    {primary:r.allocation==='used'?'Used':'Reserved',detail:'Recorded '+r.status},
    {primary:r.patient_name||'Name unavailable',detail:r.patient_id},
    {primary:r.clinic||'Unrecorded',detail:r.therapist||'Therapist unrecorded'},
    {primary:r.payer_name||'Name unavailable',detail:r.payer_id},
    {primary:r.auth_no,detail:r.auth_start+' to '+r.auth_end+'; '+r.auth_visits_authorized+' authorized; patient '+r.auth_patient_id+'; payer '+r.auth_payer_id},
    {primary:'Visit: '+(r.visit_evidence||'Unrecorded'),detail:'Authorization: '+(r.auth_evidence||'Unrecorded')}
   ]);}
   fs.writeFileSync(path.join(out,'visible-records.json'),JSON.stringify(actual,null,2)+'\n');
   return {records:13,cells:104,primary_and_detail_comparisons:208};
  });
  await group('retained-duplicate-source-and-excluded-rows',async()=>{const shown=await ids();assert.equal(shown.filter(x=>x==='DUP-1').length,1);for(const x of ['P3-EVAL','CANCEL','NO-SHOW','NO-AUTH','P1-OUTSIDE'])assert(!shown.includes(x),x);const dup=page.locator('#alloc-rows tbody tr').filter({has:page.locator('td').filter({hasText:'DUP-1'})});assert((await dup.textContent()).includes('schedule.csv:row18'));return {last_duplicate_row:18,excluded:5};});
  await group('complete-totals-and-occurrence-options',async()=>{const count=await page.locator('#alloc-count').textContent();assert(count.includes('13 of 13')&&count.includes('6 used / 7 reserved'));const options=await page.locator('#alloc-auth option').evaluateAll(os=>os.map(o=>({value:o.value,label:o.textContent})));const repeated=options.filter(o=>o.label.includes('AUTH-REPEAT'));assert.equal(repeated.length,2);assert.notEqual(repeated[0].value,repeated[1].value);assert(options.every(o=>!o.label.includes('authorizations.csv:row4')));return {count,authorization_options:options.length-1};});
  await group('allocation-used-filter',async()=>{await clear();await page.locator('#alloc-status').selectOption('used');await assertIds(expected.expected_records.filter(r=>r.allocation==='used').map(r=>r.visit_id));return {rows:6};});
  await group('allocation-reserved-filter',async()=>{await clear();await page.locator('#alloc-status').selectOption('scheduled');await assertIds(expected.expected_records.filter(r=>r.allocation==='scheduled').map(r=>r.visit_id));return {rows:7};});
  await group('exact-separated-authorization-periods',async()=>{await clear();const first=records.find(r=>r.auth_start==='2026-10-01'&&r.auth_no.startsWith('AUTH-REPEAT'));const second=records.find(r=>r.auth_start==='2026-10-16');await page.locator('#alloc-auth').selectOption(authKey(first));await assertIds(['P1-EARLY','DUP-1','P1-NEXT','P1-EXTRA']);await page.locator('#alloc-auth').selectOption(authKey(second));await assertIds(['P1-LATE-DONE','P1-LATE']);return {period_rows:[4,2]};});
  await group('visit-clinic-not-patient-home',async()=>{await clear();await page.locator('#alloc-clinic').selectOption(JSON.stringify('Clinic A.*B'));await assertIds(['P1-EARLY','DUP-1','P1-EXTRA','P1-LATE']);const labels=await page.locator('#alloc-clinic option').allTextContents();assert(!labels.some(x=>x.startsWith('Home ')));return {rows:4};});
  await group('literal-case-insensitive-search',async()=>{await clear();await page.locator('#alloc-search').fill('p1-eArLy');await assertIds(['P1-EARLY']);await page.locator('#alloc-search').fill('A.*B');await assertIds(['P1-EARLY','DUP-1','P1-EXTRA','P1-LATE']);await page.locator('#alloc-search').fill('<img');await assertIds([expected.fixture_text.markup_visit]);return {queries:3};});
  await group('search-does-not-join-fields',async()=>{await clear();await page.locator('#alloc-search').fill('p1 pay1');await assertIds([]);assert((await page.locator('#alloc-rows').textContent()).includes('No allocated visits match'));return {rows:0};});
  await group('four-filter-intersection-and-reset',async()=>{await clear();await page.locator('#alloc-status').selectOption('scheduled');await page.locator('#alloc-auth').selectOption(authKey(records[0]));await page.locator('#alloc-clinic').selectOption(JSON.stringify('Clinic A.*B'));await page.locator('#alloc-search').fill('extra');await assertIds(['P1-EXTRA']);await clear();await assertIds(expected.expected_records.map(r=>r.visit_id));return {intersection:1,reset:13};});
  await group('actual-native-keyboard-select',async()=>{await clear();await page.locator('#alloc-status').focus();await page.keyboard.press('Home');await page.keyboard.press('ArrowDown');await page.keyboard.press('Enter');assert.equal(await page.locator('#alloc-status').inputValue(),'used');await assertIds(expected.expected_records.filter(r=>r.allocation==='used').map(r=>r.visit_id));return {selected:'used',rows:6};});
  await group('filtered-view-downloads-complete-native-csv',async()=>{await clear();await page.locator('#alloc-search').fill('p1-next');await assertIds(['P1-NEXT']);const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('link',{name:'Download all allocated visits CSV',exact:true}).click()]);const file=path.join(out,'actual-all-allocated.csv');await download.saveAs(file);assert.equal(await download.failure(),null);const actual=fs.readFileSync(file),gold=fs.readFileSync(path.join(config.outputs.normal,'allocated_visits.csv'));assert(actual.equals(gold));const info={file:path.basename(file),suggested_filename:download.suggestedFilename(),bytes:actual.length,sha256:sha(actual),visible_rows_at_click:1,complete_rows:13};report.downloads.push(info);return info;});
  await group('filtered-view-opens-complete-printable-digest',async()=>{const [p]=await Promise.all([page.waitForEvent('popup'),page.getByRole('link',{name:'Open complete printable digest',exact:true}).click()]);printPage=p;await wire(p);await p.waitForLoadState('load');const count=await p.locator('#allocated-visits tbody tr').count();assert.equal(count,13);const literal=await p.locator('#allocated-visits').textContent();for(const r of expected.expected_records)assert(literal.includes(r.visit_id),r.visit_id);const pdf=await p.pdf({path:path.join(out,'complete-digest.pdf'),format:'A4',printBackground:true,margin:{top:'12mm',right:'12mm',bottom:'12mm',left:'12mm'}});const info={rows:count,pdf_bytes:pdf.length,pdf_sha256:sha(pdf),url:p.url()};await capture('complete-digest',p);return info;});
  await group('desktop-controls-and-document-bounds',async()=>{await clear();await page.setViewportSize({width:1280,height:900});const metrics=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth,panel:document.querySelector('#allocation-panel').getBoundingClientRect().toJSON(),table:document.querySelector('#alloc-rows .review-table').getBoundingClientRect().toJSON()}));assert(metrics.document<=metrics.viewport+2,JSON.stringify(metrics));await capture('desktop-allocation');return metrics;});
  await group('phone-controls-and-document-bounds',async()=>{await page.setViewportSize({width:390,height:844});await page.locator('#allocation-title').scrollIntoViewIfNeeded();const metrics=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth,controls:[...document.querySelectorAll('#alloc-filters input,#alloc-filters select')].map(e=>({id:e.id,rect:e.getBoundingClientRect().toJSON()})),region:{client:document.querySelector('#alloc-rows .review-table').clientWidth,scroll:document.querySelector('#alloc-rows .review-table').scrollWidth}}));assert(metrics.document<=metrics.viewport+2,JSON.stringify(metrics));for(const c of metrics.controls){assert(c.rect.width>=50);assert(c.rect.left>=-1&&c.rect.right<=metrics.viewport+1,JSON.stringify(c));}assert(metrics.region.scroll>metrics.region.client);await capture('phone-left');return metrics;});
  await group('phone-keyboard-reaches-rightmost-columns',async()=>{const region=page.locator('#alloc-rows .review-table');await region.focus();assert.equal(await region.evaluate(e=>e===document.activeElement),true);const before=await region.evaluate(e=>e.scrollLeft);for(let i=0;i<60;i++)await page.keyboard.press('ArrowRight');await page.waitForFunction(()=>{const e=document.querySelector('#alloc-rows .review-table');return e.scrollLeft>=e.scrollWidth-e.clientWidth-3;});const after=await region.evaluate(e=>({left:e.scrollLeft,max:e.scrollWidth-e.clientWidth}));assert(after.left>before);await capture('phone-right');return {before,...after};});
  await group('phone-keyboard-reaches-complete-download',async()=>{await page.locator('#alloc-search').focus();await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>document.activeElement?.getAttribute('role')),'region');await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>document.activeElement?.textContent),'Download all allocated visits CSV');const [download]=await Promise.all([page.waitForEvent('download'),page.keyboard.press('Enter')]);const file=path.join(out,'keyboard-all-allocated.csv');await download.saveAs(file);assert.equal(await download.failure(),null);const actual=fs.readFileSync(file);assert(actual.equals(fs.readFileSync(path.join(config.outputs.normal,'allocated_visits.csv'))));const info={file:path.basename(file),bytes:actual.length,sha256:sha(actual),keyboard:true};report.downloads.push(info);return info;});
  await group('legacy-native-report-is-unavailable',async()=>{const p=await context.newPage();await wire(p);await p.goto('http://127.0.0.1:'+ports.legacy+'/');await p.getByRole('button',{name:'Auth ledger',exact:true}).click();await p.waitForFunction(()=>document.querySelector('#alloc-note')?.textContent.includes('unavailable'));assert((await p.locator('#alloc-note').textContent()).includes('Allocation details are unavailable'));assert.equal(await p.locator('#alloc-export a').count(),0);for(const s of ['#alloc-status','#alloc-auth','#alloc-clinic','#alloc-search'])assert(await p.locator(s).isDisabled());await capture('legacy-unavailable',p);await p.close();return {disabled_controls:4,no_download:true};});
  await group('valid-empty-native-report-is-empty',async()=>{const p=await context.newPage();await wire(p);await p.goto('http://127.0.0.1:'+ports.empty+'/');await p.getByRole('button',{name:'Auth ledger',exact:true}).click();await p.waitForFunction(()=>document.querySelector('#alloc-count')?.textContent.startsWith('0 of 0'));assert((await p.locator('#alloc-rows').textContent()).includes('No visits were allocated'));assert.equal(await p.locator('#alloc-export a').count(),2);assert(!(await p.locator('#alloc-status').isDisabled()));const [download]=await Promise.all([p.waitForEvent('download'),p.getByRole('link',{name:'Download all allocated visits CSV',exact:true}).click()]);const file=path.join(out,'empty-all-allocated.csv');await download.saveAs(file);assert.equal(await download.failure(),null);const actual=fs.readFileSync(file);assert(actual.equals(fs.readFileSync(path.join(config.outputs.empty,'allocated_visits.csv'))));report.downloads.push({file:path.basename(file),bytes:actual.length,sha256:sha(actual),rows:0});await capture('valid-empty',p);await p.close();return {enabled_controls:4,download_bytes:actual.length};});
  await group('literal-markup-and-offline-read-only-requests',async()=>{for(const p of context.pages())assert.equal(await p.evaluate(()=>window.__allocatedInjected),undefined);assert.equal(report.page_errors.length,0);assert.equal(report.dialogs.length,0);assert.equal(report.external_requests.length,0);assert(report.requests.every(r=>r.method==='GET'));return {page_errors:0,dialogs:0,external_requests:0,all_requests_get:true,request_count:report.requests.length};});
 }catch(e){report.fatal={name:e.name,message:e.message,stack:e.stack};}
 finally{
  if(context)await context.close();
  report.capacity_after={tmp_free:free('/tmp'),shm_free:free('/dev/shm')};
  if(profile){fs.rmSync(profile,{recursive:true,force:false});report.owned_profile_removed=true;}
  report.completed_at=new Date().toISOString();report.pass=report.groups.filter(g=>g.status==='pass').length;report.fail=report.groups.filter(g=>g.status==='fail').length;save();
  console.log(JSON.stringify({pass:report.pass,fail:report.fail,fatal:report.fatal??null,report:reportPath,sha256:sha(fs.readFileSync(reportPath))}));
  process.exitCode=report.fatal||report.fail?1:0;
 }
})().catch(e=>{report.fatal={name:e.name,message:e.message,stack:e.stack};save();console.error(e);process.exitCode=1;});
