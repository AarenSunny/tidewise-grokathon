/**
 * Provider-neutral contract for live water-recreation conditions.
 * API adapters should emit observations shaped like:
 * { metric, value, unit, observedAt, source }
 */

export const ACTIVITIES = Object.freeze([
  "clamming",
  "crabbing",
  "swimming",
  "fishing",
  "boating",
  "kiting",
  "parasailing",
  "sailing",
]);

const METRICS = Object.freeze({
  airTempC: { maxAgeMinutes: 90 },
  waterTempC: { maxAgeMinutes: 180 },
  windSpeedMps: { maxAgeMinutes: 60 },
  windGustMps: { maxAgeMinutes: 60 },
  waveHeightM: { maxAgeMinutes: 120 },
  tideHeightM: { maxAgeMinutes: 360 },
  tideCurrentKnots: { maxAgeMinutes: 360 },
  precipitationMmHr: { maxAgeMinutes: 60 },
  visibilityKm: { maxAgeMinutes: 60 },
  waterQualityIndex: { maxAgeMinutes: 1440 },
  bacteriaAdvisory: { maxAgeMinutes: 1440 },
  lightningDistanceKm: { maxAgeMinutes: 15 },
  uvIndex: { maxAgeMinutes: 90 },
});

// Ideal ranges score 100. Scores taper to zero at the hard range boundary.
const PROFILES = Object.freeze({
  clamming: [
    rule("tideHeightM", 4, [-0.5, 0.8], [-1.5, 1.8]),
    rule("waveHeightM", 2, [0, 0.7], [0, 1.8]),
    rule("windSpeedMps", 1, [0, 7], [0, 14]),
    rule("waterQualityIndex", 3, [80, 100], [45, 100]),
  ],
  crabbing: [
    rule("tideCurrentKnots", 3, [0.2, 1.2], [0, 2.5]),
    rule("waveHeightM", 2, [0, 0.8], [0, 2]),
    rule("windSpeedMps", 2, [0, 8], [0, 16]),
    rule("waterQualityIndex", 3, [70, 100], [40, 100]),
  ],
  swimming: [
    rule("waterTempC", 3, [18, 29], [10, 34]),
    rule("waveHeightM", 3, [0, 0.5], [0, 1.5]),
    rule("windSpeedMps", 1, [0, 6], [0, 14]),
    rule("waterQualityIndex", 4, [85, 100], [55, 100]),
    rule("visibilityKm", 1, [5, 100], [1, 100]),
  ],
  fishing: [
    rule("windSpeedMps", 2, [1, 7], [0, 16]),
    rule("waveHeightM", 2, [0, 0.8], [0, 2.5]),
    rule("precipitationMmHr", 1, [0, 2], [0, 12]),
    rule("waterQualityIndex", 2, [65, 100], [35, 100]),
  ],
  boating: [
    rule("windSpeedMps", 3, [1, 8], [0, 17]),
    rule("windGustMps", 2, [0, 11], [0, 22]),
    rule("waveHeightM", 3, [0, 0.8], [0, 2.5]),
    rule("visibilityKm", 2, [8, 100], [1, 100]),
  ],
  kiting: [
    rule("windSpeedMps", 5, [5, 11], [2, 17]),
    rule("windGustMps", 2, [5, 14], [2, 22]),
    rule("waveHeightM", 1, [0, 1.2], [0, 2.8]),
    rule("visibilityKm", 1, [5, 100], [1, 100]),
  ],
  parasailing: [
    rule("windSpeedMps", 4, [2, 8], [0, 13]),
    rule("windGustMps", 3, [2, 10], [0, 16]),
    rule("waveHeightM", 2, [0, 0.7], [0, 1.8]),
    rule("visibilityKm", 2, [8, 100], [2, 100]),
  ],
  sailing: [
    rule("windSpeedMps", 5, [3, 10], [1, 18]),
    rule("windGustMps", 2, [3, 14], [1, 24]),
    rule("waveHeightM", 2, [0, 1.2], [0, 3]),
    rule("visibilityKm", 1, [5, 100], [1, 100]),
  ],
});

function rule(metric, weight, ideal, hard) {
  return Object.freeze({ metric, weight, ideal, hard });
}

const UNIT_CONVERTERS = Object.freeze({
  "airTempC:F": (v) => (v - 32) * (5 / 9),
  "waterTempC:F": (v) => (v - 32) * (5 / 9),
  "windSpeedMps:mph": (v) => v * 0.44704,
  "windGustMps:mph": (v) => v * 0.44704,
  "windSpeedMps:knots": (v) => v * 0.514444,
  "windGustMps:knots": (v) => v * 0.514444,
  "waveHeightM:ft": (v) => v * 0.3048,
  "tideHeightM:ft": (v) => v * 0.3048,
  "visibilityKm:mi": (v) => v * 1.609344,
  "precipitationMmHr:in/hr": (v) => v * 25.4,
});

/**
 * Normalize live observations, discard malformed records, and retain the newest
 * record for each metric. Unknown metrics are ignored so providers can evolve.
 */
