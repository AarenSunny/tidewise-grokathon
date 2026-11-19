# TideWise — Review of Phase 2

- **Reviewed commit (main HEAD at review time): `62185cd9c7d7dcf5a192e023e260634bfb14234d`** (`62185cd`)
- Scope: Phase 2 build commits `0d08bf3` (probes + `scripts/probes/REPORT.md`), `0528875`, `9fa1e7b`; research rounds 2–3 (`6265787`, `ed08814`, plus `ffd0e94`/`214c7a0` session exports); and the later deploy PR (`eb58052`, merge `3b25a4d`: `render.yaml`, `frontend/vercel.json`, `frontend/src/api.js`) because it puts main on a public host.
- Reviewer: independent review session. No application code modified. Review date 2026-11-19 (America/Los_Angeles), ~15:50–16:10.
- Method: diffed `f50ae9d..HEAD`; reran `scripts/probes/run_all.py` myself (copy outside the repo; **26/26 OK at 15:51 PST**); re-queried the endpoints behind every new DATA_SOURCES claim (CO-OPS, NDBC, ERDDAP metadata + data, USNO, sunrise-sunset.org, data.ca.gov SQL, CDPH ArcGIS layer metadata, CDPH HTML, EPA UV); fetched the CCR text from Cornell LII to check the quoted regulations; re-ran my Phase 1 probes against the unchanged adapter/model code; ran `pytest` (**3 passed**, unchanged).
- Note: a `phase3-wip` branch exists on origin with adapter/validation work. Per instructions it is **not reviewed here**; all re-review statuses below refer to **main only**.

## Scope note — what changed in main since Phase 1

`git diff --stat f50ae9d HEAD -- backend tests` is **empty**. Phase 2 added **no application code**: probes, a probe report, docs, and deploy config. Consequently **every REVIEW_1 code finding is still present in main** (re-verified by rerunning the Phase 1 probes: same output). Still **not yet in main**: concrete adapters, gate engine, FeatureEngine, scorers, bots, orchestrator, Leaflet map (not findings).

## REVIEW_1 fix status (main @ HEAD)

| # | R1 finding | Status in main | Evidence |
|---|---|---|---|
| 1 | Gate contract not default-deny | **Not fixed** | `backend/models/scoring.py:29` `eligible: bool = True`; `backend/models/common.py:25-36` no validator; probe: contradictory `GateResult` and gate-less eligible window still construct; `backend/config/__init__.py:22-25` returns raw dict |
| 2 | Freshness = fetch time, no `observed_at` | **Not fixed** (and now empirically worse, see N4) | `backend/models/sources.py:13-24` unchanged; `backend/adapters/base.py:53,86-94` |
| 3 | Stale cache keyed on exact window | **Not fixed** | `base.py:48-49`; probe: 1 µs shift → `down` |
| 4 | No max stale age / no eviction | **Not fixed** | `backend/cache/memory.py:33-41`; `base.py:116-122` |
| 5 | Cache round-trip changes data type | **Not fixed** | `base.py:71,95`; probe: live `Obs` vs cached `dict` |
| 6 | Timeout not enforced for blocking code; no deadline | **Not fixed** | `base.py:79-83`; probe: blocking 1.0 s with `timeout_s=0.3` → `ok` |
| 7 | Indiscriminate retries | **Not fixed** | `base.py:85,104-114`; probe: deterministic validation error → 3 live calls |
| 8 | No validation layer; models accept junk; None/empty = ok | **Not fixed** | `base.py:146-148`; `backend/models/features.py` unchanged; probe accepted `wind=-5, dir=999, NaN` |
| 9 | HealthMonitor disconnected; `/debug/fail` inert | **Not fixed** | grep: only `api.py` touches the monitor |
| 10 | TZ contract undefined | **Not fixed** (new sources add more conventions, N8) | `features.py:16`, `intent.py:32-33`; DATA_SOURCES still advises `lst_ldt` |
| 11 | Gate coverage gaps | **Not fixed** (new evidence, N3) | `backend/config/activities/*.yaml` unchanged |
| 12 | Spot data vs research mismatch | **Not fixed** | `backend/config/region.yaml` unchanged (null station ids, same coords) |
| 13 | Error strings w/ URLs logged/exposed | **Not fixed** (exposure grew: public deploy, N9) | `base.py:105-112`; `backend/api.py:39-45` |
| 14 | No single-flight / concurrency control | **Not fixed** | probe: 5 concurrent identical fetches → 5 live calls |
| 15 | Debug default-on, wildcard CORS, dead config | **Partially mitigated** for the *deployed* instance only: `render.yaml:18-19` sets `DEBUG=false`. `.env.example:5`, `api.py:22-27`, `Makefile:11` unchanged; `.env` still never loaded | |
| 16 | Tests don't match claims | **Not fixed** | still 3 smoke tests; nothing covers the probe runner either |
| 17 | Personal e-mail in history | **Not fixed**, slightly worse (N11) | author metadata of `f80b73c`, `3b25a4d`, `eb58052` |
| 18 | CDPH TLS verification disabled | **Not fixed / now in committed build code** | `scripts/probes/run_all.py:56,492` (`ssl._create_unverified_context()`); research script still `curl -k` |
| 19 | Misc base-class quality / unpinned deps | **Not fixed** | `requirements.txt` unchanged; now consumed by `render.yaml:12` |

