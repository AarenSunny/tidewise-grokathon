/**
 * Parsers for the phase-3 API contract.
 * Live UI only renders what these endpoints return. Fixtures are for tests.
 *
 * Factors: { name, value, unit, verdict, source, observed_at, age_minutes }
 * verdict: good | fair | poor | blocked | cannot_confirm
 * Replay responses may include mode: "replay" and snapshot_time.
 */

import { formatActivity } from "./spots.js";

export const PACIFIC = "America/Los_Angeles";
export const GOOD_SCORE_THRESHOLD = 70;
export const STALE_AFTER_MINUTES = 360;
export const VERDICTS = ["good", "fair", "poor", "blocked", "cannot_confirm"];

const VERDICT_SET = new Set(VERDICTS);

export function replayMeta(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) return null;
  if (body.mode !== "replay") return null;
  const snapshot = body.snapshot_time ?? body.snapshot ?? body.as_of ?? null;
  return { mode: "replay", snapshot: snapshot || null };
}

export function formatPacific(iso, options = {}) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("en-US", { timeZone: PACIFIC, ...options })
    .format(date)
    .replace(/[\u202f\u00a0]/g, " ");
}

export function formatPacificDate(iso) {
  return formatPacific(iso, { month: "short", day: "numeric", year: "numeric" });
}

