# TideWise DATA_SOURCES

Verified live on **2026-11-19** (America/Los_Angeles). Accuracy over coverage: every primary URL below was called today; field names and snippets are from real responses. Probe scripts: `scripts/research_probes/`. Those scripts are the checks that called these feeds.

Team note: **National Oceanic and Atmospheric Administration (NOAA) CoastWatch Environmental Research Division's Data Access Program (ERDDAP) sea-surface temperature (SST) (`jplMURSST41`) and chlorophyll-a (`erdVHNchla*`) are the core space data.** Chlorophyll spikes and California Harmful Algae Risk Mapping (C-HARM) harmful algal bloom (HAB) probabilities are early-warning inputs. **California Department of Public Health (CDPH) and California Department of Fish and Wildlife (CDFW) advisories remain the legal safety gate for clam beds.**

## How to read this doc

This catalog is the list of feeds TideWise can call. You do not need an ocean-data background to follow it.

- Start with the glossary if a short name is unfamiliar. Each major section also writes the full name the first time that section uses it.
- The Recommended API stack is which feed to use. Hard safety-gate feeds are the checks that can force a spot to unsafe, closed, or unknown before any score. Part A is how to call each feed. Part B is the activity rules. Risks and Unverified is what was not confirmed.
- Each numbered source starts with one plain sentence: what the feed gives TideWise and why it is needed. The bullets under that sentence are the exact contract: URL, parameters, station identifiers, field names, and a real sample.
- Monospace text is an exact string from a request or a live response. Copy it as written. Placeholders in braces, such as a station id or a map key, are values you fill in. The braces are part of the documented pattern.
- An older note sometimes used an arrow to mean "returns" or "which is." Those arrows are written as sentences here. A buoy cell that says MM was not reported. Do not read MM as zero. A star after a code, such as PZZ*, means "codes that start with those letters."
- The word unverified means that statement was not confirmed from a source fetched for this document. Leave that word in place.
- Samples and thresholds are from the verification day in the first paragraph unless a bullet gives another time.

## Glossary

Definitions below explain words already used in this catalog. Numeric limits live in the sections that measured them, not here.

### Agencies and programs

- **NOAA** — National Oceanic and Atmospheric Administration. The U.S. agency behind the tide, buoy, weather, and many satellite feeds here.
- **CO-OPS** — Center for Operational Oceanographic Products and Services. The NOAA office for tide predictions, water levels, and currents.
- **NDBC** — National Data Buoy Center. The NOAA office that publishes buoy observations.
- **NWS** — National Weather Service. The NOAA office for forecasts, watches, and warnings.
- **CDPH** — California Department of Public Health. Publishes shellfish and biotoxin advisories.
- **CDFW** — California Department of Fish and Wildlife. Publishes fishery closures and in-season rules.
- **OEHHA** — California Office of Environmental Health Hazard Assessment. Writes health memos cited with the crab advisories.
- **EPA** — U.S. Environmental Protection Agency. Source of the recreational-water criteria and the UV index service.
- **FDA** — U.S. Food and Drug Administration. The gate table cites its seafood hazards guide.
- **NASA** — National Aeronautics and Space Administration. Source of EONET, FIRMS, and POWER.
- **USNO** — United States Naval Observatory. Moon-phase feed in Part B.
- **SWRCB** — State Water Resources Control Board. Runs the BeachWatch archive on data.ca.gov.
- **SFPUC** — San Francisco Public Utilities Commission. Publishes the human-facing beach pages.
- **EH** — environmental health. County offices that post beach bacteria results.
- **CDIP** — Coastal Data Information Program. A wave network whose buoys also appear under NDBC identifiers.
- **CoastWatch** — NOAA program that distributes satellite ocean data. The host used here is the West Coast ERDDAP.
- **OceanWatch** — a related NOAA ERDDAP host used as a backup.
- **PODAAC** — Physical Oceanography Distributed Active Archive Center. NASA archive of ocean satellite files.
- **CMR** — Common Metadata Repository. NASA's catalog of those files.
- **Earthdata** — NASA login required to download PODAAC NetCDF files.
- **C-HARM** — California Harmful Algae Risk Mapping. A model that publishes probabilities of harmful-algal-bloom conditions.
- **PACE** — Plankton, Aerosol, Cloud, ocean Ecosystem satellite. No dedicated chlorophyll dataset was confirmed on CoastWatch.
- **VIIRS** — Visible Infrared Imaging Radiometer Suite. The satellite instrument behind the chlorophyll composite and the FIRMS fire product.
- **SNPP** — Suomi National Polar-orbiting Partnership. The satellite named in the FIRMS product VIIRS_SNPP_NRT.
- **EONET** — Earth Observatory Natural Event Tracker. NASA's catalog of events such as wildfires.
- **FIRMS** — Fire Information for Resource Management System. NASA active-fire detections. Needs a free MAP_KEY.
- **POWER** — Prediction Of Worldwide Energy Resources. NASA solar and weather point data.
- **Envirofacts** — EPA's public data service, used here for the UV index.
- **BEACON** — EPA Beach Advisory and Closing Online Notification. This catalog found no clean live API.
- **BeachWatch** — California beach-water site. The data.ca.gov copy is a historical archive. County feeds are the live postings.
- **BWTF** — Blue Water Task Force. Surfrider's volunteer water-quality program. The San Mateo page says local volunteers help with Monday sampling.
- **Heal the Bay** — publisher of the Beach Report Card website.
- **DataSF** — San Francisco's open-data catalog.
- **Socrata** — the platform behind DataSF. Queries use SoQL parameters such as $where and $order.
- **ArcGIS** — mapping software. CDPH and San Mateo expose map layers through it. A FeatureServer is that map's query endpoint.
- **GovDelivery** — a government email-subscription service. The CDPH signup path returned not found.
- **SharePoint** — the web system that hosts the CDPH news list.
- **OSM / Nominatim** — OpenStreetMap and its geocoder. Source of the named-spot coordinates.
- **NDFD** — National Digital Forecast Database. The grid behind api.weather.gov.

### Services, formats, and access

