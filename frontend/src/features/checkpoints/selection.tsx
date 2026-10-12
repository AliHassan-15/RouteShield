import { useEffect, useRef } from 'react';
import type { Route } from '../../api/types';
import { useSelection, useSelectionStore } from '../../api/selection-store';
import { displayNumber } from '../../lib/format';

export const orderedCheckpoints = (route: Route) => [...route.checkpoints].sort((a, b) => (displayNumber(a.mile_marker) ?? 0) - (displayNumber(b.mile_marker) ?? 0) || a.index - b.index);
export function stepIndex(route: Route, index: number | null, delta: number) {
  const points = orderedCheckpoints(route), at = points.findIndex(cp => cp.index === index);
  return points[Math.max(0, Math.min(points.length - 1, at < 0 ? 0 : at + delta))]?.index ?? null;
}
function edgeFeedback(node: HTMLElement | null, delta: number) { if (!matchMedia('(prefers-reduced-motion: reduce)').matches) node?.animate?.([{ transform: 'translateX(0)' }, { transform: `translateX(${delta * 3}px)` }, { transform: 'translateX(0)' }], { duration: 160 }); }
export function useCheckpointKeys(route: Route | undefined) {
  const store = useSelectionStore(), latest = useRef(route); latest.current = route;
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.defaultPrevented || !latest.current || !['[', ']'].includes(e.key) || (e.target instanceof Element && e.target.closest('input,textarea,select,[contenteditable="true"]'))) return;
      e.preventDefault(); const delta = e.key === ']' ? 1 : -1, current = store.getState().selectedCheckpointIndex, next = stepIndex(latest.current, current, delta);
      if (next === current) edgeFeedback(document.querySelector<HTMLElement>('.profile-interaction,.inspector-dock'), delta);
      store.selectCheckpoint(next);
    };
    document.addEventListener('keydown', key); return () => document.removeEventListener('keydown', key);
  }, [store]);
}
export function CheckpointSteps({ route }: { route: Route }) {
  const selection = useSelection(), points = orderedCheckpoints(route), at = points.findIndex(cp => cp.index === selection.selectedCheckpointIndex), bounce = useRef<HTMLDivElement>(null);
  const step = (delta: number) => {
    const next = stepIndex(route, selection.selectedCheckpointIndex, delta);
    if (next === selection.selectedCheckpointIndex) edgeFeedback(bounce.current, delta);
    selection.selectCheckpoint(next);
  };
  return <div className="checkpoint-steps" ref={bounce}><button type="button" aria-label="Previous checkpoint" aria-disabled={at <= 0} onClick={() => step(-1)}>← Previous</button><button type="button" aria-label="Next checkpoint" aria-disabled={at >= points.length - 1} onClick={() => step(1)}>Next →</button></div>;
}
