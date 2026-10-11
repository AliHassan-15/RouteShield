import type { AnalysisResponse, Route, RiskLevel } from '../../api/types';
import { displayNumber } from '../../lib/format';

export const LEVELS: readonly RiskLevel[] = ['LOW', 'MODERATE', 'HIGH', 'SEVERE', 'NO_TRAVEL', 'UNKNOWN'];
export const CRITERIA = [
  { code: 'SEVERE_MILES', key: 'severe_miles', label: 'Severe miles' },
  { code: 'HIGH_MILES', key: 'high_miles', label: 'High miles' },
  { code: 'AVERAGE_RISK', key: 'average_risk', label: 'Average risk' },
  { code: 'DURATION', key: 'duration_seconds', label: 'Travel time' },
] as const;
export function serverOrder(routes: readonly Route[]): Route[] {
  // Only replay explicit server ranks/groups. Never inspect criteria values.
  const group = (r: Route) => r.group === 'UNRANKED' || r.rank === null ? 2 : r.group === 'BLOCKED_COMPLETE' ? 1 : 0;
  return [...routes].sort((a, b) => group(a) - group(b) || (a.rank ?? Infinity) - (b.rank ?? Infinity));
}
export function routeLabels(response: AnalysisResponse): Map<string, string> {
  // API has no human label. One server-order label map is also used to substitute
  // exact ID tokens in server prose, preserving every sentence and near-tie note.
  return new Map(serverOrder(response.routes).map((r, i) => [r.route_id, `Route ${i + 1}`]));
}
export function labelText(text: string, labels: Map<string, string>): string {
  let result = text;
  for (const [id, label] of labels) {
    result = result.replaceAll(`Route ${id}`, label).replaceAll(id, label);
  }
  return result;
}
export function eligibleRecommended(response: AnalysisResponse): Route | undefined {
  if (!['RECOMMENDED', 'BEST_FULLY_ASSESSED_AVAILABLE'].includes(response.recommendation_status)) return undefined;
  return response.routes.find(r => r.route_id === response.recommended_route_id && r.travel_status === 'ASSESSED' && !r.summary.known_blocked && r.summary.average_risk !== null);
}
export function stripSegments(route: Route) {
  // Ownership comes directly from API, no midpoint or risk calculation required.
  return route.checkpoints.map(p => ({ id: p.id, level: p.risk.final_risk, miles: Math.max(0, displayNumber(p.owned_miles) ?? 0) }));
}
export function stripMatchesSummary(route: Route): boolean {
  return LEVELS.every(level => Math.abs(stripSegments(route).filter(s => s.level === level).reduce((sum, s) => sum + s.miles, 0) - (displayNumber(route.summary.miles_by_level[level]) ?? 0)) <= .01);
}
