import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {pathToFileURL,fileURLToPath} from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const [adapterPath,outputPath]=process.argv.slice(2);
if(!adapterPath||!outputPath) throw new Error('Usage: node semantic-receiver-v1.mjs ADAPTER.mjs NEW_RECEIPT.json');
if(fs.existsSync(outputPath)) throw new Error('Receipt output already exists; preserve the earlier attempt.');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const rawIndex=fs.readFileSync(path.join(root,'fixture-index-v1.json'));
assert.equal(sha(rawIndex),'9695e82b5749e80f9531ad1916bcddfb5a40d83f37ffe874abe3506f40f421e8');
const rawContract=fs.readFileSync(path.join(root,'contract-v1.json'));
assert.equal(sha(rawContract),'3713b8fb96f560689bdcba78985917bc3bf988fc884209622016fd6bac5f09d2');
const rawManifest=fs.readFileSync(path.join(root,'freeze-manifest-v1.json'));
assert.equal(sha(rawManifest),'f3b20a7158b177796894b078942d56f023171e75a865aba944b0494c05f5bcb1');
const index=JSON.parse(rawIndex), manifest=JSON.parse(rawManifest);
for(const m of manifest.members){const b=fs.readFileSync(path.join(root,m.path));assert.equal(b.length,m.bytes,m.path);assert.equal(sha(b),m.sha256,m.path);}
const adapter=await import(pathToFileURL(path.resolve(adapterPath)).href);
assert.equal(typeof adapter.admit,'function','Thin receiver adapter exports admit({text,byteLength,filename})');
assert.ok(adapter.sourceBinding && typeof adapter.sourceBinding==='object','Adapter supplies exact source binding');
function canonical(value) {
 if(value===null||typeof value==='string'||typeof value==='boolean') return value;
 if(typeof value==='number'){assert.ok(Number.isFinite(value));return value===0?0:value;}
 if(Array.isArray(value)) return value.map(canonical);
 assert.equal(typeof value,'object','Expected a JSON-safe result');
 return Object.fromEntries(Object.keys(value).sort().map(k=>[k,canonical(value[k])]));
}
const outcomes=[],started_at=new Date().toISOString();
for(const c of index.cases){
 const bytes=fs.readFileSync(path.join(root,c.path));
 assert.equal(bytes.length,c.bytes);assert.equal(sha(bytes),c.sha256);
 const request=Object.freeze({text:bytes.toString('utf8'),byteLength:bytes.length,filename:c.displayFilename||path.basename(c.path)});
 let returned,admissionError=null,error=null;
 try{returned=await adapter.admit(request);}catch(e){admissionError={name:e?.name||typeof e,message:String(e?.message||e).slice(0,2000)};}
 try{
  if(c.accept){assert.equal(admissionError,null,'Expected complete record admission');assert.deepEqual(canonical(returned),canonical(c.expected));}
  else {assert.notEqual(admissionError,null,'Expected whole-file refusal, but adapter returned a record');}
 }catch(e){error={name:e.name,message:e.message,expectedAccept:c.accept,admissionError};}
 outcomes.push({id:c.id,expectedAccept:c.accept,pass:error===null,fixtureSha256:c.sha256,fixtureBytes:c.bytes,...(admissionError?{admissionError}:{}),...(error?{error}:{})});
}
const receipt={format:'estate-freight-independent-admission-receipt/1',started_at,finished_at:new Date().toISOString(),node:process.version,
 fixture_index_sha256:sha(rawIndex),contract_sha256:sha(rawContract),freeze_manifest_sha256:sha(rawManifest),
 receiver:{path:path.basename(fileURLToPath(import.meta.url)),sha256:sha(fs.readFileSync(fileURLToPath(import.meta.url)))},
 adapter:{path:path.resolve(adapterPath),sha256:sha(fs.readFileSync(adapterPath))},
 source:adapter.sourceBinding,total:outcomes.length,passed:outcomes.filter(x=>x.pass).length,failed:outcomes.filter(x=>!x.pass).length,
 scope:'Independent preimplementation admission fixtures only; no browser, deployed-site or unchanged-rule-math requalification is implied.',outcomes};
fs.writeFileSync(outputPath,JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({receipt:outputPath,sha256:sha(fs.readFileSync(outputPath)),total:receipt.total,passed:receipt.passed,failed:receipt.failed}));
if(receipt.failed)process.exitCode=1;
