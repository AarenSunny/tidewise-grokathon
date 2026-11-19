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

**Real sample:** time `2026-11-09T00:00:00Z`, `chla` ≈ 1.7–2.4 mg m^-3 near 37.60 N, −122.60 W.

**Latency:** 8-day composite `(last)` was ~10 days behind “today” on 2026-11-19 — cloudy CA coast often gaps daily fields; prefer 3- or 8-day.

**PACE:** No dedicated “PACE chlorophyll” dataset showed up in CoastWatch search today (MODIS/SeaWiFS/VIIRS hits only). Treat PACE as **unverified here**; revisit NASA Ocean Color / future CoastWatch ingest.

#### 5b. C-HARM (Pseudo-nitzschia / domoic acid probability)

**Primary (v3.1 nowcast):** `wvcharmV3_0day`  
Forecasts: `wvcharmV3_1day`, `_2day`, `_3day` (also `*_LonPM180` variants).  
Info: `https://coastwatch.pfeg.noaa.gov/erddap/info/wvcharmV3_0day/index.html`

**Critical quirk:** longitude axis is **0–360** (min ≈ 232.5), **not** −180–180. Use `237.3` for −122.7° E.

**Variables + thresholds (from attributes / HABMAP):**
| Variable | Meaning |
|----------|---------|
| `pseudo_nitzschia` | P(Pseudo-nitzschia **> 10,000 cells/L**) |
| `particulate_domoic` | P(particulate DA **> 500 ng/L**) |
| `cellular_domoic` | P(cellular DA **> 10 pg/cell**) |

`_FillValue` = −99999.0 (JSON may show `null`).

