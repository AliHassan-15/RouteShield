// Entirely synthetic presentation fixtures, never a provider response recording.
import type { HeatmapFrame, Position, TruckPosition } from '../../api/types';
import { mapFixture } from '../map/fixtures';
import { exact } from '../results/fixtures';
export function heatFixture(mode: 'calm' | 'stormy' | 'partial' | 'worst' | 'no filters' = 'stormy') {
  const response = mapFixture(mode !== 'calm'), n = mode === 'worst' ? 200 :  90;
  const reference = '2026-10-12T12:20:00Z', last = mode === 'calm' || mode === 'worst' ? 48 : 42;
  const points: Position[] = [response.routes[0]!.geometry[0]!], owners = [-1];
  response.routes.forEach((route, owner) => { for (const fraction of [.2, .4, .6, .8]) { points.push(route.geometry[Math.round(fraction * (route.geometry.length - 1))]!); owners.push(owner); } });
  points.push(response.routes[0]!.geometry.at(-1)!); owners.push(-1);
  const seen = new Set(points.map(p => p.join(',')));
  const candidates = response.routes.flatMap((r, owner) => r.geometry.slice(1, -1).filter(p => !seen.has(p.join(','))).map(p => ({ p, owner })));
  for (let i = 0; i < n - 14; i++) { const candidate = candidates[Math.floor(i / (n - 14) * candidates.length)]!; points.push(candidate.p); owners.push(candidate.owner); }
  const checkpointIndex = (route: number, cp: number) => cp === 0 ? 0 : cp === 5 ? 13 : 1 + route * 4 + cp - 1;
  const frames: HeatmapFrame[] = Array.from({ length: 49 }, (_, hour) => {
    const codes = points.map((_, i) => hour > last ? 9 : mode === 'calm' ? 1 : (i + hour * 2) % 17 === 0 ? 0 : mode === 'partial' && i % 3 === 0 ? 9 : 1 + (Math.floor(i / 8) + Math.floor(hour / 3)) % 5);
    const levels = codes.join('');
    return { hour, timestamp: new Date(Date.parse(reference) + hour * 3600000).toISOString(), levels, intensities: codes.map((c, i) => c === 0 || c === 9 ? 0 : c === 5 ? 100 : mode === 'calm' ? 35 : 35 + (i * 7 + hour * 3) % 65), dominant_hazards: codes.map((c, i) => c === 9 || c === 0 ? 0 : c === 5 && i % 3 === 0 ? 4 : 1 + i % 3).join(''), known_blocked: codes.map(c => c === 5 || c === 0 ? 1 : 0).join(''), known_risk_floors: codes.map(c => c === 9 ? 0 : c === 0 ? 5 : c).join(''), ...(mode === 'no filters' ? {} : { hazard_levels: { wind: levels, rain: codes.map(c => c === 9 || c === 0 ? c : Math.max(1, c - 1)).join(''), snow: codes.map(c => c === 9 || c === 0 ? c : c === 5 ? 4 : 1).join('') } }), unavailable_reasons: Object.fromEntries(codes.flatMap((c, i) => c === 9 ? [[String(i), hour > last ? 'OUT_OF_HORIZON' as const : 'PROVIDER_FAILURE' as const]] : [])) };
  });
  response.routes.forEach((route, i) => { route.duration_s = exact((20 + i) * 3600); route.summary.total_duration_s = route.duration_s; route.criteria.duration_seconds = route.duration_s; });
  response.routes.forEach((route, i) => route.checkpoints.forEach((cp, at) => { cp.elapsed_seconds = exact(at / 5 * (20 + i) * 3600); cp.eta_utc = new Date(Date.parse(reference) + at / 5 * (20 + i) * 3600000).toISOString(); cp.coordinate = points[checkpointIndex(i, at)]!; cp.mile_marker = exact(at * 283, '5'); }));
  const trucks = Object.fromEntries(response.routes.map((route, i) => [route.route_id, Array.from({ length: 49 }, (_, h): TruckPosition => { if (h > 20 + i) return null; const p = route.geometry[Math.min(route.geometry.length - 1, Math.round(h / (20 + i) * (route.geometry.length - 1)))]!; return [p[1], p[0], h / (20 + i) * 283]; })]));
  response.trip.departure_time = reference; response.trip.reference_time = reference; response.generated_at = reference;
  response.heatmap = { reference_time: reference, hour_0_timestamp: reference, frame_count: 49, point_count: n, points, frames, route_mappings: response.routes.map((route, i) => ({ route_id: route.route_id, checkpoint_point_indices: route.checkpoints.map((_, j) => checkpointIndex(i, j)), optional_point_mappings: points.flatMap((_, j) => j >= 14 && owners[j] === i ? [{ sample_index: j, point_index: j, coarsened: false, distance_to_point_m: 0 }] : []) })), truck_positions: trucks, density: { mandatory_point_count: 14, optional_candidate_count: n * 2, optional_selected_count: n - 14, optional_unique_point_count: n - 14, requested_optional_spacing_miles: 10, optional_stride: 2, actual_optional_max_gap_miles: Object.fromEntries(response.routes.map(r => [r.route_id, 20])), reduced: true }, forecast_coverage: { last_usable_hour: last, last_usable_timestamp: frames[last]!.timestamp, last_usable_hour_by_point: points.map(() => last) }, hazard_filters_included: mode !== 'no filters', hazard_filter_omission_reason: mode === 'no filters' ? 'COMPRESSED_PAYLOAD_AT_LEAST_300KB' : null, legends: { levels: { 0: 'UNKNOWN', 1: 'LOW', 2: 'MODERATE', 3: 'HIGH', 4: 'SEVERE', 5: 'NO_TRAVEL', 9: 'UNAVAILABLE' }, dominant_hazards: { 0: 'none', 1: 'wind', 2: 'rain', 3: 'snow', 4: 'load-promoted wind' } }, intensity_mapping: 'SYNTHETIC display intensity; not measured weather', attribution: { provider: 'Open-Meteo', text: 'Weather data by Open-Meteo; unit conversion and risk classification by RouteShield.', confirmed: true, source_url: 'https://open-meteo.com/', licence_url: 'https://creativecommons.org/licenses/by/4.0/' }, warnings: ['HEATMAP_DENSITY_REDUCED', ...(last < 48 ? ['FORECAST_HORIZON_LIMIT'] : [])] };
  if (mode === 'calm') {
    // Hand-authored all-clear arrival evidence, consistent with the all-Low
    // corridor fixture. This is data construction, never application risk logic.
    response.routes.forEach(route => {
      route.checkpoints.forEach(cp => {
        cp.risk = { wind_risk: 'LOW', rain_risk: 'LOW', snow_risk: 'LOW', hazard_risk: 'LOW', load_adjusted_wind_risk: 'LOW', final_risk: 'LOW', known_risk_floor: 'LOW', known_blocked: false, ordinal: 1, reasons: [] };
        cp.weather.values = { wind_mph: '10', rain_in_hr: '0', snow_in_hr: '0', gust_mph: null }; cp.weather.unavailable_reason = null; cp.weather.missing_fields = [];
      });
      route.risk_profile.forEach(segment => { segment.final_risk = 'LOW'; segment.known_risk_floor = 'LOW'; segment.known_blocked = false; });
      Object.assign(route.summary, { total_duration_s: route.duration_s, miles_by_level: { LOW: exact(283), MODERATE: exact(0), HIGH: exact(0), SEVERE: exact(0), NO_TRAVEL: exact(0) }, unknown_miles: exact(0), average_risk: exact(1), known_only_average_risk_diagnostic: exact(1), maximum_known_level: 'LOW', known_risk_floor: 'LOW', no_travel_checkpoint_count: 0, no_travel_miles: exact(0), known_blocked_checkpoint_count: 0, known_blocked_miles_diagnostic: exact(0), known_blocked: false, coverage_fraction: exact(1) });
      route.criteria = { ...route.criteria, no_travel_miles: exact(0), severe_miles: exact(0), high_miles: exact(0), average_risk: exact(1), duration_seconds: route.duration_s };
    });
    response.decisive_criterion = 'DURATION'; response.explanation = 'Synthetic calm trip: all routes are fully assessed Low; Route 1 has the shortest supplied duration.';
    response.comparison_facts = [{ winner_route_id: response.routes[0]!.route_id, other_route_id: response.routes[1]!.route_id, criterion: 'DURATION', winner_value: response.routes[0]!.duration_s, other_value: response.routes[1]!.duration_s, code: 'DURATION' }];
    response.explanation_facts = response.comparison_facts.map(f => ({ code: f.code, route_id: f.winner_route_id, other_route_id: f.other_route_id, values: { winner_value: f.winner_value, other_value: f.other_value } }));
  }
  response.capabilities.hazard_filter = mode !== 'no filters'; return response;
}
