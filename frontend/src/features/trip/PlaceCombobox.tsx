import { useEffect, useId, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { geocode } from '../../api/client';
import { ApiError } from '../../api/errors';
import type { SelectedPlace } from '../../api/types';
import { Button } from '../../components/controls';
import { Icon } from '../../components/icons';
import { useReducedMotion } from '../../lib/motion';
import { GEO_DEBOUNCE_MS, GEO_MIN_CHARACTERS, LABEL_LIMIT } from './config';
import type { PlaceChoice, PlaceField } from './model';

interface Props { field: 'origin' | 'destination'; value: PlaceField; onEdit: (text: string) => void; onSelect: (place: PlaceChoice) => void; recent: SelectedPlace[]; error?: string }
export function PlaceCombobox({ field, value, onEdit, onSelect, recent, error }: Props) {
  const id = useId(), root = useRef<HTMLDivElement>(null), client = useQueryClient(), reduced = useReducedMotion();
  const [open, setOpen] = useState(false), [present, setPresent] = useState(false), [debounced, setDebounced] = useState(''), [active, setActive] = useState(-1), [retry, setRetry] = useState(0);
  const text = value.text.trim(), recentMode = !text, eligible = text.length >= GEO_MIN_CHARACTERS && !value.place;
  useEffect(() => {
    setDebounced(''); setActive(-1);
    if (!eligible || !open) return;
    const timer = setTimeout(() => setDebounced(text), GEO_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [text, eligible, open]);
  useEffect(() => {
    if (open) { setPresent(true); return; }
    void client.cancelQueries({ queryKey: ['geocode', id] });
    const timer = setTimeout(() => setPresent(false), reduced ? 0 : 120);
    return () => clearTimeout(timer);
  }, [open, client, id, reduced]);
  const query = useQuery({ queryKey: ['geocode', id, text, retry], queryFn: ({ signal }) => geocode(text, signal), enabled: open && eligible && debounced === text, gcTime: 0, staleTime: 0, retry: false });
  const options: PlaceChoice[] = recentMode ? recent : query.data?.candidates ?? [];
  const loading = eligible && !query.data && !query.isError;
  const expanded = open && !value.place;
  useEffect(() => { if (expanded && active >= 0) document.getElementById(`${id}-option-${active}`)?.scrollIntoView?.({ block: 'nearest' }); }, [expanded, active, id]);
  const choose = (index: number) => { const option = options[index]; if (option) { onSelect(option); setOpen(false); setActive(-1); } };
  const status = loading ? 'Finding matches.' : query.isError ? 'Location search unavailable.' : options.length ? `${options.length} ${recentMode ? 'recent places' : 'matches'} available.` : eligible && query.isSuccess ? 'No matches.' : 'Type at least three characters to search.';
  return <div ref={root} className={`place-field ${value.place ? 'is-resolved' : ''}`} onBlur={event => { if (!root.current?.contains(event.relatedTarget as Node | null)) setOpen(false); }}>
    <label htmlFor={`trip-${field}`}>{field === 'origin' ? 'Origin' : 'Destination'}</label>
    <div className="place-input"><input id={`trip-${field}`} role="combobox" autoComplete="off" spellCheck={false} maxLength={LABEL_LIMIT} value={value.text} placeholder={field === 'origin' ? 'City, address or place name' : 'Where is the truck going?'} aria-autocomplete="list" aria-expanded={expanded} aria-controls={`${id}-list`} aria-activedescendant={expanded && active >= 0 && options[active] ? `${id}-option-${active}` : undefined} aria-describedby={`${id}-hint`} aria-invalid={!!error} onChange={event => { onEdit(event.target.value); setOpen(true); setActive(-1); }} onFocus={() => { if (!value.place) setOpen(true); }} onKeyDown={event => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); if (open) setOpen(false); else onEdit(''); return; }
      if (event.key === 'Tab') { setOpen(false); return; }
      if (event.key === 'Enter' && expanded && active >= 0) { event.preventDefault(); choose(active); return; }
      if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key) && options.length) {
        event.preventDefault(); setOpen(true);
        setActive(previous => event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 : event.key === 'ArrowDown' ? (previous + 1) % options.length : previous <= 0 ? options.length - 1 : previous - 1);
      }
    }} /><Icon name={value.place ? 'check' : 'search'} /></div>
    <p id={`${id}-hint`} className={error ? 'field-error' : 'field-hint'}>{error || (value.place ? 'Selected location' : value.text ? 'Select a match' : 'Search or use an example trip')}</p>
    <span className="sr-only" role="status" aria-live="polite">{expanded ? status : ''}</span>
    {present && <div className={`place-dropdown ${expanded ? 'is-open' : 'is-closing'}`} aria-hidden={!expanded} inert={!expanded}>
      <div id={`${id}-list`} role="listbox" aria-label={`${field} matches`}>
        {recentMode && <p className="micro dropdown-note">Recent places</p>}
        {loading ? <p className="dropdown-state"><Icon name="clock" />Finding matches…</p> : query.isError && !recentMode ? <div className="dropdown-state"><p>{query.error instanceof ApiError ? query.error.presentation.message : 'Location search unavailable.'}</p><Button onClick={() => setRetry(n => n + 1)}>Retry search</Button></div> : options.length ? options.map((option, index) => <div key={`${index}-${option.label}`} id={`${id}-option-${index}`} role="option" aria-selected={active === index} className={`place-option ${active === index ? 'is-active' : ''}`} onPointerDown={event => event.preventDefault()} onPointerMove={() => setActive(index)} onClick={() => choose(index)}><Icon name="location" /><div><span>{option.label}</span>{(option.region || option.country) && <small>{[option.region, option.country].filter(Boolean).join(' · ')}</small>}</div></div>) : <p className="dropdown-state">{eligible && query.isSuccess ? 'No matches. Try a city, address or place name.' : recentMode ? 'No recent places on this device.' : 'Type at least three characters to search.'}</p>}
      </div>
      {query.data && !recentMode ? <footer className="geocode-credit"><p>{query.data.attribution.text}</p>{!query.data.attribution.confirmed && <span>Attribution unconfirmed</span>}</footer> : recentMode && <footer className="geocode-credit">Stored on this device only.</footer>}
    </div>}
  </div>;
}
