import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { mapFixture } from '../src/features/map/fixtures';
import type { Position } from '../src/api/types';

declare global { interface Window { __routeShieldMap: { inspect(): { selectedRouteId: string | null; selectedCheckpointIndex: number | null; layers: number; sources: number; rendered: number; vertices: number[]; applyMs: number; prepareMs: number; drawStartedAt: number; dataWrites: number; center: number[] }; project(p: Position): { x: number; y: number }; select(id: string): void; replaceStyle(): void }; __webglContexts: number; __mapFrames: { at: number; interval: number }[]; __mapTasks: { start: number; duration: number }[] } }
test.use({ trace: 'off', launchOptions: { args: ['--enable-unsafe-swiftshader', '--enable-precise-memory-info'] } });
const output = resolve(process.cwd(), '../output/playwright/map');
async function initialize(page: Page) {
  await page.route('**/*', route => ['127.0.0.1', 'localhost'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
  await page.route('**/api/v1/health/', route => route.fulfill({ json: { status: 'ok', version: 'synthetic', check: 'liveness' } }));
  await page.addInitScript(() => {
    localStorage.setItem('routeshield-theme', 'light'); window.__webglContexts = 0;
    const original = HTMLCanvasElement.prototype.getContext, seen = new WeakSet<HTMLCanvasElement>();
    HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, ...args: Parameters<typeof original>) { const context = original.apply(this, args); if (context && String(args[0]).startsWith('webgl') && !seen.has(this)) { seen.add(this); window.__webglContexts++; } return context; } as typeof original;
  });
  await page.setViewportSize({ width: 1440, height: 1000 }); await page.goto('/');
  await expect(page.locator('.header-service')).toContainText('healthy'); await page.waitForFunction(() => !!window.__routeShieldMap);
  await page.getByRole('button', { name: 'Chicago, IL to Detroit, MI' }).click();
}
async function analyze(page: Page, fixture = mapFixture()) {
  await page.unroute('**/api/v1/route-analysis/'); fixture.analysis_id = `synthetic-map-${Date.now()}`; fixture.generated_at = new Date().toISOString(); fixture.expires_at = new Date(Date.now() + 900000).toISOString();
  await page.route('**/api/v1/route-analysis/', route => route.fulfill({ json: fixture }));
  await page.getByRole('tab', { name: 'Trip', exact: true }).click(); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click();
  await page.waitForFunction(id => window.__routeShieldMap.inspect().selectedRouteId === id, fixture.recommended_route_id);
  await page.waitForTimeout(1150);
}
test('offline canvas renders three routes and debug feature counts', async ({ page }) => {
  await initialize(page); await analyze(page); const data = await page.evaluate(() => window.__routeShieldMap.inspect()); expect(data.layers).toBe(16); expect(data.sources).toBe(3); expect(data.rendered).toBeGreaterThan(3);
  const colors = await page.locator('.map-engine-host canvas').evaluate(canvas => { const c = document.createElement('canvas'); c.width = (canvas as HTMLCanvasElement).width; c.height = (canvas as HTMLCanvasElement).height; const ctx = c.getContext('2d')!; ctx.drawImage(canvas as HTMLCanvasElement, 0, 0); const pixels = ctx.getImageData(0, 0, c.width, c.height).data, distinct = new Set<string>(); for (let i = 0; i < pixels.length; i += 100) distinct.add(`${pixels[i]},${pixels[i + 1]},${pixels[i + 2]}`); return distinct.size; }); expect(colors).toBeGreaterThan(8);
  await mkdir(output, { recursive: true }); await page.screenshot({ path: resolve(output, 'offline-render.png') }); await writeFile(resolve(output, 'synthetic.json'), JSON.stringify(mapFixture(true))); await writeFile(resolve(output, 'synthetic-overlap.json'), JSON.stringify(mapFixture(true, 180, true)));
  const overlap = mapFixture(false, 180, true); await analyze(page, overlap); const pixel = await page.evaluate(p => window.__routeShieldMap.project(p), overlap.routes[0]!.geometry[90]!); const box = (await page.locator('.map-engine-host').boundingBox())!; await page.mouse.click(box.x + pixel.x, box.y + pixel.y + 7); await expect.poll(() => page.evaluate(() => window.__routeShieldMap.inspect().selectedRouteId)).not.toBe(overlap.routes[0]!.route_id);
});
test('card, route, checkpoint, keyboard and list selection synchronize without hover data writes', async ({ page }) => {
  await initialize(page); const fixture = mapFixture(); await analyze(page, fixture);
  await page.getByRole('radio', { name: /Route 2/ }).click(); await page.waitForFunction(id => window.__routeShieldMap.inspect().selectedRouteId === id, fixture.routes[1]!.route_id); await page.waitForTimeout(1000);
  const point = await page.evaluate(p => window.__routeShieldMap.project(p), fixture.routes[1]!.checkpoints[2]!.coordinate); const box = (await page.locator('.map-engine-host').boundingBox())!;
  await page.mouse.click(box.x + point.x, box.y + point.y); await page.waitForFunction(() => window.__routeShieldMap.inspect().selectedCheckpointIndex === 2);
  await expect(page.locator('[data-checkpoint="2"]')).toHaveAttribute('aria-pressed', 'true'); await expect(page.locator('.map-checkpoint-tooltip')).toBeVisible();
  const writes = await page.evaluate(() => window.__routeShieldMap.inspect().dataWrites); await page.mouse.move(box.x + point.x, box.y + point.y); await page.waitForTimeout(100); expect(await page.evaluate(() => window.__routeShieldMap.inspect().dataWrites)).toBe(writes);
  await page.locator('.map-engine-host canvas').focus(); await page.keyboard.press(']'); await expect(page.locator('[data-checkpoint="3"]')).toHaveAttribute('aria-pressed', 'true'); await page.keyboard.press('Escape'); await expect(page.locator('.map-checkpoint-tooltip')).toBeHidden();
});
test('theme and fullscreen preserve overlays, selection and camera without console errors', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.name)); page.on('console', m => { if (m.type() === 'error' || m.text().includes('cannot fit within canvas')) errors.push(m.text()); }); await initialize(page); await analyze(page);
  const initial = await page.evaluate(() => window.__routeShieldMap.inspect()); await page.getByRole('radio', { name: 'Dark theme', exact: true }).click(); await page.waitForTimeout(300);
  const dark = await page.evaluate(() => window.__routeShieldMap.inspect()); expect(dark.selectedRouteId).toBe(initial.selectedRouteId); expect(dark.layers).toBe(initial.layers); expect(dark.center).toEqual(initial.center); expect(dark.dataWrites).toBe(initial.dataWrites);
  await page.evaluate(() => { window.__routeShieldMap.replaceStyle(); const id = window.__routeShieldMap.inspect().selectedRouteId; if (id) window.__routeShieldMap.select(id); }); await page.waitForFunction(() => window.__routeShieldMap.inspect().layers === 16);
  const full = page.getByRole('button', { name: 'Fullscreen map', exact: true }); if (await full.count()) { await full.click(); await expect(page.getByRole('button', { name: 'Exit fullscreen map' })).toBeVisible(); await page.getByRole('button', { name: 'Exit fullscreen map' }).click(); }
  await page.setViewportSize({ width: 320, height: 844 }); await page.waitForTimeout(200); await page.locator('.sheet-handle').press('Home'); await expect(page.locator('.bottom-sheet')).toHaveAttribute('data-snap', 'full'); await page.getByRole('button', { name: 'Recenter routes' }).click(); await page.waitForTimeout(1100);
  const origin = await page.evaluate(p => window.__routeShieldMap.project(p), mapFixture().routes[0]!.geometry[0]!); const host = (await page.locator('.map-engine-host').boundingBox())!, sheet = (await page.locator('.bottom-sheet').boundingBox())!; expect(origin.x).toBeGreaterThanOrEqual(20); expect(origin.x).toBeLessThanOrEqual(252); expect(origin.y).toBeGreaterThanOrEqual(70); expect(origin.y).toBeLessThan(sheet.y - host.y - 18);
  await page.locator('.sheet-handle').press('End'); const skip = page.getByRole('link', { name: 'Skip map', exact: true }); await skip.focus(); await skip.press('Enter'); await expect(page.locator('.bottom-sheet')).toHaveAttribute('data-snap', 'full');
  await page.locator('.map-credit-strip summary').click(); await expect.poll(async () => { const sheet = (await page.locator('.bottom-sheet').boundingBox())!, footer = (await page.locator('.map-credit-strip').boundingBox())!; return sheet.y + sheet.height - footer.y; }).toBeLessThanOrEqual(1); await page.locator('.map-credit-strip summary').click();
  expect(errors).toEqual([]);
});
test('ten analyses retain one WebGL context and bounded memory, DOM and listeners', async ({ page }) => {
  test.setTimeout(90000); await initialize(page); const session = await page.context().newCDPSession(page);
  await page.evaluate(() => { window.__mapTasks = []; window.__mapFrames = []; new PerformanceObserver(list => list.getEntries().forEach(e => window.__mapTasks.push({ start: e.startTime, duration: e.duration }))).observe({ type: 'longtask' }); const start = performance.now(); let last: number | undefined; const frame = (now: number) => { if (last !== undefined) window.__mapFrames.push({ at: now, interval: now - last }); last = now; if (now - start < 1800) requestAnimationFrame(frame); }; requestAnimationFrame(frame); });
  await analyze(page, mapFixture(false, 38000)); await session.send('HeapProfiler.collectGarbage');
  const baseline = { ...await session.send('Memory.getDOMCounters'), ...await session.send('Runtime.getHeapUsage'), ...await page.evaluate(() => ({ contexts: window.__webglContexts, map: window.__routeShieldMap.inspect() })) };
  for (let i = 1; i < 10; i++) await analyze(page, mapFixture(false, 38000));
  await session.send('HeapProfiler.collectGarbage'); const final = { ...await session.send('Memory.getDOMCounters'), ...await session.send('Runtime.getHeapUsage'), ...await page.evaluate(() => ({ contexts: window.__webglContexts, map: window.__routeShieldMap.inspect() })) };
  const metrics = await page.evaluate(start => ({ tasks: window.__mapTasks.filter(t => t.start < start + 900 && t.start + t.duration >= start).map(t => t.duration), frames: window.__mapFrames.filter(f => f.at >= start && f.at - f.interval <= start + 900).map(f => f.interval), windowMs: 900, hardwareConcurrency: navigator.hardwareConcurrency, userAgent: navigator.userAgent }), baseline.map.drawStartedAt);
  expect(final.contexts).toBe(1); expect(final.nodes).toBeLessThanOrEqual(baseline.nodes + 30); expect(final.jsEventListeners).toBeLessThanOrEqual(baseline.jsEventListeners + 30); expect(final.usedSize).toBeLessThanOrEqual(baseline.usedSize * 1.5);
  console.log(JSON.stringify({ baseline, final, performance: metrics })); await mkdir(output, { recursive: true }); await writeFile(resolve(output, 'performance.json'), JSON.stringify({ baseline, final, performance: metrics }, null, 2));
});
