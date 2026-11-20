import type {
  Activity,
  HealthResponse,
  QueryResponse,
  RecommendResponse,
  ScoreWindowResponse,
  SpotsResponse,
} from '../types';

/**
 * Default to '' (same-origin) so Vite's dev proxy forwards
 * /recommend, /score, /health, /spots, /query to http://localhost:8000.
 * Set VITE_API_URL (used by the Vercel deploy) or VITE_API_BASE_URL to point at a deployed backend.
 */
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  ''
).replace(/\/+$/, '');

async function requestJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw new Error(`TideWise API error (${res.status}): ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export function fetchRecommend(params: {
  activity: Activity;
  spot?: string;
  start?: string;
  end?: string;
  signal?: AbortSignal;
}): Promise<RecommendResponse> {
  const qs = new URLSearchParams({ activity: params.activity });
  if (params.spot) qs.set('spot', params.spot);
  if (params.start) qs.set('start', params.start);
  if (params.end) qs.set('end', params.end);
  return requestJson<RecommendResponse>(`/recommend?${qs.toString()}`, {
    signal: params.signal,
  });
}

export function fetchScore(params: {
  activity: Activity;
  location?: string;
  spot?: string;
  signal?: AbortSignal;
}): Promise<ScoreWindowResponse> {
  const qs = new URLSearchParams({ activity: params.activity });
  if (params.location) qs.set('location', params.location);
  if (params.spot) qs.set('spot', params.spot);
  return requestJson<ScoreWindowResponse>(`/score?${qs.toString()}`, {
    signal: params.signal,
  });
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/health', { signal });
}

export function fetchSpots(signal?: AbortSignal): Promise<SpotsResponse> {
  return requestJson<SpotsResponse>('/spots', { signal });
}

export function postQuery(
  text: string,
  signal?: AbortSignal,
): Promise<QueryResponse> {
  return requestJson<QueryResponse>('/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
    signal,
  });
}
