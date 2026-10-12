import { useEffect } from 'react';
import type { AnalysisResponse } from '../../api/types';
import { useSelection } from '../../api/selection-store';
import { Inspector } from './Inspector';
import { RiskProfile } from './RiskProfile';
import './checkpoints.css';
export { InspectorDock } from './Inspector';
export default function ProfileView({ response }: { response: AnalysisResponse }) {
  const selection = useSelection(), route = response.routes.find(r => r.route_id === selection.selectedRouteId);
  useEffect(() => { if (route && selection.selectedCheckpointIndex === null) selection.selectCheckpoint(route.checkpoints[0]?.index ?? null); }, [route, selection.selectCheckpoint]);
  if (!route) return <p>Select a route to inspect its profile.</p>;
  const cp = route.checkpoints.find(c => c.index === selection.selectedCheckpointIndex);
  return <><RiskProfile route={route} response={response} />{cp ? <Inspector response={response} route={route} checkpoint={cp} /> : <p>Select a checkpoint to inspect its weather and rules.</p>}</>;
}
