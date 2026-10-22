// Local, opt-in evidence. Synthetic by default; --live has a persistent one-send guard.
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
process.env.PLAYWRIGHT_BROWSERS_PATH ??= resolve(process.cwd(), '../.cache/ms-playwright');
const { chromium } = await import('@playwright/test');
const output = resolve(process.cwd(), '../output/playwright/motion-audit'); await mkdir(output, { recursive: true });
const mode = process.argv[2] ?? '--profile', screenshots = [], errors = [];
const browser = await chromium.launch({ headless: false, args: ['--enable-gpu', '--use-angle=d3d11', '--enable-precise-memory-info'] });
const video = mode === '--capture';
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, ...(video ? { recordVideo: { dir: output, size: { width: 1440, height: 1000 } } } : {}) });
const page = await context.newPage(); page.on('pageerror', e => errors.push(e.name));
await page.route('**/*', route => ['localhost', '127.0.0.1', 'tiles.openfreemap.org'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
await page.addInitScript(() => { localStorage.setItem('routeshield-theme', 'light'); localStorage.setItem('routeshield-map-legend', 'false'); sessionStorage.clear(); });
if (mode !== '--live') await page.route('**/api/v1/health/', route => route.fulfill({ json: { status: 'ok', version: 'synthetic', check: 'liveness' } }));
const capture = async (name, fullPage = false) => { await page.waitForTimeout(250); await page.screenshot({ path: resolve(output, `${name}.png`), fullPage }); screenshots.push(name); };
const waitTiles = async () => {
  // This requires an actual MapLibre idle event AND a loaded-tiles check. A
  // successful API response or loaded style alone cannot pass the capture gate.
  await page.waitForFunction(() => { const m = window.__routeShieldMap?.inspect(); return m?.idleCount > 0 && m.tilesLoaded && m.basemapReady && (!m.analysisId || m.lastIdleAt >= m.drawStartedAt); }, null, { timeout: 40000 });
};
const settle = async () => { await page.waitForFunction(() => { const m = window.__routeShieldMap?.inspect(), h = window.__routeShieldHeat?.inspect(); return m?.arrivalDone && h && !h.transitioning; }); };
const fixture = async () => {
  const body = await page.evaluate(async choice => (await import('/src/features/heatmap/fixtures.ts')).heatFixture(choice), mode === '--capture' ? 'calm' : 'worst');
  body.analysis_id = `synthetic-motion-${Date.now()}`; body.generated_at = new Date().toISOString(); body.expires_at = new Date(Date.now() + 900000).toISOString(); body.routes.forEach(r => r.checkpoints.forEach(cp => cp.weather.fetched_at = body.generated_at)); return body;
};
const prepare = async (onResponse = async () => {}) => {
  const body = await fixture(); await page.unroute('**/api/v1/route-analysis/');
  await page.route('**/api/v1/route-analysis/', async route => { await page.waitForTimeout(200); await onResponse(); await route.fulfill({ json: body }); });
  await page.getByRole('tab', { name: 'Trip', exact: true }).click(); await page.getByRole('button', { name: 'Chicago, IL to Detroit, MI' }).click();
};
const startMeasure = () => page.evaluate(() => {
  const record = { frames: [], tasks: [], cls: 0, clsAll: 0, active: true };
  window.__motionMeasure = record;
  const tasks = new PerformanceObserver(list => { if (record.active) list.getEntries().forEach(e => record.tasks.push(e.duration)); }); tasks.observe({ type: 'longtask' });
  const shifts = new PerformanceObserver(list => { if (record.active) list.getEntries().forEach(e => { record.clsAll += e.value; if (!e.hadRecentInput) record.cls += e.value; }); }); shifts.observe({ type: 'layout-shift' });
  let last; const step = now => { if (last !== undefined) record.frames.push(now - last); last = now; if (record.active) requestAnimationFrame(step); else { tasks.disconnect(); shifts.disconnect(); } }; requestAnimationFrame(step);
});
const endMeasure = () => page.evaluate(() => { const r = window.__motionMeasure; r.active = false; const frames = r.frames.sort((a, b) => a - b); return { frames: { median: frames[Math.floor(frames.length / 2)], p95: frames[Math.floor(frames.length * .95)], max: Math.max(...frames), count: frames.length }, longTasks: { count: r.tasks.length, max: Math.max(0, ...r.tasks), totalBlockingMs: r.tasks.reduce((s, t) => s + Math.max(0, t - 50), 0) }, cls: r.cls, clsIncludingInput: r.clsAll }; });
// Capture compositor frames without serial screenshots delaying the choreography.
const filmSeries = async (prefix, targets, action, timings) => {
  const cdp = await context.newCDPSession(page), frames = [];
  const onFrame = frame => { frames.push(frame); void cdp.send('Page.screencastFrameAck', { sessionId: frame.sessionId }).catch(() => {}); };
  cdp.on('Page.screencastFrame', onFrame); await cdp.send('Page.startScreencast', { format: 'png', everyNthFrame: 1 });
  await page.waitForTimeout(50); const start = await action(); await page.waitForTimeout(Math.max(50, start + Math.max(...targets) + 200 - Date.now()));
  await cdp.send('Page.stopScreencast'); cdp.off('Page.screencastFrame', onFrame);
  if (!frames.length) throw Error('No compositor frames recorded');
  for (const target of targets) {
    const frame = frames.reduce((best, frame) => Math.abs(frame.metadata.timestamp * 1000 - start - target) < Math.abs(best.metadata.timestamp * 1000 - start - target) ? frame : best);
    const name = `${prefix}-${target}`; await writeFile(resolve(output, `${name}.png`), Buffer.from(frame.data, 'base64')); screenshots.push(name); timings.push({ name, targetMs: target, actualMs: frame.metadata.timestamp * 1000 - start, compositorFrames: frames.length });
  }
  await cdp.detach();
};
const domAudit = () => page.evaluate(() => {
  const visible = node => { const r = node.getBoundingClientRect(), s = getComputedStyle(node); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && !node.closest('[hidden],[inert]'); };
  const controls = [...document.querySelectorAll('button,input,select,[role="slider"],summary,a[href],[role="radio"]')].filter(visible);
  const name = node => node.getAttribute('aria-label') || (node.getAttribute('aria-labelledby') ?? '').split(' ').map(id => document.getElementById(id)?.textContent ?? '').join('') || ('labels' in node ? [...node.labels ?? []].map(l => l.textContent).join('') : '') || node.textContent?.trim();
  const ids = [...document.querySelectorAll('[id]')].map(n => n.id);
  const rgb = value => (value.match(/[\d.]+/g) ?? []).map(Number);
  const blend = (top, bottom) => { const a = top[3] ?? 1; return top.slice(0, 3).map((v, i) => v * a + bottom[i] * (1 - a)); };
  const background = node => { const rect = node.getBoundingClientRect(), x = rect.x + rect.width / 2, y = rect.y + rect.height / 2, chain = []; for (let n = node; n; n = n.parentElement) chain.unshift(n); return chain.reduce((b, n) => { const r = n.getBoundingClientRect(); return (r.width > 4 && r.height > 4) || x >= r.left && x <= r.right && y >= r.top && y <= r.bottom ? blend(rgb(getComputedStyle(n).backgroundColor), b) : b; }, [255, 255, 255]); };
  const lum = c => c.map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((s, v, i) => s + v * [.2126, .7152, .0722][i], 0);
  const contrast = [...document.querySelectorAll('.trip-form *, .shell-header *, .bottom-sheet *, .results-body *, .heat-control *, .map-controls *, .map-legend *, .inspector-dock *, .map-route-chip, .map-endpoint, .heat-truck-card, .map-checkpoint-tooltip *')].filter(n => visible(n) && !n.closest('.sr-only') && [...n.childNodes].some(c => c.nodeType === 3 && c.textContent.trim())).map(n => { const s = getComputedStyle(n), bg = background(n), fg = blend(rgb(s.color), bg), a = lum(bg), b = lum(fg); return { element: n.className?.baseVal ?? n.className ?? n.tagName, parent: n.parentElement?.className, text: n.textContent?.trim().slice(0, 60), ratio: (Math.max(a, b) + .05) / (Math.min(a, b) + .05), opacity: s.opacity }; });
  const roles = new Set(['status', 'alert', 'region', 'radiogroup', 'radio', 'tab', 'tablist', 'tabpanel', 'slider', 'img', 'combobox', 'listbox', 'option', 'dialog', 'tooltip', 'button', 'group', 'presentation', 'none', 'switch']);
  return { controls: controls.length, invalidRoles: [...document.querySelectorAll('[role]')].map(n => n.getAttribute('role')).filter(r => !roles.has(r)), missingNames: controls.filter(n => !name(n)).map(n => n.outerHTML.slice(0, 150)), duplicateIds: [...new Set(ids.filter((id, i) => ids.indexOf(id) !== i))], brokenLabels: [...document.querySelectorAll('label[for]')].filter(n => !document.getElementById(n.htmlFor)).map(n => n.htmlFor), brokenReferences: [...document.querySelectorAll('[aria-labelledby],[aria-describedby],[aria-controls]')].flatMap(n => ['aria-labelledby', 'aria-describedby', 'aria-controls'].flatMap(attr => (n.getAttribute(attr) ?? '').split(' ').filter(id => id && !document.getElementById(id)))), smallTargets: controls.filter(n => { const r = n.getBoundingClientRect(); return r.width < 43.9 || r.height < 43.9; }).map(n => ({ name: name(n), width: n.getBoundingClientRect().width, height: n.getBoundingClientRect().height, tag: n.tagName })), contrastMinimum: Math.min(...contrast.map(c => c.ratio)), contrastFailures: contrast.filter(c => c.ratio < 4.5), contrastCount: contrast.length };
});
try {
  await page.goto('http://127.0.0.1:5173/'); await page.waitForFunction(() => !!window.__routeShieldMap); await page.evaluate(() => document.fonts.ready); await waitTiles();
  const renderer = await page.locator('.map-engine-host canvas').evaluate(c => { const gl = c.getContext('webgl2'), ext = gl?.getExtension('WEBGL_debug_renderer_info'); return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'Unavailable'; });
  if (mode === '--profile') {
    const cdp = await context.newCDPSession(page); await cdp.send('Tracing.start', { categories: 'devtools.timeline,blink.user_timing', transferMode: 'ReturnAsStream' });
    await prepare(startMeasure); const firstResponse = page.waitForResponse(r => r.url().endsWith('/route-analysis/')); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); const firstBody = await (await firstResponse).json(); await page.waitForFunction(id => window.__routeShieldMap.inspect().analysisId === id, firstBody.analysis_id); await settle(); await page.waitForTimeout(100); const arrival = await endMeasure();
    await waitTiles(); let requests = 0; const request = () => requests++; page.on('request', request); await startMeasure();
    const slider = page.getByRole('slider', { name: 'Forecast hour' }), box = await slider.boundingBox(); await page.mouse.move(box.x, box.y + 22); await page.mouse.down(); await page.mouse.move(box.x + box.width, box.y + 22, { steps: 48 }); await page.mouse.up(); await settle();
    await page.evaluate(() => { window.__routeShieldHeatStore.hour(0); window.__routeShieldHeatStore.update({ speed: 4, playing: true }); }); await page.waitForFunction(() => !window.__routeShieldHeatStore.inspect().playing, null, { timeout: 15000 }); await settle(); const scrubPlayback = await endMeasure(); page.off('request', request);
    await page.emulateMedia({ reducedMotion: 'reduce' }); await prepare(startMeasure); const reducedResponse = page.waitForResponse(r => r.url().endsWith('/route-analysis/')); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); const reducedBody = await (await reducedResponse).json(); await page.waitForFunction(id => window.__routeShieldMap.inspect().analysisId === id, reducedBody.analysis_id); await settle(); await page.waitForTimeout(100); const reducedArrival = await endMeasure();
    const complete = new Promise(resolve => cdp.once('Tracing.tracingComplete', resolve)); await cdp.send('Tracing.end'); const { stream } = await complete; let trace = ''; while (true) { const chunk = await cdp.send('IO.read', { handle: stream }); trace += chunk.data; if (chunk.eof) break; } await cdp.send('IO.close', { handle: stream }); await writeFile(resolve(output, 'performance-trace.json'), trace);
    const metrics = { renderer, hardware: !/SwiftShader|software/i.test(renderer), browser: browser.version(), logicalProcessors: await page.evaluate(() => navigator.hardwareConcurrency), arrival, scrubPlayback, reducedArrival, scrubRequests: requests, heat: await page.evaluate(() => window.__routeShieldHeat.inspect()) };
    await writeFile(resolve(output, process.env.AUDIT_FINAL ? 'performance-final.json' : 'performance-before.json'), JSON.stringify(metrics, null, 2)); console.log(JSON.stringify(metrics));
  } else if (mode === '--capture') {
    const audits = { form: await domAudit() }, timing = [];
    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(viewport); await page.waitForTimeout(350); if (viewport.width < 760) await page.locator('.sheet-handle').press('Home'); await prepare(async () => { audits.loading = await domAudit(); });
      await filmSeries(`arrival-${viewport.width}`, [0, 150, 300, 600, 1000, 1800], async () => {
        const incoming = page.waitForResponse(r => r.url().endsWith('/route-analysis/')); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); const incomingId = (await (await incoming).json()).analysis_id;
        await page.waitForFunction(id => window.__routeShieldMap.inspect().analysisId === id, incomingId);
        return page.evaluate(() => performance.timeOrigin + window.__routeShieldMap.inspect().drawStartedAt);
      }, timing);
      await waitTiles();
    }
    await page.setViewportSize({ width: 1440, height: 1000 }); await page.waitForTimeout(350); await page.evaluate(() => window.__routeShieldHeatStore.hour(12)); await page.waitForTimeout(250); await page.getByRole('button', { name: 'Options +' }).click(); await page.getByRole('button', { name: 'Wind', exact: true }).click();
    const stateBefore = await page.evaluate(() => ({ map: window.__routeShieldMap.inspect(), heat: window.__routeShieldHeat.inspect() }));
    await filmSeries('theme', [0, 50, 100, 200, 350], async () => { const start = Date.now(); await page.getByRole('radio', { name: 'Dark theme', exact: true }).click(); return start; }, timing);
    const stateAfter = await page.evaluate(() => ({ map: window.__routeShieldMap.inspect(), heat: window.__routeShieldHeat.inspect() }));
    await page.getByRole('button', { name: 'Options −' }).click();
    for (const theme of ['dark', 'light']) { await page.getByRole('radio', { name: `${theme === 'light' ? 'Light' : 'Dark'} theme`, exact: true }).click(); await page.waitForTimeout(300); audits[theme] = await domAudit(); }
    await page.getByRole('tab', { name: 'Trip', exact: true }).click(); await page.locator('#trip-origin').focus(); await page.keyboard.press('Tab'); await capture('focus-form');
    await page.getByRole('tab', { name: 'Results', exact: true }).click();
    for (const [name, locator] of [['focus-card', page.locator('.route-option').first()], ['focus-matrix', page.locator('.comparison-matrix thead button').first()], ['focus-map', page.getByRole('button', { name: 'Zoom in' })]]) { await locator.focus(); await page.keyboard.press('Tab'); await page.keyboard.press('Shift+Tab'); await capture(name); }
    await page.getByRole('radio', { name: 'Profile', exact: true }).click(); const chart = page.getByRole('slider', { name: 'Wind checkpoint profile' }); await chart.focus(); await chart.press('ArrowRight'); await chart.press('Enter'); await capture('focus-profile'); audits.profile = await domAudit();
    await page.getByRole('slider', { name: 'Forecast hour' }).focus(); await page.keyboard.press('ArrowRight'); await capture('focus-heat');
    await page.emulateMedia({ reducedMotion: 'reduce' }); await prepare(); const reducedDone = page.waitForResponse(r => r.url().endsWith('/route-analysis/')); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); const reducedId = (await (await reducedDone).json()).analysis_id; await page.waitForFunction(id => window.__routeShieldMap.inspect().analysisId === id, reducedId); await settle(); await capture('reduced-final');
    await page.emulateMedia({ reducedMotion: 'no-preference' }); await page.getByRole('radio', { name: 'Compare', exact: true }).click();
    for (const viewport of [{ width: 320, height: 844 }, { width: 720, height: 500 }]) {
      await page.setViewportSize(viewport); await page.waitForTimeout(400); const prefix = viewport.width === 320 ? 'mobile-320' : 'reflow-200';
      for (const [key, snap] of [['End', 'peek'], ['ArrowUp', 'half'], ['Home', 'full']]) { await page.locator('.sheet-handle').press(key); await page.waitForTimeout(350); await capture(`${prefix}-${snap}`, true); }
      await page.getByRole('tab', { name: 'Trip', exact: true }).click(); await page.waitForTimeout(250); await capture(`${prefix}-form`, true); await page.getByRole('tab', { name: 'Results', exact: true }).click(); audits[prefix] = await domAudit();
    }
    await page.setViewportSize({ width: 1440, height: 1000 }); await page.getByRole('tab', { name: 'Trip', exact: true }).click(); await page.unroute('**/api/v1/route-analysis/'); await page.route('**/api/v1/route-analysis/', route => route.fulfill({ status: 503, json: { error: { code: 'PROVIDER_UNAVAILABLE', message: 'Synthetic provider failure', details: {} } } })); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); await page.getByRole('alert').first().waitFor(); await page.getByRole('alert').first().scrollIntoViewIfNeeded(); await page.waitForTimeout(250); audits.error = await domAudit(); await capture('error-state');
    await writeFile(resolve(output, 'visual-audit.json'), JSON.stringify({ audits, timing, stateBefore, stateAfter, errors, screenshots, videoPath: await page.video().path() }, null, 2)); console.log(JSON.stringify({ screenshots: screenshots.length, errors, audits }));
  } else if (mode === '--roles') {
    await prepare(); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); await settle(); const result = await domAudit(); await writeFile(resolve(output, 'role-validation.json'), JSON.stringify(result, null, 2)); console.log(JSON.stringify({ invalidRoles: result.invalidRoles, controls: result.controls }));
  } else if (mode === '--live') {
    const guard = resolve(output, 'live-budget.json'); let sends = 0; try { sends = JSON.parse(await readFile(guard, 'utf8')).analysisSends; if (!Number.isInteger(sends) || sends < 0) throw Error('Invalid budget'); } catch (e) { if (e.code !== 'ENOENT') throw e; }
    if (sends) throw Error('Live budget exhausted; no retry.');
    await page.route('**/api/v1/route-analysis/', async route => { if (sends) return route.abort(); sends++; await writeFile(guard, JSON.stringify({ analysisSends: sends })); await route.continue(); });
    await page.getByRole('button', { name: 'Santa Monica Pier to Los Angeles City Hall' }).click(); await page.getByRole('button', { name: 'In 3 hours' }).click();
    const pending = page.waitForResponse(r => r.url().endsWith('/route-analysis/') && r.request().method() === 'POST', { timeout: 40000 }), start = Date.now(); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); const http = await pending;
    const metrics = { http: http.status(), wallMs: Date.now() - start, analysisSends: sends, tileCompleteLight: false, tileCompleteDark: false };
    await writeFile(resolve(output, 'live-metrics.json'), JSON.stringify(metrics, null, 2));
    if (http.status() === 200) { const body = await http.json(); Object.assign(metrics, { routeCount: body.route_count, status: body.recommendation_status, providerCalls: body.metadata.provider_calls, backendMs: body.metadata.total_ms }); await writeFile(resolve(output, 'live-metrics.json'), JSON.stringify(metrics, null, 2)); await settle();
      for (const theme of ['light', 'dark']) { await page.getByRole('radio', { name: `${theme === 'light' ? 'Light' : 'Dark'} theme`, exact: true }).click(); await page.waitForTimeout(300); await waitTiles(); metrics[theme === 'light' ? 'tileCompleteLight' : 'tileCompleteDark'] = true; await writeFile(resolve(output, 'live-metrics.json'), JSON.stringify(metrics, null, 2)); await capture(`real-santa-${theme}-hour-0`); }
    }
    await writeFile(resolve(output, 'live-metrics.json'), JSON.stringify(metrics, null, 2)); console.log(JSON.stringify(metrics));
  }
} finally { await context.close(); await browser.close(); }
