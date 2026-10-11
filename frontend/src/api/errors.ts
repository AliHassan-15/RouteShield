import type { ErrorCode, ErrorValue } from './types';

export const errorMessages = {
  VALIDATION_ERROR: { title: 'Check trip details', message: 'Review the highlighted inputs before trying again.', action: 'Review inputs', recovery: 'edit' },
  PAYLOAD_TOO_LARGE: { title: 'Request too large', message: 'Shorten the location labels and submit again.', action: 'Review inputs', recovery: 'edit' },
  UNSUPPORTED_MEDIA_TYPE: { title: 'Request format unavailable', message: 'Reload this view to restore the supported request format.', action: 'Reload view', recovery: 'reload' },
  LOCATION_REQUIRES_SELECTION: { title: 'Select a location', message: 'Choose a confirmed origin and destination from the location results.', action: 'Choose locations', recovery: 'edit' },
  NO_ROUTE: { title: 'No truck route found', message: 'Check the endpoints or choose a different corridor.', action: 'Change endpoints', recovery: 'edit' },
  TRIP_TOO_LARGE: { title: 'Trip exceeds the supported range', message: 'Choose closer endpoints or a wider offered checkpoint spacing.', action: 'Shorten trip', recovery: 'edit' },
  THROTTLED: { title: 'Request limit reached', message: 'Wait for the request window to reset before trying again.', action: 'Wait and retry', recovery: 'wait' },
  DEADLINE_EXCEEDED: { title: 'Analysis time limit reached', message: 'The analysis could not finish in its allotted time. A shorter corridor may help.', action: 'Retry or shorten trip', recovery: 'retry' },
  PROVIDER_TIMEOUT: { title: 'Data source timed out', message: 'A required source did not respond in time.', action: 'Retry request', recovery: 'retry' },
  PROVIDER_UNAVAILABLE: { title: 'Data source unavailable', message: 'A required source is temporarily unavailable.', action: 'Retry request', recovery: 'retry' },
  QUOTA_EXCEEDED: { title: 'Source allowance reached', message: 'The data allowance is exhausted. Try after it resets.', action: 'Wait for reset', recovery: 'wait' },
  PROVIDER_AUTH: { title: 'Data access needs attention', message: 'The service operator needs to restore access to a required source.', action: 'Contact support', recovery: 'support' },
  MALFORMED_PROVIDER_RESPONSE: { title: 'Source data could not be read', message: 'A required source returned unusable data.', action: 'Retry request', recovery: 'retry' },
  INTERNAL_ERROR: { title: 'Analysis interrupted', message: 'An unexpected service error interrupted this request.', action: 'Retry request', recovery: 'retry' },
  METHOD_NOT_ALLOWED: { title: 'Request method unavailable', message: 'Reload this view to restore the supported request method.', action: 'Reload view', recovery: 'reload' },
  NOT_FOUND: { title: 'Service endpoint unavailable', message: 'The requested service endpoint could not be found.', action: 'Reload view', recovery: 'reload' },
  SIMULATION_DISABLED: { title: 'Simulation is disabled', message: 'Use live weather for this analysis.', action: 'Use live weather', recovery: 'live' },
  INVALID_SCENARIO: { title: 'Select a simulation preset', message: 'Choose one of the available weather presets.', action: 'Choose preset', recovery: 'edit' },
} satisfies Record<ErrorCode, { title: string; message: string; action: string; recovery: string }>;
export type ClientErrorCode = 'NETWORK_ERROR' | 'INVALID_RESPONSE' | 'ABORTED';
export class ApiError extends Error {
  readonly name = 'ApiError';
  constructor(readonly code: ErrorCode | ClientErrorCode, readonly status = 0, readonly details: Record<string, ErrorValue> = {}, readonly requestId?: string, readonly retryAfterSeconds?: number) {
    super(code in errorMessages ? errorMessages[code as ErrorCode].message : code === 'ABORTED' ? 'Request cancelled.' : code === 'INVALID_RESPONSE' ? 'The service returned an unreadable response.' : 'The backend could not be reached.');
  }
  get presentation() {
    if (this.code in errorMessages) return errorMessages[this.code as ErrorCode];
    return { title: this.code === 'ABORTED' ? 'Request cancelled' : 'Connection unavailable', message: this.message, action: 'Check connection and retry', recovery: 'retry' };
  }
}
export function isErrorCode(value: unknown): value is ErrorCode {
  return typeof value === 'string' && Object.hasOwn(errorMessages, value);
}
