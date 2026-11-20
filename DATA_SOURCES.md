# TideWise Data Sources

Every feed below was checked live on 2026-11-19 (Pacific time). The scripts that ran those checks are in `scripts/research_probes/`.

**Key acronyms:** NOAA = National Oceanic and Atmospheric Administration · NASA = National Aeronautics and Space Administration · NWS = National Weather Service · CO-OPS = NOAA's tides and currents office · NDBC = National Data Buoy Center · ERDDAP = NOAA's satellite data server · SST = sea surface temperature · CDPH / CDFW = California Department of Public Health / Department of Fish and Wildlife · EPA = Environmental Protection Agency

| What we need | Main source (why) | Backup | Watch out for |
|---|---|---|---|
| Tides, water level, currents | **NOAA CO-OPS** (`api.tidesandcurrents.noaa.gov`): official tide predictions, live water levels, and Bay current forecasts. No key needed. | None that's reliable. | Some stations have no predictions or no water temperature (e.g. `9414290` San Francisco). |
| Waves, wind, water temperature | **NDBC buoys** (`realtime2/{id}.txt`): live readings every 10 to 60 minutes. | CO-OPS stations `9414750` (Alameda) and `9414863` (Richmond). | `MM` means missing, not zero. Some buoys go stale (`46239`). |
| Weather and marine alerts | **NWS** (`api.weather.gov`): forecasts plus small craft, gale, and rip current alerts. Needs a User-Agent header. | Open-Meteo (unverified). | Rip current text is sometimes missing, so the parser has to tolerate that. |
| Satellite water temperature | **NOAA ERDDAP** `jplMURSST41`: daily NASA JPL satellite SST at about 1 km. | OceanWatch `goes-poes-1d-ghrsst-RAN`. | Two ERDDAP servers returned 502 errors today. Pixels at the shoreline come back empty. |
| Chlorophyll and algal blooms | **ERDDAP** `erdVHNchla8day` (satellite chlorophyll) plus C-HARM bloom risk `wvcharmV3_0day`. | `erdVHNchla1day` (fails on cloudy days) and `noaa_snpp_chla_daily`. | This is an early warning only, never a legal closure. C-HARM is about 17 days stale. |
| Shellfish / biotoxin closures | **CDPH** shellfish advisories and **CDFW** health advisories (web pages, no API). | CDPH hotline (800) 553-4133. | The CDPH site has a broken TLS certificate chain, and its map layers are 2020 snapshots. |
| Beach bacteria | **DataSF** `v3fv-x3ux` (SF Enterococcus results) plus San Mateo County postings. | None. | EPA BEACON has no live API. BeachWatch stopped updating. |
| Fires and smoke | **NASA EONET** events near the Bay. | **NASA FIRMS** fire detections (needs a free key). | Events marked "open" in EONET can be years old. |
| UV and sunlight | **EPA** UV index by ZIP code. | **NASA POWER** daily sunlight and air temperature. | POWER has no ocean data and lags by 2 to 5 days. |
| Water temperature vs. normal | **ERDDAP** `jplMURSST41anom1day` and `jplMURSST41clim`. | `jplMURSST42`. | Don't compute "normal" from a single buoy. |

## Safety rules

- Safety checks run before any score. A closure (CDPH/CDFW), a bacteria exceedance (EPA Enterococcus 70 cfu/100 mL), or an NWS small craft, gale, or rip current alert forces **CLOSED** or **UNSAFE**.
- **UNKNOWN** appears only when a live safety feed the activity needs is down or stale. Sources without an API use a dated snapshot that says when it was last verified.
- Cached data is always labeled with its fetch time and lowers the confidence score.

The full, detailed version (request URLs, parameters, samples) is in git history at `2dadcd6`.
