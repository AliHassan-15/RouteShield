import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { createSelectionStore, SelectionProvider, useSelection } from '../../api/selection-store';
import { bounds, cameraPadding, chipAvoidsPoints, chipFits, markerEncoding, measureLine, placeChips, pointAt, prepareRoute, routeOffset, sliceMiles, validPosition, visibleLow } from './geometry';
import { attributionEntries, creditParts, offlineStyle, transformStyle } from './basemap';
import { tooltipContent } from './tooltip';
import { resultFixture } from '../results/fixtures';
import { LEVELS } from '../results/presentation';
import { MapWorkspace } from './MapWorkspace';
import { CheckpointList } from './CheckpointList';
import { FakeEngine } from './fake-engine';

beforeEach(() => { vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} }); vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener() {}, removeEventListener() {} })); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe('display geometry calibration', () => {
  const line = measureLine([[0, 0], [1, 0], [2, 0]]);
  it('golden equatorial middle slice preserves an interior vertex', () => { expect(sliceMiles(line, 25, 75, 100)).toEqual([[.5, 0], [1, 0], [1.5, 0]]); });
  it.each([99, 100, 101])('provider length %s calibrates to the actual endpoints', total => { expect(sliceMiles(line, 0, total, total)).toEqual([[0, 0], [1, 0], [2, 0]]); });
  it.each([[], [[1, 0]], [[1, 0], [1, 0]]].map(points => ({ points: points as [number, number][] })))('degenerate geometry remains finite', ({ points }) => { expect(sliceMiles(measureLine(points), 0, 10, 10).flat().every(Number.isFinite)).toBe(true); });
  it('clips ranges, rejects reversed and zero ranges', () => { expect(pointAt(line, -1)).toEqual([0, 0]); expect(pointAt(line, 2)).toEqual([2, 0]); expect(sliceMiles(line, 8, 2, 10)).toEqual([]); expect(sliceMiles(line, 0, 10, 0)).toEqual([]); });
  it('segments consume API ownership and preserve UNKNOWN and block patterns', () => { const r = resultFixture().routes[0]!; r.checkpoints[1]!.risk.final_risk = 'UNKNOWN'; r.checkpoints[2]!.risk.final_risk = 'NO_TRAVEL'; const p = prepareRoute(r); expect(p.segments.map(s => [s.start, s.end])).toEqual([[0, 5], [5, 15], [15, 21.5], [21.5, 23]]); expect(p.segments.map(s => s.pattern)).toEqual([false, true, true, false]); });
  it('rejects missing or invalid geometry and coordinates safely', () => { for (const geometry of [undefined, null, [], [null, [0, 0]], [[NaN, 0], [0, 0]], [[181, 0], [0, 0]]]) { const r = resultFixture().routes[0]!; Object.assign(r, { geometry }); expect(prepareRoute(r).valid).toBe(false); expect(prepareRoute(r).segments[0]!.coordinates).toEqual([]); } expect(validPosition(undefined)).toBe(false); expect(validPosition([false, 0])).toBe(false); });
});
it.each(LEVELS)('%s encoding and tooltip preserve API risk', level => { const info = markerEncoding(level), cp = resultFixture().routes[0]!.checkpoints[0]!; cp.risk.final_risk = level; expect(info.shape).toBeTruthy(); expect(info.size).toBeGreaterThanOrEqual(12); expect(info.collision).toBe(['LOW', 'MODERATE'].includes(level)); expect(tooltipContent(cp).risk.toLowerCase().replace(' ', '_')).toBe(level.toLowerCase()); });
it('UNKNOWN tooltip includes unavailable reason and explicit UTC', () => { const cp = resultFixture().routes[0]!.checkpoints[0]!; cp.risk.final_risk = 'UNKNOWN'; cp.weather.unavailable_reason = 'OUT_OF_HORIZON'; cp.utc_fallback = true; expect(tooltipContent(cp).unavailable).toBe('out of horizon'); expect(tooltipContent(cp).title).toContain('UTC'); });
it('Low thinning is deterministic and switches at zoom 7', () => { expect([0, 1, 4, 5].map(i => visibleLow(i, 6))).toEqual([true, false, true, false]); expect(visibleLow(5, 7)).toBe(true); });
it.each([0, 200, 400])('mobile padding tracks sheet height %s', sheet => { expect(cameraPadding(320, 740, 0, sheet).bottom).toBe(112 + sheet); });
it('desktop padding includes console and degenerate bounds have span', () => { expect(cameraPadding(1440, 900, 420).left).toBe(444); expect(bounds([[1, 1]])).toEqual([[.9975, .9975], [1.0025, 1.0025]]); expect(bounds([])).toBeNull(); });
it('chip collisions prefer selected, with deterministic remaining order', () => { expect([...placeChips([{ id: 'a', x: 100, y: 100, selected: false }, { id: 'b', x: 110, y: 100, selected: true }, { id: 'c', x: 400, y: 100, selected: false }])]).toEqual(['b', 'c']); });
it('basemap transformation retains sources and recolors both themes', () => { const original = offlineStyle('light'); const dark = transformStyle(original, 'dark'); expect(dark.layers[0]!.paint).toEqual({ 'background-color': '#101c25' }); expect(original.layers[0]!.paint).toEqual({ 'background-color': '#f6f3eb' }); expect(dark.sources).toEqual(original.sources); });
it('quiet basemap removes icon-image instead of leaving an invalid undefined value', () => {
  const style = offlineStyle('light'); style.layers.push({ id: 'label_city', type: 'symbol', source: 'synthetic', layout: { 'text-field': 'City', 'icon-image': 'poi' } });
  const transformed = transformStyle(style, 'dark'); expect(transformed.layers[1]?.layout).not.toHaveProperty('icon-image'); expect(style.layers[1]?.layout).toHaveProperty('icon-image', 'poi');
});
it('attributions retain exact source text, remove duplicates and sanitize links', () => { const a = resultFixture().attributions; expect(attributionEntries(['A', 'A'], [...a, ...a]).html).toEqual(['A']); expect(attributionEntries([], [...a, ...a]).providers).toEqual(a); expect(creditParts('<a href="https://evil.test/">Credit</a>')[0]).toEqual({ text: 'Credit', href: undefined }); });
it('hover preserves the selection snapshot identity and incompatible checkpoint resets', () => { const store = createSelectionStore(); store.selectRoute('a'); store.selectCheckpoint(2); const snapshot = store.getSelection(); store.hoverRoute('b'); expect(store.getSelection()).toBe(snapshot); store.selectRoute('b'); expect(store.getState().selectedCheckpointIndex).toBeNull(); });
function Probe({ count }: { count: () => void }) { const selection = useSelection(); count(); return <span>{selection.selectedRouteId}</span>; }
it('hover does not render subscribed React selectors', () => { const store = createSelectionStore(), count = vi.fn(); render(<SelectionProvider value={store}><Probe count={count} /></SelectionProvider>); const initial = count.mock.calls.length; act(() => store.hoverRoute('a')); expect(count).toHaveBeenCalledTimes(initial); act(() => store.selectRoute('a')); expect(count.mock.calls.length).toBeGreaterThan(initial); });
it('StrictMode initializes one engine; controls, map events, theme and cleanup synchronize', async () => {
  const fake = new FakeEngine(), factory = vi.fn(() => fake), store = createSelectionStore(), analysis = resultFixture();
  const tree = render(<StrictMode><SelectionProvider value={store}><MapWorkspace analysis={analysis} factory={factory} /></SelectionProvider></StrictMode>);
  await waitFor(() => expect(factory).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(fake.calls.some(c => c.method === 'routes')).toBe(true));
  fireEvent.click(screen.getByRole('button', { name: 'Zoom in' })); fireEvent.click(screen.getByRole('button', { name: 'Recenter routes' }));
  act(() => fake.emit({ type: 'route', id: analysis.routes[1]!.route_id })); expect(store.getState().selectedRouteId).toBe(analysis.routes[1]!.route_id);
  act(() => fake.emit({ type: 'checkpoint', index: 1 })); expect(store.getState().selectedCheckpointIndex).toBe(1); await waitFor(() => expect(screen.getByRole('status').textContent).toContain('Checkpoint at mile'));
  act(() => { document.documentElement.dataset.theme = 'dark'; }); await waitFor(() => expect(fake.calls.some(c => c.method === 'theme')).toBe(true));
  expect(fake.calls.some(c => c.method === 'zoom')).toBe(true); expect(fake.calls.some(c => c.method === 'fit')).toBe(true);
  tree.unmount(); expect(fake.calls.filter(c => c.method === 'destroy')).toHaveLength(1);
});
it('style failure exposes retry while no WebGL retains a non-map alternative', async () => {
  const fake = new FakeEngine(), store = createSelectionStore(); render(<SelectionProvider value={store}><MapWorkspace analysis={null} factory={() => fake} /></SelectionProvider>);
  await waitFor(() => expect(screen.getByText('Plan a trip to see routes')).toBeTruthy()); act(() => fake.emit({ type: 'failure', reason: 'style failed to load' }));
  fireEvent.click(screen.getByRole('button', { name: 'Retry basemap' })); expect(fake.calls.some(c => c.method === 'retry')).toBe(true);
  act(() => fake.emit({ type: 'failure', reason: 'no WebGL' })); expect(screen.getByText('Map unavailable')).toBeTruthy(); expect(screen.getByText(/Routes and checkpoints remain/)).toBeTruthy();
});
it('checkpoint list buttons preserve order and synchronize selection', () => { const store = createSelectionStore(), route = resultFixture().routes[0]!; store.selectRoute(route.route_id); render(<SelectionProvider value={store}><CheckpointList route={route} /></SelectionProvider>); const buttons = screen.getAllByRole('button', { hidden: true }); fireEvent.click(buttons[2]!); expect(store.getState().selectedCheckpointIndex).toBe(2); expect(buttons[2]!.getAttribute('aria-pressed')).toBe('true'); expect(screen.getByText('Checkpoints · 4').parentElement?.getAttribute('open')).not.toBeNull(); fireEvent.focus(buttons[1]!); expect(store.getState().selectedCheckpointIndex).toBe(1); });

