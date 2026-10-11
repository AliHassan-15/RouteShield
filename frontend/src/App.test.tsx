import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import App from './App';
import { AnalysisStoreProvider } from './api/analysis-store';

vi.mock('./features/map/MapWorkspace', () => ({ MapWorkspace: () => <section aria-label="Interactive route map" /> }));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function renderShell() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AnalysisStoreProvider><App /></AnalysisStoreProvider>
    </QueryClientProvider>,
  );
}

test('shows loading while health is pending', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
  renderShell();
  expect(screen.getByRole('heading', { name: 'Trip plan' })).toBeTruthy();
  expect(screen.getByText('Checking API')).toBeTruthy();
});

test('shows the backend version when healthy', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'ok', version: '0.1.0', check: 'liveness' }))));
  renderShell();
  expect((await screen.findByText('API healthy · 0.1.0')).textContent).toContain('healthy');
});

test('shows unreachable on a network failure', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network unavailable')));
  vi.useFakeTimers();
  renderShell();
  await act(() => vi.advanceTimersByTimeAsync(91_000));
  expect(screen.getByText('API unreachable')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Retry backend health' })).toBeTruthy();
});