- **API** — application programming interface. A URL a program can call.
- **ERDDAP** — Environmental Research Division's Data Access Program. A NOAA server that subsets scientific datasets over HTTP.
- **griddap** — the ERDDAP service that returns a slice of a gridded dataset. The CSV and JSON links use it.
- **JSON** — JavaScript Object Notation, a text format for structured data.
- **CSV** — comma-separated values, a plain table as text.
- **HTML** — the markup of a web page. Several safety sources are pages to scrape, not APIs.
- **GeoJSON** — JSON that describes map features. NWS alerts and forecasts use it.
- **RSS** — a feed of dated posts. San Mateo exposes one. CDPH did not.
- **WP-JSON** — WordPress's JSON API. San Mateo postings are WordPress posts discovered this way.
- **SPA** — single-page application. A website that returns an HTML shell rather than the data itself.
- **NetCDF** — a scientific file format for gridded data.
- **HTTP status** — 200 means success, 302 means redirect, 404 means not found, 500 means the server failed, 502 and 503 mean the server is unavailable, 000 means the client got no response.
- **TLS** — Transport Layer Security, the certificate check on HTTPS. Strict TLS means the certificate chain must verify. The CDPH www host fails that check until the missing intermediate certificate is added.
- **AIA** — Authority Information Access. A URL inside a certificate that points at the missing intermediate.
- **DER** — a binary certificate encoding. The Sectigo intermediate is downloaded in that form and converted to PEM.
- **Sectigo** — the company that issued the CDPH leaf certificate named in the TLS note.
- **UA header / User-Agent** — the HTTP header that names the calling application. NWS requires it.
- **MAP_KEY** — the free key FIRMS requires in the URL. This session did not register one.
- **bbox** — bounding box. A rectangle given as west, south, east, north.
- **snapshot** — a saved copy of a page that has no clean API, stored with last_verified.
- **last_verified** — the date that saved copy was checked.
- **flapping** — up and down over short intervals. C-HARM answered, then returned not found or unavailable, then answered again.
- **stale** — the service answered, but the observation or model time is too old to treat as current.
- **NRT** — near real time, as opposed to a later final product that can revise recent days.
- **nowcast** — a model estimate for conditions now, as opposed to a forecast for a later day.
- **fill value** — a placeholder number written when there is no observation. It is not a real measurement.
- **sentinel** — a placeholder that means "no measurement," such as MM or a fill value.
- **lead held** — a teammate suggestion that was checked and is not being used as a live source.
- **unverified** — not confirmed from a source fetched for this document.

### Ocean measurements

- **SST** — sea surface temperature.
- **MUR** — Multi-scale Ultra-high Resolution. The daily sea-surface temperature analysis in dataset jplMURSST41.
- **chlorophyll-a / chla / chl** — the green pigment in phytoplankton. In these ERDDAP datasets the field name is chla, not chlorophyll. A high value can hint at a bloom. It is not by itself a legal closure.
- **HAB** — harmful algal bloom. A dense growth of algae that can produce toxins.
- **Pseudo-nitzschia / PN** — a diatom that can produce domoic acid. C-HARM publishes a probability for it.
- **domoic acid** — a toxin that can make shellfish and crab unsafe. pDA is the particulate form and cDA is the cellular form in the C-HARM field names.
- **PSP** — paralytic shellfish poisoning. A different shellfish illness. The gate table quotes the FDA action level.
- **bivalve** — a two-shelled animal such as a mussel, clam, or oyster. The advisories use this word for those harvests.
- **viscera** — a crab's internal organs, also called butter or guts in the OEHHA memo. The FDA crab limit applies to that tissue.
- **quarantine** — an official harvest ban for a time window, such as the annual mussel quarantine.
- **MLLW** — Mean Lower Low Water. The tide datum for this app: heights are relative to the average of the lower of the two daily low tides.
- **datum** — the reference height for water levels. This app uses MLLW.
- **hi/lo and hilo** — the high and low tide times, as opposed to an hourly series.
- **slack / flood / ebb** — current states. Slack is little flow, flood is incoming, and ebb is outgoing.
- **bin** — a depth layer in a current-meter record. Some stations use a default bin when the request omits it.
- **WL** — water level.
- **WVHT** — significant wave height, the average height of the highest third of the waves. On NDBC it is in meters.
- **WTMP** — water temperature.
- **WSPD / GST / WDIR** — wind speed, gust, and wind direction on an NDBC row.
- **DPD / APD / MWD** — dominant wave period, average period, and mean wave direction.
- **SwH / SwP / SwD and WWH / WWP / WWD** — swell height, period, and direction, and the same three for wind waves, on a spectral file.
- **STEEPNESS** — the text label in that spectral row for how steep the waves are.
- **PRES / ATMP / DEWP / VIS / PTDY / TIDE** — pressure, air temperature, dewpoint, visibility, pressure tendency, and a tide column on the NDBC row.
- **MM** — the NDBC missing-value sentinel. The cell was not reported.
- **NaN** — not a number. ERDDAP CSV uses it when a grid cell has no valid value, often because the cell is land or cloud.
- **Kelvin / degree_K** — a temperature scale. The OceanWatch backup SST is labeled degree_K. The sample in that section also gives the Celsius equivalent.
- **0–360 longitude** — longitude measured eastward from 0 to 360 degrees instead of negative numbers west of Greenwich. C-HARM and the OceanWatch backup use that form. Lon0–360 and lon360 in the notes mean the same convention.
- **anomaly** — how far a temperature is from the long-term average for that day of year.
- **climatology** — that long-term average. The field is mean_sst, not sst.
- **DOY / dayOfYear** — day of the year.
- **Enterococcus / ENTERO** — a fecal-indicator bacterium used to judge swimming water. ENTERO is the analyte code in the DataSF feed.
- **cfu** — colony-forming units, a lab count of bacteria. The EPA beach criterion is quoted per 100 milliliters.
- **MPN** — most probable number, another bacteria count used by the county posting thresholds.
- **COLI_TOTAL / COLI_FECAL** — total coliform and fecal coliform, other analytes in the same feed.
- **BAV** — Beach Action Value, the EPA recreational-water threshold named in the gate table.
- **RWQC** — Recreational Water Quality Criteria (EPA, 2012).
- **AB411** — the California beach-posting law. Counties often post against its single-sample figure. The gate table says to prefer the posting agency's own criterion.
- **UV index** — a unitless sunburn scale from EPA or NASA POWER.
- **geometric mean** — an average that multiplies values and takes the root. The San Mateo threshold note quotes geometric-mean limits beside the single-sample maxima.

### Weather products and zones

- **SCA** — Small Craft Advisory.
- **SRF** — Surf Zone Forecast, an NWS text product.
- **CWF** — Coastal Waters Forecast, an NWS text product.
- **MTR** — the NWS office identifier for the San Francisco Bay Area and Monterey office, used in grid and product URLs.
- **PZZ** — prefix on NWS marine zone codes (open water). PZZ* means zones that start with PZZ.
- **CAZ** — prefix on NWS coastal public zone codes. CAZ* means zones that start with CAZ.
- **NWSI** — National Weather Service Instruction. The gate table cites NWSI 10-303 and NWSI 10-320.
- **Gale / Storm / Special Marine Warning / Rip Current Statement / Beach Hazards Statement / High Surf Advisory** — NWS alert names quoted in the gate table.
- **kt** — knots, nautical miles per hour.
- **nm** — nautical miles.
- **USV** — unmanned surface vehicle. The buoy table uses this for the Half Moon Bay platform.
- **met** — meteorological, meaning wind and air observations rather than waves.
- **bar** — here, the shallow entrance to the bay. Station 46237 is the San Francisco Bar buoy.
- **rip current** — a narrow seaward current that can pull swimmers out. The risk tiers live in the SRF text, not in a separate numeric field.
- **UNKNOWN / UNSAFE / CLOSED / GOOD** — gate outcomes. UNKNOWN means a required live feed failed or is stale. UNSAFE means a hazard threshold was met. CLOSED means a harvest or fishery closure. GOOD must not be shown when a required live feed is missing.


