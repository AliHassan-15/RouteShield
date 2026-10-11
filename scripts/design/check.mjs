// Dependency-free WCAG contrast + Machado 2009 full-deficiency simulation.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export const matrices = {
  protanopia: [[.152286, 1.052583, -.204868], [.114503, .786281, .099216], [-.003882, -.048116, 1.051998]],
  deuteranopia: [[.367322, .860646, -.227968], [.280085, .672501, .047413], [-.01182, .04294, .968881]],
  tritanopia: [[1.255528, -.076749, -.178779], [-.078411, .930809, .147602], [.004733, .691367, .3039]],
};
export const levels = ['low', 'moderate', 'high', 'severe', 'no-travel', 'unknown'];
export function linear(hex) {
  return hex.match(/[a-f\d]{2}/gi).map(x => {
    const c = parseInt(x, 16) / 255;
    return c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4;
  });
}
function luminance(rgb) { return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722; }
export function contrast(a, b) {
  const x = luminance(linear(a)), y = luminance(linear(b));
  return (Math.max(x, y) + .05) / (Math.min(x, y) + .05);
}
function lab([r, g, b]) {
  const l = Math.cbrt(.4122214708 * r + .5363325363 * g + .0514459929 * b);
  const m = Math.cbrt(.2119034982 * r + .6806995451 * g + .1073969566 * b);
  const s = Math.cbrt(.0883024619 * r + .2817188376 * g + .6299787005 * b);
  return [.2104542553 * l + .793617785 * m - .0040720468 * s, 1.9779984951 * l - 2.428592205 * m + .4505937099 * s, .0259040371 * l + .7827717662 * m - .808675766 * s];
}
function simulate(rgb, matrix) {
  return matrix.map(row => Math.max(0, Math.min(1, row.reduce((sum, n, i) => sum + n * rgb[i], 0))));
}
export function readTokens(css) {
  const blocks = [css.slice(css.indexOf(':root, [data-theme=\'light\']'), css.indexOf('[data-theme=\'dark\']')), css.slice(css.indexOf('[data-theme=\'dark\']'))];
  return blocks.map(block => Object.fromEntries([...block.matchAll(/--([\w-]+):\s*(#[a-f\d]{6}|var\(--[\w-]+\))/gi)].map(m => [m[1], m[2]])));
}
export function audit(css) {
  const failures = [], colors = [], differences = [];
  readTokens(css).forEach((tokens, themeIndex) => {
    const theme = themeIndex ? 'dark' : 'light';
    const resolve = key => tokens[key].startsWith('var') ? resolve(tokens[key].slice(6, -1)) : tokens[key];
    const backgrounds = ['canvas', 'surface', 'raised', 'inset'].map(resolve);
    levels.forEach(level => {
      const color = resolve('risk-' + level);
      const ratio = Math.min(...backgrounds.map(bg => contrast(color, bg)));
      colors.push({ theme, level, color, contrast: +ratio.toFixed(2) });
      if (ratio < 4.5) failures.push(theme + '/' + level + ': text contrast <4.5');
    });
    const ordered = levels.slice(0, 5).map(level => linear(resolve('risk-' + level)));
    for (const [vision, matrix] of Object.entries(matrices)) {
      const labs = ordered.map(rgb => lab(simulate(rgb, matrix)));
      for (let i = 1; i < labs.length; i++) {
        const a = labs[i - 1], b = labs[i];
        const delta = Math.hypot(...a.map((n, j) => n - b[j])) * 100;
        const lightness = (a[0] - b[0]) * 100;
        differences.push({ theme, vision, adjacent: levels[i - 1] + '/' + levels[i], delta: +delta.toFixed(2), lightness: +lightness.toFixed(2) });
        // Conservative engineering floor, not a clinical visibility guarantee.
        if (delta < 5 || lightness < 2) failures.push(theme + '/' + vision + ': adjacent colors too close');
      }
    }
  });
  return { colors, differences, failures };
}
if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const result = audit(readFileSync(new URL('../../frontend/src/styles/tokens.css', import.meta.url), 'utf8'));
  console.log(JSON.stringify(result, null, 2));
  process.exitCode = result.failures.length ? 1 : 0;
}
