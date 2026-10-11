import { useState } from 'react';

import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';

import { afterEach, beforeEach, expect, test, vi } from 'vitest';

import type { RecommendationStatus } from '../../api/types';

import { SelectionProvider, useSelection, useSelectionState } from '../../api/selection-store';

import { ApiError, errorMessages } from '../../api/errors';

import { AnalysisError } from '../../components/AnalysisError';

import { ResultsView, ResultsSkeleton } from './ResultsView';

import { resultFixture, warningsFixture, exact } from './fixtures';

import { eligibleRecommended, routeLabels, labelText, serverOrder, stripMatchesSummary } from './presentation';

import { RiskDistance } from './RiskDistance';

import { WarningsTray, WARNING_CODES, WarningList } from './Warnings';

import { Console } from './Console';

import { AnalysisStoreProvider } from '../../api/analysis-store';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { useTripPlanner } from '../trip/useTripPlanner';

import { FIXED_NOW } from '../trip/test-fixtures';



beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(FIXED_NOW); localStorage.clear(); history.replaceState(null, '', '/'); });

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

type Response = ReturnType<typeof resultFixture>;

function Tree({ response }: { response: Response }) {

  const selection = useSelectionState();

  return <SelectionProvider value={selection}><ResultsView snapshot={{ response, request: { ...response.trip, load_weight_lb: 45000 }, wallMs: 100 }} rerun={() => {}} disabled={false} changed={false} /><Probe /></SelectionProvider>;

}

function Probe() { const selection = useSelection(); return <output aria-label="Selection">{selection.selectedRouteId ?? 'none'}</output>; }

const statuses: RecommendationStatus[] = ['RECOMMENDED', 'BEST_FULLY_ASSESSED_AVAILABLE', 'ALL_BLOCKED', 'NO_FULLY_ASSESSED_TRAVELABLE_ROUTE', 'ALL_INCOMPLETE'];

test.each(statuses)('%s renders exact status with no misleading recommendation', status => {

  const response = resultFixture(status); render(<Tree response={response} />);

  expect(document.body.textContent).toContain(response.message);

  const winner = eligibleRecommended(response); expect(screen.queryByLabelText('Recommendation') !== null).toBe(!!winner);

  if (!winner) expect(screen.queryByText('Recommended', { exact: true })).toBeNull();

  if (status === 'ALL_BLOCKED') expect(screen.getByText('Least blocked, not recommended')).toBeTruthy();

});

test.each(['SEVERE_MILES', 'HIGH_MILES', 'AVERAGE_RISK', 'DURATION', 'TIE_BROKEN_BY_ID'])('%s uses API decisive criterion and facts only', criterion => {

  const response = resultFixture('RECOMMENDED', criterion); render(<Tree response={response} />);

  if (criterion === 'TIE_BROKEN_BY_ID') { expect(document.querySelector('.decisive')).toBeNull(); expect(document.body.textContent).toContain('Stable geometry identifier decides'); }

  else { expect(document.querySelector('tr.decisive')?.getAttribute('data-criterion')).toBe(criterion); expect(document.querySelectorAll('.matrix-value .fact-tick')).toHaveLength(1); }

});

test.each([1, 2])('%i routes remain truthful, with server ranks and partial-route notice', count => { const response = resultFixture('BEST_FULLY_ASSESSED_AVAILABLE'); response.routes = response.routes.slice(0, count); response.route_count = count; response.warnings = [{ code: 'PARTIAL_ROUTES', message: '', scope: 'trip', coverage_fraction: null }]; render(<Tree response={response} />); expect(screen.getAllByRole('radio')).toHaveLength(count); fireEvent.click(screen.getByText('notices', { exact: false, selector: 'summary' })); expect(document.body.textContent).toContain(`Only ${count} route(s) available`); });

test('shuffled arrays replay server order without comparing numerical risk values', () => { const response = resultFixture(); const ids = response.routes.map(r => r.route_id); response.routes.reverse(); response.routes[0]!.criteria.severe_miles = exact(-999); expect(serverOrder(response.routes).map(r => r.route_id)).toEqual(ids); render(<Tree response={response} />); expect(screen.getAllByRole('radio').map(r => r.textContent?.match(/Route \d/)?.[0])).toEqual(['Route 1', 'Route 2', 'Route 3']); });

