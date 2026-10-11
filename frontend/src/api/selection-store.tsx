import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

// Map contract: one provider shared by console and map; selection changes clear
// checkpoint details, hover never changes selection. IDs/indices are API identities.
export interface SelectionState { selectedRouteId: string | null; selectedCheckpointIndex: number | null; hoveredRouteId: string | null }
export function useSelectionState() {
  const [state, set] = useState<SelectionState>({ selectedRouteId: null, selectedCheckpointIndex: null, hoveredRouteId: null });
  const selectRoute = useCallback((id: string | null) => set(s => ({ ...s, selectedRouteId: id, selectedCheckpointIndex: null })), []);
  const selectCheckpoint = useCallback((index: number | null) => set(s => ({ ...s, selectedCheckpointIndex: index })), []);
  const hoverRoute = useCallback((id: string | null) => set(s => ({ ...s, hoveredRouteId: id })), []);
  return useMemo(() => ({ ...state, selectRoute, selectCheckpoint, hoverRoute }), [state, selectRoute, selectCheckpoint, hoverRoute]);
}
const Context = createContext<ReturnType<typeof useSelectionState> | null>(null);
export function SelectionProvider({ value, children }: { value: ReturnType<typeof useSelectionState>; children: ReactNode }) { return <Context.Provider value={value}>{children}</Context.Provider>; }
export function useSelection() { const value = useContext(Context); if (!value) throw new Error('SelectionProvider required.'); return value; }
