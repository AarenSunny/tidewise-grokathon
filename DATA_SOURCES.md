# TideWise DATA_SOURCES

Verified live on **2026-11-19** (America/Los_Angeles). Accuracy over coverage: every primary URL below was called today; field names and snippets are from real responses. Probe scripts: `scripts/research_probes/`.

Team note: **NOAA CoastWatch ERDDAP SST (`jplMURSST41`) and chlorophyll-a (`erdVHNchla*`) are the core space data.** Chlorophyll spikes / C-HARM HAB probabilities are early-warning inputs; **CDPH/CDFW advisories remain the legal safety gate for clam beds.**

---

## Recommended API stack

| Need | Primary (why) | Backup | Avoid |
|------|---------------|--------|-------|
| 1. Tides / levels / currents | **NOAA CO-OPS** `api.tidesandcurrents.noaa.gov` — official MLLW predictions + observed levels + SF Bay current predictions; no key | NDBC `FTPC1`/`AAMC1` for wind-only; no good tide backup | Commercial tide libs that invent stations; station `9414805` (no predictions today) |
| 2. Buoy waves / wind / WTMP | **NDBC** `realtime2/{id}.txt` (+ `.spec` for swell) — free, no key, MM sentinels documented | CO-OPS wind/water_temp at `9414750`/`9414863`; CDIP via NDBC IDs `46237`/`46214` | Assuming every buoy has WVHT (46026 often MM on latest hour) |
| 3. Weather / marine alerts | **NWS** `api.weather.gov` (gridpoints MTR + `alerts/active` + products `SRF`/`CWF`) — free, UA required | Open-Meteo (**unverified**, not called) | Scraping weather.com; using grid `waveHeight` alone for ocean surf (often inland null) |
| 4. Satellite SST | **CoastWatch ERDDAP** `jplMURSST41` (`analysed_sst`) — 0.01°, daily MUR | OceanWatch `goes-poes-1d-ghrsst-RAN` (0.05°, Kelvin); PODAAC CMR list (download needs Earthdata) | `coastwatch.noaa.gov` / `polarwatch` (HTTP **502** today); nearshore MUR pixels → **NaN** |
| 5. Chlorophyll / HAB | **ERDDAP** `erdVHNchla8day` (`chla`) + **C-HARM** `wvcharmV3_0day` (probabilities) | `erdVHNchla1day` (cloudy → NaN); OceanWatch `noaa_snpp_chla_daily` | Treating satellite chl alone as a closure; PACE not found as a clean ERDDAP dataset today |
| 6. Shellfish / biotoxin closures | **CDPH** Shellfish Advisories HTML + ArcGIS map; **CDFW** Health Advisories HTML | CDPH info line (800) 553-4133; CDFW Domoic Acid Closure line (831) 649-2883 | Invented CDPH JSON API (none found) |
| 7. Beach bacteria | **DataSF** Socrata `v3fv-x3ux` (SF ENTERO) + county posting pages | BeachWatch UI (no clean JSON API verified); CA Open Data archive is historical | EPA BEACON as a live API (no clean API; lead held) |
| 8. Fires / smoke | **NASA EONET** v3 events (bbox) — no key | **NASA FIRMS** area CSV (needs free MAP_KEY) | Treating multi-year-old EONET “open” wildfires as active smoke without FIRMS |
| 9. UV / solar | **EPA Envirofacts** UV daily/hourly by ZIP — live, no key | NASA POWER daily (`ALLSKY_SFC_SW_DWN`, `T2M`); POWER UV was all fill today | POWER as a marine product (no ocean fields; ~2–5 day lag on radiation) |
| 10. SST climatology / anomaly | **ERDDAP** `jplMURSST41anom1day` + `jplMURSST41clim` (`mean_sst`) | `jplMURSST42` `sst_anomaly` (0.25°, Kelvin) | Computing anomaly from a single buoy without a climatology |

**Keys the team must sign up for:** NASA FIRMS MAP_KEY (free). Optional: NASA Earthdata for PODAAC MUR NetCDF if ERDDAP is down. Everything else verified today needs **no key** (send an identifying `User-Agent` to NWS).

---

## Hard safety-gate feeds

