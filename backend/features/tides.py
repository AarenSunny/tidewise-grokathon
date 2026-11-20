"""Contiguous tide and current windows.

Heights are feet MLLW. Current velocity is knots and ebb is negative,
matching CO-OPS ``Velocity_Major``. Hi/lo series (gaps over 20 minutes)
are interpolated with a cosine between turning points. Denser series,
including 6-minute predictions, are interpolated linearly. Output times
are America/Los_Angeles.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from backend.features.daylight import legal_light_intervals
from backend.features.timeutil import to_la, to_utc
from backend.models.features import ConditionWindow, CurrentSample, TideSample

_SPARSE_GAP_SECONDS = 20 * 60


def find_clamming_windows(
    samples: list[TideSample],
    *,
    threshold_ft_mllw: float,
    latitude: float | None = None,
    longitude: float | None = None,
    clip_daylight: bool = False,
    margin_minutes: int = 30,
    depth_weight: float = 0.7,
    duration_weight: float = 0.3,
    target_hours: float = 3.0,
) -> list[ConditionWindow]:
    """Windows where the tide is at or below ``threshold_ft_mllw``.

    Each window carries the low (minimum) height, its time, and the duration.
    When ``clip_daylight`` is set, windows are cut to the legal-light interval
    and pieces that fall entirely at night are dropped.
    """

    points = _sorted_tides(samples)
    raw = _below_threshold(points, threshold_ft_mllw)
    if clip_daylight:
        if latitude is None or longitude is None:
            raise ValueError("daylight clipping requires latitude and longitude")
        raw = _clip_to_daylight(raw, points, latitude, longitude, margin_minutes)
    ranked = _rank(
        raw,
        kind="minus_tide",
        score_of=lambda item: _clam_score(
            item,
            threshold_ft_mllw,
            depth_weight,
            duration_weight,
            target_hours,
        ),
    )
    return ranked


def find_crabbing_windows(
    samples: list[CurrentSample],
    *,
    slack_max_kt: float,
    moderate_max_kt: float,
    slack_rank_bonus: float = 20.0,
) -> list[ConditionWindow]:
    """Slack and moderate-current windows from a current series.

    Slack is ``|velocity| <= slack_max_kt``. Moderate is stronger than slack
    and at or below ``moderate_max_kt``. The extremum is the lowest absolute
    velocity in the window (closest to slack).
    """

    if moderate_max_kt < slack_max_kt:
        raise ValueError("moderate_max_kt must be at least slack_max_kt")
    points = _sorted_currents(samples)
    pieces = _current_pieces(points, slack_max_kt, moderate_max_kt)
    return _rank(
        pieces,
        kind=None,
        score_of=lambda item: _current_score(item, slack_max_kt, moderate_max_kt, slack_rank_bonus),
    )


def find_ebb_windows(
    samples: list[CurrentSample],
    *,
    ebb_velocity_kt_at_or_below: float,
) -> list[ConditionWindow]:
    """Windows where ebb velocity is at or below the configured knot line."""

    points = _sorted_currents(samples)
    raw: list[_Span] = []
    for start, end, kind, extremum, extremum_at in _threshold_runs(
        [(point.time, point.velocity_kt) for point in points],
        limit=ebb_velocity_kt_at_or_below,
        at_or_below=True,
        cosine=False,
    ):
        raw.append(_Span(start, end, "ebb", extremum, extremum_at))
    return _rank(raw, kind="ebb", score_of=lambda item: item.duration_hours)


def find_daylight_windows(
    start: datetime,
    end: datetime,
    latitude: float,
    longitude: float,
    *,
    margin_minutes: int = 30,
) -> list[ConditionWindow]:
    """Legal-light windows inside ``[start, end)``."""

    intervals = legal_light_intervals(
        start, end, latitude, longitude, margin_minutes=margin_minutes
    )
    spans = [
        _Span(lo, hi, "daylight", None, lo)
        for lo, hi in intervals
    ]
    return _rank(spans, kind="daylight", score_of=lambda item: item.duration_hours)


class _Span:
    def __init__(
        self,
        start: datetime,
        end: datetime,
        kind: str,
        extremum: float | None,
        extremum_at: datetime | None,
    ) -> None:
        self.start = start
        self.end = end
        self.kind = kind
        self.extremum = extremum
        self.extremum_at = extremum_at

    @property
    def duration_hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600.0


def _sorted_tides(samples: list[TideSample]) -> list[tuple[datetime, float]]:
    points = [(to_utc(sample.time, "tide time"), sample.height_ft_mllw) for sample in samples]
    points.sort(key=lambda item: item[0])
    return points


def _sorted_currents(samples: list[CurrentSample]) -> list[tuple[datetime, float]]:
    points = [(to_utc(sample.time, "current time"), sample.velocity_kt) for sample in samples]
    points.sort(key=lambda item: item[0])
    return points


def _sparse(points: list[tuple[datetime, float]]) -> bool:
    gaps = [
        (points[index + 1][0] - points[index][0]).total_seconds()
        for index in range(len(points) - 1)
    ]
    return bool(gaps) and max(gaps) > _SPARSE_GAP_SECONDS


def _below_threshold(points: list[tuple[datetime, float]], threshold: float) -> list[_Span]:
    spans: list[_Span] = []
    for start, end, _kind, extremum, extremum_at in _threshold_runs(
        points,
        limit=threshold,
        at_or_below=True,
        cosine=_sparse(points),
    ):
        spans.append(_Span(start, end, "minus_tide", extremum, extremum_at))
    return spans


def _threshold_runs(
    points: list[tuple[datetime, float]],
    *,
    limit: float,
    at_or_below: bool,
    cosine: bool,
) -> list[tuple[datetime, datetime, str, float | None, datetime | None]]:
    """Return runs where the series meets the inequality.

    Extremum is the minimum value inside an at-or-below run, or the maximum
    inside an at-or-above run, taken from original samples when one falls
    inside the run.
    """

    if not points:
        return []

    def meets(value: float) -> bool:
        if at_or_below:
            return value <= limit + 1e-9
        return value >= limit - 1e-9

    runs: list[tuple[datetime, datetime, str, float | None, datetime | None]] = []
    inside = meets(points[0][1])
    start = points[0][0]
    samples: list[tuple[datetime, float]] = []
    if inside:
        samples.append(points[0])

    for (time_a, value_a), (time_b, value_b) in zip(points, points[1:]):
        a_in = meets(value_a)
        b_in = meets(value_b)
        if a_in and b_in:
            samples.append((time_b, value_b))
            continue
        if a_in and not b_in:
            crossed = _crossing_time(time_a, value_a, time_b, value_b, limit, cosine)
            end = crossed if crossed is not None else time_b
            extremum, extremum_at = _extremum(samples, at_or_below)
            runs.append((start, end, "", extremum, extremum_at))
            inside = False
            samples = []
            continue
        if not a_in and b_in:
            crossed = _crossing_time(time_a, value_a, time_b, value_b, limit, cosine)
            start = crossed if crossed is not None else time_b
            samples = [(time_b, value_b)]
            inside = True
    if inside and samples:
        extremum, extremum_at = _extremum(samples, at_or_below)
        runs.append((start, points[-1][0], "", extremum, extremum_at))
    return [run for run in runs if run[1] >= run[0]]


def _extremum(
    samples: list[tuple[datetime, float]],
    at_or_below: bool,
) -> tuple[float | None, datetime | None]:
    if not samples:
        return None, None
    if at_or_below:
        moment, value = min(samples, key=lambda item: item[1])
    else:
        moment, value = max(samples, key=lambda item: item[1])
    return value, moment


def _crossing_time(
    time_a: datetime,
    value_a: float,
    time_b: datetime,
    value_b: float,
    limit: float,
    cosine: bool,
) -> datetime | None:
    fraction = _crossing_fraction(value_a, value_b, limit, cosine)
    if fraction is None:
        return None
    delta = time_b - time_a
    return time_a + timedelta(seconds=delta.total_seconds() * fraction)


def _crossing_fraction(value_a: float, value_b: float, limit: float, cosine: bool) -> float | None:
    if cosine:
        midpoint = 0.5 * (value_a + value_b)
        amplitude = 0.5 * (value_a - value_b)
        if abs(amplitude) < 1e-12:
            return None
        cosine_value = (limit - midpoint) / amplitude
        if cosine_value < -1.0 or cosine_value > 1.0:
            return None
        return math.acos(cosine_value) / math.pi
    if value_b == value_a:
        return None
    fraction = (limit - value_a) / (value_b - value_a)
    if 0.0 <= fraction <= 1.0:
        return fraction
    return None


def _clip_to_daylight(
    spans: list[_Span],
    points: list[tuple[datetime, float]],
    latitude: float,
    longitude: float,
    margin_minutes: int,
) -> list[_Span]:
    clipped: list[_Span] = []
    for span in spans:
        intervals = legal_light_intervals(
            span.start,
            span.end,
            latitude,
            longitude,
            margin_minutes=margin_minutes,
        )
        for lo, hi in intervals:
            lo_utc = to_utc(lo, "clip start")
            hi_utc = to_utc(hi, "clip end")
            inside = [(moment, height) for moment, height in points if lo_utc <= moment <= hi_utc]
            if inside:
                extremum, extremum_at = _extremum(inside, True)
            else:
                extremum, extremum_at = span.extremum, span.extremum_at
            clipped.append(_Span(lo_utc, hi_utc, span.kind, extremum, extremum_at))
    return clipped


def _current_pieces(
    points: list[tuple[datetime, float]],
    slack_max: float,
    moderate_max: float,
) -> list[_Span]:
    """Classify sub-segments by absolute velocity at the midpoint."""

    if len(points) < 2:
        if len(points) == 1:
            speed = abs(points[0][1])
            kind = _speed_kind(speed, slack_max, moderate_max)
            if kind is None:
                return []
            return [_Span(points[0][0], points[0][0], kind, speed, points[0][0])]
        return []
    cuts = [points[0][0]]
    for (time_a, value_a), (time_b, value_b) in zip(points, points[1:]):
        for limit in (slack_max, moderate_max, -slack_max, -moderate_max):
            if (value_a - limit) * (value_b - limit) < 0:
                fraction = (limit - value_a) / (value_b - value_a)
                cuts.append(time_a + (time_b - time_a) * fraction)
        cuts.append(time_b)
    cuts = sorted(set(cuts))
    pieces: list[_Span] = []
    open_span: _Span | None = None
    for left, right in zip(cuts, cuts[1:]):
        if right <= left:
            continue
        mid = left + (right - left) / 2
        speed = abs(_interp(points, mid))
        kind = _speed_kind(speed, slack_max, moderate_max)
        if kind is None:
            if open_span is not None:
                pieces.append(open_span)
                open_span = None
            continue
        if open_span is not None and open_span.kind == kind and open_span.end == left:
            open_span.end = right
            if open_span.extremum is None or speed < open_span.extremum:
                open_span.extremum = speed
                open_span.extremum_at = mid
        else:
            if open_span is not None:
                pieces.append(open_span)
            open_span = _Span(left, right, kind, speed, mid)
    if open_span is not None:
        pieces.append(open_span)
    return pieces


def _speed_kind(speed: float, slack_max: float, moderate_max: float) -> str | None:
    if speed <= slack_max + 1e-9:
        return "slack"
    if speed <= moderate_max + 1e-9:
        return "moderate_current"
    return None


def _interp(points: list[tuple[datetime, float]], moment: datetime) -> float:
    if moment <= points[0][0]:
        return points[0][1]
    if moment >= points[-1][0]:
        return points[-1][1]
    for (time_a, value_a), (time_b, value_b) in zip(points, points[1:]):
        if time_a <= moment <= time_b:
            span = (time_b - time_a).total_seconds()
            if span <= 0:
                return value_b
            fraction = (moment - time_a).total_seconds() / span
            return value_a + (value_b - value_a) * fraction
    return points[-1][1]


def _clam_score(
    span: _Span,
    threshold: float,
    depth_weight: float,
    duration_weight: float,
    target_hours: float,
) -> float:
    low = span.extremum if span.extremum is not None else threshold
    depth = max(0.0, min(1.0, (threshold - low) / 2.0))
    duration = 0.0 if target_hours <= 0 else min(1.0, span.duration_hours / target_hours)
    return 100.0 * (depth_weight * depth + duration_weight * duration)


def _current_score(span: _Span, slack_max: float, moderate_max: float, slack_bonus: float) -> float:
    speed = span.extremum if span.extremum is not None else moderate_max
    ceiling = slack_max if span.kind == "slack" else moderate_max
    closeness = 1.0 if ceiling <= 0 else max(0.0, 1.0 - speed / ceiling)
    bonus = slack_bonus if span.kind == "slack" else 0.0
    return bonus + 80.0 * closeness + min(span.duration_hours, 3.0)


def _rank(spans: list[_Span], *, kind: str | None, score_of) -> list[ConditionWindow]:
    scored = [(score_of(span), span) for span in spans if span.end >= span.start]
    scored.sort(key=lambda item: (-item[0], -item[1].duration_hours, item[1].start))
    windows: list[ConditionWindow] = []
    for index, (score, span) in enumerate(scored, start=1):
        windows.append(
            ConditionWindow(
                start=to_la(span.start, "window start"),
                end=to_la(span.end, "window end"),
                extremum_value=span.extremum,
                extremum_at=to_la(span.extremum_at, "extremum") if span.extremum_at else None,
                duration_hours=span.duration_hours,
                kind=kind or span.kind,
                score=score,
                rank=index,
            )
        )
    return windows
