import { createContext, useContext, useState, useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';
import type { HeatDecode, HeatFilter } from '../features/heatmap/decoder';
import { clampHour } from '../features/heatmap/presentation';

export interface HeatState { decoded: HeatDecode | null; heatEnabled: boolean; heatHour: number; heatFilter: HeatFilter; playing: boolean; speed: number; showSamplePoints: boolean; loop: boolean; dragging: boolean; announce: number }
export const PLAY_STEP_MS = 1000;

// Map contract: one provider shared by console and map; selection changes clear
// checkpoint details, hover never changes selection. IDs/indices are API identities.
export interface SelectionState { selectedRouteId: string | null; selectedCheckpointIndex: number | null; hoveredRouteId: string | null; hoveredCheckpointIndex: number | null }
export function createSelectionStore() {
  let state: SelectionState = { selectedRouteId: null, selectedCheckpointIndex: null, hoveredRouteId: null, hoveredCheckpointIndex: null };
  let selected = { selectedRouteId: state.selectedRouteId, selectedCheckpointIndex: state.selectedCheckpointIndex };
  const listeners = new Set<() => void>();
  let heat: HeatState = { decoded: null, heatEnabled: false, heatHour: 0, heatFilter: 'combined', playing: false, speed: 1, showSamplePoints: false, loop: false, dragging: false, announce: 0 };
  const heatListeners = new Set<() => void>();
  const updateHeat = (patch: Partial<HeatState>) => { const next = { ...heat, ...patch }; if (Object.keys(patch).every(k => next[k as keyof HeatState] === heat[k as keyof HeatState])) return; heat = next; heatListeners.forEach(fn => fn()); };
  const update = (next: SelectionState) => {
    if (JSON.stringify(next) === JSON.stringify(state)) return;
    if (next.selectedRouteId !== state.selectedRouteId || next.selectedCheckpointIndex !== state.selectedCheckpointIndex) selected = { selectedRouteId: next.selectedRouteId, selectedCheckpointIndex: next.selectedCheckpointIndex };
    state = next; listeners.forEach(fn => fn());
  };
  return {
    getState: () => state, getSelection: () => selected,
    subscribe: (fn: () => void) => { listeners.add(fn); return () => { listeners.delete(fn); }; },
    selectRoute: (id: string | null) => update({ ...state, selectedRouteId: id, selectedCheckpointIndex: null, hoveredCheckpointIndex: null }),
    selectCheckpoint: (index: number | null) => update({ ...state, selectedCheckpointIndex: index }),
    hoverRoute: (id: string | null) => update({ ...state, hoveredRouteId: id }),
    hoverCheckpoint: (index: number | null) => update({ ...state, hoveredCheckpointIndex: index }),
    getHeat: () => heat,
    subscribeHeat: (fn: () => void) => { heatListeners.add(fn); return () => { heatListeners.delete(fn); }; },
    setHeatData: (decoded: HeatDecode | null) => updateHeat({ decoded, heatEnabled: decoded?.kind === 'ready', heatHour: 0, heatFilter: 'combined', playing: false, loop: false, dragging: false }),
    updateHeat,
    setHour: (hour: number, announce = false) => updateHeat({ heatHour: clampHour(hour), playing: false, ...(announce ? { announce: heat.announce + 1 } : {}) }),
    togglePlay: () => { const last = heat.decoded?.kind === 'ready' ? heat.decoded.data.payload.forecast_coverage.last_usable_hour : null; if (last === null) return; updateHeat({ playing: !heat.playing, ...(heat.playing ? { announce: heat.announce + 1 } : heat.heatHour >= last ? { heatHour: 0 } : {}) }); },
    tick: () => { if (!heat.playing || heat.decoded?.kind !== 'ready') return; const last = heat.decoded.data.payload.forecast_coverage.last_usable_hour ?? 0; if (heat.heatHour >= last) updateHeat(heat.loop ? { heatHour: 0 } : { playing: false, announce: heat.announce + 1 }); else updateHeat({ heatHour: heat.heatHour + 1 }); },
  };
}
export type SelectionStore = ReturnType<typeof createSelectionStore>;
// A stable page store; hover subscribers update paint/DOM without React renders.
export function useSelectionState() { return useState(createSelectionStore)[0]; }
const Context = createContext<ReturnType<typeof useSelectionState> | null>(null);
export function SelectionProvider({ value, children }: { value: ReturnType<typeof useSelectionState>; children: ReactNode }) { return <Context.Provider value={value}>{children}</Context.Provider>; }
export function useSelectionStore() { const value = useContext(Context); if (!value) throw new Error('SelectionProvider required.'); return value; }
export function useSelection() {
  const store = useSelectionStore(), state = useSyncExternalStore(store.subscribe, store.getSelection, store.getSelection);
  return { ...state, selectRoute: store.selectRoute, selectCheckpoint: store.selectCheckpoint, hoverRoute: store.hoverRoute, hoverCheckpoint: store.hoverCheckpoint };
}
export function useHeatState() { const store = useSelectionStore(); return useSyncExternalStore(store.subscribeHeat, store.getHeat, store.getHeat); }
