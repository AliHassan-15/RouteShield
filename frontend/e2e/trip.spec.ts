import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { analysisFixture, geocodeFixture, testDraft } from '../src/features/trip/test-fixtures';
import { encodeDraft } from '../src/features/trip/url';

const output = resolve(process.cwd(), '../output/playwright/trip');
test.use({ trace: 'off' }); // Live checks must never record provider response bodies.
async function capture(page: Page, name: string) {
  await mkdir(output, { recursive: true }); await page.evaluate(() => document.fonts.ready);
  await page.evaluate(async () => { await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))); await Promise.all(document.getAnimations().filter(a => a.effect instanceof KeyframeEffect && a.effect.pseudoElement?.startsWith('::view-transition')).map(a => a.finished.catch(() => {}))); });
  await page.screenshot({ path: resolve(output, `${name}.png`), animations: 'disabled' });
}
async function localOnly(page: Page) {
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    return ['localhost', '127.0.0.1'].includes(url.hostname) ? route.continue() : route.abort();
  });
  await page.addInitScript(() => { localStorage.clear(); localStorage.setItem('routeshield-theme', 'light'); });
}
async function mockHealth(page: Page) { await page.route('**/api/v1/health/', route => route.fulfill({ json: { status: 'ok', version: 'synthetic', check: 'liveness' } })); }
async function example(page: Page) { await page.getByRole('button', { name: 'Chicago, IL to Detroit, MI' }).click(); }
function error(code: string, details = {}) { return { error: { code, message: 'UNTRUSTED_BODY_NOT_FOR_UI', details } }; }

test('desktop trip states, keyboard combobox, exact request and safe recovery screenshots', async ({ page }) => {
  test.setTimeout(60000); await localOnly(page); await mockHealth(page); await page.setViewportSize({ width: 1440, height: 1000 });
  let searchMode = 'results', analysisMode = 'pending', sent = 0;
  await page.route('**/api/v1/geocode/?*', async route => {
    if (searchMode === 'loading') await new Promise(resolve => setTimeout(resolve, 1500));
    await route.fulfill(searchMode === 'error' ? { status: 503, json: error('PROVIDER_UNAVAILABLE') } : { json: geocodeFixture(searchMode === 'empty' ? 0 : 3) });
  });
  await page.route('**/api/v1/route-analysis/', async route => {
    sent++; const request = route.request().postDataJSON(); expect(request).not.toHaveProperty('checkpoint_interval_miles'); expect(request.origin.latitude).toBe(41.8781);
    if (analysisMode === 'pending') { await new Promise(resolve => setTimeout(resolve, 12000)); await route.fulfill({ json: analysisFixture() }).catch(() => {}); }
    else if (analysisMode === 'throttle') await route.fulfill({ status: 429, headers: { 'Retry-After': '3', 'X-Request-ID': 'synthetic-throttle', 'Access-Control-Expose-Headers': 'X-Request-ID, Retry-After' }, json: error('THROTTLED') });
    else if (analysisMode === 'large') await route.fulfill({ status: 422, headers: { 'X-Request-ID': 'synthetic-too-large', 'Access-Control-Expose-Headers': 'X-Request-ID, Retry-After' }, json: error('TRIP_TOO_LARGE', { max_distance_miles: 300 }) });
    else await route.fulfill({ json: analysisFixture() });
  });
  await page.goto('/'); await expect(page.locator('.header-service')).toContainText('healthy');
  await capture(page, 'empty-desktop-light'); await page.getByRole('radio', { name: 'Dark theme' }).click(); await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark'); await capture(page, 'empty-desktop-dark'); await page.getByRole('radio', { name: 'Light theme' }).click(); await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  const origin = page.getByRole('combobox', { name: 'Origin' }); await origin.fill('Chicago'); await expect(page.getByRole('option')).toHaveCount(3); await capture(page, 'combobox-results');
  await origin.press('End'); await expect(origin).toHaveAttribute('aria-activedescendant', /option-2$/); await origin.press('ArrowDown'); await origin.press('Enter'); await expect(origin).toHaveValue('Chicago West');
  searchMode = 'loading'; await origin.fill('Detroit'); await expect(page.getByText('Finding matches…')).toBeVisible(); await capture(page, 'combobox-loading'); await expect(page.getByRole('option')).toHaveCount(3);
  searchMode = 'empty'; await origin.fill('Nowhere'); await expect(page.getByText('No matches. Try a city, address or place name.')).toBeVisible(); await capture(page, 'combobox-empty');
  searchMode = 'error'; await origin.fill('Failure'); await expect(page.getByRole('button', { name: 'Retry search' })).toBeVisible(); await capture(page, 'combobox-error');
  searchMode = 'results'; await page.getByRole('button', { name: 'Retry search' }).click(); await expect(page.getByRole('option')).toHaveCount(3); await origin.press('Tab'); await expect(origin).toHaveValue('Failure'); await origin.press('Escape');
  await example(page); await page.getByLabel('Cargo weight', { exact: true }).scrollIntoViewIfNeeded(); await expect(page.locator('.threshold-tick.is-active')).toHaveCount(2); await capture(page, 'filled-load-active');
  await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); await expect(page.getByText('9s', { exact: true })).toBeVisible({ timeout: 11000 }); await capture(page, 'pending-elapsed'); await page.getByRole('button', { name: 'Cancel', exact: true }).click(); await expect(page.getByLabel('Analysis error')).toHaveCount(0);
  analysisMode = 'throttle'; await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); await page.getByLabel('Analysis error').scrollIntoViewIfNeeded(); await expect(page.getByText('3s', { exact: true })).toBeVisible(); await capture(page, 'throttled'); await expect(page.getByRole('button', { name: 'Analyze routes', exact: true })).toBeEnabled({ timeout: 5000 }); expect(sent).toBe(2);
  analysisMode = 'large'; await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); await page.getByLabel('Analysis error').scrollIntoViewIfNeeded(); await expect(page.getByLabel('Analysis error')).toContainText('300 road miles'); await capture(page, 'trip-too-large'); expect(await page.locator('body').textContent()).not.toContain('UNTRUSTED');
  analysisMode = 'success'; await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); await page.getByLabel('Analysis summary').scrollIntoViewIfNeeded(); await expect(page.getByLabel('Analysis summary')).toContainText('3 routes returned'); await capture(page, 'synthetic-summary'); expect(sent).toBe(4);
});