Gates run **before** scoring. A gate that fires forces **UNSAFE**, **CLOSED**, or **UNKNOWN** as specified. Cached / snapshot policy is below.

### Policy (activity × feed + UNKNOWN / snapshot / cache)

1. **UNKNOWN** only when a **live, API-backed** safety feed that the **activity needs** fails or is stale (NWS alerts; CO-OPS/NDBC when that activity needs them for the gate). Do **not** force UNKNOWN just because a scrape-only source is hard to refresh.
2. **No-clean-API sources** (CDPH shellfish advisories/quarantines, CDFW Dungeness/domoic status, Bay Area county beach bacteria postings, NWS rip-current **text** if parsing fails): keep a **stored snapshot** with `last_verified`. Still show the score plus a caveat like `Check CDPH advisory, last verified <date>`. If the snapshot itself shows a **closure or exceedance**, still force **CLOSED** or **UNSAFE**.
3. **Per-activity required safety feeds**

| Activity | NWS alerts (API) | CO-OPS/NDBC (API) | CDPH/CDFW biotoxin (snapshot OK) | Beach bacteria (snapshot OK) | Rip / SRF text (snapshot OK) |
|----------|------------------|-------------------|----------------------------------|------------------------------|------------------------------|
| Sailing | Yes (SCA/Gale/etc.) | Yes (wind/seas for SCA context) | No | No | Optional |
| Swimming | Yes (Beach Hazards / rip stmt if issued) | Yes (waves / WTMP when used for thresholds) | No | Yes | Yes |
| Clamming | Yes (coastal hazards) | Yes (tide level) | Yes | No | Optional |
| Crabbing | Yes (SCA for small boats) | Yes (wind/seas/currents) | Yes | No | Optional |

4. **Demo resilience:** cache a recent successful response from every feed (CO-OPS, NDBC, NWS, ERDDAP, NASA POWER, USNO). On live failure, fall back to cache **with its timestamp**, mark **stale**, and **lower confidence**. Cached data must never be presented as live.

### Gate table

| Gate | Verified source | Threshold / rule (citation) | Outcome |
|------|-----------------|----------------------------|---------|
| Shellfish biotoxins | CDPH advisories page + CDFW Health Advisories (HTML; snapshot OK) | FDA action levels in Fish & Fishery Products Hazards Guide App. 5: **PSP ≥ 0.8 mg/kg (80 µg/100 g)**; **domoic acid ≥ 20 mg/kg** (tissue); **Dungeness crab viscera > 30 mg/kg**. Any CDPH “do not eat” / quarantine / CDFW fishery closure covering the spot → CLOSED | CLOSED / UNSAFE |
| Beach bacteria | DataSF `v3fv-x3ux` ENTERO; county postings | EPA 2012 RWQC **BAV 70 cfu/100 mL** enterococci (culture) *or* CA AB411 single-sample **104** if that is what the county posts against — use the posting agency’s stated criterion when present; else BAV 70 | UNSAFE if exceedance or posted |
| Marine / beach hazards | NWS `alerts/active?point=` or `?zone=` | Events: **Small Craft Advisory, Gale Warning, Storm Warning, Special Marine Warning, Rip Current Statement, Beach Hazards Statement, High Surf Advisory** (as applicable). Western Region SCA guidance: sustained winds **21–33 kt** and/or waves **> 10 ft** (NWSI 10-303). Live SCA on PZZ545 today: winds 15–25 kt gusts 30, seas 8–13 ft | UNSAFE for affected activity |
| Rip current risk | NWS product **SRF** (`/products/types/SRF/locations/MTR`) | Text tiers **Low / Moderate / High** per NWSI 10-320. Today’s MTR SRF had **0** “Rip Current” strings (High Surf only) — if parse fails, use snapshot + caveat, do not invent Low | UNSAFE if High (swim); caveat if unparsed |
| Missing **required live API** feed | — | If NWS alerts (or CO-OPS/NDBC when required by the row above) fail/stale → **UNKNOWN**, never GOOD | UNKNOWN |

---

## Part A — Data sources

### 1. Tide predictions, water levels, currents (NOAA CO-OPS)

