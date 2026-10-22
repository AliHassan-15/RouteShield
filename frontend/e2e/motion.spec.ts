import { test, expect } from '@playwright/test';
import type { Page, Locator } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { heatFixture } from '../src/features/heatmap/fixtures';

const output = resolve(process.cwd(), '../output/playwright/motion-audit');
test.use({ trace: 'off', headless: false, launchOptions: { args: ['--enable-gpu', '--use-angle=d3d11'] } });
async function setup(page: Page) {
  await page.route('**/*', route => ['localhost', '127.0.0.1', 'tiles.openfreemap.org'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
  await page.route('**/api/v1/health/', route => route.fulfill({ json: { status: 'ok', version: 'synthetic', check: 'liveness' } }));
  await page.addInitScript(() => {
    localStorage.setItem('routeshield-theme', 'light'); localStorage.setItem('routeshield-map-legend', 'false'); sessionStorage.clear();
    const state = { eligible: 0, all: 0, sources: [] as string[] };
    Object.assign(window, { __auditCLS: state });
    new PerformanceObserver(list => list.getEntries().forEach(entry => {
      const e = entry as PerformanceEntry & { value: number; hadRecentInput: boolean; sources: { node?: Element }[] };
      state.all += e.value; if (!e.hadRecentInput) state.eligible += e.value;
      state.sources.push(...e.sources.map(s => { const n = s.node instanceof Element ? s.node : (s.node as unknown as Node)?.parentElement; return JSON.stringify({ class: n?.getAttribute('class'), tag: n?.tagName, rect: s }); }));
    })).observe({ type: 'layout-shift', buffered: true });
  });
  await page.setViewportSize({ width: 1440, height: 1000 }); await page.goto('/');
  await expect(page.locator('.header-service')).toContainText('healthy'); await page.waitForFunction(() => !!window.__routeShieldMap);
  await page.evaluate(() => document.fonts.ready);
}
async function analyze(page: Page, keyboard = false) {
  const fixture = heatFixture(keyboard ? 'calm' : 'worst'); fixture.generated_at = new Date().toISOString(); fixture.expires_at = new Date(Date.now() + 900000).toISOString();
  await page.route('**/api/v1/route-analysis/', async route => { await new Promise(resolve => setTimeout(resolve, 300)); await route.fulfill({ json: fixture }); });
  if (keyboard) {
    const tabTo = async (target: Locator) => { for (let i = 0; i < 80 && !await target.evaluate(n => n === document.activeElement); i++) await page.keyboard.press('Tab'); await expect(target).toBeFocused(); };
    await tabTo(page.locator('#trip-destination')); await tabTo(page.getByRole('button', { name: 'Chicago, IL to Detroit, MI' })); await page.keyboard.press('Enter');
    for (const id of ['trip-departure', 'trip-departure-time', 'trip-weight', 'trip-weight-slider']) await tabTo(page.locator(`#${id}`));
    await tabTo(page.getByRole('radio', { name: 'Auto', exact: true })); await tabTo(page.getByRole('button', { name: 'Analyze routes', exact: true })); await page.keyboard.press('Enter');
  } else { await page.getByRole('button', { name: 'Chicago, IL to Detroit, MI' }).click(); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); }
  await expect(page.getByRole('slider', { name: 'Forecast hour' })).toBeVisible(); await page.waitForFunction(() => (window.__routeShieldMap.inspect() as unknown as { arrivalDone: boolean }).arrivalDone);
  await expect(page.locator('.map-route-chip').first()).toHaveCSS('transition-duration', '0s');
}
async function settled(page: Page) {
  await page.evaluate(async () => { await Promise.all(document.getAnimations().filter(a => a.effect?.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {}))); });
  await page.waitForTimeout(650); // Existing camera completion, not a race to assert animation state.
}
async function cls(page: Page) { return page.evaluate(() => (window as unknown as { __auditCLS: { eligible: number; all: number; sources: string[] } }).__auditCLS); }

test('layout stability across analysis, tabs, views, selection, dock, legend, theme and sheet', async ({ page }) => {
  test.setTimeout(180000); await setup(page); const flows: Record<string, { eligible: number; all: number; sources: string[] }> = { firstLoad: await cls(page) };
  const flow = async (name: string, action: () => Promise<unknown>) => {
    const before = await cls(page); await action(); await settled(page); const after = await cls(page);
    flows[name] = { eligible: after.eligible - before.eligible, all: after.all - before.all, sources: after.sources.slice(before.sources.length) };
  };
  await flow('arrival', () => analyze(page));
  await flow('tripResults', async () => { await page.getByRole('tab', { name: 'Trip', exact: true }).click(); await page.getByRole('tab', { name: 'Results', exact: true }).click(); });
  await flow('subviews', async () => { await page.getByRole('radio', { name: 'Profile', exact: true }).click(); await expect(page.locator('.profile-plot')).toBeVisible(); await page.getByRole('radio', { name: 'Checkpoints', exact: true }).click(); await page.getByRole('radio', { name: 'Compare', exact: true }).click(); });
  await flow('route', () => page.locator('.route-option').nth(1).click());
  await flow('checkpointDockOpen', async () => { await page.locator('.map-engine-host canvas').focus(); await page.keyboard.press(']'); await expect(page.locator('.inspector-dock')).toBeVisible(); });
  await flow('dockClose', () => page.getByRole('button', { name: 'Close checkpoint inspector' }).click());
  await flow('legend', () => page.getByRole('button', { name: 'Chart legend' }).click());
  await flow('theme', () => page.getByRole('radio', { name: 'Dark theme', exact: true }).click());
  await page.setViewportSize({ width: 320, height: 844 }); await settled(page);
  expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeGreaterThan(844); expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
  await flow('sheetSnaps', async () => { await page.locator('.sheet-handle').press('End'); await settled(page); await page.locator('.sheet-handle').press('ArrowUp'); await settled(page); await page.locator('.sheet-handle').press('Home'); });
  await mkdir(output, { recursive: true }); await writeFile(resolve(output, 'cls.json'), JSON.stringify(flows, null, 2));
  for (const [name, value] of Object.entries(flows)) { expect(value.eligible, name).toBeLessThanOrEqual(.01); expect(value.all, `${name} including recent input`).toBeLessThanOrEqual(.01); }
});

