"""One recommended time window for an activity and spot.

Live CO-OPS tides/currents and sunrise-sunset daylight are used when the
adapters return them. Any failure falls back to a Pacific planning window so
the response is never empty.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from backend.models.api import ScoreWindowResponse
from backend.models.common import Activity
from backend.models.spots import RegionConfig, Spot
from backend.seasons import clamming_season_status, crabbing_season_status

logger = logging.getLogger(__name__)

PT = ZoneInfo("America/Los_Angeles")
_FETCH_TIMEOUT_S = 8.0

# Short place names that are not a spot title. Crabbing at Half Moon Bay is
# Pillar Point / Princeton — the state beach itself is swim-only.
_ALIASES: dict[str, dict[Activity, str]] = {
    "half moon bay": {
        Activity.crabbing: "pillar_point_harbor",
        Activity.clamming: "pillar_point_harbor",
        Activity.sailing: "pillar_point_harbor",
        Activity.swimming: "half_moon_bay_state_beach",
    },
    "hmb": {
        Activity.crabbing: "pillar_point_harbor",
        Activity.clamming: "pillar_point_harbor",
        Activity.sailing: "pillar_point_harbor",
        Activity.swimming: "half_moon_bay_state_beach",
    },
    "pillar point": {Activity.crabbing: "pillar_point_harbor", Activity.clamming: "pillar_point_harbor", Activity.sailing: "pillar_point_harbor"},
    "princeton": {Activity.crabbing: "pillar_point_harbor", Activity.clamming: "pillar_point_harbor", Activity.sailing: "pillar_point_harbor"},
}


def _norm(text: str) -> str:
    cleaned = text.lower().replace("–", " ").replace("—", " ").replace("/", " ")
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    return " ".join(cleaned.split())


def resolve_spot(
    region: RegionConfig,
    activity: Activity,
    *,
    spot_id: Optional[str] = None,
    location: Optional[str] = None,
) -> Spot:
    """Pick a configured spot. Raises KeyError (unknown) or ValueError (bad combo)."""
    if spot_id:
        match = next((s for s in region.spots if s.id == spot_id), None)
        if match is None:
            raise KeyError(spot_id)
        if activity not in match.activities:
            raise ValueError(f"{match.name} does not support {activity.value}")
        return match

    query = _norm(location or "")
    if not query:
        raise ValueError("location or spot is required")

    exact = [
        s
        for s in region.spots
        if activity in s.activities and _norm(s.name) == query
    ]
    if len(exact) == 1:
        return exact[0]

    alias_id = _ALIASES.get(query, {}).get(activity)
    if alias_id:
        aliased = next((s for s in region.spots if s.id == alias_id), None)
        if aliased is not None and activity in aliased.activities:
            return aliased

    supporting = [s for s in region.spots if activity in s.activities]
    contained = [s for s in supporting if query in _norm(s.name) or query in s.id.replace("_", " ")]
    if len(contained) == 1:
        return contained[0]
    if len(contained) > 1:
        contained.sort(key=lambda s: (not _norm(s.name).startswith(query), len(s.name)))
        return contained[0]

    tokens = set(query.split())
    ranked: list[tuple[int, Spot]] = []
    for spot in supporting:
        overlap = tokens & set(_norm(spot.name).split())
        if overlap:
            ranked.append((len(overlap), spot))
    if ranked:
        ranked.sort(key=lambda item: (-item[0], len(item[1].name)))
        best_n, best = ranked[0]
        if best_n >= min(2, len(tokens)):
            return best

    if not supporting:
        raise KeyError(location or query)
    sample = ", ".join(s.name for s in supporting[:6])
    raise KeyError(f"{location} (try one of: {sample})")


def _as_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _points(data: Any) -> list[Any]:
    if data is None:
        return []
    points = data.get("points") if isinstance(data, dict) else getattr(data, "points", None)
    return list(points or [])


def _field(point: Any, name: str) -> Any:
    if isinstance(point, dict):
        return point.get(name)
    return getattr(point, name, None)


def tide_points_from(data: Any) -> list[tuple[datetime, float, Optional[str]]]:
    out: list[tuple[datetime, float, Optional[str]]] = []
    for point in _points(data):
        when = _as_dt(_field(point, "t"))
        height = _field(point, "v_ft_mllw")
        if when is None or height is None:
            continue
        try:
            feet = float(height)
        except (TypeError, ValueError):
            continue
        kind = _field(point, "type")
        out.append((when, feet, str(kind) if kind else None))
    out.sort(key=lambda row: row[0])
    return out


def slack_times_from(data: Any) -> list[datetime]:
    typed: list[datetime] = []
    untyped: list[datetime] = []
    for point in _points(data):
        when = _as_dt(_field(point, "t"))
        if when is None:
            continue
        kind = str(_field(point, "type") or "").lower()
        if "slack" in kind:
            typed.append(when)
        elif kind in {"", "none"}:
            untyped.append(when)
    return sorted(typed or untyped)


def _sun_field(data: Any, name: str) -> Optional[datetime]:
    if data is None:
        return None
    raw = data.get(name) if isinstance(data, dict) else getattr(data, name, None)
    return _as_dt(raw)


def _fmt(when: datetime) -> str:
    return when.astimezone(PT).strftime("%a %-I:%M %p PT")


def _overlaps(start: datetime, end: datetime, sunrise: datetime, sunset: datetime) -> bool:
    return start < sunset and end > sunrise and (min(end, sunset) - max(start, sunrise)) >= timedelta(minutes=30)


def _around(center: datetime, now: datetime, half: timedelta) -> Optional[tuple[datetime, datetime]]:
    start = center - half
    end = center + half
    if end <= now + timedelta(minutes=20):
        return None
    if start < now:
        start = now
    if end <= start + timedelta(minutes=30):
        end = start + timedelta(hours=1)
    return start, end


def _next_low(
    points: list[tuple[datetime, float, Optional[str]]], now: datetime
) -> Optional[tuple[datetime, float]]:
    labeled = [(t, h) for t, h, kind in points if (kind or "").upper() in {"L", "LOW"} and t >= now - timedelta(hours=1)]
    if labeled:
        labeled.sort(key=lambda row: row[0])
        return labeled[0]
    lows: list[tuple[datetime, float]] = []
    for i, (t, h, _kind) in enumerate(points):
        prev_h = points[i - 1][1] if i else None
        next_h = points[i + 1][1] if i + 1 < len(points) else None
        if prev_h is not None and next_h is not None and h <= prev_h and h <= next_h and t >= now - timedelta(hours=1):
            lows.append((t, h))
    if not lows:
        return None
    lows.sort(key=lambda row: row[0])
    return lows[0]


def _morning_fallback(now: datetime, activity: Activity) -> tuple[datetime, datetime]:
    hour = {Activity.swimming: 11, Activity.sailing: 10}.get(activity, 7)
    local = now.astimezone(PT)
    start_local = local.replace(hour=hour, minute=0, second=0, microsecond=0)
    if start_local <= local:
        start_local += timedelta(days=1)
    end_local = start_local + timedelta(hours=3)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _daylight_fallback(
    now: datetime,
    activity: Activity,
    sunrise: Optional[datetime],
    sunset: Optional[datetime],
) -> tuple[tuple[datetime, datetime], bool]:
    if sunrise and sunset and sunrise < sunset:
        if now < sunrise <= now + timedelta(hours=30):
            end = min(sunrise + timedelta(hours=3), sunset)
            if end > sunrise + timedelta(minutes=45):
                return (sunrise, end), True
        if sunrise <= now < sunset - timedelta(minutes=45):
            end = min(now + timedelta(hours=3), sunset)
            if end > now + timedelta(minutes=45):
                return (now, end), True
    return _morning_fallback(now, activity), False


def score_window(
    activity: Activity,
    spot: Spot,
    *,
    now: Optional[datetime] = None,
    tide_points: Optional[list[tuple[datetime, float, Optional[str]]]] = None,
    slack_times: Optional[list[datetime]] = None,
    sunrise: Optional[datetime] = None,
    sunset: Optional[datetime] = None,
    live_tide: bool = False,
    live_slack: bool = False,
    live_daylight: bool = False,
) -> ScoreWindowResponse:
    """Always return one window with a score and a short reason."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    points = tide_points or []
    slacks = slack_times or []

    start: Optional[datetime] = None
    end: Optional[datetime] = None
    basis = "fallback"
    center: Optional[datetime] = None
    height: Optional[float] = None

    if activity in {Activity.crabbing, Activity.sailing} and live_slack:
        for slack in slacks:
            span = _around(slack, now, timedelta(minutes=75))
            if span:
                start, end = span
                center = slack
                basis = "slack"
                break

    if start is None and activity in {Activity.crabbing, Activity.clamming, Activity.sailing} and live_tide:
        low = _next_low(points, now)
        if low is not None:
            span = _around(low[0], now, timedelta(minutes=90))
            if span:
                start, end = span
                center, height = low
                basis = "low"

    used_daylight = False
    if start is None:
        (start, end), used_daylight = _daylight_fallback(now, activity, sunrise if live_daylight else None, sunset if live_daylight else None)
        basis = "daylight" if used_daylight else "fallback"

    if basis == "slack":
        score = 76.0
        reason = f"Next slack current {_fmt(center)} from NOAA CO-OPS, with the window centered on that turn"
    elif basis == "low":
        score = 68.0
        height_txt = f"{height:.1f} ft MLLW" if height is not None else "the next low"
        proxy = ""
        if activity == Activity.crabbing:
            proxy = " Used as a slack proxy because a current slack time was not available."
        reason = f"Next low tide {height_txt} at {_fmt(center)} (NOAA CO-OPS).{proxy}"
        if activity == Activity.clamming and height is not None:
            if height <= 0:
                score += 12
                reason += " Minus tide — better clam exposure."
            elif height <= 1.5:
                score += 6
    elif basis == "daylight":
        score = 54.0
        if activity == Activity.swimming:
            reason = f"Daylight swim window {_fmt(start)}–{_fmt(end)} from sunrise-sunset.org"
        else:
            reason = (
                f"Daylight window {_fmt(start)}–{_fmt(end)} from sunrise-sunset.org. "
                "Tide predictions were unavailable, so this is a daylight fallback"
            )
    else:
        score = 42.0
        reason = (
            f"Live tide and daylight feeds were unavailable. "
            f"Fallback planning window {_fmt(start)}–{_fmt(end)} at {spot.name}. "
            "Verify NOAA tides before you go"
        )

    if live_daylight and sunrise and sunset and _overlaps(start, end, sunrise, sunset):
        score += 8
        if basis in {"slack", "low"}:
            reason += " The window overlaps daylight."
    elif basis in {"slack", "low"} and live_daylight:
        reason += " Daylight overlap is limited — check sunset before you go."

    if activity == Activity.crabbing:
        season = crabbing_season_status(spot, now)
        if season.dungeness_prohibited_area or not season.season_open:
            score = min(score, 28)
            reason = f"{season.reasons[0]}. {reason}"
        else:
            score += 6
            reason = f"{reason} {season.reasons[0]}."
    elif activity == Activity.clamming:
        season = clamming_season_status(now)
        if season.reasons:
            reason = f"{reason} {season.reasons[0]}."

    score = float(max(0, min(100, round(score))))
    reason = " ".join(reason.split()).strip()
    if not reason.endswith("."):
        reason += "."

    return ScoreWindowResponse(
        activity=activity,
        location=spot.name,
        spot_id=spot.id,
        start=start,
        end=end,
        score=score,
        reason=reason,
    )


