import type { Position, Route, RiskLevel } from '../../api/types';
import type { Padding } from './contracts';
import { displayNumber } from '../../lib/format';
import { riskPresentation } from '../../components/surfaces';

export const validPosition = (p: unknown): p is Position => Array.isArray(p) && p.length === 2 && p.every(v => typeof v === 'number' && Number.isFinite(v)) && Math.abs(p[0]) <= 180 && Math.abs(p[1]) <= 90;
export const validGeometry = (points: unknown): points is Position[] => Array.isArray(points) && points.length >= 2 && points.every(validPosition);
const distance = (a: Position, b: Position) => {
  const rad = Math.PI / 180, lat = (b[1] - a[1]) * rad, lon = (b[0] - a[0]) * rad;
  return 2 * Math.asin(Math.min(1, Math.sqrt(Math.sin(lat / 2) ** 2 + Math.cos(a[1] * rad) * Math.cos(b[1] * rad) * Math.sin(lon / 2) ** 2)));
};
export function measureLine(points: Position[]) {
  const cumulative = [0];
  for (let i = 1; i < points.length; i++) cumulative.push(cumulative[i - 1]! + distance(points[i - 1]!, points[i]!));
  return { points, cumulative, total: cumulative.at(-1) ?? 0 };
}
export type MeasuredLine = ReturnType<typeof measureLine>;
export function pointAt(line: MeasuredLine, fraction: number): Position | null {
  if (!line.points.length) return null;
  if (!line.total) return line.points[0]!;
  const target = Math.max(0, Math.min(1, fraction)) * line.total;
  let lo = 1, hi = line.points.length - 1;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (line.cumulative[mid]! < target) lo = mid + 1; else hi = mid; }
  const a = line.points[lo - 1]!, b = line.points[lo]!, span = line.cumulative[lo]! - line.cumulative[lo - 1]!;
  const t = span ? (target - line.cumulative[lo - 1]!) / span : 0;
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
}
// Display calibration only: API-owned miles / total maps onto real geometry
// chainage, preserving bends/endpoints and small provider-length discrepancies.
export function sliceMiles(line: MeasuredLine, start: number, end: number, providerMiles: number): Position[] {
  if (!(providerMiles > 0) || end <= start || !line.points.length) return [];
  const first = pointAt(line, start / providerMiles), last = pointAt(line, end / providerMiles);
  if (!first || !last) return [];
  return [first, ...line.points.filter((_, i) => line.cumulative[i]! > start / providerMiles * line.total && line.cumulative[i]! < end / providerMiles * line.total), last];
}
export function prepareRoute(route: Route) {
  const valid = validGeometry(route.geometry);
  const line = measureLine(valid ? route.geometry : []), total = displayNumber(route.summary.total_miles) ?? 0;
  let start = 0;
  const segments = route.checkpoints.map(cp => {
    const end = start + Math.max(0, displayNumber(cp.owned_miles) ?? 0);
    const segment = { index: cp.index, level: cp.risk.final_risk, coordinates: sliceMiles(line, start, end, total), start, end, pattern: cp.risk.final_risk === 'UNKNOWN' || cp.risk.final_risk === 'NO_TRAVEL' };
    start = end; return segment;
  });
  return { route, line, segments, valid: valid && line.total > 0 && total > 0 };
}
export const markerEncoding = (level: RiskLevel) => ({ ...riskPresentation[level], size: { LOW: 12, MODERATE: 14, HIGH: 17, SEVERE: 19, NO_TRAVEL: 22, UNKNOWN: 19 }[level], priority: { LOW: 1, MODERATE: 2, HIGH: 3, SEVERE: 4, NO_TRAVEL: 5, UNKNOWN: 6 }[level], collision: level === 'LOW' || level === 'MODERATE' });
// Below zoom 7 retain every fourth Low; dangerous/unknown points always survive.
export const visibleLow = (index: number, zoom: number) => zoom >= 7 || index % 4 === 0;
// Keep both neutral traces outside the selected 10 px casing on shared roads.
export const routeOffset = (index: number, selected: number) => index === selected ? 0 : [0, 1, 2].filter(i => i !== selected).indexOf(index) === 0 ? -7 : 7;
export const outsideViewport = (p: { x: number; y: number }, width: number, height: number, padding: Padding) => p.x < padding.left || p.x > width - padding.right || p.y < padding.top || p.y > height - padding.bottom;
export function cameraPadding(width: number, height: number, consoleWidth: number, sheetHeight = 0, footerHeight = 88): Padding {
  return { left: width <= 760 ? 24 : consoleWidth + 24, right: width <= 760 ? 72 : 40, top: width <= 760 ? 72 : 24, bottom: Math.max(24, Math.min(height - 100, footerHeight + sheetHeight + 24)) };
}
export function bounds(points: Position[]): [Position, Position] | null {
  const good = points.filter(validPosition); if (!good.length) return null;
  let west = Infinity, east = -Infinity, south = Infinity, north = -Infinity;
  for (const p of good) { west = Math.min(west, p[0]); east = Math.max(east, p[0]); south = Math.min(south, p[1]); north = Math.max(north, p[1]); }
  const dx = Math.max(.005, east - west), dy = Math.max(.005, north - south), cx = (east + west) / 2, cy = (north + south) / 2;
  return [[cx - dx / 2, Math.max(-85, cy - dy / 2)], [cx + dx / 2, Math.min(85, cy + dy / 2)]];
}
export function placeChips(items: { id: string; x: number; y: number; selected: boolean; width?: number; height?: number }[]) {
  const visible: typeof items = [];
  for (const item of [...items].sort((a, b) => Number(b.selected) - Number(a.selected))) if (!visible.some(p => Math.abs(p.x - item.x) < ((p.width ?? 176) + (item.width ?? 176)) / 2 + 8 && Math.abs(p.y - item.y) < Math.max(p.height ?? 44, item.height ?? 44) + 8)) visible.push(item);
  return new Set(visible.map(p => p.id));
}
export const chipAvoidsPoints = (x: number, bottom: number, width: number, height: number, points: { x: number; y: number }[]) => points.every(p => Math.abs(p.x - x) > width / 2 + 14 || p.y < bottom - height - 14 || p.y > bottom + 14);
type ScreenBox = { left: number; top: number; right: number; bottom: number };
export const chipFits = (chip: ScreenBox, viewport: ScreenBox, obstacles: ScreenBox[]) => chip.left >= viewport.left + 8 && chip.right <= viewport.right - 8 && chip.top >= viewport.top + 8 && chip.bottom <= viewport.bottom - 8 && obstacles.every(p => chip.right + 8 <= p.left || chip.left - 8 >= p.right || chip.bottom + 8 <= p.top || chip.top - 8 >= p.bottom);
