import type { AnalysisResponse, Warning } from '../../api/types';
import { fixed, missingPercent, percent } from '../../lib/format';
import { routeLabels } from './presentation';
export const WARNING_CODES = ['PARTIAL_ROUTES', 'INCOMPLETE_WEATHER', 'WEATHER_UNAVAILABLE', 'DEADLINE_WEATHER_UNAVAILABLE', 'DEMO_QUOTA_REACHED', 'FORECAST_HORIZON_LIMIT', 'INTERVAL_INCREASED', 'BLOCKED_TRIP', 'UTC_FALLBACK', 'ROUTING_DEPARTURE_ADJUSTED', 'FALLBACK_SKIPPED_DEADLINE', 'FALLBACK_UNAVAILABLE', 'HEATMAP_DENSITY_REDUCED'] as const;
export function warningText(w: Warning, response: AnalysisResponse): string {
  const copy: Record<string, string> = {
    PARTIAL_ROUTES: `Only ${response.route_count} route(s) available`,
    INCOMPLETE_WEATHER: `${missingPercent(w.coverage_fraction)} of this route has unavailable weather`,
    WEATHER_UNAVAILABLE: 'Weather source unavailable. Missing values remain Unknown.',
    DEADLINE_WEATHER_UNAVAILABLE: 'Weather work exceeded the remaining analysis time. Coverage is incomplete.',
    DEMO_QUOTA_REACHED: 'Demo weather quota reached. Re-run after the daily allowance resets.',
    FORECAST_HORIZON_LIMIT: 'Some arrival times fall outside the available forecast.',
    INTERVAL_INCREASED: `Spacing increased to ${response.trip.effective_interval_miles} mi (requested ${response.trip.requested_interval_miles ?? 'Auto'}). ${w.message}`,
    BLOCKED_TRIP: w.message,
    UTC_FALLBACK: 'Geographic time zone unavailable. Arrival times are explicitly shown in UTC.',
    ROUTING_DEPARTURE_ADJUSTED: 'Routing used the provider’s allowed departure recovery. Checkpoint ETAs retain your submitted departure.',
    FALLBACK_SKIPPED_DEADLINE: 'Additional route search skipped because the shared deadline was close.',
    FALLBACK_UNAVAILABLE: 'Additional route search could not return a usable alternative.',
    HEATMAP_DENSITY_REDUCED: 'Corridor display samples were coarsened. Mandatory checkpoints were retained.',
  };
  return copy[w.code] ?? `Notice ${w.code}: ${w.message}`;
}
export function WarningList({ warnings, response }: { warnings: Warning[]; response: AnalysisResponse }) {
  return <ul className="notice-list">{warnings.map((w, i) => <li key={`${w.code}-${i}`}><span className="micro">{w.code}</span><p>{warningText(w, response)}</p></li>)}</ul>;
}
export function WarningsTray({ response }: { response: AnalysisResponse }) {
  const warnings = response.warnings.filter(w => !response.routes.some(r => r.route_id === w.scope));
  if (!warnings.length) return null;
  return <details className="warnings-tray"><summary><span className="mono">{warnings.length}</span> notices</summary><WarningList warnings={warnings} response={response} /></details>;
}
export function Coverage({ response }: { response: AnalysisResponse }) {
  return <ul className="coverage-list">{response.routes.map(r => <li key={r.route_id}><span>{routeLabels(response).get(r.route_id)}</span><span className="mono">{percent(r.summary.coverage_fraction)} weather coverage · {fixed(r.summary.unknown_miles)} mi Unknown</span>{r.summary.known_blocked && <strong>Known No Travel evidence</strong>}</li>)}</ul>;
}
