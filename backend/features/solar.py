"""Offline sunrise, sunset, and civil twilight.

The equations are the NOAA Global Monitoring Laboratory solar calculator
(https://gml.noaa.gov/grad/solcalc/calcdetails.html). Nothing in this module
calls the network. Returned times are timezone-aware America/Los_Angeles.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from backend.features.timeutil import LA

# Official sunrise/sunset includes atmospheric refraction and the solar radius.
_SUNRISE_ZENITH_DEG = 90.833
# Civil twilight: geometric center of the sun is 6 degrees below the horizon.
_CIVIL_ZENITH_DEG = 96.0


@dataclass(frozen=True)
class SolarTimes:
    """Solar events for one local civil date."""

    day: date
    latitude: float
    longitude: float
    sunrise: datetime
    sunset: datetime
    civil_dawn: datetime
    civil_dusk: datetime


def solar_times(day: date, latitude: float, longitude: float) -> SolarTimes:
    """Sunrise, sunset, and civil twilight for ``day`` at lat/lon.

    ``longitude`` is degrees east (west longitudes are negative).
    """

    sunrise = _event(day, latitude, longitude, _SUNRISE_ZENITH_DEG, rise=True)
    sunset = _event(day, latitude, longitude, _SUNRISE_ZENITH_DEG, rise=False)
    civil_dawn = _event(day, latitude, longitude, _CIVIL_ZENITH_DEG, rise=True)
    civil_dusk = _event(day, latitude, longitude, _CIVIL_ZENITH_DEG, rise=False)
    return SolarTimes(
        day=day,
        latitude=latitude,
        longitude=longitude,
        sunrise=sunrise,
        sunset=sunset,
        civil_dawn=civil_dawn,
        civil_dusk=civil_dusk,
    )


def _event(day: date, latitude: float, longitude: float, zenith: float, *, rise: bool) -> datetime:
    julian = _julian_day(day.year, day.month, day.day)
    minutes = _rise_set_utc_minutes(julian, latitude, longitude, zenith, rise)
    # NOAA iterates once the event's own Julian century is known.
    for _ in range(2):
        julian_at_event = julian + minutes / 1440.0
        minutes = _rise_set_utc_minutes(julian_at_event, latitude, longitude, zenith, rise)
    base = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return (base + timedelta(minutes=minutes)).astimezone(LA)


def _julian_day(year: int, month: int, day: int) -> float:
    """Julian day at 0h UT for a Gregorian calendar date (NOAA getJD)."""

    if month <= 2:
        year -= 1
        month += 12
    century = math.floor(year / 100)
    gregorian = 2 - century + math.floor(century / 4)
    return (
        math.floor(365.25 * (year + 4716))
        + math.floor(30.6001 * (month + 1))
        + day
        + gregorian
        - 1524.5
    )


def _julian_century(julian_day: float) -> float:
    return (julian_day - 2451545.0) / 36525.0


def _geom_mean_longitude(century: float) -> float:
    longitude = 280.46646 + century * (36000.76983 + century * 0.0003032)
    return longitude % 360.0


def _geom_mean_anomaly(century: float) -> float:
    return 357.52911 + century * (35999.05029 - 0.0001537 * century)


def _eccentricity(century: float) -> float:
    return 0.016708634 - century * (0.000042037 + 0.0000001267 * century)


def _equation_of_center(century: float) -> float:
    anomaly = math.radians(_geom_mean_anomaly(century))
    return (
        math.sin(anomaly) * (1.914602 - century * (0.004817 + 0.000014 * century))
        + math.sin(2 * anomaly) * (0.019993 - 0.000101 * century)
        + math.sin(3 * anomaly) * 0.000289
    )


def _sun_true_longitude(century: float) -> float:
    return _geom_mean_longitude(century) + _equation_of_center(century)


def _sun_apparent_longitude(century: float) -> float:
    omega = 125.04 - 1934.136 * century
    return _sun_true_longitude(century) - 0.00569 - 0.00478 * math.sin(math.radians(omega))


def _mean_obliquity(century: float) -> float:
    seconds = 21.448 - century * (46.8150 + century * (0.00059 - century * 0.001813))
    return 23.0 + (26.0 + seconds / 60.0) / 60.0


def _obliquity_correction(century: float) -> float:
    omega = 125.04 - 1934.136 * century
    return _mean_obliquity(century) + 0.00256 * math.cos(math.radians(omega))


def _declination(century: float) -> float:
    obliquity = _obliquity_correction(century)
    apparent = _sun_apparent_longitude(century)
    sine = math.sin(math.radians(obliquity)) * math.sin(math.radians(apparent))
    return math.degrees(math.asin(sine))


def _equation_of_time(century: float) -> float:
    obliquity = _obliquity_correction(century)
    mean_longitude = _geom_mean_longitude(century)
    eccentricity = _eccentricity(century)
    anomaly = _geom_mean_anomaly(century)
    y_term = math.tan(math.radians(obliquity) / 2.0)
    y_term *= y_term
    sin_2l = math.sin(2.0 * math.radians(mean_longitude))
    sin_m = math.sin(math.radians(anomaly))
    cos_2l = math.cos(2.0 * math.radians(mean_longitude))
    sin_4l = math.sin(4.0 * math.radians(mean_longitude))
    sin_2m = math.sin(2.0 * math.radians(anomaly))
    e_time = (
        y_term * sin_2l
        - 2.0 * eccentricity * sin_m
        + 4.0 * eccentricity * y_term * sin_m * cos_2l
        - 0.5 * y_term * y_term * sin_4l
        - 1.25 * eccentricity * eccentricity * sin_2m
    )
    return math.degrees(e_time) * 4.0


def _hour_angle(latitude: float, declination: float, zenith: float) -> float:
    lat_rad = math.radians(latitude)
    dec_rad = math.radians(declination)
    cosine = math.cos(math.radians(zenith)) / (math.cos(lat_rad) * math.cos(dec_rad))
    cosine -= math.tan(lat_rad) * math.tan(dec_rad)
    cosine = max(-1.0, min(1.0, cosine))
    return math.acos(cosine)


def _rise_set_utc_minutes(
    julian_day: float,
    latitude: float,
    longitude: float,
    zenith: float,
    rise: bool,
) -> float:
    century = _julian_century(julian_day)
    eq_time = _equation_of_time(century)
    declination = _declination(century)
    hour_angle = _hour_angle(latitude, declination, zenith)
    if not rise:
        hour_angle = -hour_angle
    delta = longitude + math.degrees(hour_angle)
    return 720.0 - (4.0 * delta) - eq_time
