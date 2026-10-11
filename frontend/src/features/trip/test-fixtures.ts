// Hand-authored synthetic contracts only; never provider recordings.
import type { AnalysisResponse, GeocodeResponse, Route } from '../../api/types';
import { EXAMPLE_TRIPS } from './config';
import type { TripDraft } from './model';

export const FIXED_NOW = Date.parse('2026-10-11T12:00:00Z');
export function testDraft(): TripDraft {
  const trip = EXAMPLE_TRIPS[0]!;
  return { origin: { text: trip.origin.label, place: trip.origin }, destination: { text: trip.destination.label, place: trip.destination }, wall: { date: '2026-10-11', time: '15:00' }, offset: null, zone: 'UTC', weight: '45000', spacing: 'auto' };
}
const exact = (n: number) => ({ numerator: String(n), denominator: '1' });
export const syntheticCredit = { provider: 'synthetic', text: 'Synthetic attribution from API metadata', confirmed: false, source_url: null, licence_url: null };
export const syntheticMetadata = { request_id: 'synthetic-request-1', total_ms: 120, stage_ms: { routing: 80, weather: 40 }, provider_calls: { routing: 0, geocoding: 0, weather: 0 }, weather_cache: { hits: 0, misses: 0, ages_seconds: [] }, quota_units_reserved: exact(0), deadline_seconds: 35, simulated: false };
export function geocodeFixture(count = 3): GeocodeResponse {
  return { candidates: Array.from({ length: count }, (_, i) => ({ candidate_id: `synthetic-${i}`, label: ['Chicago West', 'Chicago Center', 'Chicago East'][i]!, latitude: 41 + i / 10, longitude: -87, region: 'Illinois', country: 'United States', match_type: 'synthetic', score: exact(1), provider: 'synthetic', attribution: syntheticCredit })), attribution: syntheticCredit, metadata: syntheticMetadata };
}
export function analysisFixture(): AnalysisResponse {
  const draft = testDraft();
  const routes: Route[] = Array.from({ length: 3 }, (_, i) => ({ route_id: `synthetic-route-${i}`, geometry: [[-87, 41], [-83, 42]], distance_m: exact(450000), duration_s: exact(17000 + i * 100), profile: 'truck', live_traffic: false, attribution: syntheticCredit, travel_status: 'ASSESSED', rank: i + 1, group: 'travelable', criteria: { no_travel_miles: exact(0), severe_miles: exact(0), high_miles: exact(0), average_risk: exact(1), duration_seconds: exact(17000 + i * 100), stable_route_id: `synthetic-route-${i}` }, checkpoints: [], risk_profile: [], summary: { total_miles: exact(280), total_duration_s: exact(17000), miles_by_level: { LOW: exact(280) }, unknown_miles: exact(0), average_risk: exact(1), known_only_average_risk_diagnostic: exact(1), maximum_known_level: 'LOW', known_risk_floor: 'LOW', no_travel_checkpoint_count: 0, no_travel_miles: exact(0), known_blocked_checkpoint_count: 0, known_blocked_miles_diagnostic: exact(0), known_blocked: false, coverage_fraction: exact(1), travel_status: 'ASSESSED' } }));
  return {
    analysis_id: 'synthetic-analysis', policy_version: 'synthetic-policy', generated_at: '2026-10-11T12:00:00Z', expires_at: '2026-10-11T12:15:00Z',
    trip: { origin: draft.origin.place!, destination: draft.destination.place!, departure_time: '2026-10-11T15:00:00+00:00', departure_timezone: 'UTC', load_weight_lb: '45000', reference_time: '2026-10-11T15:00:00Z', requested_interval_miles: null, effective_interval_miles: 25 }, routes, route_count: 3, recommended_route_id: routes[0]!.route_id, least_blocked_route_id: null, recommendation_status: 'RECOMMENDED', message: 'Synthetic backend recommendation: route one has the shortest duration after equal risk.', decisive_criterion: 'duration', diagnostic_decisive_criterion: null, explanation: 'Synthetic contract fixture.', comparison_facts: [], explanation_facts: [], is_simulation: false, simulation_scenario: null, warnings: [], attributions: [syntheticCredit], metadata: syntheticMetadata,
    heatmap: { reference_time: '2026-10-11T15:00:00Z', hour_0_timestamp: '2026-10-11T15:00:00Z', frame_count: 49, point_count: 0, points: [], frames: Array.from({ length: 49 }, (_, hour) => ({ hour, timestamp: new Date(Date.parse('2026-10-11T15:00:00Z') + hour * 3600000).toISOString(), levels: '', intensities: [], dominant_hazards: '', known_blocked: '', known_risk_floors: '', unavailable_reasons: {} })), route_mappings: [], truck_positions: {}, density: { mandatory_point_count: 0, optional_candidate_count: 0, optional_selected_count: 0, optional_unique_point_count: 0, requested_optional_spacing_miles: 10, optional_stride: 1, actual_optional_max_gap_miles: {}, reduced: false }, forecast_coverage: { last_usable_hour: null, last_usable_timestamp: null, last_usable_hour_by_point: [] }, hazard_filters_included: false, hazard_filter_omission_reason: 'synthetic', legends: { levels: {}, dominant_hazards: {} }, intensity_mapping: 'synthetic', attribution: syntheticCredit, warnings: [] }, capabilities: { hazard_filter: false },
  };
}
