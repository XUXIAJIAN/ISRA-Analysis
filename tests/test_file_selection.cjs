// Optional UI regression: install Playwright and Chromium, then run this file.
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent(fs.readFileSync(path.join(__dirname,'../index.html'),'utf8'));await page.context().setOffline(true);
  const row=(id,product,sign,value)=>`2026-11-03_10000${id},03.11.2026,10:00:0${id},${id},9,${product},${sign},A_HORIZONTAL,${sign},${value},1,2,50,3,4\n`;
  const a={name:'first.csv',mimeType:'text/csv',buffer:Buffer.from(row(1,'BMW G65','+',20)+row(2,'BMW G65','-',100))};
  const b={name:'second.csv',mimeType:'text/csv',buffer:Buffer.from(row(3,'C1UL WS','+',30))};
  const count=async n=>page.waitForFunction(n=>document.querySelector('#count').textContent===String(n),n);
  await page.locator('#files').setInputFiles([a,b]);await count(3);assert.equal(await page.locator('#fileRows input:checked').count(),2);
  await page.locator('#fileRows input').first().uncheck();await count(1);assert.equal(await page.locator('#yield').textContent(),'100.0%');assert.equal(await page.locator('#ng').textContent(),'0');assert.deepEqual(await page.locator('#product option').allTextContents(),['全部品种','C1UL WS']);
  await page.evaluate(()=>{window.exported=null;download=(name,text)=>window.exported={name,text}});await page.click('#export');let exported=await page.evaluate(()=>window.exported.text);assert(exported.includes('second.csv'));assert(!exported.includes('first.csv'));
  await page.click('#selectNoFiles');await count(0);assert.equal(await page.locator('#rows tr').count(),0);assert.equal(await page.locator('#summary tr').count(),0);assert.equal(await page.locator('#yield').textContent(),'—');
  await page.click('#selectAllFiles');await count(3);await page.selectOption('#product','BMW G65');await count(2);await page.selectOption('#item','A_HORIZONTAL');assert.equal(await page.locator('#trend circle').count(),2);
  await page.locator('#files').setInputFiles(a);await count(4);assert.equal(await page.locator('#fileRows tr').count(),3);assert((await page.locator('#messages').textContent()).includes('重复'));
  await page.locator('#fileRows input').first().uncheck();await count(2);await page.locator('#fileRows input').nth(2).uncheck();await count(1);assert.deepEqual(await page.locator('#product option').allTextContents(),['全部品种','C1UL WS']);
  await page.click('#clear');await count(0);assert.equal(await page.locator('#fileRows tr').count(),0);assert.equal(await page.locator('#rules tr').count(),34);assert.deepEqual(errors,[]);
  console.log('PASS: offline batch import, checkbox scope, all/none, filter/trend/export consistency, append, same-name isolation, duplicate warning, clear preserves tolerances');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
