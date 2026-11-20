/**
 * Pure helpers for the spots map.
 * Spots always come from GET /spots. Scores are optional input for later,
 * when GET /recommend exists — nothing here calls that endpoint.
 */

export const ACTIVITIES = ["clamming", "crabbing", "swimming", "sailing"];

export const API_DOWN_MESSAGE =
  "The spots API is not responding. Start the TideWise API and refresh. No backup spots are shown.";

const UNSCORED_COLOR = "#1d4ed8";

/** Leaflet pin color for a 0–100 recommendation score. Null means not scored yet. */
export function markerColorForScore(score) {
  if (score == null || !Number.isFinite(Number(score))) return UNSCORED_COLOR;
  const value = Number(score);
  if (value >= 80) return "#15803d";
  if (value >= 60) return "#65a30d";
  if (value >= 40) return "#ca8a04";
  if (value >= 20) return "#ea580c";
  return "#b91c1c";
}

/**
 * Map a future GET /recommend `recommendations` array onto spot ids.
 * Expected item shape matches SpotRecommendation: { spot_id, best_score }.
 */
export function scoresFromRecommendations(recommendations) {
  const scores = {};
  if (!Array.isArray(recommendations)) return scores;
  for (const rec of recommendations) {
    const id = rec?.spot_id;
    const raw = rec?.best_score;
    // null/omitted means "not scored", which is distinct from a real 0.
    if (typeof id !== "string" || !id || raw == null || raw === "") continue;
    const score = Number(raw);
    if (Number.isFinite(score)) scores[id] = score;
  }
  return scores;
}

export function spotsEndpoint() {
  const configured = import.meta.env?.VITE_API_BASE;
  const base = typeof configured === "string" ? configured.trim().replace(/\/+$/, "") : "";
  return `${base}/spots`;
}

export function isMappableSpot(spot) {
  return Boolean(spot) && Number.isFinite(Number(spot.lat)) && Number.isFinite(Number(spot.lon));
}

export function spotActivities(spot) {
  if (!Array.isArray(spot?.activities)) return [];
  return spot.activities.map((activity) => String(activity).toLowerCase());
}

export function filterSpots(spots, activity) {
  const list = Array.isArray(spots) ? spots : [];
  if (!activity || activity === "all") return list.slice();
  const wanted = String(activity).toLowerCase();
  return list.filter((spot) => spotActivities(spot).includes(wanted));
}

export function formatActivity(activity) {
  const text = String(activity || "");
  if (!text) return "";
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Arrow rotation and label for shoreline_orientation_deg (0 = north, 90 = east). */
export function shorelineFacing(degrees) {
  if (degrees == null || degrees === "") return null;
  const value = Number(degrees);
  if (!Number.isFinite(value)) return null;
  const rotation = ((value % 360) + 360) % 360;
  const cardinals = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const cardinal = cardinals[Math.round(rotation / 45) % 8];
  const label = Number.isInteger(value) ? String(value) : String(Math.round(value * 10) / 10);
  return { degrees: value, label, cardinal, rotation };
}

function boundsFromBbox(bbox) {
  if (!Array.isArray(bbox) || bbox.length !== 4) return null;
  const [minLon, minLat, maxLon, maxLat] = bbox.map(Number);
  if (![minLon, minLat, maxLon, maxLat].every(Number.isFinite)) return null;
  if (minLat > maxLat || minLon > maxLon) return null;
  return [
    [minLat, minLon],
    [maxLat, maxLon],
  ];
}

/**
 * Leaflet lat/lng bounds [[south, west], [north, east]].
 * Prefers bbox [minLon, minLat, maxLon, maxLat] when the API sends one
 * (same order as region.yaml). Otherwise frames the spots that were returned.
 */
export function regionBounds(spots, bbox) {
  const fromApi = boundsFromBbox(bbox);
  if (fromApi) return fromApi;
  const points = (Array.isArray(spots) ? spots : []).filter(isMappableSpot);
  if (!points.length) return null;
  let minLat = Infinity;
  let minLon = Infinity;
  let maxLat = -Infinity;
  let maxLon = -Infinity;
  for (const spot of points) {
    const lat = Number(spot.lat);
    const lon = Number(spot.lon);
    minLat = Math.min(minLat, lat);
    maxLat = Math.max(maxLat, lat);
    minLon = Math.min(minLon, lon);
    maxLon = Math.max(maxLon, lon);
  }
  return [
    [minLat, minLon],
    [maxLat, maxLon],
  ];
}

export async function fetchSpots(signal) {
  let response;
  try {
    response = await fetch(spotsEndpoint(), {
      signal,
      headers: { Accept: "application/json" },
    });
  } catch (err) {
    if (err?.name === "AbortError") throw err;
    throw new Error(API_DOWN_MESSAGE);
  }
  if (!response.ok) throw new Error(API_DOWN_MESSAGE);
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error(API_DOWN_MESSAGE);
  }
  if (!body || typeof body !== "object" || !Array.isArray(body.spots)) {
    throw new Error(API_DOWN_MESSAGE);
  }
  return {
    regionId: typeof body.region_id === "string" ? body.region_id : "",
    spots: body.spots,
    bbox: body.bbox ?? null,
  };
}
