import { createServer } from "node:http";
import { readFile, writeFile, mkdir, rm, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createHash } from "node:crypto";
import assert from "node:assert/strict";
const ROOT=path.dirname(fileURLToPath(import.meta.url));
const [SITE,OUT,PINS,EXECUTABLE]=process.argv.slice(2);
if(!SITE||!OUT||!PINS||!EXECUTABLE)throw new Error("Pass installed site, new owned output, frozen pins and Chromium executable.");
await mkdir(OUT,{recursive:false});
const temporary=path.join(OUT,"temporary");await mkdir(temporary);
process.env.TMPDIR=temporary;
const modulePath="/Users/me/workspace/estate/production-evidence-49f845d0dece/browser-tools/node_modules/playwright/index.mjs";
const {chromium}=await import(pathToFileURL(modulePath).href);
const pins=JSON.parse(await readFile(PINS,"utf8"));
const oracle=JSON.parse(await readFile(path.join(ROOT,"independent-oracle.json"),"utf8"));
const cases=new Map(oracle.cases.map(c=>[c.id,c]));
const sha=b=>createHash("sha256").update(b).digest("hex");
const files=["index.html","styles.css","app.mjs","model.mjs","data.mjs"];
const sourceHashes=async()=>Object.fromEntries(await Promise.all(files.map(async n=>[n,sha(await readFile(path.join(SITE,n)))])));
assert.deepStrictEqual(await sourceHashes(),pins);
const checks=[],pageErrors=[],consoleErrors=[],external=[],requests=new Set(),servedHashes={};
let browser,server,origin,port;
let browserVersion,initialRecord;
const screenshots=[];
const filter=process.env.FREIGHT_REVIEW_FILTER?.split("|");
async function check(name,fn){if(filter&&!filter.includes(name))return;try{await fn();checks.push({name,passed:true});}catch(e){checks.push({name,passed:false,error:e.stack||String(e),actual:e.actual,expected:e.expected});}}
async function screenshot(page,name,selector=null){
 const output=path.join(OUT,name+".png");
 if(selector)await page.locator(selector).screenshot({path:output});else await page.screenshot({path:output,fullPage:false});
 screenshots.push({name:path.basename(output),sha256:sha(await readFile(output))});
}
async function makePage(viewport,{isMobile=false,timezoneId="America/Los_Angeles"}={}){
 const context=await browser.newContext({viewport,isMobile,hasTouch:isMobile,timezoneId,locale:"en-US",acceptDownloads:true});
 await context.route("**/*",route=>{
  const u=route.request().url();
  if(u.startsWith(origin+"/")||u.startsWith("blob:"+origin))return route.continue();
  external.push(u);return route.abort();
 });
 const page=await context.newPage();
 page.on("pageerror",e=>pageErrors.push(e.message));
 page.on("console",m=>{if(m.type()==="error")consoleErrors.push(m.text());});
 await page.goto(origin+"/",{waitUntil:"networkidle"});
 await page.locator("#result-content").waitFor({state:"visible"});
 return {context,page};
}
const money=c=>(c<0?"-":"")+"$"+Math.floor(Math.abs(c)/100).toLocaleString("en-US")+"."+String(Math.abs(c)%100).padStart(2,"0");
const defaultScenario={
 appointment:"2026-09-07T09:00",arrival:"2026-09-07T08:45",departure:"2026-09-07T12:45",free_minutes:120,
 increment_minutes:15,late_grace_minutes:15,detention_rate_cents:7500,detention_cap_cents:30000,
 linehaul_cents:145000,fuel_cents:24500,detention_cents:15000,lumper_cents:15000,tonu_cents:0,
 invoice_total_cents:null,pod_received:true,ratecon_complete:true};
