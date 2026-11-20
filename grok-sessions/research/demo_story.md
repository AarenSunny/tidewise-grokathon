# TideWise demo story: one Saturday, clamming then crabbing

Verified 2026-11-19 (America/Los_Angeles). Every endpoint below was called during research; sample values are from **today (Nov 19)** to show the pipeline, not a forecast for the demo day. Detail and quotes: `DATA_SOURCES.md` and `grok-sessions/research/DATA_SOURCES_full.md`.

## The plan: Saturday, December 5, 2026, Half Moon Bay / Pillar Point

**Tide (real, CO-OPS predictions, station 9414131 Pillar Point Harbor, MLLW, local time incl. DST):**
Low **14:44 = −0.27 ft** (only daytime Saturday minus in Nov 28 – Dec 31). Same day: low 01:08 (2.12 ft), high 07:29 (6.06 ft), high 21:15 (3.95 ft).
Honest framing: this is a *shallow* minus. Deeper minuses fall on weekdays (e.g. Wed Nov 25, 17:20, −1.77 ft) or at night on Saturdays (Nov 28 19:58, −0.96 ft; Dec 26 18:45, −1.32 ft). The app should score the −0.27 ft low as "marginal", not "great".

**Daylight (USNO, 37.50 N −122.50 E, UTC−8):** civil twilight begins 06:41, sunrise 07:10, sunset **16:52**, civil twilight ends 17:21. So the 14:44 low leaves about two hours of light after it, which suits "clams first, crabs after".

### Step by step

| Step | Question | Data source and endpoint (all verified) | Result in the story |
|---|---|---|---|
| 1. Pick the day | When is a minus tide on a weekend? | CO-OPS `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=predictions&station=9414131&datum=MLLW&time_zone=lst_ldt&units=english&interval=hilo&format=json&begin_date=20261128&end_date=20261231&application=...` | Sat Dec 5, low 14:44, −0.27 ft |
| 2. Is it legal and safe to eat? | CDPH closure check | Scrape CDPH news list `https://www.cdph.ca.gov/Programs/OPA/Pages/Shellfish-Advisories.aspx` (dated releases; hotline (800) 553-4133). `www.` host needs the Sectigo R36 intermediate added to the CA bundle (probe `11_cdph_live.sh`). | See "Closure status" below |
| 3. Surf and wind | Is the beach workable? | NDBC 46012 (Half Moon Bay) `https://www.ndbc.noaa.gov/data/realtime2/46012.txt` (WVHT, DPD; `MM` = missing); NWS alerts `https://api.weather.gov/alerts/active?point=37.4636,-122.4286` (User-Agent required) | Nov 19 sample: 46012 WVHT 3.8 m; Small Craft Advisory active on PZZ545 (seas 8–13 ft). A real Dec 5 morning check would gate the plan. |
| 4. Water | Water temp and bloom hints | MUR SST ERDDAP `https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.json?analysed_sst[(last)][(37.6)][(-122.7)]`; VIIRS chl `erdVHNchla8day` (variable `chla`, altitude `(0.0)`) on the same host | Nov 19 sample: SST 18.77 C (2026-11-18T09Z); chl 1.81 mg m^-3 (8-day, 2026-11-09). Fallback host `upwell.pfeg.noaa.gov` returned the same values (one 503 then OK). |
| 5. Toxin early warning | C-HARM | `wvcharmV3_0day` on CoastWatch (lon 0–360) | **Stale**: last model time 2026-11-02, and the server flaps (404/503). The app shows "C-HARM stale" and leans on CDPH. |
| 6. Light | Safe window | USNO `https://aa.usno.navy.mil/api/rstt/oneday?date=2026-12-05&coords=37.50,-122.50&tz=-8` | Sunset 16:52 |
| 7. Crab rules | Is crabbing open and what gear? | CDFW In-Season page `https://wildlife.ca.gov/Fishing/Ocean/Regulations/Inseason` and Whale Safe Fisheries page; CCR Title 14 sections quoted in `DATA_SOURCES_full.md` Part B | Recreational Dungeness season opened Nov 7 per press coverage; Humboldt/Mendocino area delayed for domoic acid (see below). Whether a trap restriction covers our zone on Dec 5 was **not confirmed**: re-check CDFW before showing. |
| 8. Beach water quality | Swim/wade check | San Mateo: `https://smchealth.org/wp-json/wp/v2/posts?search=Beach%20and%20Creek%20Updates` (latest "11/18/26 Beach and Creek Updates", samples Nov 16). SF: `https://data.sf.gov/resource/v3fv-x3ux.json` (latest sample 2026-11-17). | Pillar Point #5/#7/#9 and Fitzgerald Marine Reserve were on the Nov 18 posting list |

