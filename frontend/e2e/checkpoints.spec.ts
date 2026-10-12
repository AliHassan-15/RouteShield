import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { checkpointFixture } from '../src/features/checkpoints/fixtures';
test.use({ trace: 'off', launchOptions: { args: ['--enable-unsafe-swiftshader'] } });
const output = resolve(process.cwd(), '../output/playwright/checkpoints');
async function initialize(page: Page) {
  await page.route('**/*', route => ['127.0.0.1','localhost'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
  await page.route('**/api/v1/health/',route=>route.fulfill({json:{status:'ok',version:'synthetic',check:'liveness'}}));
  const body=checkpointFixture(); body.generated_at=new Date().toISOString(); body.expires_at=new Date(Date.now()+900000).toISOString(); body.routes.forEach(r=>r.checkpoints.forEach(cp=>{cp.weather.fetched_at=body.generated_at;}));
  await page.route('**/api/v1/route-analysis/',route=>route.fulfill({json:body}));
  await page.addInitScript(()=>{localStorage.setItem('routeshield-theme','light');sessionStorage.removeItem('routeshield-results-view');});
  await page.setViewportSize({width:1440,height:1000}); await page.goto('/'); await page.waitForFunction(()=>!!window.__routeShieldMap);
  await page.getByRole('button',{name:'Chicago, IL to Detroit, MI'}).click(); await page.getByRole('button',{name:'Analyze routes',exact:true}).click();
  await page.waitForFunction(()=>window.__routeShieldMap.inspect().selectedRouteId!==null); await page.getByRole('radio',{name:/Route 3 /}).click(); await page.waitForTimeout(1100);
  await mkdir(output,{recursive:true}); await writeFile(resolve(output,'synthetic.json'),JSON.stringify(body)); return body;
}
test('profile keyboard selects inspector, dock, map and list without errors or extra requests',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.name));page.on('console',m=>{if(m.type()==='error')errors.push('console error');});let analyses=0;page.on('request',r=>{if(r.url().endsWith('/route-analysis/'))analyses++;});
  const body=await initialize(page); await page.getByRole('radio',{name:'Profile',exact:true}).click(); const chart=page.getByRole('slider',{name:'Wind checkpoint profile'});await chart.focus();await chart.press('Home');await chart.press('ArrowRight');await chart.press('ArrowRight');await chart.press('Enter');
  await expect(page.getByRole('region',{name:'Checkpoint inspector'})).toContainText('Checkpoint 3 of 14');await expect.poll(()=>page.evaluate(()=>window.__routeShieldMap.inspect().selectedCheckpointIndex)).toBe(2);
  const center=await page.evaluate(()=>window.__routeShieldMap.inspect().center);await chart.press('ArrowRight');await chart.press('Enter');await page.waitForTimeout(500);expect(await page.evaluate(()=>window.__routeShieldMap.inspect().center)).toEqual(center);
  await page.getByRole('button',{name:'Zoom in',exact:true}).click();await page.getByRole('button',{name:'Zoom in',exact:true}).click();await page.waitForTimeout(400);const zoom=await page.evaluate(()=>(window.__routeShieldMap.inspect() as unknown as {zoom:number}).zoom);await chart.press('End');await chart.press('Enter');await page.waitForTimeout(500);expect(await page.evaluate(()=>(window.__routeShieldMap.inspect() as unknown as {zoom:number}).zoom)).toBeCloseTo(zoom,5);const point=await page.evaluate(p=>window.__routeShieldMap.project(p),body.routes[0]!.checkpoints[13]!.coordinate);expect(point.x).toBeGreaterThan(444);expect(point.x).toBeLessThan(1400);await chart.press('Home');await chart.press('ArrowRight');await chart.press('ArrowRight');await chart.press('ArrowRight');await chart.press('Enter');
  await chart.press('ArrowRight');await chart.press('Enter');await expect(page.getByText('Load rule applied')).toBeVisible();await chart.press('ArrowRight');await chart.press('Enter');await expect(page.getByText(/Known No Travel evidence present/)).toBeVisible();
  await page.getByRole('radio',{name:'Compare',exact:true}).click();await expect(page.getByRole('complementary',{name:'Selected checkpoint dock'})).toContainText('Mile 50.0');await page.getByRole('radio',{name:'Checkpoints',exact:true}).click();await expect(page.locator('[data-checkpoint="5"]')).toHaveAttribute('aria-pressed','true');
  await page.getByRole('button',{name:'Next checkpoint'}).click();await expect.poll(()=>page.evaluate(()=>window.__routeShieldMap.inspect().selectedCheckpointIndex)).toBe(6);expect(analyses).toBe(1);expect(errors).toEqual([]);expect(body.routes[0]!.summary.known_blocked).toBe(true);
  await page.setViewportSize({width:320,height:844});await page.locator('.sheet-handle').press('End');await page.locator('.sheet-handle').press('ArrowUp');await page.waitForTimeout(250);const control=await page.getByRole('button',{name:'Next checkpoint'}).boundingBox(),footer=await page.locator('.map-credit-strip').boundingBox();expect(control!.y+control!.height).toBeLessThanOrEqual(footer!.y+1);await page.screenshot({path:resolve(output,'dock-mobile-half.png')});
});
test('route/theme switching preserves Profile and renders a nonblank chart at narrow width',async({page})=>{
  await initialize(page);await page.getByRole('radio',{name:'Profile',exact:true}).click();await expect(page.getByRole('slider')).toBeVisible();const route=page.getByLabel('Inspected route');await route.selectOption('synthetic-route-1');await expect.poll(()=>page.evaluate(()=>window.__routeShieldMap.inspect().selectedRouteId)).toBe('synthetic-route-1');await expect(page.getByRole('radio',{name:'Profile',exact:true})).toHaveAttribute('aria-checked','true');
  await page.getByRole('radio',{name:'Dark theme',exact:true}).click();await page.getByRole('radio',{name:'Rain',exact:true}).click();await expect(page.locator('.profile-trace')).toHaveAttribute('d',/M\d/);expect(await page.locator('.profile-plot > svg').evaluate(node=>node.querySelectorAll('path,text').length)).toBeGreaterThan(10);
  await route.selectOption('synthetic-route-0');await page.getByRole('slider').press('Home');await page.getByRole('slider').press('ArrowRight');await page.getByRole('slider').press('Enter');
  await page.setViewportSize({width:320,height:844});await page.locator('.sheet-handle').press('Home');await page.getByRole('slider').scrollIntoViewIfNeeded();expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);await expect.poll(()=>page.evaluate(()=>window.__routeShieldMap.inspect().selectedRouteId)).toBe('synthetic-route-0');await expect.poll(()=>page.evaluate(()=>window.__routeShieldMap.inspect().selectedCheckpointIndex)).toBe(1);await page.getByRole('slider').press('End');await page.getByRole('slider').press('Enter');await expect(page.getByRole('region',{name:'Checkpoint inspector'})).toContainText('Checkpoint 14 of 14');await page.screenshot({path:resolve(output,'browser-narrow.png')});
});
