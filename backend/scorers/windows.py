"""Ranked activity windows for the next 48–72 hours.

Candidates come from tide or current predictions and from daylight. Each
candidate is then passed through the activity gates (season, closures, bloom,
gear). Labels and start/end are America/Los_Angeles.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from backend.features.tides import (
    find_clamming_windows,
    find_crabbing_windows,
    find_daylight_windows,
)
from backend.features.timeutil import LA, to_la, to_utc
from backend.models.features import (
    ConditionWindow,
    CurrentSample,
    HourlyFeatures,
    SpotFeatureGrid,
    TideSample,
)
from backend.models.scoring import ScoredWindow

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def best_windows(
    grid: SpotFeatureGrid,
    activity: str,
    *,
    latitude: float,
    longitude: float,
    as_of: datetime | None = None,
    horizon_hours: int = 72,
    gear: str | None = None,
    tides: list[TideSample] | None = None,
    currents: list[CurrentSample] | None = None,
) -> list[ScoredWindow]:
    """Ranked windows from ``as_of`` through the next 48–72 hours."""

    if horizon_hours < 48 or horizon_hours > 72:
        raise ValueError("horizon_hours must be between 48 and 72")
    start = to_la(as_of, "as_of") if as_of is not None else datetime.now(LA)
    end = start + timedelta(hours=horizon_hours)
    return ranked_windows(
        grid,
        activity,
        start,
        end,
        latitude=latitude,
        longitude=longitude,
        gear=gear,
        tides=tides,
        currents=currents,
        as_of=start,
    )


def ranked_windows(
    grid: SpotFeatureGrid,
    activity: str,
    start: datetime,
    end: datetime,
    *,
    latitude: float,
    longitude: float,
    gear: str | None = None,
    tides: list[TideSample] | None = None,
    currents: list[CurrentSample] | None = None,
    as_of: datetime | None = None,
) -> list[ScoredWindow]:
    """Score candidate windows inside ``[start, end)`` and label them."""

    from backend.scorers import get_scorer

    scorer = get_scorer(activity)
    reference = to_la(as_of, "as_of") if as_of is not None else to_la(start, "window start")
    intervals = _candidates(
        activity,
        grid,
        start,
        end,
        latitude,
        longitude,
        scorer.config,
        tides,
        currents,
    )
    scored: list[ScoredWindow] = []
    for window_start, window_end in intervals:
        if window_end <= window_start:
            continue
        scored.append(
            scorer.score_window(
                grid,
                window_start,
                window_end,
                lat=latitude,
                lon=longitude,
                gear=gear,
                as_of=reference,
            )
        )
    scored.sort(key=lambda item: (not item.eligible, -item.score, item.start))
    phrase = str(scorer.config.get("window_phrase") or activity)
    best_assigned = False
    labeled: list[ScoredWindow] = []
    for window in scored:
        if window.eligible and not best_assigned:
            prefix = f"Best {activity}"
            best_assigned = True
        else:
            prefix = activity.capitalize()
        label = f"{prefix}: {_when(window.start, window.end)}, {phrase}"
        labeled.append(window.model_copy(update={"label": label}))
    return labeled


def _candidates(
    activity: str,
    grid: SpotFeatureGrid,
    start: datetime,
    end: datetime,
    latitude: float,
    longitude: float,
    config: dict,
    tides: list[TideSample] | None,
    currents: list[CurrentSample] | None,
) -> list[tuple[datetime, datetime]]:
    start_utc = to_utc(start, "window start")
    end_utc = to_utc(end, "window end")
    if activity == "clamming":
        found = _clamming_candidates(grid, latitude, longitude, config, tides)
    elif activity == "crabbing":
        found = _crabbing_candidates(grid, config, currents, tides)
    else:
        margin = int(config.get("daylight_margin_minutes", 30))
        found = find_daylight_windows(start, end, latitude, longitude, margin_minutes=margin)
    bounded: list[tuple[datetime, datetime]] = []
    for window in found:
        lo = max(to_utc(window.start, "candidate start"), start_utc)
        hi = min(to_utc(window.end, "candidate end"), end_utc)
        if hi > lo:
            bounded.append((to_la(lo, "candidate start"), to_la(hi, "candidate end")))
    return bounded


def _clamming_candidates(grid, latitude, longitude, config, tides: list[TideSample] | None):
    samples = list(tides or [])
    if not samples:
        samples = [
            TideSample(time=hour.hour, height_ft_mllw=hour.tide_height_ft_mllw)
            for hour in grid.hours
            if hour.tide_height_ft_mllw is not None
        ]
    tide_cfg = config.get("tide_window", {})
    return find_clamming_windows(
        samples,
        threshold_ft_mllw=float(tide_cfg.get("threshold_ft_mllw", 0.0)),
        latitude=latitude,
        longitude=longitude,
        clip_daylight=True,
        margin_minutes=int(config.get("daylight_margin_minutes", 30)),
        depth_weight=float(tide_cfg.get("depth_weight", 0.7)),
        duration_weight=float(tide_cfg.get("duration_weight", 0.3)),
        target_hours=float(tide_cfg.get("target_hours", 3)),
    )


def _crabbing_candidates(grid, config, currents, tides) -> list[ConditionWindow]:
    if currents:
        current_cfg = config.get("currents", {})
        return find_crabbing_windows(
            currents,
            slack_max_kt=float(current_cfg.get("slack_max_kt", 0.5)),
            moderate_max_kt=float(current_cfg.get("moderate_max_kt", 1.5)),
            slack_rank_bonus=float(current_cfg.get("slack_rank_bonus", 20)),
        )
    from_hours = _slack_runs(grid.hours)
    if from_hours:
        return from_hours
    return _slack_from_tide_turns(tides or _tide_samples(grid), config)


def _tide_samples(grid: SpotFeatureGrid) -> list[TideSample]:
    return [
        TideSample(time=hour.hour, height_ft_mllw=hour.tide_height_ft_mllw, kind=None)
        for hour in grid.hours
        if hour.tide_height_ft_mllw is not None
    ]


def _slack_runs(hours: list[HourlyFeatures]) -> list[ConditionWindow]:
    ordered = sorted(
        (hour for hour in hours if hour.hour.tzinfo is not None),
        key=lambda hour: hour.hour,
    )
    runs: list[list[HourlyFeatures]] = []
    current: list[HourlyFeatures] = []
    for hour in ordered:
        slack = hour.is_slack_water is True or (hour.tide_phase or "").lower() == "slack"
        if slack:
            current.append(hour)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    windows: list[ConditionWindow] = []
    for index, run in enumerate(runs, start=1):
        start = to_la(run[0].hour, "slack start")
        end = to_la(run[-1].hour, "slack end") + timedelta(hours=1)
        windows.append(
            ConditionWindow(
                start=start,
                end=end,
                extremum_value=0.0,
                extremum_at=start,
                duration_hours=(end - start).total_seconds() / 3600.0,
                kind="slack",
                score=0.0,
                rank=index,
            )
        )
    return windows


def _slack_from_tide_turns(samples: list[TideSample], config: dict) -> list[ConditionWindow]:
    half = timedelta(minutes=int(config.get("currents", {}).get("slack_half_window_minutes", 45)))
    windows: list[ConditionWindow] = []
    turns = [sample for sample in samples if (sample.kind or "").upper() in {"H", "L"}]
    for index, sample in enumerate(sorted(turns, key=lambda item: item.time), start=1):
        center = to_la(sample.time, "tide turn")
        windows.append(
            ConditionWindow(
                start=center - half,
                end=center + half,
                extremum_value=sample.height_ft_mllw,
                extremum_at=center,
                duration_hours=half.total_seconds() / 1800.0,
                kind="slack",
                score=0.0,
                rank=index,
            )
        )
    return windows


def _when(start: datetime, end: datetime) -> str:
    local_start = to_la(start, "label start")
    local_end = to_la(end, "label end")
    start_clock, start_suffix = _clock(local_start)
    end_clock, end_suffix = _clock(local_end)
    day = _WEEKDAYS[local_start.weekday()]
    if start_suffix == end_suffix:
        return f"{day} {start_clock}-{end_clock} {start_suffix}"
    return f"{day} {start_clock} {start_suffix}-{end_clock} {end_suffix}"


def _clock(moment: datetime) -> tuple[str, str]:
    suffix = "AM" if moment.hour < 12 else "PM"
    hour = moment.hour % 12
    if hour == 0:
        hour = 12
    return f"{hour}:{moment.minute:02d}", suffix
