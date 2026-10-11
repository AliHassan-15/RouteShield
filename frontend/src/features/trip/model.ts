import type { AnalysisRequest, ErrorValue, SelectedPlace } from '../../api/types';
import { LABEL_LIMIT, STRAIGHT_LINE_ADVISORY_MILES } from './config';
import { chosenTime, departureError, resolveWall } from './time';
import type { WallTime } from './time';
import { parseWeight } from './weight';

export type Spacing = 'auto' | '10' | '25' | '50';
export type PlaceChoice = SelectedPlace & { region?: string | null; country?: string | null };
export interface PlaceField { text: string; place: PlaceChoice | null }
export interface TripDraft { origin: PlaceField; destination: PlaceField; wall: WallTime; offset: number | null; zone: string; weight: string; spacing: Spacing }
export type FormField = 'origin' | 'destination' | 'departure' | 'weight' | 'spacing';
export type FieldErrors = Partial<Record<FormField, string>>;
export function isPlace(value: unknown): value is SelectedPlace {
  if (typeof value !== 'object' || value === null) return false;
  const place = value as Record<string, unknown>;
  return typeof place.label === 'string' && place.label.trim().length >= 2 && place.label.length <= LABEL_LIMIT && ![...place.label].some(c => c.charCodeAt(0) < 32 || c.charCodeAt(0) === 127) && typeof place.latitude === 'number' && typeof place.longitude === 'number' && Number.isFinite(place.latitude) && Number.isFinite(place.longitude) && Math.abs(place.latitude) <= 90 && Math.abs(place.longitude) <= 180;
}
export function projectPlace(place: SelectedPlace): SelectedPlace {
  return { label: place.label, latitude: place.latitude, longitude: place.longitude, ...(place.candidate_id ? { candidate_id: place.candidate_id } : {}), ...(place.provider ? { provider: place.provider } : {}), ...(place.attribution ? { attribution: place.attribution } : {}) };
}
export function validateDraft(draft: TripDraft, now: number) {
  const errors: FieldErrors = {}, time = resolveWall(draft.wall, draft.zone), choice = chosenTime(time, draft.offset), weight = parseWeight(draft.weight);
  for (const field of ['origin', 'destination'] as const) if (!isPlace(draft[field].place)) errors[field] = draft[field].text ? 'Select a location with coordinates.' : field === 'origin' ? 'Choose an origin.' : 'Choose a destination.';
  if (draft.origin.place && draft.destination.place && draft.origin.place.latitude === draft.destination.place.latitude && draft.origin.place.longitude === draft.destination.place.longitude) errors.destination = 'Choose different endpoints.';
  if (time.kind === 'invalid') errors.departure = 'Enter a valid departure date and time.';
  else if (time.kind === 'gap') errors.departure = 'This local time does not exist because the clocks move forward.';
  else if (!choice) errors.departure = 'This time occurs twice. Choose the earlier or later offset.';
  else { const error = departureError(choice, now, draft.zone); if (error) errors.departure = error; }
  if (!weight) errors.weight = 'Enter cargo weight from 0 to 100,000 lb using ordinary decimals.';
  if (!['auto', '10', '25', '50'].includes(draft.spacing)) errors.spacing = 'Choose Auto, 10, 25 or 50 miles.';
  const request: AnalysisRequest | null = Object.keys(errors).length || !draft.origin.place || !draft.destination.place || !choice || !weight ? null : { origin: projectPlace(draft.origin.place), destination: projectPlace(draft.destination.place), departure_time: choice.iso, departure_timezone: draft.zone, load_weight_lb: weight.numeric, ...(draft.spacing === 'auto' ? {} : { checkpoint_interval_miles: Number(draft.spacing) as 10 | 25 | 50 }) };
  return { errors, request, weightToken: weight?.token, time, choice };
}
/** Advisory geometry only; this never blocks submission or estimates road miles. */
export function distantEndpoints(a: SelectedPlace | null, b: SelectedPlace | null): boolean {
  if (!a || !b) return false;
  const radians = (n: number) => n * Math.PI / 180;
  const lat = radians(b.latitude - a.latitude), lon = radians(b.longitude - a.longitude);
  const haversine = Math.sin(lat / 2) ** 2 + Math.cos(radians(a.latitude)) * Math.cos(radians(b.latitude)) * Math.sin(lon / 2) ** 2;
  return 3958.7613 * 2 * Math.atan2(Math.sqrt(haversine), Math.sqrt(Math.max(0, 1 - haversine))) > STRAIGHT_LINE_ADVISORY_MILES;
}
export function validationFields(details: Record<string, ErrorValue>): FieldErrors {
  const errors: FieldErrors = {};
  for (const field of Object.keys(details)) {
    if (field === 'origin' || field.startsWith('origin.')) errors.origin = 'Select a location with valid coordinates.';
    if (field === 'destination' || field.startsWith('destination.')) errors.destination = 'Select a location with valid coordinates.';
    if (field === 'departure_time' || field === 'departure_timezone') errors.departure = 'Check the departure date, time and browser time zone.';
    if (field === 'load_weight_lb') errors.weight = 'Enter cargo weight from 0 to 100,000 lb using ordinary decimals.';
    if (field === 'checkpoint_interval_miles') errors.spacing = 'Choose Auto, 10, 25 or 50 miles.';
  }
  return errors;
}
