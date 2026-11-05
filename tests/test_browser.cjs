// Run with: node tests/test_browser.cjs (Node 18+). Browser UI checks use Playwright separately.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8');
const engine=html.slice(html.indexOf('function csvRows('),html.indexOf('\nfunction message('));
const ctx=vm.createContext({TextDecoder,Uint8Array,atob});vm.runInContext(engine,ctx);
const input='2025-12-11_080729,11.12.2025,08:07:29,1,9,"BMW, G65",+,A_HORIZONTAL,+,-85,1,2,47,3,4\r\n';
const files=[{name:'renamed.zone.C.csv',data:Buffer.from(input).toString('base64')}];
const parsed=ctx.localParse(files);assert.equal(parsed.records.length,1);assert.equal(parsed.errors.length,0);assert.equal(parsed.records[0].product,'BMW, G65');
const rules=[{product:'BMW, G65',item:'A_HORIZONTAL',metric:'maximum',lower:-85,upper:85}];
let out=ctx.localEvaluate(parsed.records,rules);assert.equal(out[0].status,'合格');assert.equal(out[1].status,'未配置');
parsed.records[0].measurements[0].maximum=-86;assert.equal(ctx.localEvaluate(parsed.records,rules)[0].status,'超差');
assert.throws(()=>ctx.localEvaluate(parsed.records,[rules[0],{...rules[0],upper:90}]),/冲突/);
assert.equal(ctx.localParse([{name:'utf16.csv',data:Buffer.concat([Buffer.from([255,254]),Buffer.from(input,'utf16le')]).toString('base64')}]).records.length,1);
assert.equal(ctx.localParse([{name:'invalid.csv',data:Buffer.from('Zone,Blob-Nr.,Area,Quality,max. Optic').toString('base64')}]).errors.length,1);
console.log('Browser engine regressions passed: quoted CSV, renamed total, UTF-16, boundary, missing/NG/conflicting tolerance, invalid CSV.');
