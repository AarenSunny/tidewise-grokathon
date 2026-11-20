import { useEffect, useState } from 'react';
import { API_BASE_URL } from '../lib/api';

type State =
  | { status: 'checking' }
  | { status: 'ok'; health: string; spots: string[] }
  | { status: 'error'; error: string };

// Production check carried over from main (PR #6): proves the deployed
// frontend can reach the backend's /health and /spots.
export function ApiStatus() {
  const [state, setState] = useState<State>({ status: 'checking' });

  useEffect(() => {
    Promise.all([fetch(`${API_BASE_URL}/health`), fetch(`${API_BASE_URL}/spots`)])
      .then(async ([h, s]) => {
        if (!h.ok || !s.ok) throw new Error(`HTTP ${h.status} / ${s.status}`);
        const health = (await h.json()) as { status: string };
        const spots = (await s.json()) as { spots: { name: string }[] };
        setState({ status: 'ok', health: health.status, spots: spots.spots.map((x) => x.name) });
      })
      .catch((err: unknown) => setState({ status: 'error', error: String(err) }));
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
