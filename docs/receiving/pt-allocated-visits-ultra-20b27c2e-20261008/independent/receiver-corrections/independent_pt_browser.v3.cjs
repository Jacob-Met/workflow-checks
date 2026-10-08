/* Independent public-control receiver; uses only synthetic loopback fixtures. */
"use strict";
const fs=require("node:fs"),path=require("node:path"),crypto=require("node:crypto");
const assert=require("node:assert/strict"),{spawn}=require("node:child_process");
const puppeteer=require("/Users/me/.npm/_npx/4b4c857f6efdfb61/node_modules/puppeteer/lib/puppeteer/puppeteer.js");
const ROOT=__dirname,oracle=JSON.parse(fs.readFileSync(path.join(ROOT,"oracle.json"),"utf8"));
const args=process.argv.slice(2),source=path.resolve(args[0]),native=path.resolve(args[1]),out=path.resolve(args[2]);
const sha=b=>crypto.createHash("sha256").update(b).digest("hex");
const write=(file,obj)=>fs.writeFileSync(file,JSON.stringify(obj,null,2)+"\n");
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const norm=s=>String(s).replace(/\s+/g," ").trim();
const ids=rows=>rows.map(r=>r.visit_id).sort();
const occurrence=r=>JSON.stringify([r.auth_no,r.auth_patient_id,r.auth_payer_id,r.auth_start,r.auth_end,r.auth_visits_authorized,r.auth_evidence]);
const groups=(rows,key)=>{const m=new Map();for(const r of rows){const k=key(r);if(!m.has(k))m.set(k,[]);m.get(k).push(r);}return m;};
const expectedGroups=groups(oracle.rows,occurrence),clinicGroups=groups(oracle.rows,r=>r.clinic);
fs.mkdirSync(out,{recursive:false});fs.mkdirSync(path.join(out,"downloads"));
const stat=fs.statfsSync("/tmp"),free=stat.bavail*stat.bsize;
assert(free>=256*1024*1024,"Receiver capacity floor 256 MiB unmet before browser launch");
const events=[],requests=[],responses=[],pageErrors=[],blocked=[],dialogs=[],downloads=[],exec=[];
let browser,child,page,origins,serverExit,cdp;
async function group(name,fn){
  try{const detail=await fn();events.push({name,outcome:"passed",detail:detail??null});console.log("PASS "+name);}
  catch(e){events.push({name,outcome:e instanceof assert.AssertionError?"failed":"error",message:String(e.message),stack:e.stack});
    console.log((e instanceof assert.AssertionError?"FAIL ":"ERROR ")+name+": "+e.message);}
}
const attached=new WeakSet();
async function attach(p){
  if(attached.has(p))return;attached.add(p);
  await p.setRequestInterception(true);
  p.on("request",r=>{
    const u=new URL(r.url());requests.push({url:r.url(),method:r.method(),resource_type:r.resourceType()});
    if((u.protocol==="http:"||u.protocol==="https:")&&["127.0.0.1","localhost","[::1]"].includes(u.hostname))r.continue();
    else{blocked.push({url:r.url(),method:r.method()});r.abort("blockedbyclient");}
  });
  p.on("response",async r=>{
    if(new URL(r.url()).pathname==="/"||new URL(r.url()).pathname==="/calendar_ui.js"){
      try{const b=await r.buffer();responses.push({url:r.url(),status:r.status(),bytes:b.length,sha256:sha(b)});}
      catch(e){responses.push({url:r.url(),status:r.status(),body_error:e.message});}
    }
  });
  p.on("pageerror",e=>pageErrors.push({url:p.url(),message:e.message}));
  p.on("dialog",async d=>{dialogs.push({type:d.type(),message:d.message()});await d.dismiss();});
}
async function open(variant="modern"){
  await page.goto(origins[variant]+"/",{waitUntil:"domcontentloaded",timeout:15000});
  await page.waitForFunction(()=>document.querySelector("#cards")?.children.length>0,{timeout:10000});
  await page.click('button[data-t="ledger"]');
}
async function panel(){
  assert.equal(await page.$eval("#t-ledger",e=>e.innerText.includes("Allocated visits")),true,"Auth ledger lacks the Allocated visits panel");
  for(const sel of ["#alloc-status","#alloc-auth","#alloc-clinic","#alloc-search","#alloc-count","#alloc-rows","#alloc-export"])
    assert(await page.$(sel),"Public allocation control missing: "+sel);
}
async function rows(){
  return await page.$$eval("#alloc-rows tr[data-visit-id]",els=>els.map(e=>({visit_id:e.dataset.visitId,authorization:e.dataset.authorization,text:e.innerText})));
}
async function checkRows(expected){
  const actual=await rows();assert.deepEqual(ids(actual),ids(expected));
  const count=await page.$eval("#alloc-count",e=>e.innerText),numbers=count.match(/\d+/g)?.map(Number)||[];
  assert.equal(numbers[0],expected.length,"Visible filtered count differs from actual rows");
  assert.equal(numbers[1],oracle.rows.length,"Visible complete count is missing or changed");
  for(const r of actual){const target=expected.find(x=>x.visit_id===r.visit_id);
    for(const field of ["auth_no","auth_evidence","visit_evidence","visit_date","patient_id","payer_id"])
      assert(norm(r.text).includes(norm(target[field])),r.visit_id+" omits "+field);}
  return actual;
}
async function options(sel){
  return await page.$$eval(sel+" option",els=>els.map(e=>({value:e.value,text:e.textContent})));
}
async function keyboardSelect(sel,value){
  const opts=await options(sel),index=opts.findIndex(o=>o.value===value);
  assert(index>=0,"Requested option absent");
  await page.focus(sel);await page.keyboard.press("Home");
  for(let i=0;i<index;i++)await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  assert.equal(await page.$eval(sel,e=>e.value),value,"Native select keyboard action did not choose requested option");
}
async function query(value){
  await page.focus("#alloc-search");await page.keyboard.down("Meta");await page.keyboard.press("A");await page.keyboard.up("Meta");
  await page.keyboard.press("Backspace");
  if(value)await page.keyboard.type(value);
  assert.equal(await page.$eval("#alloc-search",e=>e.value),value,"Search input differs from entered literal query");
}
async function clear(){
  await page.select("#alloc-status","");await page.select("#alloc-auth","");await page.select("#alloc-clinic","");await query("");
}
async function download(selector,expected){
  const n=downloads.length;await page.click(selector);
  const deadline=Date.now()+15000;
  while(Date.now()<deadline){
    const found=downloads.slice(n).find(d=>d.state==="completed");
    if(found){
      const p=path.join(out,"downloads",found.suggestedFilename),b=fs.readFileSync(p);
      assert.equal(sha(b),sha(expected));found.bytes=b.length;found.sha256=sha(b);found.local_path=p;return found;
    }
    await sleep(50);
  }
  assert.fail("Actual browser download did not complete");
}
(async()=>{
  try{
    const serverDir=path.join(out,"server");
    const argv=[path.join(ROOT,"pt_browser_server.py"),"--source",source,"--native",native,"--out",serverDir];
    child=spawn("/usr/local/bin/python3",argv,{env:{...process.env,PYTHONDONTWRITEBYTECODE:"1"},stdio:["ignore","pipe","pipe"]});
    exec.push({command:"/usr/local/bin/python3",argv});
    const stdout=fs.createWriteStream(path.join(out,"server.stdout")),stderr=fs.createWriteStream(path.join(out,"server.stderr"));
    child.stdout.pipe(stdout);child.stderr.pipe(stderr);
    const exited=new Promise(resolve=>child.once("exit",(code,signal)=>{serverExit={code,signal};resolve(serverExit);}));
    const readyPath=path.join(serverDir,"server-ready.json"),deadline=Date.now()+15000;
    while(!fs.existsSync(readyPath)&&Date.now()<deadline&&!serverExit)await sleep(50);
    assert(fs.existsSync(readyPath),"Native make_handler server did not become ready");
    origins=JSON.parse(fs.readFileSync(readyPath,"utf8")).origins;
    browser=await puppeteer.launch({executablePath:"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
      headless:true,userDataDir:path.join(out,"chrome-profile"),
      args:["--disable-background-networking","--disable-sync","--disable-component-update","--disable-default-apps",
            "--no-first-run","--no-default-browser-check","--disable-features=MediaRouter"]});
    page=await browser.newPage();await attach(page);await page.setViewport({width:1280,height:860});
    cdp=await browser.target().createCDPSession();
    await cdp.send("Browser.setDownloadBehavior",{behavior:"allow",downloadPath:path.join(out,"downloads"),eventsEnabled:true});
    cdp.on("Browser.downloadWillBegin",e=>downloads.push({...e,state:"inProgress"}));
    cdp.on("Browser.downloadProgress",e=>{const d=downloads.find(x=>x.guid===e.guid);if(d)Object.assign(d,e);});
    write(path.join(out,"runtime.json"),{node:process.version,chrome:await browser.version(),free_bytes_before:free,source,native,origins,
      probe_sha256:sha(fs.readFileSync(__filename)),oracle_sha256:sha(fs.readFileSync(path.join(ROOT,"oracle.json")))});

    await group("01_existing_worklist_ledger_review_calendar_and_download",async()=>{
      await open();
      const oldLedgerCount=await page.$eval("#t-ledger table",table=>table.rows.length-1);
      assert.equal(oldLedgerCount,oracle.ledger_count);
      for(const tab of ["work","uncovered","review","files"]){
        await page.click('button[data-t="'+tab+'"]');assert.equal(await page.$eval("#t-"+tab,e=>getComputedStyle(e).display!=="none"),true);
      }
      await page.click('button[data-t="work"]');
      assert(await page.$("#calendar [data-calendar-download]"),"Existing calendar panel disappeared");
      await page.click('button[data-t="files"]');
      const d=await download('#t-files a[href="/out/ledger.csv"]',fs.readFileSync(path.join(native,"mixed","ledger.csv")));
      return {ledger_rows:oldLedgerCount,old_download_sha256:d.sha256};
    });
    await group("02_full_panel_identity_and_provenance",async()=>{
      await open();await panel();const actual=await checkRows(oracle.rows);
      assert(actual.every(r=>typeof r.authorization==="string"&&r.authorization.length),"Rows omit an exact authorization identity");
      assert.equal(await page.evaluate(()=>window.__alloc_xss??null),null);
      assert.equal(await page.$$eval("#alloc-rows img,#alloc-rows svg,#alloc-rows script,#alloc-rows iframe",es=>es.length),0);
      await page.screenshot({path:path.join(out,"desktop.png"),fullPage:true});
      return {rows:actual.length,authorization_occurrences:new Set(actual.map(r=>r.authorization)).size};
    });
    await group("03_keyboard_used_bucket_preserves_future_completed",async()=>{
      await open();await panel();await keyboardSelect("#alloc-status","used");
      const expected=oracle.rows.filter(r=>r.allocation==="used");await checkRows(expected);
      assert(expected.some(r=>r.visit_id==="A-CFUTURE"&&r.visit_date>oracle.as_of));
      return {rows:expected.length};
    });
    await group("04_keyboard_scheduled_bucket_preserves_past_reservation",async()=>{
      await open();await panel();await keyboardSelect("#alloc-status","scheduled");
      const expected=oracle.rows.filter(r=>r.allocation==="scheduled");await checkRows(expected);
      assert(expected.some(r=>r.visit_id==="A-S0"&&r.visit_date<oracle.as_of));
      return {rows:expected.length};
    });
    const authOptions=new Map(),clinicOptions=new Map();
    await group("05_every_exact_authorization_occurrence",async()=>{
      await open();await panel();const opts=(await options("#alloc-auth")).filter(o=>o.value!=="");
      assert.equal(opts.length,expectedGroups.size);assert.equal(new Set(opts.map(o=>o.value)).size,opts.length);
      const seen=new Set();
      for(let i=0;i<opts.length;i++){
        if(i===0)await keyboardSelect("#alloc-auth",opts[i].value);else await page.select("#alloc-auth",opts[i].value);
        const actual=await rows();assert(actual.length>0);
        const reference=oracle.rows.find(r=>r.visit_id===actual[0].visit_id);assert(reference);
        const key=occurrence(reference);assert(!seen.has(key),"Two options target the same authorization occurrence");
        seen.add(key);await checkRows(expectedGroups.get(key));
        assert(actual.every(r=>r.authorization===opts[i].value),"Displayed row identity differs from selected occurrence");
        authOptions.set(key,opts[i].value);
      }
      assert.equal(seen.size,expectedGroups.size);return {options:opts.length,groups:seen.size};
    });
    await group("06_every_visit_clinic_including_blank_and_multiline",async()=>{
      await open();await panel();const opts=(await options("#alloc-clinic")).filter(o=>o.value!=="");
      assert.equal(opts.length,clinicGroups.size);const seen=new Set();
      for(let i=0;i<opts.length;i++){
        if(i===0)await keyboardSelect("#alloc-clinic",opts[i].value);else await page.select("#alloc-clinic",opts[i].value);
        const actual=await rows();assert(actual.length>0);
        const reference=oracle.rows.find(r=>r.visit_id===actual[0].visit_id);assert(reference);
        const key=reference.clinic;assert(!seen.has(key));seen.add(key);
        await checkRows(clinicGroups.get(key));clinicOptions.set(key,opts[i].value);
        if(key==="")assert(actual.every(r=>!r.text.includes("Home fallback must not replace raw clinic")));
      }
      assert(seen.has(""));assert(seen.has('West "A",\n第二诊所 [x]'));
      return {options:opts.length,groups:seen.size};
    });
    await group("07_compound_filters_and_complete_clear",async()=>{
      await open();await panel();
      const target=oracle.rows.find(r=>r.visit_id==="AM-SCHED"),key=occurrence(target);
      assert(authOptions.has(key)&&clinicOptions.has("South"),"Earlier occurrence/clinic qualification did not supply controls");
      await page.select("#alloc-auth",authOptions.get(key));await page.select("#alloc-clinic",clinicOptions.get("South"));
      await keyboardSelect("#alloc-status","scheduled");
      const expected=oracle.rows.filter(r=>occurrence(r)===key&&r.clinic==="South"&&r.allocation==="scheduled");
      await checkRows(expected);await clear();await checkRows(oracle.rows);
      return {restricted:expected.length,restored:oracle.rows.length};
    });
    await group("08_literal_per_field_keyboard_search",async()=>{
      await open();await panel();
      const cases=[".*[x]","[","<img src=x","KAI.*[X]","authorizations.csv:row3","p-a twin name","second line","America/Los_Angeles"];
      const result=[];
      for(const q of cases){
        await query(q);const expected=oracle.rows.filter(r=>oracle.fields.some(f=>String(r[f]).toLowerCase().includes(q.toLowerCase())));
        await checkRows(expected);result.push({query:q,matches:expected.length});
      }
      assert.equal(result.find(r=>r.query==="p-a twin name").matches,0,"Cross-field witness unexpectedly matches a single field");
      await query("");await checkRows(oracle.rows);return result;
    });
    await group("09_no_match_is_distinct_and_restores",async()=>{
      await open();await panel();await query("definitely no such synthetic visit");
      await checkRows([]);const message=await page.$eval("#alloc-rows",e=>e.innerText);
      assert.match(message,/no .*match|no match/i);await query("");await checkRows(oracle.rows);
      return {no_match_message:message};
    });
    await group("10_restricted_filter_real_csv_and_full_digest",async()=>{
      await open();await panel();await query("AM-SCHED");await checkRows(oracle.rows.filter(r=>r.visit_id==="AM-SCHED"));
      const d=await download('#alloc-export a[href="/out/allocated_visits.csv"]',fs.readFileSync(path.join(native,"mixed","allocated_visits.csv")));
      const href=await page.$eval('#alloc-export a[href="/out/digest.html"]',e=>e.href);
      const p=await browser.newPage();await attach(p);
      await p.goto(href,{waitUntil:"domcontentloaded"});
      const body=await p.$eval("body",e=>e.innerText);
      for(const r of oracle.rows){assert(norm(body).includes(norm(r.visit_id)),r.visit_id);assert(norm(body).includes(norm(r.auth_evidence)));}
      assert.equal(await p.evaluate(()=>window.__alloc_xss??null),null);
      assert.equal(await p.$$eval("img,svg,script,iframe",es=>es.length),0);
      const digestResponse=await p.evaluate(async()=>{const r=await fetch(location.href);return {status:r.status,text:await r.text()};});
      assert.equal(digestResponse.status,200);
      assert.equal(sha(Buffer.from(digestResponse.text)),sha(fs.readFileSync(path.join(native,"mixed","digest.html"))));
      await p.close();return {csv_sha256:d.sha256,digest_sha256:sha(Buffer.from(digestResponse.text)),complete_rows:oracle.rows.length};
    });
    await group("11_narrow_controls_and_native_horizontal_scroll",async()=>{
      await page.setViewport({width:390,height:844});await open();await panel();
      for(const sel of ["#alloc-status","#alloc-auth","#alloc-clinic","#alloc-search"]){
        const rect=await page.$eval(sel,e=>{const r=e.getBoundingClientRect();return {width:r.width,height:r.height,visible:getComputedStyle(e).display!=="none"};});
        assert(rect.visible&&rect.width>30&&rect.height>15,sel+" is not a usable visible control");
      }
      const handle=await page.evaluateHandle(()=>{
        let e=document.querySelector("#alloc-rows table")?.parentElement;
        while(e&&e.id!=="t-ledger"){if(["auto","scroll"].includes(getComputedStyle(e).overflowX)&&e.scrollWidth>e.clientWidth)return e;e=e.parentElement;}
        return null;
      });
      const region=handle.asElement();assert(region,"Narrow allocation table lacks a horizontal scrolling region");
      const before=await region.evaluate(e=>({scrollLeft:e.scrollLeft,scrollWidth:e.scrollWidth,clientWidth:e.clientWidth,tabIndex:e.tabIndex}));
      assert(before.tabIndex>=0,"Scrolling allocation region is not keyboard focusable");
      await region.focus();for(let i=0;i<8;i++)await page.keyboard.press("ArrowRight");await sleep(180);
      const after=await region.evaluate(e=>e.scrollLeft);assert(after>before.scrollLeft,"Keyboard did not move the horizontal scroll position");
      await page.screenshot({path:path.join(out,"narrow.png"),fullPage:true});
      await page.setViewport({width:1280,height:860});return {before,scrollLeft_after:after};
    });
    for(const variant of ["missing","nonlist"]){
      await group("12_legacy_"+variant+"_unavailable_without_recalculation",async()=>{
        await page.setViewport({width:1280,height:860});await open(variant);
        const text=await page.$eval("#t-ledger",e=>e.innerText);
        assert(text.includes("Allocated visits"));assert.match(text,/run worklist|unavailable|not available/i);
        assert.equal((await rows()).length,0);
        assert.equal(await page.$$eval('#alloc-export a[href="/out/allocated_visits.csv"]',e=>e.length),0);
        for(const tab of ["work","uncovered","review","files"]){await page.click('button[data-t="'+tab+'"]');assert(await page.$("#t-"+tab));}
        const stored=JSON.parse(fs.readFileSync(path.join(serverDir,variant,"summary.json"),"utf8"));
        const fetched=await page.evaluate(async()=>{const r=await fetch("/api/summary");return r.json();});
        if(variant==="missing")assert.equal(Object.hasOwn(fetched,"allocation_review"),false);
        else assert.deepEqual(fetched.allocation_review,stored.allocation_review);
        return {unavailable_visible:true,stored_shape:variant};
      });
    }
    await group("13_actual_empty_report_has_completed_empty_state_and_csv",async()=>{
      await open("empty");await panel();assert.equal((await rows()).length,0);
      const text=await page.$eval("#t-ledger",e=>e.innerText);
      assert.match(text,/no (?:allocated )?visits|no .*allocat|0 (?:visits|allocations)/i);
      assert.doesNotMatch(text,/run worklist to build.*allocat|allocation.*unavailable/i);
      const d=await download('#alloc-export a[href="/out/allocated_visits.csv"]',fs.readFileSync(path.join(native,"empty","allocated_visits.csv")));
      return {empty_csv_sha256:d.sha256};
    });
    await group("14_no_script_side_effect_or_mutating_request",async()=>{
      assert(blocked.every(r=>r.method==="GET"&&sha(Buffer.from(r.url))==="04e449d20d0365d881a54ed24af7ed00fe79dd9f9e601248f4fd7793003924f2"),"Unrecognized blocked resource or non-loopback network request");assert.deepEqual(dialogs,[]);assert.deepEqual(pageErrors,[]);
      assert(requests.length>0);assert(requests.every(r=>r.method==="GET"),"Read-only receiver sent a mutating request");
      assert(requests.every(r=>!new URL(r.url).pathname.startsWith("/api/calendar")));
      const sourceUI=sha(fs.readFileSync(path.join(source,"pt_auth/ptauth/ui.html")));
      const sourceCalendar=sha(fs.readFileSync(path.join(source,"pt_auth/ptauth/calendar_ui.js")));
      assert(responses.some(r=>new URL(r.url).pathname==="/"&&r.sha256===sourceUI));
      assert(responses.some(r=>new URL(r.url).pathname==="/calendar_ui.js"&&r.sha256===sourceCalendar));
      return {requests:requests.length,served_source_bodies:responses.length};
    });
    await browser.close();browser=null;child.kill("SIGTERM");await exited;child=null;
    const receipt=JSON.parse(fs.readFileSync(path.join(serverDir,"server-receipt.json"),"utf8"));
    await group("15_native_receiver_source_inputs_staff_and_audit_custody",async()=>{
      assert.equal(serverExit.code,0);assert.equal(receipt.stopped_cleanly,true);
      assert.equal(receipt.source_unchanged,true);assert.equal(receipt.fixture_unchanged,true);
      assert.equal(receipt.all_reports_unchanged,true);
      assert(receipt.records.every(r=>r.method==="GET"));
      return {responses:receipt.records.length,variants:Object.keys(receipt.variants),all_reports_unchanged:true};
    });
  }catch(e){
    events.push({name:"receiver_setup_or_fatal",outcome:"error",message:e.message,stack:e.stack});console.error(e.stack);
  }finally{
    if(browser)try{await browser.close();}catch(e){events.push({name:"browser_close",outcome:"error",message:e.message});}
    if(child){child.kill("SIGTERM");await new Promise(resolve=>child.once("exit",resolve));}
    write(path.join(out,"result.json"),{events,groups:events.length,passed:events.filter(e=>e.outcome==="passed").length,
      failures:events.filter(e=>e.outcome==="failed").length,errors:events.filter(e=>e.outcome==="error").length,
      requests,responses,pageErrors,blocked,dialogs,downloads,exec,serverExit,
      probe_sha256:sha(fs.readFileSync(__filename)),oracle_sha256:sha(fs.readFileSync(path.join(ROOT,"oracle.json")))});
    process.exitCode=events.some(e=>e.outcome!=="passed")?1:0;
  }
})();
