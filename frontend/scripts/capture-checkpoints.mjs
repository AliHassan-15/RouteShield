// Manual screenshots only. API fixtures are synthetic; live bodies stay in memory.
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
const output=resolve(process.cwd(),'../output/playwright/checkpoints');
process.env.PLAYWRIGHT_BROWSERS_PATH ??= resolve(process.cwd(),'../.cache/ms-playwright');
const {chromium}=await import('@playwright/test');
await mkdir(output,{recursive:true});
const body=JSON.parse(await readFile(resolve(output,'synthetic.json'),'utf8'));
body.generated_at=new Date().toISOString();body.expires_at=new Date(Date.now()+900000).toISOString();body.routes.forEach(r=>r.checkpoints.forEach(cp=>{cp.weather.fetched_at=body.generated_at;}));
const browser=await chromium.launch({args:['--enable-unsafe-swiftshader']});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
async function initialize(page,live=false){
  await page.route('**/*',route=>['127.0.0.1','localhost'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
  if(!live){await page.route('**/api/v1/health/',route=>route.fulfill({json:{status:'ok',version:'synthetic',check:'liveness'}}));await page.route('**/api/v1/route-analysis/',route=>route.fulfill({json:body}));}
  await page.addInitScript(()=>{localStorage.setItem('routeshield-theme','light');sessionStorage.removeItem('routeshield-results-view');});
  await page.goto('http://127.0.0.1:5173/');await page.waitForFunction(()=>!!window.__routeShieldMap);
}
async function capture(page,name,locator){await page.evaluate(()=>document.fonts.ready);if(locator)await locator.evaluate(node=>{const scroll=node.closest('.results-scroll');if(scroll){scroll.scrollTop+=node.getBoundingClientRect().top-scroll.getBoundingClientRect().top-16;scroll.scrollLeft=0;}});await page.waitForTimeout(450);await page.screenshot({path:resolve(output,`${name}.png`),animations:'disabled'});}
async function checkpoint(page,index){const chart=page.getByRole('slider');await chart.scrollIntoViewIfNeeded();await chart.focus();await chart.press('Home');for(let i=0;i<index;i++)await chart.press('ArrowRight');await chart.press('Enter');await page.waitForTimeout(450);}
try{
  if(process.env.ROUTESHIELD_CHECKPOINT_LIVE_ONLY!=='1'){
    const page=await context.newPage();await initialize(page);await page.getByRole('button',{name:'Chicago, IL to Detroit, MI'}).click();await page.getByRole('button',{name:'Analyze routes',exact:true}).click();await page.getByRole('radio',{name:/Route 3 /}).click();await page.getByRole('radio',{name:'Profile',exact:true}).click();
    for(const theme of ['light','dark']){await page.getByRole('radio',{name:theme==='light'?'Light theme':'Dark theme',exact:true}).click();for(const variable of ['Wind','Rain','Snow']){await page.getByRole('radio',{name:variable,exact:true}).click();await page.locator('.risk-profile').scrollIntoViewIfNeeded();await capture(page,`profile-${theme}-${variable.toLowerCase()}`);}}
    await page.getByRole('radio',{name:'Light theme',exact:true}).click();await page.getByRole('radio',{name:'Wind',exact:true}).click();
    for(const [index,name]of[[2,'inspector-high'],[4,'inspector-load-no-travel'],[5,'inspector-unknown-block'],[6,'inspector-unknown-unblocked'],...['OUT_OF_HORIZON','MISSING_HOUR','MISSING_FIELD','PAST_TIME','PROVIDER_FAILURE','QUOTA_EXCEEDED','DEMO_QUOTA_REACHED'].map((code,i)=>[i+7,`unavailable-${code.toLowerCase()}`])]){await checkpoint(page,index);await capture(page,name,page.locator('.checkpoint-inspector'));if(index===2||index===4)await capture(page,`${name}-rules`,page.locator('.rules-heading'));}
    await checkpoint(page,4);await page.getByRole('radio',{name:'Compare',exact:true}).click();await capture(page,'dock-desktop');await page.getByRole('button',{name:/Details/}).click();await capture(page,'dock-expanded');await page.getByRole('button',{name:/Details/}).click();await page.getByRole('radio',{name:'Profile',exact:true}).click();await page.getByRole('slider').scrollIntoViewIfNeeded();const rect=await page.getByRole('slider').boundingBox();await page.mouse.move(rect.x+rect.width*.52,rect.y+rect.height*.4);await capture(page,'crosshair-hover');await page.getByRole('slider').focus();await page.keyboard.press('Home');await page.keyboard.press('ArrowRight');await capture(page,'chart-keyboard-focus');await page.locator('.results-scroll').evaluate(node=>{node.scrollTop=0;});await capture(page,'subnavigation-blocked');
    await page.setViewportSize({width:320,height:844});await page.locator('.sheet-handle').press('Home');await page.getByRole('slider').scrollIntoViewIfNeeded();await capture(page,'profile-320px');await page.getByRole('radio',{name:'Compare',exact:true}).click();await page.locator('.sheet-handle').press('End');await page.locator('.sheet-handle').press('ArrowUp');await page.waitForTimeout(250);await capture(page,'dock-mobile-half');
    await page.setViewportSize({width:640,height:480});await page.locator('.sheet-handle').press('Home');await page.getByRole('radio',{name:'Profile',exact:true}).click();await page.getByRole('slider').scrollIntoViewIfNeeded();await capture(page,'profile-reflow-200-percent');await page.close();
  }
  if(process.env.ROUTESHIELD_REAL_CHECKPOINTS==='1'){
    const file=resolve(output,'live-budget.json');let sends=0;try{sends=JSON.parse(await readFile(file,'utf8')).analysisSends;if(!Number.isInteger(sends)||sends<0||sends>1)throw new Error('Invalid live budget');}catch(error){if(error.code!=='ENOENT')throw error;}
    if(sends>=1)throw new Error('One live analysis already sent; no retry authorized.');
    const live=await context.newPage();await initialize(live,true);await live.route('**/api/v1/route-analysis/',async route=>{if(sends>=1)return route.abort();sends++;await writeFile(file,JSON.stringify({analysisSends:sends}));await route.continue();});
    await live.waitForFunction(()=>document.querySelector('.header-service')?.textContent?.includes('API healthy'),null,{timeout:10000});
    await live.getByRole('button',{name:'Santa Monica Pier to Los Angeles City Hall'}).click();await live.getByRole('button',{name:'In 3 hours'}).click();const started=Date.now(),pending=live.waitForResponse(r=>r.url().endsWith('/route-analysis/')&&r.request().method()==='POST',{timeout:40000});await live.getByRole('button',{name:'Analyze routes',exact:true}).click();const http=await pending,wallMs=Date.now()-started;
    if(http.status()===200){const result=await http.json();console.log(JSON.stringify({http:200,routeCount:result.route_count,status:result.recommendation_status,wallMs,providerCalls:result.metadata.provider_calls,backendMs:result.metadata.total_ms}));await live.getByRole('radio',{name:'Profile',exact:true}).click();await live.getByRole('slider').scrollIntoViewIfNeeded();await capture(live,'real-santa-monica-profile');await capture(live,'real-santa-monica-inspector',live.locator('.checkpoint-inspector'));}else console.log(JSON.stringify({http:http.status(),wallMs}));
    await live.close();
  }
  console.log('Checkpoint screenshots saved. No real API response recordings.');
}finally{await context.close();await browser.close();}
