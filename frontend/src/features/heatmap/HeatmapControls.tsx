import { useEffect, useMemo, useRef, useState } from 'react';
import type { AnalysisResponse, RiskLevel } from '../../api/types';
import { PLAY_STEP_MS, useHeatState, useSelection, useSelectionStore } from '../../api/selection-store';
import { RiskBadge } from '../../components/surfaces';
import { Icon } from '../../components/icons';
import { clampHour, dayTicks, DOMINANT, etaHour, hourLabel, LEVEL_NAMES, pointCounts, truckReadout } from './presentation';
import type { HeatFilter } from './decoder';
import './heatmap.css';

export function HeatmapLegend() {
  const heat = useHeatState(); if (heat.decoded?.kind !== 'ready') return null;
  const data = heat.decoded.data;
  return <section className="heat-legend" aria-label="Heatmap legend"><p className="micro">Heatmap / selected hour</p><div className="heat-swatches">{[1, 2, 3, 4, 5].map(code => <span key={code}><i style={{ color: `var(--risk-${LEVEL_NAMES[code]!.toLowerCase().replace('_', '-')})` }} /><RiskBadge level={LEVEL_NAMES[code] as RiskLevel} /></span>)}</div><p><span className="heat-unknown-key" /> UNKNOWN · hatched gray, known blocks retained</p><p><span className="heat-unavailable-key" /> Unavailable · dashed hollow ring</p><p>Blur shows where samples are, not probability. Colors are risk levels from the server.</p><p className="mono">{data.payload.point_count} points · optional gaps up to {Math.max(0, ...Object.values(data.payload.density.actual_optional_max_gap_miles)).toFixed(1)} mi</p></section>;
}