## Findings (worst first; numbering restarts, prefix **N** = new in Phase 2)

### N1 — BLOCKER — The clamming "no biotoxin closure" gate has no verified machine-readable live source
- `scripts/probes/run_all.py:424-466`, `DEVLOG.md:79` ("ArcGIS FeatureServer OK. Prefer ArcGIS."), `scripts/probes/REPORT.md` (`cdph_arcgis_*` rows "yes"), `backend/config/activities/clamming.yaml:13-15`
- **What's wrong:** I queried the two ArcGIS layers the build chose as the "stable" shellfish source:
  - `Health_Advisory_Symbols_(Red)/FeatureServer/0`: 21 county **map pins** with fields only `County_Name, Latitude, Longitude, x, y` — no status, date, species or advisory text; layer `dataLastEditDate` = **2020-08-25**. Probe "ok" only proves the county names exist.
  - `All_Bivalve_Shellfish_Health_Advisory_Special_Advisory/FeatureServer/3`: a single feature, "Special Advisory Area - Northern Channel Islands", last edited **2025-07-10**; layer 0 (Text) empty.
  - The actual current CDPH advisories (e.g. Nov 9 sport-Dungeness warning, Nov 17 anchovy advisory) exist only as HTML news items on `cdph.ca.gov` whose certificate chain is incomplete (strict TLS fails: "unable to get local issuer certificate", reproduced with curl).
- **Scenario:** An adapter that treats "county symbol present" as a closure flag marks SF/San Mateo/Marin *permanently* closed; one that treats "no special-advisory polygon intersects" as "no closure" **passes the gate on a layer that cannot represent a closure** (fail-open), or someone "fixes" it with `verify=False`.
- **Fix:** Declare the shellfish gate **unverifiable** until a source with per-county/species status *and* a date is found (CDPH Recreational Shellfish Advisory Map data service, or the HTML page with a pinned intermediate CA and a positive-control parse). Until then clamming must return "cannot confirm — call (800) 553-4133 / check CDPH", never eligible. Record the layer `lastEditDate` in `observed_at`; reject layers older than N days. Update DEVLOG/REPORT to retract "Prefer ArcGIS".

