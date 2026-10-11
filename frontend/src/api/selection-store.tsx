import { createContext, useContext, useState, useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';

// Map contract: one provider shared by console and map; selection changes clear
// checkpoint details, hover never changes selection. IDs/indices are API identities.
export interface SelectionState { selectedRouteId: string | null; selectedCheckpointIndex: number | null; hoveredRouteId: string | null }
export function createSelectionStore() {
  let state: SelectionState = { selectedRouteId: null, selectedCheckpointIndex: null, hoveredRouteId: null };
  let selected = { selectedRouteId: state.selectedRouteId, selectedCheckpointIndex: state.selectedCheckpointIndex };
  const listeners = new Set<() => void>();
  const update = (next: SelectionState) => {
    if (JSON.stringify(next) === JSON.stringify(state)) return;
    if (next.selectedRouteId !== state.selectedRouteId || next.selectedCheckpointIndex !== state.selectedCheckpointIndex) selected = { selectedRouteId: next.selectedRouteId, selectedCheckpointIndex: next.selectedCheckpointIndex };
    state = next; listeners.forEach(fn => fn());
  };
  return {
    getState: () => state, getSelection: () => selected,
    subscribe: (fn: () => void) => { listeners.add(fn); return () => { listeners.delete(fn); }; },
    selectRoute: (id: string | null) => update({ ...state, selectedRouteId: id, selectedCheckpointIndex: null }),
    selectCheckpoint: (index: number | null) => update({ ...state, selectedCheckpointIndex: index }),
    hoverRoute: (id: string | null) => update({ ...state, hoveredRouteId: id }),
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
  return { ...state, selectRoute: store.selectRoute, selectCheckpoint: store.selectCheckpoint, hoverRoute: store.hoverRoute };
}