export default function HeatmapControls({ response, rerun }: { response: AnalysisResponse; rerun?: () => void }) {
  const store = useSelectionStore(), heat = useHeatState(), { selectedRouteId } = useSelection();
  const data = heat.decoded?.kind === 'ready' ? heat.decoded.data : null;
  const slider = useRef<HTMLDivElement>(null), live = useRef<HTMLSpanElement>(null), [expanded, setExpanded] = useState(false);
  const ticks = useMemo(() => data ? dayTicks(data.payload.reference_time) : [], [data]);
  const label = data ? hourLabel(data.payload.hour_0_timestamp, heat.heatHour) : null;
  const truck = data ? truckReadout(data, selectedRouteId, heat.heatHour, heat.heatFilter) : null;
  const last = data?.payload.forecast_coverage.last_usable_hour ?? 0;
  const counts = data ? pointCounts(data, heat.heatHour, heat.heatFilter) : null;
  const availability = heat.heatHour > last ? 'Unavailable: beyond forecast coverage' : counts?.[9] ? 'Partial forecast availability' : counts?.[0] ? 'Includes UNKNOWN conditions' : 'Forecast available';
  const summary = truck?.kind === 'arrived' ? 'Arrived' : truck?.kind === 'position' ? `Estimated mile ${truck.mile.toFixed(1)} · ${truck.level.replace('_', ' ')} · ${truck.dominant}${truck.blocked ? ' · Known No Travel evidence' : ''}` : 'Truck position unavailable';
  useEffect(() => {
    if (!heat.playing) return;
    const timer = setInterval(store.tick, PLAY_STEP_MS / heat.speed); return () => clearInterval(timer);
  }, [store, heat.playing, heat.speed]);
  useEffect(() => () => store.updateHeat({ playing: false }), [store]);
  useEffect(() => {
    if (!label || heat.playing || heat.dragging) return;
    const timer = setTimeout(() => { if (live.current) live.current.textContent = `${label.local}, ${label.offset}. ${availability}. ${summary}.`; }, 400);
    return () => clearTimeout(timer);
    // Announce explicit keyboard changes/pause, never every drag/play frame.
  }, [heat.announce]);
  if (!data || !label) return <section className="heat-control heat-failure" aria-label="Corridor forecast"><p>Heatmap unavailable for this analysis</p><p className="field-hint">{heat.decoded?.kind ?? 'not included'}. Forecast is part of the analysis response.</p>{rerun && <button type="button" onClick={rerun}>Re-run analysis</button>}</section>;
  const route = response.routes.find(r => r.route_id === selectedRouteId), arrival = route?.checkpoints.at(-1)?.eta_utc;
  const atPointer = (x: number) => { const rect = slider.current!.getBoundingClientRect(); store.setHour(clampHour((x - rect.left) / rect.width * 48)); };
  const grab = (event: React.PointerEvent<HTMLDivElement>) => { event.currentTarget.setPointerCapture?.(event.pointerId); store.updateHeat({ dragging: true, playing: false }); atPointer(event.clientX); };
  const release = () => store.updateHeat({ dragging: false });
  const key = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, number> = { ArrowLeft: heat.heatHour - 1, ArrowRight: heat.heatHour + 1, PageUp: heat.heatHour + 6, PageDown: heat.heatHour - 6, Home: 0, End: 48 };
    if (event.key in moves) { event.preventDefault(); store.setHour(moves[event.key]!, true); }
    else if (event.key.toLowerCase() === 'p') { event.preventDefault(); store.togglePlay(); }
  };
  return <section className="heat-control" aria-label="Corridor forecast" data-heat-hour={heat.heatHour}>
    <header className="heat-heading"><div><p className="micro">Corridor forecast at departure + {heat.heatHour} h</p><p className="heat-time mono" key={label.local}>{label.local}</p><p className="heat-utc mono">{label.utc} · {label.offset}</p></div><button type="button" role="switch" aria-label="Heatmap" aria-checked={heat.heatEnabled} onClick={() => store.updateHeat({ heatEnabled: !heat.heatEnabled })}>Heat {heat.heatEnabled ? 'on' : 'off'}</button></header>
    <div className="heat-slider" ref={slider} role="slider" tabIndex={0} aria-label="Forecast hour" aria-valuemin={0} aria-valuemax={48} aria-valuenow={heat.heatHour} aria-valuetext={`${label.local}; ${label.utc}; ${label.offset}; ${availability}`} onKeyDown={key} onPointerDown={grab} onPointerMove={e => { if (store.getHeat().dragging) atPointer(e.clientX); }} onPointerUp={release} onPointerCancel={release} onLostPointerCapture={release}>
      <div className="heat-track" />{last < 48 && <span className="heat-coverage" style={{ left: `${(last + .5) / 48 * 100}%` }} title={`No forecast data beyond ${data.payload.forecast_coverage.last_usable_timestamp}`} />}
      {Array.from({ length: 49 }, (_, h) => <span key={h} className={`heat-tick ${h % 6 === 0 ? 'major' : ''}`} style={{ left: `${h / 48 * 100}%` }}>{h % 6 === 0 && <small>{h}</small>}</span>)}
      {ticks.map(t => <span className="heat-day" key={t.hour} style={{ left: `${t.hour / 48 * 100}%` }} title={t.label}><span>{t.label}</span></span>)}
      {arrival && <span className="heat-arrival" style={{ left: `${etaHour(arrival, data.payload.reference_time) / 48 * 100}%` }} title={`Selected route arrival: ${arrival}`} aria-label={`Selected route arrival ${arrival}`} />}
      <span className="heat-thumb" style={{ transform: `translateX(${heat.heatHour / 48 * 100}cqw)` }} />
    </div>
    <div className="heat-play-row"><button type="button" aria-label={heat.playing ? 'Pause forecast' : 'Play forecast'} onClick={store.togglePlay}>{heat.playing ? 'Pause' : 'Play'} <span aria-hidden="true">{heat.playing ? 'Ⅱ' : '▷'}</span></button><div className="heat-speeds" role="group" aria-label="Playback speed">{[.5, 1, 2, 4].map(speed => <button type="button" key={speed} aria-pressed={heat.speed === speed} onClick={() => store.updateHeat({ speed })}>{speed}×</button>)}</div><button type="button" aria-expanded={expanded} onClick={() => setExpanded(v => !v)}>Options {expanded ? '−' : '+'}</button></div>
    <p className="heat-truck-readout mono"><Icon name="truck" /><span>{truck?.kind === 'position' ? <>Estimated mile {truck.mile.toFixed(1)} · {truck.level === 'UNAVAILABLE' ? <><i className="heat-unavailable-key" /> Unavailable</> : <RiskBadge level={truck.level} />} · {truck.dominant}{truck.blocked && ' · Known No Travel evidence'}</> : summary}<small>Conditions here at +{heat.heatHour} h · {availability}</small></span></p>
    <p className="heat-explanation">Heatmap shows weather along the corridor at the selected hour. Route risk is scored at each checkpoint's arrival time.</p>
    <div className="heat-options" hidden={!expanded}>
      {data.filters ? <div role="group" aria-label="Heatmap hazard filter" className="heat-filters">{(['combined', 'wind', 'rain', 'snow'] as HeatFilter[]).map(filter => <button type="button" key={filter} aria-pressed={heat.heatFilter === filter} onClick={() => store.updateHeat({ heatFilter: filter })}>{filter[0]!.toUpperCase() + filter.slice(1)}</button>)}</div> : <p>Hazard filters unavailable for this trip · {data.payload.hazard_filter_omission_reason ?? 'Codes not included'}</p>}
      <div className="heat-toggles"><button type="button" aria-pressed={heat.showSamplePoints} onClick={() => store.updateHeat({ showSamplePoints: !heat.showSamplePoints })}>Show sample points {heat.showSamplePoints ? 'on' : 'off'}</button><button type="button" aria-pressed={heat.loop} onClick={() => store.updateHeat({ loop: !heat.loop })}>Loop {heat.loop ? 'on' : 'off'}</button></div>
      <p className="mono">Reference {data.payload.reference_time}<br />Hour 0 {data.payload.hour_0_timestamp}<br />Last usable hour {last} · {data.payload.forecast_coverage.last_usable_timestamp}<br />Forecast age at analysis {Math.max(0, ...response.metadata.weather_cache.ages_seconds.map(v => Number(v.numerator) / Number(v.denominator) / 60)).toFixed(1)} min</p>
      {last < 48 && <p>No forecast data beyond {data.payload.forecast_coverage.last_usable_timestamp}. Playback stops at +{last} h; Loop stays within usable hours.</p>}
      <p>{data.payload.point_count} corridor points · optional gaps up to {Math.max(0, ...Object.values(data.payload.density.actual_optional_max_gap_miles)).toFixed(1)} mi</p>
      {data.payload.warnings.map(w => <p key={w} className="field-hint mono">{w}</p>)}
      <p>{data.payload.attribution.text}</p><p className="field-hint">Dominant glyphs: {DOMINANT.slice(1).join(' · ')}. Wind filter includes load rules.</p>
      <details><summary>Selected-hour sample summary</summary><p>{[1, 2, 3, 4, 5, 0, 9].map(code => `${LEVEL_NAMES[code]?.replace('_', ' ')} ${counts![code]}`).join(' · ')}</p></details>
    </div><span ref={live} role="status" aria-live="polite" className="sr-only" />
  </section>;
}
