import type {
  Activity,
  HealthResponse,
  QueryResponse,
  RecommendResponse,
  ScoreWindowResponse,
  SpotsResponse,
} from '../types';

/**
 * Prefer VITE_API_BASE_URL, then VITE_API_URL (Render/Vercel helper).
 * Default to '' (same-origin) so Vite's dev proxy forwards
 * /recommend, /score, /health, /spots, /query to http://localhost:8000.
 * Set VITE_API_URL (used by the Vercel deploy) or VITE_API_BASE_URL to point at a deployed backend.
 */
const rawBase =
  import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '';

export const API_BASE_URL = rawBase.replace(/\/+$/, '');

/** Default network timeout for live /recommend and /health calls. */
// Render free tier cold starts take ~10-15 s; wait long enough before falling back.
export const REQUEST_TIMEOUT_MS = 20000;

function combineSignals(
  timeoutMs: number,
  userSignal?: AbortSignal,
): AbortSignal {
  const timeoutSignal = AbortSignal.timeout(timeoutMs);
  if (!userSignal) return timeoutSignal;
  if (typeof AbortSignal.any === 'function') {
    return AbortSignal.any([userSignal, timeoutSignal]);
  }
  const controller = new AbortController();
  const onAbort = () => controller.abort();
  if (userSignal.aborted || timeoutSignal.aborted) {
    controller.abort();
    return controller.signal;
  }
  userSignal.addEventListener('abort', onAbort, { once: true });
  timeoutSignal.addEventListener('abort', onAbort, { once: true });
  return controller.signal;
}

async function requestJson<T>(
  path: string,
  init?: RequestInit,
  timeoutMs: number = REQUEST_TIMEOUT_MS,
): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    signal: combineSignals(timeoutMs, init?.signal ?? undefined),
    headers: {
      Accept: 'application/json',
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw new Error(`TideWise API error (${res.status}): ${res.statusText}`);
  }
  try {
    return (await res.json()) as T;
  } catch {
    throw new Error(
      `TideWise API parse error (${res.status}): response was not valid JSON`,
    );
  }
}

export function fetchRecommend(params: {
  activity: Activity;
  spot?: string;
  start?: string;
  end?: string;
  lat?: number;
  lon?: number;
  limit?: number;
  signal?: AbortSignal;
  timeoutMs?: number;
}): Promise<RecommendResponse> {
  const qs = new URLSearchParams({ activity: params.activity });
  if (params.spot) qs.set('spot', params.spot);
  if (params.start) qs.set('start', params.start);
  if (params.end) qs.set('end', params.end);
  if (params.lat !== undefined) qs.set('lat', String(params.lat));
  if (params.lon !== undefined) qs.set('lon', String(params.lon));
  if (params.limit !== undefined) qs.set('limit', String(params.limit));
  return requestJson<RecommendResponse>(
    `/recommend?${qs.toString()}`,
    { signal: params.signal },
    params.timeoutMs ?? REQUEST_TIMEOUT_MS,
  );
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

export function fetchHealth(
  signal?: AbortSignal,
  timeoutMs: number = REQUEST_TIMEOUT_MS,
): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/health', { signal }, timeoutMs);
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
