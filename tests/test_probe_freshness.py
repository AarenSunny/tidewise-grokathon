"""review2 N4/N5/N6: probes judge frozen feeds by observation age; no insecure TLS."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

RUN_ALL = Path(__file__).resolve().parents[1] / "scripts" / "probes" / "run_all.py"


@pytest.fixture(scope="module")
def probes():
    spec = importlib.util.spec_from_file_location("probe_run_all", RUN_ALL)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["probe_run_all"] = mod  # dataclasses resolve annotations via sys.modules
    try:
        spec.loader.exec_module(mod)
        yield mod
    finally:
        sys.modules.pop("probe_run_all", None)


def _result(mod, source: str, age: timedelta):
    r = mod.ProbeResult(source=source, ok=True, http_status=200)
    mod.set_observed(r, datetime.now(UTC) - age, mod.MAX_AGE_HOURS[source])
    return mod.finalize(r)


def test_charm_17_days_is_stale_not_ok(probes):
    r = _result(probes, "erddap_charm_0day", timedelta(days=17))
    assert r.ok is True  # reachable
    assert r.verdict == "STALE"
    assert any("FROZEN/STALE" in d for d in r.discrepancies)


def test_viirs_10_days_is_stale_not_ok(probes):
    # Adapter budget is 10 days; the observed 8-day composite was ~10-11 days old.
    r = _result(probes, "erddap_viirs_chl_8day", timedelta(days=11))
    assert r.verdict == "STALE"


def test_fresh_feed_is_ok(probes):
    r = _result(probes, "erddap_mur_sst", timedelta(hours=30))
    assert r.verdict == "OK"


def test_unknown_age_never_ok(probes):
    r = probes.ProbeResult(source="x", ok=True, http_status=200)
    probes.set_observed(r, None, 3.0)
    probes.finalize(r)
    assert r.verdict == "UNKNOWN_AGE"


def test_unreachable_is_fail(probes):
    r = probes.ProbeResult(source="x", ok=False, http_status=503)
    assert probes.finalize(r).verdict == "FAIL"


def test_prediction_sources_not_age_judged(probes):
    r = probes.ProbeResult(source="coops_predictions_hilo", ok=True, http_status=200)
    probes.set_observed(r, None, probes.MAX_AGE_HOURS["coops_predictions_hilo"])
    assert probes.finalize(r).verdict == "N/A"


def test_erddap_404_503_described_as_transient(probes):
    text = RUN_ALL.read_text()
    assert "transient/intermittent" in text
    assert "treat as feed outage/rename" not in text


def test_no_insecure_tls_in_probe_runner():
    text = RUN_ALL.read_text()
    for banned in ("_create_unverified_context", "verify=False", "insecure=True", "CERT_NONE"):
        assert banned not in text
    assert "import ssl" not in text


def test_budgets_match_adapter_max_age(probes):
    """Probe budgets must equal the adapters' max_age (read-only comparison)."""
    from backend.adapters.charm import CharmAdapter
    from backend.adapters.epa_uv import EpaUvAdapter
    from backend.adapters.erddap import ErddapChlAdapter, ErddapSstAdapter
    from backend.adapters.ndbc import NdbcAdapter

    hours = probes.MAX_AGE_HOURS
    assert hours["erddap_viirs_chl_8day"] == ErddapChlAdapter.max_age.total_seconds() / 3600
    assert hours["erddap_mur_sst"] == ErddapSstAdapter.max_age.total_seconds() / 3600
    assert hours["erddap_charm_0day"] == CharmAdapter.max_age.total_seconds() / 3600
    assert hours["ndbc"] == NdbcAdapter.max_age.total_seconds() / 3600
    assert hours["epa_uv_hourly_94121"] == EpaUvAdapter.max_age.total_seconds() / 3600
