#!/usr/bin/env python3
"""TideWise build probes — live calls for every DATA_SOURCES.md Part A feed.

Writes:
  scripts/probes/out/*.json  (gitignored raw-ish summaries)
  scripts/probes/REPORT.md   (committed shape + discrepancy report)

Usage:  .venv/bin/python scripts/probes/run_all.py
"""

from __future__ import annotations

import csv
import io
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
REPORT = Path(__file__).resolve().parent / "REPORT.md"
UA = "TideWise/0.1 (build-probes; https://github.com/AarenSunny/tidewise-grokathon)"


@dataclass
class ProbeResult:
    source: str
    ok: bool
    http_status: Optional[int] = None
    latency_ms: Optional[float] = None
    shape: dict[str, Any] = field(default_factory=dict)
    sample: Any = None
    notes: list[str] = field(default_factory=list)
    discrepancies: list[str] = field(default_factory=list)
    error: Optional[str] = None


def _req(
    url: str,
    *,
    timeout: float = 60,
    headers: Optional[dict[str, str]] = None,
    insecure: bool = False,
) -> tuple[int, bytes, float]:
    h = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        h.update(headers)
    ctx = ssl._create_unverified_context() if insecure else None
    req = urllib.request.Request(url, headers=h)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read()
            status = getattr(resp, "status", 200)
        return status, body, (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        ms = (time.perf_counter() - t0) * 1000
        # Re-raise but attach timing via a small wrapper attribute
        e.latency_ms = ms  # type: ignore[attr-defined]
        e.body_bytes = body  # type: ignore[attr-defined]
        raise


def _json_shape(obj: Any, depth: int = 0) -> Any:
    if depth > 4:
        return type(obj).__name__
    if isinstance(obj, dict):
        return {k: _json_shape(v, depth + 1) for k, v in list(obj.items())[:20]}
    if isinstance(obj, list):
        if not obj:
            return []
        return [_json_shape(obj[0], depth + 1), f"... len={len(obj)}"]
    return type(obj).__name__


def probe_coops() -> list[ProbeResult]:
    results: list[ProbeResult] = []
    base = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

    # hi/lo predictions
    url = (
        f"{base}?date=today&station=9414290&product=predictions&datum=MLLW"
        f"&time_zone=lst_ldt&interval=hilo&units=english&format=json"
    )
    r = ProbeResult(source="coops_predictions_hilo", ok=False)
    try:
        status, body, ms = _req(url)
        data = json.loads(body)
        r.http_status, r.latency_ms = status, ms
        r.shape = _json_shape(data)
        preds = data.get("predictions") or []
        r.sample = preds[:2]
        r.ok = status == 200 and bool(preds)
        if preds and set(preds[0].keys()) >= {"t", "v", "type"}:
            r.notes.append("keys t,v,type match DATA_SOURCES sample")
        else:
            r.discrepancies.append(f"unexpected prediction keys: {preds[0].keys() if preds else None}")
        # Check for minus tides today
        vals = [float(p["v"]) for p in preds if p.get("type") == "L"]
        if vals:
            r.notes.append(f"today low tides ft MLLW: {vals}")
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)

    # latest water level
    url = (
        f"{base}?date=latest&station=9414290&product=water_level&datum=MLLW"
        f"&time_zone=lst_ldt&units=english&format=json"
    )
    r = ProbeResult(source="coops_water_level_latest", ok=False)
    try:
        status, body, ms = _req(url)
        data = json.loads(body)
        r.http_status, r.latency_ms = status, ms
        r.shape = _json_shape(data)
        r.sample = (data.get("data") or [])[:1]
        r.ok = status == 200 and "data" in data
        if "error" in data:
            r.discrepancies.append(f"error payload: {data['error']}")
            r.ok = False
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)

    # currents predictions
    url = (
        f"{base}?date=today&station=SFB1201&product=currents_predictions"
        f"&time_zone=lst_ldt&units=english&format=json&interval=MAX_SLACK"
    )
    r = ProbeResult(source="coops_currents_SFB1201", ok=False)
    try:
        status, body, ms = _req(url)
        data = json.loads(body)
        r.http_status, r.latency_ms = status, ms
        r.shape = _json_shape(data)
        # CO-OPS nests differently — capture actual keys
        r.sample = data if isinstance(data, dict) else str(data)[:400]
        r.ok = status == 200 and "error" not in data
        if "error" in data:
            r.discrepancies.append(f"currents error: {data['error']}")
            r.ok = False
        else:
            r.notes.append(f"top-level keys: {list(data.keys())}")
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)

    # water_temperature expected fail at 9414290
    url = (
        f"{base}?date=latest&station=9414290&product=water_temperature"
        f"&time_zone=lst_ldt&units=english&format=json"
    )
    r = ProbeResult(source="coops_water_temp_9414290_expect_nodata", ok=False)
    try:
        status, body, ms = _req(url)
        data = json.loads(body)
        r.http_status, r.latency_ms = status, ms
        r.shape = _json_shape(data)
        r.sample = data
        if "error" in data:
            r.ok = True  # confirming known quirk
            r.notes.append("Confirmed: no water_temperature at 9414290 (matches DATA_SOURCES)")
        else:
            r.ok = True
            r.discrepancies.append("DATA_SOURCES said no WTMP at 9414290 but data returned")
            r.notes.append(str(data)[:200])
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)
    return results


