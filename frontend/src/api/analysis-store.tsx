import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import type { AnalysisRequest, AnalysisResponse } from './types';
import { decodeAnalysis } from '../features/heatmap/decoder';
import type { HeatDecode } from '../features/heatmap/decoder';
import { arrivalFor } from '../lib/arrival';

export interface AnalysisSnapshot { response: AnalysisResponse; request: AnalysisRequest; wallMs: number; weightToken?: string; heat?: HeatDecode }
const Context = createContext<{ snapshot: AnalysisSnapshot | null; setSnapshot: (value: AnalysisSnapshot | null) => void } | null>(null);
export function AnalysisStoreProvider({ children }: { children: ReactNode }) {
  const [snapshot, updateSnapshot] = useState<AnalysisSnapshot | null>(null);
  const setSnapshot = (value: AnalysisSnapshot | null) => { if (value) arrivalFor(value.response); updateSnapshot(value ? { ...value, heat: decodeAnalysis(value.response) } : null); };
  return <Context.Provider value={{ snapshot, setSnapshot }}>{children}</Context.Provider>;
}
export function useAnalysisStore() {
  const value = useContext(Context);
  if (!value) throw new Error('AnalysisStoreProvider is required.');
  return value;
}
