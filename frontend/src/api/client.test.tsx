import { act, cleanup, render, screen } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, test, vi } from 'vitest';
import { apiRequest, isHealth } from './client';
import { ApiError, errorMessages } from './errors';
import { createQueryClient } from './query';
import { useHealth } from './useHealth';

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });
test('every documented API error maps to fixed recovery and correlation metadata', async () => {
  for (const code of Object.keys(errorMessages)) {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code, message: 'UNTRUSTED_UPSTREAM_DIAGNOSTIC', details: { field: 'INVALID' } } }), { status: 400, headers: { 'X-Request-ID': 'test-id', 'Retry-After': '12' } })));
    let result: unknown;
    try { await apiRequest('health/', isHealth); } catch (error) { result = error; }
    if (!(result instanceof ApiError)) throw new Error('Expected a typed API error.');
    expect(result).toBeInstanceOf(ApiError); expect(result.code).toBe(code); expect(result.presentation.action.length).toBeGreaterThan(0); expect(result.message).not.toContain('UNTRUSTED'); expect(result.requestId).toBe('test-id'); expect(result.retryAfterSeconds).toBe(12); expect(result.details).toEqual({ field: 'INVALID' });
  }
  expect(Object.keys(errorMessages)).toHaveLength(18);
});
test('malformed envelopes, unknown codes and invalid successes fail closed', async () => {
  for (const [body, status] of [[{}, 400], [{ error: { code: 'UNKNOWN', message: 'raw', details: {} } }, 500], [{ status: 'ok', version: 1 }, 200]] as const) {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })));
    await expect(apiRequest('health/', isHealth)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  }
});
test('caller AbortSignal cancels fetch without exposing network diagnostics', async () => {
  vi.stubGlobal('fetch', vi.fn((_url, options: RequestInit) => new Promise((_resolve, reject) => options.signal?.addEventListener('abort', () => reject(new Error('PRIVATE_TRANSPORT')), { once: true }))));
  const controller = new AbortController(); const request = apiRequest('health/', isHealth, { signal: controller.signal }); controller.abort(); await expect(request).rejects.toMatchObject({ code: 'ABORTED', message: 'Request cancelled.' });
});
test('query defaults forbid automatic analysis retries and focus refetches', () => {
  const defaults = createQueryClient().getDefaultOptions(); expect(defaults.mutations?.retry).toBe(false); expect(defaults.queries?.retry).toBe(false); expect(defaults.queries?.refetchOnWindowFocus).toBe(false); expect(defaults.queries?.refetchOnReconnect).toBe(false);
});
function HealthProbe() { const health = useHealth(); return <><output aria-label="Health">{health.status}</output><button onClick={health.retry}>Retry</button></>; }
function mountHealth() { const client = createQueryClient(); render(<QueryClientProvider client={client}><HealthProbe /></QueryClientProvider>); return client; }
test('health goes checking to healthy and does not poll after readiness', async () => {
  vi.useFakeTimers(); const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'ok', version: '0.1.0', check: 'liveness' }))); vi.stubGlobal('fetch', fetch); mountHealth();
  expect(screen.getByLabelText('Health').textContent).toBe('checking'); await act(() => vi.advanceTimersByTimeAsync(100)); expect(screen.getByLabelText('Health').textContent).toBe('healthy'); await act(() => vi.advanceTimersByTimeAsync(100_000)); expect(fetch).toHaveBeenCalledOnce();
});
test('cold health exposes waking then unreachable by 90 seconds with bounded sends', async () => {
  vi.useFakeTimers(); const fetch = vi.fn().mockRejectedValue(new Error('Offline')); vi.stubGlobal('fetch', fetch); mountHealth();
  await act(() => vi.advanceTimersByTimeAsync(2_000)); expect(screen.getByLabelText('Health').textContent).toBe('waking'); await act(() => vi.advanceTimersByTimeAsync(90_000)); expect(screen.getByLabelText('Health').textContent).toBe('unreachable'); expect(fetch.mock.calls.length).toBeLessThanOrEqual(7);
  const count = fetch.mock.calls.length; await act(() => vi.advanceTimersByTimeAsync(100_000)); expect(fetch).toHaveBeenCalledTimes(count);
});
test('a stuck health request is aborted and cannot run beyond the wake window', async () => {
  vi.useFakeTimers(); let aborted = 0;
  vi.stubGlobal('fetch', vi.fn((_url, options: RequestInit) => new Promise((_resolve, reject) => options.signal?.addEventListener('abort', () => { aborted++; reject(new Error('Timeout')); }))));
  mountHealth(); await act(() => vi.advanceTimersByTimeAsync(91_000)); expect(screen.getByLabelText('Health').textContent).toBe('unreachable'); expect(aborted).toBeGreaterThan(0);
});
