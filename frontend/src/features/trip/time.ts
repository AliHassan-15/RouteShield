import { DEPARTURE_WINDOW_MS, PAST_GRACE_MS } from './config';

export interface WallTime { date: string; time: string }
export interface TimeChoice { instant: number; offsetMinutes: number; iso: string }
export interface WallResolution { kind: 'valid' | 'ambiguous' | 'gap' | 'invalid'; choices: TimeChoice[]; fix?: WallTime }
const MINUTE = 60_000;
function formatter(zone: string) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
}
function parts(at: number, format: Intl.DateTimeFormat): WallTime {
  const values = Object.fromEntries(format.formatToParts(at).map(p => [p.type, p.value]));
  return { date: `${values.year}-${values.month}-${values.day}`, time: `${values.hour}:${values.minute}` };
}
function naive(wall: WallTime): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(wall.date) || !/^\d{2}:\d{2}$/.test(wall.time)) return null;
  const numbers = (wall.date + '-' + wall.time.replace(':', '-')).split('-').map(Number);
  const [year = 0, month = 0, day = 0, hour = 0, minute = 0] = numbers;
  if (year < 1900 || year > 2200 || month < 1 || month > 12 || day < 1 || hour > 23 || minute > 59) return null;
  const value = Date.UTC(year, month - 1, day, hour, minute);
  if (new Date(value).toISOString().slice(0, 16) !== wall.date + 'T' + wall.time) return null;
  return value;
}
export function offsetLabel(minutes: number): string {
  const absolute = Math.abs(minutes);
  return `${minutes < 0 ? '-' : '+'}${String(Math.floor(absolute / 60)).padStart(2, '0')}:${String(absolute % 60).padStart(2, '0')}`;
}
export function wallAt(instant: number, zone: string): WallTime { return parts(instant, formatter(zone)); }
export function browserZone(): string {
  try { const zone = Intl.DateTimeFormat().resolvedOptions().timeZone; formatter(zone).format(0); return zone; } catch { return 'UTC'; }
}
/** Enumerate actual zone offsets and round-trip candidates; never let Date guess a DST fold/gap. */
export function resolveWall(wall: WallTime, zone: string): WallResolution {
  const base = naive(wall);
  if (base === null) return { kind: 'invalid', choices: [] };
  let format: Intl.DateTimeFormat;
  try { format = formatter(zone); } catch { return { kind: 'invalid', choices: [] }; }
  const offsets = new Set<number>();
  for (let hours = -48; hours <= 48; hours += 6) {
    const instant = base + hours * 3_600_000, local = naive(parts(instant, format));
    if (local !== null) offsets.add((local - instant) / MINUTE);
  }
  const find = (candidate: WallTime, value: number): TimeChoice[] => [...offsets].map(offsetMinutes => {
    const instant = value - offsetMinutes * MINUTE, local = parts(instant, format);
    return local.date === candidate.date && local.time === candidate.time ? { instant, offsetMinutes, iso: `${candidate.date}T${candidate.time}:00${offsetLabel(offsetMinutes)}` } : null;
  }).filter((choice): choice is TimeChoice => choice !== null).sort((a, b) => a.instant - b.instant);
  const choices = find(wall, base);
  if (choices.length) return { kind: choices.length > 1 ? 'ambiguous' : 'valid', choices };
  // Covers a skipped civil day as well as ordinary one-hour/half-hour spring gaps.
  for (let minutes = 1; minutes <= 1440; minutes++) {
    const value = base + minutes * MINUTE, iso = new Date(value).toISOString();
    const fix = { date: iso.slice(0, 10), time: iso.slice(11, 16) };
    if (find(fix, value).length) return { kind: 'gap', choices: [], fix };
  }
  return { kind: 'invalid', choices: [] };
}
export function chosenTime(resolution: WallResolution, offset: number | null): TimeChoice | null {
  return resolution.kind === 'valid' ? resolution.choices[0] ?? null : resolution.kind === 'ambiguous' ? resolution.choices.find(c => c.offsetMinutes === offset) ?? null : null;
}
export function departureError(choice: TimeChoice | null, now: number, zone: string): string | null {
  if (!choice) return null;
  if (choice.instant < now - PAST_GRACE_MS) return 'Departure is more than five minutes in the past. Choose a later time.';
  if (choice.instant > now + DEPARTURE_WINDOW_MS) { const latest = wallAt(now + DEPARTURE_WINDOW_MS, zone); return `Latest allowed departure: ${latest.date} ${latest.time} (${zone}).`; }
  return null;
}
export function quickDeparture(kind: 'default' | 'one' | 'three' | 'tomorrow', now: number, zone: string): WallTime {
  if (kind === 'tomorrow') { const date = wallAt(now, zone).date; return { date: new Date(Date.parse(date + 'T00:00:00Z') + 86_400_000).toISOString().slice(0, 10), time: '06:00' }; }
  const hours = kind === 'one' ? 1 : kind === 'three' ? 3 : 2;
  const step = kind === 'default' ? 15 * MINUTE : MINUTE;
  return wallAt(Math.ceil((now + hours * 3_600_000) / step) * step, zone);
}
export function parseOffsetInstant(iso: string, zone: string): TimeChoice | null {
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}):00([+-]\d{2}:\d{2}|Z)$/.exec(iso);
  if (!match) return null;
  const instant = Date.parse(iso);
  if (!Number.isFinite(instant)) return null;
  return resolveWall({ date: match[1]!, time: match[2]! }, zone).choices.find(c => c.instant === instant) ?? null;
}