- **Endpoint:** `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter`
- **Example (hi/lo, Pillar Point / SF):**  
  `?station=9414290&product=predictions&datum=MLLW&interval=hilo&units=english&time_zone=lst_ldt&format=json&application=tidewise&begin_date=20261119&range=24`  
  Hourly: `interval=h` or `interval=6`. Observed: `product=water_level&date=latest&datum=MLLW&time_zone=gmt`. Currents: `product=currents_predictions&station=SFB1203&interval=MAX_SLACK`. Metadata: `https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{id}.json`
- **Auth:** none
- **Update / latency:** predictions continuous; observed water level ~6 min, latency minutes
- **Resolution:** station point; predictions to 0.001 ft in samples
- **Format:** JSON (or CSV). Sample **9414290** hi/lo 2026-11-19:

```json
{ "predictions" : [
{"t":"2026-11-19 00:12", "v":"1.018", "type":"L"},
{"t":"2026-11-19 07:15", "v":"5.269", "type":"H"},
{"t":"2026-11-19 13:32", "v":"1.674", "type":"L"},
{"t":"2026-11-19 19:20", "v":"4.113", "type":"H"}
]}
```

Observed water level: `{"t":"2026-11-19 23:36", "v":"3.63", "s":"0.351", "f":"0,0,0,0", "q":"p"}`.  
Currents SFB1203: `Type` slack/flood/ebb, `Velocity_Major` knots, `Bin`, `Depth`.  
Realtime currents `s08010`: `{"t":"...","s":"0.222","d":"52","b":"4"}`.

- **Missing / quirks:** JSON `error.message` when product not offered. Quality `q`: `p` preliminary. Flags `f` comma fields. **9414290 has wind but no water_temperature today** (lead held). **9414131** predictions OK; no water_level/temp/wind today. **9414805** → “No Predictions data was found”.
- **Rate limits:** none published; be polite
- **Gotchas:** always pass `datum=MLLW` for this app; `time_zone=lst_ldt` vs `gmt`; current stations often need a **bin** (default used by API when omitted on SFB* today)
- **Backup:** none equivalent for tides; for wind/temp use NDBC/CO-OPS neighbors

#### Verified CO-OPS tide stations (this region)

| ID | Name | Lat | Lon | Notes (verified 2026-11-19) |
|----|------|-----|-----|-----------------------------|
| 9414290 | San Francisco | 37.8063 | -122.4659 | Predictions + WL + wind; **no WTMP** |
| 9414131 | Pillar Point Harbor | 37.5025 | -122.4822 | Predictions only (no WL/WTMP/wind) |
| 9414750 | Alameda | 37.772 | -122.3003 | Predictions + WL + **WTMP 59.2°F** |
| 9414863 | Richmond | 37.9283 | -122.4 | Predictions + WL + **WTMP 61.2°F** |
| 9414523 | Redwood City | 37.5068 | -122.2119 | Predictions + WL; no WTMP |
| 9415020 | Point Reyes | 37.9942 | -122.9736 | Predictions + WL + WTMP 62.1°F |
| 9414575 | Coyote Creek | 37.465 | -122.023 | Predictions OK (far South Bay) |

#### Verified current stations (sample)

`SFB1201` SF Bay Entrance, `SFB1203` Golden Gate Bridge 0.46 nm E, `SFB1212` Raccoon Strait, `SFB1305` San Mateo Bridge, realtime `s08010` Southampton Shoal LB6.

---

### 2. Buoy waves, wind, water temp (NOAA NDBC)

- **Endpoint:** `https://www.ndbc.noaa.gov/data/realtime2/{ID}.txt`  
  Spectral: `.../{ID}.spec`  
  Station catalog: `https://www.ndbc.noaa.gov/activestations.xml`
- **Example:** `https://www.ndbc.noaa.gov/data/realtime2/46012.txt`
- **Auth:** none
- **Update / latency:** typically 10–60 min; rows are UTC
- **Resolution:** point; WVHT in meters, WSPD m/s, WTMP °C
- **Format:** space-separated text, 2 header lines. Sample **46012**:

```
#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE
#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft
2026 11 19 23 00 310 10.0 12.0   3.8    16    MM  MM 1012.4  14.0  18.9  10.2   MM +1.6    MM
```

**46237.spec:** `WVHT SwH SwP WWH WWP SwD WWD STEEPNESS APD MWD` → `3.3 2.6 15.4 2.1 8.7 W WSW SWELL 8.7 272`.

