import type { ReasonCode, RiskReason, UnavailableReason } from '../../api/types';
import { decimal } from '../../lib/format';
import { riskPresentation } from '../../components/surfaces';

const METRICS: Record<string, [string, string]> = { wind_mph: ['Wind', 'mph'], rain_in_per_hour: ['Rain', 'in/hr'], snow_in_per_hour: ['Snow', 'in/hr'], load_weight_lb: ['Cargo', 'lb'] };
const metric = (name: string) => METRICS[name] ?? [name, ''];
const level = (r: RiskReason) => riskPresentation[r.level].label;
const evidence = (r: RiskReason) => r.threshold === null ? '' : ` (${r.comparison ?? ''} ${decimal(r.threshold)} ${metric(r.metric)[1]}).`;
const load = (r: RiskReason) => `Wind ${decimal(r.wind_mph)} mph is ${r.band ? riskPresentation[r.band.level].label : 'unavailable'}; with cargo ${decimal(r.load_weight_lb)} lb, the API load rule gives ${level(r)}${evidence(r)}`;
// Every template restates supplied evidence. No thresholds or classification here.
export const REASON_TEMPLATES = {
  HAZARD_CLASSIFIED: (r: RiskReason) => `${metric(r.metric)[0]} ${decimal(r.measured_value)} ${metric(r.metric)[1]} is ${level(r)}${evidence(r)}`,
  MISSING_HAZARD: (r: RiskReason) => `${metric(r.metric)[0]} is unavailable; the full assessment is incomplete.`,
  EXTREME_WIND_ANY_LOAD: (r: RiskReason) => `Wind ${decimal(r.wind_mph ?? r.measured_value)} mph is ${level(r)} for any cargo load${evidence(r)}`,
  SEVERE_WIND_HEAVY_LOAD: load,
  HIGH_WIND_HEAVY_LOAD: load,
  LOAD_RULES_UNAVAILABLE_MISSING_WIND: () => 'Wind is unavailable, so the load rules cannot be evaluated.',
  LOAD_RULES_UNAVAILABLE_MISSING_LOAD: () => 'Cargo weight is unavailable, so the load rules cannot be fully evaluated.',
  MISSING_LOAD: () => 'Cargo weight is unavailable; the full assessment is incomplete.',
} satisfies Record<ReasonCode, (r: RiskReason) => string>;
export function reasonText(reason: RiskReason): string {
  const template = (REASON_TEMPLATES as Record<string, ((r: RiskReason) => string) | undefined>)[reason.code];
  return template ? template(reason) : `Unrecognized rule ${reason.code}: ${decimal(reason.measured_value)} ${reason.metric}; reported level ${level(reason)}.`;
}
export const UNAVAILABLE: Record<UnavailableReason, { title: string; text: string }> = {
  OUT_OF_HORIZON: { title: 'Beyond forecast coverage', text: 'The checkpoint arrival is outside available forecast coverage. Conditions here are unassessed; choose an earlier departure or recheck when forecasts extend.' },
  MISSING_HOUR: { title: 'Forecast hour missing', text: 'The required forecast hour is absent. Nearby hours cannot stand in for it; conditions here are unassessed.' },
  MISSING_FIELD: { title: 'Weather measurement missing', text: 'A required measurement is missing or invalid. Known observations remain visible, but the full assessment is incomplete.' },
  PAST_TIME: { title: 'Forecast time has passed', text: 'The required forecast time is in the past and unavailable. Re-analyze with a current departure.' },
  PROVIDER_FAILURE: { title: 'Weather service unavailable', text: 'The weather service could not supply this checkpoint. Re-run later; missing conditions are not safe conditions.' },
  QUOTA_EXCEEDED: { title: 'Weather quota exhausted', text: 'The weather provider refused further work because of its quota. This checkpoint is unassessed; retry when quota is available.' },
  DEMO_QUOTA_REACHED: { title: 'Demo weather allowance reached', text: 'The demo guard stopped additional weather work. This checkpoint is unassessed; ask the operator when the demo allowance resets.' },
};
export const loadEscalated = (r: { reasons: RiskReason[]; wind_risk: string; load_adjusted_wind_risk: string }) => r.wind_risk !== r.load_adjusted_wind_risk && r.reasons.some(reason => ['SEVERE_WIND_HEAVY_LOAD', 'HIGH_WIND_HEAVY_LOAD'].includes(reason.code));
