import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const filename=process.env.FREIGHT_IMPORTER_PATH,expected=process.env.FREIGHT_IMPORTER_SHA256;
assert.ok(filename&&expected&&/^[a-f0-9]{64}$/.test(expected),'Provide immutable importer path and expected SHA256');
const dir=path.dirname(path.resolve(filename)),sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const pins=[
 {name:path.basename(filename),path:path.resolve(filename),sha256:expected},
 {name:'model.mjs',path:path.join(dir,'model.mjs'),sha256:'88e3d460da6f421e937cf54b21207da95734db3de3d5932235b1ec001be52590'},
 {name:'data.mjs',path:path.join(dir,'data.mjs'),sha256:'c5b8819e50961180208fa8dd4951f6a559b28cc4467c52dd2a68abeeb1b25d81'}
];
for(const p of pins){const b=fs.readFileSync(p.path);assert.equal(sha(b),p.sha256,p.name);p.bytes=b.length;}
const api=await import(pathToFileURL(path.resolve(filename)).href);
const {data}=await import(pathToFileURL(path.join(dir,'data.mjs')).href);
assert.equal(api.MAX_RECORD_BYTES,1048576);
assert.equal(typeof api.parseScenarioRecord,'function');
export const sourceBinding=Object.freeze({api:'parseScenarioRecord(text)',baseline_commit:'39ea75b0da2a7c3463e426dd32ba52860966cae4',files:pins});
function frozen(x){if(x&&typeof x==='object'){assert.ok(Object.isFrozen(x),'Public API promises deeply frozen return');for(const v of Object.values(x))frozen(v);}}
export function admit({text,byteLength}) {
 assert.equal(Buffer.byteLength(text,'utf8'),byteLength,'Receiver passes exact UTF8 text length');
 const r=api.parseScenarioRecord(text);
 assert.deepEqual(Object.keys(r).sort(),['schema','synthetic','exported_at','loaded_preset','provenance','contract','baseline','current','comparison'].sort());
 assert.equal(r.schema,'workflow-checks.freight-whatif.v1');assert.equal(r.synthetic,true);
 assert.deepEqual(r.provenance,data.provenance);assert.deepEqual(r.contract,data.contract);
 frozen(r);
 return {preset:r.loaded_preset,scenario:r.current.scenario,baseline:r.baseline,result:r.current.result,comparison:r.comparison,exported_at:r.exported_at};
}
