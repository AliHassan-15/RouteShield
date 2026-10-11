import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

const output = resolve(process.cwd(), '../output/playwright/design');
async function capture(page: Page, name: string, fullPage = false) {
  await mkdir(output, { recursive: true });
  await page.screenshot({ path: resolve(output, `${name}.png`), fullPage, animations: 'disabled' });
}
async function theme(page: Page, value: 'light' | 'dark') {
  await page.addInitScript(value => localStorage.setItem('routeshield-theme', value), value);
}
async function settled(page: Page) {
  await page.evaluate(async () => { await document.fonts.ready; });
  await expect(page.locator('html')).not.toHaveCSS('font-family', '');
}

test('native keyboard controls, popover, tabs, toast and reduced motion', async ({ page }) => {
  await theme(page, 'light');
  await page.goto('/style-guide');
  const primary = page.getByRole('button', { name: 'Analyze trip', exact: true });
  await primary.focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('status').filter({ hasText: 'Example action activated' })).toBeVisible();
  const dismiss = page.getByRole('button', { name: 'Dismiss notification' });
  await dismiss.focus(); await page.keyboard.press('Space');
  await expect(dismiss).toHaveCount(0);
  const origin = page.getByLabel('Origin example');
  await origin.focus(); await page.keyboard.type('Keyboard input');
  await expect(origin).toHaveValue('Keyboard input');
  const select = page.getByLabel('Checkpoint spacing example');
  await select.focus(); await page.keyboard.press('Home'); await page.keyboard.press('ArrowDown'); await page.keyboard.press('Enter');
  await expect(select).toHaveValue('25');
  const slider = page.getByRole('slider', { name: 'Forecast control example' });
  await slider.focus(); await page.keyboard.press('ArrowRight');
  await expect(slider).toHaveValue('13');
  const choice = page.getByRole('radiogroup', { name: 'Spacing example' });
  await choice.getByRole('radio', { name: '25 mi' }).focus(); await page.keyboard.press('End');
  await expect(choice.getByRole('radio', { name: '50 mi' })).toBeFocused();
  await expect(choice.getByRole('radio', { name: '50 mi' })).toHaveAttribute('aria-checked', 'true');
  const tab = page.getByRole('tab', { name: 'Routes', exact: true });
  await tab.focus(); await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab', { name: 'Checkpoints' })).toBeFocused();
  const trigger = page.getByRole('button', { name: 'Popover example', exact: true });
  await trigger.focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape'); await expect(trigger).toBeFocused();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(primary).toHaveCSS('transition-duration', '0s');
  await expect(page.locator('.skeleton').first()).toHaveCSS('animation-name', 'none');
});

test('mobile sheet snaps, drag, skip link and advisory stay accessible', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 }); await theme(page, 'light');
  await page.goto('/'); await expect(page.locator('.header-service')).toContainText('API healthy'); await settled(page);
  const handle = page.locator('.sheet-handle');
  await capture(page, 'mobile-light-peek');
  await handle.focus(); await page.keyboard.press('ArrowUp');
  await expect(page.locator('.bottom-sheet')).toHaveAttribute('data-snap', 'half');
  await capture(page, 'mobile-light-half');
  await page.keyboard.press('Home'); await expect(page.locator('.bottom-sheet')).toHaveAttribute('data-snap', 'full');
  await capture(page, 'mobile-light-full');
  const box = await handle.boundingBox();
  if (!box) throw new Error('Sheet handle not rendered');
  await page.mouse.move(box.x + 100, box.y + 30); await page.mouse.down();
  await page.mouse.move(box.x + 100, box.y + 400, { steps: 8 }); await page.mouse.up();
  await expect(page.locator('.bottom-sheet')).toHaveAttribute('data-snap', 'half');
  await handle.focus(); await page.keyboard.press('Escape');
  const skip = page.getByRole('link', { name: 'Skip to console' });
  await skip.focus(); await page.keyboard.press('Enter');
  await expect(page.locator('.bottom-sheet')).toHaveAttribute('data-snap', 'full');
  await expect(page.locator('.sheet-content')).toBeFocused();
  await page.keyboard.press('Escape'); await expect(handle).toBeFocused();
  const layout = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth > innerWidth, advisoryVisible: !!document.elementFromPoint(24, innerHeight - 25)?.closest('.map-attribution') }));
  expect(layout).toEqual({ overflow: false, advisoryVisible: true });
  await page.getByRole('radio', { name: 'Dark theme' }).click(); await settled(page);
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await capture(page, 'mobile-dark');
});

test('desktop, guide and truthful failure-state screenshot evidence', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 }); await theme(page, 'light');
  await page.addInitScript(() => {
    const shifts: number[] = [];
    Object.defineProperty(window, 'designShifts', { value: shifts });
    new PerformanceObserver(list => { for (const entry of list.getEntries()) if (!('hadRecentInput' in entry) || !entry.hadRecentInput) shifts.push((entry as PerformanceEntry & { value: number }).value); }).observe({ type: 'layout-shift', buffered: true });
  });
  await page.goto('/'); await expect(page.locator('.header-service')).toContainText('API healthy'); await settled(page);
  await capture(page, 'desktop-light');
  console.log('Shell layout shifts:', await page.evaluate(() => (window as Window & { designShifts?: number[] }).designShifts));
  await page.getByRole('radio', { name: 'Dark theme' }).click(); await settled(page); await capture(page, 'desktop-dark');
  await page.goto('/style-guide'); await settled(page); await capture(page, 'style-guide-light', true);
  await page.getByRole('radio', { name: 'Dark theme' }).click(); await settled(page); await capture(page, 'style-guide-dark', true);
  await page.locator('#risk').scrollIntoViewIfNeeded(); await capture(page, 'style-guide-risk-dark');
  await page.getByRole('button', { name: 'Preview global error fallback' }).click();
  await expect(page.getByRole('heading', { name: 'Restore your workspace' })).toBeVisible(); await capture(page, 'error-fallback');
  // Browser-only local-health delay exercises startup states without provider traffic.
  await page.route('**/api/v1/health/', async route => { await new Promise(resolve => setTimeout(resolve, 2500)); await route.fulfill({ status: 503, contentType: 'application/json', body: '{}' }); });
  await page.goto('/'); await expect(page.locator('.header-service')).toContainText('Checking API'); await capture(page, 'loading-skeletons');
  await expect(page.locator('.header-service')).toContainText('Waking up'); await capture(page, 'waking-up');
});
