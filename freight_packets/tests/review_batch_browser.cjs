/* Optional native browser receiver; no dependencies are installed by this script. */
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const os = require("node:os");
const assert = require("node:assert/strict");
const {spawn, spawnSync} = require("node:child_process");
const puppeteer = require(process.env.PUPPETEER_MODULE || "puppeteer");
const source = path.resolve(process.env.FREIGHT_BATCH_SOURCE || path.join(__dirname, "../.."));
const evidence = path.resolve(process.env.FREIGHT_BATCH_EVIDENCE || fs.mkdtempSync(path.join(os.tmpdir(), "freight-batch-browser-")));
fs.mkdirSync(evidence, {recursive:true});
const downloads = path.join(evidence, "downloads");
fs.mkdirSync(downloads, {recursive:true});
const python = process.env.PYTHON || "python3";
const sha = bytes => crypto.createHash("sha256").update(bytes).digest("hex");
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const until = async (check, label) => {
  for (let i=0; i<200; i++) { if (await check()) return; await wait(50); }
  throw Error("Timed out: " + label);
};
const serverCode = [
  "import json,sys",
  "from pathlib import Path",
  "from http.server import ThreadingHTTPServer",
  "sys.path.insert(0,str(Path(sys.argv[1])/'freight_packets'))",
  "from freightpkt.synth import generate",
  "from freightpkt.pipeline import run",
  "from freightpkt.web import App,make_handler",
  "r=Path(sys.argv[2]); data=r/'data'; out=r/'out'",
  "generate(data,n_loads=8,seed=7)",
  "run(data,out,run_by='batch-browser-fixture')",
  "app=App(data,out); summary=app.summary()",
  "server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(app))",
  "print(json.dumps({'port':server.server_port,'packets':summary['packets']}),flush=True)",
  "server.serve_forever()",
].join("\n");
const processLog = fs.openSync(path.join(evidence, "server-stderr.log"), "w");
const server = spawn(python, ["-B","-u","-c",serverCode,source,evidence],
  {env:{...process.env,PYTHONDONTWRITEBYTECODE:"1"},stdio:["ignore","pipe",processLog]});
