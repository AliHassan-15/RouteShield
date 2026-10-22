import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import type { AnalysisSnapshot } from '../../api/analysis-store';
import type { AnalysisResponse, Route } from '../../api/types';
import { Button, SegmentedControl, Select } from '../../components/controls';
import { useSelection } from '../../api/selection-store';
import { CheckpointList } from '../map/CheckpointList';
import { useCheckpointKeys } from '../checkpoints/selection';
import { Icon } from '../../components/icons';
import { RequestId } from '../../components/RequestId';
import { Skeleton } from '../../components/surfaces';
import { arrival, criterionValue, decimal, displayNumber, duration, fixed, miles, time } from '../../lib/format';
import { useReducedMotion } from '../../lib/motion';
import { ARRIVAL, arrivalFor, phase, useArrival } from '../../lib/arrival';
import { ComparisonMatrix } from './ComparisonMatrix';
import { RiskDistance } from './RiskDistance';
import { RouteCards } from './RouteCards';
import { Coverage, WarningsTray } from './Warnings';
import { CRITERIA, eligibleRecommended, labelText, routeLabels, serverOrder } from './presentation';

export const ADVISORY = 'Weather-based planning aid. Forecasts and truck restrictions may be incomplete; verify conditions and road restrictions before travel.';
const ProfileView = lazy(() => import('../checkpoints/CheckpointViews'));
export type ResultsSubView = 'compare' | 'profile' | 'checkpoints';
export function readResultsSubView(): ResultsSubView { try { const value = sessionStorage.getItem('routeshield-results-view'); return value === 'profile' || value === 'checkpoints' ? value : 'compare'; } catch { return 'compare'; } }
export function CountMetric({ value, format, analysis }: { value: unknown; format: (v: unknown) => string; analysis: object }) {
  const reduced = useReducedMotion(), timeline = arrivalFor(analysis), [progress, setProgress] = useState(() => reduced ? 1 : phase(timeline.elapsed(), 0, ARRIVAL.count)), target = displayNumber(value);
  useEffect(() => {
    if (reduced) return;
    let frame = 0;
    const tick = () => { cancelAnimationFrame(frame); const p = phase(timeline.elapsed(), 0, ARRIVAL.count); setProgress(p); if (p < 1) frame = requestAnimationFrame(tick); };
    const off = timeline.subscribe(tick); tick(); return () => { off(); cancelAnimationFrame(frame); };
  }, [reduced, timeline]);
  return <span className="count-metric mono"><span className="metric-reserve">{format(value)}</span><span aria-hidden="true" className="metric-animated">{progress >= 1 || reduced || target === null ? format(value) : format(String(target * progress))}</span><span className="sr-only">{format(value)}</span></span>;
}
function RecommendationHero({ response, route, labels }: { response: AnalysisResponse; route: Route; labels: Map<string, string> }) {
  const eta = arrival(route.checkpoints.at(-1));
  return <section className="recommendation-ticket" aria-label="Recommendation"><p className="micro ticket-status"><Icon name="route" />{response.message}</p><h3>{labels.get(route.route_id)}</h3><div className="ticket-metrics"><div><p className="micro">Duration</p><CountMetric analysis={response} value={route.duration_s} format={duration} /></div><div><p className="micro">Distance</p><CountMetric analysis={response} value={route.summary.total_miles} format={v => `${miles(v)} mi`} /></div><div className="arrival-tile"><p className="micro">Arrival · destination time</p><strong className="mono">{eta.local}</strong><small className="mono">{eta.utc}</small></div></div><RiskDistance summary={route.summary} /><div className="why-route"><h4>Why this route</h4><p>{response.message}</p><dl className="fact-rows">{response.explanation_facts.filter(f => CRITERIA.some(c => c.code === f.code) || f.code === 'NO_TRAVEL_MILES' || f.code === 'TIE_BROKEN_BY_ID').map((f, i) => <div key={i}><dt>{CRITERIA.find(c => c.code === f.code)?.label ?? (f.code === 'NO_TRAVEL_MILES' ? 'No Travel miles' : 'Stable identifier')}</dt><dd><span>{labels.get(f.route_id ?? '')} / {labels.get(f.other_route_id ?? '')}</span><span className="mono">{f.code === 'TIE_BROKEN_BY_ID' ? 'Exact numeric tie' : `${criterionValue(f.code, f.values.winner_value ?? null)} vs ${criterionValue(f.code, f.values.other_value ?? null)}`}</span></dd></div>)}</dl><p className="api-explanation">{labelText(response.explanation, labels)}</p></div></section>;
}
type StatusProps = { response: AnalysisResponse; labels: Map<string, string> };
function Recommended({ response, labels }: StatusProps) { const route = eligibleRecommended(response); return route ? <RecommendationHero response={response} route={route} labels={labels} /> : <div className="result-banner">Recommendation data unavailable.</div>; }
function BestAvailable(props: StatusProps) { return <><Recommended {...props} /><div className="result-banner"><p>{props.response.message}</p><p>Only one fully assessed route is eligible. Review alternatives and weather coverage.</p><Coverage {...props} /></div></>; }
function AllBlocked({ response, labels }: StatusProps) { const diagnostic = response.routes.find(r => r.route_id === response.least_blocked_route_id && r.travel_status === 'BLOCKED' && r.summary.average_risk !== null); return <div className="result-banner blocked-banner"><h3>{response.message}</h3><p>{labelText(response.explanation, labels)}</p>{diagnostic && <p><strong>Least blocked, not recommended</strong><span>{labels.get(diagnostic.route_id)} · <span className="mono">{miles(diagnostic.summary.no_travel_miles)} mi No Travel</span></span></p>}<Coverage response={response} /></div>; }
function NoFullyAssessed({ response, labels }: StatusProps) { return <div className="result-banner"><h3>{response.message}</h3><p>{labelText(response.explanation, labels)}</p><Coverage response={response} /></div>; }
function AllIncomplete(props: StatusProps) { return <div className="result-banner"><h3>{props.response.message}</h3><p>{labelText(props.response.explanation, props.labels)}</p><Coverage response={props.response} /></div>; }
const STATUS = { RECOMMENDED: Recommended, BEST_FULLY_ASSESSED_AVAILABLE: BestAvailable, ALL_BLOCKED: AllBlocked, NO_FULLY_ASSESSED_TRAVELABLE_ROUTE: NoFullyAssessed, ALL_INCOMPLETE: AllIncomplete };
export function ResultsSkeleton() { return <div className="results-skeleton" aria-label="Results loading"><Skeleton label="Preparing recommendation" lines={5} /><div className="skeleton-matrix"><Skeleton label="Preparing comparison" lines={5} /></div><Skeleton label="Preparing routes" lines={3} /></div>; }
export function ResultsView({ snapshot, rerun, disabled, changed, view: controlledView, onViewChange }: { snapshot: AnalysisSnapshot; rerun: () => void; disabled: boolean; changed: boolean; view?: ResultsSubView; onViewChange?: (view: ResultsSubView) => void }) {
  const response = snapshot.response, labels = routeLabels(response), routes = serverOrder(response.routes), Component = STATUS[response.recommendation_status];
  const selection = useSelection(), route = routes.find(r => r.route_id === selection.selectedRouteId) ?? routes[0], [internalView, setInternalView] = useState(readResultsSubView), view = controlledView ?? internalView, viewHeading = useRef<HTMLHeadingElement>(null);
  useCheckpointKeys(route);
  useEffect(() => { if (route && selection.selectedRouteId !== route.route_id) selection.selectRoute(route.route_id); }, [route, selection.selectedRouteId, selection.selectRoute]);
  const changeView = (next: string) => { const choice = next as ResultsSubView; setInternalView(choice); onViewChange?.(choice); try { sessionStorage.setItem('routeshield-results-view', choice); } catch { /* Optional session preference. */ } requestAnimationFrame(() => viewHeading.current?.focus({ preventScroll: true })); };
  const [now, setNow] = useState(Date.now()), { arrival: timeline, done } = useArrival(response);
  const entranceOffset = useRef(timeline.elapsed());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 30_000); return () => clearInterval(timer); }, []);
  const generated = Date.parse(response.generated_at), stale = Number.isFinite(generated) && (now - generated >= 900_000 || now >= Date.parse(response.expires_at));
  const ages = response.metadata.weather_cache.ages_seconds.map(displayNumber).filter((n): n is number => n !== null);
  const fetched = response.routes.flatMap(r => r.checkpoints.map(c => Date.parse(c.weather.fetched_at))).filter(Number.isFinite);
  // Display oldest fetch age, including cache metadata. No forecast selection.
  const age = Math.max(0, ...ages.map(a => a + Math.max(0, now - generated) / 1000), ...fetched.map(t => (now - t) / 1000));
  return <div className={`results-body ${done ? 'has-entered' : ''}`} style={{ '--arrival-offset': `${-entranceOffset.current}ms` } as React.CSSProperties}>{(response.metadata.simulated || response.is_simulation) && <div className="simulation-banner"><strong>SIMULATION</strong><span>{response.simulation_scenario ?? 'Scenario unspecified'}</span></div>}
    <div className="trip-summary"><p>{response.trip.origin.label} <span aria-hidden="true">→</span> {response.trip.destination.label}</p><div><span className="mono">{decimal(response.trip.load_weight_lb)} lb</span><span className="mono">{time(response.trip.departure_time, response.trip.departure_timezone, true)}</span></div><span className="field-hint">{response.trip.departure_timezone}</span></div>
    {changed && <div className="result-banner"><p>Inputs changed since this analysis</p><Button onClick={rerun} disabled={disabled}>Re-run</Button></div>}
    {stale && <div className="result-banner stale-banner"><p>Results are older than 15 minutes. Re-run the analysis for a current recommendation.</p><Button onClick={rerun} disabled={disabled}>Re-run</Button></div>}
    <p className="freshness mono">Analyzed at {time(response.generated_at, response.trip.departure_timezone)} · {ages.length || fetched.length ? `forecast fetched ${fixed(age, 0, 1n, 60n)} min ago` : 'forecast fetch age unavailable'}</p>
    <div className="results-subnav"><SegmentedControl label="Results view" value={view} options={[{ value: 'compare', label: 'Compare' }, { value: 'profile', label: 'Profile' }, { value: 'checkpoints', label: 'Checkpoints' }]} onChange={changeView} /><span className="results-view-indicator" style={{ transform: `translateX(${['compare', 'profile', 'checkpoints'].indexOf(view) * 100}%)` }} /></div>
    <h3 className="results-view-heading" ref={viewHeading} tabIndex={-1}>{view === 'compare' ? 'Route comparison' : view === 'profile' ? 'Risk profile' : 'Ordered checkpoints'}</h3>
    <div className="results-subview" key={view}>{view === 'compare' ? <><Component response={response} labels={labels} /><ComparisonMatrix response={response} routes={routes} labels={labels} /><RouteCards response={response} routes={routes} labels={labels} /></> : <><Select label="Inspected route" value={route?.route_id ?? ''} onChange={e => selection.selectRoute(e.target.value)}>{routes.map(r => <option key={r.route_id} value={r.route_id}>{labels.get(r.route_id)} · {r.travel_status === 'BLOCKED' ? 'Blocked' : r.travel_status === 'INCOMPLETE' ? 'Incomplete' : 'Assessed'}</option>)}</Select>{view === 'profile' ? <Suspense fallback={<Skeleton label="Preparing checkpoint profile" />}><ProfileView response={response} /></Suspense> : route && <CheckpointList route={route} />}</>}
    </div><WarningsTray response={response} />
    <footer className="results-footer"><p>{ADVISORY}</p><ul>{response.attributions.map((a, i) => <li key={`${a.provider}-${i}`}><span className="micro">{a.provider}{!a.confirmed && ' · Unconfirmed attribution'}</span><p>{a.text}</p></li>)}</ul><RequestId id={response.metadata.request_id} /><p className="mono">Server computation {fixed(response.metadata.total_ms, 0)} ms</p><p>No live traffic. Durations are static estimates.</p></footer>
  </div>;
}
