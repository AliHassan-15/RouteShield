import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { expect, test } from 'vitest';
import { colors } from '../dev/contrast-data';

test('risk tokens pass contrast/CVD floors and guide values match measured output', () => {
  const report = JSON.parse(execFileSync(process.execPath, [resolve(process.cwd(), '../scripts/design/check.mjs')], { encoding: 'utf8' })) as { failures: string[]; colors: typeof colors; differences: { delta: number; lightness: number }[] };
  expect(report.failures).toEqual([]); expect(report.colors).toEqual(colors); expect(Math.min(...report.colors.map(c => c.contrast))).toBeGreaterThanOrEqual(4.5); expect(Math.min(...report.differences.map(c => c.delta))).toBeGreaterThanOrEqual(5);
});
test('contrast guard fails a pale risk-color mutation', () => {
  const script = `import {readFileSync} from 'node:fs'; import {audit} from ${JSON.stringify(pathToFileURL(resolve(process.cwd(), '../scripts/design/check.mjs')).href)}; const css=readFileSync(${JSON.stringify(resolve(process.cwd(), 'src/styles/tokens.css'))},'utf8').replace('--risk-low: #407554','--risk-low: #ffffff'); console.log(JSON.stringify(audit(css).failures));`;
  const failures: unknown = JSON.parse(execFileSync(process.execPath, ['--input-type=module', '-e', script], { encoding: 'utf8' })); expect(failures).toContain('light/low: text contrast <4.5');
});
test('production guard is a compile-time dev branch and motion only transitions transform/opacity', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8'); expect(source).toContain("import.meta.env.DEV ? lazy(() => import('./dev/StyleGuide')) : null");
  const motion = readFileSync(resolve(process.cwd(), 'src/styles/motion.css'), 'utf8'); expect(motion).toContain('prefers-reduced-motion: reduce'); expect(motion).not.toMatch(/transition:.*(?:width|height|top|left|padding|margin)/); expect(motion).not.toContain('transition: all');
});
