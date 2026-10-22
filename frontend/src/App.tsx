import { lazy, Profiler, Suspense, useEffect, useRef, useState } from 'react';
import { useHealth } from './api/useHealth';
import { BottomSheet } from './components/BottomSheet';
import { IconButton } from './components/controls';
import { Brand } from './components/icons';
import { Popover, Skeleton, StatusBadge } from './components/surfaces';
import { ProgressLine } from './features/trip/TripForm';
import { Console } from './features/results/Console';
import { ADVISORY } from './features/results/ResultsView';
import { SelectionProvider, useSelectionState } from './api/selection-store';
import { useTripPlanner } from './features/trip/useTripPlanner';
import { MapWorkspace } from './features/map/MapWorkspace';
import type { SheetSnap } from './lib/sheet';
import { useMediaQuery } from './lib/motion';
import { ThemeToggle } from './lib/theme';
import { finishArrival } from './lib/arrival';
// The dead DEV branch removes this import and reference samples from release builds.
const StyleGuide = import.meta.env.DEV ? lazy(() => import('./dev/StyleGuide')) : null;
let consoleCommits = 0;
function recordConsoleCommit() { if (import.meta.env.VITE_E2E === 'true') { consoleCommits++; Object.assign(window, { __routeShieldConsoleCommits: consoleCommits }); } }
export { ADVISORY } from './features/results/ResultsView';
export default function App() {
  const health = useHealth(), mobile = useMediaQuery('(max-width: 760px)');
  const planner = useTripPlanner(health, window.location.pathname !== '/style-guide');
  const selection = useSelectionState(), [tab, setTab] = useState('trip');
  const [scrolled, setScrolled] = useState(false), [consoleRequest, revealConsole] = useState(0);
  const [sheetRequest, setSheetRequest] = useState<{ id: number; snap: SheetSnap; focusId?: string }>();
  const revealedSnapshot = useRef(planner.snapshot);
  useEffect(() => {
    if (!mobile) return;
    const field = (['origin', 'destination', 'departure', 'weight', 'spacing'] as const).find(key => planner.errors[key]);
    const fresh = planner.snapshot && planner.snapshot !== revealedSnapshot.current;
    if (planner.busy || fresh || field || planner.error) setSheetRequest(previous => ({ id: (previous?.id ?? 0) + 1, snap: planner.busy ? 'peek' : field || planner.error || fresh ? 'full' : 'half', ...(field ? { focusId: `trip-${field}` } : fresh && !planner.busy ? { focusId: 'results-heading' } : {}) }));
    if (fresh) revealedSnapshot.current = planner.snapshot;
  }, [mobile, planner.busy, planner.snapshot, planner.errors, planner.error]);
  const showConsole = () => { if (mobile) revealConsole(n => n + 1); else document.getElementById('console')?.focus(); };
  if (StyleGuide && window.location.pathname === '/style-guide') return <Suspense fallback={<div className="guide-loading"><Skeleton label="Loading style guide" /></div>}><StyleGuide /></Suspense>;
  const status = health.status === 'checking' ? 'waking' : health.status;
  const text = health.status === 'healthy' ? `API healthy · ${health.version}` : health.status === 'unreachable' ? 'API unreachable' : health.status === 'checking' ? 'Checking API' : 'Waking up';
  return <SelectionProvider value={selection}><div className="app-shell" onPointerDownCapture={finishArrival} onKeyDownCapture={finishArrival}><a className="skip-link" href="#console" onClick={e => { e.preventDefault(); showConsole(); }}>Skip to console</a><header className="shell-header"><Brand /><span className="header-purpose micro">Weather operations</span><div className="header-service" role="status" aria-live="polite"><StatusBadge status={status}>{text}</StatusBadge></div>{health.status === 'unreachable' && <IconButton label="Retry backend health" icon="refresh" onClick={health.retry} />}<div className="header-tools"><ThemeToggle /><Popover label="Sources and planning advisory"><p>{ADVISORY}</p><p className="field-hint">OpenFreeMap basemap credits are always visible on the chart. TomTom display attribution remains flagged unconfirmed.</p></Popover></div></header><main className="shell-main"><MapWorkspace analysis={planner.snapshot?.response ?? null} onSkipMap={showConsole} onRerun={() => planner.submit()} />{mobile ? <div className="sheet-dock"><BottomSheet label="Trip plan" revealRequest={consoleRequest} snapRequest={sheetRequest} peekSummary={planner.busy ? <ProgressLine planner={planner} /> : undefined}><div id="console" tabIndex={-1}><Profiler id="route-console" onRender={recordConsoleCommit}><Console planner={planner} tab={tab} setTab={setTab} /></Profiler></div></BottomSheet></div> : <aside id="console" tabIndex={-1} className={`console-desktop trip-console ${scrolled ? 'is-scrolled' : ''}`} aria-label="Route console" onScrollCapture={e => setScrolled((e.target as HTMLElement).scrollTop > 4)}><Profiler id="route-console" onRender={recordConsoleCommit}><Console planner={planner} tab={tab} setTab={setTab} /></Profiler></aside>}</main></div></SelectionProvider>;
}
