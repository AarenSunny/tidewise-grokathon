"""Config-driven activity scorer.

Hard gates run first. A window is eligible only when every gate passed on
fresh, non-sentinel inputs. Missing, stale, unknown, and sentinel data
become cannot_confirm and are not passes. Confidence falls for each of
those causes and the notes name them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.config import load_activity_config
from backend.config.safety import load_region_rules
from backend.features.daylight import annotate_daylight
from backend.features.moon import annotate_moon
from backend.features.timeutil import NaiveDateTimeError, to_la, to_utc
from backend.features.units import fahrenheit_to_celsius, meters_to_feet
from backend.models.common import Confidence, GateResult
from backend.models.features import HourlyFeatures, SpotFeatureGrid
from backend.models.scoring import FactorBreakdown, FactorVerdict, ScoredWindow
from backend.scorers.predicates import (
    Decision,
    EvalContext,
    alert_state,
    bloom_decision,
    cite,
    cold_shock_decision,
    dungeness_water_decision,
    ebb_decision,
    failed,
    gear_decision,
    hour_value_records,
    numeric_sentinel,
    passed,
    rip_state,
    season_decision,
    small_craft_decision,
    source_problem,
    unconfirmed,
)
from backend.scorers.rules import COMPUTED_FIELDS, Rule, ScorerConfigError, SIMPLE_FIELDS, validate_activity_config

_FIELD_KIND = {
    "tide_height_ft_mllw": "tide",
    "wind_speed_kt": "wind",
    "wind_gust_kt": "wind",
    "gust_spread_kt": "wind",
    "wind_onshore_component_kt": "wind",
    "wave_height_m": "wave_m",
    "wave_period_s": "generic",
    "sst_c": "temp_c",
    "sst_anomaly_c": "generic",
    "moon_phase": "moon",
    "current_velocity_kt": "velocity",
}
_BOOL_FIELDS = {"is_daylight", "is_slack_water", "is_minus_tide"}


class BaseActivityScorer:
    """Load one activity YAML and score a spot over a UTC time window."""

    activity_name: str

    def __init__(self, config: dict[str, Any] | None = None, region_rules: dict[str, Any] | None = None) -> None:
        loaded = config if config is not None else load_activity_config(self.activity_name)
        self._gates = validate_activity_config(loaded, self.activity_name)
        self.config = loaded
        self.region_rules = region_rules if region_rules is not None else load_region_rules()

    def score_window(
        self,
        grid: SpotFeatureGrid,
        start,
        end,
        *,
        lat: float | None = None,
        lon: float | None = None,
        gear: str | None = None,
        as_of: datetime | None = None,
    ) -> ScoredWindow:
        start_la = to_la(start, "window start")
        end_la = to_la(end, "window end")
        if to_utc(end, "window end") <= to_utc(start, "window start"):
            raise ValueError("window end must be after window start")
        reference = to_la(as_of, "as_of") if as_of is not None else start_la
        try:
            hours = self._hours_in_window(grid, start, end)
        except NaiveDateTimeError as exc:
            return self._blocked(grid, start_la, end_la, f"{exc}")
        if hours:
            hours = annotate_moon(hours)
        if lat is not None and lon is not None and hours:
            margin = int(self.config.get("daylight_margin_minutes", 30))
            hours = annotate_daylight(hours, lat, lon, margin_minutes=margin)
        context = EvalContext(
            hours=hours,
            grid=grid,
            start=start_la,
            end=end_la,
            latitude=lat,
            longitude=lon,
            gear=gear,
            config=self.config,
            region=self.region_rules,
            as_of=reference,
        )
        if not hours:
            gates = [
                self._to_gate(gate, unconfirmed("no hourly features in the window", cite([]), [("hours missing", "missing")]))
                for gate, _rule in self._gates
            ]
        else:
            gates = [self._evaluate(gate, rule, context) for gate, rule in self._gates]
        factors = self._explain(context, gates)
        confidence = self._confidence(context, gates)
        eligible = self._eligible(gates)
        return ScoredWindow(
            spot_id=grid.spot_id,
            start=start_la,
            end=end_la,
            score=self._quality_score(factors),
            confidence=confidence,
            gates=gates,
            factors=factors,
            eligible=eligible,
            summary=self._one_line(factors, gates),
        )

    def _hours_in_window(self, grid: SpotFeatureGrid, start, end) -> list[HourlyFeatures]:
        start_utc = to_utc(start, "window start")
        end_utc = to_utc(end, "window end")
        selected: list[HourlyFeatures] = []
        for hour in grid.hours:
            moment = to_utc(hour.hour, "feature hour")
            if start_utc <= moment < end_utc:
                selected.append(hour)
        return selected

    def _blocked(self, grid: SpotFeatureGrid, start, end, reason: str) -> ScoredWindow:
        gates = [
            GateResult(name=gate["name"], passed=False, cannot_confirm=True, reason=reason, evidence=cite([]))
            for gate, _rule in self._gates
        ]
        confidence = Confidence(value=0.0, notes=[reason])
        return ScoredWindow(
            spot_id=grid.spot_id,
            start=start,
            end=end,
            score=0.0,
            confidence=confidence,
            gates=gates,
            factors=[],
            eligible=False,
            summary=f"Cannot confirm: {reason}",
        )

    def _evaluate(self, gate: dict[str, Any], rule: Rule, ctx: EvalContext) -> GateResult:
        sources = list(gate.get("sources") or [])
        problem = source_problem(ctx, sources)
        decision = self._decide(rule, ctx, str(gate.get("unit") or ""))
        if problem is not None and decision.passed:
            note, key = problem
            decision = unconfirmed(note, decision.evidence, [(note, key)])
        elif problem is not None and not decision.cannot_confirm:
            # A stale or missing source cannot confirm a failure either.
            note, key = problem
            decision = unconfirmed(f"{note}; {decision.reason}", decision.evidence, [(note, key)])
        elif problem is not None and decision.cannot_confirm:
            note, key = problem
            if all(existing != note for existing, _key in decision.causes):
                decision.causes.append((note, key))
        return self._to_gate(gate, decision)

    def _decide(self, rule: Rule, ctx: EvalContext, unit: str) -> Decision:
        if rule.field in COMPUTED_FIELDS:
            return self._computed(rule, ctx)
        if rule.field not in SIMPLE_FIELDS:
            raise ScorerConfigError(f"unknown field {rule.field!r}")
        return self._simple(rule, ctx, unit)

    def _computed(self, rule: Rule, ctx: EvalContext) -> Decision:
        if rule.field == "season_open":
            decision = season_decision(ctx)
        elif rule.field == "gear_allowed":
            decision = gear_decision(ctx)
        elif rule.field == "dungeness_water_legal":
            decision = dungeness_water_decision(ctx)
        elif rule.field == "bloom_clear":
            decision = bloom_decision(ctx)
        elif rule.field == "cold_shock_clear":
            decision = cold_shock_decision(ctx)
        elif rule.field == "small_craft_clear":
            decision = small_craft_decision(ctx)
        elif rule.field == "ebb_against_swell":
            decision = ebb_decision(ctx)
        elif rule.field in {"shellfish_closure", "bacteria_advisory", "thunderstorm_alert"}:
            state = alert_state(ctx, rule.field)
            decision = self._state_rule(rule, state, ctx, rule.field)
        elif rule.field == "rip_current_risk":
            decision = self._state_rule(rule, rip_state(ctx), ctx, "rip_current_risk")
        else:
            raise ScorerConfigError(f"no evaluator for {rule.field!r}")
        return self._apply_op(rule, decision)

    def _apply_op(self, rule: Rule, decision: Decision) -> Decision:
        """Computed predicates already return pass/fail/cannot_confirm for == true / not active.

        The rule operator is checked so a mismatched rule cannot silently pass.
        """

        if decision.cannot_confirm or not decision.passed:
            return decision
        if rule.op == "not_active" or (rule.op == "==" and rule.value is True) or (
            rule.op == "!=" and rule.value in {True, "high", "active"}
        ):
            return decision
        return unconfirmed(
            f"rule {rule.raw!r} did not explicitly pass",
            decision.evidence,
            [("rule did not pass", "unknown")],
        )

    def _state_rule(self, rule: Rule, state: str | None, ctx: EvalContext, name: str) -> Decision:
        alerts = [alert for hour in ctx.hours for alert in hour.active_alerts]
        evidence = cite([{"name": "active_alerts", "value": alert, "unit": ""} for alert in alerts])
        if state is None:
            return unconfirmed(f"{name} is unknown", evidence, [(f"{name} unknown", "unknown")])
        if rule.op == "not_active":
            if state == "active":
                return failed(f"{name} is active", evidence)
            if state == "inactive":
                return passed(f"{name} is not active", evidence)
            return unconfirmed(f"{name} is unknown", evidence, [(f"{name} unknown", "unknown")])
        if rule.op == "!=" and state == rule.value:
            return failed(f"{name} is {state}", evidence)
        if rule.op == "!=" and state != rule.value:
            return passed(f"{name} is {state}", evidence)
        if rule.op == "==" and state == rule.value:
            return passed(f"{name} is {state}", evidence)
        if rule.op == "==" and isinstance(rule.value, bool):
            truth = state in {"active", "high", "true"}
            if truth is rule.value:
                return passed(f"{name} is {state}", evidence)
            return failed(f"{name} is {state}", evidence)
        return unconfirmed(f"{name} is {state}", evidence, [(f"{name} unknown", "unknown")])

    def _simple(self, rule: Rule, ctx: EvalContext, unit: str) -> Decision:
        evidence = cite(hour_value_records(ctx.hours, rule.field, unit))
        if not ctx.hours:
            return unconfirmed("no hourly features in the window", evidence, [("hours missing", "missing")])
        saw_fail = False
        for hour in ctx.hours:
            value = getattr(hour, rule.field)
            if rule.field in _BOOL_FIELDS:
                if value is None:
                    return unconfirmed(
                        f"{rule.field} is missing",
                        evidence,
                        [(f"{rule.field} missing", "missing")],
                    )
                if not isinstance(value, bool):
                    return unconfirmed(
                        f"{rule.field} is unknown",
                        evidence,
                        [(f"{rule.field} unknown", "unknown")],
                    )
                ok = _compare(value, rule.op, rule.value)
                if ok is None:
                    return unconfirmed(
                        f"rule {rule.raw!r} is not a pass",
                        evidence,
                        [("rule unknown", "unknown")],
                    )
                if not ok:
                    saw_fail = True
                continue
            kind = _FIELD_KIND.get(rule.field, "generic")
            problem = numeric_sentinel(kind, value)
            if problem is not None:
                return unconfirmed(
                    f"{rule.field} is {problem}",
                    evidence,
                    [(f"{rule.field} {problem}", problem)],
                )
            ok = _compare(value, rule.op, rule.value)
            if ok is None:
                return unconfirmed(
                    f"rule {rule.raw!r} cannot be evaluated",
                    evidence,
                    [("rule unknown", "unknown")],
                )
            if not ok:
                saw_fail = True
        if saw_fail:
            return failed(f"{rule.raw} failed", evidence)
        return passed(f"{rule.raw} passed", evidence)

    def _explain(self, ctx: EvalContext, gates: list[GateResult]) -> list[FactorBreakdown]:
        """Quality factors plus a blocked/cannot_confirm row for every failed gate."""

        by_name: dict[str, FactorBreakdown] = {}
        ordered: list[FactorBreakdown] = []
        for name, spec in self.config.get("weights", {}).items():
            if not isinstance(spec, dict):
                continue
            weight = float(spec.get("weight", 0))
            if weight == 0:
                continue
            unit_score, raw_value, note, cause = self._factor_score(name, spec, ctx)
            verdict = self._verdict(unit_score, cause)
            observed_at, age = self._timing(ctx, spec, raw_value)
            if spec.get("field") == "moon_phase" and self._any_night(ctx):
                night = "Night window; moon phase is context only."
                note = f"{note} {night}".strip() if note else night
            factor = FactorBreakdown(
                name=str(spec.get("summary_name") or name),
                value=raw_value,
                unit=spec.get("unit"),
                verdict=verdict,
                source=spec.get("source"),
                observed_at=observed_at,
                age_minutes=age,
                weight=weight,
                contribution=weight * unit_score,
                note=note,
            )
            ordered.append(factor)
            by_name[name] = factor
        linked: set[str] = set()
        for gate_cfg, _rule in self._gates:
            gate = next((item for item in gates if item.name == gate_cfg["name"]), None)
            if gate is None or (gate.passed and not gate.cannot_confirm):
                continue
            verdict = FactorVerdict.cannot_confirm if gate.cannot_confirm else FactorVerdict.blocked
            reason = str(gate_cfg.get("blocked_reason") or gate.reason)
            target = gate_cfg.get("factor")
            if isinstance(target, str) and target in by_name:
                current = by_name[target]
                current.verdict = verdict
                current.note = reason
                linked.add(gate_cfg["name"])
                continue
            observed_at, age = self._gate_timing(ctx, gate_cfg)
            sources = list(gate_cfg.get("sources") or [])
            ordered.append(
                FactorBreakdown(
                    name=str(gate_cfg.get("display") or gate_cfg["name"]),
                    value=None,
                    unit=gate_cfg.get("unit") or None,
                    verdict=verdict,
                    source=sources[0] if sources else None,
                    observed_at=observed_at,
                    age_minutes=age,
                    note=reason,
                )
            )
        return ordered

    def _verdict(self, unit_score: float, cause: tuple[str, str] | None) -> FactorVerdict:
        if cause is not None:
            return FactorVerdict.cannot_confirm
        bands = self.config.get("verdict_bands", {})
        good = float(bands.get("good_at_or_above", 0.75))
        fair = float(bands.get("fair_at_or_above", 0.45))
        if unit_score >= good:
            return FactorVerdict.good
        if unit_score >= fair:
            return FactorVerdict.fair
        return FactorVerdict.poor

    def _timing(
        self,
        ctx: EvalContext,
        spec: dict[str, Any],
        raw_value: float | None,
    ) -> tuple[datetime | None, float | None]:
        field_name = spec.get("field")
        if spec.get("source") == "satellite_chl" and ctx.grid.chlorophyll is not None:
            return self._age(ctx, ctx.grid.chlorophyll.observed_at)
        if field_name == "moon_phase" and ctx.hours:
            return self._age(ctx, ctx.hours[len(ctx.hours) // 2].hour)
        if isinstance(field_name, str) and raw_value is not None:
            for hour in ctx.hours:
                value = getattr(hour, field_name, None)
                if isinstance(value, (int, float)) and abs(float(value) - raw_value) < 1e-9:
                    return self._age(ctx, hour.hour)
        if ctx.hours:
            return self._age(ctx, ctx.hours[0].hour)
        return self._age(ctx, ctx.start)

    def _gate_timing(self, ctx: EvalContext, gate_cfg: dict[str, Any]) -> tuple[datetime | None, float | None]:
        sources = list(gate_cfg.get("sources") or [])
        if "satellite_chl" in sources and ctx.grid.chlorophyll is not None:
            return self._age(ctx, ctx.grid.chlorophyll.observed_at)
        if ctx.hours:
            return self._age(ctx, ctx.hours[0].hour)
        return self._age(ctx, ctx.start)

    def _age(self, ctx: EvalContext, moment: datetime) -> tuple[datetime, float]:
        observed = to_la(moment, "observed_at")
        reference = ctx.as_of or ctx.start
        minutes = (to_utc(reference, "as_of") - to_utc(observed, "observed_at")).total_seconds() / 60.0
        return observed, round(minutes, 1)

    def _any_night(self, ctx: EvalContext) -> bool:
        return any(hour.is_daylight is False for hour in ctx.hours)

    def _one_line(self, factors: list[FactorBreakdown], gates: list[GateResult]) -> str:
        parts: list[str] = []
        for factor in factors:
            parts.append(_phrase(factor))
        advisory_names = {
            gate["name"]
            for gate, _rule in self._gates
            if gate.get("advisory") is True
        }
        advisory_gates = [gate for gate in gates if gate.name in advisory_names]
        if advisory_gates and all(gate.passed and not gate.cannot_confirm for gate in advisory_gates):
            parts.append("no advisories")
        if not parts:
            return "Cannot confirm: no factors"
        return ", ".join(parts)

    def _factor_score(
        self,
        name: str,
        spec: dict[str, Any],
        ctx: EvalContext,
    ) -> tuple[float, float | None, str | None, tuple[str, str] | None]:
        curve = spec.get("curve")
        if curve == "hour_fraction":
            target = float(spec.get("target_hours", 1))
            if not ctx.hours or target <= 0:
                return 0.0, None, "no hours to measure window length", ("window_length missing", "missing")
            duration = max(0.0, (ctx.end - ctx.start).total_seconds() / 3600.0)
            return min(1.0, duration / target), round(duration, 2), None, None
        if curve == "slack":
            return self._slack_factor(ctx)
        if curve == "moderate_current":
            return self._moderate_factor(ctx)
        if curve == "spring_tide":
            return self._moon_factor(spec, ctx)
        field_name = spec.get("field")
        if not isinstance(field_name, str):
            return 0.0, None, f"{name} has no field", (f"{name} missing", "missing")
        values = [getattr(hour, field_name) for hour in ctx.hours]
        kind = _FIELD_KIND.get(field_name, "generic")
        usable: list[float] = []
        for value in values:
            if numeric_sentinel(kind, value) is not None:
                return 0.0, None, f"{field_name} is missing or unusable", (f"{field_name} missing", "missing")
            usable.append(float(value))
        if not usable:
            return 0.0, None, f"{field_name} is missing", (f"{field_name} missing", "missing")
        aggregate = spec.get("aggregate", "mean")
        if aggregate == "min":
            raw = min(usable)
        elif aggregate == "max":
            raw = max(usable)
        else:
            raw = sum(usable) / len(usable)
        anchors, scores = self._anchors(spec)
        if anchors is None or scores is None or len(anchors) != len(scores) or len(anchors) < 2:
            raise ScorerConfigError(f"weight {name!r} has a malformed curve")
        sample = raw
        if curve == "piecewise_ft" and field_name == "wave_height_m":
            sample = meters_to_feet(raw)
        elif curve == "piecewise_f" and field_name == "sst_c":
            sample = raw  # anchors were converted to °C below
        unit_score = _piecewise(sample, anchors, scores)
        note = None
        if spec.get("folk_wisdom"):
            note = "Folk wisdom only (DATA_SOURCES.md B3); not a catch-rate rule."
        return unit_score, raw, note, None

    def _anchors(self, spec: dict[str, Any]) -> tuple[list[float] | None, list[float] | None]:
        scores = spec.get("scores")
        if not isinstance(scores, list):
            return None, None
        score_values = [float(item) for item in scores]
        if "anchors" in spec:
            return [float(item) for item in spec["anchors"]], score_values
        if "anchors_ft" in spec:
            return [meters_to_feet_anchor(float(item)) for item in spec["anchors_ft"]], score_values
        if "anchors_f" in spec:
            return [fahrenheit_to_celsius(float(item)) for item in spec["anchors_f"]], score_values
        return None, None

    def _slack_factor(self, ctx: EvalContext) -> tuple[float, float | None, str | None, tuple[str, str] | None]:
        if not ctx.hours:
            return 0.0, None, "slack is missing", ("is_slack_water missing", "missing")
        flags = []
        for hour in ctx.hours:
            if hour.is_slack_water is None and not hour.tide_phase:
                return 0.0, None, "is_slack_water is missing", ("is_slack_water missing", "missing")
            slack = hour.is_slack_water is True or (hour.tide_phase or "").lower() == "slack"
            flags.append(slack)
        score = 1.0 if all(flags) else (0.7 if any(flags) else 0.2)
        return score, None, None, None

    def _moderate_factor(self, ctx: EvalContext) -> tuple[float, float | None, str | None, tuple[str, str] | None]:
        currents = self.config.get("currents", {})
        slack_max = float(currents.get("slack_max_kt", 0.5))
        moderate_max = float(currents.get("moderate_max_kt", 1.5))
        speeds: list[float] = []
        for hour in ctx.hours:
            if hour.current_velocity_kt is None:
                continue
            if numeric_sentinel("velocity", hour.current_velocity_kt) is not None:
                return 0.0, None, "current_velocity_kt is unusable", ("current_velocity_kt sentinel", "sentinel")
            speeds.append(abs(hour.current_velocity_kt))
        if not speeds:
            slack_score, _raw, note, cause = self._slack_factor(ctx)
            if cause is not None:
                return 0.0, None, "current_velocity_kt is missing", ("current_velocity_kt missing", "missing")
            return slack_score, None, note, None
        worst = max(speeds)
        if worst <= slack_max:
            score = 1.0
        elif worst <= moderate_max:
            score = 0.6
        else:
            score = 0.2
        return score, worst, None, None

    def _moon_factor(self, spec: dict[str, Any], ctx: EvalContext) -> tuple[float, float | None, str | None, tuple[str, str] | None]:
        values = []
        for hour in ctx.hours:
            if numeric_sentinel("moon", hour.moon_phase) is not None:
                return 0.0, None, "moon_phase is missing", ("moon_phase missing", "missing")
            values.append(float(hour.moon_phase))  # type: ignore[arg-type]
        if not values:
            return 0.0, None, "moon_phase is missing", ("moon_phase missing", "missing")
        phase = sum(values) / len(values)
        distance = min(abs(phase - 0.0), abs(phase - 0.5), abs(phase - 1.0))
        score = max(0.0, 1.0 - distance / 0.25)
        note = "Folk wisdom only (DATA_SOURCES.md B3); not a catch-rate rule."
        if not spec.get("folk_wisdom"):
            note = None
        return score, phase, note, None

    def _quality_score(self, factors: list[FactorBreakdown]) -> float:
        weights = self.config.get("weights", {})
        total = 0.0
        for spec in weights.values():
            if isinstance(spec, dict):
                total += float(spec.get("weight", 0))
        if total <= 0:
            return 0.0
        points = sum(factor.contribution for factor in factors)
        return max(0.0, min(100.0, 100.0 * points / total))

    def _confidence(self, ctx: EvalContext, gates: list[GateResult]) -> Confidence:
        penalties = self.config.get("confidence_penalties", {})
        notes: list[str] = []
        keys: list[str] = []
        for gate in gates:
            if not gate.cannot_confirm:
                continue
            cause = _cause_from_reason(gate.reason)
            note = gate.reason
            if note not in notes:
                notes.append(note)
                keys.append(cause)
        for source in self.config.get("required_sources", []):
            problem = source_problem(ctx, [source]) if ctx.hours else (f"{source} is missing", "missing")
            if problem is None:
                continue
            note, key = problem
            if note not in notes:
                notes.append(note)
                keys.append(key)
        # Factor gaps (missing quality inputs) also lower confidence.
        for name, spec in self.config.get("weights", {}).items():
            if not isinstance(spec, dict) or float(spec.get("weight", 0)) <= 0:
                continue
            _score, _raw, _note, cause = self._factor_score(name, spec, ctx)
            if cause is None:
                continue
            note, key = cause
            if note not in notes:
                notes.append(note)
                keys.append(key)
        drop = 0.0
        for key in keys:
            drop += float(penalties.get(key, penalties.get("unknown", 0.25)))
        value = max(0.0, min(1.0, 1.0 - drop))
        return Confidence(value=value, notes=notes)

    def _eligible(self, gates: list[GateResult]) -> bool:
        if not gates:
            return False
        return all(gate.passed is True and gate.cannot_confirm is False for gate in gates)

    @staticmethod
    def _to_gate(gate: dict[str, Any], decision: Decision) -> GateResult:
        cannot = decision.cannot_confirm or not decision.passed and decision.cannot_confirm
        # passed is forced off whenever we cannot confirm.
        passed_flag = bool(decision.passed) and not decision.cannot_confirm
        if passed_flag and decision.cannot_confirm:
            passed_flag = False
        return GateResult(
            name=str(gate["name"]),
            passed=passed_flag,
            cannot_confirm=bool(decision.cannot_confirm) or (not passed_flag and decision.cannot_confirm),
            reason=decision.reason,
            evidence=decision.evidence,
        )


def _compare(left: object, op: str, right: object) -> bool | None:
    try:
        if op == "<=":
            return left <= right  # type: ignore[operator]
        if op == ">=":
            return left >= right  # type: ignore[operator]
        if op == "<":
            return left < right  # type: ignore[operator]
        if op == ">":
            return left > right  # type: ignore[operator]
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
    except TypeError:
        return None
    return None


def _piecewise(value: float, anchors: list[float], scores: list[float]) -> float:
    if value <= anchors[0]:
        return scores[0]
    if value >= anchors[-1]:
        return scores[-1]
    for index in range(len(anchors) - 1):
        left, right = anchors[index], anchors[index + 1]
        if left <= value <= right:
            if right == left:
                return scores[index + 1]
            span = (value - left) / (right - left)
            return scores[index] + span * (scores[index + 1] - scores[index])
    return scores[-1]


def meters_to_feet_anchor(feet: float) -> float:
    """Piecewise wave curves compare meters converted to feet."""

    return feet


def _phrase(factor: FactorBreakdown) -> str:
    verdict = factor.verdict.value if factor.verdict is not None else "cannot_confirm"
    blocked = factor.verdict in {FactorVerdict.blocked, FactorVerdict.cannot_confirm}
    if blocked and factor.note and factor.value is None:
        return f"{factor.note} ({verdict})"
    if factor.value is None:
        return f"{factor.note or factor.name} ({verdict})" if blocked and factor.note else f"{factor.name} ({verdict})"
    number = _format_number(factor.value)
    short = factor.unit or ""
    if short == "ft MLLW":
        short = "ft"
    piece = f"{factor.name} {number}"
    if short:
        piece = f"{piece} {short}"
    if blocked and factor.note:
        return f"{piece} ({verdict}: {factor.note})"
    return f"{piece} ({verdict})"


def _format_number(value: float) -> str:
    rounded = round(float(value), 2)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def _cause_from_reason(reason: str) -> str:
    lowered = reason.lower()
    for token in ("stale", "down", "degraded", "sentinel", "missing", "unknown", "unconfirmed"):
        if token in lowered:
            if token == "unconfirmed":
                return "unknown"
            return token
    return "unknown"