### N2 — BLOCKER — The swimming bacteria gate's only source is ~8 months stale; swimming can never pass (or passes on stale data)
- `backend/config/activities/swimming.yaml:3-9`, `DATA_SOURCES.md:367-373`
- **What's wrong:** Verified via data.ca.gov SQL: bacteria dataset `MAX(SampleDate)` = **2026-03-05** (San Mateo latest 2026-03-02); advisories dataset max `DateofAdvisory` = **2026-03-06**. BeachWatch is a historical bulk dataset, not an operational nowcast. The config requires `alerts_bacteria` for every swim recommendation.
- **Scenario:** With default-deny (as R1 #1 demands) *no* swim window is ever eligible; with a stale-tolerant adapter the gate "passes" on March data — exactly what the safety rule forbids.
- **Fix:** Product decision recorded in config: either (a) swimming is shown as "bacteria status unconfirmed" with an explicit uncapped-confidence-limit and a link to county/Heal the Bay, never as a green "safe" gate, or (b) find an operational source (county EH pages returned 404 per DATA_SOURCES.md:373). Add `max_age` per source so a March sample can't satisfy a gate in November.

### N3 — MAJOR — Crabbing recommendations can be illegal for the configured spot and gear; research data isn't reflected in config
- `backend/config/region.yaml:34` (`sf_bay` lists `crabbing`), `backend/config/activities/crabbing.yaml`, `DATA_SOURCES.md:574`
- **What's wrong:** I verified on Cornell LII: 14 CCR §29.85(b)(1) — *"Dungeness crab may not be taken from or possessed if taken from San Francisco Bay and San Pablo Bay… between the Golden Gate Bridge and Carquinez Bridge"*; §29.85(c) — other *Cancer* crabs are all-year, limit 35, 4 in min. DATA_SOURCES.md:574 states the Bay ban itself, yet the config still advertises Dungeness-style crabbing in the Bay and has no species, zone or gear dimension. The doc also quotes CDFW: crab **traps are prohibited in Zones 1–5 until at least Jan 1 2027** (hoop nets/snares/hand only), and the research notes **unreconciled** hoop-net-count text. `crabbing.yaml` has only `season_open`.
- **Scenario:** "Crabbing at San Francisco Bay Saturday" returns a good score with no species/gear caveat → user sets traps (prohibited) or keeps Dungeness (illegal in the Bay).
- **Fix:** Add `species` and `gear` to the crabbing model; encode (spot-zone → species allowed), the trap-restriction window as a dated config entry with a source URL and an expiry that forces "cannot confirm" after that date; never display a hoop-net count (the research doc says it's unreconciled); add domoic/CDPH crab advisory as a required source (see N1).

### N4 — MAJOR — Feeds that return HTTP 200 but are frozen/old are marked "ok" by the probes, and nothing measures it (R1 #2 now proven)
- `scripts/probes/run_all.py:361` (`r.ok = status == 200 and expect_col in cols`), `REPORT.md` summary table
- **Evidence (my rerun, 15:51 PST):** C-HARM `wvcharmV3_0day` last time **2026-11-02T12:00Z** (`time_coverage_end` same; **17 days**); VIIRS 8-day chl last **2026-11-09** (**10 days**); MUR SST 2026-11-18T09Z (~38 h); MUR anomaly 2026-11-17; NDBC 46239 row stamped 2026-10-25 (25 days, correctly flagged by the probe); POWER lags 4–5 days. All of these show **OK=yes** in the probe summary.
- **Scenario:** `swimming.yaml` gate `no_bloom` (`chl_bloom_flag`) is evaluated on a 10-day-old composite and C-HARM on a 17-day-old nowcast with confidence unaffected; the sailing/clamming factors can use any buoy that still answers HTTP 200.
- **Fix:** Per-source freshness budget in config (e.g. NDBC ≤ 2 h, CO-OPS observed ≤ 30 min, NWS alerts ≤ 15 min, MUR ≤ 72 h, 8-day chl ≤ 12 d, C-HARM ≤ 3 d, POWER not used). Compute age from the data's own timestamp (see R1 #2); probes should print age and flag `FROZEN` instead of `ok`.

### N5 — MAJOR — DATA_SOURCES.md and REPORT.md assert a C-HARM "outage/unpublished" that no longer holds; docs now mislead the adapter design
- `DATA_SOURCES.md:291-293,669`, `scripts/probes/REPORT.md` "Live outage timeline", DEVLOG "Real-world data issues"
- **What's wrong:** At ~15:35–15:40 PST research recorded 404 for `wvcharmV3_0day`/`charmForecast0dayV2` and "catalog empty"; the build probe saw 404 then global 503 at ~15:34. At **15:51** all four ERDDAP probes returned **200**, `info/wvcharmV3_0day`, `charmForecast0dayV2`, `erdVHNchla8day`, `jplMURSST41` and `jplMURSST41anom1day` returned 200, and the C-HARM `(last)` query works. The doc instructs engineers to "treat C-HARM as DOWN/unpublished". The real behavior is **flapping (404 → 503 → 200 within ~20 min)**, and ERDDAP's 404 "Currently unknown datasetID" appears transiently when datasets reload.
- **Scenario:** The build drops or hard-disables C-HARM; or conversely maps 404 to "dataset renamed → permanent failure" and caches the negative result for a day.
- **Fix:** Rewrite the doc status as "intermittent availability; `(last)` stalled at 2026-11-02"; treat ERDDAP 404/502/503 as transient (retry with backoff, then stale-with-age); regenerate REPORT.md or label it as a point-in-time snapshot. Keep this episode as a real test fixture for the failure-handling tests (outside `backend/`).

### N6 — MAJOR — Insecure-TLS helper committed into build code; probe "ok" flags give false assurance
- `scripts/probes/run_all.py:56,483-498`
- **What's wrong:** `_req(..., insecure=True)` uses `ssl._create_unverified_context()`. The CDPH TLS probe marks `ok=yes` after strict TLS **failed** and the insecure retry succeeded; the ArcGIS probes mark ok on "features key present" (N1). A future adapter author will naturally import this helper.
- **Scenario:** The closure feed is fetched with verification off → a captive portal/MITM page can say "no advisory".
- **Fix:** Delete the `insecure` option from committed code (or keep it behind a clearly named `--unsafe-probe-only` flag in a script that is never imported). Probe ok must mean "usable for the gate" (HTTP ok **and** fresh **and** parseable **and** verified TLS). For CDPH, pin the missing intermediate certificate (the server omits it) rather than disabling verification.

### N7 — MAJOR — Source latency budgets don't fit the adapter defaults (8 s timeout × 3 attempts)
- `backend/adapters/base.py:34-37`; `scripts/probes/REPORT.md` (BeachWatch 1994 ms) vs my rerun
- **Evidence:** `beachwatch_bacteria_datastore` (`datastore_search` with `q=`) took **36.6 s** on my run vs 2.0 s in the committed report (same script); the SQL endpoint with an indexed filter returned in **0.4 s**. ERDDAP `griddap` 0.8–1.0 s; CO-OPS 0.3 s; NWS 0.05–1.2 s.
- **Scenario:** A 36 s response is cancelled at 8 s three times (≈25.5 s of retries) and then reported "down" while the source is merely slow; for a stale source (N2) it is wasted latency in every request.
- **Fix:** Per-adapter timeout/deadline config (e.g. 5 s CO-OPS/NWS/NDBC, 20 s ERDDAP, skip BeachWatch bulk in the request path and refresh it in the background), prefer indexed SQL queries with `ORDER BY … LIMIT`, and run slow/stale sources off the request path (background refresh + age-flagged cache).

### N8 — MAJOR — Time conventions across the sources now differ five ways; the new sunrise guidance adds DST traps and the legal clamming window isn't the "daylight" gate
- `DATA_SOURCES.md` §11 (USNO / sunrise-sunset.org), `backend/config/activities/clamming.yaml:10-12`, `backend/models/features.py:24-25`
- **Verified live:** USNO `rstt/oneday?...&tz=-8&dst=false` → Rise 06:54, Set 16:56, End civil twilight 17:25, labelled ST; sunrise-sunset.org `formatted=0` → sunrise 14:54:05Z, sunset 00:56:40Z (consistent). CO-OPS `lst_ldt` returns offset-less local text; NDBC and ERDDAP are UTC; EPA UV returns `"DATE_TIME":"Nov/19/2026 07 AM"` (local, text, hour-ending/starting not defined); VIIRS/C-HARM `time` is a composite label, not a sample time. USNO takes a caller-supplied numeric `tz` (the doc notes `dst=true` with `tz=-8` still returned `isdst:false`), so a wrong offset silently shifts sunrise by an hour. Per 14 CCR §29.20(b) (verified on LII) legal clam-digging hours are **½ h before sunrise to ½ h after sunset**, which is not what an `is_daylight` boolean encodes.
- **Scenario:** In March/November a hard-coded `tz=-8` gives a 1-hour error in the daylight/legal-hours gate; an hourly bucket straddling sunrise is mis-scored; EPA UV hour label shifted by an hour.
- **Fix:** One time module: everything to aware UTC at the adapter edge; compute sunrise/sunset **offline** from lat/lon (astral/NOAA algorithm) and use USNO only as a **test oracle** (not a live dependency); encode clamming "legal hours" as `[sunrise−30 min, sunset+30 min]`; define composite-time semantics (store window start/end) and test on DST transition days (2026-03-08, 2026-11-01).

### N9 — MAJOR — The public deployment exposes the Phase 1 weaknesses; main auto-deploys unreviewed code with unpinned deps
- `render.yaml:5-23` (`autoDeploy: true`, `branch: main`, `pip install -r requirements.txt`, `--host 0.0.0.0`), `backend/api.py:22-27,39-45`, `backend/models/api.py:18`
- **What's wrong:** Good: `DEBUG=false` is set in the blueprint, `XAI_API_KEY` is `sync: false` (no secret committed), `/debug/*` returns 404 when off. Problems: anyone can call `/health` and read `last_error` strings (R1 #13) once adapters exist; CORS is `*`; `/query` accepts unbounded text with no rate limit (xAI cost); deps are `>=` unpinned so each deploy can pull a breaking FastAPI/pydantic/openai release (and runtime is Python 3.11.9 while I tested on 3.13; no CI at all); every push to main (including WIP) goes live; in-memory cache is lost on free-plan spin-down, so "serve stale" is empty after every cold start (R1 #3/#4).
- **Fix:** Pin versions (lockfile), add CI running the tests on 3.11, deploy from a protected/tagged branch, restrict CORS to the Vercel origin, add `max_length` + rate limit on `/query`, redact `/health` errors, and persist the last-known-good cache (SQLite/file) if stale-serving is a judged feature.

### N10 — MAJOR — Satellite pixels at the spot coordinates are frequently null; chl/bloom gate can rarely be evaluated
- `scripts/probes/REPORT.md` null-count notes (reproduced), `backend/config/region.yaml`, `backend/config/activities/swimming.yaml:13-15`
- **Evidence (rerun, tiny bbox near HMB):** MUR SST 11/36 pixels null, VIIRS 8-day chl **22/49 null**, C-HARM 4/64 null; earlier I also saw null MUR SST at the `sf_bay` spot cell. VIIRS chl longitudes are −180…−110 while C-HARM uses 0–360 and MUR −180…180 (verified from dataset metadata) — three conventions. `chla` fill is −999 (JSON null).
- **Scenario:** Spot lat/lon lies in a masked coastal pixel → `chl_bloom_flag=None` → `cannot_confirm` ≈ half the time → swimming rarely eligible; or an adapter that falls back to `0`/mean "passes" the bloom gate. Chl > 5 mg m⁻³ (Nezlin) is also an open-coast bloom marker, not a toxin test (the research doc says so), and the Bay "protective ≈ 13" is a different regime — a single threshold is wrong for both.
- **Fix:** Spatial neighbourhood search (nearest valid ocean pixel within a distance cap, with the distance reported), per-region thresholds in config, explicit `None` handling, and document the lon convention per dataset in the adapter constants (with a unit test that converts −122.5 → 237.5 for C-HARM only).

### N11 — MINOR — More personal e-mail addresses in public commit metadata
- Author/committer metadata of merge `3b25a4d` (a personal hotmail address) and `eb58052` (a tool address), in addition to R1 #17. Not reproduced here. The session transcripts under `grok-sessions/` were scanned (keys, tokens, e-mails, absolute paths, internal ids): **clean**; only the `hanzhizhu12` GitHub handle appears.
- **Fix:** Use GitHub noreply addresses for future commits/merges; consider squash-merging via the UI with noreply.

### N12 — MINOR — Documentation drift and un-triaged review
- `DEVLOG.md:79` (ArcGIS "prefer"), `DEVLOG.md` Phase 2 "Reviewer findings: N/A" even though `REVIEWS/REVIEW_1.md` has been in main since `aa178d2`; `scripts/probes/REPORT.md` is a timestamped snapshot that already disagrees with live behaviour (N5, N7).
- **Fix:** Add a "REVIEW_1 triage" table to DEVLOG (fixed / won't fix / deferred, with commit), retract the ArcGIS claim, and mark REPORT.md as a dated snapshot (or regenerate it in CI).

## DATA_SOURCES.md rounds 2–3 — claim-by-claim check

| Claim | Result |
|---|---|
| CO-OPS predictions (9414290, 9414131) and `water_level latest`, `datum=MLLW`, ft | **Confirmed** (live ids/units). `f` QC flag string (`"0,0,0,0"` in the build probe; I earlier saw `"1,0,0,0"`) and `q=p` still **not turned into a rule** in the doc; an adapter must reject/flag non-zero flags. |
| CO-OPS currents `SFB1201`: knots, ebb negative, `Velocity_Major` | **Confirmed** (`units: "feet, knots"` — the "feet" is bin depth; don't read it as speed). Predictions only (no observed currents) — must be labelled as predictions. |
| NDBC realtime2: UTC, WSPD/GST m/s, `MM` | **Confirmed** (header `m/s`; 46237 wind all `MM`; 46239 stale 25 days). Doc covers only `MM`; no `99/999` handling documented — keep per-column sentinel table (R1 #8). |
| ERDDAP dataset IDs, lon conventions, `(last)` freshness | **Confirmed**; IDs are up (see N5). Freshness numbers confirmed (N4). C-HARM thresholds (10,000 cells/L; 500 ng/L; 10 pg/cell) are model-probability definitions from metadata — OK as documented. |
| "C-HARM DOWN / unpublished" | **Contradicted** at 15:51 (N5). |
| Tiered chl thresholds (Nezlin >5; Sutula 13/25–40) | Sources cited by the doc; **not independently re-derived** by me. They apply to different regimes (N10). Not a toxin test; doc says so. |
| USNO / sunrise-sunset.org sunrise & sunset for 37.5025,-122.4822 | **Confirmed** (06:54/16:56 PST; 14:54:05Z/00:56:40Z). Note coordinates are Pillar Point, not the `half_moon_bay` spot in config (R1 #12). NOAA Solar Calculator has no API (agree). |
| BeachWatch freshness (bacteria max 2026-03-02/05, advisories 2025-10/2026-03) | **Confirmed**; consequence in N2. |
| CDPH ArcGIS "stable shellfish source" (DEVLOG) | **Not supported** (N1). CDPH HTML TLS failure **confirmed** (missing intermediate). |
| CCR §29.85 (Dungeness SF/San Pablo Bay ban, 10/5¾ in; other Cancer all year, 35/4 in), §29.20 (fishing hours ½ h before sunrise–½ h after sunset; hand tools) | **Confirmed verbatim** on Cornell LII. §29.25/§29.35/§29.40 and §29.80 quotes **not re-fetched** (only §29.85 and §29.20 were). |
| CDFW 2026–27 trap restriction (Zones 1–5 until ≥ Jan 1 2027), hoop nets/snares allowed | Taken from quoted CDFW pages; **not re-fetched by me**; the doc itself flags the hoop-net-count conflict and loop-trap/"crab trap" wording tension as **unreconciled** — agree, do not hard-code. |

## Checklist coverage (Phase 2)
1. **Safety gates** — Still not built; new source-level blockers N1, N2 (no usable closure/bacteria feed), N3 (legal gating).
2. **Validation/sentinels** — Not built (R1 #8). Probe code only does `MM`/`-999` shape notes.
3. **Failure handling** — Real outage observed and documented (404→503→200); base class behaviour unchanged (R1 #3–#7, #9).
4. **Mocks on live path** — None; probes are standalone scripts and make real calls. No fixtures committed.
5. **Confidence** — Still no computation; inputs missing (N4).
6. **ExplainerBot** — Not built; no test.
7. **TZ/datum/units/off-by-one** — N8; datum MLLW/units confirmed live; composite-time semantics open.
8. **Concurrency** — Not built; probe runner is sequential (`run_all.py` ~51 s total), latency budgets N7.
9. **Security** — No keys/tokens committed; `render.yaml` clean; insecure-TLS helper N6; e-mails N11; transcripts clean.
10. **Depth** — Still not in main.

## What's good in Phase 2
- A real, rerunnable probe harness; honest recording of the ERDDAP outage; stale NDBC 46239 caught; CO-OPS/NDBC/NWS/ERDDAP/USNO claims reproduce; research doc candidly lists unreconciled legal text; `render.yaml` sets `DEBUG=false` and keeps the xAI key out of the repo.

## Summary
- **Top risk:** The two hardest safety gates have no usable live source — shellfish closures (ArcGIS layers are 2020/2025 static pins; real advisories are HTML behind broken TLS) and bacteria (BeachWatch ends in March) — and crabbing config contradicts the CCR (Dungeness in SF Bay, trap ban) (N1–N3), while every Phase 1 code defect is still in main.
- **Quick win:** Retract "Prefer ArcGIS" and mark shellfish/bacteria gates `cannot_confirm` in config now; add per-source `max_age` + frozen-feed flag to the probe `ok`; remove `insecure` from `run_all.py`; fix the C-HARM "DOWN" note.
- **Readiness: 3/10** (data research is solid and reproducible, but no code fixes landed in main, and the deployment is public).