---

## Recommended API stack

Use this table to choose a feed. Primary is the feed to call. Backup is what to try if the primary fails. Avoid is a mistake that looks reasonable and is wrong. Acronyms are spelled in the glossary and again on first use in each row.

| Need | Primary (why) | Backup | Avoid |
|------|---------------|--------|-------|
| 1. Tides, water levels, and currents | **NOAA CO-OPS** (Center for Operational Oceanographic Products and Services) at `api.tidesandcurrents.noaa.gov`. Official mean lower low water (MLLW) predictions, observed water levels, and San Francisco Bay current predictions. No key. | National Data Buoy Center (NDBC) stations `FTPC1` and `AAMC1` are wind only. There is no good tide backup. | Commercial tide libraries that invent stations. Station `9414805` had no predictions today. |
| 2. Buoy waves, wind, and water temperature (WTMP) | **NDBC** files `realtime2/{id}.txt`, plus `.spec` for swell. Free, no key. The missing-data sentinel MM is documented. | CO-OPS wind and water temperature at `9414750` and `9414863`. Coastal Data Information Program (CDIP) buoys are available through NDBC identifiers `46237` and `46214`. | Assuming every buoy reports significant wave height (WVHT). Buoy 46026 often shows the missing marker MM on the latest hour. |
| 3. Weather and marine alerts | **National Weather Service (NWS)** `api.weather.gov`. Use Monterey (MTR) gridpoint forecasts, `alerts/active`, and the text products `SRF` (Surf Zone Forecast) and `CWF` (Coastal Waters Forecast). Free. A User-Agent header (UA) is required. | Open-Meteo (**unverified**, not called) | Scraping weather.com. Using the grid field `waveHeight` alone for ocean surf, because it is often null over inland cells. |
| 4. Satellite sea-surface temperature (SST) | **CoastWatch ERDDAP** dataset `jplMURSST41`, field `analysed_sst`. Daily Multi-scale Ultra-high Resolution (MUR) product at 0.01°. | OceanWatch dataset `goes-poes-1d-ghrsst-RAN` (0.05°, in Kelvin). The PODAAC CMR list can name granules, but download needs an Earthdata login. | `coastwatch.noaa.gov` and `polarwatch` returned HTTP **502** today. Nearshore MUR pixels come back as **NaN** (not a number). |
| 5. Chlorophyll and harmful algal blooms (HAB) | **ERDDAP** dataset `erdVHNchla8day`, field `chla`, plus **C-HARM** dataset `wvcharmV3_0day` (probabilities). | `erdVHNchla1day` comes back as NaN when it is cloudy. OceanWatch dataset `noaa_snpp_chla_daily` is the other backup. | Treating satellite chlorophyll alone as a legal closure. PACE was not found as a clean ERDDAP dataset today. |
| 6. Shellfish and biotoxin closures | **CDPH** Shellfish Advisories page (HTML) and the ArcGIS map, plus **CDFW** Health Advisories page (HTML). | CDPH info line (800) 553-4133. CDFW Domoic Acid Closure line (831) 649-2883. | An invented CDPH JSON API. None was found. |
| 7. Beach bacteria | **DataSF** Socrata dataset `v3fv-x3ux` (San Francisco Enterococcus, analyte ENTERO) and county posting pages. | The BeachWatch web UI has no clean JSON API verified. The California Open Data archive is historical. | EPA BEACON as a live API. There is no clean API. This lead is held. |
| 8. Fires and smoke | **NASA EONET** version 3 events inside a bounding box (bbox). No key. | **NASA FIRMS** area CSV, which needs a free MAP_KEY. | Treating multi-year-old EONET events marked “open” as active smoke without checking FIRMS. |
| 9. UV and solar | **EPA Envirofacts** ultraviolet (UV) index, daily and hourly, by ZIP code. Live, no key. | NASA POWER daily parameters `ALLSKY_SFC_SW_DWN` and `T2M`. The POWER UV index was all fill values today. | Using POWER as a marine product. It has no ocean fields, and radiation lags by about 2–5 days. |
| 10. SST climatology and anomaly | **ERDDAP** datasets `jplMURSST41anom1day` and `jplMURSST41clim` (field `mean_sst`). | `jplMURSST42` field `sst_anomaly` (0.25°, in Kelvin). | Computing an anomaly from a single buoy without a climatology. |

**Keys the team must sign up for:** a free NASA FIRMS MAP_KEY. Optional: a NASA Earthdata login for PODAAC MUR NetCDF files if ERDDAP is down. Everything else verified today needs **no key**. Send an identifying `User-Agent` to NWS.

---

## Hard safety-gate feeds

Read this section before the scoring rules. A gate can force the outcome even when every other signal looks fine.

In plain language, these checks decide whether a spot is even allowed before TideWise scores it. Gates run **before** scoring. A gate that fires forces **UNSAFE**, **CLOSED**, or **UNKNOWN** as specified. The cache and snapshot policy is below. National Weather Service (NWS), CO-OPS, and NDBC are the live API feeds. CDPH and CDFW advisories are snapshot sources.

### Policy (activity × feed + UNKNOWN / snapshot / cache)

1. **UNKNOWN** only when a **live, API-backed** safety feed that the **activity needs** fails or is stale (NWS alerts; CO-OPS/NDBC when that activity needs them for the gate). Do **not** force UNKNOWN just because a scrape-only source is hard to refresh.
2. **No-clean-API sources** (CDPH shellfish advisories/quarantines, CDFW Dungeness/domoic status, Bay Area county beach bacteria postings, NWS rip-current **text** if parsing fails): keep a **stored snapshot** with `last_verified`. Still show the score plus a caveat like `Check CDPH advisory, last verified <date>`. If the snapshot itself shows a **closure or exceedance**, still force **CLOSED** or **UNSAFE**.
3. **Per-activity required safety feeds**

