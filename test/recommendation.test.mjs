import test from "node:test";
import assert from "node:assert/strict";
import {
  ACTIVITIES,
  normalizeObservations,
  scoreActivity,
  scoreAllActivities,
} from "../src/data/recommendation.mjs";

const now = new Date("2026-11-19T23:00:00.000Z");

const observation = (metric, value, unit = "native", minutesAgo = 5) => ({
  metric,
  value,
  unit,
  observedAt: new Date(now.getTime() - minutesAgo * 60000).toISOString(),
  source: "test-feed",
});

test("normalizes units and chooses the newest observation", () => {
  const result = normalizeObservations([
    observation("windSpeedMps", 20, "mph", 15),
    observation("windSpeedMps", 10, "mph", 5),
    observation("notReal", 1),
  ], now);

  assert.equal(Math.round(result.values.windSpeedMps.value * 100), 447);
  assert.equal(result.rejected.length, 1);
});

test("scores good swimming conditions with useful confidence", () => {
  const result = scoreActivity({
    activity: "swimming",
    now,
    observations: [
      observation("waterTempC", 22),
      observation("waveHeightM", 0.3),
      observation("windSpeedMps", 3),
      observation("waterQualityIndex", 92),
      observation("visibilityKm", 12),
      observation("bacteriaAdvisory", false),
      observation("lightningDistanceKm", 80),
    ],
  });

  assert.equal(result.recommendation, "good");
  assert.equal(result.score, 100);
  assert.ok(result.confidence >= 90);
});

test("active advisories override an otherwise good score", () => {
  const result = scoreActivity({
    activity: "swimming",
    now,
    observations: [
      observation("waterTempC", 22),
      observation("waveHeightM", 0.3),
      observation("windSpeedMps", 3),
      observation("waterQualityIndex", 92),
      observation("visibilityKm", 12),
      observation("bacteriaAdvisory", true),
    ],
  });

  assert.equal(result.score, 0);
  assert.equal(result.recommendation, "avoid");
  assert.equal(result.warnings[0].code, "BACTERIA_ADVISORY");
});

test("stale or missing feeds reduce confidence", () => {
  const result = scoreActivity({
    activity: "boating",
    now,
    observations: [observation("windSpeedMps", 5, "native", 180)],
  });

  assert.equal(result.recommendation, "insufficient-data");
  assert.equal(result.confidence, 0);
  assert.ok(result.factors.every((factor) => factor.status !== "used"));
});

test("scores all supported activities", () => {
  const results = scoreAllActivities({
    now,
    observations: [
      observation("windSpeedMps", 6),
      observation("windGustMps", 8),
      observation("waveHeightM", 0.5),
      observation("visibilityKm", 15),
      observation("waterQualityIndex", 90),
      observation("tideHeightM", 0.4),
      observation("tideCurrentKnots", 0.7),
      observation("waterTempC", 22),
      observation("precipitationMmHr", 0),
    ],
  });

  assert.equal(results.length, ACTIVITIES.length);
  assert.deepEqual([...results].sort((a, b) => b.score - a.score), results);
});
