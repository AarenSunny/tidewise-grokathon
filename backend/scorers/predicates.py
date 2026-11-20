"""Computed safety predicates. None means the gate cannot confirm."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from backend.features.bloom import bloom_status, resolve_region
from backend.features.timeutil import LA, to_la
from backend.features.units import fahrenheit_to_celsius, meters_to_feet
from backend.models.common import SourceStatus
from backend.models.features import HourlyFeatures, SpotFeatureGrid

_SENTINEL_STRINGS = {"", "mm", "n/a", "na", "unknown", "none", "null"}


@dataclass
class Decision:
    passed: bool
    cannot_confirm: bool
    reason: str
    evidence: str
    causes: list[tuple[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.passed and self.cannot_confirm:
            raise ValueError("a gate cannot pass when cannot_confirm is true")
        if self.cannot_confirm:
            self.passed = False


@dataclass
class EvalContext:
    hours: list[HourlyFeatures]
    grid: SpotFeatureGrid
    start: datetime
    end: datetime
    latitude: float | None
    longitude: float | None
    gear: str | None
    config: dict[str, Any]
    region: dict[str, Any]
    as_of: datetime | None = None


def cite(records: list[dict[str, Any]]) -> str:
    """JSON evidence. Values are copied from inputs; explainers may cite only these."""

    return "cited:" + json.dumps(records, separators=(",", ":"), ensure_ascii=True, default=str)


def unconfirmed(reason: str, evidence: str, causes: list[tuple[str, str]]) -> Decision:
    return Decision(False, True, reason, evidence, causes)


def failed(reason: str, evidence: str) -> Decision:
    return Decision(False, False, reason, evidence, [])


def passed(reason: str, evidence: str) -> Decision:
    return Decision(True, False, reason, evidence, [])


def numeric_sentinel(kind: str, value: object) -> str | None:
    """Return a cause token when ``value`` must not be treated as a measurement."""

    if value is None:
        return "missing"
    if isinstance(value, str):
        return "unknown" if value.strip().lower() in _SENTINEL_STRINGS else "unknown"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "unknown"
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        return "unknown"
    if kind == "tide" and (abs(number) >= 30 or number in (-999, -9999, 999, 9999)):
        return "sentinel"
    if kind == "wind" and (number < 0 or number >= 150 or number in (99, 999)):
        return "sentinel"
    if kind == "temp_c" and (number < -2 or number > 45 or number <= -999 or abs(number + 7.768) < 0.02):
        return "sentinel"
    if kind == "wave_m" and (number < 0 or number > 30 or number in (99, 999)):
        return "sentinel"
    if kind == "chl" and (number < 0 or number > 500 or number <= -999):
        return "sentinel"
    if kind == "moon" and (number < 0 or number > 1):
        return "sentinel"
    if kind == "velocity" and abs(number) > 20:
        return "sentinel"
    if kind == "generic" and abs(number) >= 1e6:
        return "sentinel"
    return None


def hour_value_records(hours: list[HourlyFeatures], name: str, unit: str) -> list[dict[str, Any]]:
    records = []
    for hour in hours:
        moment = hour.hour if hour.hour.tzinfo is None else to_la(hour.hour, "hour")
        records.append(
            {
                "name": name,
                "value": getattr(hour, name),
                "unit": unit,
                "at": moment.isoformat(),
            }
        )
    return records


def alerts_match(hours: list[HourlyFeatures], patterns: list[str]) -> list[str]:
    found: list[str] = []
    needles = [pattern.lower() for pattern in patterns]
    for hour in hours:
        for alert in hour.active_alerts:
            text = alert.lower()
            if any(needle in text for needle in needles):
                found.append(alert)
    return found


def season_decision(ctx: EvalContext) -> Decision:
    season = ctx.config.get("season")
    evidence = cite([{"name": "hour", "value": _first_local_iso(ctx), "unit": "America/Los_Angeles"}])
    if not isinstance(season, dict) or season.get("confirmed") is not True:
        return unconfirmed(
            "season data is missing or unconfirmed",
            evidence,
            [("season data is missing", "missing")],
        )
    if not ctx.hours:
        return unconfirmed("no hourly features in the window", evidence, [("hours missing", "missing")])
    local_dates = _local_dates(ctx)
    if local_dates is None:
        return unconfirmed(
            "feature hour is not timezone-aware",
            evidence,
            [("hour timestamp unknown", "unknown")],
        )
    if season.get("always_open") is True:
        return passed("season is open for this activity (configured always_open)", evidence)
    try:
        open_day = date.fromisoformat(str(season["open"]))
        close_day = date.fromisoformat(str(season["close"]))
    except (KeyError, ValueError):
        return unconfirmed(
            "season open/close dates are missing",
            evidence,
            [("season dates missing", "missing")],
        )
    before = season.get("before_open", "cannot_confirm")
    after = season.get("after_close", "cannot_confirm")
    states = []
    for local_day in local_dates:
        if open_day <= local_day <= close_day:
            states.append("open")
        elif local_day < open_day:
            states.append(before)
        else:
            states.append(after)
    if "closed" in states or "prohibited" in states:
        return failed("season is closed on a date in this window", evidence)
    if any(state != "open" for state in states):
        return unconfirmed(
            "season is not confirmed for a date in this window",
            evidence,
            [("season unconfirmed for date", "unknown")],
        )
    return passed(
        f"season is open {open_day.isoformat()} through {close_day.isoformat()} (America/Los_Angeles)",
        evidence,
    )


def gear_decision(ctx: EvalContext) -> Decision:
    gear_table = ctx.config.get("gear")
    requested = ctx.gear
    evidence = cite([{"name": "gear", "value": requested, "unit": ""}])
    if not isinstance(gear_table, dict):
        return unconfirmed("gear rules are missing from config", evidence, [("gear config missing", "missing")])
    if requested is None or not str(requested).strip():
        return unconfirmed("gear type is missing", evidence, [("gear missing", "missing")])
    spec = gear_table.get(requested)
    if not isinstance(spec, dict):
        return unconfirmed(
            f"gear {requested!r} is not confirmed allowed",
            evidence,
            [(f"gear {requested} unconfirmed", "unknown")],
        )
    note = str(spec.get("note") or "").strip()
    caveat = str(spec.get("caveat") or "").strip()
    extra = " ".join(part for part in (note, caveat) if part)
    status = spec.get("status")
    if status == "allowed":
        reason = f"gear {requested} is confirmed allowed"
        if extra:
            reason = f"{reason}. {extra}"
        return passed(reason, evidence)
    if status == "restricted":
        return _restricted_gear(ctx, requested, spec, evidence, extra)
    return unconfirmed(
        f"gear {requested} is not confirmed allowed",
        evidence,
        [(f"gear {requested} unconfirmed", "unknown")],
    )


def _restricted_gear(
    ctx: EvalContext,
    requested: str,
    spec: dict[str, Any],
    evidence: str,
    extra: str,
) -> Decision:
    if not _trap_zone_applies(ctx):
        return unconfirmed(
            "crab zone is unknown, so the trap restriction cannot be confirmed clear",
            evidence,
            [("crab zone unknown", "unknown")],
        )
    local_dates = _local_dates(ctx)
    if local_dates is None:
        return unconfirmed(
            "feature hour is not timezone-aware",
            evidence,
            [("hour timestamp unknown", "unknown")],
        )
    try:
        boundary = date.fromisoformat(str(spec["boundary"]))
    except (KeyError, ValueError):
        return unconfirmed(
            "trap restriction boundary is missing",
            evidence,
            [("gear boundary missing", "missing")],
        )
    before = spec.get("before_boundary", "cannot_confirm")
    after = spec.get("on_or_after_boundary", "cannot_confirm")
    states = [before if day < boundary else after for day in local_dates]
    suffix = f" {extra}" if extra else ""
    if "prohibited" in states or "closed" in states:
        return failed(f"gear {requested} is prohibited in this window.{suffix}".rstrip(), evidence)
    if any(state != "allowed" for state in states):
        return unconfirmed(
            f"gear {requested} is not confirmed allowed on this date.{suffix}".rstrip(),
            evidence,
            [(f"gear {requested} unconfirmed", "unknown")],
        )
    return passed(f"gear {requested} is confirmed allowed.{suffix}".rstrip(), evidence)


def _trap_zone_applies(ctx: EvalContext) -> bool:
    """True only when the spot is inside a configured zone that restricts traps.

    Outside every configured zone, or with no latitude, the caller treats the
    gear as unconfirmed rather than allowed.
    """

    if ctx.latitude is None:
        return False
    zones = ctx.region.get("crab_zones", [])
    if not isinstance(zones, list):
        return False
    inside_restricted = False
    inside_any = False
    for zone in zones:
        if not isinstance(zone, dict):
            continue
        try:
            lat_min = float(zone["lat_min"])
            lat_max = float(zone["lat_max"])
        except (KeyError, TypeError, ValueError):
            continue
        if lat_min <= ctx.latitude <= lat_max:
            inside_any = True
            if zone.get("trap_restriction") is True:
                inside_restricted = True
    return inside_any and inside_restricted


def dungeness_water_decision(ctx: EvalContext) -> Decision:
    region_id = resolve_region(ctx.grid, ctx.region)
    evidence = cite(
        [
            {"name": "spot_id", "value": ctx.grid.spot_id, "unit": ""},
            {"name": "bloom_region", "value": region_id, "unit": ""},
        ]
    )
    if region_id is None:
        return unconfirmed(
            "water body is unknown, so Dungeness legality cannot be confirmed",
            evidence,
            [("dungeness water unknown", "unknown")],
        )
    prohibited = ctx.region.get("dungeness_prohibited_regions", [])
    if region_id in prohibited:
        return failed(
            "Dungeness crab may not be taken in San Francisco Bay or San Pablo Bay "
            "(14 CCR §29.85(b)(1))",
            evidence,
        )
    known = ctx.region.get("bloom_regions", {})
    if region_id not in known:
        return unconfirmed(
            f"region {region_id} has no Dungeness rule configured",
            evidence,
            [("dungeness water unknown", "unknown")],
        )
    return passed(f"spot region {region_id} is not a prohibited Dungeness water", evidence)


def bloom_decision(ctx: EvalContext) -> Decision:
    flag = bloom_status(ctx.grid, ctx.config, ctx.region)
    records: list[dict[str, Any]] = []
    if flag.chl_mg_m3 is not None:
        records.append({"name": "chl_mg_m3", "value": flag.chl_mg_m3, "unit": "mg m^-3"})
    if flag.observed_at is not None:
        records.append(
            {"name": "chlorophyll_observed_at", "value": flag.observed_at.isoformat(), "unit": "America/Los_Angeles"}
        )
    evidence = cite(records)
    if flag.cannot_confirm or flag.bloom is None:
        cause = "stale" if flag.reason.endswith("is stale") else "missing"
        if "sentinel" in flag.reason:
            cause = "sentinel"
        if "unknown" in flag.reason:
            cause = "unknown"
        return unconfirmed(flag.reason, evidence, [(flag.reason, cause)])
    if flag.bloom:
        return failed(flag.reason, evidence)
    return passed(flag.reason, evidence)


def cold_shock_decision(ctx: EvalContext) -> Decision:
    limit_f = ctx.config.get("cold_shock", {}).get("fail_at_or_below_f")
    evidence = cite(hour_value_records(ctx.hours, "sst_c", "°C"))
    if not isinstance(limit_f, (int, float)):
        return unconfirmed(
            "cold-shock threshold is missing from config",
            evidence,
            [("cold_shock threshold missing", "missing")],
        )
    limit_c = fahrenheit_to_celsius(float(limit_f))
    saw_value = False
    for hour in ctx.hours:
        problem = numeric_sentinel("temp_c", hour.sst_c)
        if problem is not None:
            return unconfirmed(
                f"sst_c is {problem}",
                evidence,
                [(f"sst_c {problem}", problem)],
            )
        saw_value = True
        assert hour.sst_c is not None
        if hour.sst_c <= limit_c:
            return failed(
                f"water temperature is at or below {limit_f}°F (cold-shock band)",
                evidence,
            )
    if not saw_value:
        return unconfirmed("sst_c is missing", evidence, [("sst_c missing", "missing")])
    return passed(f"water temperature is above {limit_f}°F", evidence)


def small_craft_decision(ctx: EvalContext) -> Decision:
    spec = ctx.config.get("small_craft", {})
    wind_limit = spec.get("wind_kt_at_or_above")
    wave_limit_ft = spec.get("wave_ft_above")
    evidence = cite(
        hour_value_records(ctx.hours, "wind_speed_kt", "kt")
        + hour_value_records(ctx.hours, "wave_height_m", "m")
        + [{"name": "active_alerts", "value": alert, "unit": ""} for hour in ctx.hours for alert in hour.active_alerts]
    )
    if not isinstance(wind_limit, (int, float)) or not isinstance(wave_limit_ft, (int, float)):
        return unconfirmed(
            "small-craft thresholds are missing from config",
            evidence,
            [("small craft thresholds missing", "missing")],
        )
    patterns = ctx.config.get("alert_patterns", {}).get("small_craft_advisory", [])
    matched = alerts_match(ctx.hours, patterns)
    if matched:
        return failed(f"small craft or hazardous seas alert is active ({matched[0]})", evidence)
    for hour in ctx.hours:
        wind_problem = numeric_sentinel("wind", hour.wind_speed_kt)
        wave_problem = numeric_sentinel("wave_m", hour.wave_height_m)
        if wind_problem is not None:
            return unconfirmed(
                f"wind_speed_kt is {wind_problem}",
                evidence,
                [(f"wind_speed_kt {wind_problem}", wind_problem)],
            )
        if wave_problem is not None:
            return unconfirmed(
                f"wave_height_m is {wave_problem}",
                evidence,
                [(f"wave_height_m {wave_problem}", wave_problem)],
            )
        assert hour.wind_speed_kt is not None and hour.wave_height_m is not None
        if hour.wind_speed_kt >= float(wind_limit):
            return failed(
                f"sustained wind is at or above {wind_limit} kt (NWS Western small-craft band)",
                evidence,
            )
        if meters_to_feet(hour.wave_height_m) > float(wave_limit_ft) + 1e-6:
            return failed(
                f"seas exceed {wave_limit_ft} ft (NWS Western small-craft band)",
                evidence,
            )
    if not ctx.hours:
        return unconfirmed("no hourly features in the window", evidence, [("hours missing", "missing")])
    return passed("no small-craft advisory and wind and seas are under the NWS lines", evidence)


def ebb_decision(ctx: EvalContext) -> Decision:
    spec = ctx.config.get("ebb_against_swell", {})
    ebb_line = spec.get("ebb_velocity_kt_at_or_below")
    wave_ft = spec.get("wave_height_ft_above")
    evidence = cite(
        hour_value_records(ctx.hours, "current_velocity_kt", "kt")
        + hour_value_records(ctx.hours, "wave_height_m", "m")
        + hour_value_records(ctx.hours, "tide_phase", "")
    )
    if not isinstance(ebb_line, (int, float)) or not isinstance(wave_ft, (int, float)):
        return unconfirmed(
            "ebb-against-swell thresholds are missing from config",
            evidence,
            [("ebb thresholds missing", "missing")],
        )
    if not ctx.hours:
        return unconfirmed("no hourly features in the window", evidence, [("hours missing", "missing")])
    for hour in ctx.hours:
        wave_problem = numeric_sentinel("wave_m", hour.wave_height_m)
        if wave_problem is not None:
            return unconfirmed(
                f"wave_height_m is {wave_problem}",
                evidence,
                [(f"wave_height_m {wave_problem}", wave_problem)],
            )
        ebbing = _is_strong_ebb(hour, float(ebb_line))
        if ebbing is None:
            return unconfirmed(
                "ebb state is unknown",
                evidence,
                [("current_velocity_kt missing", "missing")],
            )
        assert hour.wave_height_m is not None
        if ebbing and meters_to_feet(hour.wave_height_m) > float(wave_ft) + 1e-6:
            return failed(
                "ebb current meets a sea state above the configured swell line",
                evidence,
            )
    return passed("no ebb-against-swell hour in this window", evidence)


def _is_strong_ebb(hour: HourlyFeatures, ebb_line: float) -> bool | None:
    if hour.current_velocity_kt is not None:
        problem = numeric_sentinel("velocity", hour.current_velocity_kt)
        if problem is not None:
            return None
        return hour.current_velocity_kt <= ebb_line
    phase = (hour.tide_phase or "").strip().lower()
    if phase in {"falling", "ebb"}:
        return True
    if phase in {"rising", "flood", "slack", "high", "low"}:
        return False
    return None


def alert_state(ctx: EvalContext, pattern_key: str) -> str | None:
    """Return active, inactive, or None when the alert list cannot be trusted.

    Source freshness is applied by the engine before this runs. This only
    reads the alert strings that arrived with the hours.
    """

    patterns = ctx.config.get("alert_patterns", {}).get(pattern_key, [])
    if not isinstance(patterns, list):
        return None
    if alerts_match(ctx.hours, [str(item) for item in patterns]):
        return "active"
    return "inactive"


def rip_state(ctx: EvalContext) -> str | None:
    patterns = ctx.config.get("alert_patterns", {}).get("rip_high", [])
    if not isinstance(patterns, list):
        return None
    if alerts_match(ctx.hours, [str(item) for item in patterns]):
        return "high"
    return "low"


def _local_dates(ctx: EvalContext) -> list[date] | None:
    dates: list[date] = []
    for hour in ctx.hours:
        if hour.hour.tzinfo is None or hour.hour.tzinfo.utcoffset(hour.hour) is None:
            return None
        dates.append(hour.hour.astimezone(LA).date())
    return dates


def _first_local_iso(ctx: EvalContext) -> str | None:
    if not ctx.hours:
        return None
    hour = ctx.hours[0].hour
    if hour.tzinfo is None:
        return None
    return hour.astimezone(LA).isoformat()


def source_problem(ctx: EvalContext, sources: list[str]) -> tuple[str, str] | None:
    """Return (note, penalty key) when a listed source is not fresh on every hour."""

    if not ctx.hours and sources:
        return (f"{sources[0]} is missing", "missing")
    for source in sources:
        statuses: list[SourceStatus] = []
        missing_hour = False
        for hour in ctx.hours:
            status = hour.source_statuses.get(source)
            if status is None:
                missing_hour = True
            else:
                statuses.append(status)
        if source == "satellite_chl" and ctx.grid.chlorophyll is not None:
            listed_on_hours = any(source in hour.source_statuses for hour in ctx.hours)
            if not listed_on_hours:
                statuses = [ctx.grid.chlorophyll.source_status]
                missing_hour = False
            else:
                statuses.append(ctx.grid.chlorophyll.source_status)
        if missing_hour or not statuses:
            return (f"{source} is missing", "missing")
        worst = _worst(statuses)
        if worst is not SourceStatus.ok:
            return (f"{source} is {worst.value}", worst.value)
    return None


def _worst(statuses: list[SourceStatus]) -> SourceStatus:
    rank = {
        SourceStatus.ok: 0,
        SourceStatus.degraded: 1,
        SourceStatus.stale: 2,
        SourceStatus.unknown: 3,
        SourceStatus.down: 4,
    }
    return max(statuses, key=lambda status: rank.get(status, 3))
