"""Mark is_daylight from the offline solar calculation.

Clamming hours in 14 CCR §29.20 run from 30 minutes before sunrise until
30 minutes after sunset. The same window is what ``is_daylight`` means so
the daylight gate sees a real solar value rather than a placeholder.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from backend.features.solar import SolarTimes, solar_times
from backend.features.timeutil import LA, to_la
from backend.models.features import HourlyFeatures


def annotate_daylight(
    hours: list[HourlyFeatures],
    latitude: float,
    longitude: float,
    *,
    margin_minutes: int = 30,
) -> list[HourlyFeatures]:
    """Return copies of ``hours`` with sunrise, sunset, twilight, and is_daylight."""

    cache: dict[date, SolarTimes] = {}
    updated: list[HourlyFeatures] = []
    margin = timedelta(minutes=margin_minutes)
    for hour in hours:
        local = to_la(hour.hour, "feature hour")
        solar = cache.get(local.date())
        if solar is None:
            solar = solar_times(local.date(), latitude, longitude)
            cache[local.date()] = solar
        opens = solar.sunrise - margin
        closes = solar.sunset + margin
        updated.append(
            hour.model_copy(
                update={
                    "sunrise": solar.sunrise,
                    "sunset": solar.sunset,
                    "civil_dawn": solar.civil_dawn,
                    "civil_dusk": solar.civil_dusk,
                    "is_daylight": opens <= local <= closes,
                }
            )
        )
    return updated


def legal_light_intervals(
    start: datetime,
    end: datetime,
    latitude: float,
    longitude: float,
    *,
    margin_minutes: int = 30,
) -> list[tuple[datetime, datetime]]:
    """Local-light intervals overlapping ``[start, end)``, in America/Los_Angeles."""

    local_start = to_la(start, "window start")
    local_end = to_la(end, "window end")
    margin = timedelta(minutes=margin_minutes)
    pieces: list[tuple[datetime, datetime]] = []
    day = local_start.date() - timedelta(days=1)
    last = local_end.date() + timedelta(days=1)
    while day <= last:
        solar = solar_times(day, latitude, longitude)
        opens = solar.sunrise - margin
        closes = solar.sunset + margin
        lo = max(local_start, opens)
        hi = min(local_end, closes)
        if lo < hi:
            pieces.append((lo, hi))
        day += timedelta(days=1)
    return pieces


def daylight_label(moment: datetime, latitude: float, longitude: float, *, margin_minutes: int = 30) -> bool:
    local = to_la(moment, "moment").astimezone(LA)
    solar = solar_times(local.date(), latitude, longitude)
    margin = timedelta(minutes=margin_minutes)
    return solar.sunrise - margin <= local <= solar.sunset + margin