- **Missing:** **`MM`** = missing. Also reject 99/999-class sentinels if seen. Latest **46026** hour can show WVHT=MM while prior hours have waves — always scan recent rows.
- **Rate limits:** none published
- **Gotchas:** units are metric on NDBC (convert for UI); fixed met stations often have no WVHT
- **Backup:** CO-OPS wind/WTMP; other NDBC IDs in table

#### Verified NDBC / partner IDs

| ID | Role | Status today |
|----|------|--------------|
| 46026 | SF buoy 18 nm W | 200; waves intermittent (MM on some hours) |
| 46012 | Half Moon Bay USV | 200; WVHT 3.8 m |
| 46237 | SF Bar CDIP | 200; swell via `.spec` |
| 46214 | CDIP offshore | 200 |
| 46013 | Bodega | 200; no WVHT on sample |
| 46042 | Monterey | 200 |
| 46239 | Point Sur CDIP | 200 but **stale** (last 2026-10-25) — do not treat as live |
| FTPC1 | SF CO-OPS met | 200 |
| AAMC1 | Alameda | 200; WTMP 15.1°C |
| RCMC1 | Richmond | 200 |
| PXOC1 | Pier 1 | 200 |
| TIBC1 | Tiburon | **404** |
| HMBC1 | (guess) | **404** |

---

### 3. Weather forecast & marine alerts (NWS api.weather.gov)

- **Endpoints:**  
  - Points: `https://api.weather.gov/points/{lat},{lon}` → grid MTR  
  - Hourly: `https://api.weather.gov/gridpoints/MTR/82,92/forecast/hourly` (Half Moon Bay area from points call)  
  - Grid raw: `https://api.weather.gov/gridpoints/MTR/82,92` (`windSpeed`, `waveHeight`, …)  
  - Alerts: `https://api.weather.gov/alerts/active?point=37.4636,-122.4286` or `?zone=PZZ545,CAZ509`  
  - Surf Zone Forecast: `https://api.weather.gov/products/types/SRF/locations/MTR` then `/products/{id}`  
  - Coastal Waters Forecast: `.../products/types/CWF/locations/MTR`
- **Auth:** none; **required** `User-Agent` identifying the app
- **Update / latency:** forecasts ~hourly; alerts immediate; SRF/CWF few times daily (SRF issued 2026-11-19T22:53Z)
- **Resolution:** NDFD grid cell; marine zones PZZ*; coastal CAZ*
- **Format:** GeoJSON / JSON. Hourly period sample:

```json
{"number": 1, "startTime": "2026-11-19T15:00:00-08:00", "temperature": 55, "temperatureUnit": "F",
 "windSpeed": "14 mph", "windDirection": "WNW", "shortForecast": "Chance Light Rain",
 "probabilityOfPrecipitation": {"unitCode": "wmoUnit:percent", "value": 31}}
```

Alert sample: Small Craft Advisory on **PZZ545**, expires 2026-11-19T22:45-08:00; description winds 15–25 kt gusts 30, seas 8–13 ft.  
SRF CAZ509 snippet: Northwest Facing Beaches **12 to 16 feet**; High Surf Advisory; Water Temperature Around 66 degrees.

- **Missing:** many grid `waveHeight` values were `0` / long-duration inland; **do not** use land grid waves for ocean surf — use CWF/SRF/NDBC
- **Rate limits:** fair-use; cache
- **Gotchas:** zone vs point alerts differ; rip risk is **text** in SRF (tiers low/moderate/high) — today’s MTR SRF had **no** Rip Current lines
- **Backup:** none for official watches/warnings

---

### 4. Satellite SST (MUR via CoastWatch ERDDAP)

