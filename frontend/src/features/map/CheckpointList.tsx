import { useEffect, useRef } from 'react';
import type { Route } from '../../api/types';
import { useSelection } from '../../api/selection-store';
import { RiskBadge } from '../../components/surfaces';
import { tooltipContent } from './tooltip';
export function CheckpointList({ route }: { route: Route }) {
  const selection = useSelection(), list = useRef<HTMLOListElement>(null), details = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (selection.selectedCheckpointIndex === null) return;
    if (details.current) details.current.open = true;
    list.current?.querySelector<HTMLElement>(`[data-checkpoint="${selection.selectedCheckpointIndex}"]`)?.scrollIntoView?.({ block: 'nearest', behavior: 'instant' });
  }, [selection.selectedCheckpointIndex]);
  return <details ref={details} className="checkpoint-list"><summary>Checkpoints · {route.checkpoints.length}</summary><ol ref={list}>{route.checkpoints.map(cp => { const content = tooltipContent(cp); return <li key={cp.id}><button type="button" data-checkpoint={cp.index} aria-pressed={selection.selectedCheckpointIndex === cp.index} onFocus={() => selection.selectCheckpoint(cp.index)} onClick={() => selection.selectCheckpoint(cp.index)}><span className="mono">{content.title}</span><RiskBadge level={cp.risk.final_risk} /><span className="mono">{content.weather}</span>{content.unavailable && <span>{content.unavailable}</span>}</button></li>; })}</ol></details>;
}
