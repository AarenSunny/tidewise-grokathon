# TideWise — Review of Phase 1

- **Reviewed commit (main HEAD at review time): `f50ae9d5c81450ad7de6595e3c5a1dc0246dc898`** (`f50ae9d`)
  - Phase 1 scaffold = `cdb01b5`; build session exports = `21be27d`, `89b781b`; this HEAD additionally adds `DATA_SOURCES.md` + `scripts/research_probes/` (research session).
- Reviewer: independent review session. Application code was not modified.
- Review date: 2026-11-19 (America/Los_Angeles)
- Method: read every tracked source file, never relied on README / DEVLOG / comments, ran the test suite, and wrote throwaway probes (kept outside the repo) that exercise `SourceAdapter`, `MemoryTTLCache`, `HealthMonitor`, the models and the FastAPI app. Spot-checked `DATA_SOURCES.md` claims against the live endpoints.

## Scope note: what exists in main at f50ae9d

Phase 1 is a **scaffold**: pydantic models, an abstract `SourceAdapter` (timeout/retry/TTL/stale logic), `MemoryTTLCache`, `HealthMonitor`, FastAPI stubs (`/health`, `/spots` work; `/query`, `/recommend` return 501), YAML activity configs, 3 placeholder spots, 3 smoke tests.

**Not yet in main (so NOT findings; each is marked N/Y below):**
- No concrete adapters (NDBC, CO-OPS, NWS, ERDDAP SST/chl, alerts, CDPH) — only the abstract base. **Nothing in main calls a live endpoint.**
- No FeatureEngine, no activity scorers / gate engine (tide windows, daylight gating, nearest-beach ranking, chlorophyll bloom gates) — arriving later as separate PRs.
- No IntentBot / ExplainerBot (`backend/bots/` is empty), no Orchestrator (stub raises `NotImplementedError`), no Leaflet map (frontend is a static placeholder shell).
- Uncommitted Phase 2 work (e.g. `scripts/probes/run_all.py`) exists in the build session's working tree on the shared box; it is **not** in main and was **not** reviewed.

Because of that, many checklist items cannot be verified yet; where a *design hole* is already visible in the contracts, it is reported as a finding (these will bite as soon as adapters/scorers land). Where nothing exists, it is said plainly.

## Test run

`pytest -q` (Python 3.13, fresh venv from `requirements.txt`): **3 passed in 0.07 s**. The 3 tests only check that YAML/model loading works. **There are no tests for `SourceAdapter`, the cache, `HealthMonitor`, the API, gates, or validation**, so none of the "timeout, retry/backoff, TTL cache, stale serve" claims in DEVLOG/README are covered by the suite. I verified them with my own probes (see findings; what works is credited under "What works").

## Findings (worst first)

### #1 — BLOCKER — Safety-gate contract cannot enforce "missing/unknown never passes"
- `backend/models/common.py:25-36` (`GateResult`), `backend/models/scoring.py:21-30` (`ScoredWindow`, esp. line 29 `eligible: bool = True`), `backend/config/__init__.py:22-25`, `backend/config/activities/*.yaml`
- **What's wrong**
  1. `GateResult` allows `passed=True, cannot_confirm=True` at once (verified: constructs without error). "Missing never passes" is only a docstring.
  2. `ScoredWindow.eligible` **defaults to `True`** and `gates` defaults to `[]`. A window built with no gates (score 100, confidence 1.0) is eligible — verified. A scorer that forgets/skips a gate, or a gate that raises and is swallowed, yields an eligible window. Default must be deny.
  3. Gates are free-text strings in YAML (`rule: "shellfish_closure not active"`, `rule: rip_current_risk != high` — the first is not even an expression, the second compares against an unquoted token). `load_activity_config` returns a raw `dict` with no schema, so a typo in `missing:`, a deleted gate, or a misspelled `required_sources` entry silently loads. If a rule evaluator ever uses `eval`/expression parsing on these strings that is also an injection/ambiguity risk.
  4. The gate inputs have **no home in the feature model**: `HourlyFeatures` has no `shellfish_closure`, `season_open`, `bacteria_advisory`, `rip_current_risk`, `small_craft_advisory`, `thunderstorm_alert` (only `active_alerts: list[str]` and `chl_bloom_flag`). Every gate input is therefore an ad-hoc lookup waiting to default to `None`/falsey.
  5. `required_sources` names are not a registry and don't agree with each other (`coops_tides`, `coops_currents`, `alerts_shellfish`, `alerts_bacteria`, `nws_alerts`, `nws_forecast`, `nws_marine`, `ndbc_buoy`, `satellite_chl`); nothing validates them against adapters.
