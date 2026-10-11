import { useEffect, useId, useRef, useState } from 'react';
import type { ButtonHTMLAttributes, InputHTMLAttributes, KeyboardEvent, ReactNode, SelectHTMLAttributes } from 'react';
import { Icon } from './icons';
import type { IconName } from './icons';

export function Button({ variant = 'secondary', loading = false, children, disabled, className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; loading?: boolean }) {
  return <button type="button" {...props} className={`button button-${variant} ${className}`} disabled={disabled || loading} aria-busy={loading || undefined}><span className="button-content">{children}</span>{loading && <span className="button-progress" aria-hidden="true" />}<span className="sr-only">{loading ? ' — working' : ''}</span></button>;
}
export function IconButton({ icon, label, ...props }: Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> & { icon: IconName; label: string }) {
  return <Button {...props} className={`icon-button ${props.className ?? ''}`} aria-label={label}><Icon name={icon} /></Button>;
}
interface FieldProps { label: string; hint?: string; error?: string; suffix?: string }
export function Input({ label, hint, error, suffix, id: providedId, className = '', ...props }: InputHTMLAttributes<HTMLInputElement> & FieldProps) {
  const unique = useId(), id = providedId ?? unique;
  const description = error || hint;
  return <div className={`field ${className}`}><label htmlFor={id}>{label}</label><div className="input-wrap"><input {...props} id={id} aria-invalid={!!error} aria-describedby={description ? `${id}-description` : undefined} />{suffix && <span className="input-unit">{suffix}</span>}</div>{description && <p id={`${id}-description`} className={error ? 'field-error' : 'field-hint'}>{error && <Icon name="warning" />}{description}</p>}</div>;
}
export function Select({ label, hint, error, id: providedId, children, ...props }: SelectHTMLAttributes<HTMLSelectElement> & FieldProps) {
  const unique = useId(), id = providedId ?? unique;
  return <div className="field"><label htmlFor={id}>{label}</label><div className="select-wrap"><select {...props} id={id} aria-invalid={!!error} aria-describedby={hint || error ? `${id}-description` : undefined}>{children}</select><Icon name="chevron-down" /></div>{(hint || error) && <p id={`${id}-description`} className={error ? 'field-error' : 'field-hint'}>{error || hint}</p>}</div>;
}
export function Slider({ label, value, min = 0, max = 48, step = 1, unit = '', onChange, disabled = false }: { label: string; value: number; min?: number; max?: number; step?: number; unit?: string; onChange: (value: number) => void; disabled?: boolean }) {
  const id = useId();
  return <div className="field slider-field"><div className="field-row"><label htmlFor={id}>{label}</label><output htmlFor={id} className="mono">{value}<span className="unit"> {unit}</span></output></div><div className="instrument-scale"><input id={id} type="range" min={min} max={max} step={step} value={value} disabled={disabled} onChange={e => onChange(Number(e.target.value))} aria-valuetext={`${value} ${unit}`.trim()} /><div className="scale-extents mono" aria-hidden="true"><span>{min}</span><span>{max}</span></div></div></div>;
}
export interface Choice { value: string; label: string; icon?: IconName }
export function keyboardIndex(key: string, index: number, count: number): number | null {
  if (key === 'Home') return 0;
  if (key === 'End') return count - 1;
  if (key === 'ArrowRight' || key === 'ArrowDown') return (index + 1) % count;
  if (key === 'ArrowLeft' || key === 'ArrowUp') return (index + count - 1) % count;
  return null;
}
export function SegmentedControl({ label, value, options, onChange, compact = false }: { label: string; value: string; options: readonly Choice[]; onChange: (value: string) => void; compact?: boolean }) {
  const group = useRef<HTMLDivElement>(null);
  const key = (event: KeyboardEvent, index: number) => {
    const next = keyboardIndex(event.key, index, options.length);
    if (next === null) return;
    event.preventDefault();
    const option = options[next];
    if (option) onChange(option.value);
    group.current?.querySelectorAll<HTMLButtonElement>('button')[next]?.focus();
  };
  return <div ref={group} role="radiogroup" aria-label={label} className={`segmented ${compact ? 'compact' : ''}`}>{options.map((option, index) => <button key={option.value} type="button" role="radio" aria-checked={value === option.value} aria-label={option.label} tabIndex={value === option.value ? 0 : -1} onClick={() => onChange(option.value)} onKeyDown={e => key(e, index)}>{option.icon && <Icon name={option.icon} />}{!compact && <span>{option.label}</span>}</button>)}</div>;
}
export function Tabs({ label, tabs }: { label: string; tabs: readonly { id: string; label: string; content: ReactNode }[] }) {
  const id = useId(), list = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0), [indicator, setIndicator] = useState({ left: 0, width: 0 });
  useEffect(() => {
    const measure = () => {
      const selected = list.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[active];
      if (selected) setIndicator({ left: selected.offsetLeft, width: selected.offsetWidth });
    };
    measure();
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
    if (list.current) observer?.observe(list.current);
    window.addEventListener('resize', measure);
    return () => { observer?.disconnect(); window.removeEventListener('resize', measure); };
  }, [active]);
  return <div className="tabs"><div ref={list} role="tablist" aria-label={label} className="tab-list">{tabs.map((tab, index) => <button key={tab.id} id={`${id}-${tab.id}`} type="button" role="tab" aria-selected={active === index} aria-controls={`${id}-panel-${tab.id}`} tabIndex={active === index ? 0 : -1} onClick={() => setActive(index)} onKeyDown={e => {
    const next = keyboardIndex(e.key, index, tabs.length);
    if (next !== null) { e.preventDefault(); setActive(next); list.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus(); }
  }}>{tab.label}</button>)}<span className="tab-indicator" style={{ width: indicator.width, transform: `translateX(${indicator.left}px)` }} /></div>{tabs.map((tab, index) => <div key={tab.id} id={`${id}-panel-${tab.id}`} role="tabpanel" aria-labelledby={`${id}-${tab.id}`} tabIndex={0} hidden={active !== index}>{tab.content}</div>)}</div>;
}
