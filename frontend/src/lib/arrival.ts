import { useSyncExternalStore } from 'react';
import { MOTION, motionOff } from './motion';

/** Presentation milliseconds, shared by CSS entrances and the existing renderer. */
export const ARRIVAL = Object.freeze({ hero: 0, heroDuration: MOTION.hero, count: MOTION.entrance, matrix: 120, cards: 320, route: 100, routeDuration: 700, routeStagger: 70, checkpoints: 940, checkpointDuration: 160, heat: 1100, heatDuration: MOTION.hero, chips: 1440, chipDuration: MOTION.normal, end: 1800 });
export interface MotionClock { now(): number; later(fn: () => void, ms: number): ReturnType<typeof setTimeout>; clear(id: ReturnType<typeof setTimeout>): void }
const clock: MotionClock = { now: () => performance.now(), later: (fn, ms) => setTimeout(fn, ms), clear: id => clearTimeout(id) };
export function createArrival(off = motionOff(), source = clock) {
  const started = source.now(), listeners = new Set<() => void>();
  let done = off;
  const finish = () => { if (done) return; done = true; source.clear(timer); listeners.forEach(fn => fn()); };
  const timer = source.later(finish, off ? 0 : ARRIVAL.end);
  return { started, elapsed: () => done ? ARRIVAL.end : Math.max(0, source.now() - started), done: () => done, finish,
    subscribe: (fn: () => void) => { listeners.add(fn); return () => { listeners.delete(fn); }; } };
}
export type Arrival = ReturnType<typeof createArrival>;
const arrivals = new WeakMap<object, Arrival>();
let active: Arrival | undefined;
/** A replacement during an entrance finishes both; revisits never replay it. */
export function arrivalFor(analysis: object) {
  let arrival = arrivals.get(analysis);
  if (!arrival) { const interrupted = !!active && !active.done(); active?.finish(); arrival = createArrival(interrupted || motionOff()); arrivals.set(analysis, arrival); active = arrival; }
  return arrival;
}
export function finishArrival() { active?.finish(); }
export function useArrival(analysis: object) {
  const arrival = arrivalFor(analysis), done = useSyncExternalStore(arrival.subscribe, arrival.done, arrival.done);
  return { arrival, done };
}
export const phase = (elapsed: number, start: number, duration: number) => Math.max(0, Math.min(1, (elapsed - start) / duration));
export function arrivalFrame(elapsed: number) {
  return { routes: [0, 1, 2].map(i => phase(elapsed, ARRIVAL.route + i * ARRIVAL.routeStagger, ARRIVAL.routeDuration)), checkpoints: phase(elapsed, ARRIVAL.checkpoints, ARRIVAL.checkpointDuration), heat: phase(elapsed, ARRIVAL.heat, ARRIVAL.heatDuration), chips: phase(elapsed, ARRIVAL.chips, ARRIVAL.chipDuration) };
}