- **Endpoint:** `https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.csv?analysed_sst[(last)][(37.75)][(-122.9)]`
- **Auth:** none on ERDDAP. PODAAC NetCDF download needs Earthdata.
- **Update / latency:** daily; metadata: recent days revised; NRT vs final (~1–4 day). Sample time **2026-11-18T09:00:00Z** on 2026-11-19 → ~1 day lag.
- **Resolution:** 0.01°
- **Format:** CSV. Sample: `2026-11-18T09:00:00Z,37.75,-122.9,18.28` (°C). Land/coast pixel `(-122.5)` → **`NaN`**.
- **Missing:** NaN; mask variable available
- **Gotchas:** pick offshore lon ≤ about -122.7 for this lat; `upwell.pfeg` **302**→same host; **`coastwatch.noaa.gov` ERDDAP 502** today
- **Backup:** `https://oceanwatch.pifsc.noaa.gov/erddap/griddap/goes-poes-1d-ghrsst-RAN.csv?analysed_sst[(last)][(37.75)][(237.1)]` → `291.35` **degree_K** (≈18.2°C). Lon0–360. `noaacwBLENDEDsstDaily` **404** on OceanWatch today. CMR lists MUR granules.

---

### 5. Chlorophyll-a / HAB indicators

- **VIIRS chl (primary composite):**  
  `.../griddap/erdVHNchla8day.csv?chla[(last)][(0.0)][(37.6)][(-122.6)]`  
  Variable is **`chla`** (not `chlorophyll`). Fill **-999**; CSV may show **NaN**.  
  Sample 8-day: `2026-11-09T00:00:00Z,...,2.234274` mg m^-3.  
  1-day same point: time 2026-11-12, **NaN** (cloud/gap).
- **C-HARM v3.1 nowcast (HAB probabilities):**  
  `.../griddap/wvcharmV3_0day.csv?pseudo_nitzschia[(last)][(37.5)][(237.4)],particulate_domoic[(last)][(37.5)][(237.4)],cellular_domoic[(last)][(37.5)][(237.4)],chla_filled[(last)][(37.5)][(237.4)]`  
  Lon is **0–360**. Sample 2026-11-02: PN 0.87, pDA 0.70, cDA 0.39, chl_filled 0.89. Fill **-99999**. Model thresholds in metadata: PN>10,000 cells/L, pDA>500 ng/L, cDA>10 pg/cell (probabilities of exceedance).
- **Reasonable bloom caution for this region:** treat **chl ≳ 5–10 mg m^-3** (8-day) or **C-HARM particulate_domoic probability ≳ 0.5** as a **warning flag** to emphasize CDPH — **not** an automatic legal closure. (No single CA “close clam beds at X mg m^-3” regulation verified; CDPH toxin tests gate harvest.)
- **Auth / rate:** none / polite
- **Backup:** OceanWatch `noaa_snpp_chla_daily` (`chlor_a`, lon360); latency older (sample 2026-11-06)
- **PACE:** no dedicated PACE chl dataset confirmed on CoastWatch search today

---

### 6. California shellfish / biotoxin closures (CDPH / CDFW)

- **No public JSON API found.** Reliable pages (scrapable HTML / news list):  
  - `https://www.cdph.ca.gov/Programs/OPA/Pages/Shellfish-Advisories.aspx` (updated 2026-11-17; annual mussel quarantine ended 2026-10-31; Dungeness/anchovy advisories active elsewhere)  
  - Recreational shellfish map (ArcGIS): item/dashboard linked from CDPH; MapTools appid `42a78fba680c4c43970cfc5dfe878d8d`  
  - `https://wildlife.ca.gov/Fishing/Ocean/Health-Advisories` (CDFW implements closures when toxins meet federal action levels; Domoic Acid Closure Info Line **(831) 649-2883**)
