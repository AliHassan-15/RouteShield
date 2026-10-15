import { Marker } from 'maplibre-gl';
import type { Map as GLMap, GeoJSONSource, ExpressionSpecification } from 'maplibre-gl';
import type { FeatureCollection, Point } from 'geojson';
import type { HeatState } from '../../api/selection-store';
import type { DecodedHeatmap } from './decoder';
import { DOMINANT, fadeWeights, LEVEL_NAMES, levelsAt, truckReadout, weightHash, weightsAt } from './presentation';

const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const tokens = ['unknown', 'low', 'moderate', 'high', 'severe', 'no-travel'];
type UpdatePath = 'feature-state' | 'setData';
/** One source, five categorical GPU layers, one cancellable transition loop. */
export class HeatOverlay {
  private state?: HeatState;
  private data?: DecodedHeatmap;
  private source: FeatureCollection<Point> = { type: 'FeatureCollection', features: [] };
  private current = new Float32Array(0);
  private from = new Float32Array(0);
  private target = new Float32Array(0);
  private frame = 0;
  private revealTimer = 0;
  private reveal = 1;
  private started = 0;
  private lastWrite = -Infinity;
  private path: UpdatePath = 'feature-state';
  private truck?: Marker;
  private truckNode?: HTMLDivElement;
  private position?: [number, number];
  private positionFrom?: [number, number];
  private positionTo?: [number, number];
  private samples: Marker[] = [];
  private writes = 0;
  private errorReported = false;
  constructor(private map: GLMap, private fail: () => void) {}
  private color(code: number) { return getComputedStyle(document.documentElement).getPropertyValue(`--risk-${tokens[code] ?? 'unknown'}`).trim(); }
  private image(kind: 'unknown' | 'unavailable' | 'blocked') {
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 24; const c = canvas.getContext('2d')!;
    c.translate(12, 12); c.strokeStyle = this.color(kind === 'blocked' ? 5 : 0); c.lineWidth = 2;
    if (kind === 'blocked') { c.font = 'bold 17px sans-serif'; c.textAlign = 'center'; c.fillStyle = c.strokeStyle; c.fillText('!', 0, 6); }
    else { c.beginPath(); c.arc(0, 0, 7, 0, Math.PI * 2); if (kind === 'unavailable') c.setLineDash([3, 2]); c.stroke(); if (kind === 'unknown') { c.save(); c.clip(); for (let x = -16; x < 16; x += 5) { c.beginPath(); c.moveTo(x, -9); c.lineTo(x + 18, 9); c.stroke(); } c.restore(); } }
    return c.getImageData(0, 0, 24, 24);
  }
  install() {
    if (!this.data || !this.map.getLayer('background')) return;
    const m = this.map, before = m.getLayer('rs-casing-0') ? 'rs-casing-0' : undefined;
    if (!m.getSource('rs-heat')) m.addSource('rs-heat', { type: 'geojson', data: this.source });
    for (let k = 1; k <= 5; k++) {
      const id = `rs-heat-${k}`, hue = this.color(k);
      if (!m.getLayer(id)) m.addLayer({ id, type: 'heatmap', source: 'rs-heat', paint: { 'heatmap-weight': this.expression(k), 'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 3, 28, 6, 48, 10, 64, 15, 84], 'heatmap-intensity': 1, 'heatmap-opacity': k === 1 ? .18 : .48, 'heatmap-opacity-transition': { duration: 0 }, 'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'], 0, `${hue}00`, .2, hue, 1, hue] } }, before);
      // RGB never changes with density; alpha alone gives the soft field.
      m.setPaintProperty(id, 'heatmap-color', ['interpolate', ['linear'], ['heatmap-density'], 0, `${hue}00`, .2, hue, 1, hue]);
    }
    for (const kind of ['unknown', 'unavailable', 'blocked'] as const) {
      const id = `rs-heat-${kind}`, image = this.image(kind); if (m.hasImage(id)) m.updateImage(id, image); else m.addImage(id, image);
      if (!m.getLayer(id)) m.addLayer({ id, type: 'symbol', source: 'rs-heat', layout: { 'icon-image': id, 'icon-allow-overlap': true, 'icon-ignore-placement': true, ...(kind === 'blocked' ? { 'icon-offset': [7, -7] } : {}) }, paint: { 'icon-opacity': kind === 'blocked' ? ['coalesce', ['feature-state', 'blocked'], 0] : ['case', ['==', ['feature-state', 'level'], kind === 'unknown' ? 0 : 9], 1, 0] } }, before);
    }
    this.write(this.current); this.visibility(); this.updateSamples();
  }
  private expression(k: number): ExpressionSpecification { return this.path === 'feature-state' ? ['coalesce', ['feature-state', `w${k}`], 0] : ['get', `w${k}`]; }
  set(state: HeatState, route: string | null) {
    const data = state.decoded?.kind === 'ready' ? state.decoded.data : undefined;
    const fresh = data !== this.data, previous = this.state, changed = fresh || previous?.heatHour !== state.heatHour || previous?.heatFilter !== state.heatFilter;
    this.state = state;
    if (fresh) {
      clearTimeout(this.revealTimer); cancelAnimationFrame(this.frame); this.frame = 0; this.position = undefined; this.data = data; this.samples.forEach(s => s.remove()); this.samples = [];
      this.source.features = data ? data.payload.points.map((coordinates, id) => ({ type: 'Feature', id, geometry: { type: 'Point', coordinates: [...coordinates] }, properties: { level: 1, blocked: 0, w1: 0, w2: 0, w3: 0, w4: 0, w5: 0 } })) : [];
      this.current = new Float32Array((data?.payload.point_count ?? 0) * 5);
      if (data) this.install();
      (this.map.getSource('rs-heat') as GeoJSONSource | undefined)?.setData(this.source);
      this.reveal = reduced() ? 1 : 0;
      if (!reduced()) this.revealTimer = window.setTimeout(() => { this.reveal = 1; for (let k = 1; k <= 5; k++) { if (!this.map.getLayer(`rs-heat-${k}`)) continue; this.map.setPaintProperty(`rs-heat-${k}`, 'heatmap-opacity-transition', { duration: 400 }); this.map.setPaintProperty(`rs-heat-${k}`, 'heatmap-opacity', k === 1 ? .18 : .48); } }, 950);
    }
    if (!data) { this.visibility(); if (this.truckNode) this.truckNode.hidden = true; return; }
    if (changed) {
      this.target = weightsAt(data, state.heatHour, state.heatFilter); this.from = this.current.slice(); this.started = performance.now();
      const levels = levelsAt(data, state.heatHour, state.heatFilter);
      this.source.features.forEach((f, i) => { f.properties!.level = levels[i]; f.properties!.blocked = data.frames[state.heatHour]!.blocked[i]; });
      // Availability and risk weights share feature state. Geometry stays fixed
      // during scrub; no source parsing or transport is needed for this path.
      if (fresh || reduced()) { this.current.set(this.target); this.write(this.current); }
    }
    const readout = truckReadout(data, route, state.heatHour, state.heatFilter);
    this.updateTruck(readout, changed || previous?.decoded !== state.decoded);
    this.updateSamples(); this.visibility();
    if (changed && !fresh && !reduced()) this.animate();
  }
  private visibility() {
    const visible = !!this.data && !!this.state?.heatEnabled;
    for (const layer of this.map.getStyle().layers.filter(l => l.id.startsWith('rs-heat-'))) this.map.setLayoutProperty(layer.id, 'visibility', visible ? 'visible' : 'none');
    for (let k = 1; k <= 5; k++) if (this.map.getLayer(`rs-heat-${k}`)) this.map.setPaintProperty(`rs-heat-${k}`, 'heatmap-opacity', this.reveal * (k === 1 ? .18 : .48));
    this.samples.forEach(s => s.getElement().hidden = !visible || !this.state?.showSamplePoints);
  }
  private animate() {
    cancelAnimationFrame(this.frame);
    const step = (now: number) => {
      const t = Math.min(1, (now - this.started) / 180);
      if (now - this.lastWrite >= 16 || t === 1) {
        fadeWeights(this.from, this.target, t, this.current); this.write(this.current); this.lastWrite = now;
        if (this.positionFrom && this.positionTo) { this.position = [this.positionFrom[0] + (this.positionTo[0] - this.positionFrom[0]) * t, this.positionFrom[1] + (this.positionTo[1] - this.positionFrom[1]) * t]; this.truck?.setLngLat(this.position); }
      }
      this.frame = t < 1 ? requestAnimationFrame(step) : 0;
    }; this.frame = requestAnimationFrame(step);
  }
  private write(weights: Float32Array) {
    if (!this.data || !this.map.getSource('rs-heat')) return;
    try {
      const n = this.data.payload.point_count;
      for (let i = 0; i < n; i++) {
        const values: Record<string, number> = { level: this.source.features[i]!.properties!.level as number, blocked: this.source.features[i]!.properties!.blocked as number }; for (let k = 1; k <= 5; k++) values[`w${k}`] = weights[(k - 1) * n + i]!;
        if (this.path === 'feature-state') this.map.setFeatureState({ source: 'rs-heat', id: i }, values); else Object.assign(this.source.features[i]!.properties!, values);
      }
      if (this.path === 'setData') (this.map.getSource('rs-heat') as GeoJSONSource).setData(this.source);
      this.writes++;
    } catch { if (!this.errorReported) { this.errorReported = true; this.fail(); } }
  }
  private updateTruck(info: ReturnType<typeof truckReadout>, changed: boolean) {
    if (!this.truck) {
      this.truckNode = document.createElement('div'); this.truckNode.className = 'heat-truck';
      this.truckNode.innerHTML = '<div class="heat-truck-glyph"><svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M3 5h11v12H3zM14 10h4l3 4v3h-7"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/></svg></div><div class="heat-truck-card"><i></i><span></span></div>';
      this.truck = new Marker({ element: this.truckNode, anchor: 'top-left', offset: [-17, -17] }).setLngLat([0, 0]).addTo(this.map);
    }
    this.truckNode!.hidden = info.kind !== 'position';
    if (info.kind !== 'position') { this.position = undefined; return; }
    this.positionFrom = this.position; this.positionTo = [info.lon, info.lat];
    if (!this.position || !changed || reduced()) { this.position = this.positionTo; this.truck.setLngLat(this.position); }
    const card = this.truckNode!.querySelector<HTMLElement>('.heat-truck-card')!, screen = this.map.project([info.lon, info.lat]);
    card.style.transform = `translate(${Math.min(0, this.map.getContainer().clientWidth - screen.x - 200)}px, ${screen.y > 120 ? -84 : 44}px)`;
    const shape = card.querySelector<HTMLElement>('i')!; shape.className = info.level === 'UNAVAILABLE' ? 'heat-unavailable-key' : 'map-tooltip-shape'; shape.dataset.level = info.level; shape.style.color = this.color(Number(Object.entries(LEVEL_NAMES).find(([, level]) => level === info.level)?.[0] ?? 0));
    card.querySelector('span')!.textContent = `Estimated mile ${info.mile.toFixed(1)} · ${info.level.replace('_', ' ')} · ${info.dominant}${info.blocked ? ' · Known No Travel evidence' : ''}. Conditions here at +${this.state!.heatHour} h.`;
  }
  private updateSamples() {
    if (!this.data || !this.state) return;
    const data = this.data, state = this.state, levels = levelsAt(data, state.heatHour, state.heatFilter);
    if (!this.samples.length && state.showSamplePoints) this.samples = data.payload.points.map((p, i) => {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'heat-sample'; button.innerHTML = '<span></span><small class="heat-sample-tip" role="tooltip" hidden></small>';
      const tip = button.querySelector<HTMLElement>('small')!;
      button.addEventListener('mouseenter', () => tip.hidden = false); button.addEventListener('mouseleave', () => tip.hidden = true); button.addEventListener('focus', () => tip.hidden = false); button.addEventListener('blur', () => tip.hidden = true); button.addEventListener('keydown', e => { if (e.key === 'Escape') tip.hidden = true; });
      const glyph = document.createElement('b'); glyph.setAttribute('aria-hidden', 'true'); button.append(glyph);
      button.dataset.sample = String(i); return new Marker({ element: button, anchor: 'center' }).setLngLat(p).addTo(this.map);
    });
    this.samples.forEach((marker, i) => {
      const node = marker.getElement(), frame = data.frames[state.heatHour]!, level = levels[i]!, text = `Sample ${i + 1} · ${LEVEL_NAMES[level]} · ${DOMINANT[frame.dominant[i]!]} · +${state.heatHour} h · ${data.payload.frames[state.heatHour]!.unavailable_reasons[String(i)] ?? (level === 0 ? 'Incomplete measurements' : 'Available')}${frame.blocked[i] ? ' · Known No Travel evidence' : ''}`;
      node.dataset.level = String(level); node.dataset.blocked = String(!!frame.blocked[i]); node.style.color = this.color(level); node.setAttribute('aria-label', text); node.querySelector('small')!.textContent = `${text} · Known floor ${LEVEL_NAMES[frame.floors[i]!]}`; node.querySelector('b')!.textContent = ['', 'W', 'R', 'S', 'L'][frame.dominant[i]!]!;
    });
  }
  inspect() { return { hour: this.state?.heatHour, filter: this.state?.heatFilter, transitioning: this.frame !== 0, hash: weightHash(this.current), targetHash: weightHash(this.target), bytes: this.data?.bytes, decodeMs: this.data?.decodeMs, writes: this.writes, path: this.path, truck: this.position, pointCount: this.data?.payload.point_count }; }
  async benchmark() {
    if (!this.data) return null;
    const results: Record<string, { medianMs: number; p95Ms: number; syncMedianMs: number }> = {};
    for (const path of ['feature-state', 'setData'] as const) {
      this.path = path; for (let k = 1; k <= 5; k++) this.map.setPaintProperty(`rs-heat-${k}`, 'heatmap-weight', this.expression(k));
      const total: number[] = [], sync: number[] = [];
      for (let h = 0; h < 16; h++) {
        const start = performance.now(); this.write(weightsAt(this.data, h, 'combined')); sync.push(performance.now() - start);
        await new Promise<void>(resolve => this.map.once('idle', () => resolve())); total.push(performance.now() - start);
      }
      total.sort((a, b) => a - b); sync.sort((a, b) => a - b); results[path] = { medianMs: total[8]!, p95Ms: total[15]!, syncMedianMs: sync[8]! };
    }
    this.path = results['feature-state']!.medianMs <= results.setData!.medianMs ? 'feature-state' : 'setData';
    for (let k = 1; k <= 5; k++) this.map.setPaintProperty(`rs-heat-${k}`, 'heatmap-weight', this.expression(k)); this.write(this.current); return results;
  }
  destroy() { cancelAnimationFrame(this.frame); clearTimeout(this.revealTimer); this.samples.forEach(s => s.remove()); this.truck?.remove(); }
}
