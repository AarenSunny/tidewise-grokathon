"""Unit conversions. Scorers keep tide in ft MLLW, wind in knots, and
temperature in °C. Feet and Fahrenheit appear only as config inputs.
"""

from __future__ import annotations

METERS_PER_FOOT = 0.3048


def feet_to_meters(feet: float) -> float:
    return feet * METERS_PER_FOOT


def meters_to_feet(meters: float) -> float:
    return meters / METERS_PER_FOOT


def fahrenheit_to_celsius(fahrenheit: float) -> float:
    return (fahrenheit - 32.0) * 5.0 / 9.0
