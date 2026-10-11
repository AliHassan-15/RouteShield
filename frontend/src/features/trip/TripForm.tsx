import { useEffect, useRef, useState } from 'react';
import { Button, IconButton, SegmentedControl } from '../../components/controls';
import { Icon } from '../../components/icons';
import { Toast, TickDivider } from '../../components/surfaces';
import { useReducedMotion } from '../../lib/motion';
import { DepartureControl } from './DepartureControl';
import { LoadControl } from './LoadControl';
import { PlaceCombobox } from './PlaceCombobox';
import { EXAMPLE_TRIPS, STRAIGHT_LINE_ADVISORY_MILES } from './config';
import { distantEndpoints } from './model';
import type { Spacing } from './model';
import type { TripPlanner } from './useTripPlanner';
import './trip.css';

function RequestId({ id, onCopied }: { id: string; onCopied: (message: string) => void }) {
  const input = useRef<HTMLInputElement>(null);
  return <div className="request-chip"><input ref={input} aria-label="Request ID" className="mono" readOnly value={id} onFocus={e => e.currentTarget.select()} /><Button variant="ghost" onClick={async () => { try { await navigator.clipboard.writeText(id); onCopied('Request ID copied.'); } catch { input.current?.focus(); input.current?.select(); onCopied('Request ID selected. Use your copy shortcut.'); } }}>Copy ID</Button></div>;
}
function SpacingControl({ value, onChange }: { value: Spacing; onChange: (value: Spacing) => void }) {
  const root = useRef<HTMLDivElement>(null), [indicator, setIndicator] = useState({ left: 0, width: 0 });
  useEffect(() => {
    const measure = () => { const button = root.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]'); if (button) setIndicator({ left: button.offsetLeft, width: button.offsetWidth }); };
    measure(); const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure); if (root.current) observer?.observe(root.current); return () => observer?.disconnect();
  }, [value]);
  return <div id="trip-spacing" tabIndex={-1} ref={root} className="spacing-choice"><SegmentedControl label="Checkpoint spacing" value={value} options={[{ value: 'auto', label: 'Auto' }, { value: '10', label: '10 mi' }, { value: '25', label: '25 mi' }, { value: '50', label: '50 mi' }]} onChange={next => onChange(next as Spacing)} /><span className="spacing-indicator" style={{ width: indicator.width, transform: `translateX(${indicator.left}px)` }} /><p className="field-hint">{value === 'auto' ? 'Auto picks 10, 25 or 50 miles from the trip length. Finer spacing samples more weather points.' : `${value} miles between checkpoints. ${value === '10' ? 'More weather samples and finer detail.' : value === '25' ? 'A balance of coverage and request size.' : 'Fewer weather samples for longer corridors.'}`}</p></div>;
}
export function ProgressLine({ planner }: { planner: TripPlanner }) {
  return <div className="peek-progress"><span><span role="status" aria-live="polite">{planner.phase === 'waking' ? 'Waking backend' : 'Analyzing routes'}</span><span className="mono" aria-live="off">{planner.elapsed}s</span></span><Button variant="ghost" onClick={planner.cancel}>Cancel</Button></div>;
}
export function TripForm({ planner }: { planner: TripPlanner }) {
  const { draft, change, errors, validation, error } = planner;
  const summary = useRef<HTMLElement>(null);
  const reduced = useReducedMotion(), [swaps, setSwaps] = useState(0);
  useEffect(() => {
    if (!planner.snapshot) return;
    // Scroll only the form. scrollIntoView also scrolls the sheet's clipped dock.
    const frame = requestAnimationFrame(() => {
      const target = summary.current, body = target?.closest('.trip-form-body');
      if (target && body) body.scrollTop += target.getBoundingClientRect().top - body.getBoundingClientRect().top;
    });
    return () => cancelAnimationFrame(frame);
  }, [planner.snapshot]);
  const dateError = errors.departure || (validation.choice ? validation.errors.departure : undefined);
  const fields = Object.values(errors), maximum = error?.details.max_distance_miles;
  const supported = typeof maximum === 'number' && Number.isFinite(maximum) && maximum > 0 ? maximum.toLocaleString('en-US') : null;
  const demoQuota = error?.code === 'QUOTA_EXCEEDED' && Object.values(error.details).includes('DEMO_QUOTA_REACHED');
  const message = error?.code === 'TRIP_TOO_LARGE' ? supported ? `This demo supports up to ${supported} road miles. Choose closer endpoints or use an example trip.` : 'This trip exceeds the supported range. Choose closer endpoints or use an example trip.' : demoQuota ? 'Demo weather quota reached; try again after the quota window resets.' : error?.presentation.message;
  const progress = planner.phase === 'waking' ? 'Waking up the backend. Analysis starts when it is ready.' : 'Routing, forecasting and scoring. Long trips can take up to 35 seconds.';
  return <form className="trip-form" noValidate onSubmit={event => { event.preventDefault(); planner.submit(); }}>
    <div className="trip-form-body"><header className="trip-heading"><p className="micro">Weather operations</p><h2>Trip plan</h2><p className="field-hint">Plan the corridor. Assess the conditions.</p></header>
      {planner.notice && <p className="info-note">{planner.notice}</p>}
      <div role="status" aria-live="polite" className={fields.length ? 'validation-summary' : 'sr-only'}>{fields.length ? `Review ${fields.length} ${fields.length === 1 ? 'field' : 'fields'}: ${fields.join(' ')}` : ''}</div>
      <fieldset disabled={planner.busy} className="trip-fields">
        <section className="trip-section" aria-label="Route"><TickDivider label="01 / Route" /><div className="route-stack"><div className="route-connector" aria-hidden="true"><i /><span /><b /></div><PlaceCombobox field="origin" value={draft.origin} onEdit={text => change({ origin: { text, place: null } })} onSelect={place => planner.selectPlace('origin', place)} recent={planner.history.places} error={errors.origin} /><div className="swap-row"><IconButton icon="swap" label="Swap origin and destination" className="swap-control" style={{ transform: `rotate(${swaps * 180}deg)`, transitionDuration: reduced ? '0s' : undefined }} onClick={() => { setSwaps(n => n + 1); planner.swap(); }} /></div><PlaceCombobox field="destination" value={draft.destination} onEdit={text => change({ destination: { text, place: null } })} onSelect={place => planner.selectPlace('destination', place)} recent={planner.history.places} error={errors.destination} /></div>
          <div className="example-trips"><p className="micro">Use example trip</p>{EXAMPLE_TRIPS.map(trip => <Button key={trip.label} variant="ghost" onClick={() => { planner.selectPlace('origin', trip.origin); planner.selectPlace('destination', trip.destination); }}><Icon name="route" />{trip.label}</Button>)}</div><p className="field-hint">Demo supports trips up to about 300 road miles.</p>{distantEndpoints(draft.origin.place, draft.destination.place) && <p className="info-note">These endpoints are more than {STRAIGHT_LINE_ADVISORY_MILES} straight-line miles apart. Road distance may exceed the demo range; the backend checks the supported limit.</p>}
          <details className="recent-trips"><summary>Recent trips <span className="mono">{planner.history.trips.length}</span></summary>{planner.history.trips.length ? planner.history.trips.map((trip, index) => <Button key={index} variant="ghost" onClick={() => planner.restore(trip)}>{trip.origin.label} → {trip.destination.label}<small>Uses the current departure</small></Button>) : <p className="field-hint">No analyzed trips on this device.</p>}</details><div className="privacy-row"><p className="field-hint">Stored on this device only.</p><Button variant="ghost" onClick={planner.clear}>Clear history</Button></div>
        </section>
        <section className="trip-section" aria-label="Departure"><TickDivider label="02 / Departure" /><DepartureControl draft={draft} change={change} now={planner.now} error={dateError} /></section>
        <section className="trip-section" aria-label="Load"><TickDivider label="03 / Load" /><LoadControl value={draft.weight} onChange={weight => change({ weight })} error={errors.weight || (draft.weight ? validation.errors.weight : undefined)} /></section>
        <section className="trip-section" aria-label="Checkpoint spacing"><TickDivider label="04 / Checkpoint spacing" /><SpacingControl value={draft.spacing} onChange={spacing => change({ spacing })} />{errors.spacing && <p className="field-error">{errors.spacing}</p>}</section>
      </fieldset>
      {error && <section className="trip-error" aria-label="Analysis error"><div role="status" aria-live="polite"><p className="micro">Request unavailable</p><h3>{error.presentation.title}</h3><p>{message}</p></div>{error.code === 'THROTTLED' && <p>Retry available in <span className="mono" aria-live="off">{planner.secondsLeft}s</span><span className="sr-only" role="status">{planner.secondsLeft === 0 ? 'Retry is available.' : 'Wait for the request limit to reset.'}</span></p>}{error.requestId && <RequestId id={error.requestId} onCopied={planner.setToast} />}<Button disabled={planner.secondsLeft > 0} onClick={() => { if (error.code === 'TRIP_TOO_LARGE') document.querySelector<HTMLButtonElement>('.example-trips button')?.focus(); else if (error.presentation.recovery === 'edit') document.getElementById('trip-origin')?.focus(); else planner.submit(); }}>{error.code === 'TRIP_TOO_LARGE' ? 'Choose an example trip' : error.presentation.action}</Button></section>}
      {planner.snapshot && <section ref={summary} className="temporary-summary" aria-label="Analysis summary" aria-live="polite"><p className="micro">{import.meta.env.DEV ? 'Temporary summary' : 'Analysis received'}</p><p><span className="metric-number mono">{planner.snapshot.response.route_count}</span>{' '}routes returned</p><p>{planner.snapshot.response.message}</p><RequestId id={planner.snapshot.response.metadata.request_id} onCopied={planner.setToast} /></section>}
    </div>
    <footer className={`trip-action-bar ${planner.busy ? 'is-running' : ''}`}><div className="action-ticks" aria-hidden="true"><span /></div>{planner.busy ? <><div className="submit-status"><span className="mono elapsed" aria-live="off">{planner.elapsed}s</span><div><p role="status" aria-live="polite">{progress}</p>{planner.elapsed >= 8 && planner.phase === 'running' && <p className="field-hint">Still working. The weather service can be slow.</p>}</div></div><div className="action-buttons"><Button variant="primary" loading>Analyze routes</Button><Button onClick={planner.cancel}>Cancel</Button></div></> : <Button variant="primary" type="submit" disabled={planner.secondsLeft > 0}><Icon name="route" />Analyze routes</Button>}</footer>
    {planner.toast && <div className="trip-toast"><Toast onDismiss={() => planner.setToast('')}>{planner.toast}</Toast></div>}
  </form>;
}
