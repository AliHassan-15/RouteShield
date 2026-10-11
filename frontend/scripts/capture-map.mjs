// Manual visual verification only. Real basemap allowed; synthetic API bodies
// come from the typed offline tests. Live responses stay in memory, never files.
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
const output = resolve(process.cwd(), '../output/playwright/map');
process.env.PLAYWRIGHT_BROWSERS_PATH ??= resolve(process.cwd(), '../.cache/ms-playwright');
const { chromium } = await import('@playwright/test');
await mkdir(output, { recursive: true });
const fixture = JSON.parse(await readFile(resolve(output, 'synthetic.json'), 'utf8'));
const overlap = JSON.parse(await readFile(resolve(output, 'synthetic-overlap.json'), 'utf8'));
const browser = await chromium.launch({ args: ['--enable-unsafe-swiftshader', '--enable-precise-memory-info'] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
async function initialize(page, live = false) {
  await page.route('**/*', route => ['127.0.0.1', 'localhost', 'tiles.openfreemap.org', 'openfreemap.org'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
  if (!live) await page.route('**/api/v1/health/', route => route.fulfill({ json: { status: 'ok', version: 'synthetic', check: 'liveness' } }));
  await page.addInitScript(() => localStorage.setItem('routeshield-theme', 'light'));
  await page.goto('http://127.0.0.1:5173/'); await page.waitForFunction(() => !!window.__routeShieldMap);
  await page.waitForTimeout(1800);
}
async function capture(page, name) { if (name !== 'webgl-unavailable') await page.waitForFunction(() => window.__routeShieldMap?.inspect().basemapReady, null, { timeout: 25000 }); await page.evaluate(() => document.fonts.ready); await page.waitForTimeout(1000); await page.screenshot({ path: resolve(output, `${name}.png`), animations: 'disabled' }); }
async function analyze(page, body) {
  await page.unroute('**/api/v1/route-analysis/'); body.analysis_id = `synthetic-map-visual-${Date.now()}`; body.generated_at = new Date().toISOString(); body.expires_at = new Date(Date.now() + 900000).toISOString();
  body.routes.forEach(r => r.checkpoints.forEach(c => { c.weather.fetched_at = body.generated_at; }));
  await page.route('**/api/v1/route-analysis/', route => route.fulfill({ json: body }));
  if (await page.locator('.sheet-handle').count()) await page.locator('.sheet-handle').press('Home');
  await page.getByRole('tab', { name: 'Trip', exact: true }).click(); await page.getByRole('button', { name: 'Chicago, IL to Detroit, MI' }).click(); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click();
  await page.waitForTimeout(1200); await page.evaluate(id => window.__routeShieldMap.select(id), body.routes[0].route_id); await page.waitForTimeout(1100);
}
try {
  if (process.env.ROUTESHIELD_LIVE_ONLY !== 'santa-monica') {
    const page = await context.newPage(); await initialize(page); await capture(page, 'empty');
    await analyze(page, structuredClone(fixture)); await capture(page, 'desktop-light-six-shapes');
    await page.getByRole('radio', { name: 'Dark theme' }).click(); await capture(page, 'desktop-dark-six-shapes');
    await page.getByRole('radio', { name: /Route 1 / }).click(); await capture(page, 'route-selection');
    await page.evaluate(id => window.__routeShieldMap.select(id), fixture.routes[0].route_id); await page.waitForTimeout(1000); await page.locator('.map-engine-host canvas').focus(); await page.keyboard.press(']'); await page.keyboard.press(']'); await capture(page, 'checkpoint-tooltip'); await page.keyboard.press('Escape');
    await page.getByRole('radio', { name: 'Light theme' }).click(); await analyze(page, structuredClone(overlap)); await capture(page, 'overlapping-routes');
    for (let i = 0; i < 3; i++) await page.getByRole('button', { name: 'Zoom out', exact: true }).click(); await capture(page, 'declutter-low-zoom');
    for (let i = 0; i < 5; i++) await page.getByRole('button', { name: 'Zoom in', exact: true }).click(); await capture(page, 'declutter-high-zoom'); await page.getByRole('button', { name: 'Recenter routes' }).click();
    await capture(page, 'legend-expanded');
    if (await page.getByRole('button', { name: 'Fullscreen map', exact: true }).count()) { await page.getByRole('button', { name: 'Fullscreen map', exact: true }).click(); await capture(page, 'fullscreen'); await page.getByRole('button', { name: 'Exit fullscreen map' }).click(); }
    const mobile = await context.newPage(); await mobile.setViewportSize({ width: 320, height: 844 }); await initialize(mobile); await analyze(mobile, structuredClone(fixture));
    for (const [key, name] of [['End', 'mobile-peek'], ['ArrowUp', 'mobile-half'], ['Home', 'mobile-full']]) { await mobile.locator('.sheet-handle').press(key); await mobile.waitForTimeout(120); await mobile.getByRole('button', { name: 'Recenter routes' }).click(); await capture(mobile, name); }
    await mobile.locator('.sheet-handle').press('End'); await mobile.locator('.map-credit-strip summary').click(); await mobile.waitForTimeout(250); await capture(mobile, 'mobile-credits');
    await mobile.close();
    const unavailable = await context.newPage(); await unavailable.addInitScript(() => { const original = HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext = function (type, ...args) { return type.startsWith('webgl') ? null : original.call(this, type, ...args); }; }); await unavailable.route('**/*', route => ['127.0.0.1', 'localhost'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort()); await unavailable.route('**/api/v1/health/', route => route.fulfill({ json: { status: 'ok', version: 'synthetic', check: 'liveness' } })); await unavailable.goto('http://127.0.0.1:5173/'); await unavailable.getByRole('heading', { name: 'Map unavailable' }).waitFor(); await capture(unavailable, 'webgl-unavailable'); await unavailable.close();
    const skeleton = await context.newPage(); await skeleton.route('**/src/features/map/maplibre-engine.ts*', async route => { await new Promise(resolve => setTimeout(resolve, 2500)); await route.continue(); }); await skeleton.route('**/api/v1/health/', route => route.fulfill({ json: { status: 'ok', version: 'synthetic', check: 'liveness' } })); await skeleton.goto('http://127.0.0.1:5173/'); await skeleton.getByText('Preparing map', { exact: true }).waitFor(); await skeleton.screenshot({ path: resolve(output, 'skeleton.png') }); await skeleton.close();
  }
  if (process.env.ROUTESHIELD_REAL_MAP === '1') {
    const live = await context.newPage(); await initialize(live, true);
    const budgetFile = resolve(output, 'live-budget.json');
    let sends = 0; try { sends = JSON.parse(await readFile(budgetFile, 'utf8')).analysisSends; } catch { /* First run. */ }
    await live.route('**/api/v1/route-analysis/', async route => {
      if (sends >= 2) return route.abort(); sends++;
      await writeFile(budgetFile, JSON.stringify({ analysisSends: sends })); await route.continue();
    });
    for (const [name, chip, theme] of [['real-chicago-detroit', 'Chicago, IL to Detroit, MI', 'light'], ['real-santa-monica-la', 'Santa Monica Pier to Los Angeles City Hall', 'dark']]) {
      if (process.env.ROUTESHIELD_LIVE_ONLY === 'santa-monica' && name !== 'real-santa-monica-la') continue;
      await live.getByRole('radio', { name: theme === 'light' ? 'Light theme' : 'Dark theme' }).click(); await live.getByRole('tab', { name: 'Trip', exact: true }).click(); await live.getByRole('button', { name: chip }).click(); await live.getByRole('button', { name: 'In 3 hours' }).click();
      const started = Date.now(), pending = live.waitForResponse(r => r.url().endsWith('/route-analysis/') && r.request().method() === 'POST', { timeout: 40_000 }); await live.getByRole('button', { name: 'Analyze routes', exact: true }).click(); const http = await pending, wallMs = Date.now() - started;
      if (http.status() !== 200) { console.log(JSON.stringify({ corridor: name, http: http.status(), wallMs })); await capture(live, `${name}-error`); break; }
      const body = await http.json(); console.log(JSON.stringify({ corridor: name, http: http.status(), status: body.recommendation_status, routeCount: body.route_count, wallMs, providerCalls: body.metadata.provider_calls })); await capture(live, name);
    }
    console.log(JSON.stringify({ liveAnalysisSends: sends })); await live.close();
  }
  console.log('Manual map screenshots saved; no real response recordings.');
} finally { await context.close(); await browser.close(); }
