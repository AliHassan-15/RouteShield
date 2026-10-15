import type { AnalysisResponse, Heatmap } from '../../api/types';

export type HeatFilter = 'combined' | 'wind' | 'rain' | 'snow';
export interface DecodedFrame {
  levels: Uint8Array; intensity: Uint8Array; dominant: Uint8Array;
  blocked: Uint8Array; floors: Uint8Array;
  hazards?: Record<Exclude<HeatFilter, 'combined'>, Uint8Array>;
}
export interface DecodedHeatmap {
  payload: Heatmap; coordinates: Float64Array; frames: DecodedFrame[];
  trucks: Record<string, Float64Array>; truckPresent: Record<string, Uint8Array>;
  filters: boolean; bytes: number; decodeMs: number;
}
export type HeatDecode = { kind: 'ready'; data: DecodedHeatmap } | { kind: 'not included' | 'malformed' | 'no coverage' };
const cache = new WeakMap<object, HeatDecode>();
const digits = (value: string, count: number, allowed: string) => {
  if (typeof value !== 'string' || value.length !== count) throw Error();
  const result = new Uint8Array(count);
  for (let i = 0; i < count; i++) { const char = value[i]!; if (!allowed.includes(char)) throw Error(); result[i] = Number(char); }
  return result;
};
const validNumber = (v: number, min: number, max: number) => typeof v === 'number' && Number.isFinite(v) && v >= min && v <= max;

/** Presentation-only decoding: no classification, intensity calculation or lookup. */
export function decodeHeatmap(input: Heatmap | undefined | null, capability = false): HeatDecode {
  if (!input) return { kind: 'not included' };
  const start = performance.now();
  try {
    const n = input.point_count;
    if (!Number.isInteger(n) || n < 1 || n > 200 || input.frame_count !== 49 || input.points.length !== n || input.frames.length !== 49) throw Error();
    if (!Number.isFinite(Date.parse(input.reference_time)) || !Number.isFinite(Date.parse(input.hour_0_timestamp))) throw Error();
    if (!input.density || !Object.values(input.density.actual_optional_max_gap_miles).every(v => validNumber(v, 0, Number.MAX_VALUE)) || !Array.isArray(input.warnings) || input.warnings.some(v => typeof v !== 'string') || typeof input.attribution.text !== 'string') throw Error();
    const coordinates = new Float64Array(n * 2);
    input.points.forEach((p, i) => { if (p.length !== 2 || !validNumber(p[0], -180, 180) || !validNumber(p[1], -90, 90)) throw Error(); coordinates.set(p, i * 2); });
    for (const [code, label] of Object.entries({ 0: 'UNKNOWN', 1: 'LOW', 2: 'MODERATE', 3: 'HIGH', 4: 'SEVERE', 5: 'NO_TRAVEL', 9: 'UNAVAILABLE' })) if (input.legends.levels[code]?.toUpperCase().replaceAll(' ', '_') !== label) throw Error();
    const filters = capability === true && input.hazard_filters_included === true;
    const frames = input.frames.map((f, hour): DecodedFrame => {
      if (f.hour !== hour || Date.parse(f.timestamp) !== Date.parse(input.hour_0_timestamp) + hour * 3600000 || f.intensities.length !== n || f.intensities.some(v => !Number.isInteger(v) || !validNumber(v, 0, 100))) throw Error();
      const frame: DecodedFrame = { levels: digits(f.levels, n, '0123459'), intensity: Uint8Array.from(f.intensities), dominant: digits(f.dominant_hazards, n, '01234'), blocked: digits(f.known_blocked, n, '01'), floors: digits(f.known_risk_floors, n, '012345') };
      if (filters) { if (!f.hazard_levels) throw Error(); frame.hazards = { wind: digits(f.hazard_levels.wind, n, '0123459'), rain: digits(f.hazard_levels.rain, n, '0123459'), snow: digits(f.hazard_levels.snow, n, '0123459') }; }
      for (const [index, reason] of Object.entries(f.unavailable_reasons)) if (!/^\d+$/.test(index) || Number(index) >= n || !['OUT_OF_HORIZON', 'MISSING_HOUR', 'MISSING_FIELD', 'PAST_TIME', 'PROVIDER_FAILURE', 'QUOTA_EXCEEDED', 'DEMO_QUOTA_REACHED'].includes(reason)) throw Error();
      return frame;
    });
    const coverage = input.forecast_coverage;
    if (coverage.last_usable_hour !== null && (!Number.isInteger(coverage.last_usable_hour) || !validNumber(coverage.last_usable_hour, 0, 48)) || coverage.last_usable_hour_by_point.length !== n || coverage.last_usable_hour_by_point.some(h => h !== null && (!Number.isInteger(h) || !validNumber(h, 0, 48)))) throw Error();
    const trucks: Record<string, Float64Array> = {}, truckPresent: Record<string, Uint8Array> = {};
    for (const [route, positions] of Object.entries(input.truck_positions)) {
      if (positions.length !== 49) throw Error();
      const values = new Float64Array(49 * 3), mask = new Uint8Array(49);
      positions.forEach((p, h) => { if (p === null) { if (h === 0) throw Error(); return; } if (h > 0 && !mask[h - 1] || p.length !== 3 || !validNumber(p[0], -90, 90) || !validNumber(p[1], -180, 180) || !validNumber(p[2], 0, Number.MAX_VALUE)) throw Error(); values.set(p, h * 3); mask[h] = 1; });
      trucks[route] = values; truckPresent[route] = mask;
    }
    for (const mapping of input.route_mappings) for (const index of [...mapping.checkpoint_point_indices, ...mapping.optional_point_mappings.map(p => p.point_index)]) if (!Number.isInteger(index) || index < 0 || index >= n) throw Error();
    if (coverage.last_usable_hour === null || frames.every(f => f.levels.every(v => v === 9))) return { kind: 'no coverage' };
    let bytes = coordinates.byteLength;
    for (const f of frames) { bytes += f.levels.byteLength * 5; if (f.hazards) bytes += n * 3; }
    bytes += Object.values(trucks).reduce((s, v) => s + v.byteLength, 0) + Object.values(truckPresent).reduce((s, v) => s + v.byteLength, 0);
    return { kind: 'ready', data: { payload: input, coordinates, frames, trucks, truckPresent, filters, bytes, decodeMs: performance.now() - start } };
  } catch { return { kind: 'malformed' }; }
}
export function decodeAnalysis(response: AnalysisResponse): HeatDecode {
  let decoded = cache.get(response);
  if (!decoded) { decoded = decodeHeatmap(response.heatmap, response.capabilities?.hazard_filter); cache.set(response, decoded); }
  return decoded;
}