- **Scenario:** CDPH page adapter is down → shellfish-closure value is `None` → the scorer's `if not closure:` evaluates truthy → `no_biotoxin_closure` "passes" and the window is `eligible=True`. The scaffolding does nothing to stop this.
- **Fix:** Make `GateResult` a validated tri-state (`pass | fail | cannot_confirm`), with a `model_validator` forcing `passed=False` when `cannot_confirm`. Remove the `eligible` default; derive it (computed field) as "gate set == the activity's required gate set AND every gate is `pass`". Replace string rules with a typed `ActivityConfig` Pydantic schema (`field`, `op`, `threshold`, `missing: Literal["fail"]`, `source`), validated at startup (unknown fields/sources → refuse to boot). Add explicit boolean/enum fields for every gate input to `HourlyFeatures`, `Optional` with `None` ⇒ cannot_confirm, and a test per gate for None/stale/down inputs.

### #2 — BLOCKER — Freshness is judged on fetch time, not observation time; stale observations are `ok`
- `backend/adapters/base.py:53,86-94`, `backend/models/sources.py:13-24`
- **What's wrong:** `SourceResult` has no `observed_at` / `data_as_of`. `fetched_at=now`, `valid_until=now+ttl`, `status=ok` whenever the HTTP call and `_validate` succeed. A feed that happily returns an old record is "ok" and "fresh". `DATA_SOURCES.md` documents exactly these cases: C-HARM `(last)` was 17 days old (2026-11-02 on 11-19), POWER lags 4–5 days, EONET "open" fires include stale events; I additionally saw `jplMURSST41` `(last)` = `2026-11-18T09:00Z` (~38 h old) and NDBC rows whose latest timestamp is ~1 h behind wall clock. Nothing in the model lets confidence or a gate see that.
- **Scenario:** NDBC buoy stuck reporting a 9-hour-old wind obs: adapter returns `ok`, sailing "no gust spread" and wind factors score on 9-hour-old wind with confidence unaffected.
- **Fix:** Add `observed_at` (newest sample timestamp, UTC) and per-source `max_age` in config; the base class computes `age = now - observed_at` and sets `stale` (or `down` for safety-critical sources) when `age > max_age`, independent of cache TTL. Confidence/gates must consume age, not `status` alone.

### #3 — MAJOR — Stale-cache fallback keyed on exact window; effectively never hits in real use
- `backend/adapters/base.py:48-49` (`cache_key` uses `start.isoformat()`/`end.isoformat()`), `:116-131`
- **What's wrong:** Key includes microsecond-exact `start`/`end`. Verified: after a successful fetch, the same call shifted by 1 µs returns `down / no_stale_cache` when live fails. Any caller that derives windows from `now()` (every `/recommend` without explicit `start`) misses the cache every time, so the "serve stale on failure" claim (README "Robustness") doesn't hold. Naive vs aware datetimes also produce different keys.
- **Scenario:** NWS is down at 15:05; the 15:00 run cached data under window 15:00:00.123–…; the 15:05 request has a different `start`; result: `down` even though a 5-minute-old valid payload exists.
- **Fix:** Key by `(source, station/grid id, product)` and cache the *superset* series; slice windows after retrieval; or quantise windows to the hour in UTC before keying.

