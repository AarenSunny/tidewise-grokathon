"""Rule-based intent parser for POST /query. No network, never invents spots."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.models.common import Activity
from backend.models.intent import Preferences, QueryIntent
from backend.models.spots import Spot

_ACTIVITY_WORDS = {
    Activity.clamming: ("clam",),
    Activity.crabbing: ("crab", "dungeness"),
    Activity.swimming: ("swim",),
    Activity.sailing: ("sail",),
}
_GEAR_WORDS = (
    ("hoop_net", ("hoop net", "hoop-net", "hoopnet", "hoop")),
    ("loop_trap", ("loop trap",)),
    ("snare", ("snare",)),
    ("hand", ("by hand", "hands", "hand")),
    ("trap", ("crab trap", "traps", "trap")),
)
_ALIASES = {
    "pillar point": "pillar_point_harbor",
    "half moon": "half_moon_bay_state_beach",
    "hmb": "half_moon_bay_state_beach",
    "pacifica": "pacifica_linda_mar",
    "ocean beach": "ocean_beach_sf",
    "crissy": "crissy_field",
    "tomales": "tomales_inverness",
    "bodega": "bodega_harbor",
    "baker beach": "baker_beach",
}


def parse_intent(text: str, spots: list[Spot]) -> tuple[QueryIntent, Optional[str]]:
    lower = text.lower()
    activity = next(
        (a for a, words in _ACTIVITY_WORDS.items() if any(w in lower for w in words)), None
    )
    gear = next((g for g, words in _GEAR_WORDS if any(w in lower for w in words)), None)
    matched: list[Spot] = []
    for s in spots:
        if s.name.lower() in lower or s.id.replace("_", " ") in lower:
            matched.append(s)
    for alias, sid in _ALIASES.items():
        hit = next((s for s in spots if s.id == sid), None)
        if alias in lower and hit is not None and hit not in matched:
            matched.append(hit)
    now = datetime.now(timezone.utc)
    clarifying = None
    if activity is None:
        clarifying = "Which activity: clamming, crabbing, swimming, or sailing?"
    elif not matched:
        clarifying = (
            "Which spot? Name a TideWise spot (for example Pillar Point Harbor), "
            "or use GET /recommend with lat/lon."
        )
    intent = QueryIntent(
        activity=activity,
        location=matched[0].name if matched else None,
        spot_ids=[s.id for s in matched],
        start=now,
        end=now + timedelta(hours=48),
        preferences=Preferences(extra={"parse": "rule", **({"gear": gear} if gear else {})}),
        clarifying_question=clarifying,
        raw_text=text[:2000],
    )
    return intent, gear
