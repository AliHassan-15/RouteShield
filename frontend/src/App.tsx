import { lazy, Suspense, useState } from 'react';
import { useHealth } from './api/useHealth';
import { BottomSheet } from './components/BottomSheet';
import { Button, IconButton } from './components/controls';
import { Brand, Icon } from './components/icons';
import { EmptyState, Panel, Popover, Skeleton, StatusBadge, TickDivider } from './components/surfaces';
import { useMediaQuery } from './lib/motion';
import { ThemeToggle } from './lib/theme';

// The dead DEV branch removes this import and reference samples from release builds.
const StyleGuide = import.meta.env.DEV ? lazy(() => import('./dev/StyleGuide')) : null;
export const ADVISORY = 'Weather-based planning aid. Forecasts and truck restrictions may be incomplete; verify conditions and road restrictions before travel.';

function MapWorkspace() {
  return <section className="map-workspace" aria-label="Map workspace"><svg className="topography" viewBox="0 0 1000 800" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><g fill="none" stroke="currentColor" strokeWidth=".7">{Array.from({ length: 14 }, (_, i) => <path key={i} d={`M${-160 + i * 18} -50C${90 + i * 18} ${190 + i * 14} ${690 + i * 8} ${20 + i * 19} ${980 + i * 11} 340S${680 + i * 21} ${560 + i * 13} ${510 + i * 17} 850`} />)}{Array.from({ length: 6 }, (_, i) => <path key={`b${i}`} d={`M-40 ${460 + i * 24}C230 ${390 + i * 21} 450 ${850 - i * 13} 1020 ${680 - i * 24}`} />)}</g></svg><div className="map-placeholder"><span className="workspace-cross" aria-hidden="true" /><p className="micro">{import.meta.env.DEV ? 'Development placeholder' : 'Map unavailable'}</p><h2>Map workspace</h2><p>No route or forecast data is loaded.</p></div></section>;
}
function Console({ status, onRetry }: { status: ReturnType<typeof useHealth>['status']; onRetry: () => void }) {
  return <div className="console-body"><Panel eyebrow="Weather operations" title="Route console"><TickDivider label="Planning" /><EmptyState title="Conditions before commitment" icon="route">Compare routes by weather, load and travel time. Trip planning is not available yet.</EmptyState></Panel><TickDivider label="Connection" /><div className="console-connection"><p className="micro">Backend service</p>{status === 'checking' || status === 'waking' ? <><Skeleton label={status === 'waking' ? 'Waking up the backend' : 'Checking backend health'} lines={2} /><p className="field-hint">{status === 'waking' ? 'The free host may be starting. This check stops within 90 seconds.' : 'Checking service availability.'}</p></> : status === 'unreachable' ? <><p className="field-hint">The backend could not be reached. Check the connection and try again.</p><Button onClick={onRetry}><Icon name="refresh" />Check again</Button></> : <p className="field-hint">Service ready. No route analysis has been submitted.</p>}</div></div>;
}
export default function App() {
  const health = useHealth(), mobile = useMediaQuery('(max-width: 760px)');
  const [scrolled, setScrolled] = useState(false), [consoleRequest, revealConsole] = useState(0);
  if (StyleGuide && window.location.pathname === '/style-guide') return <Suspense fallback={<div className="guide-loading"><Skeleton label="Loading style guide" /></div>}><StyleGuide /></Suspense>;
  const status = health.status === 'checking' ? 'waking' : health.status;
  const text = health.status === 'healthy' ? `API healthy · ${health.version}` : health.status === 'unreachable' ? 'API unreachable' : health.status === 'checking' ? 'Checking API' : 'Waking up';
  return <div className="app-shell"><a className="skip-link" href="#console" onClick={e => { e.preventDefault(); if (mobile) revealConsole(n => n + 1); else document.getElementById('console')?.focus(); }}>Skip to console</a><header className="shell-header"><Brand /><span className="header-purpose micro">Weather operations</span><div className="header-service" role="status" aria-live="polite"><StatusBadge status={status}>{text}</StatusBadge></div>{health.status === 'unreachable' && <IconButton label="Retry backend health" icon="refresh" onClick={health.retry} />}<div className="header-tools"><ThemeToggle /><Popover label="Sources and planning advisory"><p>{ADVISORY}</p><p className="field-hint">No route, weather or basemap data is loaded. Provider attribution will accompany the data it credits.</p></Popover></div></header><main className="shell-main"><MapWorkspace />{mobile ? <div className="sheet-dock"><BottomSheet revealRequest={consoleRequest}><div id="console" tabIndex={-1}><Console status={health.status} onRetry={health.retry} /></div></BottomSheet></div> : <aside id="console" tabIndex={-1} className={`console-desktop ${scrolled ? 'is-scrolled' : ''}`} aria-label="Route console" onScroll={e => setScrolled(e.currentTarget.scrollTop > 4)}><Console status={health.status} onRetry={health.retry} /><div className="console-footnote"><Icon name="info" /><span>Continuous-driving estimates. Verify truck restrictions before departure.</span></div></aside>}<footer className="map-attribution"><span className="attribution-source"><Icon name="layers" />No basemap loaded</span><p>{ADVISORY}</p></footer></main></div>;
}
