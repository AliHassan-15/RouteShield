import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError } from './errors';
import { fetchHealth } from './health';

export const WAKE_BUDGET_MS = 90_000;
export function useHealth() {
  const [attempt, setAttempt] = useState(0), [expired, setExpired] = useState(false), [slow, setSlow] = useState(false);
  const start = useRef(Date.now()), client = useQueryClient();
  const key = ['health', attempt];
  const health = useQuery({ queryKey: key, queryFn: ({ signal }) => {
    const remaining = WAKE_BUDGET_MS - (Date.now() - start.current);
    if (remaining <= 0) throw new ApiError('NETWORK_ERROR');
    return fetchHealth(signal, Math.min(5_000, remaining));
  }, enabled: !expired, gcTime: 0,
  retry: (count, error) => count < 6 && Date.now() - start.current < WAKE_BUDGET_MS - 100 && error instanceof ApiError && (error.code === 'NETWORK_ERROR' || error.status === 503 || error.status === 504),
  retryDelay: count => Math.max(0, Math.min(5_000 * (count + 1), 15_000, WAKE_BUDGET_MS - (Date.now() - start.current))),
  refetchOnWindowFocus: false, refetchOnReconnect: false, staleTime: Infinity });
  useEffect(() => {
    if (!health.isPending) return;
    const waiting = setTimeout(() => setSlow(true), 1_500);
    const end = setTimeout(() => { setExpired(true); void client.cancelQueries({ queryKey: ['health', attempt] }); }, Math.max(0, WAKE_BUDGET_MS - (Date.now() - start.current)));
    return () => { clearTimeout(waiting); clearTimeout(end); };
  }, [health.isPending, client, attempt]);
  const status = health.isSuccess ? 'healthy' : expired || health.isError ? 'unreachable' : slow || health.failureCount > 0 ? 'waking' : 'checking';
  const retry = () => { start.current = Date.now(); setExpired(false); setSlow(false); setAttempt(n => n + 1); };
  return { status, version: health.data?.version, requestId: health.error instanceof ApiError ? health.error.requestId : undefined, retry } as const;
}
