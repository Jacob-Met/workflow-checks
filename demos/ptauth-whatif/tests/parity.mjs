/** Existing receiving comparator; native Python results arrive on stdin. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {isDeepStrictEqual} from 'node:util';

const here=path.dirname(fileURLToPath(import.meta.url));
const pin=JSON.parse(fs.readFileSync(path.join(here,'pins.json'),'utf8'));
const source=path.join(here,'..',pin.model.path),raw=fs.readFileSync(source);
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
if(sha(raw)!==pin.model.sha256)throw Error('Pinned browser model changed; reconcile and qualify before updating the pin');
if(/^\s*import\s/m.test(raw.toString()))throw Error('Model dependencies need explicit receiving custody');
const packet=JSON.parse(fs.readFileSync(0,'utf8'));
if(packet.corpus_sha256!==pin.corpus.sha256||packet.cases?.length!==pin.corpus.cases||packet.native_cases!==pin.corpus.cases)
  throw Error('Run parity.py to provide all current native-oracle cases');
const {evaluate}=await import(pathToFileURL(source));
const normalized=x=>JSON.parse(JSON.stringify(x));
const differences=(a,b,p='')=>{
  if(isDeepStrictEqual(a,b))return [];
  if(a===null||b===null||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b))return[{path:p,expected:b,actual:a}];
  const out=[];for(const k of new Set([...Object.keys(a),...Object.keys(b)])){out.push(...differences(a[k],b[k],p+'/'+k));if(out.length>=20)break;}return out;
};
const failures=[];let passed=0;
for(const c of packet.cases){
  const input=structuredClone(c.input),before=JSON.stringify(input);
  try{
    const actual=normalized(evaluate(input));
    if(JSON.stringify(input)!==before){failures.push({id:c.id,kind:'input_mutated'});continue;}
    const repeated=normalized(evaluate(structuredClone(c.input)));
    if(!isDeepStrictEqual(actual,repeated)){failures.push({id:c.id,kind:'nondeterministic'});continue;}
    const diff=differences(actual,c.expected);
    if(diff.length)failures.push({id:c.id,kind:'oracle_mismatch',differences:diff});
    else passed++;
  }catch(error){failures.push({id:c.id,kind:'candidate_exception',name:error.name,message:error.message});}
}
if(sha(fs.readFileSync(source))!==sha(raw))throw Error('Browser model changed during receiving');
const receipt={schema:'ptauth-whatif.portable-parity.v1',python_source_commit:packet.python_source_commit,
  python_engine_blob:pin.python_inputs.find(p=>p.path.endsWith('/engine.py')).git_blob,
  model_sha256:sha(raw),corpus_sha256:packet.corpus_sha256,
  native_cases:packet.native_cases,matched_recorded_expected:packet.matched_recorded_expected,
  cases:packet.cases.length,passed,failed:failures.length,
  identical_results_on_repeat:failures.every(x=>x.kind!=='nondeterministic'),
  unchanged_inputs:failures.every(x=>x.kind!=='input_mutated'),failures};
process.stdout.write(JSON.stringify(receipt,null,2)+'\n');
process.exitCode=failures.length?1:0;