| Activity | NWS alerts (API) | CO-OPS/NDBC (API) | CDPH/CDFW biotoxin (snapshot OK) | Beach bacteria (snapshot OK) | Rip current text in the Surf Zone Forecast (SRF) (snapshot OK) |
|----------|------------------|-------------------|----------------------------------|------------------------------|------------------------------|
| Sailing | Yes (Small Craft Advisory (SCA), Gale, and similar warnings) | Yes (wind and seas, for SCA context) | No | No | Optional |
| Swimming | Yes (Beach Hazards Statement, or a rip current statement if one is issued) | Yes (waves and water temperature (WTMP) when those are used for thresholds) | No | Yes | Yes |
| Clamming | Yes (coastal hazards) | Yes (tide level) | Yes | No | Optional |
| Crabbing | Yes (SCA for small boats) | Yes (wind, seas, and currents) | Yes | No | Optional |

4. **Demo resilience:** cache a recent successful response from every feed (CO-OPS, NDBC, NWS, ERDDAP, NASA POWER, USNO). On live failure, fall back to cache **with its timestamp**, mark **stale**, and **lower confidence**. Cached data must never be presented as live.

### Gate table

| Gate | Verified source | Threshold / rule (citation) | Outcome |
|------|-----------------|----------------------------|---------|
| Shellfish biotoxins | CDPH advisories page + CDFW Health Advisories (HTML; snapshot OK) | FDA action levels in Fish & Fishery Products Hazards Guide App. 5: **PSP ≥ 0.8 mg/kg (80 µg/100 g)**; **domoic acid ≥ 20 mg/kg** (tissue); **Dungeness crab viscera > 30 mg/kg**. Any CDPH notice that says “do not eat”, any quarantine, or any CDFW fishery closure covering the spot forces the outcome CLOSED | CLOSED / UNSAFE |
| Beach bacteria | DataSF `v3fv-x3ux` ENTERO; county postings | EPA 2012 RWQC **BAV 70 cfu/100 mL** enterococci (culture) *or* CA AB411 single-sample **104** if that is what the county posts against — use the posting agency’s stated criterion when present; else BAV 70 | UNSAFE if exceedance or posted |
| Marine / beach hazards | NWS `alerts/active?point=` or `?zone=` | Events: **Small Craft Advisory, Gale Warning, Storm Warning, Special Marine Warning, Rip Current Statement, Beach Hazards Statement, High Surf Advisory** (as applicable). Western Region SCA guidance: sustained winds **21–33 kt** and/or waves **> 10 ft** (NWSI 10-303). Live SCA on PZZ545 today: winds 15–25 kt gusts 30, seas 8–13 ft | UNSAFE for affected activity |
| Rip current risk | NWS product **SRF** (`/products/types/SRF/locations/MTR`) | Text tiers **Low / Moderate / High** per NWSI 10-320. Today’s MTR SRF had **0** “Rip Current” strings (High Surf only) — if parse fails, use snapshot + caveat, do not invent Low | UNSAFE if High (swim); caveat if unparsed |
| Missing **required live API** feed | — | If NWS alerts (or CO-OPS/NDBC when required by the row above) fail or are stale, the outcome is **UNKNOWN**, never GOOD | UNKNOWN |

---

## Part A — Data sources

### 1. Tide predictions, water levels, currents (NOAA CO-OPS)

**What this gives us / why TideWise needs it:** Predicted and observed tide heights, plus bay currents, so TideWise can tell whether a flat is low enough to clam or whether a harbor current is slack, flooding, or ebbing.

The provider is the National Oceanic and Atmospheric Administration (NOAA) Center for Operational Oceanographic Products and Services (CO-OPS). Heights in this section use the mean lower low water datum (MLLW).

- **Endpoint:** `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter`
- **Example (hi/lo, Pillar Point / SF):**  
  `?station=9414290&product=predictions&datum=MLLW&interval=hilo&units=english&time_zone=lst_ldt&format=json&application=tidewise&begin_date=20261119&range=24`  
  Hourly: `interval=h` or `interval=6`. Observed: `product=water_level&date=latest&datum=MLLW&time_zone=gmt`. Currents: `product=currents_predictions&station=SFB1203&interval=MAX_SLACK`. Metadata: `https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{id}.json`
- **Auth:** none
- **Update / latency:** predictions continuous; observed water level updates about every 6 minutes, and the delay is on the order of minutes
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

- **Missing / quirks:** JSON `error.message` when product not offered. Quality `q`: `p` preliminary. Flags `f` comma fields. **9414290 has wind but no water_temperature today** (lead held). **9414131** predictions OK; no water_level/temp/wind today. **9414805** returns the message “No Predictions data was found”.
- **Rate limits:** none published; be polite
- **Gotchas:** always pass `datum=MLLW` for this app; `time_zone=lst_ldt` vs `gmt`; current stations often need a **bin** (default used by API when omitted on SFB* today)
- **Backup:** none equivalent for tides; for wind/temp use NDBC/CO-OPS neighbors

#### Verified CO-OPS tide stations (this region)

| ID | Name | Lat | Lon | Notes (verified 2026-11-19) |
|----|------|-----|-----|-----------------------------|
| 9414290 | San Francisco | 37.8063 | -122.4659 | Predictions, plus water level (WL) and wind. **No water temperature (WTMP).** |
| 9414131 | Pillar Point Harbor | 37.5025 | -122.4822 | Predictions only (no water level (WL), water temperature (WTMP), or wind) |
| 9414750 | Alameda | 37.772 | -122.3003 | Predictions, plus water level (WL), and **water temperature (WTMP) 59.2°F** |
| 9414863 | Richmond | 37.9283 | -122.4 | Predictions, plus water level (WL), and **water temperature (WTMP) 61.2°F** |
| 9414523 | Redwood City | 37.5068 | -122.2119 | Predictions plus water level (WL). No water temperature (WTMP). |
| 9415020 | Point Reyes | 37.9942 | -122.9736 | Predictions, plus water level (WL), and water temperature (WTMP) 62.1°F |
| 9414575 | Coyote Creek | 37.465 | -122.023 | Predictions OK (far South Bay) |

#### Verified current stations (sample)

`SFB1201` is the San Francisco Bay Entrance. `SFB1203` is the Golden Gate Bridge, 0.46 nautical miles (nm) east. `SFB1212` is Raccoon Strait. `SFB1305` is the San Mateo Bridge. Realtime station `s08010` is Southampton Shoal LB6.

---

### 2. Buoy waves, wind, water temp (NOAA NDBC)

**What this gives us / why TideWise needs it:** Live wave height, wind, and water temperature from offshore buoys, so TideWise can judge surf, wind, and cold water.

The provider is the NOAA National Data Buoy Center (NDBC). WVHT is significant wave height. WTMP is water temperature. MM means the sensor did not report a value.

- **Endpoint:** `https://www.ndbc.noaa.gov/data/realtime2/{ID}.txt`  
  Spectral: `.../{ID}.spec`  
  Station catalog: `https://www.ndbc.noaa.gov/activestations.xml`
