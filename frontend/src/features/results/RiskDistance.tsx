import type { Route, RouteSummary } from '../../api/types';
import { RiskBadge, riskPresentation } from '../../components/surfaces';
import { displayNumber, miles } from '../../lib/format';
import { LEVELS, stripSegments } from './presentation';

export function RiskDistance({ summary }: { summary: RouteSummary }) {
  const segments = LEVELS.map(level => ({ level, value: summary.miles_by_level[level], width: displayNumber(summary.miles_by_level[level]) ?? 0 })).filter(s => s.width > 0);
  return <div className="risk-distance"><div className="distance-bar" role="img" aria-label={`Risk miles: ${segments.map(s => `${riskPresentation[s.level].label} ${miles(s.value)} mi`).join(', ')}`}>{segments.map(s => <span key={s.level} data-level={s.level} className={`distance-segment risk-${riskPresentation[s.level].token}`} style={{ flexGrow: s.width, minWidth: 3 }} />)}</div><div className="distance-scale mono" aria-hidden="true"><span>0</span><i /><i /><i /><span>{miles(summary.total_miles)} mi</span></div><div className="distance-legend">{segments.map(s => <span key={s.level}><RiskBadge level={s.level} /><span className="mono">{miles(s.value)} mi</span></span>)}</div></div>;
}
export function MiniRiskStrip({ route }: { route: Route }) {
  const segments = stripSegments(route);
  return <div className="mini-strip" role="img" aria-label={`Checkpoint risk strip, ${route.checkpoints.length} checkpoints`}>{segments.map(s => <span key={s.id} data-level={s.level} className={`distance-segment risk-${riskPresentation[s.level].token}`} style={{ flexGrow: s.miles }}><i /></span>)}</div>;
}