def probe_ndbc() -> list[ProbeResult]:
    results: list[ProbeResult] = []
    base = "https://www.ndbc.noaa.gov/data/realtime2"
    for sid in ("46026", "46012", "46237", "46239"):
        r = ProbeResult(source=f"ndbc_{sid}", ok=False)
        try:
            status, body, ms = _req(f"{base}/{sid}.txt", timeout=30)
            text = body.decode("utf-8", errors="replace")
            lines = text.strip().splitlines()
            r.http_status, r.latency_ms = status, ms
            r.shape = {
                "format": "space_separated_txt",
                "header_lines": lines[:2],
                "n_data_rows": max(0, len(lines) - 2),
            }
            data_rows = [ln for ln in lines if ln and not ln.startswith("#")]
            r.sample = data_rows[:1]
            r.ok = status == 200 and bool(data_rows)
            if data_rows:
                # parse first row datetime
                parts = data_rows[0].split()
                if len(parts) >= 5:
                    stamp = f"{parts[0]}-{parts[1]}-{parts[2]} {parts[3]}:{parts[4]}Z"
                    r.notes.append(f"latest_row_stamp={stamp}")
                    # staleness check for known-stale 46239
                    if sid == "46239":
                        # year month day
                        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                        now = datetime.now(timezone.utc)
                        age_days = (now - datetime(y, m, d, tzinfo=timezone.utc)).days
                        if age_days > 3:
                            r.notes.append(f"STALE confirmed age_days={age_days} (DATA_SOURCES warned)")
                        else:
                            r.discrepancies.append(
                                f"46239 not stale today (age_days={age_days}); DATA_SOURCES said Oct/early Nov"
                            )
                if "MM" in data_rows[0]:
                    r.notes.append("MM sentinel present in row")
                # WTMP column index 14 in standard met (0-based after YY MM DD hh mm ...)
                # Columns: YY MM DD hh mm WDIR WSPD GST WVHT DPD APD MWD PRES ATMP WTMP ...
                if len(parts) > 14:
                    wtmp = parts[14]
                    r.notes.append(f"WTMP={wtmp}")
                    if wtmp not in ("MM",) and wtmp.replace(".", "", 1).isdigit():
                        t = float(wtmp)
                        if not (-2 <= t <= 40):
                            r.discrepancies.append(f"WTMP out of plausible range: {t}")
        except Exception as e:  # noqa: BLE001
            r.error = f"{type(e).__name__}: {e}"
        results.append(r)

    # spectral
    r = ProbeResult(source="ndbc_46026_spec", ok=False)
    try:
        status, body, ms = _req(f"{base}/46026.spec", timeout=30)
        lines = body.decode("utf-8", errors="replace").strip().splitlines()
        r.http_status, r.latency_ms = status, ms
        r.shape = {"header": lines[:2], "n_rows": max(0, len(lines) - 2)}
        r.sample = [ln for ln in lines if not ln.startswith("#")][:1]
        r.ok = status == 200 and len(lines) > 2
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)
    return results


