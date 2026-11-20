"""Review1 #1: GateResult + ScoredWindow default-deny + tz-aware."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.models.common import Activity, Confidence, GateResult, SourceStatus
from backend.models.intent import QueryIntent
from backend.models.scoring import ScoredWindow
from backend.models.sources import SourceResult


def test_gate_cannot_confirm_forbids_passed_true():
    with pytest.raises(ValidationError):
        GateResult(name="shellfish", passed=True, cannot_confirm=True, reason="x")


def test_gate_cannot_confirm_with_passed_false_ok():
    g = GateResult(name="shellfish", passed=False, cannot_confirm=True, reason="missing")
    assert g.cannot_confirm is True
    assert g.passed is False


def test_scored_window_eligible_defaults_false():
    w = ScoredWindow(
        spot_id="x",
        start=datetime(2026, 11, 19, 12, tzinfo=timezone.utc),
        end=datetime(2026, 11, 19, 13, tzinfo=timezone.utc),
        score=100,
        confidence=Confidence(value=1.0),
    )
    assert w.eligible is False
    assert w.gates_all_passed is False


def test_scored_window_rejects_naive_datetime():
    with pytest.raises(ValidationError):
        ScoredWindow(
            spot_id="x",
            start=datetime(2026, 11, 19, 12),
            end=datetime(2026, 11, 19, 13),
            score=50,
            confidence=Confidence(value=0.5),
        )


def test_source_result_requires_aware_fetched_at():
    with pytest.raises(ValidationError):
        SourceResult(
            fetched_at=datetime(2026, 11, 19),
            valid_until=datetime(2026, 11, 19),
            status=SourceStatus.ok,
            source_name="x",
        )


def test_intent_rejects_naive_start():
    with pytest.raises(ValidationError):
        QueryIntent(activity=Activity.clamming, start=datetime(2026, 11, 19, 8))