**Bloom threshold to use in-app (cited):** **10,000 cells/L** Pseudo-nitzschia as C-HARM’s bloom cutoff (Trainer & Suddleson 2005; Lane et al. 2009; Anderson et al. — summarized at https://calhabmap.org/hab-forecast). Interpret model output as **probability**, not cell count. For UI alerts, consider highlighting pixels with P ≳ 0.5–0.7 **and** confirming against CDPH advisories (section 6) — never open harvest on model alone.

**Real sample:** `(last)` returned **2026-11-02T12:00:00Z** with P ≈ 0.70–0.88 near 37.39 N, 237.3 E — i.e. multi-day staleness possible; check `time` every call.

**Backup:** SCCOOS/CenCOOS HABMAP pages; CDPH biotoxin line (human health source of truth).

**Probe:** `scripts/research_probes/04_erddap_sst_chl.py`  
**Verified on:** 2026-11-19

---

### 6. CDPH shellfish / biotoxin closures & advisories

**No stable public REST “advisory status” API** found. Best sources:

1. **News / advisory index (scrapable HTML):**  
   https://www.cdph.ca.gov/Programs/OPA/Pages/Shellfish-Advisories.aspx  
2. **Annual mussel quarantine explainer:**  
   https://www.cdph.ca.gov/Programs/CEH/DRSEM/Pages/EMB/Shellfish/Annual-Mussel-Quarantine.aspx  
   - Normal window: **May 1 – Oct 31** (sport mussels only).  
   - On 2026-11-19 research: quarantine lifted end of day **2026-10-31** (CDPH release 2026-10-28). Localized advisories can remain.
3. **Marine Biotoxin Monitoring Program:**  
   https://www.cdph.ca.gov/Programs/CEH/DRSEM/Pages/EMB/Shellfish/Marine-Biotoxin-Monitoring-Program.aspx  
4. **Phone:** Shellfish Information Line **1-800-553-4133** (recorded).
5. **Interactive map (Experience Builder):**  
   https://experience.arcgis.com/experience/394836318cfe4f7494e1c09097a43559/  
6. **ArcGIS Feature Services** (queryable; verified):  
   - Special advisory polygons:  
     `https://services2.arcgis.com/wi1yEacfYjH5viqb/arcgis/rest/services/All_Bivalve_Shellfish_Health_Advisory_Special_Advisory/FeatureServer/3`  
     Fields: `TITLE`, `VISIBLE`, `DESCRIPTION`, `DATE`, …  
     Example feature today: `Special Advisory Area - Northern Channel Islands` (`VISIBLE=1`).  
   - County advisory symbol points:  
     `.../Health_Advisory_Symbols_(Red)/FeatureServer/0`  
     Fields: `County_Name`, `Latitude`, `Longitude` (21 counties returned; includes San Francisco, San Mateo, Marin…).  
   - Related layers listed in webmap `ad52187023f24b09b073d287f656df14` (mussel quarantine export, razor clam boundaries, etc.).

**Auth:** None for public FeatureServer queries.

**Update:** Event-driven press releases + map edits; not a fixed interval. **Always re-query** before recommending harvest.

**TLS quirk:** `cdph.ca.gov` failed strict certificate verify in this environment (`curl` exit 60); succeeded with `curl -k`. Engineering should use a normal CA bundle in production and treat `-k` as probe-only.

**Structure for scrapers:** SharePoint-style pages with dated news items (title + month/day/year + body mentioning counties / lat bounds). Prefer ArcGIS layers + official news list over brittle HTML.

**Domoic acid / crab:** CDPH Domoic Acid page + CDFW health advisories; Oct 30, 2026 release warned against sport Dungeness from one Northern CA coastal area (outside core HMB–SF focus, but check before northern trips).

**Backup:** County environmental health postings; CDFW Marine Region news https://wildlife.ca.gov/Regions/Marine

**Probe:** `scripts/research_probes/06_cdph_shellfish.sh`  
**Verified on:** 2026-11-19

---

### 7. California beach bacteria / water quality advisories

**Primary statewide (queryable):** California Open Data — Beach Watch package  
`https://data.ca.gov/dataset/beach-water-quality-postings-and-closures`  
CKAN API: `https://data.ca.gov/api/3/action/package_show?id=beach-water-quality-postings-and-closures`  
Metadata modified **2026-10-13** (not necessarily row-level freshness).

**Datastore resource IDs verified:**

| Resource | ID | Notes |
|----------|-----|------|
| Beach Posting and Closures – Advisories | `d5cd6a23-829c-426d-a63e-689a55a3db9c` | 35,748 rows; fields include `DateofAdvisory`, `AdvisoryType`, `AdvisoryCause`, `Description`, `DescriptionofArea`, … |
| Beach Water Quality Monitoring Results – Bacteria | `7bd961cf-abe4-433b-8033-378161237ff3` | 88,728+ rows; `Parameter` (e.g. Total Coliforms), `Result`, `Unit` (MPN/100ml), `County`, `SampleDate` |
| Monitoring Stations | `98e628ff-d012-4982-ad32-b9f9ad8ab524` | e.g. Pacifica “Linda Mar Beach #7” 37.5976, −122.5047; County San Mateo; agency San Mateo EH |

Example:
```
https://data.ca.gov/api/3/action/datastore_search?resource_id=7bd961cf-abe4-433b-8033-378161237ff3&limit=3&q=San%20Mateo
```

**Local backups / supplements:**
- San Mateo County Environmental Health beach monitoring (HTML; redirects — confirm current URL in browser).
- SF beach water quality reports on sf.gov (URL pattern `/reports/{month}-{year}/beach-water-quality` — verify month).
- Heal the Bay Beach Report Card: public site exists; **`api.healthebay.org` TLS failed** in this environment today → treat any HTB API as **unverified**.

**Gotchas:** BeachWatch historical bulk is excellent for trends; for **same-day swim decisions**, prefer county EH + NWS Beach Hazards / SRF. Field names are mixed Case (`DateofAdvisory`).

**Probe:** `scripts/research_probes/05_fires_uv_beach.sh`  
**Verified on:** 2026-11-19

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

## Part B — Domain rules (cited)

> Not legal advice. Seasons and closures change (whale entanglement RAMP, domoic acid). Re-check CDFW + CDPH on the day of use. **Checked against public sources on 2026-11-19.**

### B1. Clamming tides & spots (region)

- **Tide height:** Good recreational digs generally need **minus tides (≤ 0 ft MLLW)**; many local guides treat **≤ −0.5 ft** as “good” and **≤ −1.5 ft** as excellent exposure. Tidewindow’s Pillar Point scoring uses windows below ~+1.0 ft MLLW with better scores toward −2.0 ft (https://thetidewindow.com/beaches/ca/pillar-point-ca/) — useful UX heuristic, not a regulation.
- **Hours:** Daylight only — ½ hour before sunrise to ½ hour after sunset (14 CCR §29.20).
- **Spots often cited for cockles / clams:** protected flats **inside Half Moon Bay / Pillar Point Harbor** (north & south ends), **Tomales Bay** (e.g. west shore / state park areas), **Bodega Bay**, **Drakes / Estero** area subject to rules & advisories. Open high-energy surf beaches are poor clam habitat.
- **MPA caution:** **Montara SMR** — no take. **Pillar Point SMCA** — take of living marine resources generally prohibited except listed finfish/crab/squid methods (https://www.parks.ca.gov/?page_id=27716). Do **not** recommend clamming inside no-take MPAs / Fitzgerald tidepools.
- **Always:** CDPH advisory map + sport license.

### B2. CA crab & clam rules (high level)

**Dungeness crab (recreational)** — 14 CCR §29.85 / CDFW summaries:
- Season (nominal): first Saturday in November → **June 30** (central) / **July 30** (Del Norte–Mendocino).  
- For **2026–27** CDFW flyer: opens **Saturday Nov 7, 2026** (confirm PDF DocumentID=195690 on wildlife.ca.gov). Prior year (2025–26) had northern domoic delays & trap restrictions — expect in-season RAMP/health changes.
- Bag: **10** crabs; min size **5¾ in** (carapace, excluding spines).  
- **No Dungeness** from SF Bay / San Pablo Bay between Golden Gate and Carquinez.  
- License: CA sport fishing license; **crab trap validation** required to use traps (~$2.98 in 2025/26 fee tables). Hoop nets/snares have separate gear rules; hoop nets must be tended (recent rules: service intervals).

**Rock crab:** Different section/limits — verify current §29.85 subsections before implementing (not fully re-probed line-by-line today).

**Clams:**
- General §29.20: no universal closed season; species-specific limits apply.  
- **Cockles / littlenecks etc. (§29.35):** commonly **50 in combination**, **1½ in** minimum (confirm text before ship).  
- **Gaper / Washington (§29.25):** low bag (order of **10/species**, aggregate caps — confirm exact CCR text before ship).  
- Hand tools only; no hydraulic pumps.

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

| Item | Status |
|------|--------|
| NASA PACE chlorophyll on CoastWatch | **Not found** in search today |
| POWER `ALLSKY_SFC_UV_INDEX` / `UVB` for SF daily | Returned all fill (−999) — **unverified as usable** |
| Heal the Bay API | TLS failure — **unverified** |
| FIRMS area API with live MAP_KEY | Not exercised (no key in env); CSV feeds OK |
| Exact CCR text for §29.25 / §29.35 bag numbers | Summarized from secondary sources / search; **re-read CCR before shipping limits UI** |
| Rock crab recreational limits | Not fully expanded here |
| 2026–27 in-season crab trap closures / DA zones | Change quickly — **must live-check CDFW** |
| C-HARM `(last)` age | Can be days old (saw 2026-11-02 on 2026-11-19) |
| EONET “open” wildfires | May include stale events |
| CDPH TLS | Certificate issues from some runtimes |
| Real-time Golden Gate current meter | Not in today’s `type=currents` region list — predictions only via harmonic stations |
| Water temperature product at 9414290 | No data today |
| Shoreline orientation angles | Approximate |
| AirNow / HMS smoke polygons | Not probed in depth |

---

## Probe scripts

| Script | Covers |
|--------|--------|
| `scripts/research_probes/01_coops_tides.sh` | CO-OPS metadata + datagetter |
| `scripts/research_probes/02_ndbc_buoys.sh` | NDBC realtime2 + spectral |
| `scripts/research_probes/03_nws_weather.sh` | points, alerts, PZZ545, SRF |
| `scripts/research_probes/04_erddap_sst_chl.py` | MUR, VIIRS chl, C-HARM, MUR anom |
| `scripts/research_probes/05_fires_uv_beach.sh` | FIRMS, EONET, POWER, EPA UV, BeachWatch |
| `scripts/research_probes/06_cdph_shellfish.sh` | CDPH pages + ArcGIS layers |

Optional env: `FIRMS_MAP_KEY` for area API; `UA` to override User-Agent.

---

*End of DATA_SOURCES.md — generated for TideWise research session, verified 2026-11-19.*
