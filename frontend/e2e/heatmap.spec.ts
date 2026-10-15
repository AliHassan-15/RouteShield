import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { heatFixture } from '../src/features/heatmap/fixtures';
import { decodeAnalysis } from '../src/features/heatmap/decoder';
import { weightsAt, weightHash } from '../src/features/heatmap/presentation';
declare global {
  interface Window {
    __routeShieldHeat: { inspect(): { hour: number; filter: string; transitioning: boolean; hash: string; targetHash: string; bytes: number; decodeMs: number; writes: number; path: string; truck: number[] | undefined; pointCount: number }; benchmark(): Promise<Record<string, { medianMs: number; p95Ms: number; syncMedianMs: number }>> };
    __routeShieldHeatStore: { hour(h: number): void; update(patch: { playing?: boolean; speed?: number; loop?: boolean }): void; tick(): void; inspect(): { hour: number; playing: boolean; speed: number; loop: boolean } };
    __heatLoops: number;
    __routeShieldConsoleCommits: number;
  }
}
test.use({ trace: 'off', headless: process.env.HEAT_HARDWARE !== '1', launchOptions: { args: process.env.HEAT_HARDWARE === '1' ? ['--enable-gpu', '--use-angle=d3d11', '--enable-precise-memory-info'] : ['--enable-unsafe-swiftshader', '--enable-precise-memory-info'] } });
const output = resolve(process.cwd(), '../output/playwright/heatmap');
async function init(page: Page) {
  await page.route('**/*', route => ['127.0.0.1', 'localhost'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
  await page.route('**/api/v1/health/', route => route.fulfill({ json: { status: 'ok', version: 'synthetic', check: 'liveness' } }));
  await page.addInitScript(() => { localStorage.setItem('routeshield-theme', 'light'); window.__webglContexts = 0; const original = HTMLCanvasElement.prototype.getContext, seen = new WeakSet<HTMLCanvasElement>(); HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, ...args: Parameters<typeof original>) { const c = original.apply(this, args); if (c && String(args[0]).startsWith('webgl') && !seen.has(this)) { seen.add(this); window.__webglContexts++; } return c; } as typeof original; });
  await page.setViewportSize({ width: 1440, height: 1000 }); await page.goto('/'); await expect(page.locator('.header-service')).toContainText('healthy'); await page.waitForFunction(() => !!window.__routeShieldMap);
  await page.getByRole('button', { name: 'Chicago, IL to Detroit, MI' }).click();
}
async function analyze(page: Page, fixture = heatFixture()) {
  await page.unroute('**/api/v1/route-analysis/'); fixture.analysis_id = `synthetic-heat-${Date.now()}`; fixture.generated_at = new Date().toISOString(); fixture.expires_at = new Date(Date.now() + 900000).toISOString();
  await page.route('**/api/v1/route-analysis/', route => route.fulfill({ json: fixture }));
  await page.getByRole('tab', { name: 'Trip', exact: true }).click(); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click();
  await expect(page.getByRole('slider', { name: 'Forecast hour' })).toBeVisible(); await page.waitForFunction(() => window.__routeShieldHeat?.inspect()?.pointCount > 0); await page.waitForTimeout(1700);
}
test('cached keyboard and pointer scrub changes categorical weights with zero requests', async ({ page }) => {
  test.setTimeout(120000); await init(page); const fixture = heatFixture(); await analyze(page, fixture); const decoded = decodeAnalysis(fixture); if (decoded.kind !== 'ready') throw Error();
  const commits = await page.evaluate(() => window.__routeShieldConsoleCommits);
  const requests: string[] = []; page.on('request', r => { const u = new URL(r.url()); requests.push(u.protocol + ' ' + (u.protocol === 'blob:' ? 'in-memory-source' : u.pathname)); }); const hashes: string[] = [], slider = page.getByRole('slider', { name: 'Forecast hour' });
  for (const hour of [0, 12, 24, 48]) { await slider.focus(); await slider.press('Home'); for (let h = 0; h < hour; h += 6) await slider.press('PageUp'); await page.waitForFunction(() => !window.__routeShieldHeat.inspect().transitioning); const value = await page.evaluate(() => window.__routeShieldHeat.inspect()); expect(value.hash).toBe(weightHash(weightsAt(decoded.data, hour, 'combined'))); hashes.push(value.hash); }
  expect(new Set(hashes).size).toBe(4); const box = (await slider.boundingBox())!; await page.mouse.move(box.x, box.y + 22); await page.mouse.down(); await page.mouse.move(box.x + box.width, box.y + 22, { steps: 48 }); await page.mouse.up(); await page.waitForTimeout(250); console.log(JSON.stringify({ requestClasses: Object.fromEntries([...new Set(requests)].map(k => [k, requests.filter(v => v === k).length])) })); expect(requests).toEqual([]); expect(await page.evaluate(() => window.__routeShieldConsoleCommits)).toBe(commits);
});
test('calm and stormy draw, preserve hour/filter/truck across theme and style replacement', async ({ page }) => {
  test.setTimeout(120000); const errors: string[] = []; page.on('pageerror', e => errors.push(e.message)); page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); }); await init(page); await analyze(page, heatFixture('calm'));
  await page.getByRole('button', { name: 'Options +' }).click(); await page.getByRole('button', { name: 'Wind', exact: true }).click(); await page.evaluate(() => window.__routeShieldHeatStore.hour(12)); await page.waitForFunction(() => !window.__routeShieldHeat.inspect().transitioning); const before = await page.evaluate(() => window.__routeShieldHeat.inspect());
  await page.getByRole('radio', { name: 'Dark theme', exact: true }).click(); await page.waitForTimeout(250); const after = await page.evaluate(() => window.__routeShieldHeat.inspect()); expect(after.hour).toBe(12); expect(after.filter).toBe('wind'); expect(after.truck).toEqual(before.truck);
  await page.evaluate(() => window.__routeShieldMap.replaceStyle()); await page.waitForTimeout(400); expect(await page.evaluate(() => window.__routeShieldMap.inspect().layers)).toBe(24);
  const colors = await page.locator('.map-engine-host canvas').evaluate(canvas => { const copy = document.createElement('canvas'); copy.width = (canvas as HTMLCanvasElement).width; copy.height = (canvas as HTMLCanvasElement).height; const c = copy.getContext('2d')!; c.drawImage(canvas as HTMLCanvasElement, 0, 0); const pixels = c.getImageData(0, 0, copy.width, copy.height).data, values = new Set(); for (let i = 0; i < pixels.length; i += 160) values.add(`${pixels[i]},${pixels[i + 1]},${pixels[i + 2]}`); return values.size; }); expect(colors).toBeGreaterThan(8);
  await analyze(page); expect(await page.evaluate(() => window.__routeShieldMap.inspect().sources)).toBe(4); expect(errors).toEqual([]);
});
test('worst-case updates, ten replacements and 200 accelerated full playback loops stay bounded', async ({ page }) => {
  test.setTimeout(1800000); await init(page); await analyze(page, heatFixture('worst')); const cdp = await page.context().newCDPSession(page); await cdp.send('HeapProfiler.collectGarbage');
  const baseline = { ...await cdp.send('Memory.getDOMCounters'), ...await cdp.send('Runtime.getHeapUsage') };
  for (let i = 1; i < 10; i++) await analyze(page, heatFixture('worst'));
  const paths = await page.evaluate(() => window.__routeShieldHeat.benchmark());
  await page.evaluate(() => { window.__heatLoops = 0; window.__routeShieldHeatStore.hour(0); window.__routeShieldHeatStore.update({ speed: 4, loop: true, playing: true }); });
  const started = Date.now();
  // Stress every discrete playback frame, accelerating only the between-step wait.
  // The ordinary timer continues at 4x; rAF is never mocked or replaced.
  await page.evaluate(async () => { let previous = 0; while (window.__heatLoops < 200) { await new Promise<void>(resolve => requestAnimationFrame(() => resolve())); window.__routeShieldHeatStore.tick(); const hour = window.__routeShieldHeatStore.inspect().hour; if (hour < previous) window.__heatLoops++; previous = hour; } window.__routeShieldHeatStore.update({ playing: false }); });
  await cdp.send('HeapProfiler.collectGarbage'); const final = { ...await cdp.send('Memory.getDOMCounters'), ...await cdp.send('Runtime.getHeapUsage') }, loops = await page.evaluate(() => window.__heatLoops), heat = await page.evaluate(() => window.__routeShieldHeat.inspect());
  expect(await page.evaluate(() => window.__webglContexts)).toBe(1); expect(final.nodes).toBeLessThanOrEqual(baseline.nodes + 50); expect(final.jsEventListeners).toBeLessThanOrEqual(baseline.jsEventListeners + 50); expect(final.usedSize).toBeLessThan(baseline.usedSize * 1.8);
  await mkdir(output, { recursive: true }); await writeFile(resolve(output, 'loops.json'), JSON.stringify({ baseline, final, paths, heat, loops, wallMs: Date.now() - started, acceleratedBetweenStepWait: true }, null, 2));
});
