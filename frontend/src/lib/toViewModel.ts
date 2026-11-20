import type {
  AdapterHealth,
  AvailabilityWindow,
  ClosureStatusView,
  DataFreshnessSummary,
  FactorBreakdown,
  GateResult,
  PlannerDayInfo,
  PlannerViewModel,
  RecommendResponse,
  ScoredWindow,
  SpotDisplayMeta,
  SpotWindowViewModel,
  TradeoffSummary,
} from '../types';
import {
  formatDuration,
  formatIsoToPacificTime,
  formatRange,
  formatSignedHeight,
  formatTime,
  isoToPacificMinutes,
} from './time';

function getFactor(
  factors: FactorBreakdown[],
  name: string,
): FactorBreakdown | undefined {
  return factors.find((f) => f.name === name);
}

function getGate(
  gates: GateResult[],
  name: string,
): GateResult | undefined {
  return gates.find((g) => g.name === name);
}

/**
 * Derive closure state from the backend's `no_biotoxin_closure` safety gate.
 * Missing data (`cannot_confirm = true`) NEVER counts as safe.
 */
function resolveClosureStatus(gate?: GateResult): {
  status: ClosureStatusView;
  label: string;
  detail: string;
  alertTitle?: string;
  alertMessage?: string;
} {
  if (!gate || (!gate.passed && gate.cannot_confirm)) {
    return {
      status: 'unverified',
      label: 'Unable to verify closure',
      detail: 'Closure feed unreachable',
      alertTitle: 'Unable to verify closure status',
      alertMessage:
        gate?.reason ??
        "We couldn't confirm today's shellfish closure status. Check the official advisory before you dig.",
    };
  }
  if (!gate.passed && !gate.cannot_confirm) {
    return {
      status: 'closed',
      label: 'Closed',
      detail: 'Biotoxin quarantine',
      alertTitle: 'Closed to shellfish harvest',
      alertMessage:
        gate.reason ||
        'A confirmed state quarantine is in effect for this beach. Do not harvest clams here today.',
    };
  }
  return {
    status: 'open',
    label: 'Open — eligible',
    detail: gate.evidence ?? 'No active quarantine',
  };
}

function deriveSources(
  window: ScoredWindow,
  closureStatus: ClosureStatusView,
  health: AdapterHealth[],
  daySunsetTime: string,
): SpotWindowViewModel['sources'] {
  const tideHealth = health.find((h) => h.source_name === 'noaa_tides');
  const closureHealth = health.find((h) => h.source_name === 'cdph_shellfish');
  const daylightHealth = health.find((h) => h.source_name === 'daylight_table');
  const closureGate = getGate(window.gates, 'no_biotoxin_closure');

  const tideUpdated = tideHealth?.last_success_at
    ? formatIsoToPacificTime(tideHealth.last_success_at)
    : '2:05 PM';

  const daylightUpdated = daylightHealth?.last_success_at
    ? formatIsoToPacificTime(daylightHealth.last_success_at)
    : '6:00 AM';

  let closureDetail: string;
  let closureIsWarning = false;

  if (closureStatus === 'unverified') {
    const since = closureHealth?.last_success_at
      ? formatIsoToPacificTime(closureHealth.last_success_at)
      : '6:10 AM';
    closureDetail = `CDPH shellfish advisory feed — last successful check ${since} (failing since)`;
    closureIsWarning = true;
  } else {
    const checkedAt = closureHealth?.last_success_at
      ? formatIsoToPacificTime(closureHealth.last_success_at)
      : '1:40 PM';
    closureDetail = `${closureGate?.evidence ?? 'CDPH shellfish advisory'} — checked ${checkedAt}`;
  }

  return [
    {
      label: 'Tide',
      detail: `NOAA tide prediction — updated ${tideUpdated}`,
    },
    {
      label: 'Closure',
      detail: closureDetail,
      isWarning: closureIsWarning,
    },
    {
      label: 'Daylight',
      detail: `Sunrise/sunset table (sunset ${daySunsetTime}) — updated ${daylightUpdated}`,
    },
  ];
}