### Closure status (real, found 2026-11-19)

**No CDPH bivalve closure or Dungeness do-not-eat advisory was found for Marin, San Francisco or San Mateo.** Dated items from the CDPH list (https://www.cdph.ca.gov/Programs/OPA/Pages/Shellfish-Advisories.aspx):
- Oct 28, 2026: statewide annual mussel quarantine "ends at midnight on Saturday, October 31, 2026."
- May 26, 2026: CDPH "has lifted the shellfish safety notification today related to sport-harvested bivalve shellfish from San Mateo County."
- Nov 9, 2026: warning not to eat sport-harvested Dungeness crab (meat or viscera) from an area of the Northern California coast, Reading Rock SMP (41°17.6' N) to Ten Mile SMR (39°33.3' N), about 200+ nm north of Half Moon Bay (CDFW declaration: https://nrm.dfg.ca.gov/FileHandler.ashx?DocumentID=247966&inline=).
- Nov 17, 2026: northern anchovy advisory updated for Pigeon Point (37°11' N) to Point Lobos (not our beaches).
- Standing guidance that applies here (OEHHA memo, Oct 30, 2026): CDPH and OEHHA "strongly recommend that consumers avoid eating the viscera".
The demo should say "no local advisory found as of the check time" with a timestamp and the hotline, never "safe".

## Slide outline: "Data sources & scoring" (for judge Q&A)

1. **Sources (free, no keys):** NOAA CO-OPS (tides), NDBC (waves/wind/SST), NWS api.weather.gov (alerts, forecast, surf zone), NASA/NOAA ERDDAP: MUR SST, VIIRS chl-a, C-HARM; CDPH/CDFW advisories; DataSF and San Mateo County beach data; USNO sunrise/sunset.
2. **Latency (observed):** CO-OPS, NDBC and NWS: per-source latency is in `DATA_SOURCES.md`; ERDDAP 0.6–1 s typically, with 503s and one 23 s response; CDPH and county pages are scrape-and-cache.
3. **Fallbacks:** ERDDAP `coastwatch.pfeg` then `upwell.pfeg` (MUR also on `oceanview.pfeg`); `coastwatch.noaa.gov` and `polarwatch` returned 502 or were unreachable today. Every feed is cached with an age stamp and shows UNKNOWN or STALE rather than a guess.
4. **How each feeds the score:**
   - Tide: minus depth and timing relative to the clamming window drives the clamming score (the −0.27 ft Dec 5 low scores "marginal"); slack and daylight drive crabbing.
   - NDBC/NWS: wave height, period and alerts act as a **hard gate** (Small Craft Advisory, High Surf, Rip Current Statement make the activity UNSAFE).
   - CDPH/CDFW: advisory or quarantine for the area is a **hard gate** for eating shellfish; absence is reported as "none found at time T".
   - SST and chl: soft inputs (comfort for swimming/sailing; high chl is a caution flag for CDPH, not a legal rule).
   - Beach bacteria: caution flag for swimming and wading, with sampled-date caveat.
5. **Known gaps (say these out loud):** C-HARM about 17 days stale and flapping; CDPH has no API or RSS and its `www.` host has a TLS chain fault; the CDPH ArcGIS map layers are static 2020 pins; BeachWatch ended (Mar 2026); no NASA PACE chlorophyll on ERDDAP; minus-tide depth on Saturdays is shallow in this window; trap-restriction status for our zone on Dec 5 unconfirmed; the ERDDAP WMS overlays and the hoop-net and loop-trap reconciliation were not completed in this pass.
