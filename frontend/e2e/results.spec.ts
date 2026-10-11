import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { resultFixture, warningsFixture } from '../src/features/results/fixtures';
import type { AnalysisResponse } from '../src/api/types';

const output = resolve(process.cwd(), '../output/playwright/results');
test.use({ trace: 'off' }); // No real response bodies, traces or provider recordings.
async function capture(page: Page, name: string) {
  await mkdir(output, { recursive: true }); await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(550);
  await page.screenshot({ path: resolve(output, `${name}.png`), animations: 'disabled' });
}
async function localOnly(page: Page) {
  await page.route('**/*', route => ['localhost', '127.0.0.1'].includes(new URL(route.request().url()).hostname) ? route.continue() : route.abort());
  await page.addInitScript(() => { localStorage.clear(); localStorage.setItem('routeshield-theme', 'light'); });
}
async function initialize(page: Page, mock = true) {
  await localOnly(page);
  if (mock) await page.route('**/api/v1/health/', route => route.fulfill({ json: { status: 'ok', version: 'synthetic', check: 'liveness' } }));
  await page.goto('/'); await expect(page.locator('.header-service')).toContainText('healthy');
  if (await page.locator('.sheet-handle').count()) await page.locator('.sheet-handle').press('Home');
  await page.getByRole('button', { name: 'Chicago, IL to Detroit, MI' }).click();
}
async function synthetic(page: Page, response: AnalysisResponse) {
  await page.unroute('**/api/v1/route-analysis/');
  response.generated_at = new Date().toISOString(); response.expires_at = new Date(Date.now() + 900_000).toISOString();
  for (const route of response.routes) for (const cp of route.checkpoints) cp.weather.fetched_at = response.generated_at;
  await page.route('**/api/v1/route-analysis/', route => route.fulfill({ json: response }));
  if (await page.locator('.sheet-handle').count()) await page.locator('.sheet-handle').press('Home');
  await page.getByRole('tab', { name: 'Trip', exact: true }).click();
  await page.getByRole('button', { name: 'Analyze routes', exact: true }).click();
  await expect(page.getByRole('tab', { name: 'Results', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('heading', { name: 'Results', exact: true })).toBeFocused();
}
test('synthetic desktop variants, API facts, selection, notices, stale, skeleton and errors', async ({ page }) => {
  test.setTimeout(90000); await page.clock.install(); await page.setViewportSize({ width: 1440, height: 1100 }); await initialize(page);
  const variants = [
    ['recommended-severe', resultFixture()], ['recommended-average', resultFixture('RECOMMENDED', 'AVERAGE_RISK')], ['recommended-id-tie', resultFixture('RECOMMENDED', 'TIE_BROKEN_BY_ID')],
    ['best-available', resultFixture('BEST_FULLY_ASSESSED_AVAILABLE')], ['all-blocked', resultFixture('ALL_BLOCKED')], ['no-fully-assessed', resultFixture('NO_FULLY_ASSESSED_TRAVELABLE_ROUTE')], ['all-incomplete', resultFixture('ALL_INCOMPLETE')],
  ] as const;
  const consoleErrors: string[] = []; page.on('pageerror', error => consoleErrors.push(error.name));
  for (const [name, fixture] of variants) { await synthetic(page, fixture); await capture(page, name); if (!fixture.recommended_route_id) await expect(page.getByLabel('Recommendation')).toHaveCount(0); if (['recommended-average', 'recommended-id-tie', 'best-available'].includes(name)) { await page.locator('.matrix-section').scrollIntoViewIfNeeded(); await capture(page, `${name}-matrix`); } }
  const two = resultFixture(); two.routes.pop(); two.route_count = 2; await synthetic(page, two); await capture(page, 'two-routes');
  await synthetic(page, resultFixture()); await page.locator('.matrix-section').scrollIntoViewIfNeeded(); await capture(page, 'matrix-desktop-light');
  await page.getByRole('radio', { name: /Route 2/ }).click(); await expect(page.locator('thead .is-selected')).toContainText('Route 2'); await capture(page, 'selected-route-2');
  await page.getByRole('radio', { name: 'Dark theme' }).click(); await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark'); await capture(page, 'matrix-desktop-dark');
  await page.locator('.results-scroll').evaluate(e => e.scrollTop = 0); await capture(page, 'recommended-dark'); await page.getByRole('radio', { name: 'Light theme' }).click();
  await synthetic(page, warningsFixture()); await page.locator('.warnings-tray summary').click(); await page.locator('.warnings-tray').scrollIntoViewIfNeeded(); await capture(page, 'warnings-expanded');
  const sim = resultFixture(); sim.metadata.simulated = true; sim.is_simulation = true; sim.simulation_scenario = 'winter_storm'; await synthetic(page, sim); await capture(page, 'simulation');
  await page.clock.fastForward(901000); await page.locator('.results-scroll').evaluate(e => e.scrollTop = 0); await expect(page.locator('.stale-banner')).toBeVisible(); await capture(page, 'stale');
  await page.clock.resume();
  await page.unroute('**/api/v1/route-analysis/'); let finish: (() => void) | undefined;
  await page.route('**/api/v1/route-analysis/', async route => { await new Promise<void>(resolve => finish = resolve); await route.fulfill({ status: 504, headers: { 'X-Request-ID': 'synthetic-timeout', 'Access-Control-Expose-Headers': 'X-Request-ID' }, json: { error: { code: 'PROVIDER_TIMEOUT', message: 'UNTRUSTED', details: {} } } }); });
  await page.getByRole('tab', { name: 'Trip', exact: true }).click(); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); await page.getByRole('tab', { name: 'Results', exact: true }).click(); await expect(page.getByLabel('Results loading')).toBeVisible(); await capture(page, 'skeleton'); finish?.(); await expect(page.getByRole('alert')).toContainText('timed out'); await capture(page, 'timeout');
  expect(consoleErrors).toEqual([]);
});
test('synthetic 320px and 200 percent reflow, mobile half/full hero and matrix, reduced motion', async ({ page, browser }) => {
  test.setTimeout(60000); await page.setViewportSize({ width: 320, height: 844 }); await initialize(page); await synthetic(page, resultFixture());
  await expect(page.locator('.bottom-sheet')).toHaveAttribute('data-snap', 'half'); await capture(page, 'mobile-hero-half');
  await page.locator('.sheet-handle').press('Home'); await capture(page, 'mobile-hero-full');
  await page.locator('.matrix-section').scrollIntoViewIfNeeded(); await capture(page, 'mobile-matrix-full');
  const matrix = await page.locator('.comparison-matrix').boundingBox(); expect(matrix && matrix.x >= 0 && matrix.x + matrix.width <= 320).toBe(true);
  expect(await page.locator('.matrix-scroll').evaluate(e => e.scrollWidth <= e.clientWidth)).toBe(true);
  await page.locator('.sheet-handle').press('ArrowDown'); await page.locator('.matrix-section').scrollIntoViewIfNeeded(); await capture(page, 'mobile-matrix-half');
  await page.locator('.sheet-handle').press('Home'); const option = page.getByRole('radio', { name: /Route 2/ }); await option.press('Space'); await expect(option).toHaveAttribute('aria-checked', 'true'); await option.press('End'); await page.keyboard.press('Enter'); await expect(page.getByRole('radio', { name: /Route 3/ })).toHaveAttribute('aria-checked', 'true');
  expect(await page.locator('.sheet-dock').evaluate(e => e.scrollTop)).toBe(0); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.emulateMedia({ reducedMotion: 'reduce' }); await expect(page.locator('.distance-bar')).toHaveCSS('animation-name', 'none');
  const context = await browser.newContext({ viewport: { width: 640, height: 480 }, deviceScaleFactor: 2 }); const zoom = await context.newPage(); await initialize(zoom); await synthetic(zoom, resultFixture()); await zoom.locator('.sheet-handle').press('Home'); await capture(zoom, 'zoom-200-percent'); expect(await zoom.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true); await context.close();
});
test.describe('explicit final real checks', () => {
  for (const [name, chip] of [['real-chicago-detroit', 'Chicago, IL to Detroit, MI'], ['real-santa-monica-la', 'Santa Monica Pier to Los Angeles City Hall']] as const) {
    test(name, async ({ page }) => {
      test.skip(process.env.ROUTESHIELD_REAL_RESULTS !== '1', 'Explicit final live check only.'); test.setTimeout(65000);
      await page.setViewportSize({ width: 1440, height: 1100 }); await initialize(page, false); await page.getByRole('button', { name: chip }).click(); await page.getByRole('button', { name: 'In 3 hours' }).click();
      let sends = 0; await page.route('**/api/v1/route-analysis/', route => ++sends === 1 ? route.continue() : route.abort());
      const started = Date.now(), pending = page.waitForResponse(r => r.url().endsWith('/route-analysis/') && r.request().method() === 'POST');
      await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); const http = await pending;
      if (http.status() !== 200) { console.log(JSON.stringify({ corridor: name, http: http.status(), wallMs: Date.now() - started, sends })); await capture(page, `${name}-error`); throw new Error('Live analysis returned an error; no retry.'); }
      const body = await http.json() as AnalysisResponse;
      console.log(JSON.stringify({ corridor: name, http: http.status(), status: body.recommendation_status, routeCount: body.route_count, wallMs: Date.now() - started, recommendedRoute: body.recommended_route_id, providerCalls: body.metadata.provider_calls }));
      await expect(page.getByRole('tab', { name: 'Results', exact: true })).toHaveAttribute('aria-selected', 'true'); await capture(page, name); await page.locator('.matrix-section').scrollIntoViewIfNeeded(); await capture(page, `${name}-matrix`); expect(sends).toBe(1);
    });
  }
});
