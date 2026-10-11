import type { SVGProps } from 'react';

const paths = {
  search: 'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z',
  swap: 'M3 7h18l-4-4M21 17H3l4 4',
  clock: 'M12 8v4l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
  weight: 'M8 6h8l4 15H4L8 6ZM9 6V4a3 3 0 0 1 6 0v2',
  route: 'M6 6v8a4 4 0 0 0 8 0V8a4 4 0 0 1 4-4M8 4a2 2 0 1 1-4 0 2 2 0 0 1 4 0ZM20 4l-2 3-2-3',
  checkpoint: 'M12 2v20M2 12h20M18 12a6 6 0 1 1-12 0 6 6 0 0 1 12 0Z',
  wind: 'M3 7h13a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 17h5a3 3 0 1 1-3 3',
  rain: 'M7 13a5 5 0 1 1 1-9 6 6 0 0 1 11 5 3 3 0 0 1-1 6M7 17l-1 3M13 17l-1 3M19 17l-1 3',
  snow: 'M12 2v20M3 7l18 10M3 17 21 7M9 4l3 3 3-3M9 20l3-3 3 3',
  warning: 'M12 3 2 21h20L12 3ZM12 9v5M12 17v1',
  check: 'M4 12l5 5L20 6',
  close: 'm6 6 12 12M18 6 6 18',
  'chevron-down': 'm6 9 6 6 6-6',
  'chevron-up': 'm6 15 6-6 6 6',
  'chevron-right': 'm9 6 6 6-6 6',
  play: 'm8 4 13 8L8 20V4Z',
  pause: 'M8 4v16M16 4v16',
  layers: 'm12 2 10 6-10 6L2 8l10-6ZM2 12l10 6 10-6M2 16l10 6 10-6',
  sun: 'M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1 1M18 18l1 1M5 19l1-1M18 6l1-1M17 12a5 5 0 1 1-10 0 5 5 0 0 1 10 0Z',
  moon: 'M20 16A9 9 0 0 1 8 4a9 9 0 1 0 12 12Z',
  system: 'M3 4h18v13H3V4ZM8 21h8M12 17v4',
  info: 'M12 11v6M12 7v1M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
  location: 'M12 22s8-8 8-13A8 8 0 0 0 4 9c0 5 8 13 8 13ZM15 9a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z',
  truck: 'M2 6h12v12H2V6ZM14 10h4l4 5v3h-8M8 18a2 2 0 1 1-4 0 2 2 0 0 1 4 0ZM20 18a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z',
  refresh: 'M20 8V3l-4 4M4 16v5l4-4M20 8A9 9 0 0 0 4 6M4 16a9 9 0 0 0 16 2',
  external: 'M14 3h7v7M21 3 10 14M10 3H3v18h18v-7',
  grip: 'M8 7h8M8 12h8M8 17h8',
  'risk-low': 'M20 12a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z',
  'risk-moderate': 'm12 2 10 10-10 10L2 12 12 2Z',
  'risk-high': 'M12 3 2 21h20L12 3Z',
  'risk-severe': 'M4 4h16v16H4V4Z',
  'risk-no-travel': 'M8 2h8l6 6v8l-6 6H8l-6-6V8l6-6ZM8 8l8 8M16 8l-8 8',
  'risk-unknown': 'M20 12a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z',
};
export type IconName = keyof typeof paths;
export const iconNames = Object.keys(paths) as IconName[];
export function Icon({ name, ...props }: SVGProps<SVGSVGElement> & { name: IconName }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...props}><path d={paths[name]} strokeDasharray={name === 'risk-unknown' ? '3 3' : undefined} /></svg>;
}
export function Brand() {
  return <a className="brand" href="/" aria-label="RouteShield home"><svg viewBox="0 0 28 32" width="27" height="31" fill="none" aria-hidden="true"><path d="M14 2 25 6v11c0 6-6 10-11 13C9 27 3 23 3 17V6L14 2Z" stroke="currentColor" strokeWidth="1.6" /><path d="M10 23v-8a4 4 0 0 1 8 0V9M15 9h6" stroke="currentColor" strokeWidth="1.7" /><circle cx="10" cy="24" r="1.5" fill="currentColor" /></svg><span>Route<span className="brand-light">Shield</span></span></a>;
}
