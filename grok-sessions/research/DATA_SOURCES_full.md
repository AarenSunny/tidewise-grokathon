> **Companion file (full detail).** This is the long-form research notes (regulation quotes §29.80/§28.65, sunrise APIs, gear-allowed notes, C-HARM, CDPH, beach sources) kept in `grok-sessions/research/`. The condensed, authoritative-for-build summary is `/DATA_SOURCES.md`. Section numbers below are this file's own. Verified 2026-11-19 (America/Los_Angeles).

# TideWise Data Sources

Research notes for the SF Bay Area coast (Half Moon Bay → Pacifica → SF Bay / Golden Gate / Point Reyes approaches).  
**Accuracy over coverage.** Every primary endpoint below was called live on **2026-11-19** (America/Los_Angeles) unless marked otherwise. Sample snippets are real responses from those calls.

Allowed engineering inputs only: this file, `scripts/research_probes/`, and `grok-sessions/research/`.

---

## Part A — Data sources

### 1. NOAA CO-OPS — tides, water levels, currents

**Primary:** NOAA CO-OPS Metadata API + Data API  
- Metadata: `https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/`  
- Data: `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter`

**Auth:** None.

**Example queries (region):**
```
# Hi/Lo tide predictions, San Francisco (Golden Gate), MLLW feet, local time
https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=today&station=9414290&product=predictions&datum=MLLW&time_zone=lst_ldt&interval=hilo&units=english&format=json

# Latest observed water level
https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=latest&station=9414290&product=water_level&datum=MLLW&time_zone=lst_ldt&units=english&format=json

# Current predictions (slack/max), SF Bay Entrance
https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=today&station=SFB1201&product=currents_predictions&time_zone=lst_ldt&units=english&format=json&interval=MAX_SLACK

# Station lists
https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=waterlevels&units=english
https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=tidepredictions&units=english
https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=currentpredictions&units=english
https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=currents&units=english
```

**Region water-level (real-time capable) stations verified via metadata API (lat 37.0–38.5, lon −123.5…−121.8):**

| ID | Name | Lat | Lon | Notes |
|----|------|-----|-----|-------|
| 9414290 | San Francisco | 37.8063 | −122.4659 | Primary reference; predictions + observed WL + PORTS/OFS links |
| 9414523 | Redwood City | 37.5068 | −122.2119 | South Bay |
| 9414750 | Alameda | 37.7720 | −122.3003 | |
| 9414863 | Richmond | 37.9283 | −122.4000 | |
| 9415020 | Point Reyes | 37.9942 | −122.9736 | Outer coast / Pt Reyes |
| 9415102 | Martinez-Amorco Pier | 38.0346 | −122.1252 | Carquinez |
| 9415144 | Port Chicago | 38.0560 | −122.0395 | |

**Prediction-only tide stations of interest (no water-level product in WL list):**

| ID | Name | Lat | Lon |
|----|------|-----|-----|
| 9414131 | Pillar Point Harbor, Half Moon Bay | 37.5025 | −122.4822 |
| 9414275 | Ocean Beach, outer coast | 37.7750 | −122.5130 |
| 9413878 | Ano Nuevo Island | 37.1083 | −122.3380 |
| 9414958 | Bolinas Lagoon | 37.9080 | −122.6785 |
| 9415228 | Inverness, Tomales Bay | 38.1133 | −122.8680 |
| 9415469 | Tomales Bay entrance | 38.2283 | −122.9770 |
| 9414816 | Berkeley | 37.8650 | −122.3070 |
| 9414817 | Angel Island (west side) | 37.8600 | −122.4430 |

**Currents:**
- **Predictions:** many harmonic stations under `type=currentpredictions` (288 in the bbox). Useful IDs include Golden Gate / entrance area (e.g. `SFB1201` San Francisco Bay Entrance — predictions worked today; metadata shows a 2012–2013 survey deployment history). Also `PCT*` stations near Point Bonita / Fort Point / Alcatraz.
- **Real-time currents** (`type=currents`) in bbox today: `s06010` Martinez-AMORCO, `s08010` Southampton Shoal LB6, `s09010` Oakland Outer Harbor LB3, `s10010` Oakland Inner Harbor LB4. (No Golden Gate real-time current station appeared in this list today.)

**Update / latency:** Predictions are model/harmonic (available years ahead). Observed water levels typically 6-minute samples; `q=p` = preliminary. PORTS stations often near-real-time (minutes).

**Resolution:** Point stations; 6-min observed WL; hi/lo or 6-min/hourly predictions via `interval`.

**Response format + real sample (2026-11-19):**
```json
{"predictions": [
  {"t": "2026-11-19 00:12", "v": "1.018", "type": "L"},
  {"t": "2026-11-19 07:15", "v": "5.269", "type": "H"},
  {"t": "2026-11-19 13:32", "v": "1.674", "type": "L"},
  {"t": "2026-11-19 19:20", "v": "4.113", "type": "H"}
]}
```
```json
{"metadata": {"id": "9414290", "name": "San Francisco", "lat": "37.8063", "lon": "-122.4659"},
 "data": [{"t": "2026-11-19 15:18", "v": "3.42", "s": "0.328", "f": "0,0,0,0", "q": "p"}]}
```
Currents predictions sample fields: `Type` (`slack`/`flood`/`ebb`), `Time`, `Velocity_Major` (knots; ebb negative), `meanFloodDir`/`meanEbbDir`, `Depth`, `Bin`.

**Missing / quirks:**
- Error JSON when product unavailable: `{"error":{"message":"No data was found..."}}` (e.g. `water_temperature` on 9414290 returned this today).
- Datum must match product (`MLLW` for tides). Use `time_zone=lst_ldt` for local.
- Pillar Point `9414131` is **prediction-only** (metadata exists; not in waterlevels list).

**Rate limits:** No published hard quota found on the API landing page; be polite (burst-friendly but cache predictions). Documented public API — no key.

**Gotchas:** Station IDs for currents use different schemas (`SFB####`, `PCT####`, `s0####`). Always resolve via metadata API — do not hard-code unverified IDs.

**Backup:** NOAA Tides & Currents HTML/CSV exports; USGS NWIS for a few Bay gauges; NOAA OFS SF Bay model pages linked from station products.

**Probe:** `scripts/research_probes/01_coops_tides.sh`  
**Verified on:** 2026-11-19

---

### 2. NOAA NDBC — buoy waves, wind, water temp

**Primary:** `https://www.ndbc.noaa.gov/data/realtime2/{STATION}.txt` (standard meteorological)  
Spectral: `https://www.ndbc.noaa.gov/data/realtime2/{STATION}.spec`  
Station page: `https://www.ndbc.noaa.gov/station_page.php?station={STATION}`

**Auth:** None.

**Region stations verified HTTP 200 today:**

| ID | Approx location (from station page) | Role | Notes from today’s file |
|----|-------------------------------------|------|-------------------------|
| 46026 | 37.750 N, 122.838 W (SF Bar / approaches) | Waves + wind + WTMP | WVHT 3.5 m; WTMP 18.8 °C; DPD=`MM` |
| 46012 | 37.356 N, 122.881 W (Half Moon Bay offshore) | Waves + wind + WTMP | Active |
| 46013 | Bodega / North (in probe set) | Wind/pressure; waves often `MM` | |
| 46042 | Monterey Bay offshore | Waves | Farther south but useful swell |
| 46237 | 37.788 N, 122.634 W (SF ocean) | CDIP/wave buoy | Waves+WTMP; wind `MM` |
| 46214 | 37.944 N, 123.466 W (Pt Reyes / Bodega swell) | Swell | Large WVHT today (5.4 m) |
| 46239 / 46213 | CDIP | | Files present but **stale** (last rows Oct/early Nov 2026) |
| FTPC1 | 37.806 N, 122.466 W (Fort Point) | Wind/pressure coastal | |
| AAMC1 | Alameda | Wind + WTMP | |
| RTYC1 | Redwood City | Wind | |
| PXOC1 | Pier 1 / SF | Wind | |

**Update / latency:** Standard met often 10–60 min; CDIP wave buoys ~30 min. Files are rolling recent history.

**Resolution:** Point; wave height in meters; wind m/s; WTMP °C; directions degT.

**Format:** Space-separated; two header lines (`#YY…` units, `#yr…`).  
**Missing marker: `MM`** (confirmed).

Real sample (`46026.txt`, 2026-11-19):
```
#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE
#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft
2026 11 19 22 30 300 12.0 15.0   3.5    MM   8.2 268 1011.4    MM  18.8    MM   MM   MM    MM
```

Spectral sample (`46026.spec`):
```
#YY  MM DD hh mm WVHT  SwH  SwP  WWH  WWP SwD WWD  STEEPNESS  APD MWD
2026 11 19 22 40  3.5  3.1 14.8  1.5  5.3   W WNW      SWELL  8.2 268
```

**Rate limits:** None published; static file CDN-like. Cache 5–15 min.

**Gotchas:** Not all columns populate on all stations (wind buoys vs wave buoys). Stale CDIP IDs can still return HTTP 200 with old timestamps — **always check the datetime of the first data row**. Units are metric in realtime2 (convert for UI).

