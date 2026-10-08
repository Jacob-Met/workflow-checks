from pathlib import Path
import hashlib,json,datetime,subprocess
r=Path('/tmp/ultra-20b27c2e-runtime-pt-allocations-review')
p=r/'independent_pt_browser.cjs';b=p.read_bytes()
assert hashlib.sha256(b).hexdigest()=='5821894c601bcf94428af8f01481a03056cd169732beb4fbd90984c1c95dd09f'
(r/'receiver-corrections/independent_pt_browser.v3.cjs').write_bytes(b)
text=b.decode()
old='''const events=[],requests=[],responses=[],pageErrors=[],blocked=[],dialogs=[],downloads=[],exec=[];'''
new='''const requestedGroups=process.env.PT_REVIEW_GROUPS?process.env.PT_REVIEW_GROUPS.split(",").map(Number):null;
const events=[],requests=[],responses=[],pageErrors=[],blocked=[],dialogs=[],downloads=[],exec=[];'''
assert text.count(old)==1;text=text.replace(old,new)
old='''async function group(name,fn){
  try{'''
new='''async function group(name,fn){
  if(requestedGroups&&!requestedGroups.includes(Number(name.split("_")[0])))return;
  try{'''
assert text.count(old)==1;text=text.replace(old,new)
old='''  await page.focus(sel);await page.keyboard.press("Home");
  for(let i=0;i<index;i++)await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");'''
new='''  // Primary existing-control traces qualify native visible-label typeahead.
  const prefix=opts[index].text.trim()[0].toLowerCase();
  assert(/^[a-z]$/.test(prefix),"This fixed fixture requires an ASCII visible-label initial");
  await page.focus(sel);await page.keyboard.press(prefix);await page.keyboard.press("Enter");'''
assert text.count(old)==1;text=text.replace(old,new)
old='''  await page.focus("#alloc-search");await page.keyboard.down("Meta");await page.keyboard.press("A");await page.keyboard.up("Meta");
  await page.keyboard.press("Backspace");'''
new='''  // Plain edit keys are qualified on the unchanged existing search input.
  await page.focus("#alloc-search");
  const length=await page.$eval("#alloc-search",e=>e.value.length);
  for(let i=0;i<length;i++)await page.keyboard.press("Backspace");
  for(let i=0;i<length;i++)await page.keyboard.press("Delete");'''
