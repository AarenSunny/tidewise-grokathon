"""Context feeds that are not required live safety gates.

C-HARM, satellite chlorophyll, UV, the daylight cross-check, and the extra
tide-interval product are optional. When they are down or stale they stay on
GET /health and are left out of user-facing explanations. Measured safety
blocks (closures, bacteria, NWS alerts, and a chlorophyll value that is
actually over the bloom threshold) are unchanged. No value is invented.
"""

from __future__ import annotations

# Adapter registry names.
OPTIONAL_CONTEXT_SOURCES = frozenset(
    {
        "erddap_chl",
        "erddap_charm",
        "epa_uv",
        "daylight_sunrise_api",
        "coops_tides_interval",
    }
)

# Scorer / config keys for the same context feeds.
OPTIONAL_CONTEXT_SCORER_KEYS = frozenset({"satellite_chl"})

# Gates that only exist to read an optional context feed.
# A real fail (measured bloom) is still shown. cannot_confirm is not.
OPTIONAL_CONTEXT_GATES = frozenset({"no_bloom"})

HIDDEN_NOTE = "some optional data sources hidden"

# Live safety feeds whose outage may leave a window UNKNOWN.
# CO-OPS and NDBC count when the activity's gates list them.
REQUIRED_LIVE_SAFETY_SOURCES = frozenset(
    {
        "nws_alerts",
        "coops_tides",
        "coops_currents",
        "ndbc_buoy",
    }
)


def is_optional_context_source(name: str) -> bool:
    return name in OPTIONAL_CONTEXT_SOURCES or name in OPTIONAL_CONTEXT_SCORER_KEYS
