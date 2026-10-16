/* Bounded receiver mechanism check on existing controls and unmodified candidate layout. */
"use strict";
const fs=require("node:fs"),path=require("node:path"),{spawn}=require("node:child_process"),crypto=require("node:crypto");
const assert=require("node:assert/strict");
const puppeteer=require("/Users/me/.npm/_npx/4b4c857f6efdfb61/node_modules/puppeteer/lib/puppeteer/puppeteer.js");
const ROOT=__dirname,out=path.join(ROOT,"control-layout-diagnostic");
fs.mkdirSync(out);const free=fs.statfsSync("/tmp");assert(free.bavail*free.bsize>=256*1024*1024);
const sleep=ms=>new Promise(r=>setTimeout(r,ms)),sha=b=>crypto.createHash("sha256").update(b).digest("hex");
const traces=[],blocked=[],errors=[],servers=[];let browser;
async function serve(name,source,native){
 const dir=path.join(out,name+"-server");
 const args=[path.join(ROOT,"pt_browser_server.py"),"--source",path.join(ROOT,source),"--native",path.join(ROOT,native),"--out",dir];
 const child=spawn("/usr/local/bin/python3",args,{env:{...process.env,PYTHONDONTWRITEBYTECODE:"1"},stdio:["ignore","pipe","pipe"]});
 child.stdout.pipe(fs.createWriteStream(path.join(out,name+".server.stdout")));child.stderr.pipe(fs.createWriteStream(path.join(out,name+".server.stderr")));
 const exited=new Promise(resolve=>child.once("exit",(code,signal)=>resolve({code,signal})));servers.push({name,child,exited,args});
 const ready=path.join(dir,"server-ready.json");for(let i=0;i<200&&!fs.existsSync(ready);i++)await sleep(50);
 assert(fs.existsSync(ready));return JSON.parse(fs.readFileSync(ready,"utf8")).origins.modern;
}
async function keys(p,selector,sequence){
 await p.focus(selector);const steps=[];
 for(const step of sequence){
   if(step==="click"){await p.click(selector);}
   else if(step==="triple-click"){await p.click(selector,{clickCount:3});}
   else if(Array.isArray(step)){
     await p.keyboard.down(step[0]);await p.keyboard.press(step[1]);await p.keyboard.up(step[0]);
   }else await p.keyboard.press(step);
   await sleep(60);
   steps.push({step,state:await p.$eval(selector,e=>({id:e.id,value:e.value,index:e.selectedIndex,selectionStart:e.selectionStart,
                     selectionEnd:e.selectionEnd,active:document.activeElement.id}))});
 }
 return steps;
}
(async()=>{
 try{
  const baseline=await serve("baseline","baseline","before-native"),candidate=await serve("candidate","candidate","candidate-native");
  browser=await puppeteer.launch({executablePath:"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",headless:true,
   userDataDir:path.join(out,"chrome-profile"),args:["--disable-background-networking","--disable-sync","--disable-component-update","--disable-default-apps","--no-first-run"]});
  const p=await browser.newPage();await p.setRequestInterception(true);
  p.on("request",r=>{const u=new URL(r.url());if(u.protocol==="http:"&&u.hostname==="127.0.0.1")r.continue();else{blocked.push({url:r.url(),sha256:sha(Buffer.from(r.url()))});r.abort("blockedbyclient");}});
  p.on("pageerror",e=>errors.push(e.message));
  async function open(origin,tab){
   await p.goto(origin+"/",{waitUntil:"domcontentloaded"});await p.waitForFunction(()=>document.querySelector("#cards").children.length>0);
   await p.click('button[data-t="'+tab+'"]');
   await p.evaluate(()=>{window.__receiverKeyEvents=[];for(const name of ["keydown","keyup","input","change"])document.addEventListener(name,e=>{
      if(["uc-status","uc-search","alloc-status","alloc-search"].includes(e.target.id))window.__receiverKeyEvents.push({
        event:name,id:e.target.id,key:e.key,code:e.code,ctrl:e.ctrlKey,meta:e.metaKey,shift:e.shiftKey,value:e.target.value,
        selectionStart:e.target.selectionStart,selectionEnd:e.target.selectionEnd});
   },true);});
  }
  const selectCases=[
   ["original",["Home","ArrowDown","Enter"]],
   ["space_down",["Space","ArrowDown","Enter"]],
   ["click_down",["click","ArrowDown","Enter"]],
   ["type_character",["c","Enter"]],
   ["alt_open",[["Alt","ArrowDown"],"ArrowDown","Enter"]],
   ["focus_down_only",["ArrowDown","ArrowDown","Tab"]]
  ];
  for(const [name,seq] of selectCases){
   await open(baseline,"uncovered");const steps=await keys(p,"#uc-status",seq);
   traces.push({surface:"baseline existing recorded-status select",name,steps,events:await p.evaluate(()=>window.__receiverKeyEvents)});
  }
  for(const [name,seq] of [
   ["meta_a",[["Meta","A"],"Backspace"]],
   ["control_a",[["Control","A"],"Backspace"]],
   ["triple_click",["triple-click","Backspace"]],
   ["shift_left",...[]]
  ].filter(x=>x[0]!=="shift_left")){
   await open(baseline,"uncovered");await p.focus("#uc-search");await p.keyboard.type("alpha");
   const steps=await keys(p,"#uc-search",seq);
   traces.push({surface:"baseline existing literal-search input",name,steps,events:await p.evaluate(()=>window.__receiverKeyEvents)});
  }
  await open(candidate,"ledger");await p.setViewport({width:390,height:844});
  await p.$eval("#allocation-panel",e=>e.scrollIntoView({block:"start"}));
  const layout=await p.evaluate(()=>{
   const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,scrollWidth:e.scrollWidth,clientWidth:e.clientWidth,
     overflowX:getComputedStyle(e).overflowX,overflowWrap:getComputedStyle(e).overflowWrap,fontSize:getComputedStyle(e).fontSize,tabIndex:e.tabIndex};};
   const table=document.querySelector("#alloc-rows table");
   return {viewport:{width:innerWidth,height:innerHeight},page:{scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth},
     panel:rect(document.querySelector("#allocation-panel")),region:rect(table.parentElement),table:rect(table),
     firstRows:[...table.querySelectorAll("tbody tr")].slice(0,3).map(e=>({visit:e.dataset.visitId,...rect(e),cells:[...e.cells].map(c=>({...rect(c),text:c.innerText}))}))};
  });
  await p.screenshot({path:path.join(out,"narrow-candidate-viewport.png"),fullPage:false});
  fs.writeFileSync(path.join(out,"layout.json"),JSON.stringify(layout,null,2)+"\n");
  traces.push({surface:"unchanged candidate narrow allocation layout",layout});
  console.log(JSON.stringify({select_results:traces.filter(x=>x.surface.includes("select")).map(x=>({name:x.name,last:x.steps.at(-1).state})),
    input_results:traces.filter(x=>x.surface.includes("input")).map(x=>({name:x.name,last:x.steps.at(-1).state})),
    narrow:{region:layout.region,table:layout.table,rowHeights:layout.firstRows.map(r=>r.height)}}));
 }catch(e){errors.push(e.stack);console.error(e.stack);}
 finally{
  if(browser)await browser.close();
  for(const s of servers){s.child.kill("SIGTERM");s.result=await s.exited;}
  const receipt={traces,blocked,errors,servers:servers.map(({name,args,result})=>({name,args,result})),probe_sha256:sha(fs.readFileSync(__filename))};
  fs.writeFileSync(path.join(out,"receipt.json"),JSON.stringify(receipt,null,2)+"\n");
  process.exitCode=errors.length?1:0;
 }
})();
