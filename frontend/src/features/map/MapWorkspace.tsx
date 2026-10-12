import { useEffect, useRef, useState } from 'react';
import type { AnalysisResponse } from '../../api/types';
import { useSelectionStore } from '../../api/selection-store';
import type { EngineFactory, MapEngine, Theme } from './contracts';
import { cameraPadding } from './geometry';
import { attributionEntries, creditParts, mapConfig } from './basemap';
import { routeLabels, LEVELS } from '../results/presentation';
import { RiskBadge } from '../../components/surfaces';
import { ADVISORY } from '../results/ResultsView';
import { tooltipContent } from './tooltip';
import { miles } from '../../lib/format';
import './map.css';

let modulePromise: Promise<typeof import('./maplibre-engine')> | undefined;
const load = () => modulePromise ??= import('./maplibre-engine');
const readTheme = (): Theme => document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
export function MapWorkspace({ analysis, factory, onSkipMap }: { analysis: AnalysisResponse | null; factory?: EngineFactory; onSkipMap?: () => void }) {
  const region = useRef<HTMLElement>(null), host = useRef<HTMLDivElement>(null), engine = useRef<MapEngine | null>(null), status = useRef<HTMLSpanElement>(null);
  const store = useSelectionStore(), latest = useRef(analysis), updatePadding = useRef(() => {}); latest.current = analysis;
  const [ready, setReady] = useState(false), [failure, setFailure] = useState(''), [fatal, setFatal] = useState(false), [credits, setCredits] = useState<string[]>([]);
  const [legend, setLegend] = useState(() => { try { const saved = localStorage.getItem('routeshield-map-legend'); return saved === 'true' || saved === null && innerWidth > 760; } catch { return innerWidth > 760; } });
  const [fullscreen, setFullscreen] = useState(false);
  const fullButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    let cancelled = false, unsubscribe = () => {}, unsubscribeEvents = () => {}, resizeTimer = 0, announcementTimer = 0, bootstrapFrame = 0, bootstrapIdle = 0;
    const themeObserver = new MutationObserver(() => engine.current?.setTheme(readTheme()));
    const padding = () => {
      const node = region.current; if (!node || !engine.current) return;
      const rect = node.getBoundingClientRect(), full = document.fullscreenElement === node;
      const consoleWidth = full ? 0 : document.querySelector('.console-desktop')?.getBoundingClientRect().width ?? 0;
      const sheet = full ? null : document.querySelector('.bottom-sheet')?.getBoundingClientRect();
      const footer = node.querySelector('.map-credit-strip')?.getBoundingClientRect().height ?? 88;
      // Expanded credits reserve their actual height, including the mobile dock.
      const shell = node.closest<HTMLElement>('.app-shell'); if (shell && shell.style.getPropertyValue('--advisory-height') !== `${footer}px`) shell.style.setProperty('--advisory-height', `${footer}px`);
      const sheetHeight = sheet ? Math.max(0, rect.bottom - footer - sheet.top) : 0;
      engine.current.setPadding(cameraPadding(rect.width, rect.height, consoleWidth, sheetHeight, footer));
    };
    updatePadding.current = padding;
    const resize = () => { clearTimeout(resizeTimer); resizeTimer = window.setTimeout(() => { padding(); engine.current?.resize(); }, 80); };
    const observer = new ResizeObserver(resize), sheetObserver = new MutationObserver(resize);
    const fullChange = () => { setFullscreen(document.fullscreenElement === region.current); resize(); if (!document.fullscreenElement) fullButton.current?.focus(); else host.current?.querySelector<HTMLCanvasElement>('canvas')?.focus(); };
    document.addEventListener('fullscreenchange', fullChange);
    // Async boundary lets StrictMode's rehearsal cleanup cancel before WebGL init.
    const start = async () => {
      const create = factory ?? (await load()).createEngine;
      await Promise.resolve(); if (cancelled || !host.current) return;
      const instance = create(); engine.current = instance;
      unsubscribeEvents = instance.on(event => {
        if (cancelled) return;
        if (event.type === 'ready') { setReady(true); padding(); }
        if (event.type === 'failure') { setFailure(event.reason); if (event.reason === 'no WebGL') setFatal(true); }
        if (event.type === 'attribution') setCredits(previous => JSON.stringify(previous) === JSON.stringify(event.html) ? previous : event.html);
        if (event.type === 'route') store.selectRoute(event.id);
        if (event.type === 'checkpoint') store.selectCheckpoint(event.index);
        if (event.type === 'hover') store.hoverRoute(event.id);
        if (event.type === 'checkpoint-hover') store.hoverCheckpoint(event.index);
      });
      let previous = store.getState();
      const sync = () => {
        const next = store.getState(); instance.setSelection(next);
        if (next.selectedRouteId !== previous.selectedRouteId || next.selectedCheckpointIndex !== previous.selectedCheckpointIndex) clearTimeout(announcementTimer);
        if (status.current && latest.current) {
          if (next.selectedRouteId !== previous.selectedRouteId) status.current.textContent = `${routeLabels(latest.current).get(next.selectedRouteId ?? '') ?? 'No route'} selected`;
          else if (next.selectedCheckpointIndex !== previous.selectedCheckpointIndex && next.selectedCheckpointIndex !== null) {
            const cp = latest.current.routes.find(r => r.route_id === next.selectedRouteId)?.checkpoints.find(c => c.index === next.selectedCheckpointIndex);
            clearTimeout(announcementTimer);
            if (cp) announcementTimer = window.setTimeout(() => { if (status.current) status.current.textContent = `Checkpoint at mile ${miles(cp.mile_marker)} selected, ${tooltipContent(cp).risk} risk`; }, 400);
          }
        }
        previous = next;
      };
      unsubscribe = store.subscribe(sync);
      try { await instance.init(host.current, readTheme()); if (cancelled) return; padding(); instance.setRoutes(latest.current); sync(); } catch { if (!cancelled) { setFatal(true); setFailure('no WebGL'); } }
      if (region.current) observer.observe(region.current);
      const footer = region.current?.querySelector('.map-credit-strip'); if (footer) observer.observe(footer);
      const sheet = document.querySelector('.bottom-sheet'); if (sheet) { observer.observe(sheet); sheetObserver.observe(sheet, { attributes: true, attributeFilter: ['data-snap', 'style'] }); }
      themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    };
    const boot = () => { void start().catch(() => { if (!cancelled) { setFatal(true); setFailure('style failed to load'); } }); };
    if (factory) boot(); else bootstrapFrame = requestAnimationFrame(() => { if (typeof requestIdleCallback === 'function') bootstrapIdle = requestIdleCallback(boot, { timeout: 400 }); else boot(); });
    return () => { cancelled = true; cancelAnimationFrame(bootstrapFrame); if (bootstrapIdle && typeof cancelIdleCallback === 'function') cancelIdleCallback(bootstrapIdle); unsubscribe(); unsubscribeEvents(); themeObserver.disconnect(); observer.disconnect(); sheetObserver.disconnect(); document.removeEventListener('fullscreenchange', fullChange); clearTimeout(resizeTimer); clearTimeout(announcementTimer); engine.current?.destroy(); engine.current = null; };
  }, [factory, store]);
  useEffect(() => { updatePadding.current(); engine.current?.setRoutes(analysis); }, [analysis]);
  const toggleLegend = () => { const next = !legend; setLegend(next); try { localStorage.setItem('routeshield-map-legend', String(next)); } catch { /* Optional preference. */ } };
  const toggleFull = async () => { if (document.fullscreenElement) await document.exitFullscreen(); else await region.current?.requestFullscreen(); };
  const recenter = async () => {
    // A snap's CSS height transition can otherwise cancel the fit mid-flight.
    await Promise.all((document.querySelector('.bottom-sheet')?.getAnimations() ?? []).map(animation => animation.finished.catch(() => {})));
    updatePadding.current(); engine.current?.fitTo(null, true);
  };
  const attribution = attributionEntries(credits, analysis?.attributions ?? []);
  return <><a className="skip-link map-skip" href="#console" onClick={e => { if (onSkipMap) { e.preventDefault(); onSkipMap(); } }}>Skip map</a><section ref={region} className="map-workspace interactive-map" aria-label="Interactive route map">
    <div ref={host} className="map-engine-host" />
    {!ready && !fatal && <div className="map-skeleton" role="status"><p className="micro">RouteShield / chart engine</p><span className="map-tick-shimmer" /><p>Preparing map</p></div>}
    {fatal ? <div className="map-unavailable" role="status"><p className="micro">{failure}</p><h2>Map unavailable</h2><p>Routes and checkpoints remain available in the cards and Checkpoints list.</p></div> : <>
      {!analysis && ready && <div className="map-empty"><p className="micro">RouteShield / route chart</p><h2>Plan a trip to see routes</h2></div>}
      {failure && <div className="map-warning" role="status"><span>{failure}. Route overlays remain available.</span><button type="button" onClick={() => { setFailure(''); engine.current?.retry(); }}>Retry basemap</button></div>}
      <div className="map-controls" aria-label="Map controls"><button type="button" aria-label="Zoom in" title="Zoom in" onClick={() => engine.current?.zoom(1)}>+</button><button type="button" aria-label="Zoom out" title="Zoom out" onClick={() => engine.current?.zoom(-1)}>−</button><button type="button" aria-label="Recenter routes" title="Recenter routes (Home or R)" onClick={() => { void recenter(); }}>⌖</button>{document.fullscreenEnabled && <button ref={fullButton} type="button" aria-label={fullscreen ? 'Exit fullscreen map' : 'Fullscreen map'} title="Fullscreen map" onClick={() => { void toggleFull().catch(() => setFailure('Fullscreen unavailable')); }}>⛶</button>}</div>
      <div className="map-key-hint mono">Arrows pan · +/− zoom · R recenter · [ ] checkpoints · Esc dismiss</div>
      <div className="map-legend"><button type="button" aria-expanded={legend} aria-controls="map-legend-content" onClick={toggleLegend}>Chart legend <span aria-hidden="true">{legend ? '−' : '+'}</span></button><div id="map-legend-content" hidden={!legend}><div className="map-risk-legend">{LEVELS.map(level => <RiskBadge key={level} level={level} />)}</div><p>Larger markers indicate higher risk. Unknown uses a dashed ring.</p><p className="mono">━━ selected · risk segments<br />━ Route 1 · ━ ━ Route 2 · ━ · ━ Route 3</p><div data-heatmap-legend-slot="" /><p>Arrival-time weather. Continuous driving; no live traffic.</p></div></div>
    </>}
    {analysis?.is_simulation && <div className="map-simulation">SIMULATION · {analysis.simulation_scenario}</div>}
    <footer className="map-credit-strip"><div>{attribution.html.length ? attribution.html.map((html, i) => <span key={i}>{creditParts(html).map((part, j) => part.href ? <a key={j} href={part.href} target="_blank" rel="noreferrer">{part.text}</a> : <span key={j}>{part.text}</span>)}</span>) : <span>{mapConfig.offline ? 'Offline basemap' : ready && !failure ? 'OpenFreeMap · basemap loading' : 'Basemap unavailable'}</span>}</div>{attribution.providers.length > 0 && <details><summary>Provider credits · {attribution.providers.length}</summary><ul>{attribution.providers.map((a, i) => <li key={i}>{a.provider}{!a.confirmed && ' · Unconfirmed attribution'}: {a.text}</li>)}</ul></details>}<p>{ADVISORY}</p></footer>
    <span ref={status} className="sr-only" role="status" aria-live="polite" />
  </section><a className="skip-link map-skip-after" href="#console" onClick={e => { if (onSkipMap) { e.preventDefault(); onSkipMap(); } }}>Skip map to route results</a></>;
}