- **Structure:** reverse-chronological press releases with county names and lat bounds (e.g. Pigeon Point 37°11'N). Parse titles for “Warns”/“Lifts”/“Quarantine”.
- **Auth:** none
- **Update:** irregular; snapshot + `last_verified` required
- **Backup:** phone lines; county EH posts

---

### 7. Beach bacteria / water quality

- **SF API (verified):** `https://data.sf.gov/resource/v3fv-x3ux.json?$where=analyte%20IS%20NOT%20NULL&$order=sample_date%20DESC&$limit=...`  
  Fields: `source`, `sample_date`, `analyte` (`ENTERO`,`COLI_TOTAL`,`COLI_FECAL`), `data` (string; may be `<5`, `>16000`).  
  Sample 2026-11-17: OCEAN#22_SL ENTERO **10**; BAY#320_SL ENTERO **2143**.
- **Thresholds:** EPA RWQC BAV **70 cfu/100 mL** enterococci (culture); CA counties often post using AB411 **104** — prefer posted status when available.
- **BeachWatch** `beachwatch.waterboards.ca.gov` — HTML forms; **no clean public API verified**. EPA **BEACON** — no clean API (lead held).
- **San Mateo / Pacifica:** county EH beach pages (HTML snapshot) — curl to smchealth was not fully parsed this session; treat as scrape + snapshot.
- **Backup:** SFPUC beach pages / hotline 415-242-2214

---

### 8. Fires and smoke (FIRMS, EONET)

- **EONET:** `https://eonet.gsfc.nasa.gov/api/v3/events?status=open&bbox=-123.2,37.2,-121.8,38.2&limit=20`  
  Sample returned 2 “open” wildfires with geometries dated **2024** — filter by geometry date / close stale events.
- **FIRMS:** `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/VIIRS_SNPP_NRT/-123.2,37.2,-121.8,38.2/1`  
  Without key → `Invalid MAP_KEY.` Sign up: firms.modaps.eosdis.nasa.gov.
- **Auth:** FIRMS key required; EONET none
- **Backup:** NWS smoke/Air Quality alerts via api.weather.gov

---

### 9. UV and solar (NASA POWER + EPA)

- **EPA Envirofacts (better for same-day UV):**  
  `https://data.epa.gov/efservice/getEnvirofactsUVDAILY/ZIP/94019/JSON` → `{"UV_INDEX":"2","UV_ALERT":"0","DATE":"Nov/19/2026"}`  
  Hourly: `.../getEnvirofactsUVHOURLY/ZIP/94019/JSON` (`UV_VALUE` by hour).
- **NASA POWER:**  
  `https://power.larc.nasa.gov/api/temporal/daily/point?parameters=ALLSKY_SFC_UV_INDEX,ALLSKY_SFC_SW_DWN,T2M&community=RE&longitude=-122.5&latitude=37.7&start=YYYYMMDD&end=YYYYMMDD&format=JSON`  
  `fill_value: -999.0`. On 2026-11-19, **ALLSKY_SFC_SW_DWN** last non-fill **2026-11-14**; **T2M** last **2026-11-16**; **ALLSKY_SFC_UV_INDEX** all fill for the window. **Latency ~2–5 days**; **no marine fields** — context only (lead held).
- **Backup:** each other

---

### 10. Seasonal SST climatology / anomalies

- **Anomaly:** `jplMURSST41anom1day` `sstAnom` — sample `2026-11-17T09:00:00Z,37.75,-122.9,5.004` °C  
- **Climatology:** `jplMURSST41clim` variables **`mean_sst`**, **`standard_deviation`** vs `dayOfYear` (1–365) — sample DOY 322: mean **13.24** °C, sd **0.86**  
- **Lower-res:** `jplMURSST42` `sst_anomaly` in **kelvin** (sample 4.964)  
- **Auth:** none  
- **Gotchas:** clim variable is `mean_sst` not `sst`; anomaly dataset lag can differ from analysed_sst day

---

## Part B — Domain rules (brief, cited)

- **Clamming tides:** aim for lows **≲ 0.0 to +1.0 ft MLLW** (lower is better) on outer coast flats; use CO-OPS MLLW. Popular spots: Fitzgerald Marine Reserve, Pillar Point / Princeton harbor flats, Half Moon Bay state beaches — confirm access/tidepools rules locally. (**unverified** — general guidance, no source fetched this session; pair with CDPH.)
- **Seasons / limits:** Recreational **Dungeness 2026–27**: opens **Sat Nov 7, 2026**; bag **10**/day; min **5¾ in**; ocean waters (not SF/San Pablo bays); sport license; crab trap validation for traps — CDFW recreational Dungeness summary (DocumentID 195690). Clams: species-specific CDFW ocean sport regs + **CDPH** biotoxin status. Annual CA mussel quarantine historically May–Oct; **lifted Oct 31, 2026** per CDPH.
- **Crabbing tides/currents/moon:** many crabbers prefer **slack** or moderate current and soak across exchanges; moon phase via USNO (`https://aa.usno.navy.mil/api/moon/phases/date?date=2026-11-19&nump=4` — next Full Moon 2026-11-24 14:53) — treat moon as folk/secondary, not a hard gate. Slack/moon preference **unverified** (no source fetched).
- **Sailing wind/sea:** beginner small-boat: stay below SCA conditions; Western SCA guidance **21–33 kt** or seas **>10 ft** (NWSI 10-303). Experienced: respect Gale (≥34 kt) and local bar forecasts (46237).
- **Swimming:** cold SF water often **50–60°F** (**unverified** general figure; today's live readings: 59–62°F CO-OPS, 15–19°C NDBC); hypothermia risk; prefer WTMP from 9414750/NDBC. Avoid High Surf / High rip risk; wave height from SRF/NDBC not land-grid.

### Named spots (lat/lon from OSM Nominatim 2026-11-19; shore orientation **unverified** estimates)

| Spot | Lat | Lon | Activities | Shore ° (approx facing) |
|------|-----|-----|------------|-------------------------|
| Pillar Point Harbor | 37.5012 | -122.4748 | crab, sail (harbor), clam nearby | 180 (S, harbor) |
| Mavericks Beach | 37.4956 | -122.4968 | surf watch; not swim | 270 (W) |
| Dunes Beach (HMB) | 37.4837 | -122.4534 | clam, beach walk | 270 (W) |
| Francis Beach (HMB) | 37.4692 | -122.4471 | swim (caution), clam | 270 (W) |
| Fitzgerald Marine Reserve | 37.5138 | -122.5134 | tidepool/clam (rules!) | 270 (W) |
| Montara State Beach | 37.5505 | -122.5141 | beach; surf hazard | 270 (W) |
| Rockaway Beach (Pacifica) | 37.6098 | -122.4975 | surf, swim caution | 270 (W) |
| Pacifica Municipal Pier | 37.6334 | -122.4962 | crab (pier) | 270 (W) |
| Ocean Beach (SF) | 37.7562 | -122.5102 | swim rarely safe; surf | 270 (W) |
| Baker Beach | 37.7931 | -122.4838 | swim caution | 250 (WSW) |
| China Beach | 37.7883 | -122.4909 | swim caution | 250 (WSW) |
| Crissy Field East | 37.8058 | -122.4491 | swim, windsurf | 0 (N into bay) |
| Aquatic Park | 37.8064 | -122.4235 | swim (protected) | 0 (N) |
| Crown Memorial (Alameda) | 37.7610 | -122.2693 | swim, sail | 225 (SW) |
| Berkeley Marina | 37.8679 | -122.3131 | sail | 270 (W) |
| Coyote Point | 37.5895 | -122.3346 | sail, windsurf | 315 (NW) |

---

## Risks & Unverified

- **Unverified (not called/sourced):** Part B clamming tide range, crabbing slack/moon guidance, swim temp ranges, shoreline orientations, Open-Meteo, AB411 104 threshold (cited from a secondary site only), San Mateo County beach posting pages, FIRMS with a real key.
- Live SST reads unusually warm (MUR 18.3°C, +5.0°C anomaly; NDBC WTMP 18.8–18.9°C) — consistent across sources but cross-check before demo.

- `coastwatch.noaa.gov` and `polarwatch.noaa.gov` ERDDAP **502** today; rely on **pfeg** + OceanWatch backup.
- OceanWatch `noaacwBLENDEDsstDaily` **404** despite appearing in search index.
- NASA POWER **UV index** all `-999` in tested window; use EPA UV for forecasts.
- CDPH page sometimes fails datacenter curl (**HTTP 000**); WebFetch succeeded — scrapers need retries/browser fallback; use snapshots.
- San Mateo/Pacifica bacteria **posting pages** not fully structured in this pass (SF Socrata was).
- EONET “open” wildfires can be **years** old — always check geometry dates; FIRMS key not registered in this session (endpoint shape verified via error).
- PACE chlorophyll on ERDDAP **not verified**.
- Exact legal “chlorophyll closes clam beds” threshold **unverified** — CDPH toxin results gate harvest.
- Linda Mar beach geocode snapped to a post office POI; use Rockaway/Pacifica pier coords or hand-correct.
- NWS SRF rip lines **absent** today — parser must tolerate missing section.
- Station `46239` stale; `TIBC1`/`HMBC1` 404.