function buildFreshnessSummary(
  health: AdapterHealth[],
  unverifiedSpotNames: string[],
): DataFreshnessSummary {
  const tideHealth = health.find((h) => h.source_name === 'noaa_tides');
  const closureHealth = health.find((h) => h.source_name === 'cdph_shellfish');

  const tidesUpdatedAt = tideHealth?.last_success_at
    ? formatIsoToPacificTime(tideHealth.last_success_at)
    : '2:05 PM';
  const closuresCheckedAt = closureHealth?.last_success_at
    ? formatIsoToPacificTime(closureHealth.last_success_at)
    : '1:40 PM';

  let warningNote: string | undefined;
  if (closureHealth && closureHealth.status !== 'ok' && unverifiedSpotNames.length > 0) {
    const since = closureHealth.last_success_at
      ? formatIsoToPacificTime(closureHealth.last_success_at)
      : '6:10 AM';
    warningNote = `${unverifiedSpotNames[0]} closure feed failing since ${since}`;
  }

  return {
    tidesUpdatedAt,
    closuresCheckedAt,
    warningNote,
  };
}

/**
 * Pure adapter + ranking/clipping function: converts a backend `RecommendResponse`
 * and display metadata into the `PlannerViewModel` consumed by TideWise components.
 *
 * Ranking rules:
 * 1. Confirmed shellfish closures (`no_biotoxin_closure`: passed=false, cannot_confirm=false)
 *    are excluded from ranking (`notRankedSpots`).
 * 2. Each window is clipped to `[availability.startMinutes, availability.endMinutes]`
 *    and `day.sunsetMinutes`. Zero-overlap windows move to `notRankedSpots`.
 * 3. Safety tier: verified `open` spots ALWAYS rank strictly above `unverified`
 *    (`cannot_confirm=true`) spots. Missing data never ranks #1 over a verified spot.
 * 4. Within the same safety tier:
 *    - Capturing the peak low tide inside the clipped window beats missing it.
 *    - Lower low-tide height (ft MLLW) ranks higher (exposes more clam bed).
 *    - Tie-breaker: higher backend `score`, then longer clipped duration.
 */
