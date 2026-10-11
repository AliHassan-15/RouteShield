import { apiRequest, isHealth } from './client';
export function fetchHealth(signal: AbortSignal, timeoutMs = 5_000) {
  return apiRequest('health/', isHealth, { signal, timeoutMs });
}