async function apply(page,s){
 const details=page.locator("details.terms");
 if(!(await details.getAttribute("open"))&&!(await details.evaluate(e=>e.open)))await details.locator("summary").click();
 for(const [field,value] of Object.entries(s)){
  const control=page.locator("#"+field);
  if(typeof value==="boolean")await control.setChecked(value);
  else await control.fill(value===null?"":field.endsWith("_cents")?(value/100).toFixed(2):String(value));
 }
 assert.equal(await page.locator("#invalid-state").isVisible(),false);
 assert.equal(await page.locator("#download").isDisabled(),false);
}
async function record(page,name){
 const event=page.waitForEvent("download");
 await page.locator("#download").click();
 const download=await event;
 const target=path.join(OUT,name+".json");
 await download.saveAs(target);
 assert.equal(await download.failure(),null);
 const r=JSON.parse(await readFile(target,"utf8"));
 assert.equal(r.schema,"workflow-checks.freight-whatif.v1");assert.equal(r.synthetic,true);
 assert.equal(r.provenance.baseline_commit,"2f1e5f777197eedd69d51a4d81c0da744b65ad88");
 assert.deepStrictEqual(r.provenance.source_sha256,oracle.core_sha256);
 assert(Number.isFinite(Date.parse(r.exported_at)));
 return r;
}
function compare(before,after){
 const old=new Set(before.flags.map(f=>f.code)),now=new Set(after.flags.map(f=>f.code));
 return {status_before:before.stop.status,status_after:after.stop.status,
 supported_detention_delta_cents:after.stop.amount_cents-before.stop.amount_cents,
 billable_minutes_delta:after.stop.billable_minutes-before.stop.billable_minutes,
 invoice_total_delta_cents:after.totals.invoice_total_cents-before.totals.invoice_total_cents,
 added_flags:[...now].filter(x=>!old.has(x)),removed_flags:[...old].filter(x=>!now.has(x))};
}
async function assertCase(page,c,{exportName=null}={}){
 await apply(page,c.scenario);
 const expected=c.expected;
 assert.equal((await page.locator("#supported-amount").innerText()).trim(),
  expected.stop.status==="exception"?"No automatic claim":money(expected.stop.amount_cents));
 assert.deepStrictEqual(await page.locator("#findings [data-code]").evaluateAll(es=>es.map(e=>e.dataset.code)),expected.flags.map(f=>f.code));
 const actualDetails=await page.locator("#findings .finding>p").allTextContents();
 assert.deepStrictEqual(actualDetails,expected.flags.map(f=>f.detail));
 assert.equal((await page.locator("#invoice-total").innerText()).trim(),"Invoice "+money(expected.totals.invoice_total_cents));
 if(exportName){
  const r=await record(page,exportName);
  assert.deepStrictEqual(r.current.scenario,c.scenario);
  assert.deepStrictEqual(r.current.result,expected);
  if(initialRecord)assert.deepStrictEqual(r.baseline,initialRecord.baseline);
  assert.deepStrictEqual(r.comparison,compare(r.baseline.result,expected));
  assert.equal(r.loaded_preset.id,"long-dwell");
 }
}
async function layout(page,name){
 const geometry=await page.evaluate(()=>{
  const rect=r=>({left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height});
  const card=document.querySelector(".decision-card"),container=card.getBoundingClientRect();
  const textRects=id=>{const e=document.getElementById(id),range=document.createRange();range.selectNodeContents(e);
   return [...range.getClientRects()].filter(r=>r.width>0&&r.height>0).map(rect);};
  const amount=textRects("supported-amount"),billed=textRects("billed-amount");
  const overlaps=amount.some(a=>billed.some(b=>Math.min(a.right,b.right)>Math.max(a.left,b.left)+1&&Math.min(a.bottom,b.bottom)>Math.max(a.top,b.top)+1));
  const clipped=[...amount,...billed].filter(r=>r.left<container.left-1||r.right>container.right+1||r.top<container.top-1||r.bottom>container.bottom+1);
  const controls=[...document.querySelectorAll("input,button,summary")].filter(e=>e.getClientRects().length).map(e=>({id:e.id||e.textContent.trim().slice(0,40),...rect(e.getBoundingClientRect())}));
  return {viewport:innerWidth,document:document.documentElement.scrollWidth,card:rect(container),amount,billed,overlaps,clipped,
   controlsOutsideViewport:controls.filter(r=>r.left< -1||r.right>innerWidth+1)};
 });
 await writeFile(path.join(OUT,name+"-geometry.json"),JSON.stringify(geometry,null,2)+"\n");
 await screenshot(page,name,".decision-card");
 assert(geometry.document<=geometry.viewport+1,"Document horizontal overflow: "+JSON.stringify(geometry));
 assert.equal(geometry.controlsOutsideViewport.length,0,"Controls outside viewport: "+JSON.stringify(geometry));
 assert.equal(geometry.clipped.length,0,"Decision text clipped: "+JSON.stringify(geometry));
 assert.equal(geometry.overlaps,false,"Decision amount text overlaps: "+JSON.stringify(geometry));
}
try{
 server=createServer(async(req,res)=>{
  const pathname=new URL(req.url,"http://127.0.0.1").pathname;requests.add(pathname);
  if(pathname==="/favicon.ico"){res.writeHead(204);return res.end();}
  const file=pathname==="/"?"index.html":pathname.slice(1);
  if(!files.includes(file)){res.writeHead(404);return res.end("Not found");}
  try{const b=await readFile(path.join(SITE,file));servedHashes[file]=sha(b);
   res.writeHead(200,{"Content-Type":file.endsWith(".html")?"text/html; charset=utf-8":file.endsWith(".css")?"text/css; charset=utf-8":"text/javascript; charset=utf-8","Cache-Control":"no-store"});res.end(b);
  }catch(e){res.writeHead(500);res.end("Read failure");}
 });
 await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));port=server.address().port;origin="http://127.0.0.1:"+port;
 browser=await chromium.launch({executablePath:EXECUTABLE,headless:true,downloadsPath:temporary});
 browserVersion=browser.version();
 const desktop=await makePage({width:1440,height:1000});
 const page=desktop.page;
 await check("desktop-original-record-and-source-custody",async()=>{
  assert.match(await page.locator("body").innerText(),/Synthetic scenario/);
  assert.equal(await page.locator("#supported-amount").innerText(),"$131.25");
  assert.equal(await page.locator("#billed-amount").innerText(),"$150.00");
  assert.equal(await page.locator("#finding-count").innerText(),"1");
  initialRecord=await record(page,"desktop-original-record");
  assert.deepStrictEqual(initialRecord.current.scenario,defaultScenario);
  assert.deepStrictEqual(initialRecord.baseline,initialRecord.current);
  assert.equal(initialRecord.current.result.stop.billable_minutes,105);
  assert.equal(initialRecord.current.result.stop.dwell_minutes,240);
  assert.equal(initialRecord.current.result.stop.status,"detention");
  assert.equal(initialRecord.current.result.totals.invoice_total_cents,199500);
  assert.deepStrictEqual(initialRecord.current.result.flags.map(f=>f.code),["DETENTION_UNSUPPORTED"]);
  await screenshot(page,"desktop-original");
 });
 for(const id of ["early-exit-before-appointment","capped-then-parse-warning","all-findings-with-underbilled-base-lines","maximum-independent-lines-automatic-sum","latest-entry-inclusive","half-cent-rounds-up-2point5"]){
  await check("desktop-oracle-"+id,async()=>{
   await page.locator('[data-preset="long-dwell"]').click();
   await assertCase(page,cases.get(id),{exportName:"desktop-"+id});
   if(id==="capped-then-parse-warning"){
    assert.match(await page.locator("#decision-explanation").innerText(),/Missing or ambiguous evidence/);
    assert.match(await page.locator("#calculation").innerText(),/No automatic claim/);
    assert.match(await page.locator(".scope-inline").innerText(),/does not approve payment/);
   }
   if(id==="all-findings-with-underbilled-base-lines"){
    assert.equal(await page.locator('[data-code="LINEHAUL_MISMATCH"] .finding-variance').innerText(),"-$0.01");
    assert.equal(await page.locator('[data-code="FUEL_MISMATCH"] .finding-variance').innerText(),"-$0.01");
   }
  });
 }
 await check("invalid-hidden-term-pauses-export-and-focus-recovers",async()=>{
  await page.locator('[data-preset="long-dwell"]').click();
  const details=page.locator("details.terms");if(!(await details.evaluate(e=>e.open)))await details.locator("summary").click();
  await page.locator("#increment_minutes").fill("0");
  assert.equal(await page.locator("#result-content").isVisible(),false);
  assert.equal(await page.locator("#download").isDisabled(),true);
  assert.equal(await page.locator("#increment_minutes").getAttribute("aria-invalid"),"true");
  assert.equal(await page.locator("#increment_minutes").getAttribute("aria-describedby"),"increment_minutes-error");
  await details.locator("summary").click();
  await page.locator("#focus-error").click();
  assert.equal(await details.evaluate(e=>e.open),true);
  assert.equal(await page.evaluate(()=>document.activeElement.id),"increment_minutes");
  await page.locator("#increment_minutes").fill("17");
  assert.equal(await page.locator("#invalid-state").isVisible(),false);
  assert.equal(await page.locator("#download").isDisabled(),false);
  await page.locator("#linehaul_cents").fill("1e3");
  assert.equal(await page.locator("#download").isDisabled(),true);
  await page.locator("#reset").click();
  assert.equal(await page.locator("#linehaul_cents").inputValue(),"1450.00");
  assert.equal(await page.locator("#supported-amount").innerText(),"$131.25");
 });
 await check("keyboard-case-change-and-refresh-custody",async()=>{
  const k=await makePage({width:1440,height:1000});
  await k.page.keyboard.press("Tab");assert.equal(await k.page.evaluate(()=>document.activeElement.className),"skip-link");
  await k.page.keyboard.press("Enter");assert.equal(await k.page.evaluate(()=>document.activeElement.id),"results-heading");
  const within=k.page.locator('[data-preset="within-free"]');await within.focus();await k.page.keyboard.press("Space");
  assert.equal(await within.getAttribute("aria-pressed"),"true");
  assert.match(await k.page.locator("#baseline-label").innerText(),/Within free time/);
  await k.page.locator("#linehaul_cents").fill("1449.99");
  assert.equal(await k.page.locator("#finding-count").innerText(),"1");
  await k.page.reload({waitUntil:"networkidle"});
  assert.equal(await k.page.locator("#supported-amount").innerText(),"$131.25");
  assert.equal(await k.page.locator('[data-preset="long-dwell"]').getAttribute("aria-pressed"),"true");
  await k.context.close();
 });
 await desktop.context.close();
 for(const width of [390,320]){
  const mobile=await makePage({width,height:844},{isMobile:true,timezoneId:"Pacific/Auckland"});
  for(const id of ["maximum-independent-lines-automatic-sum","exit-24h-inclusive","capped-then-parse-warning"]){
   await check("mobile-"+width+"-"+id,async()=>{
    await assertCase(mobile.page,cases.get(id));
    await layout(mobile.page,"mobile-"+width+"-"+id);
   });
  }
  await mobile.context.close();
 }
 await check("no-runtime-errors-or-external-data-requests",async()=>{
  assert.deepStrictEqual(pageErrors,[]);assert.deepStrictEqual(consoleErrors,[]);assert.deepStrictEqual(external,[]);
  assert.deepStrictEqual(servedHashes,pins);assert.deepStrictEqual(await sourceHashes(),pins);
 });
}catch(e){checks.push({name:"receiver-setup-or-unhandled-failure",passed:false,error:e.stack||String(e)});}
finally{
 if(browser)await browser.close();
 if(server)await new Promise(resolve=>server.close(resolve));
 await rm(temporary,{recursive:true,force:true});
}
let portClosed=true;
if(origin){try{await fetch(origin+"/",{signal:AbortSignal.timeout(1000)});portClosed=false;}catch{}}
const receipt={schema:"freight-whatif.independent-browser-receipt.v1",node:process.version,browser_version:browserVersion,
 module_sha256:sha(await readFile(modulePath)),executable_sha256:sha(await readFile(EXECUTABLE)),
 runner_sha256:sha(await readFile(fileURLToPath(import.meta.url))),oracle_sha256:sha(await readFile(path.join(ROOT,"independent-oracle.json"))),
 site_root:SITE,site_sha256:await sourceHashes(),served_sha256:servedHashes,origin,
 checks,passed:checks.filter(c=>c.passed).length,failed:checks.filter(c=>!c.passed).length,
 page_errors:pageErrors,console_errors:consoleErrors,external_requests:external,requested_paths:[...requests].sort(),screenshots,
 cleanup:{browser_disconnected:!browser||!browser.isConnected(),server_closed:!server||!server.listening,loopback_port_closed:portClosed,owned_temporary_profile_root_removed:await stat(temporary).then(()=>false,()=>true)},
 limits:"Actual headless Chromium desktop and emulated mobile receiving of the installed static artifact; no physical-device, live-provider, legal, payment or real-world outcome claim."};
const receiptPath=path.join(OUT,"browser-receipt.json");await writeFile(receiptPath,JSON.stringify(receipt,null,2)+"\n");
console.log(JSON.stringify({passed:receipt.passed,failed:receipt.failed,failures:checks.filter(x=>!x.passed).map(x=>({name:x.name,error:x.error})),
 receipt:receiptPath,receipt_sha256:sha(await readFile(receiptPath)),cleanup:receipt.cleanup}));
if(receipt.failed||!portClosed)process.exitCode=1;
