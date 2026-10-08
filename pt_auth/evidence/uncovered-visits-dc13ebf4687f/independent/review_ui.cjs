// Historical independent actual-browser/UI receiving. Authored fixture only.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {chromium} = require('/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root = __dirname;
const cfg = JSON.parse(fs.readFileSync(path.join(root, 'browser-input.json')));
const report = JSON.parse(fs.readFileSync(path.join(root, 'report-receipt.json')));
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const servers = [];
const result = {kind:'actual Chromium receiving of exact PT UI + unchanged real App',
  candidate:report.source.candidate, node:process.version,
  playwright:require('/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/package.json').version,
  checks:[], observations:[], blocked:[], page_errors:[], source_before:{}, source_after:{}};
function check(ok, name) { assert.ok(ok, name); result.checks.push(name); }
function same(actual, expected, name) { assert.deepEqual(actual, expected, name); result.checks.push(name); }
function inventory() {
  const out = {};
  for (const [relative, pin] of Object.entries(report.source_after)) {
    const file = path.resolve(cfg.candidate, '..', relative);
    const raw = fs.readFileSync(file);
    assert.equal(sha(raw), pin.sha256, relative);
    out[relative] = {size:raw.length,sha256:sha(raw)};
  }
  return out;
}
async function start(label) {
  const spec = {label, source:label === 'baseline' ? cfg.baseline : cfg.candidate,
    data:label === 'empty' ? cfg.empty_data : cfg.data, output:cfg.outputs[label]};
  const child = spawn('/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3',
    ['-B','-u',path.join(root,'serve_fixture.py'),JSON.stringify(spec)], {stdio:['ignore','pipe','pipe']});
  const record = {label,child,events:[],stderr:''}; servers.push(record);
  const ready = await new Promise((resolve,reject) => {
    let pending = '';
    const timer = setTimeout(() => reject(new Error(label + ' fixture startup timed out')),5000);
    child.stdout.on('data', chunk => {
      pending += chunk.toString();
      while (pending.includes('\n')) {
        const index = pending.indexOf('\n'); const line = pending.slice(0,index); pending = pending.slice(index+1);
        if (!line) continue;
        try { const event = JSON.parse(line); record.events.push(event); if(event.ready){clearTimeout(timer); resolve(event);} }
        catch(error){clearTimeout(timer); reject(error);}
      }
    });
    child.stderr.on('data', chunk => record.stderr += chunk.toString());
    child.once('error', error => {clearTimeout(timer); reject(error);});
    child.once('exit', code => {clearTimeout(timer); if(!record.events.some(x=>x.ready))reject(new Error(label+' exited '+code+': '+record.stderr));});
  });
  Object.assign(record, ready);
  return record;
}
async function stopServers() {
  await Promise.all(servers.map(record => new Promise(resolve => {
    if(record.child.exitCode !== null) return resolve();
    record.child.once('exit',resolve); record.child.kill('SIGTERM');
  })));
  result.servers = servers.map(({child,...record})=>record);
}
function expectedIds(rows = cfg.expected) {return rows.map(row=>row.visit_id);}
async function ids(page) {return page.locator('#uc-rows tbody tr td:first-child > b').allTextContents();}
async function select(page, status='', clinic='', query='') {
  await page.locator('#uc-status').selectOption(status);
  await page.locator('#uc-clinic').selectOption(clinic);
  await page.locator('#uc-search').fill(query);
}
async function download(page) {
  const [item] = await Promise.all([page.waitForEvent('download'), page.locator('#uc-export a').click()]);
  const stream = await item.createReadStream(); const chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  return {name:item.suggestedFilename(), bytes:Buffer.concat(chunks)};
}

