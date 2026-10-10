// Official legal pages only, using the existing project-local browser installation.
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
process.env.PLAYWRIGHT_BROWSERS_PATH = fileURLToPath(new URL('../../.cache/ms-playwright', import.meta.url));
const { chromium } = await import('../../frontend/node_modules/playwright/index.mjs');
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const counts = {};
await page.route('**/*', route => {
  const host = new URL(route.request().url()).hostname;
  const allowed = host.endsWith('.tomtom.com') || ['openfreemap.org', 'account.heigit.org'].includes(host);
  if (!allowed) return route.abort();
  counts[host] = (counts[host] || 0) + 1;
  return route.continue();
});
const evidence = {};
try {
  for (const [label, url] of [['tomtom', 'https://docs.tomtom.com/legal/terms-and-conditions'],
    ['openfreemap', 'https://openfreemap.org/terms/'], ['ors', 'https://account.heigit.org/info/tos']]) {
    const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30_000 });
    await page.waitForTimeout(1500);
    const text = await page.locator('body').innerText();
    evidence[label] = { status: response.status(), text_length: text.length };
    // Read clauses to assess permissions; do not preserve wholesale copyrighted legal text.
    console.log(JSON.stringify({ label, relevant: text.split('\n').filter(s => label === 'tomtom'
      ? /^(2\.1|2\.2|11\.[1-5]|17\.3|23\.1)|Permitted Solution|Evaluation Use means|Free Use|free of charge/i.test(s)
      : /licen[cs]|commercial|cach|storag|attribut|terms|copyright|non.commercial|permitted/i.test(s)) }));
  }
} catch (error) { evidence.error = { type: error.name }; }
finally { await browser.close(); }
evidence.documentation_requests = counts;
writeFileSync(new URL('./evidence/terms_read.json', import.meta.url), JSON.stringify(evidence, null, 2));
console.log(JSON.stringify(evidence));