- **Example:** `https://www.ndbc.noaa.gov/data/realtime2/46012.txt`
- **Auth:** none
- **Update / latency:** typically every 10–60 minutes; rows are UTC
- **Resolution:** point; WVHT in meters, WSPD m/s, WTMP °C
- **Format:** space-separated text, 2 header lines. Sample **46012**:

```
#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE
#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft
2026 11 19 23 00 310 10.0 12.0   3.8    16    MM  MM 1012.4  14.0  18.9  10.2   MM +1.6    MM
```

**46237.spec:** The spectral columns are `WVHT SwH SwP WWH WWP SwD WWD STEEPNESS APD MWD`. The sample values are `3.3 2.6 15.4 2.1 8.7 W WSW SWELL 8.7 272`.

- **Missing:** **`MM`** means the value is missing. It is a sentinel, not a zero. Also reject 99/999-class sentinels if seen. The latest hour at station **46026** can show significant wave height (WVHT) equal to MM while earlier hours still have waves. Always scan the recent rows, not only the last line.
- **Rate limits:** none published
- **Gotchas:** units are metric on NDBC (convert for UI); fixed met stations often have no WVHT
- **Backup:** CO-OPS wind/WTMP; other NDBC IDs in table

#### Verified NDBC / partner IDs

| ID | Role | Status today |
|----|------|--------------|
| 46026 | San Francisco buoy, 18 nautical miles (nm) west | HTTP 200. Waves are intermittent (the missing marker MM appears on some hours). |
| 46012 | Half Moon Bay unmanned surface vehicle (USV) | HTTP 200. Significant wave height (WVHT) 3.8 m. |
| 46237 | San Francisco Bar, Coastal Data Information Program (CDIP) | HTTP 200. Swell comes from the `.spec` file. |
| 46214 | CDIP, farther offshore | HTTP 200 |
| 46013 | Bodega | HTTP 200. No significant wave height (WVHT) on the sample. |
| 46042 | Monterey | HTTP 200 |
| 46239 | Point Sur, CDIP | HTTP 200 but **stale** (last observation 2026-10-25). Do not treat this station as live. |
| FTPC1 | San Francisco CO-OPS meteorological station | HTTP 200 |
| AAMC1 | Alameda | HTTP 200. Water temperature (WTMP) 15.1°C. |
| RCMC1 | Richmond | HTTP 200 |
| PXOC1 | Pier 1 | HTTP 200 |
| TIBC1 | Tiburon | **HTTP 404** (not found) |
| HMBC1 | (guess) | **HTTP 404** (not found) |

---

### 3. Weather forecast & marine alerts (NWS api.weather.gov)

**What this gives us / why TideWise needs it:** Official forecasts and hazard alerts, so TideWise can block an activity when the weather service warns of dangerous wind, surf, or rip currents.

The provider is the National Weather Service (NWS), at api.weather.gov. SRF is the Surf Zone Forecast. CWF is the Coastal Waters Forecast. The User-Agent header (UA) is required.

- **Endpoints:**  
  - Points: `https://api.weather.gov/points/{lat},{lon}`, which returns grid MTR  
  - Hourly: `https://api.weather.gov/gridpoints/MTR/82,92/forecast/hourly` (Half Moon Bay area from points call)  
  - Grid raw: `https://api.weather.gov/gridpoints/MTR/82,92` (`windSpeed`, `waveHeight`, …)  
  - Alerts: `https://api.weather.gov/alerts/active?point=37.4636,-122.4286` or `?zone=PZZ545,CAZ509`  
  - Surf Zone Forecast: `https://api.weather.gov/products/types/SRF/locations/MTR` then `/products/{id}`  
  - Coastal Waters Forecast: `.../products/types/CWF/locations/MTR`
- **Auth:** none; **required** `User-Agent` identifying the app
- **Update / latency:** forecasts update about hourly; alerts immediate; SRF/CWF few times daily (SRF issued 2026-11-19T22:53Z)
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

**What this gives us / why TideWise needs it:** A daily satellite sea-surface temperature near the coast, so TideWise can describe how warm the ocean surface is when a buoy is missing.

