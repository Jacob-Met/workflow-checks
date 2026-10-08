const fs=require("node:fs"),path=require("node:path"),crypto=require("node:crypto"),{spawnSync}=require("node:child_process"),assert=require("node:assert/strict");
const root=__dirname;
const hash=(b,a="sha256")=>crypto.createHash(a).update(b).digest("hex");
const git=b=>hash(Buffer.concat([Buffer.from("blob "+b.length+"\0"),b]),"sha1");
const payload=JSON.parse(fs.readFileSync(path.join(root,"source-payload.json"),"utf8")).files;
const originals=new Map(payload.map(x=>[x.path,x]));
const spans=JSON.parse(fs.readFileSync(path.join(root,"inverse-spans.json"),"utf8"));
const own=new Set(spans.map(x=>x.path)),verified=[],unchanged=[],inverses=[];
for(const original of payload){
 const file=path.join(root,"baseline",original.path), b=fs.readFileSync(file);
 assert.equal(git(b),original.sha,original.path);
 assert.deepEqual(b,Buffer.from(original.content),original.path);
 verified.push({path:original.path,bytes:b.length,git_blob:git(b),sha256:hash(b)});
 if(!own.has(original.path)){
  assert.deepEqual(fs.readFileSync(path.join(root,"candidate",original.path)),b,original.path);
  unchanged.push(original.path);
 }
}
for(const item of spans){
 const file=path.join(root,"candidate",item.path), bytes=fs.readFileSync(file);let restored=bytes.toString("utf8");
 for(const part of item.remove){assert.equal(restored.split(part).length,2,item.path);restored=restored.replace(part,"");}
 assert.deepEqual(Buffer.from(restored),fs.readFileSync(path.join(root,"baseline",item.path)),item.path);
 inverses.push({path:item.path,removed_spans:item.remove.length,restored_git_blob:git(Buffer.from(restored)),
  candidate_sha256:hash(bytes),candidate_crlf:(bytes.toString().match(/\r\n/g)||[]).length,
  candidate_bare_lf:(bytes.toString().match(/(?<!\r)\n/g)||[]).length});
}
const first=fs.readFileSync(path.join(root,"first-candidate/batch_handoff_ui.js"),"utf8");
const before='        queueMicrotask(updateControls);\n      }\n    }, true);';
const after='      }\n    }, true);\n    // Bubble after the existing target handler has set reviewBusy or disabled its button.\n    document.addEventListener("click", event => {\n      if (event.target.closest("#run, #gen, button[data-d]")) updateControls();\n    });';
assert.equal(first.split(before).length,2);
const final=fs.readFileSync(path.join(root,"candidate/freight_packets/freightpkt/batch_handoff_ui.js"));
assert.deepEqual(Buffer.from(first.replace(before,after)),final);
const astCode=[
'import ast,json,sys',
'from pathlib import Path',
'r=Path(sys.argv[1])',
'def members(kind):',
' t=ast.parse((r/kind/"freight_packets/freightpkt/web.py").read_bytes()); c=next(x for x in t.body if isinstance(x,ast.ClassDef) and x.name=="App")',
' return {x.name:ast.dump(x,include_attributes=False) for x in c.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))}',
'a=members("baseline"); b=members("candidate")',
'assert all(b.get(k)==v for k,v in a.items())',
'assert set(b)-set(a)=={"review_batch"}',
'print(json.dumps({"unchanged_app_methods":sorted(a),"new_app_methods":sorted(set(b)-set(a))}))'
].join("\n");
const ast=spawnSync(process.env.PYTHON||"python3",["-B","-c",astCode,root],{encoding:"utf8"});
assert.equal(ast.status,0,ast.stderr);
const local=JSON.parse(fs.readFileSync(path.join(root,"local-qualification-payload.json"),"utf8"));
fs.mkdirSync(path.join(root,"local-qualification"),{recursive:true});
for(const item of local){const b=Buffer.from(item.base64,"base64");assert.equal(hash(b),item.sha256);assert.equal(git(b),item.git_blob);assert.equal(b.length,item.bytes);fs.writeFileSync(path.join(root,"local-qualification",item.path),b);}
const finalPins=JSON.parse(fs.readFileSync(path.join(root,"final-source-pins.json"),"utf8"));
for(const item of finalPins.files){const b=fs.readFileSync(path.join(root,"candidate",item.path));assert.equal(hash(b),item.sha256);assert.equal(git(b),item.git_blob);assert.equal(b.length,item.bytes);}
const receipt={schema:"freight-batch-source-preservation.v1",
 baseline_commit:"5b12dcd4c3a2c09d6602b2313e2bb556ac5997f7",baseline_tree:"e16dd0815e252c7e1715545999918f303bc823af",
 verified_originals:verified,unchanged_originals:unchanged,inverses,app_ast:JSON.parse(ast.stdout),
 ui_successor:{first_sha256:hash(Buffer.from(first)),final_sha256:hash(final),exact_replacement_only:true},
 final_sources:finalPins.files,local_receipt_custody:local.map(({base64,...x})=>x)};
fs.writeFileSync(path.join(root,"source-preservation.json"),JSON.stringify(receipt,null,2)+"\n");
console.log(JSON.stringify({baseline_files:verified.length,unowned_unchanged:unchanged.length,inverses:inverses.length,
 unchanged_app_methods:receipt.app_ast.unchanged_app_methods.length,final_sources:finalPins.files.length,local_receipts:local.length,
 receipt:path.join(root,"source-preservation.json")}));