assert text.count(old)==1;text=text.replace(old,new)
start=text.index('    await group("11_narrow_controls_and_native_horizontal_scroll"')
end=text.index('    for(const variant of ["missing","nonlist"])',start)
new='''    await group("11_narrow_controls_readable_dates_and_content_access",async()=>{
      await page.setViewport({width:390,height:844});await open();await panel();
      await page.$eval("#allocation-panel",e=>e.scrollIntoView({block:"start"}));
      for(const sel of ["#alloc-status","#alloc-auth","#alloc-clinic","#alloc-search"]){
        const rect=await page.$eval(sel,e=>{const r=e.getBoundingClientRect();return {width:r.width,height:r.height,visible:getComputedStyle(e).display!=="none"};});
        assert(rect.visible&&rect.width>30&&rect.height>15,sel+" is not a usable visible control");
      }
      const dates=await page.$$eval("#alloc-rows tbody tr",es=>es.slice(0,3).map(tr=>{
        const cell=tr.cells[1],range=document.createRange();range.selectNodeContents(cell);
        return {visit_id:tr.dataset.visitId,date:cell.textContent,lines:range.getClientRects().length,
                font_size:parseFloat(getComputedStyle(cell).fontSize),column_width:cell.getBoundingClientRect().width,
                row_height:tr.getBoundingClientRect().height};
      }));
      await page.screenshot({path:path.join(out,"narrow.png"),fullPage:false});
      write(path.join(out,"narrow-date-geometry.json"),dates);
      assert.equal(dates.length,3);
      for(const row of dates){
        assert.equal(row.date,oracle.rows.find(r=>r.visit_id===row.visit_id).visit_date);
        assert.equal(row.lines,1,"Recorded date "+row.date+" is broken across "+row.lines+" lines");
        assert(row.font_size>=12,"Recorded date became too small to read");
      }
      const handle=await page.evaluateHandle(()=>{
        let e=document.querySelector("#alloc-rows table")?.parentElement;
        while(e&&e.id!=="t-ledger"){if(["auto","scroll"].includes(getComputedStyle(e).overflowX))return e;e=e.parentElement;}
        return null;
      });
      const region=handle.asElement();assert(region,"Allocation table lacks its focusable review region");
      const before=await region.evaluate(e=>({scrollLeft:e.scrollLeft,scrollWidth:e.scrollWidth,clientWidth:e.clientWidth,tabIndex:e.tabIndex}));
      assert(before.tabIndex>=0);
      await page.focus("#alloc-search");await page.keyboard.press("Tab");
      assert(await region.evaluate(e=>document.activeElement===e),"Native Tab does not reach the allocation review region");
      let after=before.scrollLeft;
      if(before.scrollWidth>before.clientWidth){
        const box=await region.boundingBox();
        await page.mouse.move(box.x+Math.min(100,box.width/2),Math.max(10,Math.min(810,box.y+30)));
        await page.mouse.wheel({deltaX:before.scrollWidth*2,deltaY:0});await sleep(220);
        after=await region.evaluate(e=>e.scrollLeft);
        assert(after>before.scrollLeft,"Horizontal input cannot reveal the remaining source columns");
        assert(before.scrollWidth-before.clientWidth-after<=2,"Horizontal access did not reach the complete rightmost source column");
        await page.screenshot({path:path.join(out,"narrow-source-column.png"),fullPage:false});
      }
      await page.setViewport({width:1280,height:860});
      return {dates,before,scrollLeft_after:after,keyboard_reached_region:true};
    });
'''
text=text[:start]+new+text[end:]
old='''      probe_sha256:sha(fs.readFileSync(__filename)),oracle_sha256:sha(fs.readFileSync(path.join(ROOT,"oracle.json")))});
    process.exitCode'''
new='''      probe_sha256:sha(fs.readFileSync(__filename)),oracle_sha256:sha(fs.readFileSync(path.join(ROOT,"oracle.json"))),requested_groups:requestedGroups});
    process.exitCode'''
assert text.count(old)==1;text=text.replace(old,new)
updated=text.encode();p.write_bytes(updated)
check=subprocess.run(['/opt/homebrew/Cellar/node/26.3.0/bin/node','--check',str(p)],capture_output=True)
assert check.returncode==0,check.stderr
receipt={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_sha256':hashlib.sha256(b).hexdigest(),
 'corrected_sha256':hashlib.sha256(updated).hexdigest(),'source_changed':False,'oracle_changed':False,
 'mechanism_source':'existing-control-key-qualification-v2/receipt.json',
 'changes':['Use actual visible-label typeahead qualified on unchanged baseline select.',
            'Use plain Backspace/Delete then typing qualified on unchanged baseline search.',
            'Narrow acceptance checks readable one-line recorded dates, native Tab reachability and access to all columns; overflow is conditional, not an independent goal.',
            'Allow named affected-group replay; retain all original run results.'],
 'baseline_failed_mechanism_results':['control-layout-diagnostic/receipt.json','existing-control-key-qualification/receipt.json'],
 'product_finding':'control-layout-diagnostic/narrow-candidate-viewport.png',
 'replay_plan':{'original_ui':'3,4,5,6,7,8,9,11,14,15','css_successor':'11,14,15'},
 'unchanged_guards':'All non-loopback requests still blocked; only the exact recorded baseline internal date SVG is classified separately.'}
(r/'receiver-corrections/qualified-keys-and-readable-layout.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
