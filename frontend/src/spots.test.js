import { describe, expect, it } from "vitest";
import {
  filterSpots,
  markerColorForScore,
  regionBounds,
  scoresFromRecommendations,
  shorelineFacing,
} from "./spots.js";

const spots = [
  {
    id: "half_moon_bay",
    name: "Half Moon Bay",
    lat: 37.4636,
    lon: -122.4286,
    activities: ["clamming", "crabbing", "swimming", "sailing"],
  },
  {
    id: "pacifica",
    name: "Pacifica",
    lat: 37.6138,
    lon: -122.4869,
    activities: ["clamming", "swimming"],
  },
  {
    id: "sf_bay",
    name: "San Francisco Bay",
    lat: 37.8076,
    lon: -122.4156,
    activities: ["sailing", "crabbing", "swimming"],
  },
];

describe("filterSpots", () => {
  it("keeps every spot when the filter is all", () => {
    expect(filterSpots(spots, "all").map((spot) => spot.id)).toEqual([
      "half_moon_bay",
      "pacifica",
      "sf_bay",
    ]);
  });

  it("hides spots that do not list the activity", () => {
    expect(filterSpots(spots, "clamming").map((spot) => spot.id)).toEqual([
      "half_moon_bay",
      "pacifica",
    ]);
    expect(filterSpots(spots, "sailing").map((spot) => spot.id)).toEqual([
      "half_moon_bay",
      "sf_bay",
    ]);
  });
});

describe("regionBounds", () => {
  it("prefers an API bbox in region.yaml order", () => {
    expect(regionBounds(spots, [-123.0, 37.2, -121.7, 38.0])).toEqual([
      [37.2, -123.0],
      [38.0, -121.7],
    ]);
  });

  it("frames the returned spots when the payload has no bbox", () => {
    expect(regionBounds(spots, null)).toEqual([
      [37.4636, -122.4869],
      [37.8076, -122.4156],
    ]);
  });
});

describe("recommendation score hook", () => {
  it("maps recommend rows to colors without requiring the endpoint", () => {
    const scores = scoresFromRecommendations([
      { spot_id: "half_moon_bay", best_score: 88 },
      { spot_id: "pacifica", best_score: null },
      { spot_id: "", best_score: 10 },
    ]);
    expect(scores).toEqual({ half_moon_bay: 88 });
    expect(markerColorForScore(scores.half_moon_bay)).toBe("#15803d");
    expect(markerColorForScore(undefined)).toBe("#1d4ed8");
    expect(markerColorForScore(10)).toBe("#b91c1c");
  });
});

describe("shorelineFacing", () => {
  it("treats 0 as north and 270 as west", () => {
    expect(shorelineFacing(270)).toMatchObject({ cardinal: "W", label: "270", rotation: 270 });
    expect(shorelineFacing(0)).toMatchObject({ cardinal: "N", rotation: 0 });
    expect(shorelineFacing(null)).toBeNull();
  });
});
