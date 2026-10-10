import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import App from './App';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderShell() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <App />
    </QueryClientProvider>,
  );
}

test('shows loading while health is pending', () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
  renderShell();
  expect(screen.getByRole('status').textContent).toContain('Loading');
});

test('shows the backend version when healthy', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ status: 'ok', version: '0.1.0' }),
  }));
  renderShell();
  expect((await screen.findByText('Healthy — version 0.1.0')).textContent).toContain('Healthy');
});

test('shows unreachable on a network failure', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network unavailable')));
  renderShell();
  expect((await screen.findByRole('alert')).textContent).toContain('unreachable');
});