This product is the Multi-scale Ultra-high Resolution (MUR) analysis, served by NOAA CoastWatch through ERDDAP (Environmental Research Division's Data Access Program). SST means sea-surface temperature. The griddap link is the subset request.

- **Endpoint:** `https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.csv?analysed_sst[(last)][(37.75)][(-122.9)]`
- **Auth:** none on ERDDAP. PODAAC NetCDF download needs Earthdata.
- **Update / latency:** daily; metadata: recent days revised; near real time (NRT) versus a final product (about 1–4 days). The sample time **2026-11-18T09:00:00Z** on 2026-11-19 is a lag of about 1 day.
- **Resolution:** 0.01°
- **Format:** CSV. Sample: `2026-11-18T09:00:00Z,37.75,-122.9,18.28` (°C). A land or coast pixel at `(-122.5)` comes back as **`NaN`**.
- **Missing:** NaN; mask variable available
- **Gotchas:** pick an offshore longitude at or below about -122.7 for this latitude (further west); `upwell.pfeg` responds with HTTP **302**, which redirects to the same host; **`coastwatch.noaa.gov` ERDDAP 502** today
- **Backup:** `https://oceanwatch.pifsc.noaa.gov/erddap/griddap/goes-poes-1d-ghrsst-RAN.csv?analysed_sst[(last)][(37.75)][(237.1)]` returns `291.35` **degree_K** (about 18.2°C). Longitude is on the 0–360 scale (Lon0–360). `noaacwBLENDEDsstDaily` **404** on OceanWatch today. CMR lists MUR granules.

---

### 5. Chlorophyll-a / HAB indicators

**What this gives us / why TideWise needs it:** A satellite chlorophyll estimate and a model probability of harmful-algal-bloom conditions, so TideWise can warn people to check the health advisory. These are early warnings, not a legal closure.

Chlorophyll-a is the field chla. HAB means harmful algal bloom. C-HARM is California Harmful Algae Risk Mapping.

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

**What this gives us / why TideWise needs it:** A status check on the C-HARM probability grids. The service answers only some of the time, and the newest model time is old, so TideWise must not present it as a current bloom probability.

Pseudo-nitzschia is the diatom that can produce domoic acid. Flapping means the same dataset was found, then missing, then found again during the probes. Stale means the model time has not moved forward.

**Datasets (CoastWatch West Coast ERDDAP, `https://coastwatch.pfeg.noaa.gov/erddap`):** `wvcharmV3_0day` (nowcast), `wvcharmV3_1day`, `wvcharmV3_2day`, `wvcharmV3_3day` (forecasts); `charmForecast0dayV2` is a legacy v2 dataset that ends **2022-11-30** — do not use.

- Variables: `pseudo_nitzschia`, `particulate_domoic`, `cellular_domoic`, `chla_filled`, `r486_filled`, `r551_filled`, `salinity`, `water_temparture` (typo is upstream). Fill `-99999.0` (JSON `null`).
- **Lon convention: 0–360** (axis 232.5–243.0, which is −127.5…−117.0 °E); grid 0.03°, lat 31.3–43.0 (391 lat × 351 lon values; `info` verified 2026-11-19 16:04 PST), time axis 1,166 values (not evenly spaced).
- Working query (2026-11-19 15:57 PST):  
  `https://coastwatch.pfeg.noaa.gov/erddap/griddap/wvcharmV3_0day.json?pseudo_nitzschia[(last)][(37.7):1:(37.7)][(237.2):1:(237.2)]`  
  The response is `["2026-11-02T12:00:00Z", 37.69, 237.21, 0.9121059]`

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
| 16:01:38 | `coastwatch.pfeg.noaa.gov` info returned **200**. `oceanview.pfeg.noaa.gov` info for `wvcharmV3_0day` returned **404** |
| 16:02:27 | info returned **200 but took 23.4 s** |
| 16:03:05, 16:03:22, 16:03:39 | info returned **503** (1.5–1.7 s) for `wvcharmV3_0day`; also 503 for `wvcharmV3_2day`, `wvcharmV3_0day_LonPM180`, `charmForecast0dayV2` (so the 503 hit the whole server, not just one dataset) |
| 16:04:02 | info returned **200** (0.86 s) |

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

**What this gives us / why TideWise needs it:** The legal health advisories for shellfish and crab, so TideWise can close a harvest even when satellite chlorophyll looks ordinary.

CDPH is the California Department of Public Health. CDFW is the California Department of Fish and Wildlife. There is still no single JSON feed of current advisory status. The live source is the dated news list, checked against the phone lines and the CDFW in-season page.

**There is no public REST/JSON "current advisory status" feed.** The authoritative *live, dated* source is the CDPH news-release list (HTML), cross-checked with the hotline and CDFW in-season page.

#### 6a. Live, dated sources (verified 2026-11-19 ~15:58 PST)

These are the pages that were actually retrieved. A row marked live has a dated item. A row marked static loaded, but it is not a current-status feed.

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
| CDPH RSS / GovDelivery | `…/Programs/OPA/Pages/NR_RSS.aspx` returned **404**. `/Pages/RSS.aspx` returned **404**. `public.govdelivery.com/accounts/CACDPH/subscriber/new` returned **404**. `/_layouts/15/listfeed.aspx` returned 200 HTML (not a feed) | — | **No RSS found** |

**Scrape structure (news list):** SharePoint page; each release = a headline line starting `CDPH …` (e.g. "CDPH Updates Northern Anchovy Consumption Advisory for Central California Waters") followed by a line beginning with the date, `November 17, 2026 — The California Department of Public Health (CDPH) …`. The page also embeds older archive lists (e.g. "News Releases 2017" links such as "CDPH Lifts Rock Crab Health Advisory in Portions of San Mateo County - South of Pillar Point") — **ignore items without a 2026 date**. Parse by regex `^(Month) \d{1,2}, 20\d\d —`.

#### 6b. TLS status of CDPH hosts (diagnosed 2026-11-19 ~15:58 PST)

TLS is the certificate check on HTTPS. The CDPH www host fails a strict check because the server leaves out an intermediate certificate. The workaround below is the one that was verified. Do not ship the insecure skip-verify option.

| Host | Strict TLS | Cause | Workaround |
|------|-----------|-------|-----------|
| `https://www.cdph.ca.gov/…` | **FAILS** — curl exit 60 / `verify=20`, `openssl: unable to verify the first certificate (21)`, Python `CERTIFICATE_VERIFY_FAILED` | Server presents leaf issued by **"Sectigo Public Server Authentication CA OV R36"** but sends a *different* intermediate ("Sectigo RSA Organization Validation Secure Server CA"), so the issuing intermediate is missing from the chain | **Preferred:** download the missing intermediate from the cert's AIA URL `http://crt.sectigo.com/SectigoPublicServerAuthenticationCAOVR36.crt` (DER; `openssl x509 -inform DER -out r36.pem`), append to the system CA bundle, and pass as `curl --cacert bundle.pem` / `requests.get(verify='bundle.pem')`. Verified: **HTTP 200, verify=0**. Quick-and-dirty: `curl -k` (probe only; do not ship). |
| `https://cdph.ca.gov/…` (apex) | **OK** (verify=0) but 302-redirects to `www.` (which fails) | — | Use apex only for the redirect check |

Leaf cert validity (openssl, 2026-11-19): notBefore Dec 31 2025, **notAfter Dec 31 2026** — re-check after rotation. `wildlife.ca.gov`, `smchealth.org`, `data.ca.gov` and `data.sf.gov` fetched fine with default TLS in this session; `oehha.ca.gov` and `webapps.sfpuc.org` were fetched using the bundle above (system roots + R36), so their strict-TLS status was not isolated.

#### 6c. CURRENT advisories affecting our coast (quoted from the CDPH list, retrieved 2026-11-19)

This is what the dated CDPH list said for the San Francisco, San Mateo, and Half Moon Bay coast on the retrieval day. Quotes stay as retrieved. Places far to the north or south are included so they are not mistaken for local closures.

**Honest conclusion: no active CDPH bivalve closure/quarantine and no Dungeness "do not eat" advisory currently covers Marin, San Francisco, or San Mateo (Half Moon Bay / Pacifica / SF Bay) — except the standing viscera recommendation and the anchovy advisory below.**

- **Annual mussel quarantine — ended.** Oct 28, 2026: "…the statewide annual quarantine on mussels taken for human consumption by sport-harvesters from California's ocean waters ends at midnight on Saturday, October 31, 2026." Source: https://www.cdph.ca.gov/Programs/OPA/Pages/Shellfish-Advisories.aspx (normal window May 1–Oct 31 per the Annual-Mussel-Quarantine page).
- **San Mateo County bivalve advisory — lifted.** May 26, 2026: "The California Department of Public Health (CDPH) has lifted the shellfish safety notification today related to sport-harvested bivalve shellfish from San Mateo County."
- **Anchovy advisory touching our southern boundary (current).** Nov 17, 2026: "The California Department of Public Health (CDPH) has updated its advisory for northern anchovies to include waters between: Pigeon Point, San Mateo County (37⁰ 11.00' N. lat.) and Point Lobos, Monterey County (36⁰ 31.46' N. Lat.)". CDFW In-Season (headline "Recreational Anchovy Take Restrictions Lifted in Monterey Bay", dated November 17, 2026), separately: "The recreational "bait only" fishing restriction for northern anchovy in the Monterey Bay area has been lifted, after state health agencies determined northern anchovy no longer poses a human health risk. The restriction prohibiting the commercial distribution of northern anchovy seafood products for human consumption remains in effect." (Sources: CDPH list above; https://wildlife.ca.gov/Fishing/Ocean/Regulations/Inseason.) Relevance: only Pigeon Point/south San Mateo and south — not HMB/Pacifica.
- **Nearest active Dungeness domoic-acid advisory (far north).** Nov 9, 2026: "The California Department of Public Health (CDPH) is warning the public not to consume any part of sport-harvested Dungeness crab (meat or viscera), caught from an area of the Northern California coast due to dangerous levels of domoic acid." Area per CDFW declaration (https://nrm.dfg.ca.gov/FileHandler.ashx?DocumentID=247966&inline=): "…from the southern boundary of the Reading Rock State Marine Protected Areas (41⁰ 17.6' N. latitude) to the southern boundary of the Ten Mile State Marine Reserve (39⁰ 33.3' N. latitude)." (~200+ nautical miles north of Half Moon Bay.) CDFW closure: https://wildlife.ca.gov/News/Archive/additional-recreational-dungeness-crab-area-delay-in-portions-of-humboldt-county-due-to-public-health-hazard (Nov 5, 2026).
- **Standing guidance that DOES apply locally.** OEHHA memo, Oct 30, 2026: "For other sections of the coast that will be open for recreational harvesting of Dungeness crab, CDPH and OEHHA continue to strongly recommend that consumers avoid eating the viscera (internal organs, also known as “butter” or “guts”) because they usually contain much higher levels of domoic acid than the meat." (https://oehha.ca.gov/sites/default/files/media/2026-10/FINAL%20DungenessCrab_RecFisheryMemo_103026.pdf)
- **Other nearest non-local items on the list:** Monterey County bivalve warning Sept 14, 2026, which was lifted Oct 12, 2026; Del Norte razor clam warning Oct 9, 2026; a San Luis Obispo County bivalve warning headline is present (date not extracted).

**Rule for the app:** treat "no active local CDPH advisory" as true only if the news list was fetched within the last 24 h and contains no 2026-dated release naming San Mateo/SF/Marin; always show the hotline number and a "last checked" timestamp.

#### 6d. CDPH ArcGIS layers — **NOT live status (static pins)**

The map layers answer queries, but their last edit dates are old. Do not treat a pin on the map as a current closure.

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

**What this gives us / why TideWise needs it:** Whether recent beach-water samples failed a bacteria test, so TideWise can mark swimming unsafe.

The state BeachWatch archive (SWRCB, on data.ca.gov) is not current. San Francisco's DataSF feed and San Mateo County's posting pages are the live sources.

**Bottom line (verified 2026-11-19 ~15:59 PST):** SWRCB BeachWatch (data.ca.gov) is **not live** — it ends in 2026-03 — but **two county-level feeds ARE live and dated within 2 days**: San Francisco (DataSF Socrata API) and San Mateo (County Health posting pages + RSS/WP-JSON).

#### 7a. San Francisco — DataSF "Beach Water Quality Monitoring" (**LIVE, queryable JSON**)

This is a real JSON API. ENTERO means Enterococcus. The data field is text and may include a less-than or greater-than qualifier instead of a plain number.
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
- Analytes: `ENTERO` (Enterococcus), `COLI_FECAL`, `COLI_TOTAL` (MPN/100 mL). **Quirks:** `data` is a **string** and may carry qualifiers (`<5`, `<10`); sorting `sample_date` uses the lowercase column name (asking for `SampleDate` returns an error). No lat/lon in this dataset: **join `source` to BeachWatch station table** (`https://data.ca.gov/api/3/action/datastore_search?resource_id=98e628ff-d012-4982-ad32-b9f9ad8ab524&q=OCEAN%2322`) where `AgencyStationIdentifier` = `source`, e.g. `OCEAN#22_SL` is "Fort Funston", Ocean Beach, 37.71526, −122.50476; `BAY#301.2_SL` is "Jack Rabbit Beach", beach name Candlestick Point (both verified in the station table). (Station table is static — good for geometry.)
- **Thresholds (state single-sample maxima, as quoted by San Mateo County):** total coliform 10,000; E. coli 400; Enterococcus 104 MPN/100 mL (geometric mean limits 1,000 / 200 / 35). Apply to SF `ENTERO` 104 for a simple flag.
- Human-facing: SFPUC map https://webapps.sfpuc.org/sapps/beachesandbay.html (200; page text lists 877-SFBEACH / 877-732-3224); program page https://sfwater.org/index.aspx?page=87 (200).

#### 7b. San Mateo County Environmental Health (**LIVE, dated HTML + RSS**)

San Mateo publishes weekly posting pages as WordPress posts. RSS and the WordPress JSON API are how to find the newest post. The list names sites that were posted, not every site that was sampled.
- Program page: https://smchealth.org/division/divisions/environmental-health-services/permits-business-services/water-protection-and-land-use/beach-creek-monitoring-program/ (200). Page states: "San Mateo County routinely tests 43 sites each week" and "Sites are sampled every Monday morning by a combination of County staff and volunteers, primarily associated with the local chapter of the Surfrider F[oundation]". Contact number on page: 650-372-6200 (County Environmental Health Services).
- **Posting pages are WordPress posts.** Latest (retrieved 2026-11-19): https://smchealth.org/8-27-beach-and-creek-updates/ — title "11/18/26 Beach and Creek Updates", "Posted on November 18, 2026 … based off samples collected November 16, 2026". (Slug is stale/reused; **discover the newest post by title/date, not slug**.)
- **Discovery:** `https://smchealth.org/wp-json/wp/v2/posts?search=Beach%20and%20Creek%20Updates&per_page=3&_fields=id,date,slug,link,title` returns `[{"id":1964,"date":"2026-11-18T09:30:34","slug":"8-27-beach-and-creek-updates","link":"https://smchealth.org/8-27-beach-and-creek-updates/","title":{"rendered":"11/18/26 Beach and Creek Updates"}}]` (200); RSS `https://smchealth.org/feed/` (200, `application/rss+xml`) also lists these posts (pubDate Wed, 18 Nov 2026 17:30:34 +0000).
- **Structure:** headings `BEACH (PACIFIC-SIDE) POSTINGS:`, `CREEK POSTINGS:`, `BEACH (BAYSIDE) POSTINGS:` then one site per line. Quoted current list (11/18/26): Pacific-side — "Linda Mar #5 (Linda Mar Blvd.)", "Fitzgerald Marine Reserve", "Pillar Point #5 (Capistrano Beach)", "Pillar Point #7 (Surf-West Point Ave)", "Pillar Point #9 (Outer Harbor)", "Venice Beach"; creeks — San Pedro, San Vicente (at Fitzgerald), North Roosevelt, Gazos; Bayside — Aquatic Park, Kiteboard Beach, Oyster Point, Lakeshore Park, Erckenbrack Park, Gull Park, Marlin Park. **The list is POSTINGS (sites with elevated bacteria); a site absent from the list is "not posted", not necessarily "sampled and clean".**
- Interactive map service `https://gis.smcgov.org/maps2/rest/services/HEALTH/BEACH_MONITORING_PRJ/MapServer` returns **HTTP 500 "Service … not started"** today (map backend down; do not depend on it).
- Older URL `smchealth.org/beach-monitoring` returns 404 (replaced by the URL above).
- Latency: samples collected on Monday are posted typically on Tuesday or Wednesday; stated lag ≈ 2 days. Cadence weekly.

#### 7c. SWRCB BeachWatch (data.ca.gov) — **STALE; historical only**

This statewide table still answers queries, but the newest sample dates are months old. Use it for station locations and history, not for today's posting.
Queried `datastore_search_sql` 2026-11-19 (max `SampleDate` in bacteria results): **San Mateo 2026-03-02**, **San Francisco 2025-10-28**, **Marin 2025-10-31**, all California **2026-03-05**; advisories table max `DateofAdvisory` **2026-03-06**. Use for station geometry and long-term history only. Resource IDs: advisories `d5cd6a23-829c-426d-a63e-689a55a3db9c`, bacteria `7bd961cf-abe4-433b-8033-378161237ff3`, stations `98e628ff-d012-4982-ad32-b9f9ad8ab524`.

#### 7d. Heal the Bay Beach Report Card / Surfrider BWTF

These sites loaded as web pages. Neither one yielded a confirmed machine-readable feed in this pass. BWTF is the Surfrider Blue Water Task Force.
- `https://beachreportcard.org/` returns 200 (HTML SPA). `https://beachreportcard.org/api/v1/locations` returns 200 but **6,788 bytes of `text/html`** (a shell, not JSON — only this path tested). `https://api.healthebay.org/` connection failed (curl code 000). **No machine-readable API confirmed** (not exhaustively searched). Report-card grades are seasonal/annual anyway.
- Surfrider Blue Water Task Force https://www.surfrider.org/programs/blue-water-task-force returns 200 (program page; no queryable feed found). The San Mateo program page says its Monday sampling is done by County staff and volunteers "primarily associated with the local chapter of the Surfrider F[oundation]"; results are published via the County posts above.

**Recommended best-available stack:** SF = DataSF `v3fv-x3ux` (daily, JSON) ; San Mateo = County posting post (weekly, scrape via WP-JSON/RSS) ; both with a "sampled {date}, posted {date}" staleness caveat (typically 2–9 days old) and the rule "avoid ocean contact during and 3 days after storms; stay 300 ft from creek mouths/storm drains" (San Mateo County Health program page: "avoid swimming in ocean waters during and for three days after a storm. When swimming in ocean waters, stay at least 300 feet away from flowing storm drains and creek mouths."). Fall back to BeachWatch only as "no recent data".

**Probe:** `scripts/research_probes/12_beach_live.sh`  
**Verified on:** 2026-11-19 (15:59–16:05 PST)

---

### 8. Fires and smoke (FIRMS, EONET)

**What this gives us / why TideWise needs it:** Nearby wildfire and smoke signals, so TideWise can warn that the air or the shoreline may be affected.

EONET is NASA's natural-event catalog. FIRMS is NASA's active-fire detection feed and needs a MAP_KEY. An EONET event marked open can still be years old.

- **EONET:** `https://eonet.gsfc.nasa.gov/api/v3/events?status=open&bbox=-123.2,37.2,-121.8,38.2&limit=20`  
  Sample returned 2 “open” wildfires with geometries dated **2024** — filter by geometry date / close stale events.
- **FIRMS:** `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/VIIRS_SNPP_NRT/-123.2,37.2,-121.8,38.2/1`  
  Without a key, the service returns `Invalid MAP_KEY.` Sign up: firms.modaps.eosdis.nasa.gov.
- **Auth:** FIRMS key required; EONET none
- **Backup:** NWS smoke/Air Quality alerts via api.weather.gov

---

### 9. UV and solar (NASA POWER + EPA)

**What this gives us / why TideWise needs it:** A same-day ultraviolet (UV) index for the beach, plus a slower solar record for context.

EPA Envirofacts is the same-day source. NASA POWER is the backup and lags by days. POWER is not an ocean product.

- **EPA Envirofacts (better for same-day UV):**  
  `https://data.epa.gov/efservice/getEnvirofactsUVDAILY/ZIP/94019/JSON` returns `{"UV_INDEX":"2","UV_ALERT":"0","DATE":"Nov/19/2026"}`  
  Hourly: `.../getEnvirofactsUVHOURLY/ZIP/94019/JSON` (`UV_VALUE` by hour).
- **NASA POWER:**  
  `https://power.larc.nasa.gov/api/temporal/daily/point?parameters=ALLSKY_SFC_UV_INDEX,ALLSKY_SFC_SW_DWN,T2M&community=RE&longitude=-122.5&latitude=37.7&start=YYYYMMDD&end=YYYYMMDD&format=JSON`  
  `fill_value: -999.0`. On 2026-11-19, **ALLSKY_SFC_SW_DWN** last non-fill **2026-11-14**; **T2M** last **2026-11-16**; **ALLSKY_SFC_UV_INDEX** all fill for the window. **Latency is about 2–5 days**; **no marine fields** — context only (lead held).
- **Backup:** each other

---

### 10. Seasonal SST climatology / anomalies

**What this gives us / why TideWise needs it:** How today's sea-surface temperature compares with the usual temperature for this day of the year.

An anomaly is the difference from that long-term average (the climatology). The climatology field is mean_sst.

- **Anomaly:** `jplMURSST41anom1day` `sstAnom` — sample `2026-11-17T09:00:00Z,37.75,-122.9,5.004` °C  
- **Climatology:** `jplMURSST41clim` variables **`mean_sst`**, **`standard_deviation`** vs `dayOfYear` (1–365) — sample DOY 322: mean **13.24** °C, sd **0.86**  
- **Lower-res:** `jplMURSST42` `sst_anomaly` in **kelvin** (sample 4.964)  
- **Auth:** none  
- **Gotchas:** clim variable is `mean_sst` not `sst`; anomaly dataset lag can differ from analysed_sst day

---

## Part B — Domain rules (brief, cited)

These are the activity rules the feeds above are meant to support. Where a rule was not fetched from a source, it stays marked unverified. MLLW is the tide datum. SCA is a Small Craft Advisory. SRF is the Surf Zone Forecast.

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

This list is what not to trust as settled. Unverified means the item was not confirmed from a source fetched for this document. The C-HARM, CDPH, and beach-bacteria updates from the later pass are included here as well.

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
