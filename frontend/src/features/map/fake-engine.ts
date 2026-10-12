import type { AnalysisResponse, Position } from '../../api/types';
import type { SelectionState } from '../../api/selection-store';
import type { MapEngine, MapEvent, Padding, Theme } from './contracts';
// A test-only engine: no WebGL or vendor imports in React component tests.
export class FakeEngine implements MapEngine {
  calls: { method: string; value?: unknown }[] = [];
  private events = new Set<(event: MapEvent) => void>();
  async init(_host: HTMLElement, theme: Theme) { this.calls.push({ method: 'init', value: theme }); this.emit({ type: 'ready' }); }
  setTheme(theme: Theme) { this.calls.push({ method: 'theme', value: theme }); }
  setRoutes(analysis: AnalysisResponse | null) { this.calls.push({ method: 'routes', value: analysis?.analysis_id }); }
  setSelection(selection: SelectionState) { this.calls.push({ method: 'selection', value: selection }); }
  setHover(id: string | null) { this.calls.push({ method: 'hover', value: id }); }
  fitTo(id?: string | null, force?: boolean) { this.calls.push({ method: 'fit', value: [id, force] }); }
  focusPoint(lng: number, lat: number, options?: { duration?: number }) { this.calls.push({ method: 'focus', value: [lng, lat, options] }); }
  setPadding(padding: Padding) { this.calls.push({ method: 'padding', value: padding }); }
  resize() { this.calls.push({ method: 'resize' }); }
  zoom(delta: number) { this.calls.push({ method: 'zoom', value: delta }); }
  project(p: Position) { return { x: p[0], y: p[1] }; }
  retry() { this.calls.push({ method: 'retry' }); }
  dismissTooltip() { this.calls.push({ method: 'dismiss' }); }
  on(listener: (event: MapEvent) => void) { this.events.add(listener); return () => { this.events.delete(listener); }; }
  emit(event: MapEvent) { this.events.forEach(fn => fn(event)); }
  destroy() { this.calls.push({ method: 'destroy' }); this.events.clear(); }
}
