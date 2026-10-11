import { ApiError } from '../api/errors';
import { ErrorState } from './surfaces';
export function AnalysisError({ error, retry, edit, secondsLeft = 0 }: { error: ApiError; retry: () => void; edit: () => void; secondsLeft?: number }) {
  const max = error.details.max_distance_miles;
  const quota = error.code === 'QUOTA_EXCEEDED' && Object.values(error.details).includes('DEMO_QUOTA_REACHED');
  const message = error.code === 'TRIP_TOO_LARGE' ? typeof max === 'number' && Number.isFinite(max) ? `This demo supports up to ${max.toLocaleString('en-US')} road miles. Choose closer endpoints or use an example trip.` : 'This trip exceeds the supported range. Choose closer endpoints or use an example trip.' : quota ? 'Demo weather quota reached; try again after the quota window resets.' : error.presentation.message;
  const timeout = ['DEADLINE_EXCEEDED', 'PROVIDER_TIMEOUT', 'NETWORK_ERROR'].includes(error.code);
  const recover = () => {
    if (error.presentation.recovery === 'reload') location.reload();
    else if (error.presentation.recovery === 'support') { const id = document.querySelector<HTMLInputElement>('.error-state input[aria-label="Request ID"]'); id?.focus(); id?.select(); }
    else if (['edit', 'live'].includes(error.presentation.recovery)) edit();
    else retry();
  };
  return <ErrorState title={error.presentation.title} action={timeout ? 'Retry' : error.code === 'TRIP_TOO_LARGE' ? 'Choose an example trip' : error.presentation.action} onRecover={recover} requestId={error.requestId} disabled={secondsLeft > 0}>{message}{secondsLeft > 0 && <span className="retry-count">Retry available in <span className="mono">{secondsLeft}s</span></span>}</ErrorState>;
}
