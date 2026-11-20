"""Parse activity-gate rule strings. Unknown or malformed rules fail at load."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Union

RuleValue = Union[float, bool, str]

_COMPARE = re.compile(
    r"^(?P<field>[a-z][a-z0-9_]*)\s*(?P<op><=|>=|==|!=|<|>)\s*(?P<value>.+)$"
)
_NOT_ACTIVE = re.compile(r"^(?P<field>[a-z][a-z0-9_]*)\s+not\s+active$")

# Fields the engine knows how to evaluate. A rule that names anything else
# is rejected at load so a typo cannot skip a gate.
SIMPLE_FIELDS = {
    "tide_height_ft_mllw",
    "is_daylight",
    "is_slack_water",
    "is_minus_tide",
    "wind_speed_kt",
    "wind_gust_kt",
    "gust_spread_kt",
    "wave_height_m",
    "wave_period_s",
    "sst_c",
    "sst_anomaly_c",
    "moon_phase",
    "current_velocity_kt",
    "wind_onshore_component_kt",
}
COMPUTED_FIELDS = {
    "shellfish_closure",
    "bacteria_advisory",
    "thunderstorm_alert",
    "rip_current_risk",
    "season_open",
    "gear_allowed",
    "dungeness_water_legal",
    "bloom_clear",
    "cold_shock_clear",
    "small_craft_clear",
    "ebb_against_swell",
}
_OPS = {"<=", ">=", "==", "!=", "<", ">"}
_BOOL_WORDS = {"true": True, "false": False}


class ScorerConfigError(ValueError):
    """An activity YAML gate or weight is missing or malformed."""


@dataclass(frozen=True)
class Rule:
    raw: str
    field: str
    op: str
    value: RuleValue


def parse_rule(raw: object) -> Rule:
    if not isinstance(raw, str) or not raw.strip():
        raise ScorerConfigError("gate rule must be a non-empty string")
    text = " ".join(raw.strip().split())
    not_active = _NOT_ACTIVE.fullmatch(text)
    if not_active:
        field = not_active.group("field")
        _require_known(field, text)
        return Rule(raw=text, field=field, op="not_active", value="active")
    match = _COMPARE.fullmatch(text)
    if match is None:
        raise ScorerConfigError(f"malformed gate rule: {raw!r}")
    field = match.group("field")
    op = match.group("op")
    if op not in _OPS:
        raise ScorerConfigError(f"unsupported operator in rule: {raw!r}")
    _require_known(field, text)
    return Rule(raw=text, field=field, op=op, value=_parse_value(match.group("value"), text))


def _require_known(field: str, raw: str) -> None:
    if field not in SIMPLE_FIELDS and field not in COMPUTED_FIELDS:
        raise ScorerConfigError(f"unknown field {field!r} in gate rule: {raw!r}")


def _parse_value(token: str, raw: str) -> RuleValue:
    word = token.strip()
    lowered = word.lower()
    if lowered in _BOOL_WORDS:
        return _BOOL_WORDS[lowered]
    try:
        if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", word):
            return float(word)
    except ValueError as exc:
        raise ScorerConfigError(f"malformed gate rule value: {raw!r}") from exc
    if re.fullmatch(r"[a-z][a-z0-9_]*", lowered):
        return lowered
    raise ScorerConfigError(f"malformed gate rule value: {raw!r}")


def validate_activity_config(config: dict[str, Any], activity: str) -> list[tuple[dict[str, Any], Rule]]:
    """Reject a config that could skip a gate. Returns gates paired with rules."""

    if not isinstance(config, dict):
        raise ScorerConfigError("activity config must be a mapping")
    declared = config.get("activity")
    if declared != activity:
        raise ScorerConfigError(f"config activity {declared!r} does not match {activity!r}")
    gates = config.get("gates")
    if not isinstance(gates, list) or not gates:
        raise ScorerConfigError("activity config needs at least one gate")
    parsed: list[tuple[dict[str, Any], Rule]] = []
    names: set[str] = set()
    for gate in gates:
        if not isinstance(gate, dict):
            raise ScorerConfigError("each gate must be a mapping")
        unknown = set(gate) - {
            "name",
            "rule",
            "missing",
            "sources",
            "unit",
            "blocked_reason",
            "display",
            "factor",
            "advisory",
            "summary_name",
        }
        if unknown:
            raise ScorerConfigError(f"unknown gate keys: {sorted(unknown)}")
        name = gate.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ScorerConfigError("gate name is missing")
        if name in names:
            raise ScorerConfigError(f"duplicate gate name {name!r}")
        names.add(name)
        if gate.get("missing") != "cannot_confirm":
            raise ScorerConfigError(
                f"gate {name!r} must set missing: cannot_confirm, not {gate.get('missing')!r}"
            )
        sources = gate.get("sources", [])
        if not isinstance(sources, list) or not all(isinstance(item, str) for item in sources):
            raise ScorerConfigError(f"gate {name!r} sources must be a list of names")
        parsed.append((gate, parse_rule(gate.get("rule"))))
    weights = config.get("weights", {})
    if not isinstance(weights, dict):
        raise ScorerConfigError("weights must be a mapping")
    for key, spec in weights.items():
        weight = spec.get("weight") if isinstance(spec, dict) else spec
        if isinstance(spec, dict) and set(spec) - _WEIGHT_KEYS:
            raise ScorerConfigError(f"unknown keys on weight {key!r}")
        if not isinstance(weight, (int, float)) or isinstance(weight, bool):
            raise ScorerConfigError(f"weight {key!r} must be a number")
        if weight < 0:
            raise ScorerConfigError(f"weight {key!r} cannot be negative")
    penalties = config.get("confidence_penalties", {})
    if not isinstance(penalties, dict):
        raise ScorerConfigError("confidence_penalties must be a mapping")
    return parsed


_WEIGHT_KEYS = {
    "weight",
    "field",
    "aggregate",
    "curve",
    "anchors",
    "scores",
    "anchors_ft",
    "anchors_f",
    "target_hours",
    "folk_wisdom",
    "display",
    "summary_name",
    "unit",
    "summary_unit",
    "source",
}