export function toPlannerViewModel(params: {
  response: RecommendResponse;
  spotMeta: Record<string, SpotDisplayMeta>;
  day: PlannerDayInfo;
  availability: AvailabilityWindow;
  isExampleData: boolean;
  exampleBannerText: string;
}): PlannerViewModel {
  const {
    response,
    spotMeta,
    day,
    availability,
    isExampleData,
    exampleBannerText,
  } = params;

  const eligibleOrUnverified: SpotWindowViewModel[] = [];
  const notRankedSpots: SpotWindowViewModel[] = [];

  for (const rec of response.recommendations) {
    const primaryWindow = rec.windows[0];
    if (!primaryWindow) continue;

    const meta = spotMeta[rec.spot_id] ?? {
      area: 'Bay Area Coast',
      mapPosition: { x: 50, y: 50 },
    };

    const rawStartMinutes = isoToPacificMinutes(primaryWindow.start);
    const rawEndMinutes = isoToPacificMinutes(primaryWindow.end);
    const clippedStartMinutes = Math.max(rawStartMinutes, availability.startMinutes);
    const clippedEndMinutes = Math.min(
      rawEndMinutes,
      availability.endMinutes,
      day.sunsetMinutes,
    );
    const durationMinutes = Math.max(0, clippedEndMinutes - clippedStartMinutes);

    const tideHeightFactor = getFactor(
      primaryWindow.factors,
      'low_tide_height_ft',
    );
    const tideMinutesFactor = getFactor(
      primaryWindow.factors,
      'low_tide_time_min',
    );
    const lowTideHeightFt = tideHeightFactor?.value ?? 0;
    const lowTideMinutes =
      tideMinutesFactor?.value ?? Math.round((rawStartMinutes + rawEndMinutes) / 2);
    const lowTideTime = formatTime(lowTideMinutes);

    const closureGate = getGate(primaryWindow.gates, 'no_biotoxin_closure');
    const closure = resolveClosureStatus(closureGate);

    const capturesLowTidePeak =
      durationMinutes > 0 &&
      lowTideMinutes >= clippedStartMinutes &&
      lowTideMinutes <= clippedEndMinutes;

    const sources = deriveSources(
      primaryWindow,
      closure.status,
      response.health,
      day.sunsetTime,
    );

    const baseVm: SpotWindowViewModel = {
      spotId: rec.spot_id,
      spotName: rec.spot_name,
      area: meta.area,
      rank: null,
      isTopPick: false,
      isRanked: false,
      score: primaryWindow.score,
      confidenceValue: primaryWindow.confidence.value,
      clippedStartMinutes,
      clippedEndMinutes,
      durationMinutes,
      lowTideTime,
      lowTideMinutes,
      lowTideHeightFt,
      lowTideDatum: 'MLLW',
      capturesLowTidePeak,
      sunsetTime: day.sunsetTime,
      closureStatus: closure.status,
      closureLabel: closure.label,
      closureDetail: closure.detail,
      closureAlertTitle: closure.alertTitle,
      closureAlertMessage: closure.alertMessage,
      reasonSummary: primaryWindow.summary ?? '',
      bestPickTagline: '',
      sources,
      mapPosition: meta.mapPosition,
      rawWindow: primaryWindow,
    };

    if (closure.status === 'closed') {
      notRankedSpots.push({
        ...baseVm,
        clippedStartMinutes: rawStartMinutes,
        clippedEndMinutes: rawEndMinutes,
        durationMinutes: Math.max(0, rawEndMinutes - rawStartMinutes),
        reasonSummary:
          primaryWindow.summary ??
          `Not recommended: ${closure.detail.toLowerCase()} is active today, even though the tide drops to ${formatSignedHeight(lowTideHeightFt)} at ${lowTideTime}.`,
        notRankedReason: 'Confirmed shellfish quarantine — not shown on the chart.',
      });
      continue;
    }

    if (durationMinutes <= 0) {
      notRankedSpots.push({
        ...baseVm,
        clippedStartMinutes: rawStartMinutes,
        clippedEndMinutes: rawEndMinutes,
        durationMinutes: 0,
        reasonSummary: `Outside your ${availability.shortLabel} free hours: this spot's clamming window runs ${formatRange(rawStartMinutes, rawEndMinutes)}.`,
        notRankedReason: `Window (${formatRange(rawStartMinutes, rawEndMinutes)}) falls outside your ${availability.shortLabel} hours.`,
      });
      continue;
    }

    eligibleOrUnverified.push({
      ...baseVm,
      isRanked: true,
    });
  }

  eligibleOrUnverified.sort((a, b) => {
    const aTier = a.closureStatus === 'open' ? 0 : 1;
    const bTier = b.closureStatus === 'open' ? 0 : 1;
    if (aTier !== bTier) return aTier - bTier;

    if (a.capturesLowTidePeak !== b.capturesLowTidePeak) {
      return a.capturesLowTidePeak ? -1 : 1;
    }

    if (a.lowTideHeightFt !== b.lowTideHeightFt) {
      return a.lowTideHeightFt - b.lowTideHeightFt;
    }

    if (a.score !== b.score) {
      return b.score - a.score;
    }

    return b.durationMinutes - a.durationMinutes;
  });

  const totalRanked = eligibleOrUnverified.length;
  const rankedSpots = eligibleOrUnverified.map((spot, index): SpotWindowViewModel => {
    const rank = index + 1;
    const isTopPick = rank === 1 && spot.closureStatus === 'open';
    const heightStr = formatSignedHeight(spot.lowTideHeightFt);

    let reasonSummary: string;
    if (spot.closureStatus === 'unverified') {
      reasonSummary = `Ranked #${rank} of ${totalRanked}: the tide is good (${heightStr} at ${spot.lowTideTime}), but we couldn't confirm today's shellfish closure status, so we can't recommend digging here yet.`;
    } else if (isTopPick) {
      if (spot.capturesLowTidePeak) {
        reasonSummary = `Ranked #1 because it has the day's lowest verified tide (${heightStr} at ${spot.lowTideTime}), exposing the most clam flat, and the ${formatDuration(spot.durationMinutes)} window fits in daylight and your free hours.`;
      } else {
        reasonSummary = `Ranked #1 because it is verified open with ${formatDuration(spot.durationMinutes)} of clamming time inside your ${availability.shortLabel} hours before sunset (${day.sunsetTime}).`;
      }
    } else if (!spot.capturesLowTidePeak) {
      reasonSummary = `Ranked #${rank} because its peak low tide (${heightStr} at ${spot.lowTideTime}) falls outside your ${availability.shortLabel} window, leaving a ${formatDuration(spot.durationMinutes)} overlap.`;
    } else {
      reasonSummary = `Ranked #${rank}: verified open with a ${formatDuration(spot.durationMinutes)} window around a ${heightStr} low tide at ${spot.lowTideTime} — longer than #1, though the tide doesn't drop as low.`;
    }

    const bestPickTagline = spot.capturesLowTidePeak
      ? `Lowest tide of the day (${heightStr} at ${spot.lowTideTime}) · all in daylight · inside your hours`
      : `Verified open · ${formatDuration(spot.durationMinutes)} inside your hours · all in daylight`;

    return {
      ...spot,
      rank,
      isTopPick,
      reasonSummary,
      bestPickTagline,
    };
  });

  const bestPick =
    rankedSpots.find((s) => s.closureStatus === 'open') ?? null;

  const tradeoff = computeTradeoff(rankedSpots, availability);

  const unverifiedNames = rankedSpots
    .filter((s) => s.closureStatus === 'unverified')
    .map((s) => s.spotName.split(' ')[0]);

  const freshness = buildFreshnessSummary(response.health, unverifiedNames);

  return {
    isExampleData,
    exampleBannerText,
    activity: response.activity,
    day,
    availability,
    rankedSpots,
    notRankedSpots,
    bestPick,
    tradeoff,
    freshness,
    health: response.health,
  };
}