def probe_nws() -> list[ProbeResult]:
    results: list[ProbeResult] = []
    headers = {"User-Agent": UA, "Accept": "application/geo+json"}

    r = ProbeResult(source="nws_points_sf", ok=False)
    try:
        status, body, ms = _req(
            "https://api.weather.gov/points/37.8063,-122.4659", headers=headers
        )
        data = json.loads(body)
        props = data.get("properties", {})
        r.http_status, r.latency_ms = status, ms
        r.shape = {"properties_keys": sorted(props.keys())[:25]}
        r.sample = {
            "gridId": props.get("gridId"),
            "gridX": props.get("gridX"),
            "gridY": props.get("gridY"),
            "forecastZone": props.get("forecastZone"),
        }
        r.ok = status == 200 and props.get("gridId") == "MTR"
        expected = (83, 107)
        got = (props.get("gridX"), props.get("gridY"))
        if got != expected:
            r.discrepancies.append(
                f"SF grid XY {got} != DATA_SOURCES {expected} (grids can shift; note for adapters)"
            )
        else:
            r.notes.append("grid MTR/83,107 matches DATA_SOURCES")
        zone = props.get("forecastZone") or ""
        if "PZZ530" not in zone:
            r.discrepancies.append(f"forecastZone {zone} does not contain PZZ530")
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)

    r = ProbeResult(source="nws_alerts_CA", ok=False)
    try:
        status, body, ms = _req(
            "https://api.weather.gov/alerts/active?area=CA", headers=headers, timeout=45
        )
        data = json.loads(body)
        feats = data.get("features", [])
        events: dict[str, int] = {}
        for f in feats:
            ev = f.get("properties", {}).get("event", "?")
            events[ev] = events.get(ev, 0) + 1
        r.http_status, r.latency_ms = status, ms
        r.shape = {"type": data.get("type"), "n_features": len(feats)}
        r.sample = sorted(events.items(), key=lambda x: -x[1])[:10]
        r.ok = status == 200
        r.notes.append(f"alert_count={len(feats)} (DATA_SOURCES had 38 earlier today)")
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)

    r = ProbeResult(source="nws_zone_PZZ545", ok=False)
    try:
        status, body, ms = _req(
            "https://api.weather.gov/zones/forecast/PZZ545/forecast", headers=headers
        )
        data = json.loads(body)
        periods = data.get("properties", {}).get("periods", [])
        r.http_status, r.latency_ms = status, ms
        r.shape = {"n_periods": len(periods), "period0_keys": list(periods[0].keys()) if periods else []}
        r.sample = {
            "name": periods[0].get("name") if periods else None,
            "detailedForecast": (periods[0].get("detailedForecast") or "")[:240] if periods else None,
        }
        r.ok = status == 200 and bool(periods)
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)

    r = ProbeResult(source="nws_srf_MTR", ok=False)
    try:
        status, body, ms = _req(
            "https://api.weather.gov/products/types/SRF/locations/MTR", headers=headers
        )
        data = json.loads(body)
        graph = data.get("@graph") or data.get("graph") or []
        r.http_status, r.latency_ms = status, ms
        r.shape = {"keys": list(data.keys()), "n_products": len(graph)}
        r.sample = {
            "latest_id": graph[0].get("id") if graph else None,
            "issuanceTime": graph[0].get("issuanceTime") if graph else None,
            "productName": graph[0].get("productName") if graph else None,
        }
        r.ok = status == 200 and bool(graph)
        if graph and graph[0].get("productName") not in (None, "Surf Forecast", "Surf Zone Forecast"):
            r.notes.append(f"productName={graph[0].get('productName')}")
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)
    return results


