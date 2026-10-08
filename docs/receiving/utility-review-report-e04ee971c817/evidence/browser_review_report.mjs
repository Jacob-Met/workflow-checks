// Utility Watch saved worksheet browser/print receiving.
// CDP/loopback/owned-profile lifecycle adapted from the existing ShadeWindow
// historical-review browser-smoke.mjs; test cases and served bytes are isolated here.
// Node 22+ and an already installed Chromium; no package installation.
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import {spawn, execFileSync} from 'node:child_process';

const root = path.resolve(process.argv[2]);
const browserPath = process.argv[3] ?? '/snap/bin/chromium';
const profileRoot = process.argv[4] ?? '/home/jacob/snap/chromium/common';
const evidence = path.join(root, 'evidence');
const sourcePath = path.join(evidence, 'example-saved-review.html');
const worksheetPath = path.join(evidence, 'native-review-with-history.csv');
const expected = JSON.parse(await fs.readFile(path.join(evidence, 'browser-expected.json'), 'utf8'));
const raw = await fs.readFile(sourcePath);
const worksheet = await fs.readFile(worksheetPath);
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
assert.equal(sha(raw), expected.html_sha256);
assert.equal(sha(worksheet), expected.worksheet_sha256);
const disk = await fs.statfs(profileRoot);
const available = disk.bavail * disk.bsize;
if (available < 64 * 1024 * 1024) throw new Error('Fixture needs 64 MiB profile headroom; available=' + available);
const profile = await fs.mkdtemp(path.join(profileRoot, 'hamon-utility-review-e04ee-'));
const checks = [], requests = [], exceptions = [], failures = [], artifacts = {};
let browser, socket, server, receipt, url, cleanupError;
const pending = new Map();
let nextId = 0;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
function check(name, actual, expectedValue) {
  const ok = JSON.stringify(actual) === JSON.stringify(expectedValue);
  checks.push({name, ok, actual, expected: expectedValue});
  if (!ok) throw new Error('Receiving condition failed: ' + name);
}
function send(method, params = {}, sessionId) {
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('CDP timeout: ' + method)); }, 15000);
    pending.set(id, {resolve, reject, timer});
    socket.send(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})}));
  });
}
async function evaluate(sessionId, expression) {
  const result = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true}, sessionId);
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
  return result.result.value;
}
async function waitFor(sessionId, expression) {
  const until = Date.now() + 15000;
  while (Date.now() < until) {
    if (await evaluate(sessionId, expression)) return;
    await delay(75);
  }
  throw new Error('Expected page state was not reached: ' + expression);
}
async function save(name, data) {
  await fs.writeFile(path.join(evidence, name), data, {flag: 'wx'});
  artifacts[name] = {bytes: data.length, sha256: sha(data)};
}
const browserVersion = execFileSync(browserPath, ['--version'], {encoding: 'utf8', timeout: 15000}).trim();
try {
  server = http.createServer((request, response) => {
    const pathname = new URL(request.url, 'http://localhost').pathname;
    if (pathname === '/' || pathname === '/saved-review.html') {
      response.writeHead(200, {'content-type':'text/html; charset=utf-8','cache-control':'no-store'});
      response.end(raw);
    } else if (pathname === '/favicon.ico') {
      response.writeHead(204); response.end();
    } else {
      response.writeHead(404); response.end('Outside this isolated fixture');
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  url = 'http://127.0.0.1:' + server.address().port + '/saved-review.html';
  browser = spawn(browserPath, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    '--disable-background-networking', '--disable-component-update', '--disable-sync',
    '--disable-extensions', '--disable-default-apps', '--password-store=basic',
    '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0',
    '--user-data-dir=' + profile, 'about:blank'
  ], {stdio:['ignore','ignore','pipe']});
  const endpoint = await new Promise((resolve, reject) => {
    let text = '';
    const timer = setTimeout(() => reject(new Error('Owned Chromium did not expose CDP')), 15000);
    browser.once('error', err => {clearTimeout(timer); reject(err);});
    browser.once('exit', code => {clearTimeout(timer); reject(new Error('Owned Chromium exited: ' + code + '; ' + text.slice(-2500)));});
    browser.stderr.on('data', chunk => {
      text = (text + chunk.toString()).slice(-15000);
      const match = text.match(/DevTools listening on (ws:\/\/127\.0\.0\.1:[^\s]+)/);
      if (match) {clearTimeout(timer); resolve(match[1]);}
    });
  });
  socket = new WebSocket(endpoint);
  await new Promise((resolve, reject) => {socket.addEventListener('open', resolve, {once:true}); socket.addEventListener('error', reject, {once:true});});
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id) {
      const task = pending.get(message.id);
      if (!task) return;
      pending.delete(message.id); clearTimeout(task.timer);
      message.error ? task.reject(new Error(JSON.stringify(message.error))) : task.resolve(message.result);
    } else if (message.method === 'Network.requestWillBeSent') {
      requests.push(message.params.request.url);
    } else if (message.method === 'Runtime.exceptionThrown') {
      exceptions.push(message.params.exceptionDetails.text);
    } else if (message.method === 'Network.loadingFailed') {
      failures.push({errorText:message.params.errorText,canceled:message.params.canceled??false});
    }
  });
  const {targetId} = await send('Target.createTarget', {url:'about:blank'});
  const {sessionId} = await send('Target.attachToTarget', {targetId, flatten:true});
  await send('Runtime.enable', {}, sessionId);
  await send('Page.enable', {}, sessionId);
  await send('Network.enable', {}, sessionId);
  await send('Emulation.setDeviceMetricsOverride', {width:1280,height:900,deviceScaleFactor:1,mobile:false}, sessionId);
  await send('Page.navigate', {url}, sessionId);
  await waitFor(sessionId, "document.readyState === 'complete' && document.querySelectorAll('article.finding').length === 15");
  const dom = await evaluate(sessionId, String.raw`(() => {
    const fields = root => Object.fromEntries([...root.querySelectorAll('dt')].map(dt => [dt.textContent,dt.nextElementSibling.textContent]));
    return {
      title:document.title,
      current:document.querySelectorAll('#current article').length,
      history:document.querySelectorAll('#history article').length,
      counts:document.querySelector('.counts').textContent,
      snapshot:document.querySelector('.snapshot').textContent,
      source:document.querySelector('.source').textContent,
      active:document.querySelectorAll('script,iframe,object,embed,form,input,button,link,img,video,audio').length,
      eventAttributes:[...document.querySelectorAll('*')].flatMap(el=>[...el.attributes].filter(attr=>/^on/i.test(attr.name)).map(attr=>attr.name)),
      links:[...document.querySelectorAll('a')].map(el=>el.getAttribute('href')),
      rows:[...document.querySelectorAll('article')].map(article => ({
        id:article.id, state:article.dataset.rowState, section:article.parentElement.id,
        fields:fields(article), evidence:[...article.querySelectorAll('li code')].map(el=>el.textContent),
        detail:article.querySelector('p.multiline').textContent
      })),
      overflow:document.documentElement.scrollWidth > innerWidth
    };
  })()`);
  check('title', dom.title, 'Utility Watch saved review');
  check('current/native worksheet count', dom.current, expected.current);
  check('historical/native worksheet count', dom.history, expected.history);
  check('no active elements in saved HTML', dom.active, 0);
  check('no user-controlled event attributes', dom.eventAttributes, []);
  check('only in-document navigation', dom.links, ['#current','#history']);
  check('desktop has no horizontal document overflow', dom.overflow, false);
  check('snapshot contains exact input digest', dom.source.includes(expected.worksheet_sha256), true);
  check('synthetic snapshot notice', dom.snapshot.includes('SYNTHETIC DATA · Read-only snapshot'), true);
  check('exact finding row IDs/order', dom.rows.map(row=>row.id), expected.rows.map(row=>'row-'+row.row_id));
  for (let i=0;i<expected.rows.length;i++) {
    const row=expected.rows[i], actual=dom.rows[i];
    check('row '+i+' state/section', [actual.state,actual.section], [row.row_state,row.row_state==='current'?'current':'history']);
    check('row '+i+' reviewer and saved note', [actual.fields.Reviewer,actual.fields.Note],
          [row.reviewer || 'Unassigned', row.note || 'No note recorded']);
    check('row '+i+' source evidence pointers', actual.evidence, JSON.parse(row.evidence));
    check('row '+i+' identity values', [actual.fields['Worksheet row ID'],actual.fields['Finding ID'],actual.fields['Evidence version'],actual.fields['Protected record SHA256']],
          [row.row_id,row.finding_id,row.evidence_version,row.record_sha256]);
    check('row '+i+' finding detail', actual.detail, row.detail);
  }
  const annotated=expected.rows.filter(row=>row.note);
  check('native prior annotation is retained only in history', annotated.map(row=>row.row_state), ['changed']);
  check('literal HTML-like note is text', dom.rows.find(row=>row.state==='changed').fields.Note, annotated[0].note);
  const desktop = await send('Page.captureScreenshot', {format:'png',captureBeyondViewport:false}, sessionId);
  await save('browser-desktop.png', Buffer.from(desktop.data,'base64'));
  await send('Runtime.evaluate', {expression:"document.querySelector('#history').scrollIntoView()"}, sessionId);
  await delay(80);
  const history = await send('Page.captureScreenshot', {format:'png',captureBeyondViewport:false}, sessionId);
  await save('browser-history.png', Buffer.from(history.data,'base64'));
  await send('Emulation.setDeviceMetricsOverride', {width:390,height:844,deviceScaleFactor:1,mobile:true}, sessionId);
  await evaluate(sessionId, 'scrollTo(0,0)');
  const mobile = await evaluate(sessionId, "({width:innerWidth,overflow:document.documentElement.scrollWidth > innerWidth,columns:getComputedStyle(document.querySelector('article dl')).gridTemplateColumns,articles:document.querySelectorAll('article').length})");
  check('mobile width', mobile.width, 390);
  check('mobile has no horizontal document overflow', mobile.overflow, false);
  check('mobile retains every finding', mobile.articles, expected.rows.length);
  check('mobile field definitions use one column', mobile.columns.trim().split(/\s+/).length, 1);
  await save('browser-mobile.png', Buffer.from((await send('Page.captureScreenshot', {format:'png',captureBeyondViewport:false}, sessionId)).data,'base64'));
  await send('Emulation.setDeviceMetricsOverride', {width:1280,height:900,deviceScaleFactor:1,mobile:false}, sessionId);
  await send('Emulation.setEmulatedMedia', {media:'print'}, sessionId);
  await evaluate(sessionId, 'scrollTo(0,0)');
  const print = await evaluate(sessionId, "({navigation:getComputedStyle(document.querySelector('nav')).display,identities:[...document.querySelectorAll('.identities')].map(el=>getComputedStyle(el).display),notes:[...document.querySelectorAll('article')].map(article=>[...article.querySelectorAll('dt')].find(el=>el.textContent==='Note').nextElementSibling.textContent),overflow:document.documentElement.scrollWidth > innerWidth})");
  check('print omits navigation', print.navigation, 'none');
  check('print retains visible identity blocks', print.identities.every(value=>value!=='none'), true);
  check('print retains exact saved notes', print.notes, expected.rows.map(row=>row.note||'No note recorded'));
  check('print has no horizontal document overflow', print.overflow, false);
  const pdf=Buffer.from((await send('Page.printToPDF', {printBackground:true,paperWidth:8.27,paperHeight:11.69,marginTop:0.4,marginBottom:0.4,marginLeft:0.4,marginRight:0.4}, sessionId)).data,'base64');
  check('real Chromium PDF header', pdf.subarray(0,5).toString(), '%PDF-');
  check('real Chromium PDF EOF', pdf.subarray(-100).toString().includes('%%EOF'), true);
  await save('browser-print.pdf',pdf);
  const textTool='/usr/bin/pdftotext';
  let pdfText;
  try {
    await fs.access(textTool);
    pdfText=execFileSync(textTool,[path.join(evidence,'browser-print.pdf'),'-'],{encoding:'utf8',timeout:15000,maxBuffer:1024*1024});
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  if (pdfText !== undefined) {
    check('printed PDF retains history section', pdfText.includes('Prior findings (1)'), true);
    check('printed PDF retains literal note', pdfText.includes('<script>must remain text</script>.'), true);
    check('printed PDF retains reviewer', pdfText.includes('Zoë'), true);
    await save('browser-print-text.txt',Buffer.from(pdfText));
  }
  check('no page runtime exceptions', exceptions, []);
  check('no page resource loading failures', failures, []);
  check('all observed page requests are fixture loopback', requests.every(value=>value.startsWith(new URL(url).origin+'/')), true);
  check('served HTML remains byte exact', sha(await fs.readFile(sourcePath)), sha(raw));
  check('saved worksheet remains byte exact', sha(await fs.readFile(worksheetPath)), sha(worksheet));
  receipt={result:'PASS',node:process.version,browser:browserVersion,uid:process.getuid(),profile_parent:profileRoot,profile:path.basename(profile),available_before:available,
    html:{sha256:sha(raw),bytes:raw.length},worksheet:{sha256:sha(worksheet),bytes:worksheet.length},checks,artifacts,observed_page_requests:requests,
    limits:['Synthetic captured worksheet only.','Observed page requests are loopback; no claim about every Chromium background operation.','Print is the existing installed Chromium, not every browser or physical printer.']};
} catch(error) {
  receipt={result:'FAIL',node:process.version,browser:browserVersion,uid:process.getuid(),checks,artifacts,error:String(error.stack??error),observed_page_requests:requests};
  process.exitCode=1;
} finally {
  try {
    if(socket?.readyState===WebSocket.OPEN) await Promise.race([send('Browser.close').catch(()=>{}),delay(3000)]);
    socket?.close();
    if(browser && browser.exitCode===null){
      browser.kill('SIGTERM');
      await Promise.race([new Promise(resolve=>browser.once('exit',resolve)),delay(4000)]);
      if(browser.exitCode===null){browser.kill('SIGKILL');await Promise.race([new Promise(resolve=>browser.once('exit',resolve)),delay(2000)]);}
    }
    server?.closeAllConnections();
    if(server) await new Promise(resolve=>server.close(resolve));
    await fs.rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:100});
  } catch(error) {cleanupError=String(error.stack??error);process.exitCode=1;}
  for(const task of pending.values()) clearTimeout(task.timer);
  if(receipt){
    receipt.cleanup={profile_removed:await fs.stat(profile).then(()=>false,error=>error.code==='ENOENT'),owned_browser_exited:!browser||browser.exitCode!==null,error:cleanupError??null};
    if(cleanupError || !receipt.cleanup.profile_removed || !receipt.cleanup.owned_browser_exited) receipt.result='FAIL';
    await fs.writeFile(path.join(evidence,'browser-results.json'),JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
    console.log(JSON.stringify({result:receipt.result,conditions:checks.length,failures:checks.filter(check=>!check.ok).length,browser:browserVersion,artifacts,cleanup:receipt.cleanup}));
  }
}
