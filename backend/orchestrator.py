"""Orchestrator: adapter fan-out -> grid builder -> activity scorers -> ScoredWindows.

Does not import concrete adapters — only AdapterRegistry — so A/B cloud-agent
adapters plug in when merged. Scorers/features are off-limits; missing scorers
⇒ empty windows + note (no mock data on the live path).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.adapters.registry import AdapterRegistry
from backend.config import load_region
from backend.geo.nearby import select_spots as geo_select_spots
from backend.grid_builder import build_grid
from backend.health import HealthMonitor
from backend.models.api import ClarifyingQuestion, QueryResponse, RecommendResponse
from backend.models.common import Activity, GateResult
from backend.models.scoring import ScoredWindow, SpotRecommendation
from backend.models.sources import SourceResult
from backend.models.spots import RegionConfig, Spot
from backend.optional_feeds import HIDDEN_NOTE, OPTIONAL_CONTEXT_GATES, is_optional_context_source
from backend.redact import redact
from backend.source_aliases import FETCH_SOURCES

logger = logging.getLogger(__name__)

# Default sources for a recommend/query fan-out (registry names; absent → skipped)
DEFAULT_SOURCES = (
    "coops_tides",
    "coops_currents",
    "ndbc_buoy",
    "erddap_chl",
    "erddap_sst",
    "erddap_charm",
    "cdph_shellfish",
    "beachwatch_bacteria",
    "epa_uv",
    "nws_alerts",
    "daylight_sunrise_api",
)


def _dungeness_blocked(spot: Spot) -> bool:
    """SF Bay / San Pablo Bay Dungeness is a hard fail (14 CCR 29.85(b)(1)), enforced here from
    config as defense in depth in case a scorer path bypasses its own water gate."""
    if spot.dungeness_prohibited:
        return True
    try:
        from backend.config.safety import load_region_rules

        rules = load_region_rules()
        region_id = (rules.get("spot_regions") or {}).get(spot.id)
        return region_id in (rules.get("dungeness_prohibited_regions") or [])
    except Exception:  # noqa: BLE001 - unknown config must not become a pass
        return False


def _force_blocked(window: ScoredWindow, reason: str) -> ScoredWindow:
    gate = GateResult(name="dungeness_water", passed=False, cannot_confirm=False, reason=reason)
    gates = [g for g in window.gates if g.name != "dungeness_water"] + [gate]
    return window.model_copy(update={"eligible": False, "gates": gates})


@dataclass
class SpotFetchBundle:
    spot: Spot
    results: dict[str, SourceResult] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


class Orchestrator:
    """Fans out to registered adapters with deadline, concurrency, isolation."""

    def __init__(
        self,
        registry: AdapterRegistry,
        *,
        region: Optional[RegionConfig] = None,
        overall_deadline_s: float = 20.0,
        max_concurrency: int = 8,
        sources: Optional[tuple[str, ...]] = None,
    ) -> None:
        self.registry = registry
        self.region = region or load_region()
        self.overall_deadline_s = overall_deadline_s
        self.max_concurrency = max_concurrency
        self.sources = sources or DEFAULT_SOURCES

    @property
    def health(self) -> HealthMonitor:
        return self.registry.health

    def select_spots(
        self,
        activity: Activity,
        *,
        spot_id: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        limit: int = 6,
    ) -> tuple[list[Spot], dict[str, float], list[str]]:
        """Resolve spots via geo.nearby (activity, no-take, distance)."""
        return geo_select_spots(
            list(self.region.spots),
            activity,
            spot_id=spot_id,
            lat=lat,
            lon=lon,
            limit=limit,
            bbox=self.region.bbox,
        )

    async def fetch_spot_sources(
        self,
        spot: Spot,
        start: datetime,
        end: datetime,
        *,
        sources: Optional[list[str]] = None,
    ) -> SpotFetchBundle:
        """Fetch all requested sources for one spot; isolate failures."""
        names = [n for n in (sources or list(self.sources)) if self.registry.get(n)]
        sem = asyncio.Semaphore(self.max_concurrency)
        bundle = SpotFetchBundle(spot=spot)

        async def _one(name: str) -> None:
            adapter = self.registry.get(name)
            if adapter is None:
                return
            async with sem:
                try:
                    result = await adapter.fetch(spot, start, end)
                    bundle.results[name] = result
                except Exception as exc:  # noqa: BLE001 — never fail the request
                    msg = redact(f"{type(exc).__name__}: {exc}")
                    bundle.errors[name] = msg
                    logger.warning(
                        "orchestrator source isolated fail source=%s spot=%s err=%s",
                        name,
                        spot.id,
                        msg,
                    )

        try:
            await asyncio.wait_for(
                asyncio.gather(*[_one(n) for n in names]),
                timeout=self.overall_deadline_s,
            )
        except asyncio.TimeoutError:
            for n in names:
                if n not in bundle.results and n not in bundle.errors:
                    bundle.errors[n] = "orchestrator_deadline_exceeded"
        return bundle

    def _max_ages(self) -> dict[str, timedelta]:
        return {n: a.max_age for n, a in self.registry.all().items()}

    def score_spot(
        self,
        bundle: SpotFetchBundle,
        activity: Activity,
        start: datetime,
        end: datetime,
        *,
        gear: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> tuple[list[ScoredWindow], list[str]]:
        """adapters -> grid -> real scorers. Missing/stale data is cannot_confirm, never a pass."""
        notes: list[str] = []
        try:
            from backend.scorers.windows import ranked_windows
        except Exception:  # noqa: BLE001 - scorers not importable: no scores, never fake ones
            return [], ["scorers unavailable: windows empty (not scored)"]
        built = build_grid(
            bundle.spot,
            bundle.results,
            bundle.errors,
            start,
            end,
            now=now,
            max_ages=self._max_ages(),
        )
        notes.extend(built.notes)
        try:
            windows = ranked_windows(
                built.grid,
                activity.value,
                start,
                end,
                latitude=bundle.spot.lat,
                longitude=bundle.spot.lon,
                gear=gear,
                tides=built.tides or None,
                currents=built.currents or None,
                as_of=now or datetime.now(timezone.utc),
            )
        except Exception as exc:  # noqa: BLE001 - isolate scorer failures
            logger.warning("scorer failed spot=%s err=%s", bundle.spot.id, redact(type(exc).__name__))
            return [], [f"scorer error ({type(exc).__name__}): windows empty (not scored)"]
        if activity is Activity.crabbing and _dungeness_blocked(bundle.spot):
            reason = "Dungeness take prohibited in SF Bay / San Pablo Bay (14 CCR 29.85(b)(1))"
            windows = [_force_blocked(w, reason) for w in windows]
        return windows[:6], notes

    async def recommend(
        self,
        activity: Activity,
        *,
        spot_id: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 6,
        gear: Optional[str] = None,
    ) -> RecommendResponse:
        now = datetime.now(timezone.utc)
        start = start or now
        end = end or (now + timedelta(hours=48))
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start/end must be timezone-aware UTC")

        spots, distances, selection_notes = self.select_spots(
            activity, spot_id=spot_id, lat=lat, lon=lon, limit=limit
        )
        fetch = tuple(dict.fromkeys((*self.sources, *FETCH_SOURCES))) if self.sources else ()
        # predictions are date-granular: pad so tides/currents cover the whole window
        fetch_start, fetch_end = start - timedelta(hours=12), end + timedelta(hours=12)
        bundles = await asyncio.gather(
            *[
                self.fetch_spot_sources(s, fetch_start, fetch_end, sources=list(fetch) or ["__none__"])
                for s in spots
            ]
        )

        recs: list[SpotRecommendation] = []
        notes: list[str] = []
        scorer = "activity_scorers"
        for b in bundles:
            windows, n = self.score_spot(b, activity, start, end, gear=gear, now=now)
            if n and any("unavailable" in x for x in n):
                scorer = "unavailable"
            notes.extend(f"{b.spot.id}: {x}" for x in n if x not in notes)
            eligible = [w.score for w in windows if w.eligible]
            recs.append(
                SpotRecommendation(
                    spot_id=b.spot.id,
                    spot_name=b.spot.name,
                    windows=windows,
                    best_score=max(eligible) if eligible else None,
                    distance_km=distances.get(b.spot.id),
                )
            )
        degraded = _required_sources_degraded(bundles)
        hidden_optional = self.health.optional_context_hidden()
        note = (
            "Windows are scored from live adapters. best_score is set only for eligible windows; "
            "a gate that cannot be confirmed (missing/stale/unconfirmed data) is not a pass."
        )
        if activity is Activity.crabbing and gear is None:
            note += " Pass gear=hoop_net|snare|loop_trap|hand to confirm the crab gear gate."
        if degraded:
            note += " One or more sources degraded/down; see health."
        if hidden_optional:
            note += " " + HIDDEN_NOTE + "."
        if selection_notes:
            note += " " + " ".join(selection_notes)
        return RecommendResponse(
            activity=activity,
            spot_ids=[s.id for s in spots],
            start=start,
            end=end,
            recommendations=recs,
            health=_user_facing_health(self.health.snapshot()),
            distances_km=distances,
            note=note,
            scorer=scorer,
        )

    async def query(self, text: str) -> QueryResponse:
        """Rule-based intent -> the same scored pipeline. Never invents spots."""
        from backend.bots.intent import parse_intent

        intent, gear = parse_intent(text, list(self.region.spots))
        if intent.clarifying_question or intent.activity is None:
            return QueryResponse(
                intent=intent,
                clarifying=ClarifyingQuestion(
                    question=intent.clarifying_question or "Which activity?",
                    partial_intent=intent,
                ),
                recommendations=[],
                explanation=None,
                health=self.health.snapshot(),
                scorer=None,
            )
        spot_id = intent.spot_ids[0] if intent.spot_ids else None
        try:
            rec = await self.recommend(
                intent.activity, spot_id=spot_id, limit=3, gear=gear
            )
        except ValueError as exc:
            return QueryResponse(
                intent=intent,
                clarifying=None,
                recommendations=[],
                explanation=f"Cannot answer: {exc}",
                health=self.health.snapshot(),
            )
        return QueryResponse(
            intent=intent,
            recommendations=rec.recommendations,
            explanation=explain(rec),
            health=rec.health,
            scorer=rec.scorer,
            note=rec.note,
        )


def _required_sources_degraded(bundles: list[SpotFetchBundle]) -> bool:
    """Optional context feeds that are down do not mark the whole answer degraded."""
    for bundle in bundles:
        if any(not is_optional_context_source(name) for name in bundle.errors):
            return True
        for name, result in bundle.results.items():
            if is_optional_context_source(name):
                continue
            if result.status.value != "ok":
                return True
    return False


def _user_facing_health(adapters: list) -> list:
    """Drop optional context feeds that are not ok. Full detail stays on GET /health."""
    return [
        adapter
        for adapter in adapters
        if not (
            is_optional_context_source(adapter.source_name) and adapter.status.value != "ok"
        )
    ]


def _visible_gate(gate: GateResult) -> bool:
    """Hide an optional context gate that cannot be confirmed. A real fail stays."""
    return not (gate.name in OPTIONAL_CONTEXT_GATES and gate.cannot_confirm)


def explain(rec: RecommendResponse) -> str:
    """Deterministic answer built only from scorer output (no invented numbers)."""
    lines: list[str] = []
    for r in rec.recommendations:
        top = r.windows[0] if r.windows else None
        if top is None:
            lines.append(f"{r.spot_name}: no candidate window in range (cannot confirm).")
            continue
        visible = [g for g in top.gates if _visible_gate(g)]
        pending = [g.name for g in visible if g.cannot_confirm]
        blocked = [g.name for g in visible if not g.passed and not g.cannot_confirm]
        if top.eligible or (not pending and not blocked):
            lines.append(f"{r.spot_name}: {top.label or ''} {top.summary or ''}".strip())
            continue
        why = []
        if blocked:
            why.append("blocked: " + ", ".join(blocked))
        if pending:
            why.append("cannot confirm: " + ", ".join(pending))
        lines.append(
            f"{r.spot_name}: {top.label or 'candidate window'} is NOT recommended ("
            + "; ".join(why)
            + ")."
        )
    return "\n".join(lines) if lines else "No spots matched."