def probe_erddap() -> list[ProbeResult]:
    results: list[ProbeResult] = []
    base = "https://coastwatch.pfeg.noaa.gov/erddap/griddap"

    def erddap(name: str, path_q: str, expect_col: str) -> ProbeResult:
        r = ProbeResult(source=name, ok=False)
        url = f"{base}/{path_q}"
        try:
            status, body, ms = _req(url, timeout=90)
            data = json.loads(body)
            table = data.get("table", {})
            cols = table.get("columnNames", [])
            rows = table.get("rows", [])
            r.http_status, r.latency_ms = status, ms
            r.shape = {"columnNames": cols, "n_rows": len(rows)}
            r.sample = rows[:3]
            r.ok = status == 200 and expect_col in cols
            if rows:
                # time usually col 0
                r.notes.append(f"time_sample={rows[0][0] if rows[0] else None}")
            nulls = sum(1 for row in rows if expect_col in cols and row[cols.index(expect_col)] is None)
            if nulls:
                r.notes.append(f"null_{expect_col}_count={nulls}/{len(rows)} (coast/land fill)")
        except urllib.error.HTTPError as e:
            r.http_status = e.code
            r.latency_ms = getattr(e, "latency_ms", None)
            body = getattr(e, "body_bytes", b"")[:300].decode("utf-8", "replace")
            r.error = f"HTTPError: {e.code}"
            r.sample = body
            if e.code in (404, 503):
                r.discrepancies.append(
                    f"CoastWatch ERDDAP returned {e.code} for dataset path — "
                    "DATA_SOURCES verified this ID earlier today; treat as feed outage/rename"
                )
            return r
        except Exception as e:  # noqa: BLE001
            r.error = f"{type(e).__name__}: {e}"
        return r


    q = urllib.parse.quote
    results.append(
        erddap(
            "erddap_mur_sst",
            "jplMURSST41.json?"
            + q("analysed_sst[(last)][(37.5):1:(37.55)][(-122.55):1:(-122.5)]", safe="[](),:"),
            "analysed_sst",
        )
    )
    results.append(
        erddap(
            "erddap_viirs_chl_8day",
            "erdVHNchla8day.json?"
            + q("chla[(last)][(0.0)][(37.5):1:(37.55)][(-122.55):1:(-122.5)]", safe="[](),:"),
            "chla",
        )
    )
    results.append(
        erddap(
            "erddap_charm_0day",
            "wvcharmV3_0day.json?"
            + q(
                "pseudo_nitzschia[(last)][(37.4):1:(37.6)][(237.3):1:(237.5)]",
                safe="[](),:",
            ),
            "pseudo_nitzschia",
        )
    )
    results.append(
        erddap(
            "erddap_mur_anom",
            "jplMURSST41anom1day.json?"
            + q("sstAnom[(last)][(37.5):1:(37.52)][(-122.55):1:(-122.52)]", safe="[](),:"),
            "sstAnom",
        )
    )
    return results


