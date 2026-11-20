import { useEffect, useState } from 'react';
import { API_BASE_URL, fetchHealth, fetchSpots } from '../lib/api';

type State =
  | { status: 'checking' }
  | { status: 'ok'; health: string; spots: string[] }
  | { status: 'error'; error: string };

// Production check carried over from main (PR #6 / PR #8): proves the
// deployed frontend can reach the backend's /health and /spots.
export function ApiStatus() {
  const [state, setState] = useState<State>({ status: 'checking' });

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetchHealth(controller.signal),
      fetchSpots(controller.signal),
    ])
      .then(([health, spots]) => {
        if (controller.signal.aborted) return;
        setState({
          status: 'ok',
          health: health.status,
          spots: spots.spots.map((spot) => spot.name),
        });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setState({ status: 'error', error: String(err) });
      });
    return () => controller.abort();
  }, []);

  return (
    <p className="mt-2 font-mono text-[11px] text-navy-500" data-testid="api-status">
      Backend ({API_BASE_URL || 'local proxy'}):{' '}
      {state.status === 'checking' && 'checking…'}
      {state.status === 'ok' &&
        `connected, health ${state.health}, ${state.spots.length} spots (${state.spots.join(', ')})`}
      {state.status === 'error' && `unreachable (${state.error})`}
    </p>
  );
}
