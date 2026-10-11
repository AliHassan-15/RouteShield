import { ApiError, isErrorCode } from './errors';
import type { AnalysisRequest, AnalysisResponse, ErrorValue, GeocodeResponse, HealthResponse } from './types';

type Endpoint = 'health/' | 'route-analysis/' | 'geocode/';
function record(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null && !Array.isArray(value); }
function apiBase() {
  const base = new URL(import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1/');
  if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password || base.search || base.hash) throw new ApiError('INVALID_RESPONSE');
  if (!base.pathname.endsWith('/')) base.pathname += '/';
  return base;
}
export async function apiRequest<T>(endpoint: Endpoint, parse: (body: unknown) => body is T, options: { signal?: AbortSignal; body?: AnalysisRequest; query?: URLSearchParams; timeoutMs?: number } = {}): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  options.signal?.addEventListener('abort', abort, { once: true });
  if (options.signal?.aborted) abort();
  const timer = setTimeout(abort, options.timeoutMs ?? 36_000);
  try {
    const url = new URL(endpoint, apiBase());
    if (options.query) url.search = options.query.toString();
    const response = await fetch(url, { signal: controller.signal, method: options.body ? 'POST' : 'GET', headers: { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}) }, ...(options.body ? { body: JSON.stringify(options.body) } : {}) });
    const rawId = response.headers.get('X-Request-ID');
    const requestId = rawId && /^[a-zA-Z0-9-]{1,80}$/.test(rawId) ? rawId : undefined;
    const retry = Number(response.headers.get('Retry-After'));
    const retryAfter = Number.isInteger(retry) && retry > 0 && retry <= 86_400 ? retry : undefined;
    let body: unknown;
    try { body = await response.json(); } catch { throw new ApiError('INVALID_RESPONSE', response.status, {}, requestId); }
    if (!response.ok) {
      if (!record(body) || !record(body.error) || !isErrorCode(body.error.code) || typeof body.error.message !== 'string' || !record(body.error.details)) throw new ApiError('INVALID_RESPONSE', response.status, {}, requestId);
      const details: Record<string, ErrorValue> = {};
      for (const [key, value] of Object.entries(body.error.details)) if (typeof value === 'string' || typeof value === 'number' && Number.isFinite(value)) details[key] = value;
      // Display fixed recovery text. Never render arbitrary server messages/exception strings.
      throw new ApiError(body.error.code, response.status, details, requestId, retryAfter);
    }
    if (!parse(body)) throw new ApiError('INVALID_RESPONSE', response.status, {}, requestId);
    return body;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(options.signal?.aborted ? 'ABORTED' : 'NETWORK_ERROR');
  } finally { clearTimeout(timer); options.signal?.removeEventListener('abort', abort); }
}
export function isHealth(body: unknown): body is HealthResponse {
  return record(body) && (body.status === 'ok' || body.status === 'ready') && typeof body.version === 'string' && (body.check === 'liveness' || body.check === 'readiness');
}
function isAnalysis(body: unknown): body is AnalysisResponse {
  return record(body) && Array.isArray(body.routes) && typeof body.request_id === 'string' && typeof body.is_simulation === 'boolean' && Array.isArray(body.warnings) && typeof body.recommendation_status === 'string' && record(body.heatmap);
}
function isGeocode(body: unknown): body is GeocodeResponse {
  return record(body) && Array.isArray(body.candidates) && body.candidates.every(item => record(item) && typeof item.candidate_id === 'string' && typeof item.label === 'string' && typeof item.latitude === 'number' && typeof item.longitude === 'number' && Number.isFinite(item.latitude) && Number.isFinite(item.longitude)) && record(body.attribution);
}
export function analyzeTrip(body: AnalysisRequest, signal?: AbortSignal) { return apiRequest('route-analysis/', isAnalysis, { body, signal }); }
export function geocode(query: string, signal?: AbortSignal) { return apiRequest('geocode/', isGeocode, { query: new URLSearchParams({ q: query }), signal }); }