def probe_cdph_arcgis() -> list[ProbeResult]:
    results: list[ProbeResult] = []
    # Prefer ArcGIS (stable) over HTML
    url = (
        "https://services2.arcgis.com/wi1yEacfYjH5viqb/arcgis/rest/services/"
        "All_Bivalve_Shellfish_Health_Advisory_Special_Advisory/FeatureServer/3/query"
        "?where=1%3D1&outFields=TITLE,DESCRIPTION,DATE,VISIBLE&returnGeometry=false&f=json"
    )
    r = ProbeResult(source="cdph_arcgis_special_advisory", ok=False)
    try:
        status, body, ms = _req(url, timeout=45)
        data = json.loads(body)
        feats = data.get("features", [])
        r.http_status, r.latency_ms = status, ms
        r.shape = {"n_features": len(feats), "attr_keys": list(feats[0]["attributes"].keys()) if feats else []}
        r.sample = [
            {
                "TITLE": f["attributes"].get("TITLE"),
                "VISIBLE": f["attributes"].get("VISIBLE"),
            }
            for f in feats[:5]
        ]
        r.ok = status == 200 and "features" in data
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)

    url2 = (
        "https://services2.arcgis.com/wi1yEacfYjH5viqb/arcgis/rest/services/"
        "Health_Advisory_Symbols_(Red)/FeatureServer/0/query"
        "?where=1%3D1&outFields=County_Name,Latitude,Longitude&returnGeometry=false&f=json"
    )
    r = ProbeResult(source="cdph_arcgis_county_symbols", ok=False)
    try:
        status, body, ms = _req(url2, timeout=45)
        data = json.loads(body)
        feats = data.get("features", [])
        counties = [f["attributes"].get("County_Name") for f in feats]
        r.http_status, r.latency_ms = status, ms
        r.shape = {"n_features": len(feats)}
        r.sample = counties[:10]
        r.ok = status == 200
        for need in ("San Francisco County", "San Mateo County", "Marin County"):
            if need not in counties:
                r.discrepancies.append(f"missing county symbol: {need}")
            else:
                r.notes.append(f"has {need}")
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)

    # TLS check on cdph.ca.gov (document only)
    r = ProbeResult(source="cdph_html_tls_check", ok=False)
    try:
        status, body, ms = _req(
            "https://www.cdph.ca.gov/Programs/OPA/Pages/Shellfish-Advisories.aspx",
            timeout=45,
        )
        r.http_status, r.latency_ms = status, ms
        r.ok = status == 200
        r.notes.append("strict TLS succeeded in this environment")
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
        r.notes.append("strict TLS failed — matches DATA_SOURCES quirk; try insecure for probe only")
        try:
            status, body, ms = _req(
                "https://www.cdph.ca.gov/Programs/OPA/Pages/Shellfish-Advisories.aspx",
                timeout=45,
                insecure=True,
            )
            r.http_status, r.latency_ms = status, ms
            r.ok = status == 200
            r.discrepancies.append("CDPH TLS requires insecure context here (probe-only)")
        except Exception as e2:  # noqa: BLE001
            r.error = f"strict+insecure failed: {e} / {e2}"
    results.append(r)
    return results


def probe_beachwatch() -> list[ProbeResult]:
    results: list[ProbeResult] = []
    rid = "7bd961cf-abe4-433b-8033-378161237ff3"
    url = (
        "https://data.ca.gov/api/3/action/datastore_search"
        f"?resource_id={rid}&limit=3&q=San%20Mateo"
    )
    r = ProbeResult(source="beachwatch_bacteria_datastore", ok=False)
    try:
        status, body, ms = _req(url, timeout=45)
        data = json.loads(body)
        result = data.get("result", {})
        records = result.get("records", [])
        r.http_status, r.latency_ms = status, ms
        r.shape = {
            "success": data.get("success"),
            "record_keys": list(records[0].keys()) if records else [],
            "total": result.get("total"),
        }
        r.sample = records[:2]
        r.ok = status == 200 and data.get("success") is True
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)

    rid2 = "d5cd6a23-829c-426d-a63e-689a55a3db9c"
    url = f"https://data.ca.gov/api/3/action/datastore_search?resource_id={rid2}&limit=2&q=San%20Mateo"
    r = ProbeResult(source="beachwatch_advisories_datastore", ok=False)
    try:
        status, body, ms = _req(url, timeout=45)
        data = json.loads(body)
        records = data.get("result", {}).get("records", [])
        r.http_status, r.latency_ms = status, ms
        r.shape = {"record_keys": list(records[0].keys()) if records else [], "n": len(records)}
        r.sample = records[:1]
        r.ok = status == 200 and data.get("success") is True
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)
    return results


