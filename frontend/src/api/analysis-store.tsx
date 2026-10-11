import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import type { AnalysisRequest, AnalysisResponse } from './types';

export interface AnalysisSnapshot { response: AnalysisResponse; request: AnalysisRequest; wallMs: number }
const Context = createContext<{ snapshot: AnalysisSnapshot | null; setSnapshot: (value: AnalysisSnapshot | null) => void } | null>(null);
export function AnalysisStoreProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshot] = useState<AnalysisSnapshot | null>(null);
  return <Context.Provider value={{ snapshot, setSnapshot }}>{children}</Context.Provider>;
}
export function useAnalysisStore() {
  const value = useContext(Context);
  if (!value) throw new Error('AnalysisStoreProvider is required.');
  return value;
}