**Backup:** CO-OPS met at 9414290; NWS buoy observations via marine forecast discussion; CDIP thrudata if NDBC path fails.

**Probe:** `scripts/research_probes/02_ndbc_buoys.sh`  
**Verified on:** 2026-11-19

---

### 3. NWS api.weather.gov — forecast, marine zones, alerts, Surf Zone Forecast

**Primary:** `https://api.weather.gov/`  
**Auth:** None, but **User-Agent is required** (anonymous/default UAs are blocked). Use a descriptive UA string including project + contact path.

**Example flow:**
```
GET /points/{lat},{lon}          → gridId, gridX, gridY, forecast, forecastZone
GET /gridpoints/{office}/{x},{y}/forecast
GET /zones/forecast/{UGC}/forecast   e.g. PZZ545
GET /alerts/active?area=CA
GET /alerts/active?zone=PZZ545,CAZ509
GET /products/types/SRF/locations/MTR
GET /products/{id}
```

**Verified points (2026-11-19):**

| Place | Lat,Lon | Grid | forecastZone (from points) |
|-------|---------|------|----------------------------|
| SF Golden Gate | 37.8063,-122.4659 | MTR/83,107 | PZZ530 |
| Pacifica | 37.6135,-122.4869 | MTR/81,99 | CAZ509 (county land zone) |
| Half Moon Bay / El Granada | 37.5025,-122.4822 | MTR/80,94 | PZZ545 |

**Marine zones verified (MTR office):**

| UGC | Name |
|-----|------|
| PZZ530 | SF Bay north of Bay Bridge / San Pablo / Suisun / West Delta |
| PZZ535 | Monterey Bay |
| PZZ540 | Pt Arena → Pt Reyes out to 10 nm |
| PZZ545 | Pt Reyes → Pigeon Point out to 10 nm (**HMB/Pacifica ocean**) |
| PZZ560 | Pigeon Point → Pt Pinos out to 10 nm |
| PZZ570 / PZZ571 / PZZ575 | 10–60 nm bands |

**Alerts:** `GET /alerts/active?area=CA` returned 38 features today, including **High Surf Advisory**, **Beach Hazards Statement**, **Coastal Flood Advisory** (MTR zones CAZ505/509/529/530 etc.). Filter `properties.event` for `Small Craft Advisory`, `Beach Hazards Statement`, `High Surf Advisory`, rip-related wording in description/instruction.

**Surf Zone Forecast (SRF):**  
`/products/types/SRF/locations/MTR` returned 74 products; latest id `58caca9e-1f69-4cc6-b6f9-043ac81b3160` issued 2026-11-19T22:53:00+00:00. Product text includes per-coast-segment surf height, weather, tides, and advisories (e.g. HIGH SURF ADVISORY). Note: productName in API was `"Surf Forecast"` (type still `SRF`).

**Update / latency:** Grid forecasts updated several times daily; alerts near-real-time; SRF typically a few times per day.

**Resolution:** ~2.5 km NDFD grid for MTR; zone text for marine; alert polygons/UGC.

**Missing / quirks:** Some `points` near water return a marine `forecastZone` (PZZ*) instead of land CAZ*. Always also map activities to the correct marine UGC. No API key; CORS open (`access-control-allow-origin: *`).

**Rate limits:** Not a hard published RPS in headers today; NWS asks for caching and a real User-Agent. Avoid tight loops.

**SCA criteria (Western region, NWS CWD):** sustained winds **21–33 kt** and/or **wave heights exceeding 10 ft** (or local steepness). Source: https://www.weather.gov/marine/cwd

**Backup:** `https://tgftp.nws.noaa.gov/data/forecasts/marine/coastal/pz/pzz545.txt` plain-text marine forecast; forecast.weather.gov HTML.

**Probe:** `scripts/research_probes/03_nws_weather.sh`  
**Verified on:** 2026-11-19

---

### 4. Satellite SST — NASA JPL MUR via NOAA CoastWatch ERDDAP

**Primary dataset:** `jplMURSST41`  
`https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41`

**Auth:** None.

**Example (JSON, small bbox near Pacifica/HMB):**
```
https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.json?analysed_sst[(last)][(37.5):1:(37.6)][(-122.6):1:(-122.5)]
```

**Variables:** `analysed_sst` (°C), `analysis_error`, `sea_ice_fraction`.  
**Fill:** `_FillValue` ≈ −7.768 for `analysed_sst` (JSON often shows land/coast as `null`).

**Update / latency:** Daily fields; today’s `(last)` was **2026-11-18T09:00:00Z** → ~1-day lag for “final” MUR.

**Resolution:** 0.01° (~1 km), global, daily.

**Real sample:**
```json
{"table":{"columnNames":["time","latitude","longitude","analysed_sst"],
 "rows":[["2026-11-18T09:00:00Z",37.5,-122.6,18.695],
         ["2026-11-18T09:00:00Z",37.5,-122.59,18.698],
         ["2026-11-18T09:00:00Z",37.5,-122.5,null]]}}
```

**Rate limits:** ERDDAP fair use; keep bboxes tiny; prefer `.csv`/`.json` subsets over full grids.

**Gotchas:** Coast/land pixels null; use offshore points or quality/error layer. Dataset id spelling `jplMURSST41` (confirmed).

**Backup:** `ncdcOisst21Agg` / `ncdcOisst21NrtAgg` on same ERDDAP (0.25°); NDBC WTMP for in-situ.

**Probe:** `scripts/research_probes/04_erddap_sst_chl.py`  
**Verified on:** 2026-11-19

---

### 5. Chlorophyll-a / HAB indicators (VIIRS + C-HARM)

#### 5a. VIIRS chlorophyll (CoastWatch ERDDAP)

**Recommended regional:** `erdVHNchla8day` — “Chlorophyll a, North Pacific, NOAA VIIRS, 750m, 2015–present (8 Day Composite)”  
Also: `erdVHNchla1day`, `erdVHNchla3day`; global NRT `nesdisVHNchlaDaily` / science-quality `nesdisVHNSQchlaDaily`.

**Example:**
```
https://coastwatch.pfeg.noaa.gov/erddap/griddap/erdVHNchla8day.json?chla[(last)][(0.0)][(37.5):1:(37.6)][(-122.6):1:(-122.5)]
```
(Note altitude dimension `(0.0)` is required.)

**Real sample:** time `2026-11-09T00:00:00Z`, `chla` ≈ 1.7–2.4 mg m^-3 near 37.60 N, −122.60 W. Re-checked same afternoon: `(last)` still 2026-11-09 (cloudy-coast lag).

**Latency:** Prefer **3- or 8-day** composites for CA coast; daily often sparse. Values are linear **mg m^-3**; NASA ocean-color chl is commonly **log-scaled for display** (`colorBarScale=Log` on related products) — apply thresholds on linear values, not log10.

#### 5a-ii. Tiered chlorophyll-a thresholds (Bay Area / central CA)

| Tier | Chl-a (mg m^-3) | Where it applies | How to use with VIIRS | Source |
|------|-----------------|------------------|------------------------|--------|
| **Coastal bloom front** | **> 5** | Central & southern CA open coast (SeaWiFS-era definition still used as a remote-sensing bloom/frontal marker) | Flag pixels / smoothed nearshore medians on daily or 8-day VIIRS when chl > 5; Nezlin used ~10 km smoothing — match with spatial median before alerting | Nezlin et al. 2012, *JGR Oceans* (doi:10.1029/2011JC007773); SCCWRP reprint https://ftp.sccwrp.org/pub/download/DOCUMENTS/AnnualReports/2011AnnualReport/ar11_305_322.pdf — threshold ≈ 85th percentile nearshore chl |
| **Elevated / watch** | **~5–13** | Outer coast + Bay mouth | Treat as elevated biomass; **not** by itself a Pseudo-nitzschia toxin call — pair with C-HARM (when available) + CDPH | Same Nezlin bloom definition as lower bound; SF Bay protective threshold below |
| **SF Bay “protective”** | **≤ 13** preferred; risk rises above | **Inside San Francisco Bay** (eutrophication / HAB-abundance context — not outer ocean) | Use Bay-oriented products or in-situ; satellite chl in Bay is optically complex | Sutula et al. 2017, *Estuaries and Coasts* / PMC6134865 — CPA “protective” chl ≈ **13 mg m^-3**; “at risk” **25–40 mg m^-3** for HAB-alert / low-DO probability |
| **SF Bay “at risk”** | **25–40** | SF Bay subembayments | Strong management signal for nutrients/HAB risk inside Bay | Same |