test('fixed browser zone exposes gaps and overlaps with explicit keyboard choices', async ({ browser }) => {
  const context = await browser.newContext({ timezoneId: 'America/New_York', viewport: { width: 1440, height: 1000 } }); const page = await context.newPage(); await localOnly(page); await mockHealth(page);
  await page.clock.install({ time: new Date('2026-03-07T12:00:00Z') }); await page.goto('/');
  await page.getByLabel('Date', { exact: true }).fill('2026-03-08'); await page.getByLabel('Time', { exact: true }).fill('02:30'); await page.locator('.time-notice').scrollIntoViewIfNeeded(); await capture(page, 'dst-gap');
  await page.getByRole('button', { name: 'Move to 03:00' }).click(); await expect(page.getByLabel('Time', { exact: true })).toHaveValue('03:00');
  await page.clock.setFixedTime(new Date('2026-10-31T12:00:00Z'));
  await page.getByLabel('Date', { exact: true }).fill('2026-11-01'); await page.getByLabel('Time', { exact: true }).fill('01:30'); await page.locator('.time-notice').scrollIntoViewIfNeeded(); await capture(page, 'dst-fold');
  const earlier = page.getByRole('radio', { name: 'Earlier · UTC-04:00' }); await expect(earlier).toHaveAttribute('tabindex', '0'); await earlier.focus(); await page.keyboard.press('ArrowRight'); await expect(page.getByRole('radio', { name: 'Later · UTC-05:00' })).toHaveAttribute('aria-checked', 'true'); await expect(page.locator('.zone-readout')).toContainText('2026-11-01T06:30:00Z'); await context.close();
});