export function formatObserved(iso) {
  return formatPacific(iso, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

export function replayLabel(snapshot) {
  const when = snapshot
    ? formatPacific(snapshot, {
        weekday: "short",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        timeZoneName: "short",
      })
    : "time unknown";
  return `Replay data, snapshot ${when}`;
}

export function formatAge(ageMinutes) {
  if (ageMinutes == null || ageMinutes === "") return null;
  const minutes = Number(ageMinutes);
  if (!Number.isFinite(minutes) || minutes < 0) return null;
  const rounded = Math.round(minutes);
  if (rounded < 1) return "just now";
  if (rounded < 60) return `${rounded} min old`;
  const hours = Math.floor(rounded / 60);
  const rest = rounded % 60;
  if (rest === 0) return `${hours} h old`;
  return `${hours} h ${rest} min old`;
}

export function normalizeFactor(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const name = typeof raw.name === "string" ? raw.name.trim() : "";
  if (!name) return null;
  const verdict = typeof raw.verdict === "string" ? raw.verdict.trim() : "";
  const ageRaw = raw.age_minutes ?? raw.ageMinutes;
  const age = ageRaw == null || ageRaw === "" ? null : Number(ageRaw);
  return {
    name,
    value: raw.value == null ? null : raw.value,
    unit: raw.unit ? String(raw.unit) : "",
    verdict: VERDICT_SET.has(verdict) ? verdict : verdict,
    reason: raw.reason || raw.detail || "",
    source: raw.source ? String(raw.source) : "",
    observedAt: raw.observed_at || raw.observedAt || "",
    ageMinutes: Number.isFinite(age) ? age : null,
    stale: raw.stale === true || raw.status === "stale",
    status: typeof raw.status === "string" ? raw.status : "",
  };
}

export function factorIsCited(factor) {
  return Boolean(factor?.source && factor?.observedAt);
}

export function isStaleFactor(factor) {
  if (!factor) return false;
  if (factor.stale || factor.status === "stale") return true;
  return Number.isFinite(factor.ageMinutes) && factor.ageMinutes >= STALE_AFTER_MINUTES;
}

export function formatValue(value) {
  if (value == null || value === "") return "";
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(Math.round(value * 1000) / 1000);
  }
  const text = String(value).trim();
  const numeric = Number(text.replace(/,/g, ""));
  if (text && Number.isFinite(numeric) && /^-?\d/.test(text)) {
    return String(Math.round(numeric * 1000) / 1000);
  }
  return text;
}

export function formatFactorPhrase(factor) {
  if (!factor) return "";
  const verdict = factor.verdict ? ` (${String(factor.verdict).replaceAll("_", " ")})` : "";
  const cited = factorIsCited(factor);
  const hasValue = factor.value != null && factor.value !== "";
  if (factor.verdict === "cannot_confirm") {
    if (hasValue && cited) return `${factor.name} ${formatValue(factor.value)}${factor.unit ? ` ${factor.unit}` : ""} (cannot confirm)`;
    return `${factor.name}: cannot confirm`;
  }
  if (hasValue && !cited) {
    return `${factor.name}${verdict} — number withheld, no source or time`;
  }
  if (!hasValue) return `${factor.name}${verdict}`.trim();
  if (String(factor.value).toLowerCase() === "none") return `no ${factor.name}${verdict}`;
  const unit = factor.unit ? ` ${factor.unit}` : "";
  return `${factor.name} ${formatValue(factor.value)}${unit}${verdict}`;
}

export function citationLine(factor) {
  if (!factorIsCited(factor)) return "No source and observation time — number withheld.";
  const parts = [factor.source];
  const when = formatObserved(factor.observedAt);
  if (when) parts.push(when);
  const age = formatAge(factor.ageMinutes);
  if (age) parts.push(age);
  if (isStaleFactor(factor)) parts.push("stale");
  return parts.join(" · ");
}

export function blockedReasons(factors, extra) {
  const reasons = [];
  if (typeof extra === "string" && extra.trim()) reasons.push(extra.trim());
  else if (extra && typeof extra === "object") {
    const reason = extra.reason || extra.blocked_reason;
    if (reason) reasons.push(String(reason));
  }
  for (const factor of factors || []) {
    if (factor?.verdict !== "blocked") continue;
    const reason = factor.reason || factor.name;
    if (reason) reasons.push(String(reason));
  }
  return [...new Set(reasons)];
}

export function presentAnswer(answer, factors) {
  const text = typeof answer === "string" ? answer : "";
  const cited = [];
  for (const factor of factors || []) {
    if (!factorIsCited(factor) || factor.value == null || factor.value === "") continue;
    const numeric = Number(String(factor.value).replace(/,/g, ""));
    if (Number.isFinite(numeric)) cited.push(numeric);
  }
  let withheld = false;
  const shown = text.replace(/-?\d[\d,]*(?:\.\d+)?/g, (token) => {
    const numeric = Number(token.replace(/,/g, ""));
    const match = cited.some((value) => nearlyEqual(value, numeric));
    if (match) return token;
    withheld = true;
    return "…";
  });
  return {
    text: shown,
    withheld,
    citedCount: (factors || []).filter(factorIsCited).length,
  };
}

function nearlyEqual(left, right) {
  const scale = Math.max(Math.abs(left), Math.abs(right), 1);
  return Math.abs(left - right) <= scale * 1e-6;
}

export function normalizeWindow(raw, fallback = {}) {
  if (!raw || typeof raw !== "object") return null;
  const start = raw.start || raw.start_time;
  const end = raw.end || raw.end_time;
  if (!start || !end) return null;
  const startMs = new Date(start).getTime();
  const endMs = new Date(end).getTime();
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs <= startMs) return null;
  const score = raw.score == null || raw.score === "" ? null : Number(raw.score);
  return {
    spotId: raw.spot_id || fallback.spotId || "",
    activity: String(raw.activity || fallback.activity || ""),
    start,
    end,
    startMs,
    endMs,
    summary: raw.summary || raw.label || raw.note || "",
    score: Number.isFinite(score) ? score : null,
  };
}

export function windowsInView(windows, nowMs, hours = 72) {
  const end = nowMs + hours * 3600000;
  return (windows || []).filter((window) => window.endMs > nowMs && window.startMs < end);
}

export function bestWindow(windows) {
  const list = (windows || []).filter(Boolean);
  if (!list.length) return null;
  return list.reduce((best, window) => {
    const score = Number.isFinite(window.score) ? window.score : -Infinity;
    const bestScore = Number.isFinite(best.score) ? best.score : -Infinity;
    if (score > bestScore) return window;
    if (score === bestScore && window.startMs < best.startMs) return window;
    return best;
  });
}

export function formatWindowRange(startIso, endIso) {
  const start = new Date(startIso);
  const end = new Date(endIso);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return "";
  const day = formatPacific(startIso, { weekday: "short" });
  const clock = {
    timeZone: PACIFIC,
    hour: "numeric",
    minute: "2-digit",
  };
  const startTime = formatPacific(startIso, clock);
  const endTime = formatPacific(endIso, clock);
  const startParts = splitMeridiem(startTime);
  const endParts = splitMeridiem(endTime);
  const range = startParts && endParts && startParts.meridiem === endParts.meridiem
    ? `${startParts.clock}–${endParts.clock} ${endParts.meridiem}`
    : `${startTime}–${endTime}`;
  return `${day} ${range}`;
}

