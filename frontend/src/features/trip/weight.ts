import { MAX_WEIGHT_LB } from './config';

export interface ParsedWeight { token: string; numeric: number }
/** Retain the exact decimal token; Number is only the slider's approximate position. */
export function parseWeight(value: unknown): ParsedWeight | null {
  if (typeof value !== 'string' || value.length > 100) return null;
  const text = value.trim();
  if (!/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?$/.test(text)) return null;
  const [rawWhole = '', fraction] = text.replaceAll(',', '').split('.');
  const whole = rawWhole.replace(/^0+(?=\d)/, '');
  if (whole.length > 6 || Number(whole) > MAX_WEIGHT_LB || Number(whole) === MAX_WEIGHT_LB && fraction && /[1-9]/.test(fraction)) return null;
  const token = whole + (fraction === undefined ? '' : '.' + fraction);
  return { token, numeric: Number(token) };
}
export function aboveWeight(weight: ParsedWeight | null, threshold: number): boolean {
  if (!weight) return false;
  const [whole = '', fraction = ''] = weight.token.split('.');
  return Number(whole) > threshold || Number(whole) === threshold && /[1-9]/.test(fraction);
}
export function weightReadout(value: string): string {
  const parsed = parseWeight(value);
  if (!parsed) return '—';
  const [whole = '', fraction] = parsed.token.split('.');
  return whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (fraction === undefined ? '' : '.' + fraction);
}
