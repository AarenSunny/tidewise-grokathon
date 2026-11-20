import type {
  AdapterHealth,
  SourceBadgeKind,
  SourceFreshnessBadge,
  SourceStatus,
  SpotSourceIssue,
} from '../types';
import { formatIsoToPacificTime } from './time';

/** Treat a source as stale when last_success_at is older than this. */
export const SOURCE_STALE_AFTER_MS = 24 * 60 * 60 * 1000;

/**
 * Canonical backend source names (phase3-core) plus legacy aliases used in
 * earlier example payloads: noaa_tides → coops_tides, daylight_table →
 * daylight_sunrise_api. cdph_shellfish already matches.
 */
export const SOURCE_ALIASES: Record<string, readonly string[]> = {
  coops_tides: ['coops_tides', 'noaa_tides'],
  cdph_shellfish: ['cdph_shellfish'],
  daylight_sunrise_api: ['daylight_sunrise_api', 'daylight_table'],
};

export const SOURCE_DISPLAY_NAMES: Record<string, string> = {
  coops_tides: 'NOAA CO-OPS tides',
  noaa_tides: 'NOAA CO-OPS tides',
  coops_tides_interval: 'NOAA CO-OPS tides (interval)',
  coops_currents: 'NOAA CO-OPS currents',
  erddap_chl: 'ERDDAP chlorophyll',
  erddap_sst: 'ERDDAP SST',
  erddap_charm: 'C-HARM',
  cdph_shellfish: 'CDPH shellfish',
  ndbc_buoy: 'NDBC buoy',
  epa_uv: 'EPA UV',
  beachwatch_bacteria: 'BeachWatch bacteria',
  daylight_sunrise_api: 'Daylight',
  daylight_table: 'Daylight',
};

/** Sources whose staleness/outage means a window is not verified-safe. */
export const SAFETY_SOURCE_NAMES = new Set([
  'coops_tides',
  'cdph_shellfish',
]);

export function isTruthyEnvFlag(value: string | undefined): boolean {
  if (!value) return false;
  return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase());
}

export function canonicalSourceName(sourceName: string): string {
  if (sourceName === 'noaa_tides') return 'coops_tides';
  if (sourceName === 'daylight_table') return 'daylight_sunrise_api';
  return sourceName;
}

export function displayNameForSource(sourceName: string): string {
  return SOURCE_DISPLAY_NAMES[sourceName] ?? sourceName;
}

export function findAdapter(
  health: AdapterHealth[],
  sourceName: string,
): AdapterHealth | undefined {
  const canonical = canonicalSourceName(sourceName);
  const aliases = SOURCE_ALIASES[canonical] ?? [sourceName, canonical];
  return health.find((adapter) => {
    const name = canonicalSourceName(adapter.source_name);
    return name === canonical || aliases.includes(adapter.source_name);
  });
}

export function effectiveSourceStatus(
  health: AdapterHealth,
  asOf: Date,
): SourceStatus {
  if (health.status === 'down') return 'down';
  if (health.status === 'stale') return 'stale';
  if (health.status === 'unknown') return 'unknown';
  if (health.last_success_at) {
    const timestamp = new Date(health.last_success_at).getTime();
    if (Number.isFinite(timestamp)) {
      const ageMs = asOf.getTime() - timestamp;
      if (ageMs > SOURCE_STALE_AFTER_MS) return 'stale';
    }
  }
  return health.status;
}

/** Stale/down/unknown data must never be treated as verified-safe. */
export function isUnreliableStatus(status: SourceStatus): boolean {
  return status === 'stale' || status === 'down' || status === 'unknown';
}

/** Any non-ok effective status gets a visible warning badge. */
export function showsStaleBadge(status: SourceStatus): boolean {
  return (
    status === 'stale' ||
    status === 'down' ||
    status === 'degraded' ||
    status === 'unknown'
  );
}

export function badgeForStatus(status: SourceStatus): {
  badge: SourceBadgeKind;
  badgeLabel: SourceFreshnessBadge['badgeLabel'];
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

export function formatAgeLabel(
  lastSuccessAt: string,
  asOf: Date,
): string | undefined {
  const timestamp = new Date(lastSuccessAt).getTime();
  if (!Number.isFinite(timestamp)) return undefined;
  const ageMs = asOf.getTime() - timestamp;
  if (ageMs < 0) return undefined;
  const minutes = Math.round(ageMs / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function buildSourceBadges(
  health: AdapterHealth[],
  asOf: Date,
): SourceFreshnessBadge[] {
  return health.map((adapter) => {
    const effectiveStatus = effectiveSourceStatus(adapter, asOf);
    const { badge, badgeLabel } = badgeForStatus(effectiveStatus);
    const lastSuccessLabel = adapter.last_success_at
      ? formatIsoToPacificTime(adapter.last_success_at)
      : 'unknown';
    const ageLabel = adapter.last_success_at
      ? formatAgeLabel(adapter.last_success_at, asOf)
      : undefined;

    return {
      sourceName: canonicalSourceName(adapter.source_name),
      displayName: displayNameForSource(adapter.source_name),
      status: adapter.status,
      effectiveStatus,
      badge,
      badgeLabel,
      lastSuccessAt: adapter.last_success_at,
      lastSuccessLabel,
      ageLabel,
    };
  });
}

export function collectSourceIssues(
  health: AdapterHealth[],
  asOf: Date,
): SpotSourceIssue[] {
  const issues: SpotSourceIssue[] = [];
  for (const adapter of health) {
    const effective = effectiveSourceStatus(adapter, asOf);
    if (!showsStaleBadge(effective)) continue;
    const { badge, badgeLabel } = badgeForStatus(effective);
    if (
      badge === 'ok' ||
      (badge !== 'stale' &&
        badge !== 'unavailable' &&
        badge !== 'degraded' &&
        badge !== 'unknown')
    ) {
      continue;
    }
    const name = displayNameForSource(adapter.source_name);
    const age = adapter.last_success_at
      ? formatAgeLabel(adapter.last_success_at, asOf)
      : undefined;
    let detail: string;
    if (effective === 'down') {
      detail = `${name} is unavailable`;
    } else if (effective === 'stale') {
      detail = age
        ? `${name} is stale (last success ${age})`
        : `${name} is stale`;
    } else if (effective === 'unknown') {
      detail = `${name} status is unknown`;
    } else {
      detail = `${name} is degraded`;
    }
    issues.push({
      sourceName: canonicalSourceName(adapter.source_name),
      badge,
      badgeLabel: badgeLabel as SpotSourceIssue['badgeLabel'],
      detail,
    });
  }
  return issues;
}

export function safetySourcesUnreliable(
  health: AdapterHealth[],
  asOf: Date,
): boolean {
  for (const sourceName of SAFETY_SOURCE_NAMES) {
    const adapter = findAdapter(health, sourceName);
    if (!adapter) {
      // Missing safety source is never safe.
      return true;
    }
    if (isUnreliableStatus(effectiveSourceStatus(adapter, asOf))) {
      return true;
    }
  }
  return false;
}

export function closureSourceUnreliable(
  health: AdapterHealth[],
  asOf: Date,
): boolean {
  const adapter = findAdapter(health, 'cdph_shellfish');
  if (!adapter) return true;
  return isUnreliableStatus(effectiveSourceStatus(adapter, asOf));
}