function splitMeridiem(value) {
  const match = String(value || "").match(/^(.*?)\s*(AM|PM)$/i);
  if (!match) return null;
  return { clock: match[1], meridiem: match[2].toUpperCase() };
}

export function bestWindowCaption(window) {
  if (!window) return "";
  const when = formatWindowRange(window.start, window.end);
  const activity = (window.activity || "window").toLowerCase();
  const detail = window.summary ? `, ${window.summary}` : "";
  return `Best ${activity}: ${when}${detail}`;
}

export function activityLabel(activity) {
  return formatActivity(activity);
}

function normalizeRecommendation(raw, payload) {
  if (!raw || typeof raw !== "object") return null;
  const spotId = raw.spot_id || raw.spotId;
  if (!spotId) return null;
  const activity = raw.activity || payload.activity || "";
  const ownFactors = Array.isArray(raw.factors) ? raw.factors : null;
  const factorSource = ownFactors || (Array.isArray(payload.factors) ? payload.factors : []);
  const factors = factorSource.map(normalizeFactor).filter(Boolean);
  const windows = (Array.isArray(raw.windows) ? raw.windows : [])
    .map((window) => normalizeWindow(window, { spotId, activity }))
    .filter(Boolean);
  const safety = raw.safety || null;
  const extraReason = safety?.reason || raw.blocked_reason || "";
  const scoreRaw = raw.best_score ?? raw.bestScore;
  const bestScore = scoreRaw == null || scoreRaw === "" ? null : Number(scoreRaw);
  return {
    spotId: String(spotId),
    spotName: raw.spot_name || raw.spotName || "",
    activity: String(activity),
    factors,
    windows,
    blocked: blockedReasons(factors, extraReason),
    note: typeof raw.note === "string" ? raw.note : "",
    bestScore: Number.isFinite(bestScore) ? bestScore : null,
  };
}

export function parseRecommend(body) {
  const payload = body && typeof body === "object" ? body : {};
  const recommendations = (Array.isArray(payload.recommendations) ? payload.recommendations : [])
    .map((rec) => normalizeRecommendation(rec, payload))
    .filter(Boolean);
  const factors = (Array.isArray(payload.factors) ? payload.factors : [])
    .map(normalizeFactor)
    .filter(Boolean);
  return {
    activity: payload.activity || null,
    recommendations,
    factors,
    note: typeof payload.note === "string" ? payload.note : "",
    replay: replayMeta(payload),
  };
}

export function indexRecommendations(payloads) {
  const bySpot = {};
  let replay = null;
  const notes = [];
  for (const payload of payloads || []) {
    if (payload?.replay) replay = payload.replay;
    if (payload?.note) notes.push(payload.note);
    for (const rec of payload?.recommendations || []) {
      const bucket = bySpot[rec.spotId] || {
        spotId: rec.spotId,
        spotName: rec.spotName,
        activities: {},
        factors: [],
        windows: [],
        blocked: [],
        note: "",
        bestScore: null,
      };
      if (rec.spotName) bucket.spotName = rec.spotName;
      if (rec.activity) bucket.activities[rec.activity] = rec;
      bucket.factors = bucket.factors.concat(rec.factors);
      bucket.windows = bucket.windows.concat(rec.windows);
      bucket.blocked = [...new Set([...bucket.blocked, ...rec.blocked])];
      if (!bucket.note && rec.note) bucket.note = rec.note;
      if (rec.bestScore != null) {
        bucket.bestScore = bucket.bestScore == null ? rec.bestScore : Math.max(bucket.bestScore, rec.bestScore);
      }
      bySpot[rec.spotId] = bucket;
    }
  }
  const scores = {};
  for (const [id, bucket] of Object.entries(bySpot)) {
    if (bucket.blocked.length) scores[id] = { score: bucket.bestScore, blocked: true };
    else if (bucket.bestScore != null) scores[id] = bucket.bestScore;
  }
  return {
    bySpot,
    scores,
    replay,
    note: notes.find(Boolean) || "",
  };
}

