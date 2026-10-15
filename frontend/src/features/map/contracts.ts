import type { AnalysisResponse, Position } from '../../api/types';
import type { SelectionState } from '../../api/selection-store';
import type { HeatState } from '../../api/selection-store';
export type Theme = 'light' | 'dark';
export interface Padding { top: number; right: number; bottom: number; left: number }
export type MapEvent = { type: 'route' | 'hover'; id: string | null } | { type: 'checkpoint'; index: number } | { type: 'checkpoint-hover'; index: number | null } | { type: 'heat-toggle' } | { type: 'ready' } | { type: 'failure'; reason: 'no WebGL' | 'style failed to load' | 'tiles unreachable' | 'heat overlay unavailable' } | { type: 'attribution'; html: string[] };
export interface MapEngine {
  init(container: HTMLElement, theme: Theme): Promise<void>;
  setTheme(theme: Theme): void;
  setRoutes(analysis: AnalysisResponse | null): void;
  setSelection(selection: SelectionState): void;
  setHeat(state: HeatState): void;
  setHover(id: string | null): void;
  fitTo(id?: string | null, force?: boolean): void;
  focusPoint(lng: number, lat: number, options?: { duration?: number }): void;
  setPadding(padding: Padding): void;
  resize(): void;
  zoom(delta: number): void;
  project(point: Position): { x: number; y: number };
  retry(): void;
  dismissTooltip(): void;
  on(listener: (event: MapEvent) => void): () => void;
  destroy(): void;
}
export type EngineFactory = () => MapEngine;