### #4 — MAJOR — Stale data has no maximum age and the cache never evicts
- `backend/cache/memory.py:33-41`, `backend/adapters/base.py:116-122,133-140`
- **What's wrong:** `get_stale` returns an entry however old (verified); `_store` is never pruned (grows with every distinct key — and see #3, keys are nearly unique per call). Stale results carry no age and no downgrade beyond `status=stale`.
- **Scenario:** A tide/alert payload from 3 days ago is served as `stale` on an outage; a gate consumer that treats `stale` as "usable" passes on 3-day-old closure info. Long-running server leaks memory.
- **Fix:** Per-source `max_stale_age`; beyond it return `down`. Safety sources (closures, alerts) should have a very short max stale age (or none ⇒ gate = cannot_confirm). Add LRU/size cap + periodic purge.

### #5 — MAJOR — Cache round-trip changes the type of `data` (live ≠ cached shape)
- `backend/adapters/base.py:71,95`, `backend/models/sources.py:16` (`data: Any`)
- **What's wrong:** Live path returns whatever `_validate` returns (verified: a pydantic model `Obs`); cache hit/stale returns `model_dump(mode="json")` output (verified: `dict` with ISO strings; datetimes no longer datetimes). Same adapter, two shapes depending on cache state. Exotic types (numpy, pandas, bytes) would make `model_dump(mode="json")` raise **inside the try block**, so *good* data is reported as a failed fetch and retried 3×.
- **Scenario:** FeatureEngine does `obs.t.hour` → works on first request, `AttributeError` on the second (cache hit), swallowed by a broad `except` somewhere → silently dropped input.
- **Fix:** Make `SourceResult` generic with a typed payload (each adapter returns a Pydantic model) and re-parse that model on cache read; move cache serialization out of the retry `try`.

### #6 — MAJOR — Timeout is not enforced for blocking adapter code; no overall deadline
- `backend/adapters/base.py:79-83`, `:36-37`
- **What's wrong:** `asyncio.wait_for` only works for cooperative awaits. Verified: with `timeout_s=0.3`, an adapter doing a blocking call for 1.0 s returned `status=ok` after 1.00 s (event loop frozen, timeout ignored). ERDDAP/NetCDF (xarray/netCDF4), `requests`, pandas CSV parsing are all sync. Also worst case per adapter per request = 3×8 s + 0.5 + 1.0 s ≈ **25.5 s**, with no total deadline, and a failure is never negatively-cached so every request pays it again (verified: failure path re-calls live each time).
- **Fix:** Use `httpx.AsyncClient` with explicit connect/read timeouts; run any sync parsing via `asyncio.to_thread`; enforce an overall per-adapter deadline (e.g. 10 s total) and a per-request orchestrator deadline; add a circuit breaker / negative cache (e.g. 60 s after N failures).

### #7 — MAJOR — Retries are indiscriminate (validation errors and 4xx retried); no jitter, no `Retry-After`
- `backend/adapters/base.py:85,104-114`
- **What's wrong:** Everything raised, including deterministic `_validate` errors (sentinel/range) and permanent HTTP 4xx, is retried max times with backoff (verified: validator raising ⇒ 3 live calls). This hammers NOAA/NWS with identical bad requests (NWS asks for politeness; 429/503 `Retry-After` ignored), and delays the response ≈1.5 s+ for no benefit.
- **Fix:** Classify errors: retry only timeouts/connect errors/5xx/429 (honour `Retry-After`, add jitter); fail fast on 4xx and on validation errors.