test('mobile sheet, keyboard cancel, 320px and 200% zoom reflow remain usable', async ({ page, browser }) => {
  await localOnly(page); await mockHealth(page); await page.setViewportSize({ width: 320, height: 844 });
  let hold = true;
  await page.route('**/api/v1/route-analysis/', async route => { if (hold) await new Promise(resolve => setTimeout(resolve, 10000)); await route.fulfill({ json: analysisFixture() }).catch(() => {}); });
  await page.goto('/'); const handle = page.locator('.sheet-handle'); await handle.focus(); await page.keyboard.press('ArrowUp'); await expect(page.locator('.bottom-sheet')).toHaveAttribute('data-snap', 'half'); await capture(page, 'mobile-half');
  await handle.press('Home'); await example(page); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); await expect(page.locator('.bottom-sheet')).toHaveAttribute('data-snap', 'peek'); await capture(page, 'mobile-progress-peek'); await expect(handle).toBeFocused(); await page.keyboard.press('Tab'); await expect(page.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused(); await page.keyboard.press('Enter');
  hold = false; await handle.press('Home'); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click(); await expect(page.locator('.bottom-sheet')).toHaveAttribute('data-snap', 'half');
  await handle.press('Home'); await page.getByLabel('Cargo weight', { exact: true }).scrollIntoViewIfNeeded(); await capture(page, 'mobile-full-load');
  await expect(handle).toBeInViewport(); expect(await page.locator('.sheet-dock').evaluate(e => e.scrollTop)).toBe(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  // Browser zoom reflows at half the CSS viewport. Device scale 2 records the
  // same 1280x960 physical pixels without substituting CSS transform/pinch zoom.
  const zoomContext = await browser.newContext({ viewport: { width: 640, height: 480 }, deviceScaleFactor: 2 }); const zoomPage = await zoomContext.newPage(); await localOnly(zoomPage); await mockHealth(zoomPage); await zoomPage.goto('/'); await zoomPage.locator('.sheet-handle').press('Home'); await example(zoomPage); await zoomPage.getByLabel('Cargo weight', { exact: true }).scrollIntoViewIfNeeded(); await capture(zoomPage, 'zoom-200-percent');
  expect(await zoomPage.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false); const action = await zoomPage.getByRole('button', { name: 'Analyze routes', exact: true }).boundingBox(); expect(action && action.x >= 0 && action.x + action.width <= 640 && action.y + action.height <= 480).toBe(true); await zoomContext.close();
  await page.emulateMedia({ reducedMotion: 'reduce' }); await expect(page.locator('.trip-section').first()).toHaveCSS('animation-name', 'none');
  await page.goto('/?' + encodeDraft({ ...testDraft(), wall: { date: '2020-01-01', time: '15:00' } })); await handle.press('Home'); await expect(page.getByText("This link's departure time has passed. Update it to analyze.")).toBeVisible();
  await page.route('**/api/v1/health/', route => route.fulfill({ status: 503, json: {} })); await page.clock.install(); await page.goto('/'); await expect(page.locator('.header-service')).toContainText('Checking'); await page.clock.fastForward(91000); await expect(page.locator('.header-service')).toContainText('unreachable'); await capture(page, 'mobile-unreachable'); expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
});

test.describe('explicit optional real local-API check', () => {
  test('Chicago to Detroit real analysis, no retry and no response-body artifact', async ({ page }) => {
    test.skip(process.env.ROUTESHIELD_REAL_ANALYSIS !== '1', 'Explicit final live check only.'); test.setTimeout(60000);
    await localOnly(page); await page.setViewportSize({ width: 1440, height: 1000 });
    let sends = 0;
    await page.route('**/api/v1/route-analysis/', route => { sends++; return sends === 1 ? route.continue() : route.abort(); });
    await page.goto('/'); await expect(page.locator('.header-service')).toContainText('API healthy', { timeout: 10000 }); await example(page); await page.getByRole('button', { name: 'In 3 hours' }).click();
    const start = Date.now(); const responsePromise = page.waitForResponse(r => r.url().includes('/api/v1/route-analysis/') && r.request().method() === 'POST'); await page.getByRole('button', { name: 'Analyze routes', exact: true }).click();
    const response = await responsePromise; const wallMs = Date.now() - start;
    if (response.ok()) {
      const summary = page.getByLabel('Analysis summary'); await expect(summary).toBeVisible(); await summary.scrollIntoViewIfNeeded(); await capture(page, 'real-chicago-detroit');
      const body = await response.json(); console.log(JSON.stringify({ liveCheck: 'Chicago–Detroit +3h, 45000 lb', httpStatus: response.status(), status: body.recommendation_status, routeCount: body.route_count, wallMs, requestId: body.metadata.request_id, providerCalls: body.metadata.provider_calls }));
    } else { await page.getByLabel('Analysis error').scrollIntoViewIfNeeded(); await capture(page, 'real-chicago-detroit-error'); console.log(JSON.stringify({ liveCheck: 'Chicago–Detroit', httpStatus: response.status(), wallMs, sends })); }
    expect(sends).toBe(1); expect(response.ok()).toBe(true);
  });
});
