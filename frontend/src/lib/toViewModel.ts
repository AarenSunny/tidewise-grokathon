import type {
  AdapterHealth,
  AvailabilityWindow,
  ClosureStatusView,
  DataFreshnessSummary,
  DataMode,
  FactorBreakdown,
  GateResult,
  PlannerDayInfo,
  PlannerViewModel,
  RecommendResponse,
  ScoredWindow,
  Spot,
  SpotDisplayMeta,
  SpotSourceIssue,
  SpotWindowViewModel,
  TradeoffSummary,
} from '../types';
import {
  buildSourceBadges,
  closureSourceUnreliable,
  collectSourceIssues,
  effectiveSourceStatus,
  findAdapter,
  isHiddenOptionalSource,
  safetySourcesUnreliable,
  showsStaleBadge,
} from './sourceHealth';
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
 * Missing data (`cannot_confirm = true`) NEVER counts as safe. A stale, down,
 * or unknown CDPH adapter also forces unverified — never present as open.
 */
function resolveClosureStatus(
  gate: GateResult | undefined,
  health: AdapterHealth[],
  asOf: Date,
): {
  status: ClosureStatusView;
  label: string;
  detail: string;
  alertTitle?: string;
  alertMessage?: string;
} {
  const closureUnreliable = closureSourceUnreliable(health, asOf);

  if (gate && !gate.passed && !gate.cannot_confirm && !closureUnreliable) {
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

  if (!gate || (!gate.passed && gate.cannot_confirm) || closureUnreliable) {
    const closureHealth = findAdapter(health, 'cdph_shellfish');
    const effective = closureHealth
      ? effectiveSourceStatus(closureHealth, asOf)
      : 'unknown';
    const sourceHint =
      effective === 'down'
        ? 'The shellfish closure feed is unavailable.'
        : effective === 'stale'
          ? 'The shellfish closure feed is stale.'
          : effective === 'unknown'
            ? 'The shellfish closure feed status is unknown.'
            : "We couldn't confirm today's shellfish closure status.";
    return {
      status: 'unverified',
      label: 'Check advisory',
      detail: 'Live feed temporarily unavailable',
      alertTitle: 'Check the official advisory before you go',
      alertMessage:
        gate?.reason ??
        `${sourceHint} Check the official advisory before you dig.`,
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
  asOf: Date,
): SpotWindowViewModel['sources'] {
  const tideHealth = findAdapter(health, 'coops_tides');
  const closureHealth = findAdapter(health, 'cdph_shellfish');
  const daylightHealth = findAdapter(health, 'daylight_sunrise_api');
  const closureGate = getGate(window.gates, 'no_biotoxin_closure');

  const tideUpdated = tideHealth?.last_success_at
    ? formatIsoToPacificTime(tideHealth.last_success_at)
    : '2:05 PM';
  const daylightUpdated = daylightHealth?.last_success_at
    ? formatIsoToPacificTime(daylightHealth.last_success_at)
    : '6:00 AM';

  const tideStatus = tideHealth
    ? effectiveSourceStatus(tideHealth, asOf)
    : undefined;
  const closureEffective = closureHealth
    ? effectiveSourceStatus(closureHealth, asOf)
    : undefined;
  const daylightStatus = daylightHealth
    ? effectiveSourceStatus(daylightHealth, asOf)
    : undefined;

  let closureDetail: string;
  let closureIsWarning = closureStatus === 'unverified';

  if (closureStatus === 'unverified') {
    const since = closureHealth?.last_success_at
      ? formatIsoToPacificTime(closureHealth.last_success_at)
      : '6:10 AM';
    closureDetail = `CDPH shellfish advisory feed — last successful check ${since} (failing since)`;
  } else {
    const checkedAt = closureHealth?.last_success_at
      ? formatIsoToPacificTime(closureHealth.last_success_at)
      : '1:40 PM';
    closureDetail = `${closureGate?.evidence ?? 'CDPH shellfish advisory'} — checked ${checkedAt}`;
  }

  if (closureEffective && showsStaleBadge(closureEffective)) {
    closureIsWarning = true;
  }

  const tideBadge = tideStatus
    ? badgeFields(tideStatus)
    : { badge: undefined, badgeLabel: undefined };
  const closureBadge = closureEffective
    ? badgeFields(closureEffective)
    : { badge: undefined, badgeLabel: undefined };
  const daylightHidden = Boolean(
    daylightHealth && isHiddenOptionalSource(daylightHealth, asOf),
  );
  const daylightBadge =
    daylightStatus && !daylightHidden
      ? badgeFields(daylightStatus)
      : { badge: undefined, badgeLabel: undefined };

  return [
    {
      label: 'Tide',
      detail: `NOAA CO-OPS tide prediction — updated ${tideUpdated}`,
      isWarning: Boolean(tideStatus && showsStaleBadge(tideStatus)),
      badge: tideBadge.badge,
      badgeLabel: tideBadge.badgeLabel,
    },
    {
      label: 'Closure',
      detail: closureDetail,
      isWarning: closureIsWarning,
      badge: closureBadge.badge,
      badgeLabel: closureBadge.badgeLabel,
    },
    {
      label: 'Daylight',
      detail: `Sunrise/sunset table (sunset ${daySunsetTime}) — updated ${daylightUpdated}`,
      isWarning: Boolean(
        daylightStatus && showsStaleBadge(daylightStatus) && !daylightHidden,
      ),
      badge: daylightBadge.badge,
      badgeLabel: daylightBadge.badgeLabel,
    },
  ];
}

function badgeFields(status: ReturnType<typeof effectiveSourceStatus>): {
  badge: SpotWindowViewModel['sources'][number]['badge'];
  badgeLabel: string | undefined;
} {
  switch (status) {
    case 'stale':
      return { badge: 'stale', badgeLabel: 'Source stale' };
    case 'down':
      return { badge: 'unavailable', badgeLabel: 'Unavailable' };
    case 'degraded':
      return { badge: 'degraded', badgeLabel: 'Degraded' };
    case 'unknown':
      return { badge: 'unknown', badgeLabel: 'Unknown' };
    default:
      return { badge: 'ok', badgeLabel: 'OK' };
  }
}

function buildFreshnessSummary(
  health: AdapterHealth[],
  unverifiedSpotNames: string[],
  asOf: Date,
): DataFreshnessSummary {
  const tideHealth = findAdapter(health, 'coops_tides');
  const closureHealth = findAdapter(health, 'cdph_shellfish');

  const tidesUpdatedAt = tideHealth?.last_success_at
    ? formatIsoToPacificTime(tideHealth.last_success_at)
    : '2:05 PM';
  const closuresCheckedAt = closureHealth?.last_success_at
    ? formatIsoToPacificTime(closureHealth.last_success_at)
    : '1:40 PM';

  let warningNote: string | undefined;
  if (
    closureHealth &&
    showsStaleBadge(effectiveSourceStatus(closureHealth, asOf)) &&
    unverifiedSpotNames.length > 0
  ) {
    const since = closureHealth.last_success_at
      ? formatIsoToPacificTime(closureHealth.last_success_at)
      : '6:10 AM';
    warningNote = `${unverifiedSpotNames[0]} closure feed failing since ${since}`;
  }

  return {
    tidesUpdatedAt,
    closuresCheckedAt,
    warningNote,
    sources: buildSourceBadges(health, asOf),
    checkedAt: asOf.toISOString(),
  };
}

function resolveSpotIdentity(
  rec: RecommendResponse['recommendations'][number],
  spots: Spot[] | undefined,
  spotMeta: Record<string, SpotDisplayMeta>,
): { name: string; area: string; mapPosition: { x: number; y: number } } {
  const catalog = spots?.find((s) => s.id === rec.spot_id);
  const meta = spotMeta[rec.spot_id];
  const name = rec.spot_name || catalog?.name || rec.spot_id;
  const area =
    meta?.area ??
    catalog?.county ??
    catalog?.notes ??
    'Bay Area Coast';
  const mapPosition = meta?.mapPosition ?? { x: 50, y: 50 };
  return { name, area, mapPosition };
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
 * 3. Safety tier: verified-safe spots ALWAYS rank strictly above unverified
 *    (`cannot_confirm=true`) or source-stale spots. Missing data never ranks #1
 *    over a verified spot.
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
  dataMode?: DataMode;
  freshnessAsOf?: Date;
  spots?: Spot[];
  scoringPending?: boolean;
  backendNote?: string | null;
  liveSpots?: { id: string; name: string }[];
}): PlannerViewModel {
  const {
    response,
    spotMeta,
    day,
    availability,
    isExampleData,
    exampleBannerText,
    dataMode = isExampleData ? 'fallback' : 'live',
    freshnessAsOf = new Date(),
    spots,
    scoringPending = false,
    backendNote = response.note ?? null,
    liveSpots = [],
  } = params;

  const asOf = freshnessAsOf;
  const sourceIssues: SpotSourceIssue[] = collectSourceIssues(
    response.health,
    asOf,
  );
  const unverifiableSafety = safetySourcesUnreliable(response.health, asOf);

  const eligibleOrUnverified: SpotWindowViewModel[] = [];
  const notRankedSpots: SpotWindowViewModel[] = [];

  for (const rec of response.recommendations) {
    const primaryWindow = rec.windows[0];
    if (!primaryWindow) continue;

    const identity = resolveSpotIdentity(rec, spots, spotMeta);

    const rawStartMinutes = isoToPacificMinutes(primaryWindow.start);
    const rawEndMinutes = isoToPacificMinutes(primaryWindow.end);
    const clippedStartMinutes = Math.max(
      rawStartMinutes,
      availability.startMinutes,
    );
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
      tideMinutesFactor?.value ??
      Math.round((rawStartMinutes + rawEndMinutes) / 2);
    const lowTideTime = formatTime(lowTideMinutes);

    const closureGate = getGate(primaryWindow.gates, 'no_biotoxin_closure');
    const closure = resolveClosureStatus(closureGate, response.health, asOf);
    const isVerifiedSafe =
      closure.status === 'open' && !unverifiableSafety;

    const capturesLowTidePeak =
      durationMinutes > 0 &&
      lowTideMinutes >= clippedStartMinutes &&
      lowTideMinutes <= clippedEndMinutes;

    const sources = deriveSources(
      primaryWindow,
      closure.status,
      response.health,
      day.sunsetTime,
      asOf,
    );

    const baseVm: SpotWindowViewModel = {
      spotId: rec.spot_id,
      spotName: identity.name,
      area: identity.area,
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
      isVerifiedSafe,
      sourceIssues,
      mapPosition: identity.mapPosition,
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
        notRankedReason:
          'Confirmed shellfish quarantine — not shown on the chart.',
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
    const aTier = a.isVerifiedSafe ? 0 : 1;
    const bTier = b.isVerifiedSafe ? 0 : 1;
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
  const rankedSpots = eligibleOrUnverified.map(
    (spot, index): SpotWindowViewModel => {
      const rank = index + 1;
      const isTopPick = rank === 1 && spot.isVerifiedSafe;
      const heightStr = formatSignedHeight(spot.lowTideHeightFt);

      let reasonSummary: string;
      if (!spot.isVerifiedSafe) {
        const issueHint = spot.sourceIssues[0]?.detail;
        reasonSummary = issueHint
          ? `Ranked #${rank} of ${totalRanked}: the tide is ${heightStr} at ${spot.lowTideTime}, but ${issueHint.toLowerCase()}, so we can't treat this window as verified-safe.`
          : `Ranked #${rank} of ${totalRanked}: the tide is good (${heightStr} at ${spot.lowTideTime}), but we couldn't confirm today's shellfish closure status, so we can't recommend digging here yet.`;
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
    },
  );

  const bestPick =
    rankedSpots.find((s) => s.isVerifiedSafe) ?? null;

  const tradeoff = computeTradeoff(rankedSpots, availability);

  const unverifiedNames = rankedSpots
    .filter((s) => !s.isVerifiedSafe)
    .map((s) => s.spotName.split(' ')[0]);

  const freshness = buildFreshnessSummary(
    response.health,
    unverifiedNames,
    asOf,
  );

  return {
    isExampleData,
    exampleBannerText,
    dataMode,
    scoringPending,
    backendNote,
    liveSpots,
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
  const openSpots = rankedSpots.filter((s) => s.isVerifiedSafe);
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
