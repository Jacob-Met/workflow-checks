// Independent exact-inline-script review with explicit authored DOM boundaries.
// Real guarded App HTTP, generated authored reports, no browser/layout claim.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const crypto=require('node:crypto'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const root=__dirname,cfg=JSON.parse(fs.readFileSync(path.join(root,'browser-input.json')));
const report=JSON.parse(fs.readFileSync(path.join(root,'report-receipt.json')));
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const result={kind:'exact inline UI + real local App; authored DOM seam, not browser receiving',
  candidate:report.source.candidate,node:process.version,checks:[],servers:[],blocked:[],alerts:[],filter_observations:[]};
const servers=[];
function same(a,b,label){assert.deepEqual(a,b,label);result.checks.push(label);}
function check(a,label){assert.ok(a,label);result.checks.push(label);}
const decode=s=>s.replace(/&(amp|lt|gt|quot|#39|#x27|nbsp|middot);/g,(_,key)=>({amp:'&',lt:'<',gt:'>',quot:'"','#39':"'",'#x27':"'",nbsp:'\u00a0',middot:'·'}[key]));
function attr(text,name){const m=text.match(new RegExp('(?:^|\\s)'+name+'="([^"]*)"'));return m?decode(m[1]):null;}
class Element {
  constructor(tag,attrs,body=''){
    this.tag=tag;this.id=attr(attrs,'id')||'';this.dataset={};this.disabled=false;
    const tab=attr(attrs,'data-t');if(tab!==null)this.dataset.t=tab;
    const key=attr(attrs,'data-k');if(key!==null)this.dataset.k=key;
    this.classes=new Set((attr(attrs,'class')||'').split(/\s+/).filter(Boolean));
    this.classList={toggle:(key,on)=>{if(on)this.classes.add(key);else this.classes.delete(key);},contains:key=>this.classes.has(key)};
    this._value=attr(attrs,'value')||'';this.innerHTML=body;
  }
  set innerHTML(value){
    this._html=String(value);this._text=null;
    if(this.tag==='select'){
      this.options=[...this._html.matchAll(/<option\b([^>]*)>([\s\S]*?)<\/option>/g)].map(m=>({
        value:attr(m[1],'value')??decode(m[2]),label:decode(m[2]),selected:/\bselected\b/.test(m[1])}));
      this._value=(this.options.find(x=>x.selected)||this.options[0]||{value:''}).value;
    }
  }
  get innerHTML(){return this._html;}
  set textContent(value){this._text=String(value);this._html='';}
  get textContent(){return this._text??decode(this._html.replace(/<[^>]*>/g,''));}
  set value(value){this._value=String(value);}
  get value(){return this._value;}
}
function documentFor(html){
  const elements=new Map();
  for(const match of html.matchAll(/<(input|select|div|p|span|button|section)\b([^>]*\bid="[^"]+"[^>]*)>/g)){
    const [whole,tag,attributes]=match;const id=attr(attributes,'id');let body='';
    if(tag==='select'){const end=html.indexOf('</select>',match.index+whole.length);body=html.slice(match.index+whole.length,end);}
    if(elements.has(id))throw new Error('duplicate source ID '+id);
    elements.set(id,new Element(tag,attributes,body));
  }
  const tabs=[...html.matchAll(/<button\b([^>]*\bdata-t="[^"]+"[^>]*)>/g)].map(m=>new Element('button',m[1]));
  const sections=[...elements.values()].filter(e=>e.tag==='section');
  return {elements,tabs,sections,
    querySelector(selector){if(!/^#[\w-]+$/.test(selector))throw new Error('unsupported authored DOM selector '+selector);return elements.get(selector.slice(1))||null;},
    querySelectorAll(selector){
      if(selector==='#tabs button')return tabs;
      if(selector==='main > section')return sections;
      if(selector==='#work select[data-k]')return [...elements.get('work').innerHTML.matchAll(/<select\b([^>]*\bdata-k="[^"]+"[^>]*)>([\s\S]*?)<\/select>/g)].map(m=>new Element('select',m[1],m[2]));
      throw new Error('unsupported authored DOM collection '+selector);
    }};
}
async function start(label){
  const spec={label,source:label==='baseline'?cfg.baseline:cfg.candidate,data:label==='empty'?cfg.empty_data:cfg.data,output:cfg.outputs[label]};
  const child=spawn('/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3',
    ['-B','-u',path.join(root,'serve_fixture.py'),JSON.stringify(spec)],{stdio:['ignore','pipe','pipe']});
  const record={label,child,events:[],stderr:''};servers.push(record);
  const ready=await new Promise((resolve,reject)=>{
    let pending='';const timer=setTimeout(()=>reject(new Error(label+' startup timeout')),5000);
    child.stdout.on('data',chunk=>{pending+=chunk.toString();while(pending.includes('\n')){
      const n=pending.indexOf('\n'),line=pending.slice(0,n);pending=pending.slice(n+1);if(!line)continue;
      try{const event=JSON.parse(line);record.events.push(event);if(event.ready){clearTimeout(timer);resolve(event);}}
      catch(error){clearTimeout(timer);reject(error);}
    }});
    child.stderr.on('data',chunk=>record.stderr+=chunk.toString());
    child.once('error',error=>{clearTimeout(timer);reject(error);});
    child.once('exit',code=>{clearTimeout(timer);if(!record.events.some(x=>x.ready))reject(new Error(label+' exited '+code+': '+record.stderr));});
  });
  Object.assign(record,ready);return record;
}
async function stop(){
  await Promise.all(servers.map(record=>new Promise(resolve=>{if(record.child.exitCode!==null)return resolve();record.child.once('exit',resolve);record.child.kill('SIGTERM');})));
  result.servers=servers.map(({child,...record})=>record);
}
async function open(server){
  const response=await fetch(server.origin+'/');const raw=Buffer.from(await response.arrayBuffer());
  same(sha(raw),server.ui_sha256,server.label+' actual HTTP selects pinned UI bytes');
  same(server.ui_sha256,server.label==='baseline'?'c94b54f51fbdedc6fe19bb36ac8e74973c834fc5a0ffa6b474d63eb61edc61c4':'fddb0d6e5fe587f961ac602660161728195ff5904966a54577f8d4dcfcd41242',server.label+' accepted UI pin');
  same(server.web_sha256,'2f7d01cda0bb42e907d135d4a34cedb655b780c646cbe01ed4050ab7c11b2b23',server.label+' unchanged real web.py pin');
  const html=raw.toString('utf8'),scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];same(scripts.length,1,server.label+' exact one inline program');
  const document=documentFor(html);
  const guardedFetch=async(relative,options={})=>{
    const method=options.method||'GET';const allowed=(method==='GET'&&relative==='/api/summary')||
      (method==='POST'&&server.label==='legacy'&&relative==='/api/run'&&options.body==='{"as_of":"2026-10-08"}');
    if(!allowed){result.blocked.push({label:server.label,relative,method});throw new Error('authored request guard');}
    return fetch(server.origin+relative,options);
  };
  const context=vm.createContext({document,fetch:guardedFetch,alert:message=>result.alerts.push(String(message))});
  await new vm.Script(scripts[0][1],{filename:server.label+'-exact-inline.js'}).runInContext(context,{timeout:1500});
  return {document,server,script_sha256:sha(Buffer.from(scripts[0][1])),e:id=>document.elements.get(id),
    tab(name){const tab=document.tabs.find(b=>b.dataset.t===name);if(!tab)throw new Error('absent tab '+name);tab.onclick();},
    async change(id,value){const e=document.elements.get(id);if(!e)throw new Error('absent input '+id);if(e.tag==='select')assert.ok(e.options.some(o=>o.value===value),'real option value exists');e.value=value;await (id==='uc-search'||id==='q'?e.oninput():e.onchange());}};
}
function ids(app){return [...app.e('uc-rows').innerHTML.matchAll(/<tr><td><b>([\s\S]*?)<\/b>/g)].map(m=>decode(m[1]));}
function wanted(rows=cfg.expected){return rows.map(x=>x.visit_id);}
async function filter(app,status='',clinic='',query=''){
  await app.change('uc-status',status);await app.change('uc-clinic',clinic);await app.change('uc-search',query);
}
function observe(app,label,expected){same(ids(app),expected,label);result.filter_observations.push({label,shown:app.e('uc-shown').textContent,ids:ids(app)});}
function exportsOf(html){return [...html.matchAll(/<a\b([^>]*)>/g)].map(m=>({href:attr(m[1],'href'),download:/\bdownload\b/.test(m[1]),target:attr(m[1],'target')}));}
function sourceInventory(){return Object.fromEntries(Object.entries(report.source_after).map(([relative,pin])=>{
  const bytes=fs.readFileSync(path.resolve(cfg.candidate,'..',relative));assert.equal(sha(bytes),pin.sha256);return [relative,{size:bytes.length,sha256:sha(bytes)}];}));}
async function main(){
  result.program_sha256=sha(fs.readFileSync(__filename));result.server_program_sha256=sha(fs.readFileSync(path.join(root,'serve_fixture.py')));
  result.source_before=sourceInventory();
  const statePins=Object.fromEntries(Object.entries(cfg.outputs).map(([label,out])=>[label,sha(fs.readFileSync(path.join(out,'work_state.json')))]));
  const baseline=await open(await start('baseline')),candidate=await open(await start('candidate'));
  const regions=['cards','work','t-review','t-ledger'];
  for(const id of regions)same(candidate.e(id).innerHTML,baseline.e(id).innerHTML,'existing rendered markup unchanged: '+id);
  same(candidate.e('shown').textContent,'1 of 2 items','approved work item remains hidden by default');
  same(exportsOf(candidate.e('t-files').innerHTML).filter(x=>x.href!='/out/uncovered_visits.csv'),exportsOf(baseline.e('t-files').innerHTML),'all old digest/export hrefs and actions retained');
  await baseline.change('fs','all');const oldMarkup=baseline.e('work').textContent;
  check(!oldMarkup.includes(cfg.u5)&&!oldMarkup.includes(cfg.u6),'baseline all-staff-state markup still omits exact U5/U6');
  check(!baseline.document.tabs.some(x=>x.dataset.t==='uncovered'),'baseline lacks complete uncovered tab');
  candidate.tab('uncovered');check(!candidate.e('t-uncovered').classList.contains('hidden'),'actual tab handler opens complete review section');
  observe(candidate,'all nine complete rows independent of approved staff work item',wanted());
  same(candidate.e('uc-shown').textContent,'9 of 9 appointments · as of 2026-10-08','exact complete shown/total count');
  check(!/<[a-z][^>]*\bdata-pt-canary\b[^>]*>/i.test(candidate.e('uc-rows').innerHTML),'literal source HTML creates no unescaped canary tag');
  check(candidate.e('uc-rows').innerHTML.includes('Rules unavailable'),'unknown payer is visibly marked unavailable');
  await filter(candidate,'scheduled');observe(candidate,'seven scheduled rows',wanted(cfg.expected.filter(x=>x.status==='scheduled')));
  await filter(candidate,'completed');observe(candidate,'past and recorded future completed rows',['D-PAST','D-FUTURE']);
  await filter(candidate);same(candidate.e('uc-clinic').options.map(x=>x.value),['',...[...new Set(cfg.expected.map(x=>x.clinic))].sort().map(x=>JSON.stringify(x))],'actual generated option values preserve blank/newline/Unicode clinic distinction');
  await filter(candidate,'',JSON.stringify(''));observe(candidate,'blank visit clinic is distinct from all',['U3']);
  await filter(candidate,'',JSON.stringify(cfg.special_clinic));observe(candidate,'newline visit clinic exact selection',[cfg.u6]);
  check(candidate.e('uc-rows').textContent.includes(cfg.special_clinic),'source clinic embedded newline remains literal text');
  await filter(candidate,'','',cfg.u5.toUpperCase());observe(candidate,'case-insensitive literal Unicode/HTML visit search',[cfg.u5]);
  await filter(candidate,'','','ZOË');observe(candidate,'patient name search spans all eight visits',wanted(cfg.expected.filter(x=>x.patient_id==='PT-A')));
  await filter(candidate,'','','pay-missing');observe(candidate,'actual unknown payer ID search',['UNKNOWN']);
  check(candidate.e('uc-rows').textContent.includes('Name unavailable')&&!candidate.e('uc-rows').textContent.includes(cfg.payer_name),'unknown payer/name does not become patient primary payer');
  await filter(candidate,'scheduled',JSON.stringify('South'),'pt-a');observe(candidate,'status/visit-clinic/patient filter intersection',['U2','U4',cfg.u5]);
  await filter(candidate,'','','.*');observe(candidate,'regex punctuation is literal',[]);
  check(candidate.e('uc-rows').textContent.includes('No appointments match these filters.'),'filtered-empty differs from empty saved report');
  await filter(candidate,'','',cfg.therapist);observe(candidate,'search excludes undocumented therapist field',[]);
  await filter(candidate,'','','pay-missing');
  const downloadActions=exportsOf(candidate.e('uc-export').innerHTML);same(downloadActions,[{href:'/out/uncovered_visits.csv',download:true,target:null}],'native download markup points to complete CSV with no filter parameters');
  check(candidate.e('uc-export').textContent.includes('independent of these filters'),'export explicitly labels its complete unfiltered scope');
  const response=await fetch(candidate.server.origin+downloadActions[0].href);
  same(response.status,200,'unchanged real HTTP route serves complete CSV');
  const csv=Buffer.from(await response.arrayBuffer());same(csv,fs.readFileSync(path.join(cfg.outputs.candidate,'uncovered_visits.csv')),'one-row-filter URL returns exact all-nine-row CSV bytes');
  result.csv_download={bytes:csv.length,sha256:sha(csv),ui_rows:1,csv_rows:9,method:'actual Node HTTP GET from emitted link, not a browser download'};
  observe(candidate,'export leaves active UI filter unchanged',['UNKNOWN']);
  await filter(candidate);await candidate.change('q','no matching work item');same(candidate.e('shown').textContent,'0 of 2 items','existing worklist-only search remains effective');
  observe(candidate,'work-item search never truncates appointment review',wanted());
  const legacyHash=sha(fs.readFileSync(path.join(cfg.outputs.legacy,'summary.json')));
  const legacy=await open(await start('legacy'));legacy.tab('uncovered');
  same(sha(fs.readFileSync(path.join(cfg.outputs.legacy,'summary.json'))),legacyHash,'real matching-zone legacy GET does not silently rerun report');
  check(legacy.e('uc-note').textContent.includes('Run worklist'),'missing review asks for actual rerun');
  for(const id of ['uc-status','uc-clinic','uc-search'])check(legacy.e(id).disabled,'legacy disables '+id);
  same(legacy.e('uc-shown').textContent,'','missing review does not claim zero');
  same(exportsOf(legacy.e('uc-export').innerHTML),[],'legacy has no new export action');
  check(!exportsOf(legacy.e('t-files').innerHTML).some(x=>x.href==='/out/uncovered_visits.csv'),'legacy files tab also omits new export');
  await legacy.e('run').onclick({target:legacy.e('run')});
  observe(legacy,'existing Run action actually upgrades legacy report to all nine rows',wanted());
  check(!legacy.e('uc-status').disabled&&!legacy.e('run').disabled,'rerun completes and enables actual review controls');
  same(fs.readFileSync(path.join(cfg.outputs.legacy,'uncovered_visits.csv')),csv,'actual legacy web rerun creates same complete CSV bytes');
  same(legacy.e('shown').textContent,'1 of 2 items','legacy rerun preserves approved work state');
  const empty=await open(await start('empty'));empty.tab('uncovered');
  same(empty.e('uc-shown').textContent,'0 of 0 appointments · as of 2026-10-08','explicit empty saved array truthfully reports zero');
  check(empty.e('uc-rows').textContent.includes('No appointments are in this review for this report.'),'empty report message differs from legacy/no-match');
  check(!empty.e('uc-status').disabled&&exportsOf(empty.e('uc-export').innerHTML).length===1,'empty report has valid enabled review and header-only export');
  for(const [label,out] of Object.entries(cfg.outputs))same(sha(fs.readFileSync(path.join(out,'work_state.json'))),statePins[label],label+' staff state bytes unchanged through all UI/report operations');
  same(result.blocked,[],'zero attempted external/state/generator actions');same(result.alerts,[],'zero UI action errors');
  result.source_after=sourceInventory();same(result.source_after,result.source_before,'all tracked source bytes unchanged after receiving');
  result.inline_source_pins=[baseline,candidate,legacy,empty].map(x=>({label:x.server.label,sha256:x.script_sha256}));
  result.accepted=true;
}
main().catch(error=>{result.accepted=false;result.error=String(error.stack||error);process.exitCode=1;}).finally(async()=>{
  await stop();
  try{same(result.servers.flatMap(s=>s.events.filter(x=>x.request==='POST').map(x=>({label:s.label,path:x.path}))),[{label:'legacy',path:'/api/run'}],'one actual authored legacy rerun, no other POSTs');}
  catch(error){result.accepted=false;result.error=String(error.stack||error);process.exitCode=1;}
  fs.writeFileSync(path.join(root,'inline-receipt.json'),JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify({accepted:result.accepted,checks:result.checks.length,error:result.error,receipt:path.join(root,'inline-receipt.json')}));
});