let serverText = "";
server.stdout.on("data", chunk => serverText += chunk);
const groups=[], pageErrors=[], refused=[], responsePins=[], completed=[], beginnings=[];
let browser, page, cdp, origin, heldRequest=null, holdBatch=false;
const bodies = path.join(evidence, "response-bodies");
fs.mkdirSync(bodies,{recursive:true});
const pending = [];
const group = async (name, action) => {
  try { const detail = await action(); groups.push({name,ok:true,detail}); }
  catch (error) { groups.push({name,ok:false,error:String(error.stack||error)}); throw error; }
};
const get = async suffix => {
  const response = await fetch(origin+suffix);
  assert.equal(response.status,200);
  return response;
};
const snapshot = async () => (await get("/api/summary")).json();
const clickTab = name => page.click('button[data-t="'+name+'"]');
const boxes = "#freight-batch-panel input[data-batch-load]";
const batchButton = "#freight-batch-panel [data-batch-download]";
const count = async () => page.$eval("[data-batch-count]",el=>el.textContent);
const choose = async ids => {
  await clickTab("files");
  await page.click("[data-batch-clear]");
  for (const id of ids) await page.click(boxes+'[data-batch-load="'+id+'"]');
};
const waitDownload = async (before, button) => {
  await page.click(button);
  await until(()=>completed.length>before,"native download completion");
  const event=completed.at(-1);
  const begin=beginnings.find(x=>x.guid===event.guid);
  assert.ok(begin);
  const file=path.join(downloads,begin.suggestedFilename);
  await until(()=>fs.existsSync(file),"download file");
  return {file,filename:begin.suggestedFilename,bytes:fs.statSync(file).size,sha256:sha(fs.readFileSync(file))};
};
(async () => {
  try {
    await until(()=>serverText.includes("\n"),"fixture server");
    const ready=JSON.parse(serverText.split("\n")[0]);
    origin="http://127.0.0.1:"+ready.port;
    const ids=ready.packets.slice(0,3).map(x=>x.load_id);
    assert.equal(ids.length,3);
    const profile=path.join(evidence,"browser-profile");
    browser=await puppeteer.launch({executablePath:process.env.BROWSER_BIN,headless:true,userDataDir:profile,
      args:["--no-first-run","--no-default-browser-check","--disable-background-networking","--disable-sync","--disk-cache-size=1048576"]});
    page=await browser.newPage();
    await page.setViewport({width:1280,height:900,deviceScaleFactor:1});
    await page.setCacheEnabled(false);
    await page.setRequestInterception(true);
    page.on("request", request => {
      const url=request.url();
      if (!url.startsWith(origin+"/")) {refused.push({url,method:request.method()});request.abort().catch(()=>{});return;}
      if (holdBatch && new URL(url).pathname==="/api/review-batch") {heldRequest=request;return;}
      request.continue().catch(()=>{});
    });
    page.on("pageerror",error=>pageErrors.push(String(error)));
    page.on("response",response=>{
      const task=(async()=>{
        try {
          const bytes=await response.buffer(), pathname=new URL(response.url()).pathname;
          const digest=sha(bytes), blobPath=path.join(bodies,digest);
          if (!fs.existsSync(blobPath)) fs.writeFileSync(blobPath,bytes);
          const pin={path:pathname,status:response.status(),bytes:bytes.length,sha256:digest};
          if (pathname==="/" && response.status()===200) assert.equal(digest,sha(fs.readFileSync(path.join(source,"freight_packets/freightpkt/ui.html"))));
          if (pathname==="/batch-handoff-ui.js" && response.status()===200) assert.equal(digest,sha(fs.readFileSync(path.join(source,"freight_packets/freightpkt/batch_handoff_ui.js"))));
          responsePins.push(pin);
        } catch(error) {responsePins.push({path:response.url(),body_error:String(error)});}
      })();
      pending.push(task);
    });
    cdp=await browser.target().createCDPSession();
    await cdp.send("Browser.setDownloadBehavior",{behavior:"allow",downloadPath:downloads,eventsEnabled:true});
    cdp.on("Browser.downloadWillBegin",event=>beginnings.push(event));
    cdp.on("Browser.downloadProgress",event=>{if(event.state==="completed")completed.push(event);});

    await group("native source and controls",async()=>{
      await page.goto(origin,{waitUntil:"networkidle0"});
      await clickTab("files");
      await page.waitForSelector("#freight-batch-panel");
      assert.equal(await count(),"0 selected");
      assert.equal(await page.$eval(batchButton,el=>el.disabled),true);
      return {packet_count:ready.packets.length,browser:await browser.version()};
    });

    await group("selected batch and original ZIP preservation",async()=>{
      await choose(ids.slice(0,2));
      const summary=await snapshot();
      const originalPaths=[];
      for (let i=0;i<2;i++) {
        const query=new URLSearchParams({load_id:ids[i],evidence_version:summary.evidence_versions[ids[i]],review_version:summary.review_versions[ids[i]]});
        const bytes=Buffer.from(await (await get("/api/review-bundle?"+query)).arrayBuffer());
        const destination=path.join(evidence,"single-reference-"+i+".zip");
        fs.writeFileSync(destination,bytes);originalPaths.push(destination);
      }
      const download=await waitDownload(completed.length,batchButton);
      const checkCode=[
        "import json,sys,zipfile,hashlib",
        "from pathlib import Path",
        "z=zipfile.ZipFile(sys.argv[1]); m=json.loads(z.read('manifest.json'))",
        "expected=json.loads(sys.argv[2]); originals=json.loads(sys.argv[3])",
        "assert [r['load_id'] for r in m['loads']]==expected",
        "for row,original in zip(m['loads'],originals):",
        " assert z.read(row['bundle_path'])==Path(original).read_bytes()",
        " with zipfile.ZipFile(original) as single:",
        "  for name in single.namelist(): assert z.read(row['index_path'].replace('index.html',name))==single.read(name)",
        "for row in m['files']:",
        " b=z.read(row['path']); assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256']",
        "print(json.dumps({'loads':expected,'member_count':len(z.namelist()),'exact_original_zips':len(originals)}))",
      ].join("\n");
      const check=spawnSync(python,["-B","-c",checkCode,download.file,JSON.stringify(ids.slice(0,2)),JSON.stringify(originalPaths)],{encoding:"utf8"});
      assert.equal(check.status,0,check.stderr);
      await page.screenshot({path:path.join(evidence,"desktop-downloads.png"),fullPage:true});
      return {download,readback:JSON.parse(check.stdout)};
    });

    await group("all, clear and keyboard selection",async()=>{
      await page.click("[data-batch-all]");
      assert.equal(await count(),ready.packets.length+" selected");
      await page.focus(boxes);
      await page.keyboard.press("Space");
      assert.equal(await count(),(ready.packets.length-1)+" selected");
      await page.click("[data-batch-clear]");
      assert.equal(await count(),"0 selected");
      return {all_count:ready.packets.length,keyboard:"Space"};
    });

    await group("unsaved note blocks batch and can be restored",async()=>{
      await choose(ids.slice(0,2));
      await clickTab("packets");
      await page.click('tr[data-l="'+ids[0]+'"]');
      const saved=await page.$eval("#note",el=>el.value);
      await page.click("#note");await page.type("#note","unsaved fixture text");
      await clickTab("files");
      assert.equal(await page.$eval(batchButton,el=>el.disabled),true);
      await clickTab("packets");
      await page.click("#note",{clickCount:3});await page.keyboard.press("Backspace");
      const afterTripleClick = await page.$eval("#note",el=>el.value);
      // Select the current textarea value; the real Backspace emits the input event.
      await page.$eval("#note",el=>{el.focus();el.select();});
      await page.keyboard.press("Backspace");
      if(saved)await page.type("#note",saved);
      assert.equal(await page.$eval("#note",el=>el.value),saved,JSON.stringify({saved_note:saved,after_triple_click:afterTripleClick}));
      await clickTab("files");
      const restored = await page.evaluate(() => ({note:document.querySelector("#note").value,
        count:document.querySelector("[data-batch-count]").textContent,
        status:document.querySelector("[data-batch-status]").textContent,
        run_disabled:document.querySelector("#run").disabled,gen_disabled:document.querySelector("#gen").disabled,
        batch_disabled:document.querySelector("[data-batch-download]").disabled}));
      assert.equal(restored.batch_disabled,false,JSON.stringify({saved_note:saved,after_triple_click:afterTripleClick,restored}));
      return {selection_retained:await count(),after_triple_click:afterTripleClick,saved_note:saved,restored};
    });

    await group("cancel pending download retains selection",async()=>{
      const before=completed.length;
      holdBatch=true;heldRequest=null;
      await page.click(batchButton);
      await until(()=>heldRequest!==null,"held native request");
      await page.click("[data-batch-cancel]");
      holdBatch=false;await heldRequest.continue().catch(()=>{});heldRequest=null;
      await wait(350);
      assert.equal(completed.length,before);
      assert.equal(await count(),"2 selected");
      return {completed_downloads:completed.length};
    });

    await group("review updates preserve or clear exact selection",async()=>{
      await clickTab("packets");
      await page.click('tr[data-l="'+ids[2]+'"]');
      await page.type("#note","unselected local fixture review");
      await page.click('button[data-d="adjust"]');
      await until(async()=>!(await page.$eval('button[data-d="adjust"]',el=>el.disabled)),"review finished");
      await clickTab("files");
      assert.equal(await count(),"2 selected");
      await clickTab("packets");
      await page.click('tr[data-l="'+ids[0]+'"]');
      await page.type("#note","selected local fixture review");
      await page.click('button[data-d="adjust"]');
      await until(async()=>!(await page.$eval('button[data-d="adjust"]',el=>el.disabled)),"selected review finished");
      await clickTab("files");
      assert.equal(await count(),"0 selected");
      return {unselected_update_retained:true,selected_update_cleared:true};
    });

    await group("stale server evidence refuses the complete download",async()=>{
      await choose(ids.slice(0,2));
      const packet=ready.packets.find(x=>x.load_id===ids[1]);
      const target=path.join(evidence,"out",packet.file), original=fs.readFileSync(target);
      const before=completed.length;
      try {
        fs.writeFileSync(target,Buffer.concat([original,Buffer.from("\n<!-- authored stale fixture -->")]));
        await page.click(batchButton);
        await until(async()=>await page.$eval("[data-batch-status]",el=>el.textContent.includes("No batch was downloaded")),"stale refusal");
        assert.equal(completed.length,before);
        assert.equal(await count(),"2 selected");
      } finally {fs.writeFileSync(target,original);}
      return {download_count_unchanged:true,selection_retained:true};
    });

    await group("narrow selection and existing per-load download",async()=>{
      await page.setViewport({width:390,height:844,deviceScaleFactor:1});
      await page.$eval("#freight-batch-panel",el=>el.scrollIntoView());
      const layout=await page.$eval("#freight-batch-panel",el=>{
        const r=el.getBoundingClientRect();
        return {left:r.left,right:r.right,width:innerWidth,buttons:[...el.querySelectorAll("button:not([hidden])")].map(x=>x.getBoundingClientRect().height)};
      });
      assert.ok(layout.left>=0 && layout.right<=layout.width,JSON.stringify(layout));
      assert.ok(layout.buttons.every(height=>height>=44),JSON.stringify(layout));
      await page.screenshot({path:path.join(evidence,"narrow-downloads.png"),fullPage:true});
      await clickTab("packets");
      await page.click('tr[data-l="'+ids[0]+'"]');
      const original=await waitDownload(completed.length,"#download-review-bundle");
      return {layout,existing_single_load_download:original};
    });

    await group("receiving network and source identity",async()=>{
      await Promise.all(pending);
      assert.deepEqual(refused,[]);
      assert.deepEqual(pageErrors,[]);
      assert.ok(responsePins.some(x=>x.path==="/batch-handoff-ui.js" && x.status===200));
      assert.ok(responsePins.filter(x=>x.path==="/"||x.path==="/batch-handoff-ui.js").every(x=>!x.body_error));
      return {responses:responsePins.length,external_requests:refused.length,page_errors:pageErrors.length};
    });
  } catch(error) {
    if(!groups.some(x=>!x.ok))groups.push({name:"setup",ok:false,error:String(error.stack||error)});
    process.exitCode=1;
  } finally {
    if(browser)await browser.close();
    server.kill("SIGTERM");
    await wait(100);
    fs.closeSync(processLog);
    await Promise.allSettled(pending);
    const receipt={schema:"freight-batch-browser.v1",source,evidence,node:process.version,
      groups,refused,pageErrors,downloads:beginnings,completed,responsePins};
    fs.writeFileSync(path.join(evidence,"receipt.json"),JSON.stringify(receipt,null,2)+"\n");
    fs.writeFileSync(path.join(evidence,"server-stdout.log"),serverText);
    fs.rmSync(path.join(evidence,"browser-profile"),{recursive:true,force:true});
    console.log(JSON.stringify({passed:groups.filter(x=>x.ok).length,failed:groups.filter(x=>!x.ok).length,receipt:path.join(evidence,"receipt.json")}));
  }
})();
