const vm = require('node:vm');
const crypto = require('node:crypto');
const input = JSON.parse(process.argv[1]);
function inspect(html) {
  const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)];
  const external = scripts.filter(s => /\bsrc\s*=/.test(s[1])).map(s => ({attributes:s[1],body:s[2]}));
  const inline = scripts.filter(s => !/\bsrc\s*=/.test(s[1]));
  if (inline.length !== 1) throw new Error('Expected exactly one inline block beside the external script');
  for (const s of inline) new vm.Script(s[2], {filename:'pt_auth/ptauth/ui.html:inline'});
  return {sha256:crypto.createHash('sha256').update(html,'utf8').digest('hex'),bytes:Buffer.byteLength(html),external,inline_count:inline.length};
}
try {
  const baseline=inspect(input.baseline),candidate=inspect(input.candidate);
  if (JSON.stringify(baseline.external)!==JSON.stringify(candidate.external)) throw new Error('External script entry changed');
  console.log(JSON.stringify({runtime:process.version,baseline,candidate,syntax:'pass',executed:false}));
} catch (error) {
  console.error(JSON.stringify({runtime:process.version,error:error.message,syntax:'not qualified'}));
  process.exitCode=1;
}
