import { defineConfig } from '@playwright/test';
import { fileURLToPath } from 'node:url';

process.env.PLAYWRIGHT_BROWSERS_PATH ??= fileURLToPath(new URL('../.cache/ms-playwright', import.meta.url));

export default defineConfig({
  testDir: './e2e',
  outputDir: '../output/playwright/test-results',
  use: { baseURL: 'http://127.0.0.1:5173', headless: true, trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