async def _fetch(registry: Any, name: str, spot: Spot, start: datetime, end: datetime) -> Any:
    adapter = registry.get(name) if registry is not None else None
    if adapter is None:
        return None
    try:
        return await asyncio.wait_for(adapter.fetch(spot, start, end), timeout=_FETCH_TIMEOUT_S)
    except Exception as exc:  # noqa: BLE001 — scorer must still answer
        logger.warning("score fetch failed source=%s spot=%s err=%s", name, spot.id, type(exc).__name__)
        return None


def _usable(result: Any) -> Any:
    if result is None:
        return None
    status = getattr(getattr(result, "status", None), "value", None) or str(getattr(result, "status", ""))
    data = getattr(result, "data", None)
    if data is None:
        return None
    if status in {"down", "unknown"}:
        return None
    return data


async def collect_signals(registry: Any, spot: Spot, start: datetime, end: datetime) -> dict[str, Any]:
    """Fetch tide, slack, and daylight. Missing feeds become empty signals."""
    tide_res, current_res, day_res = await asyncio.gather(
        _fetch(registry, "coops_tides", spot, start, end),
        _fetch(registry, "coops_currents", spot, start, end),
        _fetch(registry, "daylight_sunrise_api", spot, start, end),
    )
    tide_data = _usable(tide_res)
    current_data = _usable(current_res)
    day_data = _usable(day_res)
    tides = tide_points_from(tide_data)
    slacks = slack_times_from(current_data)
    sunrise = _sun_field(day_data, "sunrise")
    sunset = _sun_field(day_data, "sunset")
    return {
        "tide_points": tides,
        "slack_times": slacks,
        "sunrise": sunrise,
        "sunset": sunset,
        "live_tide": bool(tides),
        "live_slack": bool(slacks),
        "live_daylight": sunrise is not None and sunset is not None,
    }
