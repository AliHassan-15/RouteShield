import { cloneElement, useEffect, useId, useRef, useState } from 'react';
import type { CSSProperties, ReactElement, ReactNode } from 'react';
import type { RiskLevel } from '../api/types';
import { useReducedMotion } from '../lib/motion';
import { Button, IconButton } from './controls';
import { Icon } from './icons';
import type { IconName } from './icons';

export const riskPresentation: Record<RiskLevel, { label: string; icon: IconName; token: string; shape: string }> = {
  LOW: { label: 'Low', icon: 'risk-low', token: 'low', shape: 'circle' },
  MODERATE: { label: 'Moderate', icon: 'risk-moderate', token: 'moderate', shape: 'diamond' },
  HIGH: { label: 'High', icon: 'risk-high', token: 'high', shape: 'triangle' },
  SEVERE: { label: 'Severe', icon: 'risk-severe', token: 'severe', shape: 'square' },
  NO_TRAVEL: { label: 'No travel', icon: 'risk-no-travel', token: 'no-travel', shape: 'octagon' },
  UNKNOWN: { label: 'Unknown', icon: 'risk-unknown', token: 'unknown', shape: 'dashed ring' },
};
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`surface ${className}`}>{children}</div>;
}
export function Panel({ title, eyebrow, children, actions }: { title: string; eyebrow?: string; children: ReactNode; actions?: ReactNode }) {
  const id = useId();
  return <section className="panel" aria-labelledby={id}><header className="panel-heading"><div>{eyebrow && <p className="micro">{eyebrow}</p>}<h2 id={id}>{title}</h2></div>{actions}</header>{children}</section>;
}
export function RiskBadge({ level }: { level: RiskLevel }) {
  const item = riskPresentation[level];
  return <span className={`risk-badge risk-${item.token}`} data-shape={item.shape}><Icon name={item.icon} /><span>{item.label}</span></span>;
}
export function StatusBadge({ status, children }: { status: 'healthy' | 'waking' | 'unreachable' | 'neutral'; children: ReactNode }) {
  return <span className={`status-badge status-${status}`}><Icon name={status === 'healthy' ? 'check' : status === 'unreachable' ? 'warning' : status === 'waking' ? 'clock' : 'info'} /><span>{children}</span></span>;
}
export function TickDivider({ label }: { label?: string }) {
  return <div className="tick-divider">{label && <span className="micro">{label}</span>}<span aria-hidden="true" /></div>;
}
export function MetricTile({ label, value, unit, hint }: { label: string; value: string; unit?: string; hint?: string }) {
  return <dl className="metric-tile"><dt className="micro">{label}</dt><dd><span className="metric-number mono">{value}</span>{unit && <span className="unit">{unit}</span>}</dd>{hint && <dd className="field-hint">{hint}</dd>}</dl>;
}
export function RiskBar({ segments }: { segments: readonly { level: RiskLevel; miles: number }[] }) {
  const total = segments.reduce((sum, s) => sum + s.miles, 0);
  return <div className="risk-bar" role="img" aria-label={`Distance by risk: ${segments.map(s => `${riskPresentation[s.level].label} ${s.miles} miles`).join(', ')}`}>
    {total > 0 && segments.filter(s => s.miles > 0).map(s => <span key={s.level} className={`risk-segment risk-${riskPresentation[s.level].token}`} style={{ flexGrow: s.miles / total }} />)}<span className="risk-bar-ticks" aria-hidden="true" />
  </div>;
}
export function Tooltip({ label, children }: { label: string; children: ReactElement<{ 'aria-describedby'?: string }> }) {
  const id = useId(), [open, setOpen] = useState(false);
  return <span className="tooltip-host" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} onKeyDown={e => { if (e.key === 'Escape') setOpen(false); }}>{cloneElement(children, { 'aria-describedby': id })}<span id={id} role="tooltip" className="tooltip" hidden={!open}>{label}</span></span>;
}
export function floatingPosition(anchor: DOMRect, width: number, height: number, viewport: { width: number; height: number }) {
  return { left: Math.max(8, Math.min(anchor.left, viewport.width - width - 8)), top: anchor.bottom + 8 + height > viewport.height ? Math.max(8, anchor.top - height - 8) : anchor.bottom + 8 };
}
export function Popover({ label, icon = 'info', children }: { label: string; icon?: IconName; children: ReactNode }) {
  const native = typeof HTMLElement !== 'undefined' && 'showPopover' in HTMLElement.prototype;
  const id = useId(), panel = useRef<HTMLDivElement>(null), trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false), [position, setPosition] = useState<CSSProperties>({});
  const close = () => { if (panel.current?.hidePopover && panel.current.matches(':popover-open')) panel.current.hidePopover(); setOpen(false); trigger.current?.focus(); };
  useEffect(() => {
    if (!open || !panel.current || !trigger.current) return;
    const node = panel.current;
    if (node.showPopover && !node.matches(':popover-open')) node.showPopover();
    const place = () => { if (trigger.current) setPosition(floatingPosition(trigger.current.getBoundingClientRect(), node.offsetWidth, node.offsetHeight, { width: window.innerWidth, height: window.innerHeight })); };
    place();
    node.querySelector<HTMLElement>('button, a, input, [tabindex="0"]')?.focus();
    if (!node.contains(document.activeElement)) node.focus();
    const dismiss = (e: globalThis.KeyboardEvent) => { if (e.key === 'Escape') { e.preventDefault(); close(); } };
    const outside = (e: globalThis.PointerEvent) => { if (e.target instanceof Node && !node.contains(e.target) && !trigger.current?.contains(e.target)) close(); };
    document.addEventListener('keydown', dismiss);
    document.addEventListener('pointerdown', outside);
    window.addEventListener('resize', place);
    return () => { document.removeEventListener('keydown', dismiss); document.removeEventListener('pointerdown', outside); window.removeEventListener('resize', place); };
  }, [open]);
  return <><button ref={trigger} type="button" className="button button-ghost icon-button" aria-label={label} aria-haspopup="dialog" aria-expanded={open} aria-controls={id} onClick={() => { if (open) close(); else setOpen(true); }}><Icon name={icon} /></button><div ref={panel} id={id} role="dialog" aria-label={label} tabIndex={-1} popover={native ? 'auto' : undefined} className={`popover ${open ? 'is-open' : ''}`} hidden={!open} style={position} onToggle={e => { if (e.newState === 'closed') setOpen(false); }}><div className="popover-heading"><strong>{label}</strong><IconButton icon="close" label={`Close ${label}`} onClick={close} /></div>{children}</div></>;
}
export function Toast({ children, onDismiss, tone = 'neutral' }: { children: ReactNode; onDismiss: () => void; tone?: 'neutral' | 'error' }) {
  const [closing, setClosing] = useState(false), reduced = useReducedMotion();
  useEffect(() => { if (!closing) return; const timer = setTimeout(onDismiss, reduced ? 0 : 200); return () => clearTimeout(timer); }, [closing, onDismiss, reduced]);
  return <div className={`toast ${closing ? 'is-closing' : ''}`} role={tone === 'error' ? 'alert' : 'status'}><Icon name={tone === 'error' ? 'warning' : 'check'} /><span>{children}</span><IconButton icon="close" label="Dismiss notification" onClick={() => setClosing(true)} /></div>;
}
export function Skeleton({ label = 'Loading', lines = 3 }: { label?: string; lines?: number }) {
  return <div role="status" aria-label={label} className="skeleton-group"><span className="sr-only">{label}</span>{Array.from({ length: lines }, (_, i) => <span key={i} className="skeleton" aria-hidden="true" />)}</div>;
}
export function EmptyState({ title, children, icon = 'route', action }: { title: string; children: ReactNode; icon?: IconName; action?: ReactNode }) {
  return <div className="empty-state"><Icon name={icon} width="36" height="36" /><h3>{title}</h3><p>{children}</p>{action}</div>;
}
export function ErrorState({ title, children, action, onRecover, requestId }: { title: string; children: ReactNode; action: string; onRecover: () => void; requestId?: string }) {
  return <div className="error-state" role="alert"><Icon name="warning" /><h3>{title}</h3><p>{children}</p>{requestId && <p className="field-hint">Support ID <span className="mono">{requestId}</span></p>}<Button onClick={onRecover}>{action}</Button></div>;
}
