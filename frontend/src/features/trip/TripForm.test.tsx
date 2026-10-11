import { StrictMode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { AnalysisStoreProvider } from '../../api/analysis-store';
import { TripForm } from './TripForm';
import { useTripPlanner } from './useTripPlanner';
import type { useHealth } from '../../api/useHealth';
import { analysisFixture, FIXED_NOW, testDraft } from './test-fixtures';
import { encodeDraft } from './url';

beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(FIXED_NOW); localStorage.clear(); history.replaceState(null, '', '/'); });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const healthy: ReturnType<typeof useHealth> = { status: 'healthy', version: 'test', requestId: undefined, retry: () => {} };
function Probe({ health = healthy }: { health?: ReturnType<typeof useHealth> }) { const planner = useTripPlanner(health); return <TripForm planner={planner} />; }
function mount(health = healthy) {
  return render(<StrictMode><QueryClientProvider client={new QueryClient()}><AnalysisStoreProvider><Probe health={health} /></AnalysisStoreProvider></QueryClientProvider></StrictMode>);
}
function fillExample() { fireEvent.click(screen.getByRole('button', { name: 'Chicago, IL to Detroit, MI' })); }
async function tick(ms = 50) { await act(() => vi.advanceTimersByTimeAsync(ms)); }
test('examples resolve coordinates without geocoding; swap and Auto send the exact contract', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(analysisFixture()))); vi.stubGlobal('fetch', fetch); mount(); fillExample();
  fireEvent.click(screen.getByRole('button', { name: 'Swap origin and destination' })); expect((screen.getByRole('combobox', { name: 'Origin' }) as HTMLInputElement).value).toBe('Detroit, MI');
  fireEvent.change(screen.getByLabelText('Cargo weight', { exact: true }), { target: { value: '30000.0000000000000001' } }); fireEvent.click(screen.getByRole('button', { name: 'Analyze routes' })); await tick();
  expect(fetch).toHaveBeenCalledOnce(); const body = fetch.mock.calls[0]?.[1]?.body as string;
  expect(body).toContain('"load_weight_lb":30000.0000000000000001'); expect(body).not.toContain('checkpoint_interval_miles'); expect(JSON.parse(body).origin.latitude).toBe(42.3314);
  expect(screen.getByLabelText('Analysis summary').textContent).toContain('3 routes returned'); expect(screen.getByLabelText('Request ID')).toBeTruthy();
});
test('blocked submit focuses the first invalid input and API details map safely onto inputs', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'VALIDATION_ERROR', message: 'RAW_PROVIDER_URL', details: { load_weight_lb: 'RAW' } } }), { status: 400 })));
  mount(); fireEvent.click(screen.getByRole('button', { name: 'Analyze routes' })); await tick(); expect(document.activeElement?.id).toBe('trip-origin');
  fillExample(); fireEvent.click(screen.getByRole('button', { name: 'Analyze routes' })); await tick(); expect(document.activeElement?.id).toBe('trip-weight'); expect(document.body.textContent).not.toContain('RAW');
});
test('pending progress disables submit; cancellation aborts without an error or late success', async () => {
  let signal: AbortSignal | undefined;
  vi.stubGlobal('fetch', vi.fn((_url, options: RequestInit) => { signal = options.signal as AbortSignal; return new Promise((_resolve, reject) => signal?.addEventListener('abort', () => reject(new Error('cancelled')))); }));
  mount(); fillExample(); fireEvent.click(screen.getByRole('button', { name: 'Analyze routes' }));
  expect((screen.getByRole('button', { name: /Analyze routes/ }) as HTMLButtonElement).disabled).toBe(true); await tick(9000); expect(screen.getByText('Still working. The weather service can be slow.')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' })); await tick(); expect(signal?.aborted).toBe(true); expect(screen.queryByLabelText('Analysis error')).toBeNull(); expect((screen.getByRole('button', { name: 'Analyze routes' }) as HTMLButtonElement).disabled).toBe(false);
});
test('THROTTLED honors Retry-After exactly and re-enables without automatic retry', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'THROTTLED', message: 'raw', details: {} } }), { status: 429, headers: { 'Retry-After': '3', 'X-Request-ID': 'rate-test' } })); vi.stubGlobal('fetch', fetch);
  mount(); fillExample(); fireEvent.click(screen.getByRole('button', { name: 'Analyze routes' })); await tick(); expect(screen.getByText('3s')).toBeTruthy(); expect((screen.getByRole('button', { name: 'Analyze routes' }) as HTMLButtonElement).disabled).toBe(true);
  await tick(3100); expect((screen.getByRole('button', { name: 'Analyze routes' }) as HTMLButtonElement).disabled).toBe(false); expect(fetch).toHaveBeenCalledOnce();
});
test('complete future URL runs once under StrictMode and does not repeat after remount', async () => {
  history.replaceState(null, '', '/?' + encodeDraft(testDraft()));
  const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(analysisFixture())))); vi.stubGlobal('fetch', fetch);
  const first = mount(); await tick(); expect(fetch).toHaveBeenCalledOnce(); first.unmount(); mount(); await tick(); expect(fetch).toHaveBeenCalledOnce();
});
test('past URL is restored without running, and minute revalidation exposes stale departure', async () => {
  const draft = testDraft(); draft.wall.time = '11:57'; history.replaceState(null, '', '/?' + encodeDraft(draft)); const fetch = vi.fn(); vi.stubGlobal('fetch', fetch); mount();
  expect(screen.getByText("This link's departure time has passed. Update it to analyze.")).toBeTruthy(); await tick(181000); expect(document.body.textContent).toContain('more than five minutes'); expect(fetch).not.toHaveBeenCalled();
});
test('queued analysis starts once after health wakes; cancel while waking sends nothing', async () => {
  const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(analysisFixture())))); vi.stubGlobal('fetch', fetch);
  const client = new QueryClient(); const tree = (health: ReturnType<typeof useHealth>) => <QueryClientProvider client={client}><AnalysisStoreProvider><Probe health={health} /></AnalysisStoreProvider></QueryClientProvider>;
  const view = render(tree({ ...healthy, status: 'waking' })); fillExample(); fireEvent.click(screen.getByRole('button', { name: 'Analyze routes' })); expect(screen.getByText('Waking up the backend. Analysis starts when it is ready.')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' })); view.rerender(tree(healthy)); await tick(); expect(fetch).not.toHaveBeenCalled();
  view.rerender(tree({ ...healthy, status: 'waking' })); fireEvent.click(screen.getByRole('button', { name: 'Analyze routes' })); view.rerender(tree(healthy)); await tick(); expect(fetch).toHaveBeenCalledOnce();
});
