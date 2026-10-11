import { useEffect, useId, useRef, useState } from 'react';
import type { PointerEvent, ReactNode } from 'react';
import { keyboardSnap, nearestSnap, snapOffset } from '../lib/sheet';
import type { SheetSnap } from '../lib/sheet';

export function BottomSheet({ children, label = 'Route console', initialSnap = 'peek', revealRequest = 0, snapRequest, peekSummary }: { children: ReactNode; label?: string; initialSnap?: SheetSnap; revealRequest?: number; snapRequest?: { id: number; snap: SheetSnap; focusId?: string }; peekSummary?: ReactNode }) {
  const id = useId(), sheet = useRef<HTMLElement>(null), drag = useRef<{ y: number; offset: number; height: number; pointer: number } | null>(null);
  const handle = useRef<HTMLButtonElement>(null), content = useRef<HTMLDivElement>(null), focusAfterReveal = useRef(false);
  const [snap, setSnap] = useState<SheetSnap>(initialSnap), [offset, setOffset] = useState<number | null>(null);
  const requestedFocus = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!snapRequest) return;
    if (snapRequest.snap === 'peek' && snap !== 'peek') handle.current?.focus({ preventScroll: true });
    requestedFocus.current = snapRequest.focusId;
    setSnap(snapRequest.snap);
  }, [snapRequest]);
  useEffect(() => {
    if (snapRequest?.snap === snap && requestedFocus.current) { document.getElementById(requestedFocus.current)?.focus(); requestedFocus.current = undefined; }
  }, [snap, snapRequest]);
  useEffect(() => {
    if (!revealRequest) return;
    focusAfterReveal.current = true;
    setSnap('full');
  }, [revealRequest]);
  useEffect(() => {
    // Focus after React removes inert, rather than racing the reveal commit.
    if (snap === 'full' && focusAfterReveal.current) {
      content.current?.focus({ preventScroll: true });
      focusAfterReveal.current = false;
    }
  }, [snap, revealRequest]);
  const start = (e: PointerEvent<HTMLButtonElement>) => {
    if (e.button !== 0) return;
    const height = sheet.current?.offsetHeight || 600;
    drag.current = { y: e.clientY, offset: snapOffset(snap, height), height, pointer: e.pointerId };
    e.currentTarget.setPointerCapture?.(e.pointerId);
    setOffset(drag.current.offset);
  };
  const finish = (e: PointerEvent<HTMLButtonElement>, cancelled = false) => {
    if (!drag.current || e.pointerId !== drag.current.pointer) return;
    if (!cancelled) setSnap(nearestSnap(drag.current.offset + e.clientY - drag.current.y, drag.current.height));
    drag.current = null;
    setOffset(null);
    if (e.currentTarget.hasPointerCapture?.(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
  };
  return <section ref={sheet} className={`bottom-sheet ${offset !== null ? 'dragging' : ''}`} data-snap={snap} aria-label={label} style={offset !== null ? { transform: `translateY(${offset}px)` } : undefined} onKeyDown={e => { if (e.key === 'Escape' && !e.defaultPrevented) { e.preventDefault(); setSnap('peek'); handle.current?.focus(); } }}><button ref={handle} type="button" className="sheet-handle" aria-label={`${label}: ${snap}. Use arrow keys to resize; Escape to collapse.`} aria-controls={id} aria-expanded={snap !== 'peek'} onPointerDown={start} onPointerMove={e => { if (drag.current?.pointer === e.pointerId) setOffset(Math.max(0, Math.min(drag.current.height - 108, drag.current.offset + e.clientY - drag.current.y))); }} onPointerUp={e => finish(e)} onPointerCancel={e => finish(e, true)} onLostPointerCapture={e => finish(e, true)} onKeyDown={e => { if (['ArrowUp', 'ArrowDown', 'Home', 'End', 'Escape'].includes(e.key)) { e.preventDefault(); setSnap(keyboardSnap(snap, e.key)); } }}><span className="handle-line" /><span className="micro">{label}</span><span className="sheet-position mono">{snap}</span></button>{peekSummary && <div className="sheet-peek-summary">{peekSummary}</div>}<div ref={content} id={id} tabIndex={-1} className="sheet-content" inert={snap === 'peek'}>{children}</div><span role="status" className="sr-only">Console {snap}</span></section>;
}
