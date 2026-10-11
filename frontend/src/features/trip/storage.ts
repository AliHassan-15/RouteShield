import type { SelectedPlace } from '../../api/types';
import { isPlace } from './model';
import type { Spacing, TripDraft } from './model';
import { parseWeight } from './weight';

const PREFS = 'routeshield-trip-preferences-v1', HISTORY = 'routeshield-trip-history-v1';
export interface RecentTrip { origin: SelectedPlace; destination: SelectedPlace; weight: string; spacing: Spacing }
export interface LocalHistory { places: SelectedPlace[]; trips: RecentTrip[] }
const spacing = (value: unknown): value is Spacing => value === 'auto' || value === '10' || value === '25' || value === '50';
function read(key: string): unknown { try { const raw = localStorage.getItem(key); return raw && raw.length <= 20_000 ? JSON.parse(raw) : null; } catch { return null; } }
function write(key: string, value: unknown) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* Blocked/full storage cannot prevent trip planning. */ } }
function record(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null; }
export function readPreferences(): { weight: string; spacing: Spacing } {
  const value = read(PREFS);
  return { weight: record(value) && parseWeight(value.weight) ? value.weight as string : '45000', spacing: record(value) && spacing(value.spacing) ? value.spacing : 'auto' };
}
export function savePreferences(weight: string, interval: Spacing) { if (parseWeight(weight) && spacing(interval)) write(PREFS, { weight, spacing: interval }); }
function localPlace(place: SelectedPlace): SelectedPlace { return { label: place.label, latitude: place.latitude, longitude: place.longitude }; }
function samePlace(a: SelectedPlace, b: SelectedPlace) { return a.label === b.label && a.latitude === b.latitude && a.longitude === b.longitude; }
export function readHistory(): LocalHistory {
  const value = read(HISTORY);
  if (!record(value)) return { places: [], trips: [] };
  const places = Array.isArray(value.places) ? value.places.filter(isPlace).slice(0, 5).map(localPlace) : [];
  const trips: RecentTrip[] = [];
  if (Array.isArray(value.trips)) for (const trip of value.trips.slice(0, 5)) if (record(trip) && isPlace(trip.origin) && isPlace(trip.destination) && parseWeight(trip.weight) && spacing(trip.spacing)) trips.push({ origin: localPlace(trip.origin), destination: localPlace(trip.destination), weight: trip.weight as string, spacing: trip.spacing });
  return { places, trips };
}
export function rememberPlace(history: LocalHistory, place: SelectedPlace): LocalHistory {
  const next = { ...history, places: [localPlace(place), ...history.places.filter(p => !samePlace(p, place))].slice(0, 5) };
  write(HISTORY, next); return next;
}
export function rememberTrip(history: LocalHistory, draft: TripDraft): LocalHistory {
  if (!draft.origin.place || !draft.destination.place) return history;
  const trip = { origin: localPlace(draft.origin.place), destination: localPlace(draft.destination.place), weight: draft.weight, spacing: draft.spacing };
  const next = { ...history, trips: [trip, ...history.trips.filter(t => !samePlace(t.origin, trip.origin) || !samePlace(t.destination, trip.destination) || t.weight !== trip.weight || t.spacing !== trip.spacing)].slice(0, 5) };
  write(HISTORY, next); return next;
}
export function clearHistory(): LocalHistory {
  for (const key of [PREFS, HISTORY]) try { localStorage.removeItem(key); } catch { /* Still clear the in-memory history. */ }
  return { places: [], trips: [] };
}
