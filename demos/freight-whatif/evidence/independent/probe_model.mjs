import fs from "node:fs";
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
const [modelPath,oraclePath,outPath]=process.argv.slice(2);
const {evaluate,validateScenario}=await import(pathToFileURL(modelPath).href);
const oracle=JSON.parse(fs.readFileSync(oraclePath,"utf8"));
const rows=[];
for(const c of oracle.cases){
 try{
  assert.deepStrictEqual(validateScenario(c.scenario),[]);
  const actual=evaluate(structuredClone(c.scenario));
  assert.deepStrictEqual(actual,c.expected);
  rows.push({id:c.id,passed:true,status:actual.stop.status,amount_cents:actual.stop.amount_cents,
   flags:actual.flags.map(f=>f.code)});
 }catch(e){rows.push({id:c.id,passed:false,error:e.message,actual:e.actual,expected:e.expected});}
}
const result={node:process.version,total:rows.length,passed:rows.filter(x=>x.passed).length,failed:rows.filter(x=>!x.passed).length,cases:rows};
fs.writeFileSync(outPath,JSON.stringify(result,null,2)+"\n");
console.log(JSON.stringify({total:result.total,passed:result.passed,failed:result.failed}));
if(result.failed)process.exitCode=1;
