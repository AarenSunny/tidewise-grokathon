"""ONE alias map: scorer/config source keys -> adapter registry names (PR3-1).

The scorers (backend/scorers, config/activities/*.yaml) speak in config keys such as
``alerts_shellfish``; the adapter registry uses adapter names such as ``cdph_shellfish``.
Keys with no adapter (``nws_marine``, ``nws_alerts``) map to ``None``: the grid leaves
them absent, so gates that need them are cannot_confirm (never a pass).
"""

from __future__ import annotations

from typing import Optional

SCORER_TO_REGISTRY: dict[str, Optional[str]] = {
    "coops_tides": "coops_tides",
    "coops_currents": "coops_currents",
    "ndbc_buoy": "ndbc_buoy",
    "alerts_shellfish": "cdph_shellfish",
    "alerts_bacteria": "beachwatch_bacteria",
    "satellite_chl": "erddap_chl",
    "sst": "erddap_sst",
    "nws_marine": None,  # no NWS adapter on main
    "nws_alerts": None,
}

REGISTRY_TO_SCORER: dict[str, str] = {v: k for k, v in SCORER_TO_REGISTRY.items() if v}

# Registry names the orchestrator must fetch so the grid can be built.
FETCH_SOURCES: tuple[str, ...] = tuple(sorted(REGISTRY_TO_SCORER))
