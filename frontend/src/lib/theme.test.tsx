import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { runInNewContext } from 'node:vm';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { ThemeToggle } from './theme';
import { useReducedMotion } from './motion';

beforeEach(() => localStorage.clear());
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function media(dark: boolean, reduced = false) { vi.stubGlobal('matchMedia', vi.fn((query: string) => ({ matches: query.includes('dark') ? dark : reduced, addEventListener: vi.fn(), removeEventListener: vi.fn() }))); }
test('theme follows system and persists explicit light, dark and system choices', () => {
  media(true); render(<ThemeToggle />); expect(document.documentElement.dataset.theme).toBe('dark');
  for (const value of ['light', 'dark', 'system']) { fireEvent.click(screen.getByRole('radio', { name: `${value[0]?.toUpperCase()}${value.slice(1)} theme` })); expect(localStorage.getItem('routeshield-theme')).toBe(value); expect(document.documentElement.dataset.theme).toBe(value === 'system' ? 'dark' : value); }
});
test('stored override survives a remount and denied storage remains usable', () => {
  media(false); localStorage.setItem('routeshield-theme', 'dark'); render(<ThemeToggle />); expect(document.documentElement.dataset.theme).toBe('dark'); cleanup();
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('Denied'); }); vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Denied'); }); render(<ThemeToggle />); fireEvent.click(screen.getByRole('radio', { name: 'Dark theme' })); expect(document.documentElement.dataset.theme).toBe('dark');
});
test('blocking script resolves before paint for every preference and storage denial', () => {
  const source = readFileSync(resolve(process.cwd(), 'public/theme-init.js'), 'utf8');
  for (const [saved, dark, expected] of [['light', true, 'light'], ['dark', false, 'dark'], ['system', true, 'dark'], ['invalid', false, 'light'], [null, true, 'dark']] as const) {
    const document = { documentElement: { dataset: {} as Record<string, string> } }; runInNewContext(source, { document, localStorage: { getItem: () => saved }, matchMedia: () => ({ matches: dark }) }); expect(document.documentElement.dataset.theme).toBe(expected);
  }
  const document = { documentElement: { dataset: {} as Record<string, string> } }; runInNewContext(source, { document, localStorage: { getItem: () => { throw Error(); } }, matchMedia: () => ({ matches: true }) }); expect(document.documentElement.dataset.theme).toBe('dark');
  const html = readFileSync(resolve(process.cwd(), 'index.html'), 'utf8'); expect(html.indexOf('theme-init.js')).toBeLessThan(html.indexOf('src/main.tsx')); expect(html).not.toMatch(/<script[^>]*>\s*[^<\s]/);
});
test('reduced-motion hook responds to changes and cleans its listener', () => {
  let reduced = false; const listeners = new Set<() => void>(); const remove = vi.fn((listener: () => void) => listeners.delete(listener));
  vi.stubGlobal('matchMedia', () => ({ get matches() { return reduced; }, addEventListener: (_name: string, listener: () => void) => listeners.add(listener), removeEventListener: (_name: string, listener: () => void) => remove(listener) }));
  function Probe() { return <output>{useReducedMotion() ? 'reduced' : 'full'}</output>; } render(<Probe />); expect(screen.getByText('full')).toBeTruthy(); act(() => { reduced = true; listeners.forEach(listener => listener()); }); expect(screen.getByText('reduced')).toBeTruthy(); cleanup(); expect(remove).toHaveBeenCalled(); expect(listeners.size).toBe(0);
});
