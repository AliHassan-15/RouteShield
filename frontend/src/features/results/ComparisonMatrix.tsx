import type { AnalysisResponse, FactValue, Route } from '../../api/types';
import { useSelection } from '../../api/selection-store';
import { RiskBadge } from '../../components/surfaces';
import { criterionValue, percent } from '../../lib/format';
import { CRITERIA, eligibleRecommended } from './presentation';

export function routeStatus(route: Route, recommendedId?: string): string {
  if (route.travel_status === 'BLOCKED') return 'Blocked';
  if (route.travel_status === 'INCOMPLETE') return 'Incomplete';
  return route.route_id === recommendedId ? 'Recommended' : route.rank === null ? 'Unranked' : `Ranked ${route.rank}`;
}
export function ComparisonMatrix({ response, routes, labels }: { response: AnalysisResponse; routes: Route[]; labels: Map<string, string> }) {
  const selection = useSelection(), recommended = eligibleRecommended(response);
  const rows: { code: string; key: keyof Route['criteria']; label: string; number?: number }[] = [
    ...(routes.some(r => r.travel_status === 'BLOCKED') ? [{ code: 'NO_TRAVEL_MILES', key: 'no_travel_miles' as const, label: 'No Travel miles' }] : []),
    ...CRITERIA.map((row, i) => ({ ...row, number: i + 1 })),
  ];
  const decisive = rows.findIndex(row => row.code === response.decisive_criterion);
  return <section className="matrix-section"><h3>Compare routes</h3><p className="field-hint">Server ranking · priorities in order</p><div className="matrix-scroll"><table className="comparison-matrix"><caption className="sr-only">Route comparison in server ranking order</caption><thead><tr><th scope="col">Priority</th>{routes.map(r => <th scope="col" key={r.route_id} className={`${selection.selectedRouteId === r.route_id ? 'is-selected' : ''} ${r.travel_status === 'BLOCKED' ? 'blocked-heading' : ''}`}><button type="button" onClick={() => selection.selectRoute(r.route_id)} aria-pressed={selection.selectedRouteId === r.route_id}><span>{labels.get(r.route_id)}</span><span className="mono">{r.rank === null ? 'n/a' : `#${r.rank}`}</span><small>{routeStatus(r, recommended?.route_id)}</small>{r.travel_status === 'BLOCKED' && <RiskBadge level="NO_TRAVEL" />}</button></th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={row.code} data-criterion={row.code} className={`${i === decisive ? 'decisive' : ''} ${decisive >= 0 && i > decisive ? 'after-decision' : ''}`}><th scope="row">{row.number && <span className="priority-number mono">{row.number}</span>}<span>{row.label}</span>{i === decisive && <small className="micro">Decides</small>}</th>{routes.map(r => {
    // Mark only a winning fact published for this exact criterion. No minimum
    // scan, rounding comparison or inferred ties on the browser.
    const marked = response.comparison_facts.some(f => f.winner_route_id === r.route_id && f.criterion === row.code && f.code === row.code);
    const incomplete = r.summary.average_risk === null;
    return <td key={r.route_id} className={selection.selectedRouteId === r.route_id ? 'is-selected' : ''}><span className="matrix-value mono">{incomplete ? 'n/a' : criterionValue(row.code, r.criteria[row.key] as FactValue)}{marked && !incomplete && <i className="fact-tick" aria-label="Winning API comparison fact" />}</span>{incomplete && <small className="mono">{percent(r.summary.coverage_fraction)}</small>}</td>;
  })}</tr>)}</tbody></table></div><p className="matrix-key field-hint"><i className="fact-tick" /> API comparison winner · <span>Muted rows: Not needed to decide</span></p>{response.decisive_criterion === 'TIE_BROKEN_BY_ID' && <p className="info-note">{response.explanation_facts.filter(f => f.code === 'TIE_BROKEN_BY_ID').map(f => `${labels.get(f.route_id ?? '')} / ${labels.get(f.other_route_id ?? '')}`).join(' · ')} · Stable geometry identifier decides (API)</p>}</section>;
}
