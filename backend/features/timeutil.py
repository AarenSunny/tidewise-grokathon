"""Timezone helpers. Calculations use UTC; scorer output uses America/Los_Angeles."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LA = ZoneInfo("America/Los_Angeles")
UTC = timezone.utc


class NaiveDateTimeError(ValueError):
    """A datetime on the scorer boundary was missing a timezone."""


def require_aware(value: datetime, what: str) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise NaiveDateTimeError(f"{what} must be timezone-aware")
    return value


def to_utc(value: datetime, what: str = "datetime") -> datetime:
    return require_aware(value, what).astimezone(UTC)


def to_la(value: datetime, what: str = "datetime") -> datetime:
    return require_aware(value, what).astimezone(LA)
