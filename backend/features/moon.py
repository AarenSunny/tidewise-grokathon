"""Offline moon phase.

0 is new moon and 0.5 is full moon. The epoch is the 6 January 2000 18:14 UTC
new moon and the synodic month is 29.530588853 days. No network call.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.features.timeutil import to_utc
from backend.models.features import HourlyFeatures

_SYNODIC_DAYS = 29.530588853
_KNOWN_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)


def moon_phase(moment: datetime) -> float:
    """Phase in ``[0, 1)``. 0 new, 0.25 first quarter, 0.5 full, 0.75 last quarter."""

    utc = to_utc(moment, "moon time")
    elapsed_days = (utc - _KNOWN_NEW_MOON).total_seconds() / 86400.0
    return (elapsed_days % _SYNODIC_DAYS) / _SYNODIC_DAYS


def annotate_moon(hours: list[HourlyFeatures]) -> list[HourlyFeatures]:
    """Fill ``moon_phase`` when the feature hour did not already carry one."""

    filled: list[HourlyFeatures] = []
    for hour in hours:
        if hour.moon_phase is not None:
            filled.append(hour)
            continue
        filled.append(hour.model_copy(update={"moon_phase": moon_phase(hour.hour)}))
    return filled
