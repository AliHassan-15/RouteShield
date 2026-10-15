// Manual browser evidence: synthetic API bodies and one guarded live analysis.
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
process.env.PLAYWRIGHT_BROWSERS_PATH ??= resolve(process.cwd(), '../.cache/ms-playwright');
const { chromium } = await import('@playwright/test');
const output = resolve(process.cwd(), '../output/playwright/heatmap'); await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: process.env.HEAT_HARDWARE !== '1', args: process.env.HEAT_HARDWARE === '1' ? ['--enable-gpu', '--use-angle=d3d11', '--enable-precise-memory-info'] : ['--enable-unsafe-swiftshader', '--enable-precise-memory-info'] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage(), errors = [], screenshots = [];
page.on('pageerror', e => errors.push(e.name));
await page.route('**/*', route => ['127.0.0.1', 'localhost', 'tiles.openfreemap.org'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
await page.addInitScript(() => { localStorage.setItem('routeshield-theme', 'light'); localStorage.setItem('routeshield-map-legend', 'false'); });
if (process.env.HEAT_LIVE !== '1') await page.route('**/api/v1/health/', route => route.fulfill({ json: { status: 'ok', version: 'synthetic', check: 'liveness' } }));
const capture = async name => { await page.evaluate(() => document.fonts.ready); await page.waitForTimeout(500); await page.screenshot({ path: resolve(output, `${name}.png`), animations: 'disabled', fullPage: name === 'zoom-reflow-200' }); screenshots.push(name); };
const settle = async () => { await page.waitForFunction(() => { const h = window.__routeShieldHeat?.inspect(); return h && !h.transitioning; }); };
const hour = async h => { await page.evaluate(h => window.__routeShieldHeatStore.hour(h), h); await settle(); };
const analyze = async mode => {
  const fixture = await page.evaluate(async mode => { const { heatFixture } = await import('/src/features/heatmap/fixtures.ts'); return heatFixture(mode); }, mode);
  fixture.generated_at = new Date().toISOString(); fixture.expires_at = new Date(Date.now() + 900000).toISOString(); fixture.analysis_id = `synthetic-heat-${Date.now()}`; fixture.routes.forEach(r => r.checkpoints.forEach(cp => cp.weather.fetched_at = fixture.generated_at));
  if (mode === 'malformed') fixture.heatmap.frames[0].levels = 'bad';
  await page.unroute('**/api/v1/route-analysis/'); await page.route('**/api/v1/route-analysis/', route => route.fulfill({ json: fixture }));
  await page.getByRole('tab', { name: 'Trip', exact: true }).click(); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); await page.waitForTimeout(1800); await page.waitForFunction(() => window.__routeShieldMap.inspect().basemapReady, null, { timeout: 30000 });
  return fixture;
};
try {
  await page.goto(process.env.HEAT_BASE_URL ?? 'http://127.0.0.1:5173/'); await page.waitForFunction(() => !!window.__routeShieldMap); await page.waitForFunction(() => document.querySelector('.header-service')?.textContent?.includes('healthy'));
  const renderer = await page.locator('.map-engine-host canvas').evaluate(c => { const gl = c.getContext('webgl2') || c.getContext('webgl'); const ext = gl?.getExtension('WEBGL_debug_renderer_info'); return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'Unavailable'; });
  console.log(JSON.stringify({ renderer, headedHardwareAttempt: process.env.HEAT_HARDWARE === '1' }));
  if (process.env.HEAT_RENDERER_ONLY === '1') { await writeFile(resolve(output, 'hardware-attempt.json'), JSON.stringify({ renderer, headed: true })); }
  else if (process.env.HEAT_LIVE === '1') {
    const guard = resolve(output, 'live-budget.json'); let sends = 0;
    try { sends = JSON.parse(await readFile(guard, 'utf8')).analysisSends; if (!Number.isInteger(sends) || sends < 0 || sends > 1) throw Error('Invalid budget'); } catch (e) { if (e.code !== 'ENOENT') throw e; }
    if (sends) throw Error('Live budget exhausted; no retry.');
    await page.route('**/api/v1/route-analysis/', async route => { if (sends) return route.abort(); sends++; await writeFile(guard, JSON.stringify({ analysisSends: sends })); await route.continue(); });
    await page.getByRole('button', { name: 'Santa Monica Pier to Los Angeles City Hall' }).click(); await page.getByRole('button', { name: 'In 3 hours' }).click();
    const started = Date.now(), pending = page.waitForResponse(r => r.url().endsWith('/route-analysis/') && r.request().method() === 'POST', { timeout: 40000 }); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); const http = await pending;
    const metrics = { http: http.status(), wallMs: Date.now() - started, analysisSends: sends };
    if (http.status() === 200) { const body = await http.json(); Object.assign(metrics, { routeCount: body.route_count, status: body.recommendation_status, providerCalls: body.metadata.provider_calls, backendMs: body.metadata.total_ms }); await page.waitForTimeout(2000); await page.waitForFunction(() => window.__routeShieldMap.inspect().basemapReady, null, { timeout: 30000 }); await hour(0); await capture('real-santa-hour-0'); await hour(24); await capture('real-santa-hour-24'); }
    console.log(JSON.stringify(metrics)); await writeFile(resolve(output, 'live-metrics.json'), JSON.stringify(metrics));
  } else {
    await page.getByRole('button', { name: 'Chicago, IL to Detroit, MI' }).click();
    if (process.env.HEAT_INTERPLAY_ONLY === '1') {
      await analyze('stormy'); for (const h of [4, 16, 24]) { await hour(h); await capture(h === 24 ? 'truck-arrived' : `truck-hour-${h}`); } await hour(12); await page.getByRole('switch', { name: 'Heatmap' }).focus(); await page.keyboard.press('Tab'); if (!await page.getByRole('slider', { name: 'Forecast hour' }).evaluate(node => node.matches(':focus-visible'))) throw Error('Slider keyboard focus not visible'); await capture('slider-focus'); await page.getByRole('button', { name: 'Zoom in' }).click(); await page.getByRole('button', { name: 'Zoom in' }).click(); await capture('route-closeup');
    } else if (process.env.HEAT_CALM_ONLY === '1') {
      await analyze('calm'); await hour(24); for (const theme of ['light', 'dark']) { await page.getByRole('radio', { name: `${theme === 'light' ? 'Light' : 'Dark'} theme`, exact: true }).click(); await capture(`calm-${theme}-24`); }
    } else if (process.env.HEAT_REFLOW_ONLY === '1') {
      await analyze('stormy'); await hour(12); await page.setViewportSize({ width: 720, height: 500 }); await page.locator('.sheet-handle').press('Home'); await page.waitForTimeout(350); const control = await page.locator('.heat-control').boundingBox(), sheet = await page.locator('.bottom-sheet').boundingBox(); if (sheet.y < control.y + control.height) throw Error('Sheet overlaps forecast control'); await capture('zoom-reflow-200'); console.log(JSON.stringify({ reflowOverlap: false, scrollHeight: await page.evaluate(() => document.documentElement.scrollHeight) }));
    } else if (process.env.HEAT_PERF === '1') {
      await analyze('worst'); await page.waitForTimeout(1500); const paths = await page.evaluate(() => window.__routeShieldHeat.benchmark()); await settle();
      const cdp = await context.newCDPSession(page); await cdp.send('Tracing.start', { categories: 'devtools.timeline,blink.user_timing', transferMode: 'ReturnAsStream' });
      await page.evaluate(() => { window.__heatTrace = { frames: [], tasks: [], active: true }; const record = window.__heatTrace; new PerformanceObserver(list => { if (record.active) list.getEntries().forEach(e => record.tasks.push(e.duration)); }).observe({ type: 'longtask' }); let last; const step = now => { if (last !== undefined) record.frames.push(now - last); last = now; if (record.active) requestAnimationFrame(step); }; requestAnimationFrame(step); });
      const commits = await page.evaluate(() => window.__routeShieldConsoleCommits);
      const requests = []; const onRequest = () => requests.push(1); page.on('request', onRequest);
      const slider = page.getByRole('slider', { name: 'Forecast hour' }), box = await slider.boundingBox(); await page.mouse.move(box.x, box.y + 22); await page.mouse.down(); await page.mouse.move(box.x + box.width, box.y + 22, { steps: 48 }); await page.mouse.up(); await settle();
      await page.evaluate(() => { window.__routeShieldHeatStore.hour(0); window.__routeShieldHeatStore.update({ speed: 4, playing: true }); }); await page.waitForTimeout(5000); await page.evaluate(() => window.__routeShieldHeatStore.update({ playing: false })); await settle(); page.off('request', onRequest);
      const traceEnd = new Promise(resolve => cdp.once('Tracing.tracingComplete', resolve)); await cdp.send('Tracing.end'); const { stream } = await traceEnd; let trace = ''; while (true) { const data = await cdp.send('IO.read', { handle: stream }); trace += data.data; if (data.eof) break; } await cdp.send('IO.close', { handle: stream }); await writeFile(resolve(output, process.env.HEAT_REVISION ? 'trace-final.json' : 'trace-before.json'), trace);
      const metrics = await page.evaluate(() => { const t = window.__heatTrace; t.active = false; t.frames.sort((a, b) => a - b); return { frames: { median: t.frames[Math.floor(t.frames.length / 2)], p95: t.frames[Math.floor(t.frames.length * .95)], max: Math.max(...t.frames), count: t.frames.length }, longTasks: { count: t.tasks.length, max: Math.max(0, ...t.tasks) }, heat: window.__routeShieldHeat.inspect(), hardwareConcurrency: navigator.hardwareConcurrency }; });
      Object.assign(metrics, { renderer, paths, requests: requests.length, unrelatedConsoleCommits: await page.evaluate(() => window.__routeShieldConsoleCommits) - commits }); console.log(JSON.stringify(metrics)); await writeFile(resolve(output, process.env.HEAT_REVISION ? 'performance-final.json' : 'performance-before.json'), JSON.stringify(metrics, null, 2));
    } else {
      await analyze('stormy'); await page.waitForFunction(() => window.__routeShieldMap.inspect().basemapReady, null, { timeout: 30000 });
      for (const theme of ['light', 'dark']) { await page.getByRole('radio', { name: `${theme === 'light' ? 'Light' : 'Dark'} theme`, exact: true }).click(); for (const h of [0, 12, 24, 48]) { await hour(h); await capture(`stormy-${theme}-${h}`); } }
      for (const theme of ['light', 'dark']) { await analyze('calm'); await page.getByRole('radio', { name: `${theme === 'light' ? 'Light' : 'Dark'} theme`, exact: true }).click(); await hour(24); await capture(`calm-${theme}-24`); }
      await analyze('stormy'); await page.getByRole('radio', { name: 'Light theme', exact: true }).click(); await hour(12); await capture('heat-on'); await page.getByRole('switch', { name: 'Heatmap' }).click(); await capture('heat-off'); await page.getByRole('switch', { name: 'Heatmap' }).click(); await page.getByRole('button', { name: 'Options +' }).click();
      await page.getByRole('button', { name: /Show sample points/ }).click(); await capture('samples-visible'); await page.getByRole('button', { name: /Show sample points/ }).click();
      for (const filter of ['Combined', 'Wind', 'Rain', 'Snow']) { await page.getByRole('button', { name: filter, exact: true }).click(); await settle(); await capture(`filter-${filter.toLowerCase()}`); }
      await page.getByRole('button', { name: 'Combined', exact: true }).click(); await page.getByRole('button', { name: 'Options −' }).click(); await hour(4); await capture('truck-hour-4'); await hour(16); await capture('truck-hour-16'); await hour(24); await capture('truck-arrived'); await page.getByRole('button', { name: 'Zoom in' }).click(); await page.getByRole('button', { name: 'Zoom in' }).click(); await capture('route-closeup'); await page.getByRole('button', { name: 'Recenter routes' }).click(); await hour(48); await page.getByRole('button', { name: 'Options +' }).click(); await capture('unavailable-hours-caption'); await page.getByRole('button', { name: 'Options −' }).click(); await page.getByRole('button', { name: 'Chart legend' }).click(); await capture('legend-expanded'); await page.getByRole('button', { name: 'Chart legend' }).click(); await hour(12); await page.getByRole('switch', { name: 'Heatmap' }).focus(); await page.keyboard.press('Tab'); await capture('slider-focus');
      await page.setViewportSize({ width: 320, height: 844 }); await page.locator('.sheet-handle').press('End'); await capture('mobile-320-peek'); await page.locator('.sheet-handle').press('ArrowUp'); await capture('mobile-320-half'); await page.locator('.sheet-handle').press('Home'); await capture('mobile-320-full');
      await page.setViewportSize({ width: 1440, height: 1000 }); const zoomBefore = await page.evaluate(() => ({ width: innerWidth, dpr: devicePixelRatio })); await page.keyboard.press('Control+0'); for (let i = 0; i < 5; i++) await page.keyboard.press('Control+Equal'); const zoomAfter = await page.evaluate(() => ({ width: innerWidth, dpr: devicePixelRatio })); console.log(JSON.stringify({ zoomBefore, zoomAfter, native200Verified: zoomAfter.width === zoomBefore.width / 2 })); if (zoomAfter.width === zoomBefore.width / 2) await capture('browser-native-200'); await page.keyboard.press('Control+0'); await page.setViewportSize({ width: 720, height: 500 }); await capture('zoom-reflow-200'); await page.setViewportSize({ width: 1440, height: 1000 }); await analyze('partial'); await hour(12); await capture('partial-availability'); await analyze('no filters'); await page.getByRole('button', { name: 'Options +' }).click(); await capture('filter-omitted'); await analyze('malformed'); await capture('heatmap-malformed');
      console.log(JSON.stringify({ screenshotCount: screenshots.length, pageErrors: errors }));
    }
  }
} finally { await context.close(); await browser.close(); }
