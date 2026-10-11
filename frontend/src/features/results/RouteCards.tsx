import { useRef } from 'react';
import type { AnalysisResponse, Route } from '../../api/types';
import { useSelection } from '../../api/selection-store';
import { keyboardIndex } from '../../components/controls';
import { RiskBadge } from '../../components/surfaces';
import { arrival, average, duration, miles, percent } from '../../lib/format';
import { MiniRiskStrip } from './RiskDistance';
import { LEVELS, eligibleRecommended } from './presentation';
import { routeStatus } from './ComparisonMatrix';
import { WarningList, warningText } from './Warnings';

export function RouteCards({ response, routes, labels }: { response: AnalysisResponse; routes: Route[]; labels: Map<string, string> }) {
  const selection = useSelection(), group = useRef<HTMLDivElement>(null), recommended = eligibleRecommended(response);
  const selected = routes.find(r => r.route_id === selection.selectedRouteId);
  return <section className="routes-section"><h3>Route options</h3><div ref={group} role="radiogroup" aria-label="Select a route" className="route-options">{routes.map((r, i) => {
    const warnings = response.warnings.filter(w => w.scope === r.route_id), eta = arrival(r.checkpoints.at(-1));
    return <button type="button" role="radio" key={r.route_id} aria-checked={selection.selectedRouteId === r.route_id} tabIndex={selection.selectedRouteId === r.route_id || !selected && i === 0 ? 0 : -1} className={`route-option ${selection.selectedRouteId === r.route_id ? 'is-selected' : ''}`} onMouseEnter={() => selection.hoverRoute(r.route_id)} onMouseLeave={() => selection.hoverRoute(null)} onClick={() => selection.selectRoute(r.route_id)} onKeyDown={e => {
      const next = keyboardIndex(e.key, i, routes.length);
      if (next === null) return;
      e.preventDefault(); selection.selectRoute(routes[next]!.route_id); group.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[next]?.focus();
    }}><span className="route-option-heading"><span className="rank-mark mono">{r.rank === null ? 'n/a' : `#${r.rank}`}</span><strong>{labels.get(r.route_id)}</strong><small className="route-status">{routeStatus(r, recommended?.route_id)}</small></span><span className="route-option-metrics mono"><span>{duration(r.duration_s)}</span><span>{miles(r.summary.total_miles)} mi</span><span>{eta.local}</span></span><span className="route-risk-stats"><span>Severe <b className="mono">{miles(r.summary.miles_by_level.SEVERE ?? { numerator: '0', denominator: '1' })} mi</b></span><span>High <b className="mono">{miles(r.summary.miles_by_level.HIGH ?? { numerator: '0', denominator: '1' })} mi</b></span><span className="mono">{warnings.length} notices</span></span><MiniRiskStrip route={r} />{warnings.map((w, index) => <span className="card-notice" key={index}>{warningText(w, response)}</span>)}{r.summary.known_blocked && <span className="known-block"><RiskBadge level="NO_TRAVEL" /> Known blocking evidence</span>}</button>;
  })}</div>{selected && <details className="route-details" key={selected.route_id} open><summary>Route details · {labels.get(selected.route_id)}</summary><div className="details-content"><p className="mono">{percent(selected.summary.coverage_fraction)} coverage · {selected.checkpoints.length} checkpoints · {response.trip.effective_interval_miles} mi spacing</p><p>Average risk <span className="mono">{average(selected.summary.average_risk)}</span><small className="field-hint">1 Low to 5 No Travel</small></p><table><caption className="sr-only">Miles by risk level</caption><tbody>{LEVELS.map(level => <tr key={level}><th scope="row"><RiskBadge level={level} /></th><td className="mono">{miles(selected.summary.miles_by_level[level] ?? { numerator: '0', denominator: '1' })} mi</td></tr>)}</tbody></table><WarningList warnings={response.warnings.filter(w => w.scope === selected.route_id)} response={response} /></div></details>}</section>;
}
