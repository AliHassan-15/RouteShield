import { useEffect, useState } from 'react';
import type { AnalysisSnapshot } from '../../api/analysis-store';
import type { AnalysisResponse, Route } from '../../api/types';
import { Button } from '../../components/controls';
import { Icon } from '../../components/icons';
import { RequestId } from '../../components/RequestId';
import { Skeleton } from '../../components/surfaces';
import { arrival, criterionValue, decimal, displayNumber, duration, fixed, miles, time } from '../../lib/format';
import { useReducedMotion } from '../../lib/motion';
import { ComparisonMatrix } from './ComparisonMatrix';
import { RiskDistance } from './RiskDistance';
import { RouteCards } from './RouteCards';
import { Coverage, WarningsTray } from './Warnings';
import { CRITERIA, eligibleRecommended, labelText, routeLabels, serverOrder } from './presentation';

export const ADVISORY = 'Weather-based planning aid. Forecasts and truck restrictions may be incomplete; verify conditions and road restrictions before travel.';
function CountMetric({ value, format }: { value: unknown; format: (v: unknown) => string }) {
  const reduced = useReducedMotion(), [progress, setProgress] = useState(reduced ? 1 : 0), target = displayNumber(value);
  useEffect(() => {
    if (reduced) return;
    let frame = 0, start: number | undefined;
    const tick = (now: number) => { start ??= now; const p = Math.min(1, (now - start) / 480); setProgress(p); if (p < 1) frame = requestAnimationFrame(tick); };
    frame = requestAnimationFrame(tick); return () => cancelAnimationFrame(frame);
  }, [reduced]);
  return <span className="count-metric mono"><span className="metric-reserve">{format(value)}</span><span aria-hidden="true" className="metric-animated">{progress >= 1 || reduced || target === null ? format(value) : format(String(target * progress))}</span><span className="sr-only">{format(value)}</span></span>;
}
function RecommendationHero({ response, route, labels }: { response: AnalysisResponse; route: Route; labels: Map<string, string> }) {
  const eta = arrival(route.checkpoints.at(-1));
  return <section className="recommendation-ticket" aria-label="Recommendation"><p className="micro ticket-status"><Icon name="route" />{response.message}</p><h3>{labels.get(route.route_id)}</h3><div className="ticket-metrics"><div><p className="micro">Duration</p><CountMetric value={route.duration_s} format={duration} /></div><div><p className="micro">Distance</p><CountMetric value={route.summary.total_miles} format={v => `${miles(v)} mi`} /></div><div className="arrival-tile"><p className="micro">Arrival · destination time</p><strong className="mono">{eta.local}</strong><small className="mono">{eta.utc}</small></div></div><RiskDistance summary={route.summary} /><div className="why-route"><h4>Why this route</h4><p>{response.message}</p><dl className="fact-rows">{response.explanation_facts.filter(f => CRITERIA.some(c => c.code === f.code) || f.code === 'NO_TRAVEL_MILES' || f.code === 'TIE_BROKEN_BY_ID').map((f, i) => <div key={i}><dt>{CRITERIA.find(c => c.code === f.code)?.label ?? (f.code === 'NO_TRAVEL_MILES' ? 'No Travel miles' : 'Stable identifier')}</dt><dd><span>{labels.get(f.route_id ?? '')} / {labels.get(f.other_route_id ?? '')}</span><span className="mono">{f.code === 'TIE_BROKEN_BY_ID' ? 'Exact numeric tie' : `${criterionValue(f.code, f.values.winner_value ?? null)} vs ${criterionValue(f.code, f.values.other_value ?? null)}`}</span></dd></div>)}</dl><p className="api-explanation">{labelText(response.explanation, labels)}</p></div></section>;
}
type StatusProps = { response: AnalysisResponse; labels: Map<string, string> };
function Recommended({ response, labels }: StatusProps) { const route = eligibleRecommended(response); return route ? <RecommendationHero response={response} route={route} labels={labels} /> : <div className="result-banner">Recommendation data unavailable.</div>; }
function BestAvailable(props: StatusProps) { return <><Recommended {...props} /><div className="result-banner"><p>{props.response.message}</p><p>Only one fully assessed route is eligible. Review alternatives and weather coverage.</p><Coverage {...props} /></div></>; }
function AllBlocked({ response, labels }: StatusProps) { const diagnostic = response.routes.find(r => r.route_id === response.least_blocked_route_id && r.travel_status === 'BLOCKED' && r.summary.average_risk !== null); return <div className="result-banner blocked-banner"><h3>{response.message}</h3><p>{labelText(response.explanation, labels)}</p>{diagnostic && <p><strong>Least blocked, not recommended</strong><span>{labels.get(diagnostic.route_id)} · <span className="mono">{miles(diagnostic.summary.no_travel_miles)} mi No Travel</span></span></p>}<Coverage response={response} /></div>; }
function NoFullyAssessed({ response, labels }: StatusProps) { return <div className="result-banner"><h3>{response.message}</h3><p>{labelText(response.explanation, labels)}</p><Coverage response={response} /></div>; }
function AllIncomplete(props: StatusProps) { return <div className="result-banner"><h3>{props.response.message}</h3><p>{labelText(props.response.explanation, props.labels)}</p><Coverage response={props.response} /></div>; }
const STATUS = { RECOMMENDED: Recommended, BEST_FULLY_ASSESSED_AVAILABLE: BestAvailable, ALL_BLOCKED: AllBlocked, NO_FULLY_ASSESSED_TRAVELABLE_ROUTE: NoFullyAssessed, ALL_INCOMPLETE: AllIncomplete };
export function ResultsSkeleton() { return <div className="results-skeleton" aria-label="Results loading"><Skeleton label="Preparing recommendation" lines={5} /><div className="skeleton-matrix"><Skeleton label="Preparing comparison" lines={5} /></div><Skeleton label="Preparing routes" lines={3} /></div>; }
export function ResultsView({ snapshot, rerun, disabled, changed }: { snapshot: AnalysisSnapshot; rerun: () => void; disabled: boolean; changed: boolean }) {
  const response = snapshot.response, labels = routeLabels(response), routes = serverOrder(response.routes), Component = STATUS[response.recommendation_status];
  const [now, setNow] = useState(Date.now()), [entered, setEntered] = useState(false);
  useEffect(() => { const timer = setTimeout(() => setEntered(true), 650); return () => clearTimeout(timer); }, []);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 30_000); return () => clearInterval(timer); }, []);
  const generated = Date.parse(response.generated_at), stale = Number.isFinite(generated) && (now - generated >= 900_000 || now >= Date.parse(response.expires_at));
  const ages = response.metadata.weather_cache.ages_seconds.map(displayNumber).filter((n): n is number => n !== null);
  const fetched = response.routes.flatMap(r => r.checkpoints.map(c => Date.parse(c.weather.fetched_at))).filter(Number.isFinite);
  // Display oldest fetch age, including cache metadata. No forecast selection.
  const age = Math.max(0, ...ages.map(a => a + Math.max(0, now - generated) / 1000), ...fetched.map(t => (now - t) / 1000));
  return <div className={`results-body ${entered ? 'has-entered' : ''}`}>{(response.metadata.simulated || response.is_simulation) && <div className="simulation-banner"><strong>SIMULATION</strong><span>{response.simulation_scenario ?? 'Scenario unspecified'}</span></div>}
    <div className="trip-summary"><p>{response.trip.origin.label} <span aria-hidden="true">→</span> {response.trip.destination.label}</p><div><span className="mono">{decimal(response.trip.load_weight_lb)} lb</span><span className="mono">{time(response.trip.departure_time, response.trip.departure_timezone, true)}</span></div><span className="field-hint">{response.trip.departure_timezone}</span></div>
    {changed && <div className="result-banner"><p>Inputs changed since this analysis</p><Button onClick={rerun} disabled={disabled}>Re-run</Button></div>}
    {stale && <div className="result-banner stale-banner"><p>Results are older than 15 minutes. Re-run the analysis for a current recommendation.</p><Button onClick={rerun} disabled={disabled}>Re-run</Button></div>}
    <p className="freshness mono">Analyzed at {time(response.generated_at, response.trip.departure_timezone)} · {ages.length || fetched.length ? `forecast fetched ${fixed(age, 0, 1n, 60n)} min ago` : 'forecast fetch age unavailable'}</p>
    <Component response={response} labels={labels} /><ComparisonMatrix response={response} routes={routes} labels={labels} /><RouteCards response={response} routes={routes} labels={labels} /><WarningsTray response={response} />
    <footer className="results-footer"><p>{ADVISORY}</p><ul>{response.attributions.map((a, i) => <li key={`${a.provider}-${i}`}><span className="micro">{a.provider}{!a.confirmed && ' · Unconfirmed attribution'}</span><p>{a.text}</p></li>)}</ul><RequestId id={response.metadata.request_id} /><p className="mono">Server computation {fixed(response.metadata.total_ms, 0)} ms</p><p>No live traffic. Durations are static estimates.</p></footer>
  </div>;
}