def probe_firms_eonet() -> list[ProbeResult]:
    results: list[ProbeResult] = []
    r = ProbeResult(source="firms_modis_usa_24h_csv", ok=False)
    try:
        status, body, ms = _req(
            "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/"
            "MODIS_C6_1_USA_contiguous_and_Hawaii_24h.csv",
            timeout=60,
        )
        text = body.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        # filter bbox
        local = []
        for row in rows:
            try:
                lat, lon = float(row["latitude"]), float(row["longitude"])
            except (KeyError, ValueError):
                continue
            if 37.0 <= lat <= 38.5 and -123.5 <= lon <= -121.5:
                local.append(row)
        r.http_status, r.latency_ms = status, ms
        r.shape = {"n_usa": len(rows), "n_bbox": len(local), "fields": reader.fieldnames}
        r.sample = local[:3] or rows[:1]
        r.ok = status == 200 and len(rows) > 0
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)

    r = ProbeResult(source="eonet_wildfires_bbox", ok=False)
    try:
        status, body, ms = _req(
            "https://eonet.gsfc.nasa.gov/api/v3/events?category=wildfires&status=open"
            "&limit=20&bbox=-123.5,37.0,-121.5,38.5",
            timeout=30,
        )
        data = json.loads(body)
        events = data.get("events", [])
        r.http_status, r.latency_ms = status, ms
        r.shape = {"n_events": len(events)}
        r.sample = [{"id": e.get("id"), "title": e.get("title")} for e in events[:5]]
        r.ok = status == 200
        r.notes.append("EONET open events may be stale — use FIRMS for heat (per DATA_SOURCES)")
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)
    return results


def probe_uv() -> list[ProbeResult]:
    results: list[ProbeResult] = []
    # EPA UV hourly
    r = ProbeResult(source="epa_uv_hourly_94121", ok=False)
    try:
        status, body, ms = _req(
            "https://data.epa.gov/efservice/getEnvirofactsUVHOURLY/ZIP/94121/JSON",
            timeout=45,
        )
        data = json.loads(body)
        r.http_status, r.latency_ms = status, ms
        r.shape = {"type": type(data).__name__, "n": len(data) if isinstance(data, list) else None}
        r.sample = data[:2] if isinstance(data, list) else data
        r.ok = status == 200 and isinstance(data, list) and bool(data)
        if isinstance(data, list) and data:
            keys = set(data[0].keys())
            if not {"ZIP", "UV_VALUE"} <= keys:
                r.discrepancies.append(f"unexpected EPA UV keys: {keys}")
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)

    # POWER — confirm UV fill
    r = ProbeResult(source="nasa_power_daily_sf", ok=False)
    try:
        url = (
            "https://power.larc.nasa.gov/api/temporal/daily/point"
            "?parameters=ALLSKY_SFC_SW_DWN,ALLSKY_SFC_UV_INDEX,T2M"
            "&community=RE&longitude=-122.47&latitude=37.81"
            "&start=20261101&end=20261118&format=JSON"
        )
        status, body, ms = _req(url, timeout=60)
        data = json.loads(body)
        props = data.get("properties", {}).get("parameter", {})
        r.http_status, r.latency_ms = status, ms
        r.shape = {"parameters": list(props.keys())}
        uv = props.get("ALLSKY_SFC_UV_INDEX") or {}
        sw = props.get("ALLSKY_SFC_SW_DWN") or {}
        r.sample = {
            "UV_INDEX_tail": dict(list(uv.items())[-5:]),
            "SW_DWN_tail": dict(list(sw.items())[-5:]),
        }
        r.ok = status == 200
        if uv and all(v == -999 for v in uv.values()):
            r.notes.append("ALLSKY_SFC_UV_INDEX all -999 — confirms DATA_SOURCES; use EPA UV")
        elif uv:
            nonzero = sum(1 for v in uv.values() if v != -999)
            r.discrepancies.append(f"UV_INDEX has {nonzero} non-fill values (DATA_SOURCES said all fill)")
    except Exception as e:  # noqa: BLE001
        r.error = f"{type(e).__name__}: {e}"
    results.append(r)
    return results


