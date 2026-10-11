import type { ExactNumber, FactValue, Checkpoint } from '../api/types';

// DISPLAY ONLY. Exact rational/decimal parsing and half-even rounding never feed
// ranking, risk, selection or eligibility. Bounded strings also reject hostile data.
export function fraction(value: unknown): [bigint, bigint] | null {
  try {
    if (typeof value === 'object' && value !== null && 'numerator' in value && 'denominator' in value) {
      const { numerator: n, denominator: d } = value as ExactNumber;
      if (typeof n !== 'string' || typeof d !== 'string' || n.length > 500 || d.length > 500 || !/^-?\d+$/.test(n) || !/^\d+$/.test(d) || BigInt(d) <= 0n) return null;
      return [BigInt(n), BigInt(d)];
    }
    if (typeof value !== 'string' && typeof value !== 'number') return null;
    const text = String(value);
    if (text.length > 500) return null;
    const match = /^(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d{1,3}))?$/.exec(text);
    if (!match) return null;
    const tail = match[3] ?? '', exponent = Number(match[4] ?? 0) - tail.length;
    if (Math.abs(exponent) > 500) return null;
    const n = BigInt(`${match[1]}${match[2]}${tail}`);
    return exponent >= 0 ? [n * 10n ** BigInt(exponent), 1n] : [n, 10n ** BigInt(-exponent)];
  } catch { return null; }
}
export function fixed(value: unknown, places = 1, multiplier = 1n, divisor = 1n): string {
  const pair = fraction(value);
  if (!pair || !Number.isInteger(places) || places < 0 || places > 6 || divisor <= 0n) return 'n/a';
  const signed = pair[0] * multiplier, n = (signed < 0n ? -signed : signed) * 10n ** BigInt(places), d = pair[1] * divisor;
  let scaled = n / d;
  const remainder = n % d;
  if (remainder * 2n > d || remainder * 2n === d && scaled % 2n === 1n) scaled++;
  const digits = scaled.toString().padStart(places + 1, '0');
  const integer = (places ? digits.slice(0, -places) : digits).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return `${signed < 0n && scaled !== 0n ? '-' : ''}${integer}${places ? `.${digits.slice(-places)}` : ''}`;
}
export const miles = (v: unknown) => fixed(v, 1);
export function decimal(v: unknown): string {
  const pair = fraction(v);
  if (!pair) return 'n/a';
  const n = pair[0] < 0n ? -pair[0] : pair[0], d = pair[1];
  let remainder = n % d, tail = '';
  while (remainder && tail.length < 500) { remainder *= 10n; tail += String(remainder / d); remainder %= d; }
  if (remainder) return 'n/a';
  return `${pair[0] < 0n ? '-' : ''}${(n / d).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',')}${tail ? `.${tail}` : ''}`;
}
export const percent = (v: unknown) => { const text = fixed(v, 1, 100n); return text === 'n/a' ? text : `${text}%`; };
export function missingPercent(v: unknown): string { const pair = fraction(v); return pair ? percent({ numerator: String(pair[1] - pair[0]), denominator: String(pair[1]) }) : 'n/a'; }
export const average = (v: unknown) => v === null ? 'n/a, weather incomplete' : fixed(v, 2);
export function duration(v: unknown): string {
  const pair = fraction(v);
  if (!pair || pair[0] < 0n) return 'n/a';
  const minutes = BigInt(fixed(v, 0, 1n, 60n).replaceAll(',', ''));
  return `${minutes / 60n} h ${minutes % 60n} min`;
}
export function time(instant: unknown, zone = 'UTC', date = false): string {
  if (typeof instant !== 'string' || !Number.isFinite(Date.parse(instant))) return 'n/a';
  try { return new Intl.DateTimeFormat('en-US', { timeZone: zone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZoneName: 'short', ...(date ? { month: 'short', day: 'numeric' } as const : {}) }).format(new Date(instant)); } catch { return 'n/a'; }
}
export function arrival(checkpoint: Checkpoint | undefined): { local: string; utc: string } {
  if (!checkpoint) return { local: 'n/a', utc: 'n/a' };
  return { local: time(checkpoint.eta_utc, checkpoint.utc_fallback || !checkpoint.timezone ? 'UTC' : checkpoint.timezone), utc: typeof checkpoint.eta_utc === 'string' && Number.isFinite(Date.parse(checkpoint.eta_utc)) ? checkpoint.eta_utc : 'n/a' };
}
export function displayNumber(v: unknown): number | null {
  // Approximation ONLY for visual widths and ages; never compare routes with it.
  const text = fixed(v, 6).replaceAll(',', ''), n = Number(text);
  return Number.isFinite(n) ? n : null;
}
export function criterionValue(code: string, v: FactValue): string {
  if (code === 'DURATION') return duration(v);
  if (code === 'AVERAGE_RISK') return average(v);
  if (code.endsWith('_MILES')) return `${miles(v)} mi`;
  return typeof v === 'string' ? v : fixed(v, 2);
}