**Important:** C-HARM’s operational **Pseudo-nitzschia bloom threshold is cell density (10,000 cells L^-1)**, not a chl-a cut (Anderson et al. / HABMAP: https://calhabmap.org/hab-forecast). Chl is a **predictor input** (gap-filled VIIRS), not the decision variable for toxin advisories. **Never open shellfish harvest on chl alone** — CDPH is authoritative.

**PACE OCI:** Searched CoastWatch West Coast (`coastwatch.pfeg.noaa.gov`), OceanWatch, PolarWatch, and central CoastWatch ERDDAP for “PACE” on 2026-11-19 — **no PACE/OCI chlorophyll dataset IDs** in those catalogs (0 rows / 502s on some hosts). NASA CMR *does* list PACE OCI products (e.g. `PACE_OCI_L3M_BGC`, `PACE_OCI_L2_BGC_NRT`) via Earthdata — **not ERDDAP-callable here**. Keep VIIRS as primary satellite chl until an ERDDAP mirror appears.

#### 5b. C-HARM (Pseudo-nitzschia / domoic acid probability) — **availability status: FLAPPING + STALE**

**Datasets (CoastWatch West Coast ERDDAP, `https://coastwatch.pfeg.noaa.gov/erddap`):** `wvcharmV3_0day` (nowcast), `wvcharmV3_1day`, `wvcharmV3_2day`, `wvcharmV3_3day` (forecasts); `charmForecast0dayV2` is a legacy v2 dataset that ends **2022-11-30** — do not use.

- Variables: `pseudo_nitzschia`, `particulate_domoic`, `cellular_domoic`, `chla_filled`, `r486_filled`, `r551_filled`, `salinity`, `water_temparture` (typo is upstream). Fill `-99999.0` (JSON `null`).
- **Lon convention: 0–360** (axis 232.5–243.0 → −127.5…−117.0 °E); grid 0.03°, lat 31.3–43.0 (391 lat × 351 lon values; `info` verified 2026-11-19 16:04 PST), time axis 1,166 values (not evenly spaced).
- Working query (2026-11-19 15:57 PST):  
  `https://coastwatch.pfeg.noaa.gov/erddap/griddap/wvcharmV3_0day.json?pseudo_nitzschia[(last)][(37.7):1:(37.7)][(237.2):1:(237.2)]`  
  → `["2026-11-02T12:00:00Z", 37.69, 237.21, 0.9121059]`

**Latest data time (from dataset `time_coverage_end` and `(last)` queries):**

| Dataset | Last time (UTC) | Age on 2026-11-19 |
|---------|-----------------|-------------------|
| `wvcharmV3_0day` | 2026-11-02T12:00:00Z | **~17 days** |
| `wvcharmV3_1day` | 2026-11-03T12:00:00Z | ~16 days |
| `wvcharmV3_3day` | 2026-11-05T12:00:00Z | ~14 days |

**Timed probe log (all America/Los_Angeles, 2026-11-19):**

| Time (PST) | Result |
|-----------|--------|
| session start (morning) | C-HARM queries OK |
| ~15:35–15:45 | **404 "Currently unknown datasetID"** for C-HARM IDs on `coastwatch.pfeg.noaa.gov` |
| ~15:50 | **200** again on coastwatch.pfeg |
| 15:57:43, 15:57:53, 15:58:02, 15:58:12, 15:58:21 | 5 consecutive probes of `wvcharmV3_0day` and `_1day`: **all 200 in 0.57–0.86 s**; data unchanged (`2026-11-02` / `2026-11-03`) |
| 16:01:38 | `coastwatch.pfeg.noaa.gov` info → **200**; `oceanview.pfeg.noaa.gov` info for `wvcharmV3_0day` → **404** |
| 16:02:27 | info → **200 but took 23.4 s** |
| 16:03:05, 16:03:22, 16:03:39 | info → **503** (1.5–1.7 s) for `wvcharmV3_0day`; also 503 for `wvcharmV3_2day`, `wvcharmV3_0day_LonPM180`, `charmForecast0dayV2` (so the 503 hit the whole server, not just one dataset) |
| 16:04:02 | info → **200** (0.86 s) |

**Honest status:** C-HARM on CoastWatch is **intermittently unregistered** (404 "unknown datasetID" ~15:35–15:45; 503s and one 23-second response at 16:02–16:03 PST) rather than permanently down — **but the data itself has not advanced since 2026-11-02**, so it is **~17 days stale** and must **not** be shown as a "current" HAB probability. Engineering rule: check `time_coverage_end`/`(last)` age on every call; if > 3 days, display "C-HARM stale — last model run 2026-11-02" and fall back to CDPH advisories (§6) + VIIRS chl tiers (§5a-ii). Retry 404/503 with backoff (1–2 min) before declaring it down. `oceanview.pfeg.noaa.gov` returned 404 for `wvcharmV3_0day` at 16:01 PST — not a usable C-HARM fallback as of that probe.

**Bloom / toxin probability thresholds encoded in `long_name`:**

| Variable | Threshold |
|----------|-----------|
| `pseudo_nitzschia` | P(cells **> 10,000 L^-1**) |
| `particulate_domoic` | P(pDA **> 500 ng L^-1**) |
| `cellular_domoic` | P(cDA **> 10 pg cell^-1**) |

**Probe:** `scripts/research_probes/08_charm_status.py` (updated: timed repeat probes + data age)  
**Verified on:** 2026-11-19 (probes 15:50–15:58 PST)

---

### 6. CDPH shellfish / biotoxin closures & advisories

**There is no public REST/JSON "current advisory status" feed.** The authoritative *live, dated* source is the CDPH news-release list (HTML), cross-checked with the hotline and CDFW in-season page.

#### 6a. Live, dated sources (verified 2026-11-19 ~15:58 PST)

| Source | URL | What it gives | Live? |
|--------|-----|---------------|-------|
| **CDPH Shellfish & Seafood Advisories (news list)** | https://www.cdph.ca.gov/Programs/OPA/Pages/Shellfish-Advisories.aspx | Dated press releases ("Month D, YYYY — …"); newest at top. Scrape headline + date + body. | **Yes** — newest item Nov 17, 2026 |
| CDPH Annual Mussel Quarantine | https://www.cdph.ca.gov/Programs/CEH/DRSEM/Pages/EMB/Shellfish/Annual-Mussel-Quarantine.aspx | Quarantine rules/window | 200; states "The annual quarantine is normally in effect from May 1 through October 31." |
| CDPH Marine Biotoxin Monitoring Program | https://www.cdph.ca.gov/Programs/CEH/DRSEM/Pages/EMB/Shellfish/Marine-Biotoxin-Monitoring-Program.aspx | 200; program description (not parsed for data) | Static |
| CDPH Domoic Acid page (crab/lobster test results) | https://www.cdph.ca.gov/Programs/CEH/DRSEM/Pages/EMB/Shellfish/Domoic-Acid.aspx | "Analytical Data – Crabs" (referenced by CDFW releases) | Page loads (200, 438 KB). I found **no "Analytical Data" table text in the HTML** (body is mostly the shared news archive), so crab test results were **not** verified from it |
| CDFW In-Season Regulation Changes (dated) | https://wildlife.ca.gov/Fishing/Ocean/Regulations/Inseason | Dated fishery delays/closures tied to CDPH/OEHHA | **Yes** — newest Nov 17, 2026 |
| CDFW Fishery closure / health advisories | https://wildlife.ca.gov/Fishing/Ocean/Health-Advisories | (not parsed) | Page loads (200) |
| OEHHA Dungeness memos | e.g. https://oehha.ca.gov/sites/default/files/media/2026-10/FINAL%20DungenessCrab_RecFisheryMemo_103026.pdf | Dated recommendations with sample tables | Per-event PDFs |
| **Phone lines** | CDPH Shellfish Information Line **(800) 553-4133**; Biotoxin line (510) 412-4643 | Recorded advisories | Human-only |
| CDPH RSS / GovDelivery | `…/Programs/OPA/Pages/NR_RSS.aspx` → **404**; `/Pages/RSS.aspx` → **404**; `public.govdelivery.com/accounts/CACDPH/subscriber/new` → **404**; `/_layouts/15/listfeed.aspx` → 200 HTML (not a feed) | — | **No RSS found** |

**Scrape structure (news list):** SharePoint page; each release = a headline line starting `CDPH …` (e.g. "CDPH Updates Northern Anchovy Consumption Advisory for Central California Waters") followed by a line beginning with the date, `November 17, 2026 — The California Department of Public Health (CDPH) …`. The page also embeds older archive lists (e.g. "News Releases 2017" links such as "CDPH Lifts Rock Crab Health Advisory in Portions of San Mateo County - South of Pillar Point") — **ignore items without a 2026 date**. Parse by regex `^(Month) \d{1,2}, 20\d\d —`.

#### 6b. TLS status of CDPH hosts (diagnosed 2026-11-19 ~15:58 PST)

| Host | Strict TLS | Cause | Workaround |
|------|-----------|-------|-----------|
| `https://www.cdph.ca.gov/…` | **FAILS** — curl exit 60 / `verify=20`, `openssl: unable to verify the first certificate (21)`, Python `CERTIFICATE_VERIFY_FAILED` | Server presents leaf issued by **"Sectigo Public Server Authentication CA OV R36"** but sends a *different* intermediate ("Sectigo RSA Organization Validation Secure Server CA"), so the issuing intermediate is missing from the chain | **Preferred:** download the missing intermediate from the cert's AIA URL `http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt` (DER; `openssl x509 -inform DER -out r36.pem`), append to the system CA bundle, and pass as `curl --cacert bundle.pem` / `requests.get(verify='bundle.pem')`. Verified: **HTTP 200, verify=0**. Quick-and-dirty: `curl -k` (probe only; do not ship). |
| `https://cdph.ca.gov/…` (apex) | **OK** (verify=0) but 302-redirects to `www.` (which fails) | — | Use apex only for the redirect check |

Leaf cert validity (openssl, 2026-11-19): notBefore Dec 31 2025, **notAfter Dec 31 2026** — re-check after rotation. `wildlife.ca.gov`, `smchealth.org`, `data.ca.gov` and `data.sf.gov` fetched fine with default TLS in this session; `oehha.ca.gov` and `webapps.sfpuc.org` were fetched using the bundle above (system roots + R36), so their strict-TLS status was not isolated.

#### 6c. CURRENT advisories affecting our coast (quoted from the CDPH list, retrieved 2026-11-19)

**Honest conclusion: no active CDPH bivalve closure/quarantine and no Dungeness "do not eat" advisory currently covers Marin, San Francisco, or San Mateo (Half Moon Bay / Pacifica / SF Bay) — except the standing viscera recommendation and the anchovy advisory below.**

- **Annual mussel quarantine — ended.** Oct 28, 2026: "…the statewide annual quarantine on mussels taken for human consumption by sport-harvesters from California's ocean waters ends at midnight on Saturday, October 31, 2026." Source: https://www.cdph.ca.gov/Programs/OPA/Pages/Shellfish-Advisories.aspx (normal window May 1–Oct 31 per the Annual-Mussel-Quarantine page).
- **San Mateo County bivalve advisory — lifted.** May 26, 2026: "The California Department of Public Health (CDPH) has lifted the shellfish safety notification today related to sport-harvested bivalve shellfish from San Mateo County."
- **Anchovy advisory touching our southern boundary (current).** Nov 17, 2026: "The California Department of Public Health (CDPH) has updated its advisory for northern anchovies to include waters between: Pigeon Point, San Mateo County (37⁰ 11.00' N. lat.) and Point Lobos, Monterey County (36⁰ 31.46' N. Lat.)". CDFW In-Season (headline "Recreational Anchovy Take Restrictions Lifted in Monterey Bay", dated November 17, 2026), separately: "The recreational "bait only" fishing restriction for northern anchovy in the Monterey Bay area has been lifted, after state health agencies determined northern anchovy no longer poses a human health risk. The restriction prohibiting the commercial distribution of northern anchovy seafood products for human consumption remains in effect." (Sources: CDPH list above; https://wildlife.ca.gov/Fishing/Ocean/Regulations/Inseason.) Relevance: only Pigeon Point/south San Mateo and south — not HMB/Pacifica.
- **Nearest active Dungeness domoic-acid advisory (far north).** Nov 9, 2026: "The California Department of Public Health (CDPH) is warning the public not to consume any part of sport-harvested Dungeness crab (meat or viscera), caught from an area of the Northern California coast due to dangerous levels of domoic acid." Area per CDFW declaration (https://nrm.dfg.ca.gov/FileHandler.ashx?DocumentID=247966&inline=): "…from the southern boundary of the Reading Rock State Marine Protected Areas (41⁰ 17.6' N. latitude) to the southern boundary of the Ten Mile State Marine Reserve (39⁰ 33.3' N. latitude)." (~200+ nautical miles north of Half Moon Bay.) CDFW closure: https://wildlife.ca.gov/News/Archive/additional-recreational-dungeness-crab-area-delay-in-portions-of-humboldt-county-due-to-public-health-hazard (Nov 5, 2026).
- **Standing guidance that DOES apply locally.** OEHHA memo, Oct 30, 2026: "For other sections of the coast that will be open for recreational harvesting of Dungeness crab, CDPH and OEHHA continue to strongly recommend that consumers avoid eating the viscera (internal organs, also known as “butter” or “guts”) because they usually contain much higher levels of domoic acid than the meat." (https://oehha.ca.gov/sites/default/files/media/2026-10/FINAL%20DungenessCrab_RecFisheryMemo_103026.pdf)
- **Other nearest non-local items on the list:** Monterey County bivalve warning Sept 14, 2026 → lifted Oct 12, 2026; Del Norte razor clam warning Oct 9, 2026; a San Luis Obispo County bivalve warning headline is present (date not extracted).

**Rule for the app:** treat "no active local CDPH advisory" as true only if the news list was fetched within the last 24 h and contains no 2026-dated release naming San Mateo/SF/Marin; always show the hotline number and a "last checked" timestamp.

#### 6d. CDPH ArcGIS layers — **NOT live status (static pins)**

The ArcGIS Feature Services behind the CDPH map were verified to *query* successfully but their **data is old**. `editingInfo` from the REST metadata (retrieved 2026-11-19):

| Layer | URL (…/arcgis/rest/services/…) | lastEditDate |
|-------|-------------------------------|--------------|
| "Health Advisory Symbols (Red)" | `services2.arcgis.com/wi1yEacfYjH5viqb/arcgis/rest/services/Health_Advisory_Symbols_(Red)/FeatureServer/0` | **2020-08-25** |
| "Areas" (service `California_Coastal_Counties`, layer 3) | `…/California_Coastal_Counties/FeatureServer/3` | **2020-08-26** |
| "Areas" (service `All_Bivalve_Shellfish_Health_Advisory_Special_Advisory`, layer 3) | `…/All_Bivalve_Shellfish_Health_Advisory_Special_Advisory/FeatureServer/3` | **2025-07-10** |

The "Health Advisory Symbols (Red)" layer has fields `County_Name`, `Latitude`, `Longitude` (no status or date field) and last edit **2020-08-25** — **static pins, not usable as live closure status**. The two other layers (both named "Areas") have fields incl. `TITLE`, `DESCRIPTION`, `DATE`, `TYPEID`, but last edits of 2020-08-26 and 2025-07-10, so neither reflects Nov 2026 events. (Feature counts and the CDPH web-map item modified date were not re-verified this round.) **Do not render a layer's presence as "advisory active".**

**Probe:** `scripts/research_probes/11_cdph_live.sh`  
**Verified on:** 2026-11-19 (15:57–16:05 PST)

---

### 7. California beach bacteria / water quality advisories

**Bottom line (verified 2026-11-19 ~15:59 PST):** SWRCB BeachWatch (data.ca.gov) is **not live** — it ends in 2026-03 — but **two county-level feeds ARE live and dated within 2 days**: San Francisco (DataSF Socrata API) and San Mateo (County Health posting pages + RSS/WP-JSON).

#### 7a. San Francisco — DataSF "Beach Water Quality Monitoring" (**LIVE, queryable JSON**)
- Dataset id **`v3fv-x3ux`**; landing https://data.sf.gov/d/v3fv-x3ux ; API base `https://data.sf.gov/resource/v3fv-x3ux.json` (`data.sfgov.org` 301-redirects here; use `curl -L`).
- Auth: none (Socrata app token optional for rate limits). Fields: `source` (station id), `sample_date`, `analyte`, `data` (string), `uniqueid`, `data_as_of`, `data_loaded_at`.
- **Freshness:** `max(sample_date)` = **2026-11-17**; `data_as_of` = 2026-11-18T23:01:59 ; 21,801 rows.
- Query examples (verified):  
  `https://data.sf.gov/resource/v3fv-x3ux.json?$where=sample_date>'2026-11-01'&$order=sample_date DESC&$limit=10` (URL-encode spaces)  
  `…?$select=source,max(sample_date) as last&$group=source&$order=last DESC&$limit=8`
- Real sample:
```json
{"source":"OCEAN#22_SL","sample_date":"2026-11-17T00:00:00.000","analyte":"ENTERO","data":"10","data_as_of":"2026-11-18T23:01:59.000"}
{"source":"BAY#320_SL","sample_date":"2026-11-17T00:00:00.000","analyte":"ENTERO","data":"2143"}
{"source":"BAY#202.4_SL","sample_date":"2026-11-17T00:00:00.000","analyte":"COLI_TOTAL","data":"<10"}
```
- Analytes: `ENTERO` (Enterococcus), `COLI_FECAL`, `COLI_TOTAL` (MPN/100 mL). **Quirks:** `data` is a **string** and may carry qualifiers (`<5`, `<10`); sorting `sample_date` uses the lowercase column name (`SampleDate` → error). No lat/lon in this dataset: **join `source` to BeachWatch station table** (`https://data.ca.gov/api/3/action/datastore_search?resource_id=98e628ff-d012-4982-ad32-b9f9ad8ab524&q=OCEAN%2322`) where `AgencyStationIdentifier` = `source`, e.g. `OCEAN#22_SL` → "Fort Funston", Ocean Beach, 37.71526, −122.50476; `BAY#301.2_SL` → "Jack Rabbit Beach", beach name Candlestick Point (both verified in the station table). (Station table is static — good for geometry.)
- **Thresholds (state single-sample maxima, as quoted by San Mateo County):** total coliform 10,000; E. coli 400; Enterococcus 104 MPN/100 mL (geometric mean limits 1,000 / 200 / 35). Apply to SF `ENTERO` 104 for a simple flag.
- Human-facing: SFPUC map https://webapps.sfpuc.org/sapps/beachesandbay.html (200; page text lists 877-SFBEACH / 877-732-3224); program page https://sfwater.org/index.aspx?page=87 (200).

#### 7b. San Mateo County Environmental Health (**LIVE, dated HTML + RSS**)
- Program page: https://smchealth.org/division/divisions/environmental-health-services/permits-business-services/water-protection-and-land-use/beach-creek-monitoring-program/ (200). Page states: "San Mateo County routinely tests 43 sites each week" and "Sites are sampled every Monday morning by a combination of County staff and volunteers, primarily associated with the local chapter of the Surfrider F[oundation]". Contact number on page: 650-372-6200 (County Environmental Health Services).
- **Posting pages are WordPress posts.** Latest (retrieved 2026-11-19): https://smchealth.org/8-27-beach-and-creek-updates/ — title "11/18/26 Beach and Creek Updates", "Posted on November 18, 2026 … based off samples collected November 16, 2026". (Slug is stale/reused; **discover the newest post by title/date, not slug**.)
- **Discovery:** `https://smchealth.org/wp-json/wp/v2/posts?search=Beach%20and%20Creek%20Updates&per_page=3&_fields=id,date,slug,link,title` → `[{"id":1964,"date":"2026-11-18T09:30:34","slug":"8-27-beach-and-creek-updates","link":"https://smchealth.org/8-27-beach-and-creek-updates/","title":{"rendered":"11/18/26 Beach and Creek Updates"}}]` (200); RSS `https://smchealth.org/feed/` (200, `application/rss+xml`) also lists these posts (pubDate Wed, 18 Nov 2026 17:30:34 +0000).
- **Structure:** headings `BEACH (PACIFIC-SIDE) POSTINGS:`, `CREEK POSTINGS:`, `BEACH (BAYSIDE) POSTINGS:` then one site per line. Quoted current list (11/18/26): Pacific-side — "Linda Mar #5 (Linda Mar Blvd.)", "Fitzgerald Marine Reserve", "Pillar Point #5 (Capistrano Beach)", "Pillar Point #7 (Surf-West Point Ave)", "Pillar Point #9 (Outer Harbor)", "Venice Beach"; creeks — San Pedro, San Vicente (at Fitzgerald), North Roosevelt, Gazos; Bayside — Aquatic Park, Kiteboard Beach, Oyster Point, Lakeshore Park, Erckenbrack Park, Gull Park, Marlin Park. **The list is POSTINGS (sites with elevated bacteria); a site absent from the list is "not posted", not necessarily "sampled and clean".**
- Interactive map service `https://gis.smcgov.org/maps2/rest/services/HEALTH/BEACH_MONITORING_PRJ/MapServer` → **HTTP 500 "Service … not started"** today (map backend down; do not depend on it).
- Older URL `smchealth.org/beach-monitoring` → 404 (replaced by the URL above).
- Latency: samples Monday → posting typically Tue/Wed; stated lag ≈ 2 days. Cadence weekly.

#### 7c. SWRCB BeachWatch (data.ca.gov) — **STALE; historical only**
Queried `datastore_search_sql` 2026-11-19 (max `SampleDate` in bacteria results): **San Mateo 2026-03-02**, **San Francisco 2025-10-28**, **Marin 2025-10-31**, all California **2026-03-05**; advisories table max `DateofAdvisory` **2026-03-06**. Use for station geometry and long-term history only. Resource IDs: advisories `d5cd6a23-829c-426d-a63e-689a55a3db9c`, bacteria `7bd961cf-abe4-433b-8033-378161237ff3`, stations `98e628ff-d012-4982-ad32-b9f9ad8ab524`.

#### 7d. Heal the Bay Beach Report Card / Surfrider BWTF
- `https://beachreportcard.org/` → 200 (HTML SPA); `https://beachreportcard.org/api/v1/locations` → 200 but **6,788 bytes of `text/html`** (a shell, not JSON — only this path tested); `https://api.healthebay.org/` → connection failed (curl code 000). **No machine-readable API confirmed** (not exhaustively searched). Report-card grades are seasonal/annual anyway.
- Surfrider Blue Water Task Force https://www.surfrider.org/programs/blue-water-task-force → 200 (program page; no queryable feed found). The San Mateo program page says its Monday sampling is done by County staff and volunteers "primarily associated with the local chapter of the Surfrider F[oundation]"; results are published via the County posts above.

**Recommended best-available stack:** SF = DataSF `v3fv-x3ux` (daily, JSON) ; San Mateo = County posting post (weekly, scrape via WP-JSON/RSS) ; both with a "sampled {date}, posted {date}" staleness caveat (typically 2–9 days old) and the rule "avoid ocean contact during and 3 days after storms; stay 300 ft from creek mouths/storm drains" (San Mateo County Health program page: "avoid swimming in ocean waters during and for three days after a storm. When swimming in ocean waters, stay at least 300 feet away from flowing storm drains and creek mouths."). Fall back to BeachWatch only as "no recent data".

**Probe:** `scripts/research_probes/12_beach_live.sh`  
**Verified on:** 2026-11-19 (15:59–16:05 PST)

---

### 8. Fires & smoke — NASA FIRMS + EONET

#### FIRMS
- **Key-free USA 24h CSVs (verified):**  
  - MODIS: `https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_USA_contiguous_and_Hawaii_24h.csv` (HTTP 200, hundreds of rows)  
  - NOAA-20 VIIRS: `https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv` (HTTP 200)  
  - Older Suomi-NPP path ending `SUOMI_VIIRS_C2_USA_...` returned **header-only** today — prefer NOAA-20 path.
- **Area API (needs key):**  
  `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{west},{south},{east},{north}/{day_range}`  
  Without key → `Invalid MAP_KEY.` (confirmed).  
  **Get key:** https://firms.modaps.eosdis.nasa.gov/api/map_key (free email registration).  
  **Rate limit (docs):** ~5000 transactions / 10 minutes; status URL `/mapserver/mapkey_status/?MAP_KEY=...`.

Filter CSV client-side to bbox e.g. lat 37–38.5, lon −123.5…−121.5.

#### EONET v3
```
https://eonet.gsfc.nasa.gov/api/v3/events?category=wildfires&status=open&limit=20&bbox=-123.5,37.0,-121.5,38.5
```
Returned 5 “open” events today, but geometries included older 2024-dated wildfires still marked open — **do not treat as hotspots**; use FIRMS for active heat, EONET for narrative context.

**Backup:** NOAA HMS smoke (separate GIS); AirNow PM2.5 (API key).

**Probe:** `scripts/research_probes/05_fires_uv_beach.sh`  
**Verified on:** 2026-11-19

---

### 9. UV & solar — NASA POWER (+ EPA UV backup)

**Primary:** `https://power.larc.nasa.gov/api/temporal/daily/point`

Example:
```
https://power.larc.nasa.gov/api/temporal/daily/point?parameters=ALLSKY_SFC_SW_DWN,T2M&community=RE&longitude=-122.47&latitude=37.81&start=20261101&end=20261118&format=JSON
```

**Auth:** None.

**Fill value:** `-999.0` (header `fill_value`).

**Latency (observed 2026-11-19):** For `ALLSKY_SFC_SW_DWN`, last valid day was **2026-11-14** when requesting through 2026-11-18 → about **4–5 days lag**. `ALLSKY_SFC_UV_INDEX` and `ALLSKY_SFC_UVB` returned **all −999** for recent windows — do **not** rely on POWER daily UV index for this point/parameter set until a working parameter is confirmed; use EPA for UV.

**Backup (near-real-time UV):** EPA Envirofacts hourly UV by ZIP — verified:
```
https://data.epa.gov/efservice/getEnvirofactsUVHOURLY/ZIP/94121/JSON
```
Sample: `{"ZIP":"94121","CITY":"San Francisco","DATE_TIME":"Nov/19/2026 12 PM","UV_VALUE":2}`

**Probe:** `scripts/research_probes/05_fires_uv_beach.sh`  
**Verified on:** 2026-11-19

---

### 10. Seasonal SST climatology / anomalies

**Primary (simplest for anomalies):** MUR anomaly product on CoastWatch ERDDAP  
- `jplMURSST41anom1day` — daily SST anomaly fv04.1, 0.01°  
- `jplMURSST41anommday` — monthly  

Example:
```
https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41anom1day.json?sstAnom[(last)][(37.5):1:(37.55)][(-122.55):1:(-122.5)]
```

**Real sample:** time `2026-11-17T09:00:00Z`, `sstAnom` ≈ **+5.2 °C** near 37.5 N, −122.55 W (landward nulls as `null`).

**Alternative climatology path:** OISST aggregates `ncdcOisst21Agg` / NRT `ncdcOisst21NrtAgg` (0.25°) — compute anomaly vs multi-year mean client-side if a dedicated climatology dataset is missing.

**Verified on:** 2026-11-19  
**Probe:** included in `04_erddap_sst_chl.py`

---

### 11. Sunrise / sunset / civil twilight (offline-calc check)

**Primary:** USNO Astronomical Applications API — Rise/Set/Transit one-day  
`https://aa.usno.navy.mil/api/rstt/oneday`

**Auth:** None.

**Example (Half Moon Bay, 2026-11-19, PST):**
```
https://aa.usno.navy.mil/api/rstt/oneday?date=2026-11-19&coords=37.5025,-122.4822&tz=-8&dst=false
```
Params: `date` (YYYY-MM-DD), `coords` as `lat,lon` (decimal), `tz` = offset hours from UTC (−8 for PST, −7 for PDT), `dst` true/false (document actual `properties.data.isdst` in response).

**Real sample (verified 2026-11-19):**
```json
"sundata": [
  {"phen": "Begin Civil Twilight", "time": "06:26  ST"},
  {"phen": "Rise", "time": "06:54  ST"},
  {"phen": "Upper Transit", "time": "11:55  ST"},
  {"phen": "Set", "time": "16:56  ST"},
  {"phen": "End Civil Twilight", "time": "17:25  ST"}
],
"tz": -8.0, "isdst": false, "curphase": "Waxing Gibbous"
```
Also returns moon rise/set/phase. Times labeled `ST`/`DT` relative to requested offset — **not** IANA zone IDs.

**Quirks:** Caller must pick correct `tz` for the date (PST vs PDT). Passing `dst=true` with `tz=-8` in November still yielded `isdst: false` and ST labels — trust the returned flag/times. Good for checking an offline NOAA/USNO algorithm implementation.

**Backup:** sunrise-sunset.org (no key):
```
https://api.sunrise-sunset.org/json?lat=37.5025&lng=-122.4822&date=2026-11-19&tzid=America/Los_Angeles
```
Verified same day: sunrise `6:54:05 AM`, sunset `4:56:40 PM`, civil twilight begin `6:26:03 AM`, end `5:24:43 PM` (`tzid` echoed). Without `tzid`, `formatted=0` returns UTC ISO timestamps. Slight second-level differences vs USNO are expected.

**NOAA Solar Calculator:** `https://gml.noaa.gov/grad/solcalc/` is a **browser JavaScript calculator** (HTML 200 confirmed). **No documented public REST endpoint** found for automated calls — use as human cross-check only, not as an API.

**Rate limits:** Be polite; these are public government/community APIs without published keys.

**Probe:** `scripts/research_probes/07_sunrise_sunset.sh`  
**Verified on:** 2026-11-19

---

## Part B — Domain rules (cited)

> Not legal advice. Seasons and closures change (whale entanglement RAMP, domoic acid). Re-check CDFW + CDPH on the day of use. **Checked against public sources on 2026-11-19.**

### B1. Clamming tides & spots (region)

- **Tide height:** Good recreational digs generally need **minus tides (≤ 0 ft MLLW)**; many local guides treat **≤ −0.5 ft** as “good” and **≤ −1.5 ft** as excellent exposure. Tidewindow’s Pillar Point scoring uses windows below ~+1.0 ft MLLW with better scores toward −2.0 ft (https://thetidewindow.com/beaches/ca/pillar-point-ca/) — useful UX heuristic, not a regulation.
- **Hours:** Daylight only — ½ hour before sunrise to ½ hour after sunset (14 CCR §29.20).
- **Spots often cited for cockles / clams:** protected flats **inside Half Moon Bay / Pillar Point Harbor** (north & south ends), **Tomales Bay** (e.g. west shore / state park areas), **Bodega Bay**, **Drakes / Estero** area subject to rules & advisories. Open high-energy surf beaches are poor clam habitat.
- **MPA caution:** **Montara SMR** — no take. **Pillar Point SMCA** — take of living marine resources generally prohibited except listed finfish/crab/squid methods (https://www.parks.ca.gov/?page_id=27716). Do **not** recommend clamming inside no-take MPAs / Fitzgerald tidepools.
- **Always:** CDPH advisory map + sport license.

### B2. CA crab & clam rules — verbatim CCR (retrieved 2026-11-19)

Source for all quotes unless noted: Cornell LII Cal. Code Regs. Title 14 (retrieval date **2026-11-19**).  
URLs: [§29.85](https://www.law.cornell.edu/regulations/california/14-CCR-29.85), [§29.80](https://www.law.cornell.edu/regulations/california/14-CCR-29.80), [§29.20](https://www.law.cornell.edu/regulations/california/14-CCR-29.20), [§29.25](https://www.law.cornell.edu/regulations/california/14-CCR-29.25), [§29.35](https://www.law.cornell.edu/regulations/california/14-CCR-29.35), [§29.40](https://www.law.cornell.edu/regulations/california/14-CCR-29.40).

#### §29.85 Crabs (excerpt)

> (a) Any individual who fishes for crabs using crab trap(s) pursuant to subsection 29.80(c), shall have in possession a valid Recreational Crab Trap Validation (Section 701, Title 14, CCR).  
> (b) Dungeness crabs (Cancer magister):  
> (1) Dungeness crab may not be taken from or possessed if taken from San Francisco Bay and San Pablo Bay, plus all their tidal bays, sloughs and estuaries between the Golden Gate Bridge and Carquinez Bridge.  
> (2) Open season: Fishing rules for Dungeness crab may be changed during the year or in-season by the director under the authority of subsection 29.80(c)(7). …  
> (A) Del Norte, Humboldt and Mendocino counties: From the first Saturday in November through July 30.  
> (B) All other counties: From the first Saturday in November through June 30.  
> (3) Limit: Ten.  
> (5) Minimum size: Five and three-quarter inches measured by the shortest distance through the body from edge of shell to edge of shell directly in front of and excluding the points (lateral spines).  
> (c) All crabs of the Cancer genus except Dungeness crabs, but including: yellow crabs, rock crabs, red crabs and slender crabs:  
> (1) Open season: All year. …  
> (2) Limit: Thirty-five.  
> (3) Minimum size: Four inches measured by the shortest distance through the body, from edge of shell to edge of shell at the widest part, except there is no minimum size in Fish and Game districts 8 and 9.

#### §29.80 Gear (selected excerpts)

> (b)(2) The owner or operator of a hoop net shall raise the hoop net to the surface and inspect the contents of the hoop net at intervals not to exceed 2 hours.  
> (b)(3) It is unlawful to abandon or leave unchecked a hoop net for more than 2 hours. …  
> (c)(1) Crab traps shall have at least two rigid circular openings of not less than four and one-quarter inches inside diameter so constructed that the lowest portion of each opening is no lower than five inches from the top of the trap.  
> (c)(5) Every crab trap shall be raised, cleaned, and emptied (serviced) at intervals not to exceed 9 days, weather conditions at sea permitting, and no crab trap shall be abandoned in the waters of this state.  
> (c)(6)(A) An individual shall not operate more than 10 deployed traps, except an individual may service up to 10 additional traps if the individual has in possession written permission from the operator(s) of the additional traps …  
> (e) Crab trap areas: Crab traps, including crab loop traps, may be used north of Point Arguello, Santa Barbara County, to take all species of crabs.

#### Clams

**§29.20 Clams General (excerpt):**

> (a) Except as provided in this article, there are no closed seasons, bag limits or size limits on saltwater clams.  
> (b) Fishing hours: one-half hour before sunrise to one-half hour after sunset.  
> (c) Gear restrictions. It shall be unlawful to use anything other than the following hand-operated devices to take clams: spades, shovels, hoes, forks, rakes, devices that use suction to remove clams commonly known as slurp guns or clam guns, or rigid pipes used to prevent the collapse of holes when digging for clams. It shall be unlawful to use any other device to take clams, including any hydraulic pump or other device capable of liquifying sand. …

**§29.25 Gaper Clams and Washington Clams (full body as published on LII):**

> Limit: Ten of each species, except in Humboldt Bay the limit is fifty in combination; however, no more than 25 gaper clams may be taken or possessed. In Elkhorn Slough the limit is twelve in combination. All gaper clams and Washington clams dug, regardless of size or broken condition, must be retained until the bag limit is reached. For purposes of this section, clams commonly termed horse clams or horseneck clams are gaper clams, not geoduck clams regulated pursuant to Section 29.30, Title 14, CCR.

**§29.35 Littleneck Clams, Soft-Shell Clams, Chiones, Northern Quahogs, and Cockles:**

> (a) Limit: Fifty in combination.  
> (b) Minimum size: One and one-half inches in greatest diameter, except there is no size limit for soft-shell clams. All soft-shell clams dug, regardless of size or broken condition, must be retained until the bag limit is reached.

**§29.40 Pismo Clams (excerpt):**

> (a) Open season: May be taken in Santa Cruz and Monterey counties September 1 through April 30. In all other counties, except in state marine reserves or other marine protected areas which prohibit the take of clams (see Section 632), Pismo clams may be taken at any time of the year.  
> (b) Limit: Ten.  
> (c) Minimum size: Five inches in greatest shell diameter north of the boundary between San Luis Obispo and Monterey counties; four and one-half inches in greatest shell diameter south of the boundary, between San Luis Obispo and Monterey counties.

#### 2026–27 recreational Dungeness season status (checked 2026-11-19)

- Nominal opener: **Saturday, Nov 7, 2026** (CDFW Recreational Dungeness Crab Regulations 2026–27 PDF, DocumentID=195690).  
- **Trap prohibition:** recreational crab **traps restricted** CA/OR border → Point Conception (Zones 1–5) until **at least Jan 1, 2027** (whale entanglement RAMP). Hoop nets / snares / hand still allowed where season is open.  
- **Domoic acid delay (north of TideWise core):** recreational take prohibited Reading Rock SMPA southern boundary (**41°17.6′ N**) → Ten Mile SMR southern boundary (**39°33.3′ N**) per CDFW in-season notices (expanded Nov 5, 2026). **HMB / Pacifica / SF ocean remain in the open area** under trap restriction (verify before messaging).  
- Sources: https://wildlife.ca.gov/News/Archive/recreational-dungeness-crab-fishing-begins-in-most-areas-nov-7-with-trap-restrictions-commercial-season-delayed ; https://wildlife.ca.gov/Fishing/Ocean/Regulations/Inseason

#### Gear allowed during trap restriction (2026–27, retrieved 2026-11-19 ~15:43 PST)

**Short answer (explicit in CDFW sources):** Yes — while the recreational **crab trap** restriction is in effect, CDFW says **hoop nets, crab snares (loop traps), and hand take** remain allowed in open areas. CDFW states the restriction covers **Fishing Zones 1–5** (California/Oregon border to Point Conception), i.e. **all** zones that include our coast. Restriction runs **until at least January 1, 2027**; next RAMP assessments listed as **Dec 15–18** and **Jan 13–15** (subject to change).

**Our zone (derived from CDFW zone boundaries quoted on the In-Season page):** *Fishing Zone 3* = "Sonoma/Mendocino county line, 38°46.125' N. Latitude to Pigeon Point, 37°11' N. Latitude" (In-Season entry May 15, 2026) → covers **Marin, SF, and San Mateo coast down to Pigeon Point**. *Fishing Zone 4* = "Pigeon Point, 37°11' N Latitude to Point Conception, 34°27' N Latitude" (In-Season entry March 13, 2026) → Año Nuevo/Santa Cruz southward. The *mapping of our spots to Zone 3 is my reading of those latitudes*; the formal zone definitions are in 14 CCR §132.8(a)(7) (not fetched here). SF Bay / San Pablo Bay: no Dungeness may be taken at all (§29.85(b)(1)).

**Verbatim quotes**

1. CDFW news release, Oct 30, 2026 — https://wildlife.ca.gov/News/Archive/recreational-dungeness-crab-fishing-begins-in-most-areas-nov-7-with-trap-restrictions-commercial-season-delayed (retrieved 2026-11-19):
   > "The use of recreational crab traps will be restricted (PDF) from the California/Oregon border to Point Conception (34° 27' N latitude, Fishing Zones 1-5) until at least January 1, 2027, due to the number of confirmed entanglements this year and high abundance of humpback whales across the fishing grounds."
   > "The trap restriction does not affect the use of hoop nets and crab snares (loop traps), and CDFW reminds anglers that all hoop nets must be serviced every two hours and cannot be left unattended for longer periods."

2. CDFW Whale Safe Fisheries / RAMP page — https://wildlife.ca.gov/Conservation/Marine/Whale-Safe-Fisheries (retrieved 2026-11-19):
   > "The season opened to hoop net and loop trap fishing on Saturday, November 7, 2026. Crab traps are prohibited until at least January 1, 2027."
   > "A temporary crab trap prohibition is also implemented in Fishing Zones 1-5, and a Fleet Advisory for Fishing Zones 1-5 has been issued until at least January 1, 2027."

3. CDFW In-Season Ocean Fishing Regulation Changes, Oct 30, 2026 entry — https://wildlife.ca.gov/Fishing/Ocean/Regulations/Inseason (retrieved 2026-11-19):
   > "In coastal waters that are not closed due to a domoic acid advisory, the recreational Dungeness crab season will open on Nov. 7 under a trap prohibition. Only hoop nets, loop traps, or the hands may be used to capture crab."

4. CDFW "Recreational Dungeness Crab Regulations 2026-27" PDF (updated Oct 29, 2026) — https://nrm.dfg.ca.gov/FileHandler.ashx?DocumentID=195690 (retrieved 2026-11-19), Gear Type column:
   > "Taken by hand, crab trap, hoop net, or by crab snare … When crab traps are restricted due to entanglement risk, take by hand, hoop net, or crab snare with up to 6 loops elevated is allowed."
   (Text extraction of the table is garbled; the sentence above is as extracted.)

5. CDFW "Summary of Northern California Hoop Net Regulations" (effective Jan 1, 2026) — https://nrm.dfg.ca.gov/FileHandler.ashx?DocumentID=195608 (retrieved 2026-11-19 via search excerpt):
   > "Hoop Net Allowance: unlimited"
   > "Except on public piers, you cannot use more than two (2) rods and lines, two (2) hand lines, or two (2) nets, traps or other legal devices (including hoop nets) to take crabs."
   > "Service Interval (statewide): Hoop nets must be serviced every 2 hours; it is unlawful to abandon or leave unchecked a hoop net for more than 2 hours."
   ⚠ These two bullets look inconsistent on their face ("unlimited" vs. "two … nets … (including hoop nets)"); the sources do not reconcile them in what I read. **Treat the per-person hoop-net count as unconfirmed** — see 14 CCR §29.80(b)(4)(B) below and re-read the PDF before showing a number.

6. 14 CCR §29.80 (Cornell LII, https://www.law.cornell.edu/regulations/california/14-CCR-29.80, retrieved 2026-11-19):
   > "(b) Hoop nets. Hoop nets may be used to take spiny lobsters and all species of crabs."
   > "(b)(2) The owner or operator of a hoop net shall raise the hoop net to the surface and inspect the contents of the hoop net at intervals not to exceed 2 hours."
   > "(b)(4)(B) North of Point Arguello to the California-Oregon border, there is no limit on the number of hoop nets that may be possessed or deployed."
   > "(c)(7)(B)2. Recreational Dungeness crab season delay and continuation of the crab trap prohibition specified in subsection 29.80(c)(4), whereby the director shall prohibit the deployment and use of recreational crab traps until new data indicates the numerical triggers … are no longer met …"
   > "(c)(7)(C) Recreational management action may be implemented statewide or by fishing zone(s) (as defined in subsections 132.8(a)(7)(A)-(G)), if the director demonstrates less-than-statewide action protects humpback whales, blue whales, and/or Pacific leatherback sea turtles based on best available science."
   > "(d) Crab loop traps may have up to six loops."
   > "(e) Crab trap areas: Crab traps, including crab loop traps, may be used north of Point Arguello, Santa Barbara County, to take all species of crabs."

7. 14 CCR §29.85 (Cornell LII, https://www.law.cornell.edu/regulations/california/14-CCR-29.85, retrieved 2026-11-19):
   > "(a) Any individual who fishes for crabs using crab trap(s) pursuant to subsection 29.80(c), shall have in possession a valid Recreational Crab Trap Validation (Section 701, Title 14, CCR)."
   > "(b)(3) Limit: Ten."
   > "(b)(5) Minimum size: Five and three-quarter inches …"

**What the sources do NOT say (not inferred):**
- **Zone differences / depth:** The current-season sources above state the recreational trap restriction applies **uniformly to Zones 1–5**; I found **no recreational depth restriction** for hoop nets or snares. The "30-fathom Depth Constraint" appearing on the RAMP page refers to the **commercial** fishery in Zones 1–2 (earlier 2026 assessments), not recreational gear in our zone.
- **Statutory wording tension:** §29.80(e) calls loop traps "crab traps" ("Crab traps, including crab loop traps…"), while CDFW's 2026–27 announcements explicitly say crab snares/**loop traps** are **allowed** during the restriction. CDFW's public statements are explicit; I did not find a regulation sentence that resolves the definitional overlap. Engineers should follow CDFW's explicit announcement wording and link to it, and flag for human/legal review.
- **PDF quote caveat:** quote 4 comes from extracted PDF text (table layout garbled); verify against the PDF before copying verbatim into UI.
- **Pier crabbing, rock crab under restriction:** not addressed in these sources for this restriction.

**License:** https://wildlife.ca.gov/Licensing/Fishing

### B3. Crabbing tides / currents / moon

- **Practical:** Many SF/Pacifica crabbers prefer **slack or weaker current** for gear handling near the Gate/bar; strong ebb against west swell is hazardous (NWS explicitly warns bar breakers on ebb).  
- **Moon / spring tides:** Larger tidal ranges near new/full moon → stronger currents; folk wisdom says “fish the tides,” but **no peer-reviewed “always best on X moon” rule** found for Dungeness catch rate suitable as app truth. **Mark as folk wisdom** if shown. Prefer: open season + health clearance + safe sea state + slack windows from CO-OPS current predictions.

### B4. Wind & wave thresholds — small-boat sailing

- **NWS Western SCA:** 21–33 kt sustained and/or **seas > 10 ft** (https://www.weather.gov/marine/cwd). Treat active SCA / Hazardous Seas as “not for beginners.”  
- **SF Bay practice (sailing schools / operators):** introductory lessons often target roughly **5–15 kt**; summer seabreezes frequently **15–25+ kt** in central Bay slots (Modern Sailing / local PDFs). Beginners: stay **≤ ~15–18 kt** and avoid Gate ebb+swell. Experienced small keelboats often OK into low-20s kt with reefs; match to boat/crew.  
- **Ocean (PZZ545):** Today’s forecast seas **8–12 ft** with SCA — unsuitable for small open boats regardless of wind skill.

### B5. Swimming safety thresholds

- **Water temp / cold shock** (National Center for Cold Water Safety https://www.coldwatersafety.org/water-temperature-safety-guide; also NWS cold water safety):  
  - < 70°F: caution  
  - 50–60°F: max cold-shock / immediately life-threatening for unprotected immersion  
  - SF ocean WTMP today ~ **17–19°C (63–66°F)** at nearby buoys — still cold-shock territory without wetsuits.  
- **Rip currents:** Use NWS **Surf Zone Forecast** risk language + Beach Hazards Statement. Low/moderate/high rip risk; swim near lifeguards; never rely on wave height alone (long-period swell can rip on “small” faces).  
- **Wave height:** No single national “safe swim Ht” — combine SRF surf height, local lifeguard closure, and BeachWatch bacteria postings.

### B6. Named spots (8–15) — lat/lon, activities, shoreline orientation

Orientation = **approximate direction the shore faces toward open water** (degrees from north, clockwise), estimated from coastline geometry / map inspection — **±15–30°**, not a survey.

| Spot | Lat | Lon | Activities | Facing (approx) | Notes |
|------|-----|-----|------------|-----------------|-------|
| Pillar Point Harbor / Princeton | 37.502 | −122.487 | Clam (harbor flats), crab (boat), sail (harbor) | 180° (harbor mouth S) | Check SMCA boundaries before take |
| Half Moon Bay State Beach (Miramar–Francis) | 37.473 | −122.435 | Surf swim (advanced), beach | 270° W | Exposed surf |
| Montara / Fitzgerald (viewing) | 37.524 | −122.517 | Tidepool **view only** | 270° W | SMR — no take |
| Pacifica State Beach (Linda Mar) | 37.600 | −122.505 | Surf swim, beach | 250° WSW | BeachWatch stations present |
| Rockaway Beach (Pacifica) | 37.609 | −122.499 | Surf | 260° W | |
| Ocean Beach (SF) | 37.759 | −122.512 | Surf (experts), beach | 270° W | Strong rip / heavy surf common |
| Baker Beach | 37.793 | −122.484 | Beach, limited swim | 250° WSW | Currents; Gate proximity |
| Crissy Field / SF waterfront | 37.804 | −122.466 | Sail, windsurf, stroll | 10° N | Bay side; look to Gate |
| Aquatic Park / Muni Pier | 37.807 | −122.424 | Swim (club), kayak | 350° N | Protected cove |
| Angel Island (Ayala Cove) | 37.868 | −122.435 | Sail stop, hike | 320° NW (cove) | Ferry access |
| Berkeley Marina / Cesar Chavez Park | 37.863 | −122.318 | Sail, boardsport | 270° W (into Bay) | |
| Richardson Bay / Sausalito | 37.856 | −122.478 | Sail (shelter) | 90° E | More protected |
| Drakes Beach (Point Reyes) | 38.027 | −122.964 | Beach, clam **if legal/advised** | 180° S | Check CDPH + NPS rules |
| Tomales Bay (Inverness shore) | 38.113 | −122.870 | Clam, kayak, calm sail | 90° E (east-facing west shore) | Classic cockle area |
| Bodega Harbor mouth | 38.309 | −123.058 | Clam, crab, sail | 200° SSW | Just N of core box but relevant |

---

## Risks & Unverified

| Item | Status (as of 2026-11-19) |
|------|--------|
| **C-HARM ERDDAP datasets** | **FLAPPING + ~17 days STALE** — 404 ~15:35–15:45 PST, 200 from ~15:50, 5/5 timed 200s at 15:57–15:58, a 23 s response and three 503s at 16:02–16:03, 200 at 16:04. Data end **2026-11-02T12:00Z** (0day). Not DOWN, but not current. See §5b. |
| **NASA PACE chlorophyll on ERDDAP** | **Still not found** on CoastWatch / OceanWatch / PolarWatch. CMR lists `PACE_OCI_L3M_BGC` etc. via Earthdata only. |
| POWER `ALLSKY_SFC_UV_INDEX` / `UVB` for SF daily | All fill (−999) — use EPA UV instead |
| Heal the Bay / Beach Report Card API | No JSON API confirmed (`/api/v1/locations` returns an HTML shell; `api.healthebay.org` unreachable) — not exhaustively searched |
| BeachWatch (SWRCB) freshness | **Ended**: San Mateo max sample 2026-03-02, SF 2025-10-28, Marin 2025-10-31, CA-wide 2026-03-05. Use DataSF (SF) and County posts (San Mateo) instead — §7 |
| SF / San Mateo beach live feeds | **Live**: DataSF `v3fv-x3ux` (latest sample 2026-11-17) and San Mateo post "11/18/26 Beach and Creek Updates". Caveats: SF `data` is a string with qualifiers and has no lat/lon (join station table); San Mateo list = postings only, scraped HTML; County GIS MapServer returns 500 "not started"; Marin not investigated |
| FIRMS area API with live MAP_KEY | Not exercised (no key); CSV feeds OK |
| NOAA Solar Calculator REST | **None** — JS page only |
| Rock crab / hoop-net full §29.80 text | Partial excerpts quoted; full section is long — keep LII link |
| 2026–27 crab trap / DA zones | Live as of Nov 19 notes above — **re-check CDFW in-season page before every release** |
| Hoop-net per-person count during trap restriction | CDFW hoop-net summary says both “unlimited” and “two … nets … (including hoop nets)”; **unreconciled** — don't hard-code a number |
| Loop traps/snares vs “crab traps” wording | CDFW announcements say allowed; §29.80(e) groups loop traps with “crab traps” — **no reconciling sentence found** |
| Zone 3 mapping for our coast | Derived from CDFW latitude boundaries (Zone 3: 38°46.125′→37°11′ N); §132.8(a)(7) not fetched |
| EONET “open” wildfires | May include stale events |
| CDPH TLS | `www.cdph.ca.gov` serves wrong/missing intermediate (R36) → strict verify fails; workaround in §6b; leaf expires 2026-12-31 |
| CDPH live status | No API/RSS (NR_RSS 404, GovDelivery 404). Only scrape of the dated news list + hotline (800) 553-4133. ArcGIS layers are static (last edits 2020-08-25 / 2020-08-26 / 2025-07-10). Domoic-acid crab results page: no data table found in HTML |
| CDPH list scrape | Page mixes 2026 items with archive lists (2016/2017); only trust items with a 2026 date. SLO County bivalve warning headline present; date not extracted |
| Real-time Golden Gate current meter | Not in `type=currents` region list today |
| Water temperature at 9414290 | No data earlier today |
| Shoreline orientation angles | Approximate |
| AirNow / HMS smoke | Not deeply probed |

---

## Probe scripts

| Script | Covers |
|--------|--------|
| `scripts/research_probes/01_coops_tides.sh` | CO-OPS metadata + datagetter |
| `scripts/research_probes/02_ndbc_buoys.sh` | NDBC realtime2 + spectral |
| `scripts/research_probes/03_nws_weather.sh` | points, alerts, PZZ545, SRF |
| `scripts/research_probes/04_erddap_sst_chl.py` | MUR, VIIRS chl, C-HARM (when up), MUR anom |
| `scripts/research_probes/05_fires_uv_beach.sh` | FIRMS, EONET, POWER, EPA UV, BeachWatch |
| `scripts/research_probes/06_cdph_shellfish.sh` | CDPH pages + ArcGIS layers |
| `scripts/research_probes/07_sunrise_sunset.sh` | USNO + sunrise-sunset.org |
| `scripts/research_probes/08_charm_status.py` | C-HARM dataset presence check + timed repeat probes + data age |
| `scripts/research_probes/11_cdph_live.sh` | CDPH news list headlines/dates, TLS diagnosis + R36 workaround, ArcGIS lastEditDate |
| `scripts/research_probes/12_beach_live.sh` | DataSF v3fv-x3ux, San Mateo WP-JSON/RSS + latest post, BeachWatch max dates |

Optional env: `FIRMS_MAP_KEY` for area API; `UA` to override User-Agent; `LAT`/`LON`/`DATE`/`TZOFF` for sunrise probe.

---

*End of DATA_SOURCES.md — TideWise research, verified/updated 2026-11-19.*
