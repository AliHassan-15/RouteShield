import { readdir, readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { gzipSync } from 'node:zlib';

const root = resolve(process.cwd(), 'dist');
const files = await readdir(resolve(root, 'assets'));
const html = await readFile(resolve(root, 'index.html'), 'utf8');
let jsGzipBytes = 0, lazyMapGzipBytes = 0, checkpointGzipBytes = 0, fontBytes = 0, fonts = 0;
for (const name of files) {
  const bytes = await readFile(resolve(root, 'assets', name));
  if (/\.(js|css)$/.test(name) && /STYLE_GUIDE_ONLY|palette-reference|Example action activated|Every mile, assessed/.test(bytes.toString())) throw new Error(`Development specimen leaked: ${name}`);
  if (/\.(m?js)$/.test(name)) { if (/maplibre|worker/.test(name)) lazyMapGzipBytes += gzipSync(bytes).length; else if (/CheckpointViews/.test(name)) checkpointGzipBytes += gzipSync(bytes).length; else jsGzipBytes += gzipSync(bytes).length; if (bytes.toString().includes('__routeShieldMap')) throw new Error('E2E map hook leaked into production'); }
  if (name.endsWith('.woff2')) { fontBytes += bytes.length; fonts++; }
}
if (jsGzipBytes > 200_000) throw new Error('JavaScript exceeds 200 KB gzip');
if (fontBytes > 90_000 || fonts !== 2) throw new Error('Expected exactly two fonts within 90 KB');
const preloads = [...html.matchAll(/<link[^>]*rel="preload"[^>]*>/g)];
if (preloads.length !== 1 || !preloads[0][0].includes('woff2')) throw new Error('Preload only the primary sans');
const href = preloads[0][0].match(/href="([^"]+)"/)?.[1];
if (!href) throw new Error('Missing preload path');
await readFile(resolve(root, href.replace(/^\//, '')));
if (html.indexOf('theme-init.js') < 0 || html.indexOf('theme-init.js') > html.indexOf('type="module"')) throw new Error('Theme bootstrap must block before application execution');
console.log(JSON.stringify({ jsGzipBytes, lazyMapGzipBytes, checkpointGzipBytes, fontBytes, fonts, developmentGuideExcluded: true, primaryFontPreloadValid: true, themeBootstrapFirst: true }));
