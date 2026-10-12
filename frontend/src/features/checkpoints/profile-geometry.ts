import type { Checkpoint, Route } from '../../api/types';
import { displayNumber, time } from '../../lib/format';
import { visibleLow } from '../map/geometry';
export type Variable = 'wind' | 'rain' | 'snow';
export const SERIES = { wind: { label: 'Wind', unit: 'mph', value: 'wind_mph', risk: 'wind_risk' }, rain: { label: 'Rain', unit: 'in/hr', value: 'rain_in_hr', risk: 'rain_risk' }, snow: { label: 'Snow', unit: 'in/hr', value: 'snow_in_hr', risk: 'snow_risk' } } as const;
export const xPosition = (mile: number, total: number) => 36 + Math.max(0, Math.min(1, total > 0 ? mile / total : 0)) * 312;
export function niceStep(value: number) { if (!(value > 0)) return 1; const power = 10 ** Math.floor(Math.log10(value)), fraction = value / power; return (fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10) * power; }
export function distanceTicks(total: number) { const major = niceStep(total / 4), minor = niceStep(major / 5); return { major, minor, labels: Array.from({ length: Math.floor(total / major) + 1 }, (_, i) => i * major), ticks: Array.from({ length: Math.min(60, Math.floor(total / minor) + 1) }, (_, i) => i * minor) }; }
export function yScale(values: (number | null)[]) { const max = Math.max(0, ...values.filter((v): v is number => v !== null)), step = niceStep((max || 1) * 1.15 / 4), ceiling = Math.ceil((max || 1) * 1.15 / step) * step; return { ceiling, ticks: Array.from({ length: Math.round(ceiling / step) + 1 }, (_, i) => i * step), y: (value: number) => 182 - value / ceiling * 102 }; }
export function seriesPoints(route: Route, variable: Variable) { const spec = SERIES[variable]; return route.checkpoints.map(cp => ({ cp, mile: displayNumber(cp.mile_marker) ?? 0, value: displayNumber(cp.weather.values[spec.value]), level: cp.risk[spec.risk] })); }
export function gapPaths(points: { mile: number; value: number | null }[], total: number, y: (v: number) => number) { let open = false; return points.map(p => { if (p.value === null) { open = false; return ''; } const command = open ? 'L' : 'M'; open = true; return `${command}${xPosition(p.mile, total)},${y(p.value)}`; }).join(' '); }
export function nearestCheckpoint(points: Checkpoint[], mile: number) { return points.reduce<Checkpoint | undefined>((best, cp) => Math.abs((displayNumber(cp.mile_marker) ?? 0) - mile) < Math.abs((displayNumber(best?.mile_marker) ?? Infinity) - mile) ? cp : best, points[0]); }
// Interpolate existing UTC ETAs for axis labels only. Never create sampling ETAs.
export function etaLabel(points: Checkpoint[], mile: number) {
  const found = points.findIndex(cp => (displayNumber(cp.mile_marker) ?? 0) >= mile), right = found < 0 ? points.length - 1 : found, hi = points[right], lo = points[Math.max(0, right - 1)];
  if (!hi || !lo) return 'n/a';
  const a = displayNumber(lo.mile_marker) ?? 0, b = displayNumber(hi.mile_marker) ?? 0, fraction = b > a ? Math.max(0, Math.min(1, (mile - a) / (b - a))) : 0;
  const instant = Date.parse(lo.eta_utc) + fraction * (Date.parse(hi.eta_utc) - Date.parse(lo.eta_utc));
  return Number.isFinite(instant) ? time(new Date(instant).toISOString(), hi.utc_fallback || !hi.timezone ? 'UTC' : hi.timezone) : 'n/a';
}
export const profileMarkerVisible = (cp: Checkpoint, width: number, count: number) => cp.risk.final_risk !== 'LOW' || visibleLow(cp.index, width / Math.max(1, count) < 24 ? 6 : 7);
