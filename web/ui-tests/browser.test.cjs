/* CI-only browser execution. No sandbox disabling or external runtime requests. */
const {chromium,expect}=require('@playwright/test');
const assert=require('node:assert/strict');
const http=require('node:http');
const fs=require('node:fs/promises');
const path=require('node:path');
const {inventory,report,unsupported}=require('./fixtures.cjs');
const root=path.resolve(__dirname,'..');
const artifacts=path.resolve(process.env.UI_ARTIFACT_DIR||'test-results/segment-seam-ui');
const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'};
const tests=[];const test=(name,run)=>tests.push({name,run});
let browser,server,base;
const payload={before:{name:'before.gpx',data:Buffer.from('<gpx/>').toString('base64')},after:{name:'after.gpx',data:Buffer.from('<gpx/>').toString('base64')}};
async function setup(options={}) {
  const context=await browser.newContext({viewport:options.mobile?{width:390,height:844}:{width:1440,height:1100},reducedMotion:'reduce'});
  const page=await context.newPage(),errors=[],requests=[],cancelled=[],posts=[];
  page.on('pageerror',error=>errors.push(error.message));
  const jobs=new Map();let count=0;
  await page.route('**/api/**',async route=>{
    const request=route.request(),url=new URL(request.url()),tail=url.pathname.split('/api/')[1];requests.push(tail);
    const json=(value,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(value)});
    if(tail==='demo')return json(payload);
    if(tail==='jobs'&&request.method()==='POST') {
      const body=request.postDataJSON();posts.push(body);const id=String(++count);jobs.set(id,body);
      if(options.startGate)await options.startGate;
      return json({id},202);
    }
    const cancel=tail.match(/^jobs\/([^/]+)\/cancel$/);if(cancel){cancelled.push(cancel[1]);return json({id:cancel[1],status:'cancelled'});}
    if(tail.endsWith('/packet.zip'))return route.fulfill({status:200,contentType:'application/zip',headers:{'Content-Disposition':'attachment; filename="evidence.zip"'},body:Buffer.from('PK mock evidence')});
    const id=tail.split('/')[1],job=jobs.get(id);
    if(!job)return json({error:'Not found'},404);
    if(options.holdCompare&&job.mode==='compare')return json({id,status:'running',progress:45});
    if(options.inspectError&&job.mode==='inspect')return json({id,status:'error',error:'Worker crashed during inspection'});
    if(options.incomplete&&job.mode==='inspect')return json({id,status:'done',result:{kind:'inventory'}});
    if(options.compareCrash&&job.mode==='compare')return json({id,status:'error',error:'Worker process exited unexpectedly'});
    const result=job.mode==='inspect'?inventory():(options.unsupported?unsupported():report());
    if(options.rawValues&&result.kind==='comparison'){result.seams[0].left.time={state:'raw',text:''};result.seams[0].right.time={state:'raw',text:' \n '};result.seams[0].left.elevation={state:'absent'};}
    if(options.hostile){result.before.name='<img src=x onerror="window.injected=true">.gpx';if(result.kind==='inventory')result.before.tracks[0].name='<script>window.injected=true</script>';else result.seams[0].left.time.text='<img src=x onerror="window.injected=true">';}
    return json({id,status:'done',progress:100,result});
  });
  await page.goto(base);
  return {page,context,errors,requests,cancelled,posts,options};
}
async function inspect(s){await s.page.locator('#demo-button').click();await expect(s.page.locator('#track-section')).toBeVisible();}
async function select(s){await s.page.locator('#before-track').selectOption('1');await s.page.locator('#after-track').selectOption('1');await s.page.locator('#same-track').check();}
async function compare(s){await inspect(s);await select(s);await s.page.locator('#compare-button').click();await expect(s.page.locator('#report-section')).toBeVisible();}
async function close(s){assert.deepEqual(s.errors,[]);await s.context.close();}
test('initial desktop: clipped skip link, keyboard focus, no overflow',async()=>{
 const s=await setup();const p=s.page;
 const clipped=await p.locator('.skip-link').evaluate(el=>{const style=getComputedStyle(el);return style.clipPath==='inset(50%)'&&el.getBoundingClientRect().width<=1;});assert.equal(clipped,true);
 await p.keyboard.press('Tab');await expect(p.locator('.skip-link')).toBeFocused();const bounds=await p.locator('.skip-link').boundingBox();assert.ok(bounds.width>100&&bounds.x>=0&&bounds.y>=0);await p.screenshot({path:path.join(artifacts,'desktop-focused-skip.png')});
 await p.keyboard.press('Enter');await expect(p.locator('#workspace')).toBeFocused();await expect(p.locator('#inspect-button')).toBeDisabled();await expect(p.locator('#before-file')).toHaveAccessibleName('Before GPX');await expect(p.locator('#after-file')).toHaveAccessibleName('After GPX');
 await p.evaluate(()=>window.scrollTo(0,500));assert.equal(await p.locator('.skip-link').evaluate(el=>getComputedStyle(el).clipPath==='inset(50%)'&&el.getBoundingClientRect().width<=1),true);assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await p.screenshot({path:path.join(artifacts,'desktop-initial.png'),fullPage:true});await close(s);
});
test('explicit pair + bilingual witnesses + download + invalidation',async()=>{
 const s=await setup();await inspect(s);const p=s.page;await expect(p.locator('#before-track')).toHaveValue('');await expect(p.locator('#after-track')).toHaveValue('');await expect(p.locator('#compare-button')).toBeDisabled();await p.locator('#before-track').selectOption('1');await p.locator('#after-track').selectOption('1');await expect(p.locator('#compare-button')).toBeDisabled();await p.locator('#same-track').check();await p.locator('#compare-button').click();await expect(p.locator('#report-title')).toHaveText('The boundary pattern changed.');
 assert.equal(s.posts.at(-1).before_track,1);assert.equal(s.posts.at(-1).confirmed,true);await expect(p.locator('.metric-value').first()).toHaveText('2,112.71 m');await expect(p.locator('.seam-row')).toHaveCount(3);await p.locator('.seam-row summary').first().click();await expect(p.locator('.point-card').first()).toContainText('2026-01-01T00:01:00Z');
 await p.locator('[data-filter=removed]').click();await expect(p.locator('.seam-row')).toHaveCount(1);await p.locator('.seam-row summary').click();
 await p.screenshot({path:path.join(artifacts,'desktop-evidence.png'),fullPage:true});
 await p.locator('#lang-ja').click();await expect(p.locator('html')).toHaveAttribute('lang','ja');await expect(p.locator('#before-track')).toHaveValue('1');await expect(p.locator('#same-track')).toBeChecked();await expect(p.locator('.seam-row')).toHaveCount(1);await expect(p.locator('#report-title')).toHaveText('境界の構成が変わりました。');
 await p.screenshot({path:path.join(artifacts,'desktop-japanese.png'),fullPage:true});
 const downloadPromise=p.waitForEvent('download');await p.locator('#download-link').click();assert.equal((await downloadPromise).suggestedFilename(),'evidence.zip');
 await p.locator('#before-track').selectOption('2');await expect(p.locator('#report-section')).toBeHidden();await expect(p.locator('#download-link')).not.toHaveAttribute('href',/.+/);await expect(p.locator('#same-track')).not.toBeChecked();await expect.poll(()=>s.cancelled.length).toBeGreaterThan(0);await close(s);
});
test('mobile Japanese report fits viewport and raw point text wraps',async()=>{
 const s=await setup({mobile:true,hostile:true});await s.page.locator('#lang-ja').click();await compare(s);await s.page.locator('.seam-row summary').first().click();assert.equal(await s.page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await s.page.evaluate(()=>window.scrollTo(0,600));assert.equal(await s.page.locator('.skip-link').evaluate(el=>getComputedStyle(el).clipPath==='inset(50%)'&&el.getBoundingClientRect().width<=1),true);await s.page.screenshot({path:path.join(artifacts,'mobile-japanese-evidence.png'),fullPage:true});await s.page.locator('.skip-link').focus();await expect(s.page.locator('.skip-link')).toBeFocused();const focused=await s.page.locator('.skip-link').boundingBox();assert.ok(focused.width>100&&focused.x>=0&&focused.y>=0);await s.page.screenshot({path:path.join(artifacts,'mobile-focused-skip.png')});await close(s);
});
test('unsupported has reasons and ZIP but no metric or equivalent verdict',async()=>{
 const s=await setup({unsupported:true});await compare(s);await expect(s.page.locator('.unsupported-note')).toContainText('Normalized XML point content differs at point 3');await expect(s.page.locator('.metrics-grid')).toHaveCount(0);await expect(s.page.locator('.seam-row')).toHaveCount(0);await expect(s.page.locator('#download-link')).toHaveAttribute('href',/packet.zip$/);await close(s);
});
test('hostile file and raw timestamp strings remain text',async()=>{
 const s=await setup({hostile:true});await compare(s);await s.page.locator('.seam-row summary').first().click();await expect(s.page.locator('.point-card').first()).toContainText('<img src=x');assert.equal(await s.page.evaluate(()=>Boolean(window.injected)),false);assert.equal(await s.page.locator('#report-body img, #report-body script').count(),0);await close(s);
});
test('raw empty text, whitespace, and absent fields have distinct readable values',async()=>{
 const s=await setup({rawValues:true});await compare(s);await s.page.locator('.seam-row summary').first().click();const left=s.page.locator('.point-card').first(),right=s.page.locator('.point-card').nth(1);await expect(left.locator('dd').nth(3)).toHaveText('""');await expect(left.locator('dd').nth(2)).toHaveText('Not supplied');assert.equal(await right.locator('dd').nth(3).textContent(),JSON.stringify(' \n '));await close(s);
});
test('inspection crash/incomplete cannot enable compare or expose report',async()=>{
 for(const options of [{inspectError:true},{incomplete:true}]){const s=await setup(options);await s.page.locator('#demo-button').click();await expect(s.page.locator('#error-region')).toBeVisible();await expect(s.page.locator('#track-section')).toBeHidden();await expect(s.page.locator('#compare-button')).toBeDisabled();await expect(s.page.locator('#report-section')).toBeHidden();await close(s);}
});
test('worker crash never produces a stale download',async()=>{const s=await setup({compareCrash:true});await inspect(s);await select(s);await s.page.locator('#compare-button').click();await expect(s.page.locator('#error-region')).toContainText('Worker process exited');await expect(s.page.locator('#download-link')).not.toHaveAttribute('href',/.+/);await close(s);});
test('cancel before start response cancels the late job and ignores its output',async()=>{
 let release;const gate=new Promise(resolve=>{release=resolve;});const s=await setup({startGate:gate});await s.page.locator('#demo-button').click();await expect.poll(()=>s.posts.length).toBe(1);await s.page.locator('#cancel-button').click();release();await expect.poll(()=>s.cancelled.length).toBe(1);await expect(s.page.locator('#track-section')).toBeHidden();await expect(s.page.locator('#report-section')).toBeHidden();await close(s);
});
test('rapid compare double-click starts only one worker, selection aborts it',async()=>{
 const s=await setup({holdCompare:true});await inspect(s);await select(s);await s.page.locator('#compare-button').evaluate(button=>{button.click();button.click();});await expect.poll(()=>s.posts.filter(job=>job.mode==='compare').length).toBe(1);await s.page.locator('#before-track').selectOption('2');await expect(s.page.locator('#cancel-button')).toBeHidden();await expect(s.page.locator('#report-section')).toBeHidden();await expect.poll(()=>s.cancelled.length).toBeGreaterThanOrEqual(2);await close(s);
});
test('swap, new inspect, restart, and replacement file clear reports immediately',async()=>{
 for(const action of ['swap','inspect','restart','file']){const s=await setup();await compare(s);const p=s.page;
  if(action==='swap')await p.locator('#swap-button').click();if(action==='inspect')await p.locator('#inspect-button').click();if(action==='restart')await p.locator('#restart-button').click();if(action==='file')await p.locator('#before-file').setInputFiles({name:'replacement.gpx',mimeType:'application/gpx+xml',buffer:Buffer.from('<gpx/>')});
  await expect(p.locator('#report-section')).toBeHidden();await expect(p.locator('#download-link')).not.toHaveAttribute('href',/.+/);await expect.poll(()=>s.cancelled.length).toBeGreaterThanOrEqual(2);await close(s);
 }
});
test('oversized and wrong-extension files cannot start inspection',async()=>{
 const s=await setup();await s.page.locator('#before-file').setInputFiles({name:'too-big.gpx',mimeType:'application/gpx+xml',buffer:Buffer.alloc(4194305)});await expect(s.page.locator('#before-error')).toContainText('4 MiB');await expect(s.page.locator('#inspect-button')).toBeDisabled();await s.page.locator('#after-file').setInputFiles({name:'wrong.xml',mimeType:'text/xml',buffer:Buffer.from('x')});await expect(s.page.locator('#after-error')).toContainText('.gpx');assert.equal(s.posts.length,0);await close(s);
});
(async()=>{
 await fs.mkdir(artifacts,{recursive:true});
 server=http.createServer(async(req,res)=>{try{const parsed=new URL(req.url,'http://localhost');const relative=decodeURIComponent(parsed.pathname).replace(/^\/test\//,'')||'index.html';if(relative.includes('..')||!['index.html','app.js','model.js','styles.css','favicon.svg'].includes(relative)){res.writeHead(404);return res.end();}const data=await fs.readFile(path.join(root,relative));res.writeHead(200,{'Content-Type':mime[path.extname(relative)]||'text/plain'});res.end(data);}catch{res.writeHead(500);res.end();}});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));base=`http://127.0.0.1:${server.address().port}/test/`;
 try{browser=await chromium.launch({headless:true,chromiumSandbox:true});for(const item of tests){await item.run();console.log(`PASS ${item.name}`);}console.log(`${tests.length} mock browser scenarios passed`);}
 finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