### #8 — MAJOR — No validation layer exists: `_validate` is a bare abstract; models accept impossible values; empty/None passes as `ok`
- `backend/adapters/base.py:146-148,85-94`, `backend/models/features.py:13-43`
- **What's wrong (checklist #2):** Not built — there is no sentinel table (NDBC `99/999/9999/MM`, POWER `-999`, ERDDAP `-99999`/`null`), no range table, no unit conversion helper, and no tests. Moreover:
  - `HourlyFeatures` has **no field constraints**: verified it accepts `wind_speed_kt=-5`, `wind_dir_deg=999`, `moon_phase=7`, `sst_c=-99`, and `tide_height_ft_mllw=NaN`.
  - Base class does not reject `None`/empty payloads: verified a validator returning `None` yields `status=ok, data=None` and caches it as ok.
  - Validation is all-or-nothing (raise ⇒ discard whole record + retry); real NDBC rows are routinely partially `MM` (live `46026`: `DPD/ATMP/DEWP/VIS` = `MM`; live `46237`: `WDIR/WSPD/GST` = `MM`), so a naive raise would make good wave data unusable, while a naive `float()` would pass `99`.
- **Fix:** Shared `validation.py` with a per-field sentinel table (NDBC `MM`/`99`/`999`/`9999`, POWER `-999`, ERDDAP `-99999`/`null`; sentinels are column-specific, e.g. `999` is invalid for wind speed but must be checked per column) and a per-field range table (wind 0–75 m/s, gust ≥ wind, WVHT 0–25 m, WTMP/SST −2–40 °C, direction 0–360, tide roughly −5–15 ft MLLW). Reject NaN/inf, convert bad fields to `None` individually (not whole-record raise), and treat `None`/empty series as `down`. Add `Field(ge=, le=)`/validators on the feature models, and unit tests for each sentinel per adapter.

