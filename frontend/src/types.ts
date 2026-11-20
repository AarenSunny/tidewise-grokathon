// ============================================================================
// Backend Pydantic-mirrored API contracts (backend/models/*.py)
// ============================================================================

export type Activity = 'clamming' | 'crabbing' | 'swimming' | 'sailing';

export type SourceStatus = 'ok' | 'stale' | 'down' | 'degraded';

export interface GateResult {
  name: string;
  passed: boolean;
  reason: string;
  cannot_confirm: boolean;
  evidence?: string | null;
}

export interface Confidence {
  value: number;
  notes: string[];
}

export interface FactorBreakdown {
  name: string;
  value?: number | null;
  weight: number;
  contribution: number;
  note?: string | null;
}

export interface ScoredWindow {
  spot_id: string;
  start: string;
  end: string;
  score: number;
  confidence: Confidence;
  gates: GateResult[];
  factors: FactorBreakdown[];
  eligible: boolean;
  summary?: string | null;
}

export interface SpotRecommendation {
  spot_id: string;
  spot_name: string;
  windows: ScoredWindow[];
  best_score?: number | null;
}

export interface AdapterHealth {
  source_name: string;
  status: SourceStatus;
  last_success_at?: string | null;
  last_error_at?: string | null;
  last_error?: string | null;
  last_latency_ms?: number | null;
  consecutive_failures: number;
  forced_down: boolean;
}

export interface RecommendResponse {
  activity: Activity;
  spot_ids: string[];
  start?: string | null;
  end?: string | null;
  recommendations: SpotRecommendation[];
  health: AdapterHealth[];
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'down' | string;
  adapters: AdapterHealth[];
  checked_at: string;
}

export interface Spot {
  id: string;
  name: string;
  lat: number;
  lon: number;
  shoreline_orientation_deg?: number | null;
  activities: Activity[];
  tide_station_id?: string | null;
  buoy_ids: string[];
  nws_grid?: string | null;
  notes?: string | null;
}

export interface SpotsResponse {
  region_id: string;
  spots: Spot[];
}

export interface Preferences {
  max_travel_km?: number | null;
  prefer_morning?: boolean | null;
  avoid_crowds?: boolean | null;
  extra: Record<string, string>;
}

export interface QueryIntent {
  activity?: Activity | null;
  location?: string | null;
  spot_ids: string[];
  start?: string | null;
  end?: string | null;
  preferences: Preferences;
  clarifying_question?: string | null;
  raw_text?: string | null;
}

export interface ClarifyingQuestion {
  question: string;
  partial_intent: QueryIntent;
}

export interface QueryResponse {
  intent?: QueryIntent | null;
  clarifying?: ClarifyingQuestion | null;
  recommendations: SpotRecommendation[];
  explanation?: string | null;
  health: AdapterHealth[];
}

// ============================================================================
// UI View Models derived from RecommendResponse + Spot[] via toViewModel.ts
// ============================================================================

export type AvailabilityId = 'afternoon' | 'after3pm' | 'midday';

export type ClosureStatusView = 'open' | 'closed' | 'unverified';

export interface ActivityOption {
  id: Activity;
  label: string;
  enabled: boolean;
  comingSoonLabel?: string;
}

export interface AvailabilityWindow {
  id: AvailabilityId;
  label: string;
  shortLabel: string;
  axisCaption: string;
  overlineSuffix: string;
  startMinutes: number;
  endMinutes: number;
}

export interface SpotDisplayMeta {
  area: string;
  mapPosition: { x: number; y: number };
}

export interface SpotWindowViewModel {
  spotId: string;
  spotName: string;
  area: string;
  rank: number | null;
  isTopPick: boolean;
  isRanked: boolean;
  score: number;
  confidenceValue: number;
  clippedStartMinutes: number;
  clippedEndMinutes: number;
  durationMinutes: number;
  lowTideTime: string;
  lowTideMinutes: number;
  lowTideHeightFt: number;
  lowTideDatum: string;
  capturesLowTidePeak: boolean;
  sunsetTime: string;
  closureStatus: ClosureStatusView;
  closureLabel: string;
  closureDetail: string;
  closureAlertTitle?: string;
  closureAlertMessage?: string;
  reasonSummary: string;
  bestPickTagline: string;
  notRankedReason?: string;
  sources: Array<{
    label: string;
    detail: string;
    isWarning?: boolean;
  }>;
  mapPosition: { x: number; y: number };
  rawWindow: ScoredWindow;
}

export interface TradeoffSummary {
  hasTradeoff: boolean;
  headline: string;
  body: string;
  shorterByMinutes: number;
  comparisonSpanStartMinutes: number | null;
  comparisonSpanEndMinutes: number | null;
  spot1Label: string;
  spot1DurationMinutes: number;
  spot2Label: string;
  spot2DurationMinutes: number;
}

export interface DataFreshnessSummary {
  tidesUpdatedAt: string;
  closuresCheckedAt: string;
  warningNote?: string;
}

export interface PlannerDayInfo {
  dateIso: string;
  label: string;
  shortLabel: string;
  regionLabel: string;
  axisStartMinutes: number;
  axisEndMinutes: number;
  sunsetTime: string;
  sunsetMinutes: number;
}

export interface PlannerViewModel {
  isExampleData: boolean;
  exampleBannerText: string;
  activity: Activity;
  day: PlannerDayInfo;
  availability: AvailabilityWindow;
  rankedSpots: SpotWindowViewModel[];
  notRankedSpots: SpotWindowViewModel[];
  bestPick: SpotWindowViewModel | null;
  tradeoff: TradeoffSummary | null;
  freshness: DataFreshnessSummary;
  health: AdapterHealth[];
}
