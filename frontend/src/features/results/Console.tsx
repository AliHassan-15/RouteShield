import { lazy, Suspense, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Tabs, Button } from '../../components/controls';
import { AnalysisError } from '../../components/AnalysisError';
import { useSelection, useSelectionStore } from '../../api/selection-store';
import type { TripPlanner } from '../trip/useTripPlanner';
import { TripForm, ProgressLine } from '../trip/TripForm';
import { eligibleRecommended, routeLabels } from './presentation';
import { ResultsView, ResultsSkeleton, readResultsSubView } from './ResultsView';
const InspectorDock = lazy(() => import('../checkpoints/CheckpointViews').then(module => ({ default: module.InspectorDock })));
import './results.css';

export function Console({ planner, tab, setTab }: { planner: TripPlanner; tab: string; setTab: (tab: string) => void }) {
  const heading = useRef<HTMLHeadingElement>(null), latest = useRef<TripPlanner['snapshot']>(null), { selectRoute } = useSelection();
  const [announcement, announce] = useState('');
  const [view, setView] = useState(readResultsSubView);
  const store = useSelectionStore();
  const focusPending = useRef(false);
  useEffect(() => {
    if (!planner.snapshot || planner.snapshot === latest.current) return;
    const firstMount = latest.current === null;
    latest.current = planner.snapshot; focusPending.current = true; setTab('results');
    const response = planner.snapshot.response, winner = eligibleRecommended(response);
    // Desktop/mobile remounts retain the current analysis selection. A genuinely
    // new snapshot still resets to the server recommendation.
    if (!firstMount || !response.routes.some(r => r.route_id === store.getState().selectedRouteId)) selectRoute(winner?.route_id ?? null);
    announce(`${response.message}${winner ? ` · ${routeLabels(response).get(winner.route_id)}` : ''}`);
  }, [planner.snapshot, setTab, selectRoute, store]);
  useLayoutEffect(() => {
    if (tab !== 'results' || !focusPending.current) return;
    focusPending.current = false;
    // Focusing during the commit forces a full style/layout pass while map layers
    // and results are being installed. Let their first paint finish first.
    const previous = document.activeElement;
    let frame = requestAnimationFrame(() => { frame = requestAnimationFrame(() => {
      // Never steal focus from input made during these two frames.
      if (document.activeElement !== previous && document.activeElement !== document.body) return;
      heading.current?.focus({ preventScroll: true });
      const scroll = heading.current?.closest('.results-scroll');
      if (scroll) scroll.scrollTop = 0;
    }); });
    return () => cancelAnimationFrame(frame);
  }, [tab, planner.snapshot]);
  const snapshot = planner.snapshot;
  const changed = !!snapshot && (!planner.validation.request || JSON.stringify({ ...planner.validation.request, load_weight_lb: planner.validation.weightToken }) !== JSON.stringify({ ...snapshot.request, load_weight_lb: snapshot.weightToken ?? String(snapshot.request.load_weight_lb) }));
  const edit = () => { setTab('trip'); requestAnimationFrame(() => document.getElementById('trip-origin')?.focus()); };
  return <div className="analysis-console"><span className="sr-only" role="status" aria-live="polite">{announcement}</span><Tabs label="Route console" activeId={tab} onChange={setTab} tabs={[
    { id: 'trip', label: 'Trip', content: <TripForm planner={planner} /> },
    { id: 'results', label: 'Results', disabled: !snapshot, content: <div className="results-panel"><div className="results-scroll"><header className="results-heading"><div><p className="micro">Dispatch assessment</p><h2 ref={heading} id="results-heading" tabIndex={-1}>Results</h2></div><Button variant="ghost" onClick={edit}>Edit trip</Button></header>{planner.busy && <><p className="info-note">{planner.phase === 'waking' ? 'Waking backend. Analysis starts when ready.' : 'Routing, forecasting and scoring.'}</p><div className="console-state"><ResultsSkeleton /></div></>}{!planner.busy && planner.error && <div className="console-state"><AnalysisError error={planner.error} retry={planner.retry} edit={edit} secondsLeft={planner.secondsLeft} /></div>}{snapshot && <div hidden={planner.busy || !!planner.error}><ResultsView key={snapshot.response.analysis_id} snapshot={snapshot} rerun={planner.submit} disabled={planner.busy || planner.secondsLeft > 0} changed={changed} view={view} onViewChange={setView} /></div>}</div>{snapshot && !planner.busy && !planner.error && view !== 'profile' && <Suspense fallback={null}><InspectorDock response={snapshot.response} /></Suspense>}{planner.busy && <div className="results-progress"><ProgressLine planner={planner} /><p className="field-hint">{planner.elapsed >= 8 ? 'Still working. The weather service can be slow.' : 'The shared analysis deadline is 35 seconds.'}</p></div>}</div> },
  ]} /></div>;
}