test('keyboard flow and reduced motion preserve clear state without animation or traps', async ({ page }) => {
  test.setTimeout(180000); await page.emulateMedia({ reducedMotion: 'reduce' }); await setup(page);
  await page.keyboard.press('Tab'); await expect(page.getByRole('link', { name: 'Skip to console', exact: true })).toBeFocused(); await page.keyboard.press('Enter');
  await page.locator('#trip-origin').focus(); await page.keyboard.press('Tab'); await expect(page.getByRole('button', { name: 'Swap origin and destination' })).toBeFocused();
  await analyze(page, true); await expect(page.locator('#results-heading')).toBeFocused();
  const selectors = ['.recommendation-ticket', '.route-option', '.comparison-matrix tr', '.tab-indicator', '.results-view-indicator', '.heat-control', '.heat-time', '.heat-thumb', '.button', '.trip-section', '.bottom-sheet', '.inspector-dock', '.profile-trace', '.profile-crosshair', '.profile-selected', '.map-selection-pulse', '.skeleton::after'];
  const styles = async () => page.evaluate(selectors => selectors.flatMap(selector => { const pseudo = selector.includes('::') ? '::after' : undefined; return Array.from(document.querySelectorAll(selector.replace('::after', ''))).map(node => { const s = getComputedStyle(node, pseudo); return { selector, animation: s.animationDuration, transition: s.transitionDuration }; }); }), selectors);
  const assertStyles = async () => { for (const s of await styles()) { expect(s.animation.split(',').every(v => parseFloat(v) === 0), s.selector).toBe(true); expect(s.transition.split(',').every(v => parseFloat(v) === 0), s.selector).toBe(true); } };
  await assertStyles();
  expect(await page.locator('.metric-animated').allTextContents()).toEqual(await page.locator('.metric-reserve').allTextContents());
  await page.locator('.route-option').nth(1).focus(); await page.keyboard.press('Enter'); await expect(page.locator('.route-option').nth(1)).toHaveAttribute('aria-checked', 'true');
  await page.locator('.comparison-matrix thead button').first().focus(); await page.keyboard.press('Enter'); await expect(page.locator('.comparison-matrix thead button').first()).toHaveAttribute('aria-pressed', 'true');
  const canvas = page.locator('.map-engine-host canvas'); await canvas.focus(); await page.keyboard.press(']'); await page.keyboard.press(']'); await expect(page.locator('.inspector-dock')).toBeVisible();
  await page.getByRole('radio', { name: 'Profile', exact: true }).focus(); await page.keyboard.press('Space');
  const chart = page.getByRole('slider', { name: 'Wind checkpoint profile' }); await chart.focus(); await chart.press('End'); await chart.press('Enter'); await expect(page.getByRole('region', { name: 'Checkpoint inspector' })).toContainText('Checkpoint 6 of 6');
  await assertStyles();
  const slider = page.getByRole('slider', { name: 'Forecast hour' }); await slider.focus(); await slider.press('End'); await expect(slider).toHaveAttribute('aria-valuenow', '48'); await slider.press('Home');
  expect(await page.evaluate(() => window.__routeShieldHeatStore.inspect().playing)).toBe(false); expect(await page.evaluate(() => window.__routeShieldHeat.inspect().transitioning)).toBe(false);
  await slider.press('p'); await expect(page.getByRole('button', { name: 'Pause forecast' })).toBeVisible(); await slider.press('p');
  await page.getByRole('button', { name: 'Chart legend' }).focus(); await page.keyboard.press('Space'); await expect(page.locator('#map-legend-content')).toBeVisible();
  const full = page.getByRole('button', { name: 'Fullscreen map', exact: true }); if (await full.count()) { await full.focus(); await page.keyboard.press('Enter'); await expect(canvas).toBeFocused(); await page.keyboard.press('Escape'); await expect(full).toBeFocused(); }
  const focus = await page.evaluate(() => { const node = document.activeElement!; const s = getComputedStyle(node); return { visible: node.matches(':focus-visible'), outline: s.outlineStyle }; }); expect(focus.visible).toBe(true); expect(focus.outline).not.toBe('none');
  const camera = await page.evaluate(() => (window.__routeShieldMap.inspect() as unknown as { cameraDuration: number }).cameraDuration); expect(camera).toBe(0);
  await mkdir(output, { recursive: true }); await writeFile(resolve(output, 'reduced.json'), JSON.stringify({ styles: await styles(), camera, focus, playbackAutostart: false }, null, 2));
});
