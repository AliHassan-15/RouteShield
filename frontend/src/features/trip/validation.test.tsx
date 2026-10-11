import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { LoadControl } from './LoadControl';
import { aboveWeight, parseWeight } from './weight';
import { chosenTime, departureError, quickDeparture, resolveWall } from './time';
import { decodeDraft, encodeDraft, markAutoAttempt } from './url';
import { clearHistory, readHistory, readPreferences, rememberPlace, rememberTrip, savePreferences } from './storage';
import { distantEndpoints, validateDraft, validationFields } from './model';
import { FIXED_NOW, testDraft } from './test-fixtures';

afterEach(() => { cleanup(); vi.restoreAllMocks(); localStorage.clear(); history.replaceState(null, '', '/'); });
test.each(['0', '30,000', '30000.01', '100000', '100,000.000', '45,000.500'])('preserves ordinary weight %s', value => {
  expect(parseWeight(value)?.token).toBe(value.replaceAll(',', ''));
});
test('rejects invalid grouping, non-numbers, exponents and weights above the exact limit', () => {
  for (const value of [true, false, 1, '1e4', '-1', 'NaN', 'Infinity', '30,00', '100000.01', '100000.0000000000000001', '100001', '', '1.', '1,000,00']) expect(parseWeight(value)).toBeNull();
  expect(aboveWeight(parseWeight('30000.0000000000000001'), 30000)).toBe(true);
});
test.each([['30000', 1], ['30001', 2], ['40000', 2], ['40001', 3]] as const)('display-only wind rules respect strict weight cutoff at %s', (value, count) => {
  render(<LoadControl value={value} onChange={() => {}} />);
  expect(screen.getByLabelText('Wind rules for current cargo weight').querySelectorAll('.wind-helper-current p')).toHaveLength(count);
  expect(document.querySelectorAll('.threshold-tick.is-active')).toHaveLength(count - 1);
});
test.each([
  ['normal', '2026-10-11', '15:00', 'UTC', 'valid', ['2026-10-11T15:00:00+00:00']],
  ['gap', '2026-03-08', '02:30', 'America/New_York', 'gap', []],
  ['fold', '2026-11-01', '01:30', 'America/New_York', 'ambiguous', ['2026-11-01T01:30:00-04:00', '2026-11-01T01:30:00-05:00']],
  ['half-hour', '2026-10-11', '15:00', 'Asia/Kolkata', 'valid', ['2026-10-11T15:00:00+05:30']],
] as const)('resolves %s wall time with actual Intl offsets', (_name, date, time, zone, kind, isos) => {
  const result = resolveWall({ date, time }, zone);
  expect(result.kind).toBe(kind); expect(result.choices.map(c => c.iso)).toEqual(isos);
  if (kind === 'gap') expect(result.fix).toEqual({ date, time: '03:00' });
  if (kind === 'ambiguous') { expect(chosenTime(result, null)).toBeNull(); expect(chosenTime(result, -300)?.iso).toContain('-05:00'); }
});
test('validates real calendar dates, inclusive grace and seven days, and sensible quick times', () => {
  expect(resolveWall({ date: '2026-02-30', time: '00:00' }, 'UTC').kind).toBe('invalid');
  const choice = { instant: FIXED_NOW, iso: '', offsetMinutes: 0 };
  expect(departureError({ ...choice, instant: FIXED_NOW - 300000 }, FIXED_NOW, 'UTC')).toBeNull();
  expect(departureError({ ...choice, instant: FIXED_NOW - 300001 }, FIXED_NOW, 'UTC')).toContain('past');
  expect(departureError({ ...choice, instant: FIXED_NOW + 7 * 86400000 }, FIXED_NOW, 'UTC')).toBeNull();
  expect(departureError({ ...choice, instant: FIXED_NOW + 7 * 86400000 + 1 }, FIXED_NOW, 'UTC')).toContain('Latest allowed');
  expect(quickDeparture('default', FIXED_NOW + 1, 'UTC').time).toBe('14:15');
  expect(quickDeparture('one', FIXED_NOW, 'UTC').time).toBe('13:00');
  expect(quickDeparture('three', FIXED_NOW, 'UTC').time).toBe('15:00');
  expect(quickDeparture('tomorrow', FIXED_NOW, 'UTC')).toEqual({ date: '2026-10-12', time: '06:00' });
});
test('Auto omits spacing, text-only locations fail, and API fields map to fixed messages', () => {
  const draft = testDraft(); expect(validateDraft(draft, FIXED_NOW).request).not.toHaveProperty('checkpoint_interval_miles');
  expect(validateDraft({ ...draft, spacing: '10' }, FIXED_NOW).request?.checkpoint_interval_miles).toBe(10);
  expect(validateDraft({ ...draft, origin: { text: 'Chicago', place: null } }, FIXED_NOW).errors.origin).toBe('Select a location with coordinates.');
  expect(Object.keys(validationFields({ 'origin.latitude': 'RAW_URL', destination: 'raw', departure_time: 'raw', load_weight_lb: 'raw', checkpoint_interval_miles: 'raw' }))).toEqual(['origin', 'destination', 'departure', 'weight', 'spacing']);
  expect(distantEndpoints(draft.origin.place, draft.destination.place)).toBe(false);
  const distant = { label: 'Los Angeles', latitude: 34, longitude: -118 };
  expect(distantEndpoints(draft.origin.place, distant)).toBe(true);
  expect(validateDraft({ ...draft, destination: { text: distant.label, place: distant } }, FIXED_NOW).request).not.toBeNull();
});
test('URL round-trip preserves decimals and the instant while displaying the receiving browser zone', () => {
  const draft = { ...testDraft(), weight: '30000.0100', spacing: '25' as const };
  const result = decodeDraft('?' + encodeDraft(draft), { ...testDraft(), zone: 'Asia/Karachi' }, FIXED_NOW);
  expect(result.complete).toBe(true); expect(result.draft.wall.time).toBe('20:00'); expect(result.draft.zone).toBe('Asia/Karachi'); expect(result.draft.weight).toBe('30000.0100');
  expect(validateDraft(result.draft, FIXED_NOW).choice?.instant).toBe(FIXED_NOW + 3 * 3600000);
});
test('defensive URL parsing ignores hostile, duplicated, oversized and mismatched offset values', () => {
  const base = testDraft();
  for (const search of ['?v=2', '?v=1&v=1', '?v=1&from=999,0,Place&w=1e9', '?v=1&dep=2026-10-11T15%3A00%3A00%2B05%3A00&tz=UTC', '?v=1&x=' + 'a'.repeat(2100)]) expect(decodeDraft(search, base, FIXED_NOW).complete).toBe(false);
});
test('past links prefill without autorun and attempted entries suppress reload loops', () => {
  const draft = testDraft(); const result = decodeDraft('?' + encodeDraft(draft), draft, FIXED_NOW + 4 * 3600000);
  expect(result.past).toBe(true); expect(result.draft.wall).toEqual(draft.wall);
  expect(markAutoAttempt(draft)).toBe(true); expect(markAutoAttempt(draft)).toBe(false);
});
test('recents cap at five, deduplicate, strip provider data and clear all trip storage', () => {
  let state = readHistory();
  for (let i = 0; i < 7; i++) { const draft = testDraft(); draft.origin = { text: `Place ${i}`, place: { label: `Place ${i}`, latitude: i, longitude: 0, provider: 'private-provider' } }; state = rememberPlace(state, draft.origin.place!); state = rememberTrip(state, draft); }
  expect(state.places).toHaveLength(5); expect(state.trips).toHaveLength(5); expect(state.places[0]?.label).toBe('Place 6'); expect(JSON.stringify(state)).not.toContain('private-provider');
  state = rememberPlace(state, state.places[0]!); expect(state.places).toHaveLength(5);
  savePreferences('45000.5', '50'); expect(readPreferences()).toEqual({ weight: '45000.5', spacing: '50' });
  expect(localStorage.getItem('routeshield-trip-preferences-v1')).not.toMatch(/departure|wall|zone/);
  expect(clearHistory()).toEqual({ places: [], trips: [] }); expect(localStorage.length).toBe(0);
});
test('blocked, full or malformed storage never prevents planning', () => {
  localStorage.setItem('routeshield-trip-history-v1', '{malformed'); expect(readHistory().places).toEqual([]);
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('full'); });
  vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => { throw new Error('blocked'); });
  expect(readPreferences().weight).toBe('45000'); expect(() => savePreferences('0', 'auto')).not.toThrow(); expect(() => clearHistory()).not.toThrow();
});
