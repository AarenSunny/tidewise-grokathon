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

#### C-HARM availability (update 2026-11-19) (Pseudo-nitzschia / domoic acid probability) — **availability status: FLAPPING + STALE**

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

### 6. California shellfish / biotoxin closures (CDPH / CDFW) — live-source update 2026-11-19

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

### 7. Beach bacteria / water quality — live-source update 2026-11-19

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

- **Unverified (not called/sourced):** Part B clamming tide range, crabbing slack/moon guidance, swim temp ranges, shoreline orientations, Open-Meteo, AB411 104 threshold (cited from a secondary site only), FIRMS with a real key.
- Live SST reads unusually warm (MUR 18.3°C, +5.0°C anomaly; NDBC WTMP 18.8–18.9°C) — consistent across sources but cross-check before demo.

- `coastwatch.noaa.gov` and `polarwatch.noaa.gov` ERDDAP **502** today; rely on **pfeg** + OceanWatch backup.
- OceanWatch `noaacwBLENDEDsstDaily` **404** despite appearing in search index.
- NASA POWER **UV index** all `-999` in tested window; use EPA UV for forecasts.
- CDPH `www.` host TLS: server omits the Sectigo OV R36 intermediate, so strict verification fails (curl 000/exit 60); fix in §6b (append AIA intermediate to the CA bundle). CDPH ArcGIS layers are static 2020 pins, not live status. No CDPH RSS.
- Beach bacteria: live sources are DataSF `v3fv-x3ux` and the San Mateo County posting posts (§7); SWRCB BeachWatch ended (San Mateo 2026-03-02, SF 2025-10-28). San Mateo list = postings only; County GIS MapServer 500.
- **C-HARM is flapping (404/503/23 s) and ~17 days stale** (last model time 2026-11-02T12:00Z) — do not show as current; see C-HARM availability above.
- EONET “open” wildfires can be **years** old — always check geometry dates; FIRMS key not registered in this session (endpoint shape verified via error).
- PACE chlorophyll on ERDDAP **not verified**.
- Exact legal “chlorophyll closes clam beds” threshold **unverified** — CDPH toxin results gate harvest.
- Linda Mar beach geocode snapped to a post office POI; use Rockaway/Pacifica pier coords or hand-correct.
- NWS SRF rip lines **absent** today — parser must tolerate missing section.
- Station `46239` stale; `TIBC1`/`HMBC1` 404.

> Long-form regulation quotes (hoop nets, loop traps, §29.80/§28.65), sunrise APIs and the earlier detailed notes are in `grok-sessions/research/DATA_SOURCES_full.md` (the previous long version of this file; still in git history at ed08814).