async function main() {
  result.program_sha256 = sha(fs.readFileSync(__filename));
  result.server_program_sha256 = sha(fs.readFileSync(path.join(root,'serve_fixture.py')));
  const stat = fs.statfsSync('/dev/shm'); result.free_shm_before = Number(stat.bavail)*Number(stat.bsize);
  check(result.free_shm_before >= 96*1024*1024, 'at least 96 MiB temporary headroom before browser launch');
  result.source_before = inventory();
  const statesBefore = Object.fromEntries(Object.entries(cfg.outputs).map(([label,out])=>[label,sha(fs.readFileSync(path.join(out,'work_state.json')))]));
  const baseline = await start('baseline'); const candidate = await start('candidate');
  const legacy = await start('legacy'); const empty = await start('empty');
  const origins = new Set(servers.map(s=>s.origin));
  for (const server of servers) {
    same(server.web_sha256,'2f7d01cda0bb42e907d135d4a34cedb655b780c646cbe01ed4050ab7c11b2b23',server.label+' actual server uses unchanged web bytes');
    same(server.ui_sha256,server.label==='baseline'?'c94b54f51fbdedc6fe19bb36ac8e74973c834fc5a0ffa6b474d63eb61edc61c4':'fddb0d6e5fe587f961ac602660161728195ff5904966a54577f8d4dcfcd41242',server.label+' actual server selects exact UI bytes');
  }
  let browser;
  try {
    browser = await chromium.launch({executablePath:'/workspace/scratch/ae0a1ea0b247/browser-tools/runtime/chromium',
      headless:true,timeout:10000,args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote']});
    result.browser=browser.version();
    const context = await browser.newContext({viewport:{width:1280,height:900},acceptDownloads:true,reducedMotion:'reduce'});
    await context.route('**/*', route => {
      const request=route.request(), url=new URL(request.url());
      const permitted = origins.has(url.origin) && (request.method()==='GET' ||
        (request.method()==='POST' && url.origin===legacy.origin && url.pathname==='/api/run'
         && request.postData()==='{"as_of":"2026-10-08"}'));
      if(permitted)return route.continue();
      result.blocked.push({url:request.url(),method:request.method()}); return route.abort();
    });
    async function open(server) {
      const page=await context.newPage(); page.setDefaultTimeout(4000);page.setDefaultNavigationTimeout(4000);
      page.on('pageerror', error=>result.page_errors.push(String(error)));
      const response=await page.goto(server.origin+'/',{waitUntil:'load'});
      same(sha(await response.body()),server.ui_sha256,server.label+' HTTP document is pinned UI bytes');
      await page.locator('#cards .card').first().waitFor();
      return page;
    }
    const oldPage=await open(baseline);
    const oldSelectors=['#cards','#work','#t-review','#t-ledger'];
    const oldRendered=Object.fromEntries(await Promise.all(oldSelectors.map(async sel=>[sel,await oldPage.locator(sel).innerHTML()])));
    same(await oldPage.locator('#shown').textContent(),'1 of 2 items','baseline approved staff item stays hidden by default');
    const oldLinks=await oldPage.locator('#t-files a').evaluateAll(nodes=>nodes.map(a=>({href:a.getAttribute('href'),download:a.hasAttribute('download'),target:a.getAttribute('target')})));
    await oldPage.locator('#fs').selectOption('all');
    const oldText=await oldPage.locator('#work').textContent();
    check(!oldText.includes(cfg.u5)&&!oldText.includes(cfg.u6),'baseline actual worklist omits U5/U6 even with all staff states');
    same(await oldPage.locator('[data-t="uncovered"]').count(),0,'baseline has no complete uncovered review tab');
    const oldNarrow=await oldPage.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
    await oldPage.setViewportSize({width:390,height:900});
    result.baseline_layout={wide:oldNarrow,narrow:await oldPage.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}))};

    const page=await open(candidate);
    for(const sel of oldSelectors)same(await page.locator(sel).innerHTML(),oldRendered[sel],'existing actual rendered section unchanged: '+sel);
    same(await page.locator('#shown').textContent(),'1 of 2 items','candidate preserves approved work-item visibility');
    same(await page.locator('#t-files a').evaluateAll(nodes=>nodes.filter(a=>a.getAttribute('href')!='/out/uncovered_visits.csv').map(a=>({href:a.getAttribute('href'),download:a.hasAttribute('download'),target:a.getAttribute('target')}))),oldLinks,'all old export/digest actions retained exactly');
    await page.locator('[data-t="uncovered"]').focus(); await page.keyboard.press('Enter');
    check(await page.locator('#t-uncovered').isVisible(),'native Enter opens new review tab');
    same(await ids(page),expectedIds(),'actual browser renders all nine ordered visits despite approved work item');
    same(await page.locator('#uc-shown').textContent(),'9 of 9 appointments · as of 2026-10-08','complete shown/total count');
    same(await page.locator('[data-pt-canary]').count(),0,'literal HTML creates no canary element');
    const unknown=page.locator('#uc-rows tbody tr').filter({has:page.locator('td:first-child > b',{hasText:'UNKNOWN'})});
    const unknownText=await unknown.textContent();
    check(unknownText.includes('PAY-MISSING')&&unknownText.includes('Rules unavailable')&&unknownText.includes('Name unavailable')&&!unknownText.includes(cfg.payer_name),'unknown actual payer/name remains explicit without primary-payer substitution');
    await select(page,'scheduled');same(await ids(page),expectedIds(cfg.expected.filter(r=>r.status==='scheduled')),'status filter returns seven upcoming scheduled rows');
    await select(page,'completed');same(await ids(page),['D-PAST','D-FUTURE'],'completed filter retains past and recorded future completion');
    await select(page);
    const clinicValues=await page.locator('#uc-clinic option').evaluateAll(options=>options.map(o=>o.value));
    same(clinicValues,['',...[...new Set(cfg.expected.map(r=>r.clinic))].sort().map(x=>JSON.stringify(x))],'actual DOM option values preserve blank, Unicode and newline clinics');
    await select(page,'',JSON.stringify(''));same(await ids(page),['U3'],'blank visit clinic remains separately selectable from all clinics');
    await select(page,'',JSON.stringify(cfg.special_clinic));same(await ids(page),[cfg.u6],'newline-bearing visit clinic selects exact appointment');
    same(await page.locator('#uc-rows tbody tr td').nth(4).textContent(),cfg.special_clinic,'rendered cell text preserves source clinic newline');
    await select(page,'','',cfg.u5.toUpperCase());same(await ids(page),[cfg.u5],'Unicode/HTML visit ID search is literal and case insensitive');
    await select(page,'','', 'ZOË');same(await ids(page),expectedIds(cfg.expected.filter(r=>r.patient_id==='PT-A')),'patient-name search spans all eight appointments');
    await select(page,'','', 'pay-missing');same(await ids(page),['UNKNOWN'],'actual payer ID search finds unknown payer');
    await select(page,'scheduled',JSON.stringify('South'),'pt-a');same(await ids(page),['U2','U4',cfg.u5],'status/clinic/patient filters intersect');
    await select(page,'','', '.*');same(await ids(page),[],'search treats regex punctuation literally');
    check((await page.locator('#uc-rows').textContent()).includes('No appointments match these filters.'),'no-match message differs from empty report');
    await select(page,'','',cfg.therapist);same(await ids(page),[],'search does not silently add undocumented therapist field');
    await select(page,'','', 'pay-missing');
    const exported=await download(page);const expectedCsv=fs.readFileSync(path.join(cfg.outputs.candidate,'uncovered_visits.csv'));
    same(exported.name,'uncovered_visits.csv','native download uses documented CSV filename');
    same(exported.bytes,expectedCsv,'native one-row-filter download remains all-nine-row exact CSV');
    same(await ids(page),['UNKNOWN'],'download preserves active UI filters');
    result.download={name:exported.name,size:exported.bytes.length,sha256:sha(exported.bytes),displayed_rows:1,exported_rows:9};
    await select(page);await page.locator('[data-t="work"]').click();await page.locator('#q').fill('no matching work item');
    same(await page.locator('#shown').textContent(),'0 of 2 items','existing worklist search remains local');
    await page.locator('[data-t="uncovered"]').click();same(await ids(page),expectedIds(),'worklist filters do not truncate independent visit review');
    await page.locator('#uc-status').focus();
    const sequence=[];
    for(const expected of ['uc-clinic','uc-search','region','download']) {
      await page.keyboard.press('Tab');
      const focused=await page.evaluate(()=>{const e=document.activeElement;return {id:e.id,role:e.getAttribute('role'),href:e.getAttribute('href'),visible:e.matches(':focus-visible'),outline:getComputedStyle(e).outlineWidth};});
      sequence.push(focused);
      if(expected==='region')check(focused.role==='region'&&focused.visible&&parseFloat(focused.outline)>0,'keyboard reaches visibly focused scroll region');
      else if(expected==='download')same(focused.href,'/out/uncovered_visits.csv','keyboard reaches native export action');
      else same(focused.id,expected,'keyboard reaches '+expected);
    }
    result.keyboard_sequence=sequence;
    for(const width of [1280,390]) {
      await page.setViewportSize({width,height:900});
      const layout=await page.evaluate(()=>{const r=document.querySelector('#uc-rows .review-table'),b=r.getBoundingClientRect();return {width:innerWidth,documentWidth:document.documentElement.scrollWidth,regionLeft:b.left,regionRight:b.right,regionClientWidth:r.clientWidth,regionScrollWidth:r.scrollWidth};});
      check(layout.regionLeft>=0&&layout.regionRight<=width,'new review scroll container stays in viewport at '+width);
      result.observations.push({layout,rows:await ids(page)});
    }
    await page.locator('#t-uncovered').screenshot({path:path.join(root,'uncovered-review-390.png'),timeout:4000});

    const legacySummaryBefore=sha(fs.readFileSync(path.join(cfg.outputs.legacy,'summary.json')));
    const legacyPage=await open(legacy);await legacyPage.locator('[data-t="uncovered"]').click();
    same(sha(fs.readFileSync(path.join(cfg.outputs.legacy,'summary.json'))),legacySummaryBefore,'matching-zone legacy GET does not silently rerun report');
    check((await legacyPage.locator('#uc-note').textContent()).includes('Run worklist'),'legacy saved report asks for rerun');
    for(const id of ['uc-status','uc-clinic','uc-search'])check(await legacyPage.locator('#'+id).isDisabled(),'legacy disables '+id);
    same(await legacyPage.locator('#uc-shown').textContent(),'','legacy missing array does not claim zero');
    same(await legacyPage.locator('a[href="/out/uncovered_visits.csv"]').count(),0,'legacy hides all new CSV actions');
    await legacyPage.locator('#run').click();await legacyPage.waitForFunction(()=>document.querySelector('#uc-shown').textContent==='9 of 9 appointments · as of 2026-10-08',null,{timeout:4000});
    same(await ids(legacyPage),expectedIds(),'actual existing Run worklist action upgrades legacy report to all nine rows');
    check(await legacyPage.locator('#uc-export a').isVisible(),'successful rerun exposes complete CSV download');
    same(fs.readFileSync(path.join(cfg.outputs.legacy,'uncovered_visits.csv')),expectedCsv,'legacy web rerun produces exact complete CSV');
    same(await legacyPage.locator('#shown').textContent(),'1 of 2 items','legacy rerun preserves approved staff item');
    const emptyPage=await open(empty);await emptyPage.locator('[data-t="uncovered"]').click();
    same(await emptyPage.locator('#uc-shown').textContent(),'0 of 0 appointments · as of 2026-10-08','explicit empty saved array reports zero');
    check((await emptyPage.locator('#uc-rows').textContent()).includes('No appointments are in this review for this report.'),'empty report uses clear empty message');
    check(await emptyPage.locator('#uc-export a').isVisible(),'empty report offers its valid header-only CSV');
    check(!(await emptyPage.locator('#uc-status').isDisabled()),'empty report remains distinct from legacy unavailable controls');
    for(const [label,out] of Object.entries(cfg.outputs))same(sha(fs.readFileSync(path.join(out,'work_state.json'))),statesBefore[label],label+' staff state bytes remain unchanged through UI workflow');
    same(result.blocked,[],'zero external or forbidden operational attempts');
    same(result.page_errors,[],'zero actual browser script errors');
    result.accepted=true;
  } catch(error) {
    result.accepted=false;result.error=String(error.stack||error);process.exitCode=1;
  } finally {
    if(browser)await browser.close();
    await stopServers();
  }
  same(result.servers.flatMap(s=>s.events.filter(x=>x.request==='POST').map(x=>({label:s.label,path:x.path}))),[{label:'legacy',path:'/api/run'}],'one authored legacy rerun; zero state/generator actions');
  result.source_after=inventory();same(result.source_after,result.source_before,'all tracked candidate source bytes remain unchanged');
}
main().catch(async error=>{result.accepted=false;result.error=String(error.stack||error);process.exitCode=1;await stopServers();}).finally(()=>{
  fs.writeFileSync(path.join(root,'ui-receipt.json'),JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify({accepted:result.accepted,checks:result.checks.length,browser:result.browser,error:result.error,receipt:path.join(root,'ui-receipt.json')}));
});
