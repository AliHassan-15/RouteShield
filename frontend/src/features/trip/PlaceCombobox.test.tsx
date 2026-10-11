import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { PlaceCombobox } from './PlaceCombobox';
import type { PlaceField } from './model';
import { geocodeFixture } from './test-fixtures';

beforeEach(() => vi.useFakeTimers());
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });
function mount(recent = false) {
  function Field() {
    const [value, setValue] = useState<PlaceField>({ text: '', place: null });
    return <PlaceCombobox field="origin" value={value} recent={recent ? geocodeFixture().candidates : []} onEdit={text => setValue({ text, place: null })} onSelect={place => setValue({ text: place.label, place })} />;
  }
  render(<QueryClientProvider client={new QueryClient()}><Field /></QueryClientProvider>);
  return screen.getByRole('combobox');
}
async function tick(ms = 450) { await act(() => vi.advanceTimersByTimeAsync(ms)); await act(() => vi.advanceTimersByTimeAsync(0)); }
test('minimum characters, exact debounce and provider order with unconfirmed attribution', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(geocodeFixture()))); vi.stubGlobal('fetch', fetch);
  const input = mount(); fireEvent.focus(input); fireEvent.change(input, { target: { value: 'Ch' } }); await tick(500); expect(fetch).not.toHaveBeenCalled();
  fireEvent.change(input, { target: { value: 'Chi' } }); await tick(399); expect(fetch).not.toHaveBeenCalled(); expect(screen.getByText('Finding matches…')).toBeTruthy();
  await tick(50); expect(fetch).toHaveBeenCalledOnce(); expect(screen.getAllByRole('option').map(o => o.textContent)).toEqual(['Chicago WestIllinois · United States', 'Chicago CenterIllinois · United States', 'Chicago EastIllinois · United States']);
  expect(screen.getByText('Synthetic attribution from API metadata')).toBeTruthy(); expect(screen.getByText('Attribution unconfirmed')).toBeTruthy();
});
test('editing aborts the previous request immediately before the next debounce', async () => {
  let signal: AbortSignal | undefined;
  const fetch = vi.fn((_url, options: RequestInit) => { signal = options.signal as AbortSignal; return new Promise(() => {}); }); vi.stubGlobal('fetch', fetch);
  const input = mount(); fireEvent.change(input, { target: { value: 'Chicago' } }); await tick(); expect(signal?.aborted).toBe(false);
  fireEvent.change(input, { target: { value: 'Detroit' } }); await tick(1); expect(signal?.aborted).toBe(true); expect(fetch).toHaveBeenCalledOnce();
});
test('keyboard wraps, Home/End move, Enter selects, editing invalidates and Escape closes then clears', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(geocodeFixture())))));
  const input = mount(); fireEvent.change(input, { target: { value: 'Chicago' } }); await tick();
  fireEvent.keyDown(input, { key: 'ArrowUp' }); expect(input.getAttribute('aria-activedescendant')).toMatch(/option-2$/);
  fireEvent.keyDown(input, { key: 'ArrowDown' }); expect(input.getAttribute('aria-activedescendant')).toMatch(/option-0$/);
  fireEvent.keyDown(input, { key: 'End' }); fireEvent.keyDown(input, { key: 'Home' }); fireEvent.keyDown(input, { key: 'Enter' });
  expect((input as HTMLInputElement).value).toBe('Chicago West'); expect(input.getAttribute('aria-expanded')).toBe('false');
  fireEvent.change(input, { target: { value: 'Chicago West edit' } }); expect(screen.getByText('Select a match')).toBeTruthy();
  fireEvent.keyDown(input, { key: 'Escape' }); expect((input as HTMLInputElement).value).toBe('Chicago West edit'); fireEvent.keyDown(input, { key: 'Escape' }); expect((input as HTMLInputElement).value).toBe('');
});
test('Tab closes without selecting; focused empty fields offer local recents without geocoding', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch); const input = mount(true); fireEvent.focus(input);
  expect(screen.getAllByRole('option')).toHaveLength(3); fireEvent.keyDown(input, { key: 'ArrowDown' }); fireEvent.keyDown(input, { key: 'Tab' });
  expect((input as HTMLInputElement).value).toBe(''); expect(input.getAttribute('aria-expanded')).toBe('false'); await tick(); expect(fetch).not.toHaveBeenCalled();
});
test('empty search and safe error recovery do not expose raw errors', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(geocodeFixture(0)))).mockRejectedValueOnce(new Error('secret upstream URL')).mockResolvedValueOnce(new Response(JSON.stringify(geocodeFixture()))); vi.stubGlobal('fetch', fetch);
  const input = mount(); fireEvent.change(input, { target: { value: 'Nowhere' } }); await tick(); expect(screen.getByText('No matches. Try a city, address or place name.')).toBeTruthy();
  fireEvent.change(input, { target: { value: 'Chicago' } }); await tick(); expect(screen.getByRole('button', { name: 'Retry search' })).toBeTruthy(); expect(document.body.textContent).not.toContain('secret upstream');
  fireEvent.click(screen.getByRole('button', { name: 'Retry search' })); await tick(20); expect(screen.getAllByRole('option')).toHaveLength(3);
});
