import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { ARRIVAL, arrivalFor, arrivalFrame, createArrival, finishArrival } from './arrival';
import { CountMetric } from '../features/results/ResultsView';
import { FakeEngine } from '../features/map/fake-engine';
import { resultFixture } from '../features/results/fixtures';

beforeEach(() => { vi.useFakeTimers(); finishArrival(); vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener() {}, removeEventListener() {} })); });
afterEach(() => { cleanup(); finishArrival(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
test.each([0, 100, 300, 940, 1100, 1400, 1440, 1640, 1800])('shared fake-engine timeline at %d ms', ms => {
  const response = resultFixture(), timeline = arrivalFor(response), engine = new FakeEngine(); engine.setRoutes(response);
  act(() => vi.advanceTimersByTime(ms));
  expect(engine.inspectArrival()).toEqual(arrivalFrame(ms));
  expect(timeline.done()).toBe(ms === ARRIVAL.end);
  const frame = engine.inspectArrival();
  if (ms < 940) expect(frame.checkpoints).toBe(0);
  if (ms < 1100) expect(frame.heat).toBe(0);
  if (ms < 1440) expect(frame.chips).toBe(0);
});
test('selection cancellation finishes every phase once with no late callback', () => {
  const timeline = createArrival(false), listener = vi.fn(); timeline.subscribe(listener);
  vi.advanceTimersByTime(300); timeline.finish(); timeline.finish(); vi.runAllTimers();
  expect(listener).toHaveBeenCalledTimes(1); expect(arrivalFrame(timeline.elapsed()).chips).toBe(1);
});
test('replacement during entrance finishes both and returning to an analysis never replays', () => {
  const a = {}, b = {}, first = arrivalFor(a); vi.advanceTimersByTime(150); const second = arrivalFor(b);
  expect(first.done()).toBe(true); expect(second.done()).toBe(true); expect(arrivalFor(a)).toBe(first);
});
test('reduced motion immediately exposes final phases', () => {
  vi.stubGlobal('matchMedia', () => ({ matches: true })); const timeline = arrivalFor({});
  expect(timeline.done()).toBe(true); expect(arrivalFrame(timeline.elapsed())).toEqual({ routes: [1, 1, 1], checkpoints: 1, heat: 1, chips: 1 });
});
test.each(['rerender', 'selection', 'tab', 'theme', 'subview'])('count-up stays settled after %s', action => {
  const analysis = {}, props = { analysis, value: '123', format: (v: unknown) => Number(v).toFixed(0) };
  const tree = render(<CountMetric {...props} />); act(() => vi.advanceTimersByTime(600));
  expect(document.querySelector('.metric-animated')?.textContent).toBe('123');
  if (action === 'tab' || action === 'subview') { tree.unmount(); render(<CountMetric {...props} />); }
  else tree.rerender(<div data-action={action}><CountMetric {...props} /></div>);
  expect(document.querySelector('.metric-animated')?.textContent).toBe('123'); expect(screen.getByText('123', { selector: '.sr-only' })).toBeTruthy();
});
test('count-up cancels immediately with the entrance', () => {
  const analysis = {}; render(<CountMetric analysis={analysis} value="123" format={v => Number(v).toFixed(0)} />);
  act(() => { vi.advanceTimersByTime(100); finishArrival(); }); expect(document.querySelector('.metric-animated')?.textContent).toBe('123');
});
test('CSS changes no interactive layout properties and only skeleton shimmer loops', () => {
  const css = ['styles/motion.css', 'features/trip/trip.css', 'features/results/results.css', 'features/map/map.css', 'features/checkpoints/checkpoints.css', 'features/heatmap/heatmap.css'].map(p => readFileSync(`src/${p}`, 'utf8')).join('\n');
  expect(css).not.toMatch(/transition:\s*(?:all|width|height|top|left|margin|box-shadow)/);
  expect(css.match(/animation:[^;]*infinite/g)).toEqual(['animation: shimmer 1.8s ease-in-out infinite']);
  expect(css).toContain('.map-route-chip.maplibregl-marker { transition: none; }');
});
test('production guard rejects test motion switches and every debug hook family', () => {
  const guard = readFileSync('scripts/verify-build.mjs', 'utf8');
  for (const name of ['MOTION_TEST_ONLY', 'VITE_MOTION_DISABLED', 'Audit']) expect(guard).toContain(name);
});
test('one development switch disables JS motion and injects static CSS', async () => {
  vi.stubEnv('VITE_E2E', 'true'); vi.stubEnv('VITE_MOTION_DISABLED', 'true'); vi.resetModules();
  const { motionOff } = await import('./motion'); expect(motionOff()).toBe(true);
  const style = [...document.querySelectorAll('style')].find(s => s.textContent.includes('MOTION_TEST_ONLY')); expect(style).toBeTruthy(); style?.remove();
});
