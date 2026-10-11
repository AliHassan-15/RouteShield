import type { SelectedPlace } from '../../api/types';
import { URL_LIMIT } from './config';
import { isPlace, validateDraft } from './model';
import type { Spacing, TripDraft } from './model';
import { parseOffsetInstant, resolveWall, wallAt } from './time';
import { parseWeight } from './weight';

function place(value: string | null): SelectedPlace | null {
  if (!value || value.length > 250) return null;
  const [lat, lon, ...label] = value.split(',');
  if (!lat || !lon || !/^-?\d+(?:\.\d+)?$/.test(lat) || !/^-?\d+(?:\.\d+)?$/.test(lon)) return null;
  const result = { latitude: Number(lat), longitude: Number(lon), label: label.join(',').trim() };
  return isPlace(result) ? result : null;
}
export function encodeDraft(draft: TripDraft): string {
  const params = new URLSearchParams({ v: '1', w: draft.weight, step: draft.spacing });
  for (const field of ['origin', 'destination'] as const) {
    const p = draft[field].place;
    if (p) params.set(field === 'origin' ? 'from' : 'to', `${p.latitude},${p.longitude},${p.label}`);
  }
  const resolution = resolveWall(draft.wall, draft.zone), choice = resolution.choices.find(c => c.offsetMinutes === draft.offset) ?? (resolution.kind === 'valid' ? resolution.choices[0] : undefined);
  if (choice) { params.set('dep', choice.iso); params.set('tz', draft.zone); }
  return params.toString();
}
export function decodeDraft(search: string, base: TripDraft, now: number) {
  const draft: TripDraft = { ...base };
  if (!search || search.length > URL_LIMIT) return { draft, complete: false, past: false };
  const params = new URLSearchParams(search);
  if (params.get('v') !== '1' || [...params.keys()].some(key => params.getAll(key).length !== 1)) return { draft, complete: false, past: false };
  const from = place(params.get('from')), to = place(params.get('to'));
  if (from) draft.origin = { text: from.label, place: from };
  if (to) draft.destination = { text: to.label, place: to };
  const weight = params.get('w'), step = params.get('step');
  if (weight && parseWeight(weight)) draft.weight = weight;
  if (step && ['auto', '10', '25', '50'].includes(step)) draft.spacing = step as Spacing;
  const departure = params.get('dep'), zone = params.get('tz');
  const choice = departure && zone && zone.length < 100 && departure.length < 50 ? parseOffsetInstant(departure, zone) : null;
  if (choice) {
    // A shared instant is displayed in THIS browser's zone, not the sender's/origin's.
    draft.wall = wallAt(choice.instant, base.zone);
    draft.offset = resolveWall(draft.wall, base.zone).choices.find(c => c.instant === choice.instant)?.offsetMinutes ?? null;
  }
  const valid = !!validateDraft(draft, now).request;
  const complete = !!from && !!to && !!choice && !!weight && !!parseWeight(weight) && !!step && ['auto', '10', '25', '50'].includes(step) && valid;
  return { draft, complete, past: !!choice && choice.instant <= now };
}
export function updateUrl(draft: TripDraft, submitted = false) {
  const encoded = encodeDraft(draft);
  try {
    const state = typeof history.state === 'object' && history.state !== null ? history.state : {};
    const next = submitted ? { ...state, routeShieldAttempt: encoded } : state;
    history[submitted ? 'pushState' : 'replaceState'](next, '', `${location.pathname}?${encoded}${location.hash}`);
  } catch { /* Disabled/limited history never blocks explicit submission. */ }
}
export function markAutoAttempt(draft: TripDraft): boolean {
  const encoded = encodeDraft(draft);
  try {
    if (history.state?.routeShieldAttempt === encoded) return false;
    const state = typeof history.state === 'object' && history.state !== null ? history.state : {};
    history.replaceState({ ...state, routeShieldAttempt: encoded }, '', location.href);
  } catch { /* The controller's ref still guards StrictMode when history is denied. */ }
  return true;
}
