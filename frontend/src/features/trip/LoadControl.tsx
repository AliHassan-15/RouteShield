import { Input, SegmentedControl } from '../../components/controls';
import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from '../../lib/motion';
import { MAX_WEIGHT_LB } from './config';
import { WIND_RULE_COPY } from './display-copy';
import { aboveWeight, parseWeight, weightReadout } from './weight';

function WindHelper({ applicable }: { applicable: boolean[] }) {
  const reduced = useReducedMotion(), previous = useRef(applicable), [outgoing, setOutgoing] = useState<boolean[] | null>(null);
  const key = applicable.join('-');
  useEffect(() => {
    if (previous.current.join('-') === key) return;
    if (!reduced) setOutgoing(previous.current);
    previous.current = applicable;
    const timer = setTimeout(() => setOutgoing(null), reduced ? 0 : 240);
    return () => clearTimeout(timer);
  }, [key, reduced]);
  const copy = (enabled: boolean[]) => WIND_RULE_COPY.filter((_, i) => enabled[i]).map(rule => <p key={rule.wind}>{rule.text}</p>);
  return <div className="wind-helper" aria-label="Wind rules for current cargo weight"><p className="micro">Assignment wind rules</p><div className="wind-helper-content"><div className="wind-helper-measure" aria-hidden="true">{copy([true, true, true])}</div><div key={key} className="wind-helper-current">{copy(applicable)}</div>{outgoing && <div className="wind-helper-outgoing" aria-hidden="true">{copy(outgoing)}</div>}</div></div>;
}

export function LoadControl({ value, onChange, error }: { value: string; onChange: (value: string) => void; error?: string }) {
  const parsed = parseWeight(value), applicable = WIND_RULE_COPY.map(rule => rule.aboveWeight === null || aboveWeight(parsed, rule.aboveWeight));
  return <div className="load-control"><div className="load-readout"><span className="metric-number mono">{weightReadout(value)}</span><span className="unit">lb</span></div><Input id="trip-weight" label="Cargo weight" inputMode="decimal" autoComplete="off" value={value} onChange={e => onChange(e.target.value)} suffix="lb" error={error} hint="Cargo only · 0 to 100,000 lb" />
    <div className="weight-instrument"><label className="sr-only" htmlFor="trip-weight-slider">Cargo weight slider</label><input id="trip-weight-slider" type="range" min={0} max={MAX_WEIGHT_LB} step="any" value={parsed?.numeric ?? 0} onChange={e => onChange(e.target.value)} aria-valuetext={`${weightReadout(value)} pounds`} />
      <div className="weight-ticks" aria-hidden="true">{Array.from({ length: 41 }, (_, index) => <span key={index} className={index % 4 === 0 ? 'major' : ''} style={{ left: `${index / 40 * 100}%` }} />)}{WIND_RULE_COPY.filter(rule => rule.aboveWeight !== null).map(rule => <span key={rule.aboveWeight} className={`threshold-tick ${aboveWeight(parsed, rule.aboveWeight!) ? 'is-active' : ''}`} style={{ left: `${rule.aboveWeight! / MAX_WEIGHT_LB * 100}%` }}><i /><small className="mono">{rule.aboveWeight! / 1000}k</small></span>)}</div>
      <div className="weight-major-labels mono" aria-hidden="true">{Array.from({ length: 11 }, (_, index) => <span key={index}>{index * 10}k</span>)}</div>
    </div>
    <SegmentedControl label="Cargo presets" value={parsed?.token ?? ''} options={[10_000, 30_000, 45_000, 80_000].map(weight => ({ value: String(weight), label: weight.toLocaleString('en-US') }))} onChange={onChange} />
    <WindHelper applicable={applicable} />
    <table className="wind-rule-table"><caption className="sr-only">Wind rule applicability; display only</caption><thead><tr><th>Wind</th><th>Load</th><th>Effect</th></tr></thead><tbody>{WIND_RULE_COPY.map((rule, index) => <tr key={rule.wind} className={applicable[index] ? 'is-applicable' : ''}><td className="mono">{rule.wind}</td><td className="mono">{rule.aboveWeight === null ? 'Any' : `>${rule.aboveWeight.toLocaleString('en-US')}`}</td><td>{rule.effect}<span className="sr-only">{applicable[index] ? ', applies' : ', does not apply'}</span></td></tr>)}</tbody></table>
  </div>;
}
