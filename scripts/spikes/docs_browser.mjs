// Existing project-local Playwright only; block requests outside official providers.
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
process.env.PLAYWRIGHT_BROWSERS_PATH = fileURLToPath(new URL('../../.cache/ms-playwright', import.meta.url));
const { chromium } = await import('../../frontend/node_modules/playwright/index.mjs');
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const requests = [];
await page.route('**/*', async route => {
  const host = new URL(route.request().url()).hostname;
  const allowed = host === 'open-meteo.com' || host.endsWith('.tomtom.com');
  if (!allowed) return route.abort();
  requests.push({ host, type: route.request().resourceType() });
  await route.continue();
});
const evidence = {};
try {
  for (const [label, url] of [['tomtom_terms', 'https://docs.tomtom.com/legal/terms-and-conditions'],
    ['pricing', 'https://open-meteo.com/en/pricing']]) {
    const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30_000 });
    await page.waitForTimeout(3000);
    const text = await page.locator('body').innerText();
    evidence[label] = { status: response.status(), text_length: text.length,
      inputs: await page.locator('input').evaluateAll(nodes => nodes.map(n => ({ id: n.id, type: n.type, value: n.value }))) };
    if (label === 'tomtom_terms') {
      console.log(JSON.stringify({ legal_read: text.split('\n').filter(s => /cach|storag|attribut|display|third.party map|Evaluation Use|Free|commercial|5\.3|5\.4|6\.1/i.test(s)) }));
      evidence[label].clause_signals = { readable: text.length > 40_000 };
      evidence[label].iframe_count = await page.locator('iframe').count();
    } else {
      const rows = page.locator('input[type=number]');
      evidence[label].number_inputs = await rows.count();
      await page.locator('input').nth(0).fill('4');
      await page.locator('input').nth(1).fill('3');
      await page.locator('input').nth(2).fill('1');
      await page.locator('input').nth(3).fill('300');
      await page.waitForTimeout(500);
      const updated = await page.locator('body').innerText();
      evidence[label].calculator_result = updated.match(/A request with the parameters selected below will cost[^\n]*/)?.[0];
      evidence[label].selected = await page.locator('input').evaluateAll(nodes => nodes.map(n => n.value));
      await page.screenshot({ path: fileURLToPath(new URL('./evidence/quota-calculator.png', import.meta.url)), fullPage: true });
    }
  }
} catch (error) {
  evidence.error = { type: error.name }; // No raw URL-bearing exceptions.
} finally {
  await browser.close();
}
evidence.documentation_requests = requests;
writeFileSync(new URL('./evidence/docs_browser.json', import.meta.url), JSON.stringify(evidence, null, 2));
console.log(JSON.stringify(evidence));
