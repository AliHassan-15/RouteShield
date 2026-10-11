import { Map as GLMap, Marker, setWorkerUrl } from 'maplibre-gl';
import type { GeoJSONSource, MapMouseEvent, StyleSpecification, ExpressionSpecification } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { Feature, FeatureCollection, Geometry } from 'geojson';
import type { AnalysisResponse, Position, RiskLevel } from '../../api/types';
import type { SelectionState } from '../../api/selection-store';
import type { MapEngine, MapEvent, Padding, Theme } from './contracts';
import { mapConfig, offlineStyle, transformStyle } from './basemap';
import { bounds, chipAvoidsPoints, chipFits, markerEncoding, placeChips, pointAt, prepareRoute, routeOffset, validPosition } from './geometry';
import { LEVELS, routeLabels, serverOrder } from '../results/presentation';
import { duration } from '../../lib/format';
import { tooltipContent } from './tooltip';

type PaintName = Parameters<GLMap['setPaintProperty']>[1];
type PaintValue = Parameters<GLMap['setPaintProperty']>[2];
setWorkerUrl(workerUrl);
const collection = (features: Feature<Geometry>[]): FeatureCollection => ({ type: 'FeatureCollection', features });
const empty = collection([]);
const reduce = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const dashes = [[1, 0], [5, 2], [1, 2, 5, 2]];
export class MapLibreEngine implements MapEngine {
  private map?: GLMap;
  private host?: HTMLElement;
  private theme: Theme = 'light';
  private base?: StyleSpecification;
  private analysis: AnalysisResponse | null = null;
  private prepared: ReturnType<typeof prepareRoute>[] = [];
  private cache = new WeakMap<object, ReturnType<typeof prepareRoute>>();
  private selected: SelectionState = { selectedRouteId: null, selectedCheckpointIndex: null, hoveredRouteId: null };
  private listeners = new Set<(event: MapEvent) => void>();
  private markers: Marker[] = [];
  private chips: { marker: Marker; id: string; position: Position }[] = [];
  private tooltip?: HTMLDivElement;
  private tooltipIndex: number | null = null;
  private hoveredCheckpoint: number | null = null;
  private abort = new AbortController();
  private animation = 0;
  private moveFrame = 0;
  private mouseFrame = 0;
  private lastMouse?: MapMouseEvent;
  private prepareTimer: ReturnType<typeof globalThis.setTimeout> | undefined;
  private idle?: number;
  private pausedFit = false;
  private disposed = false;
  private styleFailed = false;
  private padding: Padding = { top: 24, right: 40, bottom: 110, left: 444 };
  private applyMs = 0;
  private prepareMs = 0;
  private drawStartedAt = 0;
  private dataWrites = 0;
  private onMove = () => {
    if (this.moveFrame) return;
    this.moveFrame = requestAnimationFrame(() => { this.moveFrame = 0; this.updateChips(); this.positionTooltip(); });
  };
  private onManual = () => { this.pausedFit = true; };
  private onStyle = () => { this.installOverlay(); this.updateData(); this.applySelection(); this.updateCredits(); };
  private creditSignature = '';
  private onSource = () => this.updateCredits();
  private onZoom = () => this.declutter();
  private onError = () => {
    if (this.styleFailed || this.disposed || mapConfig.offline) return;
    this.styleFailed = true; this.emit({ type: 'failure', reason: 'tiles unreachable' });
    this.map?.setStyle(offlineStyle(this.theme));
  };
  on(listener: (event: MapEvent) => void) { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; }
  private emit(event: MapEvent) { this.listeners.forEach(fn => fn(event)); }
  async init(container: HTMLElement, theme: Theme) {
    this.host = container; this.theme = theme;
    this.tooltip = document.createElement('div'); this.tooltip.className = 'map-checkpoint-tooltip'; this.tooltip.setAttribute('role', 'tooltip'); this.tooltip.hidden = true; container.append(this.tooltip);
    try {
      this.map = new GLMap({ container, style: offlineStyle(theme), center: [-95, 39], zoom: 3, maxZoom: 18, attributionControl: false, canvasContextAttributes: { preserveDrawingBuffer: import.meta.env.VITE_E2E === 'true' } });
    } catch { this.emit({ type: 'failure', reason: 'no WebGL' }); throw new Error('no WebGL'); }
    const m = this.map;
    m.getCanvas().setAttribute('aria-label', 'Route map. Arrow keys pan; plus/minus zoom; Home or R recenter; brackets select checkpoints; Escape closes tooltip.');
    m.getCanvas().tabIndex = 0;
    m.on('style.load', this.onStyle); m.on('sourcedata', this.onSource); m.on('move', this.onMove); m.on('zoomend', this.onZoom);
    m.on('dragstart', this.onManual); m.on('wheel', this.onManual); m.on('error', this.onError);
    m.on('click', this.onClick); m.on('mousemove', this.onMouse); m.on('mouseout', this.onLeave);
    m.getCanvas().addEventListener('keydown', this.onKey);
    await new Promise<void>(resolve => m.once('load', () => resolve()));
    if (this.disposed) return;
    this.emit({ type: 'ready' });
    if (!mapConfig.offline) void this.loadBase();
    if (import.meta.env.VITE_E2E === 'true') {
      // Compiled away unless explicitly enabled. No payload, keys or upstream data.
      Object.assign(window, { __routeShieldMap: { inspect: () => this.inspect(), project: (p: Position) => this.project(p), select: (id: string) => this.emit({ type: 'route', id }), replaceStyle: () => this.map?.setStyle(offlineStyle(this.theme)) } });
    }
  }
  private async loadBase() {
    try {
      const response = await fetch(mapConfig.style, { signal: this.abort.signal });
      if (!response.ok) throw new Error('style');
      this.base = await response.json() as StyleSpecification;
      if (!this.base.layers || this.base.version !== 8) throw new Error('style');
      if (!this.disposed) { this.styleFailed = false; this.map?.setStyle(transformStyle(this.base, this.theme)); }
    } catch { if (!this.disposed) this.emit({ type: 'failure', reason: 'style failed to load' }); }
  }
  setTheme(theme: Theme) {
    if (theme === this.theme) return;
    this.theme = theme; const m = this.map; if (!m) return;
    // Transform paint in place: no blank frame, camera/style-source churn or lost
    // selection. Reinstall/update overlay images via the same idempotent function.
    const style = this.base ? transformStyle(this.base, theme) : offlineStyle(theme);
    for (const layer of style.layers) if (m.getLayer(layer.id) && layer.paint) for (const [key, value] of Object.entries(layer.paint)) m.setPaintProperty(layer.id, key as PaintName, value as PaintValue);
    this.installOverlay(); this.applySelection(false); this.showTooltip(this.tooltipIndex);
  }
  private colors() {
    const css = getComputedStyle(document.documentElement);
    return { risk: Object.fromEntries(LEVELS.map(l => [l, css.getPropertyValue(`--risk-${markerEncoding(l).token}`).trim()])) as Record<RiskLevel, string>, neutral: css.getPropertyValue('--muted').trim(), accent: css.getPropertyValue('--accent').trim(), halo: this.theme === 'dark' ? '#f5f3e9' : '#182c38', surface: css.getPropertyValue('--surface').trim() };
  }
  private icon(level: RiskLevel) {
    const info = markerEncoding(level), ratio = Math.min(3, devicePixelRatio || 1), width = 30, canvas = document.createElement('canvas');
    canvas.width = canvas.height = width * ratio;
    const ctx = canvas.getContext('2d'); if (!ctx) return null;
    ctx.scale(ratio, ratio); ctx.translate(15, 15); const radius = info.size / 2;
    ctx.beginPath();
    if (level === 'LOW' || level === 'UNKNOWN') ctx.arc(0, 0, radius, 0, Math.PI * 2);
    else { const n = level === 'HIGH' ? 3 : level === 'NO_TRAVEL' ? 8 : 4, offset = level === 'SEVERE' ? Math.PI / 4 : -Math.PI / 2; for (let i = 0; i <= n; i++) { const x = radius * Math.cos(i / n * Math.PI * 2 + offset), y = radius * Math.sin(i / n * Math.PI * 2 + offset); if (!i) ctx.moveTo(x, y); else ctx.lineTo(x, y); } ctx.closePath(); }
    const c = this.colors(); ctx.strokeStyle = c.surface; ctx.lineWidth = 5; ctx.stroke();
    ctx.fillStyle = c.risk[level]; if (level !== 'UNKNOWN') ctx.fill();
    ctx.strokeStyle = c.risk[level]; ctx.lineWidth = 2; if (level === 'UNKNOWN') ctx.setLineDash([3, 2]); ctx.stroke();
    return { data: ctx.getImageData(0, 0, canvas.width, canvas.height), ratio };
  }
  // Shared by initial load, style replacement/retry and theme; safe to call twice.
  private installOverlay() {
    const m = this.map; if (!m || !m.getLayer('background')) return;
    const c = this.colors();
    for (const level of LEVELS) { const image = this.icon(level); if (image) { if (m.hasImage(`risk-${level}`)) m.updateImage(`risk-${level}`, image.data); else m.addImage(`risk-${level}`, image.data, { pixelRatio: image.ratio }); } }
    for (const id of ['rs-routes', 'rs-segments', 'rs-checkpoints']) if (!m.getSource(id)) m.addSource(id, { type: 'geojson', data: empty, tolerance: .35, lineMetrics: id === 'rs-routes' });
    for (let i = 0; i < 3; i++) {
      const filter: ExpressionSpecification = ['==', ['get', 'order'], i];
      if (!m.getLayer(`rs-casing-${i}`)) m.addLayer({ id: `rs-casing-${i}`, type: 'line', source: 'rs-routes', filter, layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': c.halo, 'line-width': 0, 'line-opacity': .9 } });
      if (!m.getLayer(`rs-route-${i}`)) m.addLayer({ id: `rs-route-${i}`, type: 'line', source: 'rs-routes', filter, layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': c.neutral, 'line-width': 3, 'line-dasharray': dashes[i]!, 'line-opacity': .85, 'line-width-transition': { duration: reduce() ? 0 : 120 } } });
    }
    for (const level of LEVELS) {
      const id = `rs-risk-${level}`;
      if (!m.getLayer(id)) m.addLayer({ id, type: 'line', source: 'rs-segments', filter: ['==', ['get', 'level'], level], layout: { 'line-cap': 'butt', 'line-join': 'round' }, paint: { 'line-color': c.risk[level], 'line-width': 6, 'line-opacity-transition': { duration: reduce() ? 0 : 160 } } });
      m.setPaintProperty(id, 'line-color', c.risk[level]);
    }
    if (!m.getLayer('rs-pattern')) m.addLayer({ id: 'rs-pattern', type: 'line', source: 'rs-segments', filter: ['in', ['get', 'level'], ['literal', ['NO_TRAVEL', 'UNKNOWN']]], paint: { 'line-color': c.surface, 'line-width': 2, 'line-dasharray': [1, 2] } });
    for (const [id, collision] of [['rs-calm', true], ['rs-critical', false]] as const) if (!m.getLayer(id)) m.addLayer({ id, type: 'symbol', source: 'rs-checkpoints', filter: ['==', ['get', 'collision'], collision], layout: { 'icon-image': ['concat', 'risk-', ['get', 'level']], 'icon-allow-overlap': !collision, 'icon-ignore-placement': !collision, 'symbol-sort-key': ['get', 'sort'], 'icon-padding': 4 }, paint: { 'icon-opacity': 1 } });
    if (!m.getLayer('rs-ring')) m.addLayer({ id: 'rs-ring', type: 'circle', source: 'rs-checkpoints', paint: { 'circle-radius': ['case', ['boolean', ['feature-state', 'selected'], false], 17, 14], 'circle-color': 'transparent', 'circle-stroke-color': c.accent, 'circle-stroke-width': ['case', ['boolean', ['feature-state', 'selected'], false], 2, ['boolean', ['feature-state', 'hover'], false], 1, 0] } });
    m.setPaintProperty('rs-ring', 'circle-stroke-color', c.accent); m.setPaintProperty('rs-pattern', 'line-color', c.surface);
  }
  setRoutes(analysis: AnalysisResponse | null) {
    if (this.analysis === analysis) return;
    this.analysis = analysis; this.pausedFit = false;
    const interrupted = this.animation !== 0;
    cancelAnimationFrame(this.animation); this.animation = 0; clearTimeout(this.prepareTimer);
    if (this.idle !== undefined) cancelIdleCallback(this.idle);
    const apply = () => {
      if (this.disposed || this.analysis !== analysis) return;
      const started = performance.now();
      this.prepared = analysis ? serverOrder(analysis.routes).map(route => { let p = this.cache.get(route); if (!p) { p = prepareRoute(route); this.cache.set(route, p); } return p; }) : [];
      this.prepareMs = performance.now() - started;
      this.updateData(); this.rebuildMarkers(); this.applySelection(); this.fitTo(null, true); this.drawIn(interrupted); this.applyMs = performance.now() - started;
    };
    // Preparation runs once during idle; newer requests cancel queued work.
    if (typeof requestIdleCallback === 'function') this.idle = requestIdleCallback(apply, { timeout: 100 }); else this.prepareTimer = globalThis.setTimeout(apply, 0);
  }
  private updateData() {
    const m = this.map; if (!m?.getSource('rs-routes')) return;
    const features: Feature<Geometry>[] = this.prepared.filter(p => p.valid).map(p => ({ type: 'Feature', id: p.route.route_id, properties: { route: p.route.route_id, order: this.prepared.indexOf(p) }, geometry: { type: 'LineString', coordinates: p.line.points } }));
    (m.getSource('rs-routes') as GeoJSONSource).setData(collection(features)); this.dataWrites++;
  }
  setSelection(selection: SelectionState) {
    const routeChanged = selection.selectedRouteId !== this.selected.selectedRouteId, cpChanged = selection.selectedCheckpointIndex !== this.selected.selectedCheckpointIndex;
    this.selected = { ...selection };
    if (routeChanged) { this.applySelection(); this.fitTo(selection.selectedRouteId); }
    if (cpChanged || routeChanged) {
      if (this.map?.getSource('rs-checkpoints')) this.map.removeFeatureState({ source: 'rs-checkpoints' });
      if (selection.selectedCheckpointIndex !== null) {
        if (this.map?.getSource('rs-checkpoints')) this.map.setFeatureState({ source: 'rs-checkpoints', id: selection.selectedCheckpointIndex }, { selected: true });
        const cp = this.selectedRoute()?.route.checkpoints.find(c => c.index === selection.selectedCheckpointIndex);
        if (cp && validPosition(cp.coordinate) && !this.pausedFit) this.map?.easeTo({ center: cp.coordinate, duration: reduce() ? 0 : 400 });
        this.pulse();
      }
      this.showTooltip(selection.selectedCheckpointIndex);
    }
    this.setHover(selection.hoveredRouteId);
  }
  private selectedRoute() { return this.prepared.find(p => p.route.route_id === this.selected.selectedRouteId); }
  private applySelection(writeData = true) {
    const m = this.map; if (!m?.getSource('rs-segments')) return;
    const c = this.colors(), selected = this.selectedRoute(), order = this.prepared.indexOf(selected!);
    const segments: Feature<Geometry>[] = selected?.valid ? selected.segments.filter(s => s.coordinates.length >= 2).map(s => ({ type: 'Feature', properties: { level: s.level }, geometry: { type: 'LineString', coordinates: s.coordinates } })) : [];
    const checkpoints: Feature<Geometry>[] = selected?.valid ? selected.route.checkpoints.filter(cp => validPosition(cp.coordinate)).map(cp => { const info = markerEncoding(cp.risk.final_risk); return { type: 'Feature', id: cp.index, properties: { index: cp.index, fraction: (Number(cp.mile_marker.numerator) / Number(cp.mile_marker.denominator)) / (Number(selected.route.summary.total_miles.numerator) / Number(selected.route.summary.total_miles.denominator)), level: cp.risk.final_risk, collision: info.collision, sort: -info.priority * 100000 + cp.index }, geometry: { type: 'Point', coordinates: cp.coordinate } }; }) : [];
    if (writeData) { (m.getSource('rs-segments') as GeoJSONSource).setData(collection(segments)); (m.getSource('rs-checkpoints') as GeoJSONSource).setData(collection(checkpoints)); this.dataWrites += 2; }
    for (let i = 0; i < 3; i++) {
      m.setPaintProperty(`rs-casing-${i}`, 'line-color', c.halo); m.setPaintProperty(`rs-casing-${i}`, 'line-width', order === i ? 10 : 0);
      m.setPaintProperty(`rs-route-${i}`, 'line-color', c.neutral); m.setPaintProperty(`rs-route-${i}`, 'line-width', i === order ? 6 : 3); m.setPaintProperty(`rs-route-${i}`, 'line-offset', routeOffset(i, order));
      m.setPaintProperty(`rs-route-${i}`, 'line-dasharray', i === order ? [1, 0] : dashes[i]!);
    }
    if (order >= 0) { m.moveLayer(`rs-casing-${order}`, 'rs-risk-LOW'); m.moveLayer(`rs-route-${order}`, 'rs-risk-LOW'); }
    this.declutter(); this.updateChips(); this.rebuildEndpoints();
    if (this.selected.selectedCheckpointIndex !== null) m.setFeatureState({ source: 'rs-checkpoints', id: this.selected.selectedCheckpointIndex }, { selected: true });
  }
  private declutter() {
    const m = this.map; if (!m?.getLayer('rs-calm')) return;
    m.setFilter('rs-calm', ['all', ['==', ['get', 'collision'], true], ['any', ['!=', ['get', 'level'], 'LOW'], m.getZoom() >= 7 ? true : ['==', ['%', ['get', 'index'], 4], 0]]]);
  }
  setHover(id: string | null) {
    const m = this.map; if (!m?.getSource('rs-routes')) return;
    for (let i = 0; i < 3; i++) { const route = this.prepared[i]?.route; m.setPaintProperty(`rs-route-${i}`, 'line-width', route?.route_id === this.selected.selectedRouteId ? 6 : route?.route_id === id ? 5 : 3); m.setPaintProperty(`rs-route-${i}`, 'line-opacity', !id || route?.route_id === id || route?.route_id === this.selected.selectedRouteId ? .95 : .85); }
  }
  private pulse() {
    const node = this.host?.querySelector('.map-selection-pulse'); if (node) node.remove();
    const cp = this.selectedRoute()?.route.checkpoints.find(c => c.index === this.selected.selectedCheckpointIndex); if (!cp || !validPosition(cp.coordinate) || reduce() || !this.host) return;
    const p = this.project(cp.coordinate), ring = document.createElement('span'); ring.className = 'map-selection-pulse'; ring.style.left = `${p.x}px`; ring.style.top = `${p.y}px`; this.host.append(ring); ring.addEventListener('animationend', () => ring.remove(), { once: true });
  }
  private onClick = (e: MapMouseEvent) => {
    const feature = this.hit(e)[0]; if (!feature) return;
    if (feature.properties?.index !== undefined) this.emit({ type: 'checkpoint', index: Number(feature.properties.index) });
    else if (feature.properties?.route) this.emit({ type: 'route', id: String(feature.properties.route) });
  };
  private hit(e: MapMouseEvent) {
    const m = this.map; if (!m) return [];
    const layers = ['rs-critical', 'rs-calm', 'rs-route-0', 'rs-route-1', 'rs-route-2'].filter(id => m.getLayer(id)), exact = m.queryRenderedFeatures(e.point, { layers });
    // A generous fallback must not steal a precise hit on an offset shared trace.
    return exact.length ? exact : m.queryRenderedFeatures([[e.point.x - 8, e.point.y - 8], [e.point.x + 8, e.point.y + 8]], { layers });
  }
  private onMouse = (e: MapMouseEvent) => {
    this.lastMouse = e;
    if (this.mouseFrame) return;
    this.mouseFrame = requestAnimationFrame(() => { this.mouseFrame = 0; if (this.lastMouse) this.processMouse(this.lastMouse); });
  };
  private processMouse(e: MapMouseEvent) {
    const feature = this.hit(e)[0], index = feature?.properties?.index;
    if (this.hoveredCheckpoint !== null && this.map?.getSource('rs-checkpoints')) this.map.setFeatureState({ source: 'rs-checkpoints', id: this.hoveredCheckpoint }, { hover: false });
    this.hoveredCheckpoint = index === undefined ? null : Number(index);
    if (this.hoveredCheckpoint !== null && this.map?.getSource('rs-checkpoints')) this.map.setFeatureState({ source: 'rs-checkpoints', id: this.hoveredCheckpoint }, { hover: true });
    for (const id of ['rs-calm', 'rs-critical']) if (this.map?.getLayer(id)) this.map.setLayoutProperty(id, 'icon-size', ['case', ['==', ['get', 'index'], this.hoveredCheckpoint ?? -1], 1.15, 1]);
    this.showTooltip(this.hoveredCheckpoint ?? this.selected.selectedCheckpointIndex);
    this.emit({ type: 'hover', id: feature?.properties?.route ? String(feature.properties.route) : null });
    if (this.map) this.map.getCanvas().style.cursor = feature ? 'pointer' : '';
  }
  private onLeave = () => { this.emit({ type: 'hover', id: null }); this.showTooltip(this.selected.selectedCheckpointIndex); };
  private onKey = (e: KeyboardEvent) => {
    if (e.key === 'Home' || e.key.toLowerCase() === 'r') { e.preventDefault(); this.fitTo(null, true); }
    if (e.key === 'Escape') { e.preventDefault(); this.dismissTooltip(); }
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', '+', '-', '='].includes(e.key)) this.pausedFit = true;
    if (e.key === '[' || e.key === ']') {
      e.preventDefault(); const checkpoints = this.selectedRoute()?.route.checkpoints ?? [], current = checkpoints.findIndex(cp => cp.index === this.selected.selectedCheckpointIndex);
      const next = checkpoints[Math.max(0, Math.min(checkpoints.length - 1, current < 0 ? 0 : current + (e.key === ']' ? 1 : -1)))]; if (next) this.emit({ type: 'checkpoint', index: next.index });
    }
  };
  private showTooltip(index: number | null) {
    if (this.tooltipIndex === index && this.tooltip && !this.tooltip.hidden) { this.positionTooltip(); return; }
    this.tooltipIndex = index; const cp = this.selectedRoute()?.route.checkpoints.find(c => c.index === index), node = this.tooltip;
    if (!node) return; node.hidden = !cp || !validPosition(cp.coordinate); if (node.hidden || !cp) return;
    const info = tooltipContent(cp); node.replaceChildren();
    for (const [i, text] of [info.title, info.risk, info.weather, ...(info.unavailable ? [info.unavailable] : []), ...(cp.risk.known_blocked ? ['Known No Travel evidence'] : [])].entries()) { const p = document.createElement('p'); p.textContent = text; if (i === 1) { const shape = document.createElement('span'); shape.className = `map-tooltip-shape risk-${markerEncoding(cp.risk.final_risk).token}`; shape.dataset.level = cp.risk.final_risk; p.prepend(shape); } node.append(p); }
    node.dataset.level = cp.risk.final_risk; this.positionTooltip();
  }
  private positionTooltip() {
    const cp = this.selectedRoute()?.route.checkpoints.find(c => c.index === this.tooltipIndex), node = this.tooltip; if (!cp || !validPosition(cp.coordinate) || !node || !this.host) return;
    const p = this.project(cp.coordinate); node.style.left = `${Math.max(8, Math.min(this.host.clientWidth - 282, p.x + 18))}px`; node.style.top = `${Math.max(8, Math.min(this.host.clientHeight - 100, p.y - 100))}px`;
  }
  dismissTooltip() { this.tooltipIndex = null; if (this.tooltip) this.tooltip.hidden = true; }
  private rebuildMarkers() {
    this.markers.forEach(m => m.remove()); this.markers = []; this.chips = [];
    if (!this.map || !this.analysis) return; const labels = routeLabels(this.analysis);
    this.prepared.forEach((p, i) => {
      const coordinate = pointAt(p.line, .35 + i * .15); if (!coordinate || !p.valid) return;
      const button = document.createElement('button'); button.type = 'button'; button.className = 'map-route-chip mono'; button.textContent = `${labels.get(p.route.route_id)} · ${duration(p.route.duration_s)}`; button.dataset.rank = p.route.rank === null ? p.route.travel_status : `#${p.route.rank}`; button.setAttribute('aria-label', `Select ${labels.get(p.route.route_id)}, ${p.route.travel_status}`);
      button.addEventListener('click', () => this.emit({ type: 'route', id: p.route.route_id })); button.addEventListener('mouseenter', () => this.emit({ type: 'hover', id: p.route.route_id })); button.addEventListener('mouseleave', () => this.emit({ type: 'hover', id: null }));
      const marker = new Marker({ element: button, anchor: 'bottom', offset: [0, -36] }).setLngLat(coordinate).addTo(this.map!); this.markers.push(marker); this.chips.push({ marker, id: p.route.route_id, position: coordinate });
    });
    this.rebuildEndpoints(); this.updateChips();
  }
  private endpoints: Marker[] = [];
  private rebuildEndpoints() {
    this.endpoints.forEach(m => m.remove()); this.endpoints = [];
    const selected = this.selectedRoute(); const route = (selected?.valid ? selected : this.prepared.find(p => p.valid))?.route; if (!this.map || !route || !this.analysis) return;
    for (const [p, label, glyph] of [[route.geometry[0], this.analysis.trip.origin.label, '◉'], [route.geometry.at(-1), this.analysis.trip.destination.label, '□']] as const) {
      if (!p || !validPosition(p)) continue;
      const button = document.createElement('button'); button.type = 'button'; button.className = 'map-endpoint'; button.textContent = `${glyph} ${label}`; button.setAttribute('aria-label', label); button.title = label;
      button.addEventListener('click', () => { this.emit({ type: 'route', id: route.route_id }); this.emit({ type: 'checkpoint', index: glyph === '◉' ? route.checkpoints[0]?.index ?? 0 : route.checkpoints.at(-1)?.index ?? 0 }); });
      const marker = new Marker({ element: button, anchor: glyph === '◉' ? 'bottom-left' : 'bottom-right', offset: [0, -24] }).setLngLat(p).addTo(this.map); this.endpoints.push(marker);
    }
  }
  private updateChips() {
    const protectedPoints = this.selectedRoute()?.route.checkpoints.filter(cp => !markerEncoding(cp.risk.final_risk).collision && validPosition(cp.coordinate)).map(cp => this.project(cp.coordinate)) ?? [];
    const host = this.host?.getBoundingClientRect(), obstacles = Array.from(this.host?.parentElement?.querySelectorAll('.map-controls,.map-legend,.map-warning,.map-credit-strip,.map-endpoint') ?? []).map(node => node.getBoundingClientRect()).filter(r => r.width && r.height).map(r => ({ left: r.left - (host?.left ?? 0), right: r.right - (host?.left ?? 0), top: r.top - (host?.top ?? 0), bottom: r.bottom - (host?.top ?? 0) }));
    const projected = this.chips.map(c => {
        const point = this.project(c.position), node = c.marker.getElement(), width = this.host && this.host.clientWidth <= 760 ? 176 : 210;
        // Critical symbols take priority over floating labels on narrow viewports.
        const offset = [36, 64, 92].find(offset => chipFits({ left: point.x - width / 2, right: point.x + width / 2, top: point.y - offset - 44, bottom: point.y - offset }, { left: (host?.width ?? 0) > 760 ? Math.max(0, this.padding.left - 24) : 0, right: host?.width ?? 0, top: 0, bottom: host?.height ?? 0 }, obstacles) && chipAvoidsPoints(point.x, point.y - offset, width, 44, protectedPoints));
        c.marker.setOffset([0, -(offset ?? 36)]); node.classList.toggle('is-selected', c.id === this.selected.selectedRouteId);
        return { id: c.id, x: point.x, y: point.y - (offset ?? 36), width, height: 44, selected: c.id === this.selected.selectedRouteId, safe: offset !== undefined };
      }), visible = placeChips(projected.filter(p => p.safe));
    this.chips.forEach(c => { c.marker.getElement().hidden = !visible.has(c.id); });
  }
  private drawIn(skip = false) {
    const m = this.map; if (!m?.getLayer('rs-route-0')) return;
    cancelAnimationFrame(this.animation);
    if (reduce() || skip) {
      for (let i = 0; i < 3; i++) { m.setPaintProperty(`rs-route-${i}`, 'line-gradient', undefined); m.setPaintProperty(`rs-casing-${i}`, 'line-opacity', 1); }
      for (const level of LEVELS) m.setPaintProperty(`rs-risk-${level}`, 'line-opacity', 1);
      m.setPaintProperty('rs-pattern', 'line-opacity', 1); m.setPaintProperty('rs-calm', 'icon-opacity', 1); m.setPaintProperty('rs-critical', 'icon-opacity', 1); this.chips.forEach(c => { c.marker.getElement().style.opacity = '1'; }); return;
    }
    for (let i = 0; i < 3; i++) m.setPaintProperty(`rs-casing-${i}`, 'line-opacity', 0);
    for (const level of LEVELS) m.setPaintProperty(`rs-risk-${level}`, 'line-opacity', 0);
    m.setPaintProperty('rs-pattern', 'line-opacity', 0); m.setPaintProperty('rs-calm', 'icon-opacity', 0); m.setPaintProperty('rs-critical', 'icon-opacity', 0);
    const start = performance.now(), color = this.colors().neutral;
    if (import.meta.env.VITE_E2E === 'true') this.drawStartedAt = start;
    const step = (now: number) => {
      if (this.disposed || !m.getLayer('rs-route-0')) return;
      for (let i = 0; i < 3; i++) { const progress = Math.max(.000001, Math.min(1, (now - start - i * 70) / 700)); m.setPaintProperty(`rs-route-${i}`, 'line-gradient', ['step', ['line-progress'], color, progress, 'transparent']); }
      const reveal = Math.min(1, Math.max(0, (now - start - 600) / 240));
      for (const level of LEVELS) m.setPaintProperty(`rs-risk-${level}`, 'line-opacity', reveal);
      const progress = Math.max(0, Math.min(1, (now - start) / 700));
      m.setPaintProperty('rs-pattern', 'line-opacity', reveal);
      for (let i = 0; i < 3; i++) m.setPaintProperty(`rs-casing-${i}`, 'line-opacity', reveal);
      for (const id of ['rs-calm', 'rs-critical']) m.setPaintProperty(id, 'icon-opacity', ['case', ['<=', ['get', 'fraction'], progress], 1, 0]);
      this.chips.forEach(c => { c.marker.getElement().style.opacity = String(reveal); });
      if (now - start < 900) this.animation = requestAnimationFrame(step); else { this.animation = 0; for (let i = 0; i < 3; i++) m.setPaintProperty(`rs-route-${i}`, 'line-gradient', undefined); }
    }; this.animation = requestAnimationFrame(step);
  }
  fitTo(id: string | null = null, force = false) {
    if (this.pausedFit && !force) return; if (force) this.pausedFit = false;
    const points = this.prepared.filter(p => p.valid && (!id || p.route.route_id === id)).flatMap(p => p.line.points), box = bounds(points);
    // v6 otherwise adds fit padding to the map's existing padding a second time.
    if (box) this.map?.fitBounds(box, { padding: this.padding, absolutePadding: true, linear: true, maxZoom: 14, duration: reduce() ? 0 : 900, easing: t => 1 - (1 - t) ** 3 });
  }
  setPadding(padding: Padding) {
    this.padding = padding;
    // MapLibre setPadding calls jumpTo, which cancels an active fit animation.
    // ResizeObserver may fire for unchanged dimensions: avoid that cancellation.
    if (this.map) { const current = this.map.getPadding(); if (Object.keys(padding).some(key => current[key as keyof Padding] !== padding[key as keyof Padding])) this.map.setPadding(padding); }
  }
  resize() { this.map?.resize(); }
  zoom(delta: number) { this.pausedFit = true; if (this.map) this.map.easeTo({ zoom: this.map.getZoom() + delta, duration: reduce() ? 0 : 200 }); }
  project(point: Position) { const p = this.map?.project(point); return p ? { x: p.x, y: p.y } : { x: 0, y: 0 }; }
  retry() { if (mapConfig.offline) return; this.styleFailed = false; if (this.base) this.map?.setStyle(transformStyle(this.base, this.theme)); else void this.loadBase(); }
  private updateCredits() {
    const m = this.map; if (!m) return;
    const html = Object.keys(m.getStyle().sources).flatMap(id => { const source = m.getSource(id); return source && 'attribution' in source && typeof source.attribution === 'string' ? [source.attribution] : []; });
    const signature = JSON.stringify(html); if (html.length && signature !== this.creditSignature) { this.creditSignature = signature; this.emit({ type: 'attribution', html }); }
  }
  private inspect() { const m = this.map; return { drawStartedAt: this.drawStartedAt, basemapReady: !!m?.loaded() && (mapConfig.offline || !!this.base) && !this.styleFailed, selectedRouteId: this.selected.selectedRouteId, selectedCheckpointIndex: this.selected.selectedCheckpointIndex, layers: m?.getStyle().layers.filter(l => l.id.startsWith('rs-')).length ?? 0, sources: Object.keys(m?.getStyle().sources ?? {}).filter(id => id.startsWith('rs-')).length, rendered: m?.queryRenderedFeatures().filter(f => f.layer.id.startsWith('rs-')).length ?? 0, vertices: this.prepared.map(p => p.line.points.length), applyMs: this.applyMs, prepareMs: this.prepareMs, dataWrites: this.dataWrites, zoom: m?.getZoom(), center: m?.getCenter().toArray(), padding: m?.getPadding() }; }
  destroy() {
    this.disposed = true; this.abort.abort(); cancelAnimationFrame(this.animation); cancelAnimationFrame(this.moveFrame); cancelAnimationFrame(this.mouseFrame); clearTimeout(this.prepareTimer); if (this.idle !== undefined) cancelIdleCallback(this.idle);
    const m = this.map;
    if (m) { m.off('style.load', this.onStyle); m.off('sourcedata', this.onSource); m.off('move', this.onMove); m.off('zoomend', this.onZoom); m.off('dragstart', this.onManual); m.off('wheel', this.onManual); m.off('error', this.onError); m.off('click', this.onClick); m.off('mousemove', this.onMouse); m.off('mouseout', this.onLeave); m.getCanvas().removeEventListener('keydown', this.onKey); }
    this.markers.forEach(marker => marker.remove()); this.endpoints.forEach(marker => marker.remove()); this.tooltip?.remove(); this.host?.querySelector('.map-selection-pulse')?.remove(); this.map?.remove(); this.listeners.clear();
    if (import.meta.env.VITE_E2E === 'true') Reflect.deleteProperty(window, '__routeShieldMap');
  }
}
export const createEngine = () => new MapLibreEngine();
