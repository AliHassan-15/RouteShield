import type { Checkpoint } from '../../api/types';
import { arrival, decimal, miles } from '../../lib/format';
import { riskPresentation } from '../../components/surfaces';
export function tooltipContent(cp: Checkpoint) {
  const v = cp.weather.values;
  return { title: `Mile ${miles(cp.mile_marker)} · ${arrival(cp).local}`, risk: riskPresentation[cp.risk.final_risk].label,
    weather: `Wind ${decimal(v.wind_mph)} mph · Rain ${decimal(v.rain_in_hr)} in/hr · Snow ${decimal(v.snow_in_hr)} in/hr`,
    unavailable: cp.risk.final_risk === 'UNKNOWN' ? (cp.weather.unavailable_reason?.replaceAll('_', ' ').toLowerCase() ?? `Missing ${cp.weather.missing_fields.join(', ') || 'required weather'}`) : null };
}