it('overlapping routes keep both neutral traces outside the selected casing', () => { for (const selected of [0, 1, 2]) expect([0, 1, 2].map(i => routeOffset(i, selected)).sort((a, b) => a - b)).toEqual([-7, 0, 7]); });
it('floating chips cannot cover a critical checkpoint halo', () => { expect(chipAvoidsPoints(100, 100, 176, 44, [{ x: 180, y: 90 }])).toBe(false); expect(chipAvoidsPoints(100, 60, 176, 44, [{ x: 180, y: 90 }])).toBe(true); });
it('chips hide instead of clipping at viewport edges or covering chart controls', () => { const viewport = { left: 0, right: 320, top: 0, bottom: 844 }, chip = { left: 16, right: 192, top: 120, bottom: 164 }; expect(chipFits(chip, viewport, [])).toBe(true); expect(chipFits({ ...chip, right: 322 }, viewport, [])).toBe(false); expect(chipFits(chip, viewport, [{ left: 12, right: 142, top: 104, bottom: 148 }])).toBe(false); });

it('both map skip links reveal the accessible route console', () => { const skip = vi.fn(); render(<SelectionProvider value={createSelectionStore()}><MapWorkspace analysis={null} factory={() => new FakeEngine()} onSkipMap={skip} /></SelectionProvider>); fireEvent.click(screen.getByRole('link', { name: 'Skip map' })); fireEvent.click(screen.getByRole('link', { name: 'Skip map to route results' })); expect(skip).toHaveBeenCalledTimes(2); });
