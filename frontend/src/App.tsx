import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { useHealth } from './api/useHealth';
import { BottomSheet } from './components/BottomSheet';
import { IconButton } from './components/controls';
import { Brand, Icon } from './components/icons';
import { Popover, Skeleton, StatusBadge } from './components/surfaces';
import { ProgressLine } from './features/trip/TripForm';
import { Console } from './features/results/Console';
import { ADVISORY } from './features/results/ResultsView';
import { SelectionProvider, useSelectionState } from './api/selection-store';
import { useTripPlanner } from './features/trip/useTripPlanner';
import type { SheetSnap } from './lib/sheet';
import { useMediaQuery } from './lib/motion';
import { ThemeToggle } from './lib/theme';
// The dead DEV branch removes this import and reference samples from release builds.
const StyleGuide = import.meta.env.DEV ? lazy(() => import('./dev/StyleGuide')) : null;
export { ADVISORY } from './features/results/ResultsView';
function MapWorkspace({ analyzed, selected }: { analyzed: boolean; selected?: string | null }) {
  return <section className="map-workspace" aria-label="Map workspace"><svg className="topography" viewBox="0 0 1000 800" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><g fill="none" stroke="currentColor" strokeWidth=".7">{Array.from({ length: 14 }, (_, i) => <path key={i} d={`M${-160 + i * 18} -50C${90 + i * 18} ${190 + i * 14} ${690 + i * 8} ${20 + i * 19} ${980 + i * 11} 340S${680 + i * 21} ${560 + i * 13} ${510 + i * 17} 850`} />)}{Array.from({ length: 6 }, (_, i) => <path key={`b${i}`} d={`M-40 ${460 + i * 24}C230 ${390 + i * 21} 450 ${850 - i * 13} 1020 ${680 - i * 24}`} />)}</g></svg><div className="map-placeholder"><span className="workspace-cross" aria-hidden="true" /><p className="micro">{import.meta.env.DEV ? 'Development placeholder' : 'Map unavailable'}</p><h2>Map workspace</h2><p>{analyzed ? `Analysis received${selected ? ' · route selected' : ''}. Map display is not connected yet.` : 'Enter a trip in the console to assess the corridor.'}</p></div></section>;
}
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
    if (planner.busy || fresh || field || planner.error) setSheetRequest(previous => ({ id: (previous?.id ?? 0) + 1, snap: planner.busy ? 'peek' : field || planner.error ? 'full' : 'half', ...(field ? { focusId: `trip-${field}` } : fresh && !planner.busy ? { focusId: 'results-heading' } : {}) }));
    if (fresh) revealedSnapshot.current = planner.snapshot;
  }, [mobile, planner.busy, planner.snapshot, planner.errors, planner.error]);
  if (StyleGuide && window.location.pathname === '/style-guide') return <Suspense fallback={<div className="guide-loading"><Skeleton label="Loading style guide" /></div>}><StyleGuide /></Suspense>;
  const status = health.status === 'checking' ? 'waking' : health.status;
  const text = health.status === 'healthy' ? `API healthy · ${health.version}` : health.status === 'unreachable' ? 'API unreachable' : health.status === 'checking' ? 'Checking API' : 'Waking up';
  return <SelectionProvider value={selection}><div className="app-shell"><a className="skip-link" href="#console" onClick={e => { e.preventDefault(); if (mobile) revealConsole(n => n + 1); else document.getElementById('console')?.focus(); }}>Skip to console</a><header className="shell-header"><Brand /><span className="header-purpose micro">Weather operations</span><div className="header-service" role="status" aria-live="polite"><StatusBadge status={status}>{text}</StatusBadge></div>{health.status === 'unreachable' && <IconButton label="Retry backend health" icon="refresh" onClick={health.retry} />}<div className="header-tools"><ThemeToggle /><Popover label="Sources and planning advisory"><p>{ADVISORY}</p><p className="field-hint">No basemap is displayed. Provider attribution accompanies the data it credits.</p></Popover></div></header><main className="shell-main"><MapWorkspace analyzed={!!planner.snapshot} selected={selection.selectedRouteId} />{mobile ? <div className="sheet-dock"><BottomSheet label="Trip plan" revealRequest={consoleRequest} snapRequest={sheetRequest} peekSummary={planner.busy ? <ProgressLine planner={planner} /> : undefined}><div id="console" tabIndex={-1}><Console planner={planner} tab={tab} setTab={setTab} /></div></BottomSheet></div> : <aside id="console" tabIndex={-1} className={`console-desktop trip-console ${scrolled ? 'is-scrolled' : ''}`} aria-label="Route console" onScrollCapture={e => setScrolled((e.target as HTMLElement).scrollTop > 4)}><Console planner={planner} tab={tab} setTab={setTab} /></aside>}<footer className="map-attribution"><span className="attribution-source"><Icon name="layers" />No basemap loaded</span><p>{ADVISORY}</p></footer></main></div></SelectionProvider>;
}
