import type {
  Activity,
  DataMode,
  HealthResponse,
  LiveSpotRef,
  RecommendResponse,
  Spot,
} from '../types';
import { fetchHealth, fetchRecommend, fetchSpots } from './api';
import {
  EXAMPLE_FRESHNESS_AS_OF,
  getExampleRecommendResponse,
  LIVE_UNAVAILABLE_BANNER_TEXT,
  PREVIEW_MODE_BANNER_TEXT,
  type PreviewScenario,
} from '../preview/exampleData';
import { pacificRangeIso } from './time';

export const SCORING_PENDING_BANNER_TEXT =
  'Scoring pending: live sources connected, rankings shown use example data';

export interface LoadedPlannerData {
  /** Response used to render the chart and rankings. */
  response: RecommendResponse;
  liveResponse?: RecommendResponse | null;
  spots: Spot[];
  liveSpots: LiveSpotRef[];
  isExampleData: boolean;
  dataMode: DataMode;
  exampleBannerText: string;
  scoringPending: boolean;
  backendNote?: string | null;
  /** Health to show in the sources panel (live when connected). */
  panelHealth: RecommendResponse['health'];
  sourcesAreLive: boolean;
  freshnessAsOf: Date;
  error?: string;
}

function allWindowsEmpty(response: RecommendResponse): boolean {
  if (!Array.isArray(response.recommendations) || response.recommendations.length === 0) {
    return true;
  }
  return response.recommendations.every(
    (rec) => !Array.isArray(rec.windows) || rec.windows.length === 0,
  );
}

function previewPayload(scenario: PreviewScenario): LoadedPlannerData {
  const response = getExampleRecommendResponse(scenario);
  return {
    response,
    liveResponse: null,
    spots: [],
    liveSpots: [],
    isExampleData: true,
    dataMode: 'preview',
    exampleBannerText: PREVIEW_MODE_BANNER_TEXT,
    scoringPending: false,
    backendNote: response.note ?? null,
    panelHealth: response.health,
    sourcesAreLive: false,
    freshnessAsOf: EXAMPLE_FRESHNESS_AS_OF,
  };
}

function fallbackPayload(
  scenario: PreviewScenario,
  error?: string,
): LoadedPlannerData {
  const response = getExampleRecommendResponse(scenario);
  return {
    response,
    liveResponse: null,
    spots: [],
    liveSpots: [],
    isExampleData: true,
    dataMode: 'fallback',
    exampleBannerText: LIVE_UNAVAILABLE_BANNER_TEXT,
    scoringPending: false,
    backendNote: null,
    panelHealth: response.health,
    sourcesAreLive: false,
    freshnessAsOf: EXAMPLE_FRESHNESS_AS_OF,
    error,
  };
}

function assertRecommendResponse(value: RecommendResponse): void {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('TideWise API parse error: RecommendResponse is not an object');
  }
  if (!Array.isArray(value.recommendations) || !Array.isArray(value.health)) {
    throw new Error('TideWise API parse error: malformed RecommendResponse');
  }
}

function assertHealthResponse(value: HealthResponse): void {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('TideWise API parse error: HealthResponse is not an object');
  }
  if (!Array.isArray(value.adapters) || !value.checked_at) {
    throw new Error('TideWise API parse error: malformed HealthResponse');
  }
}

function resolveLiveSpots(
  recommend: RecommendResponse,
  spots: Spot[],
): LiveSpotRef[] {
  const byId = new Map(spots.map((spot) => [spot.id, spot]));
  if (recommend.recommendations.length > 0) {
    return recommend.recommendations.map((rec) => ({
      id: rec.spot_id,
      name: rec.spot_name || byId.get(rec.spot_id)?.name || rec.spot_id,
    }));
  }
  return recommend.spot_ids.map((id) => ({
    id,
    name: byId.get(id)?.name || id,
  }));
}

/**
 * Load planner data from the live API, or fall back to labeled example data.
 * Both /recommend and /health must succeed (2xx) within the request timeout;
 * 501, timeouts, network errors, and parse errors trigger the
 * "Live data unavailable" fallback. /spots is best-effort.
 *
 * When live recommendations arrive with every windows[] empty, keep the
 * example chart and surface a scoring-pending state plus the backend note.
 *
 * VITE_FORCE_PREVIEW=true (or any truthy value) skips the network entirely.
 */
export async function loadPlannerData(params: {
  activity: Activity;
  forcePreview: boolean;
  scenario: PreviewScenario;
  start?: string;
  end?: string;
  lat?: number;
  lon?: number;
  limit?: number;
  signal?: AbortSignal;
}): Promise<LoadedPlannerData> {
  if (params.forcePreview) {
    return previewPayload(params.scenario);
  }

  const range = pacificRangeIso(new Date(), 24);
  const start = params.start ?? range.start;
  const end = params.end ?? range.end;

  try {
    const spotsPromise = fetchSpots(params.signal).catch(() => null);

    const [recommend, health, spotsRes] = await Promise.all([
      fetchRecommend({
        activity: params.activity,
        start,
        end,
        lat: params.lat,
        lon: params.lon,
        limit: params.limit,
        signal: params.signal,
      }),
      fetchHealth(params.signal),
      spotsPromise,
    ]);

    assertRecommendResponse(recommend);
    assertHealthResponse(health);

    const spots = spotsRes?.spots ?? [];
    const liveHealth =
      health.adapters && health.adapters.length > 0
        ? health.adapters
        : recommend.health;
    const liveResponse: RecommendResponse = {
      ...recommend,
      health: liveHealth,
      distances_km: recommend.distances_km ?? {},
    };
    const liveSpots = resolveLiveSpots(liveResponse, spots);
    const freshnessAsOf = health.checked_at
      ? new Date(health.checked_at)
      : new Date();

    if (allWindowsEmpty(liveResponse)) {
      const example = getExampleRecommendResponse(params.scenario);
      return {
        response: example,
        liveResponse,
        spots,
        liveSpots,
        isExampleData: true,
        dataMode: 'live',
        exampleBannerText: SCORING_PENDING_BANNER_TEXT,
        scoringPending: true,
        backendNote: liveResponse.note ?? null,
        panelHealth: liveHealth,
        sourcesAreLive: true,
        freshnessAsOf,
      };
    }

    return {
      response: liveResponse,
      liveResponse,
      spots,
      liveSpots,
      isExampleData: false,
      dataMode: 'live',
      exampleBannerText: '',
      scoringPending: false,
      backendNote: liveResponse.note ?? null,
      panelHealth: liveHealth,
      sourcesAreLive: true,
      freshnessAsOf,
    };
  } catch (err) {
    if (params.signal?.aborted) {
      throw err instanceof Error ? err : new Error('Aborted');
    }
    const message = err instanceof Error ? err.message : 'Unknown error';
    return fallbackPayload(params.scenario, message);
  }
}