### #9 — MAJOR — HealthMonitor is disconnected from adapters; `/debug/fail` does nothing; "ok" when nothing reported
- `backend/health.py:16-60`, `backend/api.py:29,39-45,68-82`, `backend/adapters/base.py:9-10,46`
- **What's wrong:** Nothing calls `record_success/record_failure` (grep: only `api.py` touches the monitor), despite the docstring "HealthMonitor callback". The debug `forced_down` flag lives in `HealthMonitor`, while adapters read their own constructor argument `forced_down` — they are never linked, so the README's "Failure injection: POST /debug/fail/{source}" demo (a judging criterion: robustness) cannot work as wired. Also: `set_forced_down(name, False)` does not restore status (verified: after fail→reset, source stays `down`); `overall_status()` returns **"ok" with zero adapters** (unknown reported as healthy — the same unknown-as-ok pattern as #1); `record_failure` marks `down` even when a stale value was served; `/debug/fail/<anything>` creates unbounded health entries and echoes arbitrary strings into `/health` (verified with `<img src=x>`).
- **Fix:** Inject the monitor into adapters (base class reports every outcome, incl. `stale` and age); make the monitor the single source of truth for forced-down and have `fetch` consult it; validate `source` against the adapter registry; initial state `unknown` (and overall `degraded/unknown` if any source has never reported); restore status on reset.

### #10 — MAJOR — Time-zone contract is undefined; DATA_SOURCES steers the build to ambiguous local times
- `backend/models/features.py:16` (`hour: datetime`, comment says "local region tz"), `backend/models/intent.py:32-33`, `backend/api.py:62-63`, `backend/models/spots.py:38`, `DATA_SOURCES.md:88` and `scripts/research_probes/01_coops_tides.sh:20,23,26` (`time_zone=lst_ldt`)
- **What's wrong:** Nothing requires timezone-aware datetimes: `HourlyFeatures(hour=datetime(2026,11,19))` is accepted naive (verified); `QueryIntent.start/end` and `/recommend?start=` accept naive strings. `RegionConfig.timezone` is an unchecked string. CO-OPS with `lst_ldt` returns wall-clock strings with **no offset** (live: `"t":"2026-11-19 07:15"`); during the DST fall-back hour (first Sunday of Nov) these are ambiguous, and they must be mixed with NDBC (UTC), ERDDAP (UTC `Z`) and NWS (ISO with offset). Hourly-grid semantics (start-of-hour vs centre; `end` inclusive/exclusive) are unspecified, so off-by-one at window edges is likely.
- **Fix:** Normalise everything to aware UTC at the adapter boundary; request CO-OPS with `time_zone=gmt` (live-verified to work) and convert via `zoneinfo.ZoneInfo(region.timezone)` only for display/daylight; add a validator rejecting naive datetimes in all models/API params; define `HourlyFeatures.hour` = start of hour UTC, `[start, end)` half-open, with a DST-day test.

### #11 — MAJOR — Gate coverage gaps in the activity configs (domain safety)
- `backend/config/activities/{crabbing,swimming,sailing,clamming}.yaml`; evidence in `DATA_SOURCES.md:332,414,456`
- **What's wrong**
  - **crabbing**: only `season_open`; no domoic-acid/CDFW health-advisory gate and no alert source in `required_sources`, yet DATA_SOURCES.md:332 notes an Oct 30 2026 sport-Dungeness advisory; no daylight/wind/surf/small-craft gate.
  - **swimming**: water temperature (SF ≈ 10–17 °C; live buoy 18.8 °C) is only a *weight*, no cold-water or high-surf/hazardous-surf gate; a window can score well while unsafe. `uv` weight has no declared source (`ALLSKY_SFC_UV_INDEX` was all −999 per DATA_SOURCES.md:414; EPA UV is the stated backup but not in `required_sources`).
  - **sailing**: only SCA + thunderstorm; no gale/storm/hazardous-seas/dense-fog/high-surf gate, no hard wave or gust ceiling.
  - **clamming**: Spot model has no MPA/no-take/closure attribute although DATA_SOURCES.md:456 says Montara SMR / Pillar Point SMCA must not be recommended; nothing prevents recommending illegal take.
  - Weights: nothing says what happens when a weighted factor is missing (renormalising over present factors would inflate scores).
- **Fix:** Add the missing gates (all `cannot_confirm`⇒fail), add `no_take`/`mpa` flag to `Spot` and a gate, declare every weighted source in `required_sources`, and define missing-factor handling: missing factor ⇒ contributes 0 *and* lowers confidence, never renormalise.

### #12 — MAJOR — Spot data contradicts the research doc; placeholders carry no station IDs
- `backend/config/region.yaml:9-38`, `DATA_SOURCES.md:54,177-179,455,505`
- **What's wrong:** All spots have `tide_station_id: null`, `buoy_ids: []`, `nws_grid: null` ("Placeholder"). Coordinates don't match the researched ones: Half Moon Bay is `37.4636,-122.4286` (State Beach, "exposed surf" per DATA_SOURCES.md:505) while the researched grid/station are for Pillar Point `37.5025,-122.4822` (`MTR/80,94`); live NWS `points` for the config coordinate gives `MTR/82,92`, not 80,94 (Pacifica `MTR/81,99` matches live). `clamming` is listed for Half Moon Bay/Pacifica open-surf beaches, but DATA_SOURCES.md:455 says "open high-energy surf beaches are poor clam habitat". `sf_bay` lat/lon is a single point for a whole bay, and live MUR SST at that cell returned `null` (land/coastal mask) on the last day.
- **Scenario:** A missing station id must be `cannot_confirm`; if adapters default to a "nearest/any" station the recommendation uses another place's tide.
- **Fix:** Fill IDs from DATA_SOURCES (resolve via metadata API), use the researched coordinates, make adapters raise on null station ids (→ gate cannot_confirm), pick SST/chl pixels with a coastal-valid neighbour search, and review activity↔spot assignments.

### #13 — MAJOR — Error strings (possibly containing credentials/URLs) are logged and persisted/exposed
- `backend/adapters/base.py:105-112,121,130`, `backend/models/sources.py:21`, `backend/models/sources.py:34`, `backend/api.py:39-45`
- **What's wrong:** `last_error = f"{type(exc).__name__}: {exc}"` goes to logs, to `SourceResult.notes`, into the cache, and (via `AdapterHealth.last_error`) to the public `/health`. httpx exceptions embed the full URL; verified a message containing `https://x/api/KEY123/foo` is logged and stored verbatim. FIRMS area API puts `MAP_KEY` in the URL **path** (`scripts/research_probes/05_fires_uv_beach.sh:98-101`), and xAI keys appear in headers/URLs in some SDK errors. No secret exists in the repo today (see #17) — this is a latent leak.
- **Fix:** Central `redact()` (strip query strings/path segments matching key patterns, known secret env values) applied before logging/storing; expose only error class + coarse reason on `/health`.

### #14 — MAJOR — No single-flight / concurrency control around adapters
- `backend/adapters/base.py:51-131`; `backend/orchestrator.py:8-12`
- **What's wrong (checklist #8):** The orchestrator is a stub, so "adapters run in parallel" is **not yet verifiable**. At the adapter level: verified 5 concurrent identical fetches ⇒ **5 live calls** (no request coalescing), no shared `httpx` client/connection pool, no per-host semaphore. Combined with #6/#7, a page load with 3 spots × N adapters can fan out many retries to NOAA/NWS, and cache-miss stampedes on TTL expiry.
- **Fix:** Per-key `asyncio.Lock`/in-flight-future map in `fetch`; shared `AsyncClient` with limits; orchestrator should `asyncio.gather(..., return_exceptions=True)` with a global deadline (verify when built).

### #15 — MAJOR — Debug endpoints: default-on config, wildcard CORS, no auth; config file never read
- `.env.example:5-6`, `backend/api.py:22-27,33-36,68-82`, `Makefile:11`, `requirements.txt` (pydantic-settings / python-dotenv unused)
- **What's wrong:** Gating itself works (verified: 404 when `DEBUG` unset, 200 when true). But `.env.example` ships `DEBUG=true` and README says `cp .env.example .env`; dev server binds `0.0.0.0` (`Makefile:11`, `API_HOST=0.0.0.0`); CORS is `allow_origins=["*"]`, `allow_methods=["*"]` (verified preflight to `/debug/reset` returns `access-control-allow-origin: *`), so any website open in the developer's/demo browser can flip sources to `down` via cross-origin POST. No auth/token. Conversely nothing loads `.env` (grep: no `load_dotenv`/`BaseSettings`), so `UPSTREAM_TIMEOUT_S`, `UPSTREAM_MAX_RETRIES`, `NWS_USER_AGENT`, base URLs etc. are **dead config**: values are hard-coded class attributes (`base.py:34-37`), and `DEBUG` in `.env` has no effect unless exported.
- **Fix:** Default `DEBUG=false` in the example; bind `127.0.0.1` by default; restrict CORS origins to the Vite dev origin; require a debug token header for `/debug/*`; actually load settings (pydantic-settings) and wire them into adapters.

### #16 — MAJOR — Test coverage does not match claims
- `tests/test_models_smoke.py` (22 lines, 3 tests); DEVLOG.md "Bugs found"
- **What's wrong:** No tests for adapter timeout/retry/stale, cache TTL, health transitions, API (`/spots` regression was "fixed" per DEVLOG but is untested), nor any gate/validation test. Phase 1's key claims are unverified by the suite (I verified the base behaviour manually).
- **Fix:** Add `tests/test_adapter_base.py` (timeout, retry classification, stale, forced-down, cache hit type parity), `test_health.py`, `test_api.py`, and per-gate `None/stale/down ⇒ cannot_confirm` tests as soon as scorers land.

### #17 — MINOR — Personal e-mail address present in public git history
- Author metadata of commit `f80b73c` (initial skeleton) contains a personal Gmail address (not reproduced here since this report is public). All later commits use a `users.noreply.github.com` address.
- **Scenario:** Address scraped from the public repo.
- **Fix:** Optional — not fixable without history rewrite; use GitHub noreply (`git config user.email`) going forward, and accept or rewrite the single early commit before submission if desired.

### #18 — MINOR — CDPH probe disables TLS verification; must not leak into the adapter
- `scripts/research_probes/06_cdph_shellfish.sh:11,16,21` (`curl -k`); `DATA_SOURCES.md` Risks table ("CDPH TLS")
- **What's wrong:** The shellfish-closure feed is the single most safety-critical source (gate for clamming). If the production adapter copies the probe and sets `verify=False`, a MITM or a captive-portal HTML page could say "no closure" ⇒ gate pass. Also CDPH is HTML/ArcGIS scraping: an HTML layout change that yields an empty list must be `cannot_confirm`, not "no closures".
- **Fix:** Never `verify=False`; if CDPH's chain is broken, pin the intermediate CA or mark the source `cannot_confirm`. Treat "parsed zero closures" from HTML as suspicious unless a positive control string/known structure is found.

### #19 — MINOR — Base-class code quality / dependency hygiene
- `backend/adapters/base.py:53,79,84` (`now` captured *before* up to ~25 s of retries and used as `fetched_at`; `asyncio.get_event_loop()` deprecated — use `time.monotonic()`), `:138` (no-op `result.fetched_at = result.fetched_at`), `:137` (stale notes accumulate across serves), `memory.py:25-31` (returns the cached dict by reference ⇒ downstream mutation corrupts cache); `requirements.txt` (all `>=`, no lock; `pytest` in runtime requirements; `frontend/package.json` has no lockfile); `backend/models/api.py:18` (`QueryRequest.text` has no `max_length`; unauthenticated LLM-bound endpoint ⇒ cost/abuse once IntentBot exists); `.env.example:11` (`GROK_MODEL=grok-2-latest` — unverified that this model name is current).
- **Fix:** Fix each as noted; pin versions with a lockfile; cap `text` length and add basic rate limiting before enabling the LLM path.

## DATA_SOURCES.md cross-check (requested)

There are **no adapters in main**, so claims cannot be checked against adapter code; I spot-checked them against live endpoints and against the Phase 1 contracts:

| Claim | Result |
|---|---|
| CO-OPS `datagetter` predictions (9414290, 9414131), `water_level` `date=latest`, `datum=MLLW`, `units=english` | **Confirmed live** (predictions in ft MLLW; `water_level` returns `v,s,f,q`). |
| "Use `time_zone=lst_ldt` for local" (`:88`) | Works, but **returns offset-less local strings**; recommend `gmt` (also works live). See #10. |
| CO-OPS `f` flags / `q=p` | DATA_SOURCES shows `f` but doesn't say what to do with it. Live value `"f":"1,0,0,0"` (first flag = data-limit exceeded) appeared on the latest water-level row. Adapter must treat non-zero `f` flags as invalid/low-confidence. Gap in the doc. |
| NDBC `realtime2/<id>.txt`: UTC time, WSPD/GST **m/s**, WVHT m, `MM` missing (`:125-137`) | **Confirmed live** (header `m/s`, `m`, `degC`). Doc lists only `MM`; the checklist's `99/999` sentinels (older NDBC formats/other columns) aren't mentioned. Wind must be converted m/s→kt (`wind_speed_kt` field exists; no converter exists). |
| 46026 waves+wind; 46237 "waves+WTMP; wind MM" | **Confirmed live**: 46237 has `WDIR/WSPD/GST = MM`, so wind needs a fallback buoy/NWS (fallback chain claimed in README is not built). |
| NWS grids: Pacifica `MTR/81,99` | **Confirmed**. Half Moon Bay `MTR/80,94` is for Pillar Point coords; region.yaml's HMB coords resolve to `MTR/82,92` (see #12). |
| NWS alerts by point | Works live (`point=` returns Coastal Flood Advisory + **High Surf Advisory** for the SF point) — confirms swimming/sailing need a high-surf gate (#11). |
| ERDDAP `jplMURSST41` | Reachable; **null SST** at the `sf_bay` spot cell and `(last)` ≈ 38 h old (#2, #12). Doc's lon convention note for C-HARM (0–360) not re-tested. |
| POWER UV all −999; EPA UV backup | Not re-tested; doc states it, config still weights `uv` with no declared source (#11). |
| "Missing marker MM (confirmed)" etc. | OK. `Risks & Unverified` table is honest; items flagged there (CCR bag limits, rock crab, DA zones, Heal the Bay TLS) remain **unverified** and must not be hard-coded. |

## Checklist coverage summary

1. **Safety gates** — Not built (no gate engine); contract holes are #1, #4, #9, #11, #18.
2. **Validation / sentinels** — Not built; no per-adapter validation exists (#8).
3. **Failure handling** — Base class works for: async timeout, 3 retries with exponential backoff, stale-on-failure *for identical keys*, forced-down→stale-or-down, `down` never raises. Defects: #3, #4, #5, #6, #7, #9, #14. Per-adapter fallback chains: **not built**.
4. **Mocks on live path** — **None found.** No fixtures/mocks/sample data anywhere in main (grep clean; removed Node prototype contained none either). Only non-live branch is the labelled stale/forced-down path. Keep unit-test fixtures out of `backend/`.
5. **Confidence** — Model exists (`Confidence`), **no computation exists**; and inputs needed (observation age) don't exist (#2).
6. **ExplainerBot** — **Not built; no test.** `backend/bots/` is empty; `QueryResponse.explanation` and `ScoredWindow.summary` are free `Optional[str]` with no contract for a grounded fact set. Plan a post-check that every number in the LLM text appears in the scorer JSON, with a test that injects a fake number.
7. **TZ / datum / units / off-by-one** — #10; datum named in the field `tide_height_ft_mllw` (good), but `SourceResult` carries no units/datum metadata and no converters exist.
8. **Concurrency** — Orchestrator not built; adapter-level issues #6, #14.
9. **Security** — No API keys/tokens/secrets in tree or history (regex scan of full `git log -p`); `.env` ignored; `grok-sessions/` clean of keys/paths (one personal email in commit metadata — #17). Latent: #13, #15, #18.
10. **Depth** — Nothing "chart on top of an API" exists yet; the processing (tide-window derivation, slack detection, wind-vs-shoreline, SST anomaly, bloom flag) is **not yet in main**. The design in README is reasonable; judge on delivery.

## What works (credited, verified by probes)
- 3 tests pass; `/health` and `/spots` return correctly (3 spots); `/query` and `/recommend` 501 as documented; invalid activity ⇒ 422.
- `SourceAdapter`: per-attempt async timeout, 3 attempts with exponential backoff, cache TTL, stale-on-failure, `forced_down` path, never raises to the caller; failure ⇒ `status=down, data=None` (not fabricated data).
- `/debug/*` correctly 404 when `DEBUG` is off; `.gitignore` covers `.env`; no secrets committed.

## Summary
- **Top risk:** Safety gates are only a convention — `eligible` defaults to `True`, `GateResult` allows `passed=True` with `cannot_confirm=True`, rules are unvalidated strings, and observation age is never measured (#1, #2), so missing/stale data can still pass once scorers exist.
- **Quick win:** Make `ScoredWindow.eligible` derived/default-deny, add a `GateResult` validator, require tz-aware datetimes, and add `observed_at` + `max_age` to `SourceResult` (≈1 hour of changes; plus 3–4 unit tests).
- **Readiness: 3/10** (clean scaffold with a working retry/timeout/stale core, but no adapters, validation, gates, confidence, bots, or tests of the claims yet).
