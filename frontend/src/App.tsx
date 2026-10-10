import { useQuery } from '@tanstack/react-query';
import { fetchHealth } from './api/health';

export default function App() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => fetchHealth(signal),
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    staleTime: Infinity,
  });

  return (
    <main>
      <h1>RouteShield</h1>
      <p>Project foundation</p>
      <section aria-labelledby="health-heading">
        <h2 id="health-heading">Backend health</h2>
        {health.isPending && <p role="status">Loading backend health…</p>}
        {health.isSuccess && (
          <p role="status">Healthy — version {health.data.version}</p>
        )}
        {health.isError && <p role="alert">Backend unreachable.</p>}
        <button
          type="button"
          disabled={health.isFetching}
          onClick={() => { void health.refetch(); }}
        >
          Check again
        </button>
      </section>
    </main>
  );
}
