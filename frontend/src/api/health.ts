export interface Health {
  status: 'ok' | 'ready';
  version: string;
}

function isHealth(value: unknown): value is Health {
  return typeof value === 'object' && value !== null
    && 'status' in value && (value.status === 'ok' || value.status === 'ready')
    && 'version' in value && typeof value.version === 'string';
}

export async function fetchHealth(signal: AbortSignal): Promise<Health> {
  const base = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1/';
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal.addEventListener('abort', abort, { once: true });
  if (signal.aborted) controller.abort();
  const timeout = setTimeout(abort, 5_000);
  try {
    const response = await fetch(new URL('health/', base.endsWith('/') ? base : base + '/'), {
      signal: controller.signal,
    });
    if (!response.ok) throw new Error('Backend is unreachable.');
    const body: unknown = await response.json();
    if (!isHealth(body)) throw new Error('Backend returned an invalid health response.');
    return body;
  } finally {
    clearTimeout(timeout);
    signal.removeEventListener('abort', abort);
  }
}
