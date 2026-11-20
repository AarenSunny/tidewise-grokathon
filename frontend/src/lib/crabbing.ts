import type {
  Activity,
  ActivityOption,
  GateResult,
  RecommendResponse,
  ScoredWindow,
  Spot,
} from '../types';
import { pacificRangeIso } from './time';

export const CRABBING_GEAR = 'hoop_net';
export const CRABBING_RANGE_HOURS = 72;

export const PLANNER_ACTIVITIES: ActivityOption[] = [
  { id: 'clamming', label: 'Clamming', enabled: true },
  { id: 'crabbing', label: 'Crabbing', enabled: true },
  { id: 'swimming', label: 'Swimming', enabled: true },
  { id: 'sailing', label: 'Sailing', enabled: true },
];

export function recommendParamsForActivity(activity: Activity): {
  activity: Activity;
  gear?: string;
  start: string;
  end: string;
  durationHours: number;
} {
  if (activity === 'crabbing') {
    const range = pacificRangeIso(new Date(), CRABBING_RANGE_HOURS);
    return {
      activity,
      gear: CRABBING_GEAR,
      start: range.start,
      end: range.end,
      durationHours: CRABBING_RANGE_HOURS,
    };
  }
  // The live backend scores ~72h of forecasts; 24h often returns no windows.
  const range = pacificRangeIso(new Date(), CRABBING_RANGE_HOURS);
  return {
    activity,
    start: range.start,
    end: range.end,
    durationHours: CRABBING_RANGE_HOURS,
  };
}

export function hasLiveWindows(response: RecommendResponse | null | undefined): boolean {
  if (!response) return false;
  return response.recommendations.some(
    (rec) => Array.isArray(rec.windows) && rec.windows.length > 0,
  );
}

export type GateState = 'pass' | 'fail' | 'cant-confirm';

export interface GateView {
  name: string;
  state: GateState;
  label: 'Pass' | 'Fail' | 'Check advisory';
  reason: string;
}

/** cannot_confirm (or passed=false with cannot_confirm) is never treated as safe. */
export function toGateView(gate: GateResult): GateView {
  if (gate.cannot_confirm || (gate.passed === false && gate.cannot_confirm)) {
    return {
      name: gate.name,
      state: 'cant-confirm',
      label: 'Check advisory',
      reason: gate.reason,
    };
  }
  if (!gate.passed) {
    return {
      name: gate.name,
      state: 'fail',
      label: 'Fail',
      reason: gate.reason,
    };
  }
  return {
    name: gate.name,
    state: 'pass',
    label: 'Pass',
    reason: gate.reason,
  };
}

export interface LiveWindowRow {
  id: string;
  spotId: string;
  spotName: string;
  startMs: number;
  endMs: number;
  dateKey: string;
  dateLabel: string;
  rangeLabel: string;
  score: number;
  confidence: number;
  summary?: string | null;
  gates: GateView[];
  hasCantConfirm: boolean;
  raw: ScoredWindow;
}

export interface WindowDayGroup {
  dateKey: string;
  dateLabel: string;
  windows: LiveWindowRow[];
}

const DATE_FMT = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Los_Angeles',
  weekday: 'long',
  month: 'short',
  day: 'numeric',
});

const KEY_FMT = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'America/Los_Angeles',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

const TIME_FMT = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Los_Angeles',
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
});

function formatRangePt(start: Date, end: Date): string {
  return `${TIME_FMT.format(start)} – ${TIME_FMT.format(end)} PT`;
}

export function resolveSpotName(
  spotId: string,
  spotName: string | undefined,
  spots: Spot[],
): string {
  if (spotName && spotName.trim()) return spotName;
  const catalog = spots.find((spot) => spot.id === spotId);
  return catalog?.name ?? spotId;
}

export function groupWindowsByDay(
  response: RecommendResponse,
  spots: Spot[] = [],
): WindowDayGroup[] {
  const rows: LiveWindowRow[] = [];
  for (const rec of response.recommendations) {
    const name = resolveSpotName(rec.spot_id, rec.spot_name, spots);
    rec.windows.forEach((window, index) => {
      const start = new Date(window.start);
      const end = new Date(window.end);
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return;
      const gates = (window.gates ?? []).map(toGateView);
      rows.push({
        id: `${rec.spot_id}-${window.start}-${index}`,
        spotId: rec.spot_id,
        spotName: name,
        startMs: start.getTime(),
        endMs: end.getTime(),
        dateKey: KEY_FMT.format(start),
        dateLabel: DATE_FMT.format(start),
        rangeLabel: formatRangePt(start, end),
        score: window.score,
        confidence: window.confidence?.value ?? 0,
        summary: window.summary ?? null,
        gates,
        hasCantConfirm: gates.some((gate) => gate.state === 'cant-confirm'),
        raw: window,
      });
    });
  }
  rows.sort((a, b) => a.startMs - b.startMs || b.score - a.score);
  const groups = new Map<string, WindowDayGroup>();
  for (const row of rows) {
    const existing = groups.get(row.dateKey);
    if (existing) {
      existing.windows.push(row);
    } else {
      groups.set(row.dateKey, {
        dateKey: row.dateKey,
        dateLabel: row.dateLabel,
        windows: [row],
      });
    }
  }
  return [...groups.values()];
}
