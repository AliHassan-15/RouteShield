// Local production preview, real basemap assets only; every API response is synthetic.
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { build } from 'vite';
process.env.PLAYWRIGHT_BROWSERS_PATH ??= resolve('../.cache/ms-playwright');
const { chromium } = await import('@playwright/test');
const folder = resolve('../output/playwright/deployment'), label = process.argv[2] ?? 'before';
await mkdir(folder, { recursive: true });
const generated = await build({ configFile: false, logLevel: 'silent', build: { write: false, lib: { entry: resolve('src/features/heatmap/fixtures.ts'), formats: ['es'], fileName: 'fixture' }, minify: false } });
const chunk = (Array.isArray(generated) ? generated : [generated]).flatMap(result => result.output).find(x => x.type === 'chunk');
const { heatFixture } = await import(`data:text/javascript;base64,${Buffer.from(chunk.code).toString('base64')}`);
const fixture = heatFixture('worst'); fixture.analysis_id = 'synthetic-production-audit'; fixture.generated_at = new Date().toISOString(); fixture.expires_at = new Date(Date.now() + 900000).toISOString();
const browser = await chromium.launch({ headless: false, args: ['--enable-gpu', '--use-angle=d3d11'] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage(), violations = [], errors = [], mapResponses = [];
page.on('console', m => { if (/Content Security Policy|violates.*directive|Refused to (?:load|connect|execute|create)/i.test(m.text())) violations.push(m.type()); });
page.on('pageerror', e => errors.push(e.name));
page.on('response', r => { if (new URL(r.url()).hostname === 'tiles.openfreemap.org') mapResponses.push(r.status()); });
await page.addInitScript(() => { localStorage.setItem('routeshield-theme', 'light'); localStorage.setItem('routeshield-map-legend', 'false'); sessionStorage.clear(); document.addEventListener('securitypolicyviolation', e => { (window.__deploymentCSP ??= []).push(e.violatedDirective); }); });
await page.route('**/*', route => {
  const url = new URL(route.request().url());
  if (url.origin === 'https://api.example.test') {
    const headers = { 'Access-Control-Allow-Origin': 'http://127.0.0.1:4173', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'content-type' };
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
    if (url.pathname.endsWith('/health/')) return route.fulfill({ headers, json: { status: 'ok', check: 'liveness', version: 'synthetic' } });
    if (url.pathname.endsWith('/route-analysis/')) return route.fulfill({ headers, json: fixture });
    return route.abort();
  }
  return ['127.0.0.1', 'tiles.openfreemap.org'].includes(url.hostname) ? route.continue() : route.abort();
});
try {
  await page.goto('http://127.0.0.1:4173'); await page.locator('.map-engine-host canvas').waitFor();
  await page.waitForFunction(() => !document.querySelector('.map-skeleton')); await page.evaluate(() => document.fonts.ready); await page.waitForTimeout(2000);
  const renderer = await page.locator('.map-engine-host canvas').evaluate(canvas => { const gl = canvas.getContext('webgl2'), ext = gl?.getExtension('WEBGL_debug_renderer_info'); return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'Unavailable'; });
  await page.getByRole('button', { name: 'Chicago, IL to Detroit, MI' }).click();
  const cdp = await context.newCDPSession(page);
  await cdp.send('Tracing.start', { categories: 'devtools.timeline,v8,disabled-by-default-v8.cpu_profiler', transferMode: 'ReturnAsStream' });
  await page.evaluate(() => {
    const record = { active: false, frames: [], tasks: [], cls: 0, start: 0 }; window.__deploymentMeasure = record;
    new PerformanceObserver(list => { if (record.active) list.getEntries().forEach(e => record.tasks.push({ duration: e.duration, start: e.startTime })); }).observe({ type: 'longtask' });
    new PerformanceObserver(list => { if (record.active) list.getEntries().forEach(e => { if (!e.hadRecentInput) record.cls += e.value; }); }).observe({ type: 'layout-shift' });
    let last; const step = now => { if (record.active && last !== undefined) record.frames.push(now - last); last = now; requestAnimationFrame(step); }; requestAnimationFrame(step);
  });
  // Arm immediately before fulfilling the POST, excluding form interaction and network wait.
  await page.route('**/api/v1/route-analysis/', async route => {
    const headers = { 'Access-Control-Allow-Origin': 'http://127.0.0.1:4173', 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'content-type' };
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
    await page.evaluate(() => { const r = window.__deploymentMeasure; r.active = true; r.start = performance.now(); }); await route.fulfill({ headers, json: fixture });
  });
  await page.getByRole('button', { name: 'Analyze routes', exact: true }).click();
  await page.getByRole('heading', { name: 'Route comparison', exact: true }).waitFor();
  await page.waitForFunction(() => performance.now() - window.__deploymentMeasure.start >= 2100);
  const metrics = await page.evaluate(() => { const r = window.__deploymentMeasure; r.active = false; const f = r.frames.sort((a, b) => a - b); return { median: f[Math.floor(f.length / 2)], p95: f[Math.floor(f.length * .95)], max: Math.max(...f), frameCount: f.length, longTasks: r.tasks.length, maxLongTask: Math.max(0, ...r.tasks.map(t => t.duration)), totalBlockingMs: r.tasks.reduce((s, t) => s + Math.max(0, t.duration - 50), 0), tasks: r.tasks, cls: r.cls, windowMs: performance.now() - r.start }; });
  const done = new Promise(resolve => cdp.once('Tracing.tracingComplete', resolve)); await cdp.send('Tracing.end'); const { stream } = await done;
  let trace = ''; while (true) { const piece = await cdp.send('IO.read', { handle: stream }); trace += piece.data; if (piece.eof) break; } await cdp.send('IO.close', { handle: stream });
  await writeFile(resolve(folder, `${label}-trace.json`), trace);
  await page.waitForTimeout(1500); await page.screenshot({ path: resolve(folder, `${label}-production.png`) });
  await page.getByRole('button', { name: 'Backend status', exact: true }).click(); await page.getByRole('button', { name: 'Warm up', exact: true }).waitFor(); await page.screenshot({ path: resolve(folder, `${label}-warmup.png`) });
  const directives = await page.evaluate(() => window.__deploymentCSP ?? []);
  const report = { renderer, hardware: !/SwiftShader|software|Unavailable/i.test(renderer), browser: browser.version(), fixture: { routes: 3, points: 200, frames: 49 }, metrics, violations, directives, pageErrors: errors, mapResponses: { count: mapResponses.length, failed: mapResponses.filter(s => s !== 200).length }, providerRequests: 0 };
  await writeFile(resolve(folder, `${label}.json`), JSON.stringify(report, null, 2)); console.log(JSON.stringify(report));
  if (violations.length || directives.length || errors.length || !mapResponses.length || mapResponses.some(s => s !== 200)) throw Error('Production CSP/basemap browser check failed; see numeric report.');
} finally { await context.close(); await browser.close(); }
