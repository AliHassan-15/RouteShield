import type { DecodedHeatmap, HeatFilter } from './decoder';
import type { Checkpoint, RiskLevel } from '../../api/types';
export const LEVEL_NAMES: Record<number, RiskLevel | 'UNAVAILABLE'> = { 0: 'UNKNOWN', 1: 'LOW', 2: 'MODERATE', 3: 'HIGH', 4: 'SEVERE', 5: 'NO_TRAVEL', 9: 'UNAVAILABLE' };
export const DOMINANT = ['None reported', 'Wind', 'Rain', 'Snow', 'Load-adjusted wind'];
export const clampHour = (h: number) => Number.isFinite(h) ? Math.max(0, Math.min(48, Math.round(h))) : 0;
export const etaHour = (eta: string, reference: string) => Math.max(0, Math.min(48, (Date.parse(eta) - Date.parse(reference)) / 3600000));
export const jumpHour = (cp: Checkpoint, data: DecodedHeatmap) => clampHour(etaHour(cp.eta_utc, data.payload.reference_time));
export function hourLabel(timestamp: string, hour: number, zone?: string) {
  const date = new Date(Date.parse(timestamp) + hour * 3600000);
  return { local: new Intl.DateTimeFormat('en-US', { ...(zone ? { timeZone: zone } : {}), month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZoneName: 'short' }).format(date), utc: `${date.toISOString().slice(0, 16).replace('T', ' ')} UTC`, offset: `+${hour} h from departure` };
}
export function dayTicks(reference: string, zone?: string) {
  const format = new Intl.DateTimeFormat('en-US', { ...(zone ? { timeZone: zone } : {}), month: 'short', day: 'numeric' });
  let previous = format.format(new Date(reference)); const ticks: { hour: number; label: string }[] = [];
  for (let hour = 1; hour < 49; hour++) { const label = format.format(new Date(Date.parse(reference) + hour * 3600000)); if (label !== previous) ticks.push({ hour, label }); previous = label; }
  return ticks;
}
export const levelsAt = (data: DecodedHeatmap, hour: number, filter: HeatFilter) => filter === 'combined' || !data.filters ? data.frames[hour]!.levels : data.frames[hour]!.hazards![filter];
/** Five independent weights: sentinels never enter a heat layer. */
export function weightsAt(data: DecodedHeatmap, hour: number, filter: HeatFilter) {
  const n = data.payload.point_count, weights = new Float32Array(n * 5), levels = levelsAt(data, hour, filter);
  levels.forEach((level, i) => { if (level >= 1 && level <= 5) weights[(level - 1) * n + i] = data.frames[hour]!.intensity[i]! / 100; });
  return weights;
}
export function fadeWeights(from: Float32Array, to: Float32Array, t: number, out = new Float32Array(to.length)) {
  const progress = Math.max(0, Math.min(1, t)); for (let i = 0; i < out.length; i++) out[i] = from[i]! * (1 - progress) + to[i]! * progress; return out;
}
export function weightHash(weights: Float32Array) { let hash = 2166136261; for (const v of weights) { hash ^= Math.round(v * 100000); hash = Math.imul(hash, 16777619); } return (hash >>> 0).toString(16); }
export function pointCounts(data: DecodedHeatmap, hour: number, filter: HeatFilter) { const counts = new Uint16Array(10); levelsAt(data, hour, filter).forEach(v => counts[v] = counts[v]! + 1); return counts; }
/** Nearest supplied sample is a display association, never forecast interpolation. */
export function truckReadout(data: DecodedHeatmap, route: string | null, hour: number, filter: HeatFilter) {
  if (!route || !data.trucks[route]) return { kind: 'unavailable' as const };
  if (!data.truckPresent[route]![hour]) return { kind: 'arrived' as const };
  const values = data.trucks[route]!, lat = values[hour * 3]!, lon = values[hour * 3 + 1]!, mile = values[hour * 3 + 2]!;
  const mapping = data.payload.route_mappings.find(m => m.route_id === route);
  const candidates = mapping ? [...new Set([...mapping.checkpoint_point_indices, ...mapping.optional_point_mappings.map(p => p.point_index)])] : Array.from({ length: data.payload.point_count }, (_, i) => i);
  const rad = Math.PI / 180; let point = -1, minimum = Infinity;
  for (const i of candidates) { const pLon = data.coordinates[i * 2]!, pLat = data.coordinates[i * 2 + 1]!; const a = Math.sin((pLat - lat) * rad / 2) ** 2 + Math.cos(lat * rad) * Math.cos(pLat * rad) * Math.sin((pLon - lon) * rad / 2) ** 2; if (a < minimum) { minimum = a; point = i; } }
  return { kind: 'position' as const, lat, lon, mile, point, level: point < 0 ? 'UNAVAILABLE' : LEVEL_NAMES[levelsAt(data, hour, filter)[point]!]!, dominant: point < 0 ? 'Unavailable' : DOMINANT[data.frames[hour]!.dominant[point]!]!, blocked: point >= 0 && !!data.frames[hour]!.blocked[point], floor: point >= 0 ? LEVEL_NAMES[data.frames[hour]!.floors[point]!] : undefined };
}