export function normalizeObservations(observations, now = new Date()) {
  if (!Array.isArray(observations)) {
    throw new TypeError("observations must be an array");
  }

  const values = {};
  const rejected = [];
  const nowMs = toDate(now, "now").getTime();

  for (const observation of observations) {
    const metric = observation?.metric;
    if (!Object.hasOwn(METRICS, metric)) {
      rejected.push({ observation, reason: "unknown metric" });
      continue;
    }

    const observedAt = new Date(observation.observedAt);
    const isBoolean = metric === "bacteriaAdvisory";
    const valueIsValid = isBoolean
      ? typeof observation.value === "boolean"
      : Number.isFinite(observation.value);

    if (!valueIsValid || Number.isNaN(observedAt.getTime())) {
      rejected.push({ observation, reason: "invalid value or timestamp" });
      continue;
    }

    const ageMinutes = Math.max(0, (nowMs - observedAt.getTime()) / 60000);
    const converter = UNIT_CONVERTERS[`${metric}:${observation.unit}`];
    const value = isBoolean
      ? observation.value
      : converter
        ? converter(observation.value)
        : observation.value;
    const normalized = {
      value,
      observedAt: observedAt.toISOString(),
      source: observation.source || "unknown",
      ageMinutes,
      stale: ageMinutes > METRICS[metric].maxAgeMinutes,
    };

    if (!values[metric] || observedAt > new Date(values[metric].observedAt)) {
      values[metric] = normalized;
    }
  }

  return { values, rejected };
}

/**
 * Frontend-facing scoring interface.
 * Returns a 0-100 score, a coarse recommendation, confidence, and explanations.
 */
export function scoreActivity({ activity, observations, now = new Date() }) {
  if (!ACTIVITIES.includes(activity)) {
    throw new RangeError(`unsupported activity: ${activity}`);
  }

  const { values, rejected } = normalizeObservations(observations, now);
  const profile = PROFILES[activity];
  const warnings = safetyWarnings(values, activity);
  let weightedScore = 0;
  let observedWeight = 0;
  let freshnessWeight = 0;
  const factors = [];

  for (const item of profile) {
    const observation = values[item.metric];
    if (!observation || observation.stale) {
      factors.push({ metric: item.metric, status: observation ? "stale" : "missing" });
      continue;
    }

    const factorScore = rangeScore(observation.value, item.ideal, item.hard);
    weightedScore += factorScore * item.weight;
    observedWeight += item.weight;
    freshnessWeight += item.weight * freshnessFactor(item.metric, observation.ageMinutes);
    factors.push({
      metric: item.metric,
      status: "used",
      value: round(observation.value),
      score: round(factorScore),
      source: observation.source,
    });
  }

  const totalWeight = profile.reduce((sum, item) => sum + item.weight, 0);
  const coverage = observedWeight / totalWeight;
  const freshness = observedWeight ? freshnessWeight / observedWeight : 0;
  const confidence = Math.round(100 * coverage * freshness);
  let score = observedWeight ? Math.round(weightedScore / observedWeight) : 0;

  // Safety alerts are intentionally dominant, even if ordinary conditions score well.
  if (warnings.some((warning) => warning.severity === "block")) score = 0;
  else if (warnings.some((warning) => warning.severity === "caution")) score = Math.min(score, 49);

  const recommendation = confidence < 35
    ? "insufficient-data"
    : score >= 75
      ? "good"
      : score >= 50
        ? "fair"
        : "avoid";

  return {
    activity,
    score,
    recommendation,
    confidence,
    factors,
    warnings,
    rejectedObservationCount: rejected.length,
    evaluatedAt: toDate(now, "now").toISOString(),
  };
}

/** Rank one location/time snapshot for every supported activity. */
export function scoreAllActivities({ observations, now = new Date() }) {
  return ACTIVITIES
    .map((activity) => scoreActivity({ activity, observations, now }))
    .sort((a, b) => b.score - a.score || b.confidence - a.confidence);
}

function safetyWarnings(values, activity) {
  const warnings = [];
  if (values.bacteriaAdvisory?.value === true && !values.bacteriaAdvisory.stale) {
    warnings.push({ severity: "block", code: "BACTERIA_ADVISORY", message: "Active water-quality advisory" });
  }
  if (values.lightningDistanceKm && !values.lightningDistanceKm.stale) {
    if (values.lightningDistanceKm.value < 16) {
      warnings.push({ severity: "block", code: "LIGHTNING_NEARBY", message: "Lightning detected within 16 km" });
    } else if (values.lightningDistanceKm.value < 32) {
      warnings.push({ severity: "caution", code: "LIGHTNING_WATCH", message: "Lightning detected within 32 km" });
    }
  }
  if (activity === "swimming" && values.waterTempC?.value < 10 && !values.waterTempC.stale) {
    warnings.push({ severity: "block", code: "COLD_WATER", message: "Water temperature poses cold-shock risk" });
  }
  return warnings;
}

function rangeScore(value, ideal, hard) {
  const [idealMin, idealMax] = ideal;
  const [hardMin, hardMax] = hard;
  if (value < hardMin || value > hardMax) return 0;
  if (value >= idealMin && value <= idealMax) return 100;
  if (value < idealMin) return 100 * ((value - hardMin) / (idealMin - hardMin));
  return 100 * ((hardMax - value) / (hardMax - idealMax));
}

function freshnessFactor(metric, ageMinutes) {
  const maxAge = METRICS[metric].maxAgeMinutes;
  return Math.max(0.5, 1 - (0.5 * ageMinutes) / maxAge);
}

function toDate(value, label) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) throw new TypeError(`${label} must be a valid date`);
  return date;
}

function round(value) {
  return Math.round(value * 10) / 10;
}

