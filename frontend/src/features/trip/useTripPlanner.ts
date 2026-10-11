import { useEffect, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { analyzeTrip } from '../../api/client';
import { ApiError } from '../../api/errors';
import { useAnalysisStore } from '../../api/analysis-store';
import type { useHealth } from '../../api/useHealth';
import type { AnalysisRequest } from '../../api/types';
import { validateDraft, validationFields } from './model';
import type { FieldErrors, PlaceChoice, TripDraft } from './model';
import { browserZone, quickDeparture } from './time';
import { clearHistory, readHistory, readPreferences, rememberPlace, rememberTrip, savePreferences } from './storage';
import type { RecentTrip } from './storage';
import { decodeDraft, markAutoAttempt, updateUrl } from './url';

type Phase = 'idle' | 'waking' | 'running';
interface Operation { request: AnalysisRequest; token: string; draft: TripDraft; abort: AbortController; started: number; launched: boolean }
export function useTripPlanner(health: ReturnType<typeof useHealth>, enabled = true) {
  const [initial] = useState(() => {
    const zone = browserZone(), prefs = readPreferences();
    const base: TripDraft = { origin: { text: '', place: null }, destination: { text: '', place: null }, wall: quickDeparture('default', Date.now(), zone), offset: null, zone, weight: prefs.weight, spacing: prefs.spacing };
    return enabled ? decodeDraft(location.search, base, Date.now()) : { draft: base, complete: false, past: false };
  });
  const [draft, setDraft] = useState(initial.draft), [history, setHistory] = useState(readHistory), [now, setNow] = useState(Date.now());
  const [errors, setErrors] = useState<FieldErrors>({}), [error, setError] = useState<ApiError | null>(null), [notice, setNotice] = useState(initial.past ? "This link's departure time has passed. Update it to analyze." : '');
  const [phase, setPhase] = useState<Phase>('idle'), [elapsed, setElapsed] = useState(0), [retryUntil, setRetryUntil] = useState(0), [secondsLeft, setSecondsLeft] = useState(0), [toast, setToast] = useState('');
  const active = useRef<Operation | null>(null), automatic = useRef(false), mounted = useRef(true);
  const lastOperation = useRef<Operation | null>(null);
  const store = useAnalysisStore();
  const mutation = useMutation({ mutationFn: ({ request, token, signal }: { request: AnalysisRequest; token: string; signal: AbortSignal }) => analyzeTrip(request, signal, token), retry: false, gcTime: 0 });
  const busy = phase !== 'idle';
  const validation = validateDraft(draft, now);
  const focusInvalid = (fields: FieldErrors) => {
    const first = (['origin', 'destination', 'departure', 'weight', 'spacing'] as const).find(field => fields[field]);
    if (first) requestAnimationFrame(() => document.getElementById(`trip-${first}`)?.focus());
  };
  const change = (update: Partial<TripDraft>) => {
    setDraft(previous => ({ ...previous, ...update })); setErrors({}); setError(null); setNotice('');
  };
  const selectPlace = (field: 'origin' | 'destination', place: PlaceChoice) => {
    change({ [field]: { text: place.label, place } }); setHistory(previous => rememberPlace(previous, place));
  };
  const launch = (op: Operation) => {
    if (active.current !== op || op.launched) return;
    const current = validateDraft(op.draft, Date.now());
    if (!current.request) { active.current = null; setPhase('idle'); setErrors(current.errors); focusInvalid(current.errors); return; }
    op.launched = true; setPhase('running'); op.started = Date.now(); setElapsed(0);
    void mutation.mutateAsync({ request: op.request, token: op.token, signal: op.abort.signal }).then(response => {
      if (!mounted.current || active.current !== op) return;
      store.setSnapshot({ response, request: op.request, wallMs: Date.now() - op.started, weightToken: op.token });
      setHistory(previous => rememberTrip(previous, op.draft));
      active.current = null; setPhase('idle');
    }).catch(failure => {
      if (!mounted.current || active.current !== op) return;
      active.current = null; setPhase('idle');
      const failureValue = failure instanceof ApiError ? failure : new ApiError('NETWORK_ERROR');
      if (failureValue.code === 'ABORTED') return;
      setError(failureValue);
      if (failureValue.code === 'VALIDATION_ERROR' || failureValue.code === 'LOCATION_REQUIRES_SELECTION') {
        const fields = validationFields(failureValue.details); setErrors(fields); focusInvalid(fields);
      }
      if (failureValue.code === 'THROTTLED') {
        const seconds = failureValue.retryAfterSeconds ?? 60;
        setRetryUntil(Date.now() + seconds * 1000); setSecondsLeft(seconds);
      }
    });
  };
  const submit = (auto = false) => {
    if (!enabled || active.current || Date.now() < retryUntil) return;
    const current = validateDraft(draft, Date.now());
    setNow(Date.now()); setErrors(current.errors);
    if (!current.request || !current.weightToken) { focusInvalid(current.errors); return; }
    const op: Operation = { request: current.request, token: current.weightToken, draft, abort: new AbortController(), started: Date.now(), launched: false };
    active.current = op; lastOperation.current = op; setError(null); setNotice(''); setElapsed(0);
    if (!auto) updateUrl(draft, true);
    if (health.status === 'healthy') launch(op);
    else { setPhase('waking'); if (health.status === 'unreachable') health.retry(); }
  };
  const cancel = () => { active.current?.abort.abort(); active.current = null; setPhase('idle'); setError(null); mutation.reset(); };
  const retry = () => {
    const last = lastOperation.current;
    if (!last || active.current || Date.now() < retryUntil) return;
    const op = { ...last, abort: new AbortController(), launched: false, started: Date.now() };
    active.current = op; lastOperation.current = op; setError(null); setElapsed(0);
    if (health.status === 'healthy') launch(op);
    else { setPhase('waking'); if (health.status === 'unreachable') health.retry(); }
  };
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; queueMicrotask(() => { if (!mounted.current) active.current?.abort.abort(); }); };
  }, []);
  useEffect(() => {
    if (!enabled) return;
    const timer = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(timer);
  }, [enabled]);
  useEffect(() => {
    if (!enabled) return;
    const timer = setTimeout(() => updateUrl(draft), 400);
    return () => clearTimeout(timer);
  }, [draft, enabled]);
  useEffect(() => { if (enabled) savePreferences(draft.weight, draft.spacing); }, [draft.weight, draft.spacing, enabled]);
  useEffect(() => {
    if (!busy && !retryUntil) return;
    const tick = () => { if (active.current) setElapsed(Math.floor((Date.now() - active.current.started) / 1000)); setSecondsLeft(Math.max(0, Math.ceil((retryUntil - Date.now()) / 1000))); if (retryUntil && Date.now() >= retryUntil) setRetryUntil(0); };
    const timer = setInterval(tick, 1000); tick();
    return () => clearInterval(timer);
  }, [busy, retryUntil]);
  useEffect(() => {
    const op = active.current;
    if (!op || phase !== 'waking') return;
    if (health.status === 'healthy') launch(op);
    else if (health.status === 'unreachable') { active.current = null; setPhase('idle'); setError(new ApiError('NETWORK_ERROR')); }
  }, [health.status, phase]);
  useEffect(() => {
    if (automatic.current || !enabled) return;
    automatic.current = true;
    if (initial.complete && !initial.past && markAutoAttempt(initial.draft)) submit(true);
  }, [enabled]);
  const swap = () => change({ origin: draft.destination, destination: draft.origin });
  const restore = (trip: RecentTrip) => change({ origin: { text: trip.origin.label, place: trip.origin }, destination: { text: trip.destination.label, place: trip.destination }, weight: trip.weight, spacing: trip.spacing });
  const clear = () => { setHistory(clearHistory()); setToast('History cleared from this device.'); };
  return { draft, change, selectPlace, swap, restore, history, clear, validation, errors, error, notice, phase, busy, elapsed, secondsLeft, submit, retry, cancel, toast, setToast, snapshot: store.snapshot, now };
}
export type TripPlanner = ReturnType<typeof useTripPlanner>;
