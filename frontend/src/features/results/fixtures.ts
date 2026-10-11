// Hand-built SYNTHETIC contracts for tests only; never provider responses.
import type { AnalysisResponse, Checkpoint, ExactNumber, RecommendationStatus, RiskLevel, Route } from '../../api/types';
import { analysisFixture } from '../trip/test-fixtures';
import { WARNING_CODES } from './Warnings';

export const exact = (n: number | string, d = '1'): ExactNumber => ({ numerator: String(n), denominator: d });
const e = (n: number) => exact(n * 10, '10');
function checkpoint(i: number, level: RiskLevel): Checkpoint {
  return { id: `cp-${i}`, index: i, mile_marker: e([0, 10, 20, 23][i]!), owned_miles: e([5, 10, 6.5, 1.5][i]!), elapsed_seconds: exact(i * 2000), coordinate: [-87 + i, 41], eta_utc: `2026-10-11T${15 + i}:00:00Z`, local_time: null, timezone: 'America/Detroit', utc_fallback: false,
    weather: { values: { wind_mph: '25', rain_in_hr: '0', snow_in_hr: '0', gust_mph: null }, source: null, units: {}, forecast_timestamp: '2026-10-11T16:00:00Z', interval_start: '2026-10-11T15:00:00Z', interval_end: '2026-10-11T16:00:00Z', fetched_at: '2026-10-11T12:00:00Z', provider: 'synthetic', model: 'synthetic', cache_hit: false, unavailable_reason: level === 'UNKNOWN' ? 'MISSING_FIELD' : null, missing_fields: [], hourly_average_rates: true },
    risk: { wind_risk: level, rain_risk: level, snow_risk: level, hazard_risk: level, load_adjusted_wind_risk: level, final_risk: level, known_risk_floor: level === 'UNKNOWN' ? null : level, known_blocked: level === 'NO_TRAVEL', ordinal: null, reasons: [] },
  };
}
export function resultFixture(status: RecommendationStatus = 'RECOMMENDED', criterion = 'SEVERE_MILES'): AnalysisResponse {
  const response = structuredClone(analysisFixture());
  response.analysis_id = `synthetic-${status}-${criterion}`;
  response.message = { RECOMMENDED: 'Recommended fully assessed route', BEST_FULLY_ASSESSED_AVAILABLE: 'Best fully assessed available route', ALL_BLOCKED: 'No safe route at this departure time and load', NO_FULLY_ASSESSED_TRAVELABLE_ROUTE: 'No fully assessed travelable route', ALL_INCOMPLETE: 'All routes have incomplete weather data' }[status];
  response.recommendation_status = status; response.decisive_criterion = criterion;
  response.routes.forEach((r, i) => {
    r.group = 'ASSESSED'; r.duration_s = exact(9600 + i * 120);
    r.summary.total_miles = exact(23); r.summary.total_duration_s = r.duration_s;
    r.checkpoints = [checkpoint(0, 'LOW'), checkpoint(1, i === 0 ? 'MODERATE' : 'SEVERE'), checkpoint(2, 'HIGH'), checkpoint(3, 'LOW')];
    r.summary.miles_by_level = { LOW: e(6.5), MODERATE: e(i === 0 ? 10 : 0), HIGH: e(6.5), SEVERE: e(i === 0 ? 0 : 10), NO_TRAVEL: exact(0), UNKNOWN: exact(0) };
    if (criterion !== 'SEVERE_MILES') {
      r.checkpoints[1] = checkpoint(1, i > 0 && criterion === 'HIGH_MILES' ? 'HIGH' : 'MODERATE');
      r.summary.miles_by_level = { LOW: e(6.5), MODERATE: exact(i > 0 && criterion === 'HIGH_MILES' ? 0 : 10), HIGH: e(i > 0 && criterion === 'HIGH_MILES' ? 16.5 : 6.5), SEVERE: exact(0), NO_TRAVEL: exact(0), UNKNOWN: exact(0) };
      if (i > 0 && criterion === 'AVERAGE_RISK') { r.checkpoints[0] = checkpoint(0, 'MODERATE'); r.summary.miles_by_level.LOW = e(1.5); r.summary.miles_by_level.MODERATE = exact(15); }
    }
    r.summary.average_risk = i === 0 || criterion === 'DURATION' || criterion === 'TIE_BROKEN_BY_ID' ? exact(2) : criterion === 'AVERAGE_RISK' ? exact(51, '23') : criterion === 'HIGH_MILES' ? exact(56, '23') : exact(66, '23');
    if (criterion === 'TIE_BROKEN_BY_ID') r.duration_s = exact(9600);
    r.summary.total_duration_s = r.duration_s;
    r.checkpoints.forEach((cp, index) => { const elapsed = index === 3 ? Number(r.duration_s.numerator) : index * 3000; cp.elapsed_seconds = exact(elapsed); cp.eta_utc = new Date(Date.parse(response.trip.departure_time) + elapsed * 1000).toISOString(); cp.local_time = new Date(Date.parse(cp.eta_utc) - 14400000).toISOString().replace('Z', '-04:00'); });
    r.criteria.severe_miles = r.summary.miles_by_level.SEVERE!; r.criteria.high_miles = r.summary.miles_by_level.HIGH!; r.criteria.average_risk = r.summary.average_risk; r.criteria.duration_seconds = r.duration_s;
  });
  const mark = (r: Route, blocked: boolean, incomplete: boolean) => {
    r.travel_status = blocked ? 'BLOCKED' : 'INCOMPLETE'; r.group = incomplete ? 'UNRANKED' : 'BLOCKED_COMPLETE'; r.rank = incomplete ? null : r.rank;
    r.summary.travel_status = r.travel_status; r.summary.known_blocked = blocked; r.summary.coverage_fraction = incomplete ? exact(13, '23') : exact(1); r.summary.average_risk = incomplete ? null : exact(76, '23'); r.criteria.average_risk = r.summary.average_risk;
    r.checkpoints[1] = checkpoint(1, incomplete ? 'UNKNOWN' : 'NO_TRAVEL');
    r.summary.miles_by_level = { LOW: e(6.5), HIGH: e(6.5), SEVERE: exact(0), MODERATE: exact(0), NO_TRAVEL: exact(incomplete ? 0 : 10), UNKNOWN: exact(incomplete ? 10 : 0) };
    r.summary.unknown_miles = exact(incomplete ? 10 : 0); r.summary.no_travel_miles = exact(incomplete ? 0 : 10); r.criteria.no_travel_miles = r.summary.no_travel_miles; r.criteria.severe_miles = exact(0);
  };
  if (status === 'BEST_FULLY_ASSESSED_AVAILABLE') { mark(response.routes[1]!, true, false); mark(response.routes[2]!, false, true); }
  if (status === 'ALL_BLOCKED') response.routes.forEach(r => mark(r, true, false));
  if (status === 'NO_FULLY_ASSESSED_TRAVELABLE_ROUTE') { mark(response.routes[0]!, true, false); mark(response.routes[1]!, false, true); mark(response.routes[2]!, false, true); }
  if (status === 'ALL_INCOMPLETE') response.routes.forEach(r => mark(r, false, true));
  response.recommended_route_id = ['RECOMMENDED', 'BEST_FULLY_ASSESSED_AVAILABLE'].includes(status) ? response.routes[0]!.route_id : null;
  response.least_blocked_route_id = status === 'ALL_BLOCKED' ? response.routes[0]!.route_id : null;
  if (!response.recommended_route_id || status === 'BEST_FULLY_ASSESSED_AVAILABLE') response.decisive_criterion = 'NONE';
  response.explanation = response.recommended_route_id ? `Recommended fully assessed route: ${response.recommended_route_id}. Route ${response.recommended_route_id} precedes ${response.routes[1]!.route_id} on the server comparison. Travel times for ${response.recommended_route_id} and ${response.routes[1]!.route_id} differ by 2.00 minutes (within 4 minutes); duration is lower priority and did not decide this comparison.` : `${response.message}. No route is eligible for recommendation.`;
  const key = criterion === 'HIGH_MILES' ? 'high_miles' : criterion === 'AVERAGE_RISK' ? 'average_risk' : criterion === 'DURATION' ? 'duration_seconds' : 'severe_miles';
  response.comparison_facts = status === 'RECOMMENDED' ? [{ winner_route_id: response.recommended_route_id!, other_route_id: response.routes[1]!.route_id, criterion, winner_value: response.routes[0]!.criteria[key], other_value: response.routes[1]!.criteria[key], code: criterion }] : [];
  if (status === 'BEST_FULLY_ASSESSED_AVAILABLE') response.explanation = `Best fully assessed available route: ${response.recommended_route_id}; only one route is eligible. Route ${response.routes[1]!.route_id} is blocked. Route ${response.routes[2]!.route_id} is unranked: incomplete weather data.`;
  response.explanation_facts = response.comparison_facts.map(f => ({ code: f.code, route_id: f.winner_route_id, other_route_id: f.other_route_id, values: { winner_value: f.winner_value, other_value: f.other_value } }));
  return response;
}
export function warningsFixture(): AnalysisResponse {
  const response = resultFixture('BEST_FULLY_ASSESSED_AVAILABLE');
  response.warnings = [...WARNING_CODES, 'FUTURE_NOTICE'].map(code => ({ code, message: 'Synthetic server notice', scope: code === 'INCOMPLETE_WEATHER' ? response.routes[2]!.route_id : 'trip', coverage_fraction: exact(13, '23') }));
  return response;
}
