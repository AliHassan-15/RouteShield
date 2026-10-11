import { Input, SegmentedControl, Button } from '../../components/controls';
import type { TripDraft } from './model';
import { chosenTime, offsetLabel, quickDeparture, resolveWall } from './time';

export function DepartureControl({ draft, change, now, error }: { draft: TripDraft; change: (value: Partial<TripDraft>) => void; now: number; error?: string }) {
  const resolution = resolveWall(draft.wall, draft.zone), choice = chosenTime(resolution, draft.offset);
  const offset = choice?.offsetMinutes ?? resolveWall(quickDeparture('one', now, draft.zone), draft.zone).choices[0]?.offsetMinutes ?? 0;
  return <div className="departure-control"><div className="departure-fields"><Input id="trip-departure" label="Date" type="date" className="numeric-field" value={draft.wall.date} onChange={e => change({ wall: { ...draft.wall, date: e.target.value }, offset: null })} error={error} /><Input id="trip-departure-time" label="Time" type="time" className="numeric-field" value={draft.wall.time} onChange={e => change({ wall: { ...draft.wall, time: e.target.value }, offset: null })} hint="Local wall time" /></div>
    <div className="quick-chips">{([['one', 'In 1 hour'], ['three', 'In 3 hours'], ['tomorrow', 'Tomorrow 06:00']] as const).map(([key, label]) => <Button key={key} variant="ghost" onClick={() => change({ wall: quickDeparture(key, Date.now(), draft.zone), offset: null })}>{label}</Button>)}</div>
    <div className="zone-readout"><p className="micro">Browser time zone</p><p className="mono">{draft.zone} · UTC{offsetLabel(offset)}</p><p className="field-hint">{choice ? <><span>UTC instant </span><span className="mono">{new Date(choice.instant).toISOString().replace('.000', '')}</span></> : 'UTC instant requires a valid, unambiguous time.'}</p></div>
    {resolution.kind === 'gap' && <div className="time-notice"><p>This local time does not exist because the clocks move forward.</p>{resolution.fix && <Button onClick={() => change({ wall: resolution.fix!, offset: null })}>Move to {resolution.fix.time}</Button>}</div>}
    {resolution.kind === 'ambiguous' && <div className="time-notice"><p>This time occurs twice. Choose the earlier or later offset.</p><SegmentedControl label="Repeated-time offset" value={draft.offset === null ? '' : String(draft.offset)} options={resolution.choices.map((candidate, index) => ({ value: String(candidate.offsetMinutes), label: `${index === 0 ? 'Earlier' : 'Later'} · UTC${offsetLabel(candidate.offsetMinutes)}` }))} onChange={value => change({ offset: Number(value) })} /></div>}
    {choice && choice.instant > now + 5 * 86_400_000 && <p className="info-note">Forecast coverage thins for departures this far out; some hours may be unavailable.</p>}
  </div>;
}
