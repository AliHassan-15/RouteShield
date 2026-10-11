// Hand-built SYNTHETIC geometry/weather contracts; no provider recordings.
import type { AnalysisResponse, Position } from '../../api/types';
import { exact, resultFixture } from '../results/fixtures';
import { LEVELS } from '../results/presentation';
export function mapFixture(allLevels = false, vertices = 180, overlap = false): AnalysisResponse {
  const response = resultFixture(allLevels ? 'ALL_BLOCKED' : 'RECOMMENDED');
  response.trip.origin = { label: 'Synthetic Chicago', longitude: -87.6298, latitude: 41.8781 };
  response.trip.destination = { label: 'Synthetic Detroit', longitude: -83.0458, latitude: 42.3314 };
  response.routes.forEach((route, order) => {
    const count = order ? 180 : vertices;
    route.geometry = Array.from({ length: count }, (_, i): Position => { const t = i / (count - 1); return [-87.6298 + 4.584 * t, 41.8781 + .4533 * t + Math.sin(t * Math.PI) * (overlap ? .1 : (order - 1) * .45)]; });
    route.summary.total_miles = exact(283); route.distance_m = exact(455444); route.duration_s = exact(15420 + order * 420);
    const base = route.checkpoints[0]!;
    route.checkpoints = Array.from({ length: 6 }, (_, index) => {
      const cp = structuredClone(base), level = allLevels && order === 0 ? LEVELS[index]! : ['LOW', 'MODERATE', 'HIGH', 'SEVERE', 'LOW', allLevels ? 'NO_TRAVEL' : 'MODERATE'][index] as typeof base.risk.final_risk;
      cp.index = index; cp.id = `synthetic-${order}-${index}`; cp.coordinate = route.geometry[Math.round(index / 5 * (count - 1))]!;
      cp.mile_marker = exact(566 * index, '10'); cp.owned_miles = exact(index === 0 || index === 5 ? 283 : 566, '10'); cp.risk.final_risk = level;
      cp.risk.known_blocked = level === 'NO_TRAVEL'; cp.risk.known_risk_floor = level === 'UNKNOWN' ? null : level;
      cp.weather.unavailable_reason = level === 'UNKNOWN' ? 'MISSING_FIELD' : null; cp.utc_fallback = true; cp.timezone = null;
      return cp;
    });
    route.summary.miles_by_level = Object.fromEntries(LEVELS.map(l => [l, exact(route.checkpoints.filter(cp => cp.risk.final_risk === l).reduce((sum, cp) => sum + Number(cp.owned_miles.numerator), 0), '10')]));
    if (allLevels && order === 0) { route.rank = null; route.group = 'UNRANKED'; route.summary.average_risk = null; route.summary.unknown_miles = exact(283, '10'); route.summary.coverage_fraction = exact(9, '10'); }
  });
  if (allLevels) response.least_blocked_route_id = response.routes[1]!.route_id;
  return response;
}