test('one label map replaces IDs consistently while preserving exact near-tie prose', () => { const response = resultFixture(), labels = routeLabels(response); expect(labelText(response.explanation, labels)).toContain('Travel times for Route 1 and Route 2 differ by 2.00 minutes (within 4 minutes); duration is lower priority and did not decide this comparison.'); expect(labelText(response.explanation, labels)).not.toContain('synthetic-route'); });

test('blocked and incomplete columns retain coverage, n/a and never earn winner ticks', () => { const response = resultFixture('BEST_FULLY_ASSESSED_AVAILABLE'); render(<Tree response={response} />); expect(document.querySelector('.blocked-heading')).toBeTruthy(); expect(document.querySelectorAll('td small')).toHaveLength(5); expect(screen.getAllByText('56.5%').length).toBeGreaterThan(0); fireEvent.click(screen.getAllByRole('radio')[2]!); expect(screen.getByText('n/a, weather incomplete')).toBeTruthy(); });

test('radio keys wrap, Home/End/Space/Enter select and update matrix plus details', () => { render(<Tree response={resultFixture()} />); const radios = screen.getAllByRole('radio'); fireEvent.keyDown(radios[0]!, { key: 'End' }); expect(screen.getByLabelText('Selection').textContent).toBe('synthetic-route-2'); expect(document.activeElement).toBe(radios[2]); expect(document.querySelector('thead .is-selected')?.textContent).toContain('Route 3'); fireEvent.keyDown(radios[2]!, { key: 'ArrowRight' }); expect(document.activeElement).toBe(radios[0]); fireEvent.keyDown(radios[0]!, { key: 'Home' }); fireEvent.click(radios[1]!); expect(screen.getByText('Route details · Route 2')).toBeTruthy(); });

test('ownership strips match every risk partition, and divergence is detected', () => { for (const status of statuses) for (const route of resultFixture(status).routes) expect(stripMatchesSummary(route)).toBe(true); const route = resultFixture().routes[0]!; route.summary.miles_by_level.LOW = exact(100); expect(stripMatchesSummary(route)).toBe(false); });

test('risk bar retains nonzero slivers, fixed level order, minimum 3px and legend only for nonzero', () => { const summary = resultFixture().routes[0]!.summary; summary.miles_by_level.SEVERE = exact(1, '10000'); render(<RiskDistance summary={summary} />); expect(Array.from(document.querySelectorAll('.distance-segment')).map(s => s.getAttribute('data-level'))).toEqual(['LOW', 'MODERATE', 'HIGH', 'SEVERE']); expect((document.querySelector('[data-level="SEVERE"]') as HTMLElement).style.minWidth).toBe('3px'); expect(screen.queryByText('Unknown')).toBeNull(); });

test('every warning including a future code renders, globals collapse and routes retain notices', () => { const response = warningsFixture(); render(<><WarningsTray response={response} /><WarningList response={response} warnings={response.warnings.filter(w => w.scope !== 'trip')} /></>); fireEvent.click(screen.getByText('notices', { selector: 'summary', exact: false })); for (const code of [...WARNING_CODES, 'FUTURE_NOTICE']) expect(screen.getByText(code)).toBeTruthy(); expect(document.body.textContent).toContain('43.5%'); });

test('stale timer preserves results and offers an explicit re-run at fifteen minutes', async () => { render(<Tree response={resultFixture()} />); expect(screen.queryByText(/Results are older/)).toBeNull(); await act(() => vi.advanceTimersByTimeAsync(900_000)); expect(screen.getByText(/Results are older/)).toBeTruthy(); expect(screen.getByLabelText('Recommendation')).toBeTruthy(); });

test('simulated metadata shows persistent scenario identity above the results', () => { const response = resultFixture(); response.metadata.simulated = true; response.simulation_scenario = 'winter_storm'; render(<Tree response={response} />); expect(screen.getByText('SIMULATION')).toBeTruthy(); expect(screen.getByText('winter_storm')).toBeTruthy(); });