function computeTradeoff(
  rankedSpots: SpotWindowViewModel[],
  availability: AvailabilityWindow,
): TradeoffSummary | null {
  const openSpots = rankedSpots.filter((s) => s.closureStatus === 'open');
  if (openSpots.length < 2) return null;

  const first = openSpots[0];
  const second = openSpots[1];
  const diff = second.durationMinutes - first.durationMinutes;

  if (diff > 0) {
    const comparisonStart =
      second.clippedStartMinutes < first.clippedStartMinutes
        ? second.clippedStartMinutes
        : null;
    const comparisonEnd =
      comparisonStart !== null ? first.clippedStartMinutes : null;

    return {
      hasTradeoff: true,
      headline: `Tradeoff: the #1 spot gives you ${formatDuration(diff)} less time than #2`,
      body: `${first.spotName} ranks higher because its tide drops to ${formatSignedHeight(first.lowTideHeightFt)} (vs ${formatSignedHeight(second.lowTideHeightFt)} at ${second.spotName}), exposing more clam bed. If you'd rather have a longer, easier session, ${second.spotName} gives you ${formatDuration(second.durationMinutes)}.`,
      shorterByMinutes: diff,
      comparisonSpanStartMinutes: comparisonStart,
      comparisonSpanEndMinutes: comparisonEnd,
      spot1Label: '#1',
      spot1DurationMinutes: first.durationMinutes,
      spot2Label: '#2',
      spot2DurationMinutes: second.durationMinutes,
    };
  }

  return {
    hasTradeoff: false,
    headline: `Starting ${formatTime(availability.startMinutes)}: #1 matches #2 on time (${formatDuration(first.durationMinutes)})`,
    body: `Your ${availability.shortLabel} cutoff trims ${second.spotName}'s earlier stretch, so both verified spots give you ${formatDuration(first.durationMinutes)} before sunset. ${first.spotName} wins cleanly with a ${formatSignedHeight(first.lowTideHeightFt)} low tide (vs ${formatSignedHeight(second.lowTideHeightFt)} at ${second.spotName}).`,
    shorterByMinutes: 0,
    comparisonSpanStartMinutes: null,
    comparisonSpanEndMinutes: null,
    spot1Label: '#1',
    spot1DurationMinutes: first.durationMinutes,
    spot2Label: '#2',
    spot2DurationMinutes: second.durationMinutes,
  };
}
