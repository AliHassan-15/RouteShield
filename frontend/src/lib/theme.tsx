import { useEffect, useState } from 'react';
import { flushSync } from 'react-dom';
import { SegmentedControl } from '../components/controls';
import { transitionTheme, useMediaQuery, useReducedMotion } from './motion';

export type ThemePreference = 'system' | 'light' | 'dark';
export function readTheme(): ThemePreference {
  try { const saved = localStorage.getItem('routeshield-theme'); if (saved === 'light' || saved === 'dark') return saved; } catch { /* Denied storage falls back to system. */ }
  return 'system';
}
export function ThemeToggle() {
  const [preference, setPreference] = useState<ThemePreference>(readTheme);
  const dark = useMediaQuery('(prefers-color-scheme: dark)'), reduced = useReducedMotion();
  useEffect(() => { document.documentElement.dataset.theme = preference === 'system' ? (dark ? 'dark' : 'light') : preference; document.documentElement.dataset.themePreference = preference; }, [preference, dark]);
  const update = (value: string) => {
    if (value !== 'system' && value !== 'light' && value !== 'dark') return;
    try { localStorage.setItem('routeshield-theme', value); } catch { /* A usable toggle must not depend on storage. */ }
    transitionTheme(() => flushSync(() => setPreference(value)), reduced);
  };
  return <SegmentedControl label="Color theme" value={preference} onChange={update} compact options={[{ value: 'system', label: 'System theme', icon: 'system' }, { value: 'light', label: 'Light theme', icon: 'sun' }, { value: 'dark', label: 'Dark theme', icon: 'moon' }]} />;
}