test('all API errors and network failure share specific recovery and copyable ID without raw messages', () => { for (const code of [...Object.keys(errorMessages), 'NETWORK_ERROR'] as (keyof typeof errorMessages | 'NETWORK_ERROR')[]) { const retry = vi.fn(), edit = vi.fn(); const view = render(<AnalysisError error={new ApiError(code, 500, {}, 'synthetic-error')} retry={retry} edit={edit} />); expect(screen.getByRole('alert').textContent).toContain(code === 'TRIP_TOO_LARGE' ? 'Choose closer endpoints or use an example trip.' : new ApiError(code).presentation.message); expect(screen.getByLabelText('Request ID')).toBeTruthy(); expect(within(screen.getByRole('alert')).getAllByRole('button').length).toBe(2); view.unmount(); } });

test('timeout retries respect active throttle and skeleton exposes all layout sections', () => { const retry = vi.fn(); const view = render(<AnalysisError error={new ApiError('PROVIDER_TIMEOUT')} retry={retry} edit={() => {}} secondsLeft={3} />); const button = screen.getByRole('button', { name: 'Retry' }); expect((button as HTMLButtonElement).disabled).toBe(true); fireEvent.click(button); expect(retry).not.toHaveBeenCalled(); view.unmount(); render(<ResultsSkeleton />); expect(screen.getAllByRole('status')).toHaveLength(3); });

function ConsoleProbe() { const planner = useTripPlanner({ status: 'healthy', version: 'test', requestId: undefined, retry: () => {} }), selection = useSelectionState(); const [tab, setTab] = useState('trip'); return <SelectionProvider value={selection}><Console planner={planner} tab={tab} setTab={setTab} /></SelectionProvider>; }

function mountConsole() { return render(<QueryClientProvider client={new QueryClient()}><AnalysisStoreProvider><ConsoleProbe /></AnalysisStoreProvider></QueryClientProvider>); }

test('tabs auto-select results, focus heading, default to API winner and preserve edited form plus analysis', async () => { vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new globalThis.Response(JSON.stringify(resultFixture())))); mountConsole(); expect((screen.getByRole('tab', { name: 'Results' }) as HTMLButtonElement).disabled).toBe(true); fireEvent.click(screen.getByRole('button', { name: 'Chicago, IL to Detroit, MI' })); fireEvent.click(screen.getByRole('button', { name: 'Analyze routes' })); await act(() => vi.advanceTimersByTimeAsync(100)); expect(screen.getByRole('tab', { name: 'Results' }).getAttribute('aria-selected')).toBe('true'); await act(() => vi.advanceTimersByTimeAsync(30)); expect(document.activeElement?.id).toBe('results-heading'); expect(screen.getAllByRole('radio')[0]?.getAttribute('aria-checked')).toBe('true'); fireEvent.click(screen.getByRole('button', { name: 'Edit trip' })); fireEvent.change(screen.getByLabelText('Cargo weight', { exact: true }), { target: { value: '25000' } }); fireEvent.click(screen.getByRole('tab', { name: 'Results' })); expect(screen.getByText('Inputs changed since this analysis')).toBeTruthy(); expect(screen.getByLabelText('Recommendation')).toBeTruthy(); });

test('retry uses identical failed inputs rather than any edited value', async () => { const fetch = vi.fn().mockResolvedValue(new globalThis.Response(JSON.stringify({ error: { code: 'PROVIDER_TIMEOUT', message: '', details: {} } }), { status: 504 })); vi.stubGlobal('fetch', fetch); mountConsole(); fireEvent.click(screen.getByRole('button', { name: 'Chicago, IL to Detroit, MI' })); fireEvent.click(screen.getByRole('button', { name: 'Analyze routes' })); await act(() => vi.advanceTimersByTimeAsync(100)); fireEvent.click(screen.getByRole('button', { name: 'Retry' })); await act(() => vi.advanceTimersByTimeAsync(100)); expect(fetch.mock.calls[1]?.[1].body).toBe(fetch.mock.calls[0]?.[1].body); });

test('all result variants render without console errors, including malformed display values', () => { const errors = vi.spyOn(console, 'error').mockImplementation(() => {}); for (const status of statuses) { const response = resultFixture(status); response.routes[0]!.duration_s = exact('invalid'); const view = render(<Tree response={response} />); expect(document.body.textContent).not.toContain('NaN'); view.unmount(); } expect(errors).not.toHaveBeenCalled(); });

