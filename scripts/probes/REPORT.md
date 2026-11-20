# TideWise build probe report (Phase 2)

Ran: **2026-11-19 16:00 PST** (point-in-time snapshot; feeds flap and age, re-run before relying on it)
UA: `TideWise/0.1 (build-probes; https://github.com/AarenSunny/tidewise-grokathon)`

Live probes against every Part A source in `DATA_SOURCES.md`. Raw summaries also under `scripts/probes/out/` (gitignored).

## Summary

Verdict is **OK only if reachable AND parsed AND fresh** (observation age within the adapter's `max_age`). HTTP 200 alone is never OK: frozen feeds show **STALE**. TLS verification is always strict.

| Source | Verdict | HTTP | Latency ms | Obs age h / budget h | Notes / discrepancies |
| --- | --- | --- | --- | --- | --- |
| `coops_predictions_hilo` | N/A | 200 | 374 | - | keys t,v,type match DATA_SOURCES sample; today low tides ft MLLW: [1.018, 1.674] |
| `coops_water_level_latest` | OK | 200 | 466 | 0.1 / 0.5 |  |
| `coops_currents_SFB1201` | N/A | 200 | 337 | - | top-level keys: ['current_predictions'] |
| `coops_water_temp_9414290_expect_nodata` | N/A | 200 | 371 | - | Confirmed: no water_temperature at 9414290 (matches DATA_SOURCES) |
| `ndbc_46026` | OK | 200 | 348 | 0.5 / 3.0 | latest_row_stamp=2026-11-19 23:30Z; MM sentinel present in row; WTMP=18.8 |
| `ndbc_46012` | OK | 200 | 83 | 1.0 / 3.0 | latest_row_stamp=2026-11-19 23:00Z; MM sentinel present in row; WTMP=18.9 |
| `ndbc_46237` | OK | 200 | 74 | 1.0 / 3.0 | latest_row_stamp=2026-11-19 23:00Z; MM sentinel present in row; WTMP=17.1 |
| `ndbc_46239` | STALE | 200 | 89 | 621.0 / 3.0 | latest_row_stamp=2026-10-25 03:00Z; STALE confirmed age_days=25 (DATA_SOURCES warned); MM sentinel present in row; WTMP=20.2; FROZEN/STALE: observation age 621.0 h > budget 3.0 h ( |
| `ndbc_46026_spec` | N/A | 200 | 62 | - |  |
| `nws_points_sf` | N/A | 200 | 72 | - | grid MTR/83,107 matches DATA_SOURCES |
| `nws_alerts_CA` | N/A | 200 | 179 | - | alert_count=34 (DATA_SOURCES had 38 earlier today) |
| `nws_zone_PZZ545` | N/A | 200 | 126 | - |  |
| `nws_srf_MTR` | N/A | 200 | 193 | - |  |
| `erddap_mur_sst` | OK | 200 | 723 | 39.0 / 72.0 | time_sample=2026-11-18T09:00:00Z; null_analysed_sst_count=11/36 (coast/land fill) |
| `erddap_viirs_chl_8day` | STALE | 200 | 871 | 264.0 / 240.0 | time_sample=2026-11-09T00:00:00Z; null_chla_count=22/49 (coast/land fill); FROZEN/STALE: observation age 264.0 h > budget 240.0 h (HTTP 200 does not mean usable) |
| `erddap_charm_0day` | STALE | 200 | 623 | 420.0 / 72.0 | time_sample=2026-11-02T12:00:00Z; null_pseudo_nitzschia_count=4/64 (coast/land fill); FROZEN/STALE: observation age 420.0 h > budget 72.0 h (HTTP 200 does not mean usable) |
| `erddap_mur_anom` | FAIL | 503 | 1581 | - | ERROR: HTTPError: 503; CoastWatch ERDDAP returned 503 — transient/intermittent availability (flapping observed); retry with backoff, then serve last-good with age |
| `cdph_arcgis_special_advisory` | N/A | 200 | 127 | - |  |
| `cdph_arcgis_county_symbols` | N/A | 200 | 120 | - | has San Francisco County; has San Mateo County; has Marin County |
| `cdph_html_tls_check` | FAIL | None | - | - | ERROR: URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1029)>; strict TLS verification FAILED (s |
| `beachwatch_bacteria_datastore` | N/A | 200 | 29386 | - |  |
| `beachwatch_advisories_datastore` | N/A | 200 | 1431 | - |  |
| `firms_modis_usa_24h_csv` | N/A | 200 | 511 | - |  |
| `eonet_wildfires_bbox` | N/A | 200 | 3530 | - | EONET open events may be stale — use FIRMS for heat (per DATA_SOURCES) |
| `epa_uv_hourly_94121` | OK | 200 | 947 | 1.0 / 6.0 |  |
| `nasa_power_daily_sf` | N/A | 200 | 160 | - | ALLSKY_SFC_UV_INDEX all -999 — confirms DATA_SOURCES; use EPA UV |

## Response shapes (abbreviated)

### `coops_predictions_hilo`
```json
{
  "ok": true,
  "verdict": "N/A",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": 200,
  "shape": {
    "predictions": [
      {
        "t": "str",
        "v": "str",
        "type": "str"
      },
      "... len=4"
    ]
  },
  "sample": [
    {
      "t": "2026-11-19 00:12",
      "v": "1.018",
      "type": "L"
    },
    {
      "t": "2026-11-19 07:15",
      "v": "5.269",
      "type": "H"
    }
  ],
  "notes": [
    "keys t,v,type match DATA_SOURCES sample",
    "today low tides ft MLLW: [1.018, 1.674]"
  ],
  "discrepancies": [],
  "error": null
}
```

### `coops_water_level_latest`
```json
{
  "ok": true,
  "verdict": "OK",
  "observed_at": "2026-11-19T23:54:00+00:00",
  "age_hours": 0.1,
  "max_age_hours": 0.5,
  "http_status": 200,
  "shape": {
    "metadata": {
      "id": "str",
      "name": "str",
      "lat": "str",
      "lon": "str"
    },
    "data": [
      {
        "t": "str",
        "v": "str",
        "s": "str",
        "f": "str",
        "q": "str"
      },
      "... len=1"
    ]
  },
  "sample": [
    {
      "t": "2026-11-19 23:54",
      "v": "3.843",
      "s": "0.348",
      "f": "0,0,0,0",
      "q": "p"
    }
  ],
  "notes": [],
  "discrepancies": [],
  "error": null
}
```

### `coops_currents_SFB1201`
```json
{
  "ok": true,
  "verdict": "N/A",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": 200,
  "shape": {
    "current_predictions": {
      "units": "str",
      "cp": [
        {
          "Type": "str",
          "meanFloodDir": "int",
          "Bin": "str",
          "meanEbbDir": "int",
          "Time": "str",
          "Depth": "str",
          "Velocity_Major": "int"
        },
        "... len=8"
      ]
    }
  },
  "sample": {
    "current_predictions": {
      "units": "feet, knots",
      "cp": [
        {
          "Type": "slack",
          "meanFloodDir": 61,
          "Bin": "26",
          "meanEbbDir": 239,
          "Time": "2026-11-19 02:34",
          "Depth": "19",
          "Velocity_Major": 0
        },
        {
          "Type": "flood",
          "meanFloodDir": 61,
          "Bin": "26",
          "meanEbbDir": 239,
          "Time": "2026-11-19 05:29",
          "Depth": "19",
          "Velocity_Major": 2.16
        },
        {
          "Type": "slack",
          "meanFloodDir": 61,
          "Bin": "26",
          "meanEbbDir": 239,
          "Time": "2026-11-19 08:26",
          "Depth": "19",
          "Velocity_Major": 0
        },
        {
          "Type": "ebb",
          "meanFloodDir": 61,
          "Bin": "26",
          "meanEbbDir": 239,
          "Time": "2026-11-19 11:50",
          "Depth": "19",
          "Velocity_Major": -2.64
        },
        {
          "Type": "slack",
          "meanFloodDir": 61,
          "Bin": "26",
          "meanEbbDir": 239,
          "Time": "2026-11-19 16:06",
          "Depth": "19",
          "Velocity_Major": 0
        },
        {
          "Type": "flood",
          "meanFloodDir": 61,
          "Bin": "26",
          "meanEbbDir": 239,
          "Time": "2026-11-19 18:03",
          "Depth": "19",
          "Velocity_Major": 1.08
        },
        {
          "Type": "slack",
          "meanFloodDir": 61,
          "Bin": "26",
          "meanEbbDir": 239,
          "Time": "2026-11-19 20:21",
          "Depth": "19",
          "Velocity_Major": 0
        },
        {
          "Type": "ebb",
          "meanFloodDir": 61,
          "Bin": "26",
          "meanEbbDir": 239,
          "Time": "2026-11-19 23:53",
          "Depth": "19",
          "Velocity_Major": -2.28
        }
      ]
    }
  },
  "notes": [
    "top-level keys: ['current_predictions']"
  ],
  "discrepancies": [],
  "error": null
}
```

### `coops_water_temp_9414290_expect_nodata`
```json
{
  "ok": true,
  "verdict": "N/A",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": 200,
  "shape": {
    "error": {
      "message": "str"
    }
  },
  "sample": {
    "error": {
      "message": "No data was found. This product may not be offered at this station at the requested time."
    }
  },
  "notes": [
    "Confirmed: no water_temperature at 9414290 (matches DATA_SOURCES)"
  ],
  "discrepancies": [],
  "error": null
}
```

### `ndbc_46026`
```json
{
  "ok": true,
  "verdict": "OK",
  "observed_at": "2026-11-19T23:30:00+00:00",
  "age_hours": 0.5,
  "max_age_hours": 3.0,
  "http_status": 200,
  "shape": {
    "format": "space_separated_txt",
    "header_lines": [
      "#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE",
      "#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft"
    ],
    "n_data_rows": 6500
  },
  "sample": [
    "2026 11 19 23 30 300 10.0 13.0    MM    MM    MM  MM 1012.0    MM  18.8    MM   MM   MM    MM"
  ],
  "notes": [
    "latest_row_stamp=2026-11-19 23:30Z",
    "MM sentinel present in row",
    "WTMP=18.8"
  ],
  "discrepancies": [],
  "error": null
}
```

### `ndbc_46012`
```json
{
  "ok": true,
  "verdict": "OK",
  "observed_at": "2026-11-19T23:00:00+00:00",
  "age_hours": 1.0,
  "max_age_hours": 3.0,
  "http_status": 200,
  "shape": {
    "format": "space_separated_txt",
    "header_lines": [
      "#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE",
      "#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft"
    ],
    "n_data_rows": 1101
  },
  "sample": [
    "2026 11 19 23 00 310 10.0 12.0   3.8    16    MM  MM 1012.4  14.0  18.9  10.2   MM +1.6    MM"
  ],
  "notes": [
    "latest_row_stamp=2026-11-19 23:00Z",
    "MM sentinel present in row",
    "WTMP=18.9"
  ],
  "discrepancies": [],
  "error": null
}
```

### `ndbc_46237`
```json
{
  "ok": true,
  "verdict": "OK",
  "observed_at": "2026-11-19T23:00:00+00:00",
  "age_hours": 1.0,
  "max_age_hours": 3.0,
  "http_status": 200,
  "shape": {
    "format": "space_separated_txt",
    "header_lines": [
      "#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE",
      "#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft"
    ],
    "n_data_rows": 2165
  },
  "sample": [
    "2026 11 19 23 00  MM   MM   MM   3.3    15   8.7 272     MM  14.4  17.1    MM   MM   MM    MM"
  ],
  "notes": [
    "latest_row_stamp=2026-11-19 23:00Z",
    "MM sentinel present in row",
    "WTMP=17.1"
  ],
  "discrepancies": [],
  "error": null
}
```

### `ndbc_46239`
```json
{
  "ok": true,
  "verdict": "STALE",
  "observed_at": "2026-10-25T03:00:00+00:00",
  "age_hours": 621.0,
  "max_age_hours": 3.0,
  "http_status": 200,
  "shape": {
    "format": "space_separated_txt",
    "header_lines": [
      "#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE",
      "#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft"
    ],
    "n_data_rows": 2141
  },
  "sample": [
    "2026 10 25 03 00  MM   MM   MM   2.0    10   6.9 315     MM  18.4  20.2    MM   MM   MM    MM"
  ],
  "notes": [
    "latest_row_stamp=2026-10-25 03:00Z",
    "STALE confirmed age_days=25 (DATA_SOURCES warned)",
    "MM sentinel present in row",
    "WTMP=20.2"
  ],
  "discrepancies": [
    "FROZEN/STALE: observation age 621.0 h > budget 3.0 h (HTTP 200 does not mean usable)"
  ],
  "error": null
}
```

### `ndbc_46026_spec`
```json
{
  "ok": true,
  "verdict": "N/A",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": 200,
  "shape": {
    "header": [
      "#YY  MM DD hh mm WVHT  SwH  SwP  WWH  WWP SwD WWD  STEEPNESS  APD MWD",
      "#yr  mo dy hr mn    m    m  sec    m  sec  -  degT     -      sec degT"
    ],
    "n_rows": 2147
  },
  "sample": [
    "2026 11 19 23 09  3.7  3.2 14.8  1.9  6.7   W WSW      SWELL  8.4 278"
  ],
  "notes": [],
  "discrepancies": [],
  "error": null
}
```

### `nws_points_sf`
```json
{
  "ok": true,
  "verdict": "N/A",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": 200,
  "shape": {
    "properties_keys": [
      "@id",
      "@type",
      "astronomicalData",
      "cwa",
      "forecast",
      "forecastGridData",
      "forecastHourly",
      "forecastOffice",
      "forecastZone",
      "gridId",
      "gridX",
      "gridY",
      "nwr",
      "observationStations",
      "radarStation",
      "relativeLocation",
      "timeZone",
      "type"
    ]
  },
  "sample": {
    "gridId": "MTR",
    "gridX": 83,
    "gridY": 107,
    "forecastZone": "https://api.weather.gov/zones/forecast/PZZ530"
  },
  "notes": [
    "grid MTR/83,107 matches DATA_SOURCES"
  ],
  "discrepancies": [],
  "error": null
}
```

### `nws_alerts_CA`
```json
{
  "ok": true,
  "verdict": "N/A",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": 200,
  "shape": {
    "type": "FeatureCollection",
    "n_features": 34
  },
  "sample": [
    [
      "Winter Storm Warning",
      6
    ],
    [
      "Wind Advisory",
      5
    ],
    [
      "Flood Advisory",
      4
    ],
    [
      "High Surf Advisory",
      4
    ],
    [
      "Special Weather Statement",
      3
    ],
    [
      "Beach Hazards Statement",
      3
    ],
    [
      "Cold Weather Advisory",
      3
    ],
    [
      "Winter Weather Advisory",
      2
    ],
    [
      "Coastal Flood Advisory",
      2
    ],
    [
      "Flash Flood Watch",
      1
    ]
  ],
  "notes": [
    "alert_count=34 (DATA_SOURCES had 38 earlier today)"
  ],
  "discrepancies": [],
  "error": null
}
```

### `nws_zone_PZZ545`
```json
{
  "ok": true,
  "verdict": "N/A",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": 200,
  "shape": {
    "n_periods": 11,
    "period0_keys": [
      "number",
      "name",
      "detailedForecast"
    ]
  },
  "sample": {
    "name": "Tonight",
    "detailedForecast": "NW wind 15 to 20 kt, easing to 10 to 15 kt after midnight. Seas 8 to 11 ft. Wave Detail: S 4 ft at 8 seconds and W 10 ft at 14 seconds. A slight chance of rain this evening, then a chance of rain after midnight. Rain likely late."
  },
  "notes": [],
  "discrepancies": [],
  "error": null
}
```

### `nws_srf_MTR`
```json
{
  "ok": true,
  "verdict": "N/A",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": 200,
  "shape": {
    "keys": [
      "@context",
      "@graph"
    ],
    "n_products": 74
  },
  "sample": {
    "latest_id": "58caca9e-1f69-4cc6-b6f9-043ac81b3160",
    "issuanceTime": "2026-11-19T22:53:00+00:00",
    "productName": "Surf Forecast"
  },
  "notes": [],
  "discrepancies": [],
  "error": null
}
```

### `erddap_mur_sst`
```json
{
  "ok": true,
  "verdict": "OK",
  "observed_at": "2026-11-18T09:00:00+00:00",
  "age_hours": 39.0,
  "max_age_hours": 72.0,
  "http_status": 200,
  "shape": {
    "columnNames": [
      "time",
      "latitude",
      "longitude",
      "analysed_sst"
    ],
    "n_rows": 36
  },
  "sample": [
    [
      "2026-11-18T09:00:00Z",
      37.5,
      -122.55,
      18.713
    ],
    [
      "2026-11-18T09:00:00Z",
      37.5,
      -122.54,
      18.716
    ],
    [
      "2026-11-18T09:00:00Z",
      37.5,
      -122.53,
      18.72
    ]
  ],
  "notes": [
    "time_sample=2026-11-18T09:00:00Z",
    "null_analysed_sst_count=11/36 (coast/land fill)"
  ],
  "discrepancies": [],
  "error": null
}
```

### `erddap_viirs_chl_8day`
```json
{
  "ok": true,
  "verdict": "STALE",
  "observed_at": "2026-11-09T00:00:00+00:00",
  "age_hours": 264.0,
  "max_age_hours": 240.0,
  "http_status": 200,
  "shape": {
    "columnNames": [
      "time",
      "altitude",
      "latitude",
      "longitude",
      "chla"
    ],
    "n_rows": 49
  },
  "sample": [
    [
      "2026-11-09T00:00:00Z",
      0,
      37.54875,
      -122.54625,
      1.5067434
    ],
    [
      "2026-11-09T00:00:00Z",
      0,
      37.54875,
      -122.53875,
      1.6494879
    ],
    [
      "2026-11-09T00:00:00Z",
      0,
      37.54875,
      -122.53125,
      1.7409934
    ]
  ],
  "notes": [
    "time_sample=2026-11-09T00:00:00Z",
    "null_chla_count=22/49 (coast/land fill)"
  ],
  "discrepancies": [
    "FROZEN/STALE: observation age 264.0 h > budget 240.0 h (HTTP 200 does not mean usable)"
  ],
  "error": null
}
```

### `erddap_charm_0day`
```json
{
  "ok": true,
  "verdict": "STALE",
  "observed_at": "2026-11-02T12:00:00+00:00",
  "age_hours": 420.0,
  "max_age_hours": 72.0,
  "http_status": 200,
  "shape": {
    "columnNames": [
      "time",
      "latitude",
      "longitude",
      "pseudo_nitzschia"
    ],
    "n_rows": 64
  },
  "sample": [
    [
      "2026-11-02T12:00:00Z",
      37.39,
      237.3,
      0.7369895
    ],
    [
      "2026-11-02T12:00:00Z",
      37.39,
      237.33,
      0.7491479
    ],
    [
      "2026-11-02T12:00:00Z",
      37.39,
      237.36,
      0.7009353
    ]
  ],
  "notes": [
    "time_sample=2026-11-02T12:00:00Z",
    "null_pseudo_nitzschia_count=4/64 (coast/land fill)"
  ],
  "discrepancies": [
    "FROZEN/STALE: observation age 420.0 h > budget 72.0 h (HTTP 200 does not mean usable)"
  ],
  "error": null
}
```

### `erddap_mur_anom`
```json
{
  "ok": false,
  "verdict": "FAIL",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": 503,
  "shape": {},
  "sample": "Error {\n    code=503;\n    message=\"Service Unavailable: There was a (temporary?) problem.  Wait a minute, then try again.  (In a browser, click the Reload button.)\";\n}\n",
  "notes": [],
  "discrepancies": [
    "CoastWatch ERDDAP returned 503 \u2014 transient/intermittent availability (flapping observed); retry with backoff, then serve last-good with age"
  ],
  "error": "HTTPError: 503"
}
```

### `cdph_arcgis_special_advisory`
```json
{
  "ok": true,
  "verdict": "N/A",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": 200,
  "shape": {
    "n_features": 1,
    "attr_keys": [
      "TITLE",
      "DESCRIPTION",
      "DATE",
      "VISIBLE"
    ]
  },
  "sample": [
    {
      "TITLE": "Special Advisory Area - Northern Channel Islands",
      "VISIBLE": 1
    }
  ],
  "notes": [],
  "discrepancies": [],
  "error": null
}
```

### `cdph_arcgis_county_symbols`
```json
{
  "ok": true,
  "verdict": "N/A",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": 200,
  "shape": {
    "n_features": 21
  },
  "sample": [
    "Del Norte County",
    "Humboldt County",
    "Mendocino County",
    "Sonoma County",
    "Marin County",
    "San Francisco County",
    "Contra Costa County",
    "Alameda County",
    "San Mateo County",
    "Santa Cruz County"
  ],
  "notes": [
    "has San Francisco County",
    "has San Mateo County",
    "has Marin County"
  ],
  "discrepancies": [],
  "error": null
}
```

### `cdph_html_tls_check`
```json
{
  "ok": false,
  "verdict": "FAIL",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": null,
  "shape": {},
  "sample": null,
  "notes": [
    "strict TLS verification FAILED (server omits intermediate cert); source NOT usable for the closure gate; verification is never disabled"
  ],
  "discrepancies": [
    "CDPH HTML unusable under strict TLS; closure gate must be cannot_confirm unless the intermediate CA is pinned"
  ],
  "error": "URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1029)>"
}
```

### `beachwatch_bacteria_datastore`
```json
{
  "ok": true,
  "verdict": "N/A",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": 200,
  "shape": {
    "success": true,
    "record_keys": [
      "_id",
      "Regional Board",
      "RESULTS id",
      "SampleDate",
      "StartTime",
      "StartTimeInd",
      "Parameter",
      "QualifierId",
      "Qualifier",
      "QualifierDescription",
      "Result",
      "Unit",
      "LabCode_id",
      "AnalysisMethodId",
      "AnalysisMethod",
      "SampleTypeId",
      "SampleType",
      "Results Comments",
      "County",
      "User_id",
      "upload_ts",
      "Result Record Create Date",
      "LabID",
      "StormDrainFlow",
      "Weather",
      "TidalHeight",
      "SurfHeight",
      "Turbidity",
      "WaterColor",
      "Odor",
      "Distance",
      "Direction",
      "RL",
      "MDL",
      "Dilution",
      "Station_id",
      "Station_Agency_id",
      "BeachName_id",
      "Station_Name",
      "Station_Description",
      "AgencyStationIdentifier",
      "Station_UpperLat",
      "Station_UpperLon",
      "Station_LowerLat",
      "Station_LowerLon",
      "SwimSeason",
      "OffSeason",
      "AsNeededSeason",
      "CountyCode",
      "CountyName",
      "Status",
      "UpdateDate",
      "Results Insert Date",
      "pointZero",
      "Beach_AgencyName",
      "Beach_Name",
      "Description",
      "BeachType",
      "Beach Length",
      "AttendanceWinter",
      "AttendanceSummer",
      "NearestCityName",
      "WaterBodyName",
      "WaterBodyClass",
      "AB411Beach",
      "USEPAID",
      "BeachAccess",
      "SwimSeasonLength",
      "WaterBodyType",
      "WaterShedName",
      "Beach_UpperLat",
      "Beach_UpperLon",
      "Beach_LowerLat",
      "Beach_LowerLon",
      "Beach_County",
      "Beach_User_id",
      "Beach_Status",
      "CountAsBeach",
      "Agency_id",
      "Agency_Code",
      "Agency_Name",
      "Agency_Jurisdiction",
      "StreetAddress",
      "City",
      "Results Contact Person",
      "Zip",
      "EstMonCost",
      "EstCoastlineAdvisoryCost",
      "EstTotalCost",
      "Agency_Comments",
      "Agency_County",
      "Agency_User_id",
      "Regional Board Number",
      "Regional Board Name",
      "rank"
    ],
    "total": 88728
  },
  "sample": [
    {
      "_id": 13187,
      "Regional Board": "RB2",
      "RESULTS id": 2986058,
      "SampleDate": "2025-02-10",
      "StartTime": "11:34:00",
      "StartTimeInd": 0,
      "Parameter": "Total Coliforms",
      "QualifierId": 1,
      "Qualifier": "=",
      "QualifierDescription": "Equal to",
      "Result": 906,
      "Unit": "MPN/100ml",
      "LabCode_id": 14,
      "AnalysisMethodId": 16,
      "AnalysisMethod": "Colilert-18",
      "SampleTypeId": 1,
      "SampleType": "Results",
      "Results Comments": null,
      "County": "San Mateo",
      "User_id": 257,
      "upload_ts": null,
      "Result Record Create Date": "2025-02-12",
      "LabID": null,
      "StormDrainFlow": null,
      "Weather": null,
      "TidalHeight": null,
      "SurfHeight": null,
      "Turbidity": null,
      "WaterColor": null,
      "Odor": null,
      "Distance": null,
      "Direction": null,
      "RL": 10,
      "MDL": 10,
      "Dilution": 0,
      "Station_id": 692,
      "Station_Agency_id": 14,
      "BeachName_id": 139,
      "Station_Name": "San Gregorio Creek",
      "Station_Description": "San Gregorio Creek",
      "AgencyStationIdentifier": "San Gregorio Creek",
      "Station_UpperLat": 37.32098,
      "Station_UpperLon": -122.40321,
      "Station_LowerLat": 37.32098,
      "Station_LowerLon": -122.40321,
      "SwimSeason": "Once a week",
      "OffSeason": "None(not sampled)",
      "AsNeededSeason": "Twice a week",
      "CountyCode": "SM",
      "CountyName": "San Mateo",
      "Status": "Active",
      "UpdateDate": "2018-09-19",
      "Results Insert Date": "2015-08-19",
      "pointZero": 1,
      "Beach_AgencyName": "Health Department County of San
```

### `beachwatch_advisories_datastore`
```json
{
  "ok": true,
  "verdict": "N/A",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": 200,
  "shape": {
    "record_keys": [
      "_id",
      "DURATION CALCULATED",
      "Regional Board",
      "Advisory id",
      "HistoricalStationName",
      "prefix",
      "mile",
      "DateofAdvisory",
      "TimeofAdvisory",
      "DateOpened",
      "TimeOpened",
      "AdvisoryType",
      "AdvisoryCause",
      "Description",
      "Extent",
      "StartofExtent",
      "StartOfExtentType",
      "EndofExtent",
      "EndOfExtentType",
      "Source",
      "Advisory Comments",
      "DescriptionofArea",
      "ActionBy",
      "AffectedLengthUnit",
      "SubstanceName",
      "SubstanceVolume",
      "SubstanceUnit",
      "AdditionalAction",
      "ActionDate",
      "ActionDescription",
      "County",
      "User_id",
      "Enterococcus",
      "Fecal Coliforms",
      "Total Coliforms",
      "e_coli",
      "Ratio",
      "Advisory Record Create Date",
      "Station_id",
      "Station_Agency_id",
      "BeachName_id",
      "Station_Name",
      "Station_Description",
      "AgencyStationIdentifier",
      "Station_UpperLat",
      "Station_UpperLon",
      "Station_LowerLat",
      "Station_LowerLon",
      "SwimSeason",
      "OffSeason",
      "AsNeededSeason",
      "CountyCode",
      "CountyName",
      "Status",
      "UpdateDate",
      "Advisories Insert Date",
      "pointZero",
      "Datum",
      "BeachProfileId",
      "Beach_AgencyName",
      "Beach_Name",
      "BeachDescription",
      "BeachType",
      "Beach Length",
      "AttendanceWinter",
      "AttendanceSummer",
      "NearestCityName",
      "WaterBodyName",
      "WaterBodyClass",
      "AB411Beach",
      "USEPAID",
      "BeachAccess",
      "SwimSeasonLength",
      "WaterBodyType",
      "WaterShedName",
      "Beach_UpperLat",
      "Beach_UpperLon",
      "Beach_LowerLat",
      "Beach_LowerLon",
      "Beach_County",
      "Beach_User_id",
      "Beach_Status",
      "CountAsBeach",
      "Agency_id",
      "Agency_Code",
      "Agency_Name",
      "Agency_Jurisdiction",
      "StreetAddress",
      "City",
      "Advisories Contact Person",
      "Zip",
      "EstMonCost",
      "EstCoastlineAdvisoryCost",
      "EstTotalCost",
      "Agency_Comments",
      "Agency_County",
      "Agency_User_id",
      "Regional Board Number",
      "Regional Board Name",
      "rank"
    ],
    "n": 2
  },
  "sample": [
    {
      "_id": 869,
      "DURATION CALCULATED": 14,
      "Regional Board": "RB2",
      "Advisory id": 3054,
      "HistoricalStationName": "San Gregorio Creek",
      "prefix": "C",
      "mile": 651,
      "DateofAdvisory": "2009-09-23",
      "TimeofAdvisory": "16:08:08",
      "DateOpened": "2009-10-07",
      "TimeOpened": "09:55:36",
      "AdvisoryType": "Posting",
      "AdvisoryCause": "Unknown Cause",
      "Description": "San Gregorio Creek",
      "Extent": 0.05681818,
      "StartofExtent": 651.7343,
      "StartOfExtentType": "Lat/Long",
      "EndofExtent": 651.7911,
      "EndOfExtentType": "Lat/Long",
      "Source": "Unknown",
      "Advisory Comments": null,
      "DescriptionofArea": "San Gregorio State Beach San Gregorio Creek",
      "ActionBy": null,
      "AffectedLengthUnit": "miles",
      "SubstanceName": "Unknown",
      "SubstanceVolume": null,
      "SubstanceUnit": "Gallons",
      "AdditionalAction": null,
      "ActionDate": null,
      "ActionDescription": null,
      "County": "San Mateo",
      "User_id": 9,
      "Enterococcus": null,
      "Fecal Coliforms": null,
      "Total Coliforms": 1,
      "e_coli": null,
      "Ratio": null,
      "Advisory Record Create Date": "2015-09-19T15:39:59.000",
      "Station_id": 692,
      "Station_Agency_id": 14,
      "BeachName_id": 139,
      "Station_Name": "San Gregorio Creek",
      "Station_Description": "San Gregorio Creek",
      "AgencyStationIdentifier": "San Gregorio Creek",
      "Station_UpperLat": 37
```

### `firms_modis_usa_24h_csv`
```json
{
  "ok": true,
  "verdict": "N/A",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": 200,
  "shape": {
    "n_usa": 442,
    "n_bbox": 0,
    "fields": [
      "latitude",
      "longitude",
      "brightness",
      "scan",
      "track",
      "acq_date",
      "acq_time",
      "satellite",
      "confidence",
      "version",
      "bright_t31",
      "frp",
      "daynight"
    ]
  },
  "sample": [
    {
      "latitude": "39.18688",
      "longitude": "-96.73347",
      "brightness": "303.34",
      "scan": "1.4",
      "track": "1.17",
      "acq_date": "2026-11-18",
      "acq_time": "0215",
      "satellite": "T",
      "confidence": "55",
      "version": "6.1NRT",
      "bright_t31": "280.13",
      "frp": "13.71",
      "daynight": "N"
    }
  ],
  "notes": [],
  "discrepancies": [],
  "error": null
}
```

### `eonet_wildfires_bbox`
```json
{
  "ok": true,
  "verdict": "N/A",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": 200,
  "shape": {
    "n_events": 5
  },
  "sample": [
    {
      "id": "EONET_9105",
      "title": "CREEK Wildfire, Alameda, California"
    },
    {
      "id": "EONET_6841",
      "title": "ADOBE 3 Wildfire, Sonoma, California"
    },
    {
      "id": "EONET_6842",
      "title": "ADOBE 2 Wildfire, Sonoma, California"
    },
    {
      "id": "EONET_6850",
      "title": "I 80  / CUMMINGS SKWY Wildfire, Contra Costa, California"
    },
    {
      "id": "EONET_7243",
      "title": "ST HELENA HWY S RUTHERFORD Wildfire, Napa, California"
    }
  ],
  "notes": [
    "EONET open events may be stale \u2014 use FIRMS for heat (per DATA_SOURCES)"
  ],
  "discrepancies": [],
  "error": null
}
```

### `epa_uv_hourly_94121`
```json
{
  "ok": true,
  "verdict": "OK",
  "observed_at": "2026-11-19T23:00:00+00:00",
  "age_hours": 1.01,
  "max_age_hours": 6.0,
  "http_status": 200,
  "shape": {
    "type": "list",
    "n": 9
  },
  "sample": [
    {
      "ORDER": 5,
      "ZIP": "94121",
      "CITY": "San Francisco",
      "STATE": "CA",
      "DATE_TIME": "Nov/19/2026 07 AM",
      "UV_VALUE": 0
    },
    {
      "ORDER": 6,
      "ZIP": "94121",
      "CITY": "San Francisco",
      "STATE": "CA",
      "DATE_TIME": "Nov/19/2026 08 AM",
      "UV_VALUE": 0
    }
  ],
  "notes": [],
  "discrepancies": [],
  "error": null
}
```

### `nasa_power_daily_sf`
```json
{
  "ok": true,
  "verdict": "N/A",
  "observed_at": null,
  "age_hours": null,
  "max_age_hours": null,
  "http_status": 200,
  "shape": {
    "parameters": [
      "ALLSKY_SFC_SW_DWN",
      "ALLSKY_SFC_UV_INDEX",
      "T2M"
    ]
  },
  "sample": {
    "UV_INDEX_tail": {
      "20261114": -999.0,
      "20261115": -999.0,
      "20261116": -999.0,
      "20261117": -999.0,
      "20261118": -999.0
    },
    "SW_DWN_tail": {
      "20261114": 2.8644,
      "20261115": -999.0,
      "20261116": -999.0,
      "20261117": -999.0,
      "20261118": -999.0
    }
  },
  "notes": [
    "ALLSKY_SFC_UV_INDEX all -999 \u2014 confirms DATA_SOURCES; use EPA UV"
  ],
  "discrepancies": [],
  "error": null
}
```

## Discrepancies vs DATA_SOURCES.md

- **ndbc_46239:** FROZEN/STALE: observation age 621.0 h > budget 3.0 h (HTTP 200 does not mean usable)
- **erddap_viirs_chl_8day:** FROZEN/STALE: observation age 264.0 h > budget 240.0 h (HTTP 200 does not mean usable)
- **erddap_charm_0day:** FROZEN/STALE: observation age 420.0 h > budget 72.0 h (HTTP 200 does not mean usable)
- **erddap_mur_anom:** CoastWatch ERDDAP returned 503 — transient/intermittent availability (flapping observed); retry with backoff, then serve last-good with age
- **cdph_html_tls_check:** CDPH HTML unusable under strict TLS; closure gate must be cannot_confirm unless the intermediate CA is pinned

## Adapter implications (for Phase 3)

- CO-OPS: parse `predictions[]` / `data[]`; treat `error.message` as down/no-product.
- NDBC: reject `MM`; check row timestamp for stale CDIP IDs; WTMP/WVHT metric.
- NWS: require User-Agent; resolve points→grid each time (XY may shift).
- ERDDAP: availability flaps (404/503/200); treat as transient. tiny bboxes; C-HARM lon 0-360; null fills; judge freshness by `time` (C-HARM ~17 d and VIIRS ~10 d are STALE).
- Shellfish: ArcGIS layers are static pins (cannot represent closure status); CDPH HTML fails strict TLS (missing intermediate) -> closure gate is cannot_confirm until a dated source exists. Never disable TLS verification.
- UV: EPA hourly ZIP; do not use POWER UV_INDEX (fill).
- Fires: FIRMS CSV + bbox filter; EONET narrative only.
