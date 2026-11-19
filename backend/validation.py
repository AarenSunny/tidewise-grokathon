"""Shared sentinel / range helpers for adapters (review1-#8)."""

from __future__ import annotations

import math
from typing import Any, Optional

# NDBC realtime2 missing markers
NDBC_MISSING = {"MM", "mm", "999", "99.0", "999.0", "9999", "9999.0"}

# NASA POWER fill
POWER_FILL = {-999, -999.0}

# ERDDAP common fills
ERDDAP_FILL_HINTS = {-99999, -99999.0, -7.768}


def is_missing_ndbc(token: Any) -> bool:
    if token is None:
        return True
    s = str(token).strip()
    if s in NDBC_MISSING or s == "":
        return True
    return False


def parse_float_or_none(token: Any, *, missing: Optional[set] = None) -> Optional[float]:
    if token is None:
        return None
    if isinstance(token, float) and (math.isnan(token) or math.isinf(token)):
        return None
    s = str(token).strip()
    miss = missing or NDBC_MISSING
    if s in miss or s == "":
        return None
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    if v in POWER_FILL or v in ERDDAP_FILL_HINTS:
        return None
    return v


def in_range(v: Optional[float], lo: float, hi: float) -> Optional[float]:
    if v is None:
        return None
    if v < lo or v > hi:
        return None
    return v


def ms_to_knots(ms: Optional[float]) -> Optional[float]:
    if ms is None:
        return None
    return ms * 1.94384


def c_to_f(c: Optional[float]) -> Optional[float]:
    if c is None:
        return None
    return c * 9.0 / 5.0 + 32.0
