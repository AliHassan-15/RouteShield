import { expect, test } from '@playwright/test';

test('the shell displays live backend health', async ({ page }) => {
  const health = page.waitForResponse(response =>
    response.url().endsWith('/api/v1/health/') && response.status() === 200,
  );
  await page.goto('/');
  const response = await health;
  expect(await response.json()).toMatchObject({ status: 'ok', version: '0.1.0' });
  await expect(page.getByRole('status')).toHaveText('Healthy — version 0.1.0');
  await page.screenshot({ path: '../output/playwright/health.png', fullPage: true });
});