export function insightFor(bucket, activity) {
  if (!bucket) return null;
  if (!activity || activity === "all") return bucket;
  const specific = bucket.activities?.[activity];
  if (specific) return specific;
  return {
    spotId: bucket.spotId,
    activity,
    factors: [],
    windows: [],
    blocked: [],
    note: bucket.note || "",
    bestScore: null,
  };
}

export function normalizeAlert(raw) {
  if (!raw || typeof raw !== "object") return null;
  const id = raw.id || raw.alert_id;
  const spotId = raw.spot_id || raw.spotId;
  const activity = raw.activity;
  if (!id || !spotId || !activity) return null;
  const threshold = Number(raw.threshold);
  return {
    id: String(id),
    spotId: String(spotId),
    activity: String(activity),
    threshold: Number.isFinite(threshold) ? threshold : GOOD_SCORE_THRESHOLD,
  };
}

export function parseAlerts(body) {
  const list = Array.isArray(body) ? body : body?.alerts;
  return {
    alerts: (Array.isArray(list) ? list : []).map(normalizeAlert).filter(Boolean),
    replay: replayMeta(body),
    note: typeof body?.note === "string" ? body.note : "",
  };
}

export function parseSatellite(body) {
  const source = Array.isArray(body?.layers) ? body.layers : Array.isArray(body) ? body : [];
  return {
    replay: replayMeta(body),
    layers: source.map(normalizeSatelliteLayer).filter(Boolean),
  };
}

function normalizeSatelliteLayer(raw) {
  if (!raw || typeof raw !== "object") return null;
  const name = raw.name || raw.title || raw.id || "Satellite";
  const wmsUrl = raw.wms_url || raw.wmsUrl || raw.url || "";
  const latestDate = raw.latest_date || raw.last_date || raw.observed_at || raw.time || null;
  const status = raw.status === "ok" || raw.status === "stale" || raw.status === "down"
    ? raw.status
    : wmsUrl
      ? "ok"
      : "down";
  return {
    id: String(raw.id || name).toLowerCase().replace(/\s+/g, "_"),
    name: String(name),
    units: raw.units || raw.unit || "",
    latestDate,
    wmsUrl: String(wmsUrl),
    wmsLayer: raw.wms_layer || raw.wmsLayer || raw.layers || inferWmsLayer(raw, wmsUrl),
    fallbackUrl: resolveFallbackUrl(wmsUrl, raw.fallback_host || raw.fallback_url || raw.fallback || ""),
    styles: raw.styles == null ? "" : String(raw.styles),
    colorScale: raw.colorscalerange || raw.color_scale || raw.colorscale || "",
    status,
    attribution: raw.attribution || "NOAA CoastWatch ERDDAP",
  };
}

function inferWmsLayer(raw, wmsUrl) {
  const parameter = raw.parameter || raw.variable;
  const match = String(wmsUrl || "").match(/\/wms\/([^/]+)\//i);
  if (match && parameter) return `${match[1]}:${parameter}`;
  return "";
}

export function resolveFallbackUrl(wmsUrl, fallback) {
  if (!fallback) return "";
  const text = String(fallback);
  if (/\/wms\//i.test(text)) return text;
  try {
    const primary = new URL(wmsUrl);
    const host = new URL(text.includes("://") ? text : `https://${text}`);
    primary.protocol = host.protocol;
    primary.host = host.host;
    return primary.toString();
  } catch {
    return "";
  }
}

export function satelliteUnavailableMessage(layer, lastDate) {
  const when = formatPacificDate(lastDate || layer?.latestDate);
  const name = layer?.name ? `${layer.name}: ` : "";
  if (when) return `${name}satellite layer unavailable. Last date shown: ${when}.`;
  return `${name}satellite layer unavailable.`;
}

export function colorScaleStops(colorScale) {
  if (!colorScale || typeof colorScale !== "string") return null;
  const parts = colorScale.split(",").map((part) => Number(part.trim()));
  if (parts.length < 2 || parts.some((value) => !Number.isFinite(value))) return null;
  return [parts[0], parts[parts.length - 1]];
}
