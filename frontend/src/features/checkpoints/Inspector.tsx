import { useState } from 'react';
import type { AnalysisResponse, Checkpoint, Route } from '../../api/types';
import { useSelectionStore, useSelection } from '../../api/selection-store';
import { RiskBadge } from '../../components/surfaces';
import { arrival, decimal, fixed, miles, time, displayNumber } from '../../lib/format';
import { ADVISORY } from '../results/ResultsView';
import { routeLabels } from '../results/presentation';
import { decodeAnalysis } from '../heatmap/decoder';
import { jumpHour } from '../heatmap/presentation';
import { UNAVAILABLE, loadEscalated, reasonText } from './reasons';
import { CheckpointSteps, orderedCheckpoints } from './selection';

export function WeatherReadout({ checkpoint, compact = false }: { checkpoint: Checkpoint; compact?: boolean }) {
  const cp = checkpoint, fields = [['Wind', cp.weather.values.wind_mph, 'mph', cp.risk.wind_risk], ['Rain', cp.weather.values.rain_in_hr, 'in/hr', cp.risk.rain_risk], ['Snow', cp.weather.values.snow_in_hr, 'in/hr', cp.risk.snow_risk]] as const;
  return <div className={`weather-readout ${compact ? 'is-compact' : ''}`}>{fields.map(([label, value, unit, risk]) => <div key={label}><span className="micro">{label}</span><span className="mono weather-value">{decimal(value)} <small>{unit}</small></span>{!compact && <><RiskBadge level={risk} />{value === null && <small>{cp.weather.unavailable_reason ? UNAVAILABLE[cp.weather.unavailable_reason].title : 'Required measurement unavailable'}</small>}</>}</div>)}</div>;
}
export function Inspector({ response, route, checkpoint }: { response: AnalysisResponse; route: Route; checkpoint: Checkpoint }) {
  const cp = checkpoint, points = orderedCheckpoints(route), at = points.findIndex(p => p.index === cp.index), eta = arrival(cp), [copy, setCopy] = useState(''), labels = routeLabels(response);
  const coordinate = cp.coordinate?.length === 2 && cp.coordinate.every(Number.isFinite) ? `${fixed(cp.coordinate[1], 4)}, ${fixed(cp.coordinate[0], 4)}` : 'n/a';
  const ages = response.metadata.weather_cache.ages_seconds.map(displayNumber).filter((v): v is number => v !== null);
  const age = Math.max(0, ...ages, (Date.parse(response.generated_at) - Date.parse(cp.weather.fetched_at)) / 1000);
  const copyCoordinate = async () => { try { if (coordinate === 'n/a' || !navigator.clipboard) throw new Error(); await navigator.clipboard.writeText(coordinate); setCopy('Coordinates copied'); } catch { setCopy('Copy unavailable; select the coordinate text'); } };
  return <section className="checkpoint-inspector" aria-label="Checkpoint inspector"><div className="inspector-values" key={cp.id}><header><p className="micro">{labels.get(route.route_id)} · {route.travel_status === 'BLOCKED' ? 'Blocked · inspectable, not recommended' : route.travel_status === 'INCOMPLETE' ? 'Incomplete assessment' : 'Arrival-time assessment'}</p><h4>Checkpoint {at + 1} of {points.length}</h4><p className="mono">Mile {miles(cp.mile_marker)} of {miles(route.summary.total_miles)}</p><RiskBadge level={cp.risk.final_risk} /></header>
    <div className="coordinate-row"><span className="mono">{coordinate} <small>lat, lon · degrees</small></span><button type="button" onClick={() => { void copyCoordinate(); }} aria-label="Copy checkpoint coordinates">Copy</button><span role="status" className="field-hint">{copy}</span></div>
    <dl className="checkpoint-times"><dt className="micro">Estimated arrival</dt><dd className="mono">{eta.local}{cp.utc_fallback && ' · UTC fallback'}</dd><dd className="mono field-hint">{eta.utc}</dd><dt className="micro">Forecast hour used</dt><dd>Forecast for <span className="mono">{time(cp.weather.forecast_timestamp, 'UTC')}</span>, valid for the hour ending at that time.</dd><dd className="mono field-hint">{cp.weather.forecast_timestamp}</dd></dl>
    {cp.weather.unavailable_reason && <div className="checkpoint-unavailable" data-reason={cp.weather.unavailable_reason}><h5>{UNAVAILABLE[cp.weather.unavailable_reason].title}</h5><p>{UNAVAILABLE[cp.weather.unavailable_reason].text}</p><small className="mono">{cp.weather.unavailable_reason}</small></div>}
    {cp.risk.final_risk === 'UNKNOWN' && <div className="checkpoint-evidence">{cp.risk.known_blocked && <strong>Known No Travel evidence present even though the full assessment is incomplete</strong>}{cp.risk.known_risk_floor && <p>At least <RiskBadge level={cp.risk.known_risk_floor} /></p>}<p>Unknown has no ordinal. Unavailable measurements are not zero.</p></div>}
    <WeatherReadout checkpoint={cp} />{cp.weather.values.gust_mph !== null && <p className="field-hint mono">Gust {decimal(cp.weather.values.gust_mph)} mph · display only</p>}
    <div className="rules-heading"><h5>Rules chain</h5><span className="mono">Cargo {decimal(response.trip.load_weight_lb)} lb</span></div><ol className="rules-ladder"><li><span>Hazard level</span><RiskBadge level={cp.risk.hazard_risk} /></li><li><span>Load-adjusted wind</span><RiskBadge level={cp.risk.load_adjusted_wind_risk} /></li><li><span>Final level</span><RiskBadge level={cp.risk.final_risk} /></li><li className={loadEscalated(cp.risk) ? 'load-applied' : ''}><span>{loadEscalated(cp.risk) ? 'Load rule applied' : 'Load-rule evidence'}</span><p>{cp.risk.reasons.filter(r => r.code !== 'HAZARD_CLASSIFIED' && r.code !== 'MISSING_HAZARD').map(reasonText).join(' ') || 'No load escalation reported by the API.'}</p></li></ol>
    <details className="checkpoint-reasons" open><summary>All assessment reasons · {cp.risk.reasons.length}</summary><ul>{cp.risk.reasons.map((reason, i) => <li key={i}>{reasonText(reason)}</li>)}</ul></details>
    <footer><p className="mono">Forecast age at analysis: {Number.isFinite(age) ? `${fixed(age, 0, 1n, 60n)} min` : 'unavailable'}</p><p className="mono">Fetched {cp.weather.fetched_at} · {cp.weather.provider} / {cp.weather.model}</p><p>{ADVISORY}</p></footer></div><CheckpointSteps route={route} /></section>;
}
export function InspectorDock({ response }: { response: AnalysisResponse }) {
  const heatStore = useSelectionStore(), decoded = decodeAnalysis(response);
  const selection = useSelection(), route = response.routes.find(r => r.route_id === selection.selectedRouteId), cp = route?.checkpoints.find(c => c.index === selection.selectedCheckpointIndex), [details, setDetails] = useState(false);
  if (!route || !cp) return null;
  return <aside className={`inspector-dock ${details ? 'is-expanded' : ''}`} aria-label="Selected checkpoint dock"><div className="dock-summary"><div><p className="mono">Mile {miles(cp.mile_marker)} of {miles(route.summary.total_miles)}</p><RiskBadge level={cp.risk.final_risk} /></div><button type="button" aria-label="Close checkpoint inspector" onClick={() => selection.selectCheckpoint(null)}>×</button></div><WeatherReadout checkpoint={cp} compact />{decoded.kind === 'ready' && <button type="button" className="heat-jump" title={`Exact arrival ${cp.eta_utc}; snaps to nearest forecast hour`} onClick={() => heatStore.setHour(jumpHour(cp, decoded.data), true)}>Jump to arrival at mile {miles(cp.mile_marker)} <small>{cp.eta_utc} · nearest hour</small></button>}<div className="dock-controls"><CheckpointSteps route={route} /><button type="button" aria-expanded={details} aria-controls="dock-details" onClick={() => setDetails(v => !v)}>Details {details ? '−' : '+'}</button></div>{details && <div id="dock-details" className="dock-details"><Inspector response={response} route={route} checkpoint={cp} /></div>}</aside>;
}