def write_report(all_results: list[ProbeResult]) -> None:
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    lines = [
        "# TideWise build probe report (Phase 2)",
        "",
        f"Ran: **{now}**",
        f"UA: `{UA}`",
        "",
        "Live probes against every Part A source in `DATA_SOURCES.md`. "
        "Raw summaries also under `scripts/probes/out/` (gitignored).",
        "",
        "## Summary",
        "",
        "| Source | OK | HTTP | Latency ms | Notes / discrepancies |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in all_results:
        note = "; ".join(r.notes + r.discrepancies)
        if r.error:
            note = f"ERROR: {r.error}" + (f"; {note}" if note else "")
        lines.append(
            f"| `{r.source}` | {'yes' if r.ok else 'no'} | {r.http_status} | "
            f"{(f'{r.latency_ms:.0f}' if r.latency_ms is not None else '-')} | {note[:180]} |"
        )

    lines += ["", "## Response shapes (abbreviated)", ""]
    for r in all_results:
        lines.append(f"### `{r.source}`")
        lines.append("```json")
        lines.append(
            json.dumps(
                {
                    "ok": r.ok,
                    "http_status": r.http_status,
                    "shape": r.shape,
                    "sample": r.sample,
                    "notes": r.notes,
                    "discrepancies": r.discrepancies,
                    "error": r.error,
                },
                indent=2,
                default=str,
            )[:4000]
        )
        lines.append("```")
        lines.append("")

    disc = [r for r in all_results if r.discrepancies]
    lines += ["## Discrepancies vs DATA_SOURCES.md", ""]
    if not disc:
        lines.append("No structural discrepancies beyond expected live variability (alert counts, grid XY, timestamps).")
    else:
        for r in disc:
            for d in r.discrepancies:
                lines.append(f"- **{r.source}:** {d}")
    lines.append("")
    lines.append("## Adapter implications (for Phase 3)")
    lines.append("")
    lines.append("- CO-OPS: parse `predictions[]` / `data[]`; treat `error.message` as down/no-product.")
    lines.append("- NDBC: reject `MM`; check row timestamp for stale CDIP IDs; WTMP/WVHT metric.")
    lines.append("- NWS: require User-Agent; resolve points→grid each time (XY may shift).")
    lines.append("- ERDDAP: tiny bboxes; C-HARM lon 0–360; treat null fills; check `time` freshness.")
    lines.append("- Shellfish: ArcGIS FeatureServer primary; CDPH HTML TLS may need careful CA handling.")
    lines.append("- UV: EPA hourly ZIP; do not use POWER UV_INDEX (fill).")
    lines.append("- Fires: FIRMS CSV + bbox filter; EONET narrative only.")
    lines.append("")
    REPORT.write_text("\n".join(lines))
    print(f"Wrote {REPORT}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    batches = [
        ("coops", probe_coops),
        ("ndbc", probe_ndbc),
        ("nws", probe_nws),
        ("erddap", probe_erddap),
        ("cdph", probe_cdph_arcgis),
        ("beachwatch", probe_beachwatch),
        ("firms_eonet", probe_firms_eonet),
        ("uv", probe_uv),
    ]
    all_results: list[ProbeResult] = []
    for name, fn in batches:
        print(f"== probing {name} ==")
        try:
            batch = fn()
        except Exception as e:  # noqa: BLE001
            print(f"BATCH FAIL {name}: {e}", file=sys.stderr)
            batch = [ProbeResult(source=name, ok=False, error=str(e))]
        all_results.extend(batch)
        (OUT / f"{name}.json").write_text(
            json.dumps([asdict(r) for r in batch], indent=2, default=str)
        )
        for r in batch:
            flag = "OK" if r.ok else "FAIL"
            print(f"  [{flag}] {r.source} http={r.http_status} {r.error or ''}")

    write_report(all_results)
    failed = [r for r in all_results if not r.ok]
    print(f"Done: {len(all_results) - len(failed)}/{len(all_results)} ok")
    return 1 if len(failed) > len(all_results) // 2 else 0


if __name__ == "__main__":
    raise SystemExit(main())
