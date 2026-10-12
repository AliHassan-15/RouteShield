// Hand-built SYNTHETIC API evidence; not live/scenario provider recordings.
import type { Checkpoint, RiskLevel, RiskReason, UnavailableReason } from '../../api/types';
import { mapFixture } from '../map/fixtures';
import { exact } from '../results/fixtures';
import { LEVELS } from '../results/presentation';
export const UNAVAILABLE_CODES: UnavailableReason[] = ['OUT_OF_HORIZON', 'MISSING_HOUR', 'MISSING_FIELD', 'PAST_TIME', 'PROVIDER_FAILURE', 'QUOTA_EXCEEDED', 'DEMO_QUOTA_REACHED'];
export function syntheticReason(code: RiskReason['code'] = 'HAZARD_CLASSIFIED', metric = 'wind_mph', value: string | null = '38', level: RiskLevel = 'HIGH'): RiskReason {
  return { code, metric, measured_value: value, level, band: value === null ? null : { level, printed_pdf_band: 'Synthetic supplied band', lower: '35', upper: '45', lower_inclusive: true, upper_inclusive: false }, threshold: value === null ? null : '35', comparison: value === null ? null : '>=', wind_mph: null, load_weight_lb: null };
}
export function checkpointFixture() {
  const response = mapFixture(true), route = response.routes[0]!, base = route.checkpoints[0]!, total = 130;
  response.recommendation_status = 'NO_FULLY_ASSESSED_TRAVELABLE_ROUTE'; response.message = 'No fully assessed travelable route'; response.recommended_route_id = null; response.least_blocked_route_id = null;
  route.checkpoints = Array.from({ length: 14 }, (_, index): Checkpoint => {
    const cp = structuredClone(base), final: RiskLevel = ['LOW', 'MODERATE', 'HIGH', 'SEVERE', 'NO_TRAVEL', 'UNKNOWN', 'UNKNOWN'][index] as RiskLevel ?? 'UNKNOWN';
    const wind = ['15', '30', '20', '20', '47', '60'][index] ?? null, rain = ['0', '0.15', '0.3', '0.6', '0'][index] ?? null, snow = index < 6 ? '0' : null;
    const windRisk: RiskLevel = ['LOW', 'MODERATE', 'LOW', 'LOW', 'SEVERE', 'NO_TRAVEL'][index] as RiskLevel ?? 'UNKNOWN', rainRisk: RiskLevel = ['LOW', 'MODERATE', 'HIGH', 'SEVERE', 'LOW'][index] as RiskLevel ?? 'UNKNOWN';
    cp.index = index; cp.id = `synthetic-inspector-${index}`; cp.mile_marker = exact(index * 10); cp.owned_miles = exact(index === 0 || index === 13 ? 5 : 10); cp.coordinate = route.geometry[Math.round(index / 13 * (route.geometry.length - 1))]!;
    cp.eta_utc = new Date(Date.parse('2026-10-12T12:00:00Z') + index * 600000).toISOString(); cp.elapsed_seconds = exact(index * 600); cp.utc_fallback = index % 2 === 0; cp.timezone = cp.utc_fallback ? null : 'America/Chicago'; cp.local_time = cp.utc_fallback ? null : cp.eta_utc;
    cp.weather.values = { wind_mph: wind, rain_in_hr: rain, snow_in_hr: snow, gust_mph: index < 5 ? '52' : null }; cp.weather.forecast_timestamp = '2026-10-12T14:00:00Z'; cp.weather.interval_start = '2026-10-12T13:00:00Z'; cp.weather.interval_end = cp.weather.forecast_timestamp;
    cp.weather.fetched_at = response.generated_at; cp.weather.unavailable_reason = index >= 7 ? UNAVAILABLE_CODES[index - 7]! : index >= 5 ? 'MISSING_FIELD' : null;
    cp.risk = { wind_risk: windRisk, rain_risk: rainRisk, snow_risk: snow === null ? 'UNKNOWN' : 'LOW', hazard_risk: index >= 5 ? 'UNKNOWN' : index === 4 ? 'SEVERE' : final, load_adjusted_wind_risk: index === 4 ? 'NO_TRAVEL' : windRisk, final_risk: final, known_risk_floor: index >= 6 ? null : index === 5 ? 'NO_TRAVEL' : final, known_blocked: index === 4 || index === 5, ordinal: index >= 5 ? null : index + 1, reasons: [syntheticReason(wind === null ? 'MISSING_HAZARD' : 'HAZARD_CLASSIFIED', 'wind_mph', wind, windRisk), syntheticReason(rain === null ? 'MISSING_HAZARD' : 'HAZARD_CLASSIFIED', 'rain_in_per_hour', rain, rainRisk), syntheticReason(snow === null ? 'MISSING_HAZARD' : 'HAZARD_CLASSIFIED', 'snow_in_per_hour', snow, snow === null ? 'UNKNOWN' : 'LOW')] };
    if (index === 4) cp.risk.reasons.push({ ...syntheticReason('SEVERE_WIND_HEAVY_LOAD', 'load_weight_lb', '45000', 'NO_TRAVEL'), threshold: '30000', comparison: '>', wind_mph: wind, load_weight_lb: '45000', band: { level: 'SEVERE', printed_pdf_band: 'Synthetic supplied band', lower: '45', upper: '55', lower_inclusive: true, upper_inclusive: false } });
    if (index === 5) cp.risk.reasons.push({ ...syntheticReason('EXTREME_WIND_ANY_LOAD', 'wind_mph', wind, 'NO_TRAVEL'), wind_mph: wind, load_weight_lb: '45000', threshold: '55' });
    if (wind === null) cp.risk.reasons.push(syntheticReason('LOAD_RULES_UNAVAILABLE_MISSING_WIND', 'wind_mph', null, 'UNKNOWN'));
    // This hand-built excerpt omits optional hazard boundary metadata. Dedicated
    // template tests supply thresholds; no browser fixture classifies values.
    cp.risk.reasons.filter(reason => reason.code === 'HAZARD_CLASSIFIED').forEach(reason => { reason.band = null; reason.threshold = null; reason.comparison = null; });
    return cp;
  });
  route.summary.total_miles = exact(total); route.summary.maximum_known_level = 'NO_TRAVEL'; route.summary.known_risk_floor = 'NO_TRAVEL'; route.summary.known_blocked = true; route.summary.travel_status = route.travel_status = 'BLOCKED'; route.summary.average_risk = null; route.rank = null; route.group = 'UNRANKED';
  route.summary.miles_by_level = Object.fromEntries(LEVELS.map(l => [l, exact(route.checkpoints.filter(cp => cp.risk.final_risk === l).reduce((sum, cp) => sum + Number(cp.owned_miles.numerator), 0))]));
  route.summary.unknown_miles = route.summary.miles_by_level.UNKNOWN!; route.summary.coverage_fraction = exact(45, '130');
  route.risk_profile = route.checkpoints.map((cp, index) => ({ start_mile: exact(index === 0 ? 0 : index * 10 - 5), end_mile: exact(index === 13 ? 130 : index * 10 + 5), checkpoint_id: cp.id, final_risk: cp.risk.final_risk, known_risk_floor: cp.risk.known_risk_floor, known_blocked: cp.risk.known_blocked }));
  response.routes.slice(1).forEach(r => { r.summary.maximum_known_level = 'NO_TRAVEL'; r.summary.known_risk_floor = 'NO_TRAVEL'; });
  return response;
}
