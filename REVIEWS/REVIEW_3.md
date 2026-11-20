# TideWise — Review of Phase 3 (branch `phase3-wip`)

- **Reviewed commit: `7c1af7d958214c74a907ef9d96731a9e0adf3132`** (`7c1af7d`, branch `origin/phase3-wip`). The branch moved by one commit after the requested `f66f82b`; `7c1af7d` only adds a session export (`git diff f66f82b 7c1af7d` = 1 file under `grok-sessions/`), so **all code reviewed is `f66f82b`**.
- Branch relationship: `phase3-wip` and `phase3-core` (`62b05bb`) both branch from main at `6265787` (before the deploy PR) and **neither contains the other**. `phase3-core` has its own rewrite of `adapters/base.py` plus `redact.py`, `settings.py`, `orchestrator.py` (fan-out) and `tests/test_core_review.py`; its test suite passes (**44 passed**), but the adapter bugs below (C-HARM variable names, currents shape, `Velocity_Major or`, CDPH) are **identical on `phase3-core`** (checked by grep). I did not otherwise review `phase3-core`. Neither branch contains `render.yaml` / `vercel.json` / `api.js` from main's deploy PR — merge main into the branch you ship so those aren't lost.
- Reviewer: independent review session. Application code not modified (read via a throwaway worktree; adversarial tests live outside the repo). Date 2026-11-19 (America/Los_Angeles), ~16:00 PST.
- Method: read `adapters/base.py`, all 9 adapters + registry, `cache/memory.py`, `health.py`, `validation.py`, `seasons.py` + `seasons.yaml`, `api.py`, `region.yaml`, the model changes; ran `pytest` (**1 failed, 33 passed** on `phase3-wip`); wrote adversarial tests for R1 #1–#6 and for each adapter (all failures below were reproduced); ran **every adapter against the live endpoints** through the registry (no mocks); checked live station ids, ERDDAP variable names and BeachWatch ordering.

## Not yet built (not findings)
`/ask` endpoint, ExplainerBot / IntentBot (`backend/bots/` empty), `DEMO_MODE`, FeatureEngine, activity scorers and gate engine (no code evaluates `activities/*.yaml`; the YAML is **unchanged** since main), factor breakdowns / confidence computation, an **NWS alerts/forecast/marine adapter** (sailing and swimming list `nws_alerts`, `nws_forecast`, `nws_marine` as required sources but no such adapter is registered), Leaflet map. In `phase3-wip` `/query` still returns 501 and `/recommend` only resolves spots (empty windows); **no adapter is called from any API route** (orchestrator exists only on `phase3-core`). Consequently I could not check: "factors cite real sources with honest `observed_at`" (no factors exist; adapter-level `observed_at` honesty checked below), "/ask can't state values outside the scorer JSON" (no `/ask`, no ExplainerBot, no grounding test), or "DEMO_MODE can't show a real closure as safe or leak into the live path" (no `DEMO_MODE` anywhere: `grep -ri demo_mode` is empty on both branches). Mocks/fixtures: **none reachable from the live path** — fixtures exist only in `tests/fixtures/`; only env overrides for base URLs/resource ids exist (`NDBC_BASE_URL`, `NOAA_COOPS_API_BASE_URL`, `BEACHWATCH_BACTERIA_RESOURCE_ID`).

## REVIEW_1 #1–#6 re-verification (phase3-wip @ f66f82b)

Adversarial tests: `adv1.py` (outside repo). PASS/FAIL below are my tests' results.

| # | Finding | Status | Evidence |
|---|---|---|---|
| 1 | Default-deny gates | **PARTIAL** | PASS: `GateResult(passed=True, cannot_confirm=True)` raises (`backend/models/common.py:130-137`); `ScoredWindow().eligible` defaults `False` (`backend/models/scoring.py:182`); naive datetimes rejected (`scoring.py:185-188`). FAIL: `ScoredWindow(eligible=True, gates=[])` and `eligible=True` with a `cannot_confirm` gate are still accepted (`scoring.py:174-196`; `gates_all_passed` is computed but never enforced). Gate YAML is still raw strings (`backend/config/__init__.py`, `activities/*.yaml` unchanged); `HourlyFeatures` gate inputs not added (DEVLOG defers). |
| 2 | Freshness from observation time | **PARTIAL** | PASS: old `observed_at` → `stale`; `safety_critical` + old → `down`; older than `max_stale_age` → `down` (`base.py:118-132`). FAIL: `observed_at=None` ⇒ result stays **`ok`** (`base.py:120`); `observed_at` 2 days in the **future** ⇒ `ok`; CDPH and EPA set `observed_at = now` (`cdph.py:127`, `epa_uv.py:202`); tide/current `observed_at = max(prediction time)` (`coops.py:167,253`) so age is negative (see P3-2, P3-6). |
| 3 | Cache key tolerant to window shift | **PARTIAL (fixed for shipped adapters)** | PASS: 1 µs shift keeps the key. Every adapter overrides `cache_key` by station/product/day (`coops.py:71,192`, `ndbc.py:42`, `erddap.py:97,230`, `cdph.py:65` …). FAIL (base default, `base.py:86-94`): key flips across an hour boundary (`…2026111915` vs `…16`) and ignores `end` (1 h and 72 h windows share a key). New bug introduced by overriding: NDBC key collision (P3-5). |
| 4 | Max stale age + eviction | **FIXED** (mechanism) | PASS: entry older than `max_stale_age` refused → `down`, data `None` (`cache/memory.py:51-64`, `base.py:263-264`); size cap 512 enforced (`memory.py:38-40`). Regression: malformed cached payload crashes `fetch` (P3-7). |
| 5 | Same type for cached and live data | **PARTIAL** | PASS for BaseModel payloads: live, cache-hit and stale all return the same class, `observed_at` preserved (`base.py:96-116`). FAIL: rehydration with `payload_model` has **no try/except** (`base.py:108-109`) → `ValidationError` escapes `fetch` (P3-7); the `data_type` branch swallows failures and silently leaves a `dict` (`base.py:106-107`). |
| 6 | Timeout / overall deadline enforced | **PARTIAL** | PASS: hanging async fetch bounded at 0.80 s by `overall_deadline_s` (`base.py:143-153`); httpx timeouts used by every adapter. FAIL: a blocking sync call is **not** interrupted (1.50 s elapsed, status `ok`, deadline 0.8 s) — latent only, since all current adapters use async httpx (P3-11). |

Quick status, rest of REVIEW_1: **#7 retries** fixed (Permanent/Transient classes, jitter, 429/5xx; `Retry-After` not honoured). **#8 validation** partial (`validation.py`; feature models unconstrained). **#9 health** fixed (registry-wired, `unknown` state, reset restores, `/debug/fail` validates source; `api.py:132-150`). **#10 TZ** partial (aware required in new models/API, CO-OPS `gmt`; daylight/seasons still UTC-date based, P3-10/P3-12). **#11 gate coverage** not fixed (YAML unchanged; seasons module + `Spot.no_take/dungeness_prohibited` added, unwired). **#12 spots** fixed (15 real spots; I verified station ids 9414131/9414290/9414275/9414817/9414816/9415228/9415020 exist). **#13 redaction** not fixed in wip (URL in notes verified; `redact.py` exists only on core). **#14 single-flight** not fixed (5 concurrent → 5 live calls). **#15 debug/CORS/dead config** not fixed in wip (`api.py:26-31`; `settings.py` only on core). **#16 tests** improved (34 tests) but none for currents, CDPH, C-HARM or EPA, i.e. the broken adapters. **#17 e-mails** unchanged. **#18 insecure TLS** no `verify=False` in `backend/` (CDPH now ArcGIS); `scripts/probes/run_all.py` insecure helper unchanged. **#19** partial (`get_running_loop` used; deps still unpinned).

Quick status, Phase 2 N1–N12: **N1** not fixed — worse (P3-1). **N2** partial (BeachWatch fails closed, but see P3-8). **N3** partial (`seasons.py`, `dungeness_prohibited`, SF Bay spots tagged; not wired to any gate, P3-10). **N4** partial (observed_at/max_age on NDBC, SST, chl, C-HARM; not CDPH/EPA). **N5** not fixed (DEVLOG still says C-HARM "unpublished"; ERDDAP datasets are up, see P3-3). **N6** not fixed (script). **N7** partial (per-adapter timeouts; BeachWatch `q=` query). **N8** partial. **N9** n/a on this branch. **N10** partial (nulls → `None`/`stale`; no nearest-valid-pixel search; box mean). **N11** unchanged. **N12** partial (DEVLOG triage table added; ArcGIS claim not retracted).

## Live run of every adapter (registry, no mocks, 16:01 PST)

| Adapter / spot | Status | Notes |
|---|---|---|
| `coops_tides` pillar_point_harbor / ocean_beach_sf | ok | station 9414131 / 9414275, 12 hilo points, GMT, `fallback_used=None` |
| `coops_tides_interval` pillar_point_harbor | ok (720 pts) | **down** for subordinate-station spots (P3-13) |
| `coops_currents` pillar_point_harbor | **down** | `PermanentFetchError: CO-OPS currents: empty` — real shape not parsed (P3-4) |
| `ndbc_buoy` pillar_point / crissy / berkeley | ok / ok / down | first buoy only; berkeley has no buoy (down, correct) |
| `erddap_sst` pillar_point | ok | 18.74 °C, obs 2026-11-18T09Z (age ~39 h), plausible vs buoy 46012 WTMP 18.9 |
| `erddap_chl` pillar_point / aquatic_park | stale | obs 2026-11-09 (11 d), chl 1.49 / 4.13 mg m⁻³ (box mean) |
| `erddap_charm` pillar_point | **down** after 8.0 s | variable names wrong (P3-3) |
| `cdph_shellfish` | **ok** | `any_region_advisory=True` for all six counties; `observed_at=now` (P3-1) |
| `beachwatch_bacteria` pacifica | down | reports latest sample 2025-07-14 (true max 2026-03-05) (P3-8) |
| `epa_uv` pacifica | ok | `uv_index=2.0` at 16:01 PST (daily max) (P3-9) |
| `daylight_sunrise_api` | ok | returned **Nov 20** sunrise for local Nov 19 (P3-12) |

## Findings (worst first; `P3-n`)

### P3-1 — BLOCKER — CDPH shellfish adapter reports "ok", stamps `observed_at=now`, and can read an outage/empty layer as "no advisory"
- `backend/adapters/cdph.py:93-129` (esp. `:121` `any_adv`, `:127` `observed_at=now`), `cdph.py:75-91`, `DEVLOG`/`REPORT` "prefer ArcGIS"
- **What's wrong:** (a) `observed_at` is the fetch time, not data time; the layers' `lastEditDate` (county pins 2020-08-25, special advisory 2025-07-10, verified in Phase 2) is ignored, so a frozen layer is permanently `ok`/fresh and `max_age=6h`/`safety_critical` can never trigger. (b) `any_region_advisory = bool(region_hit) or …`: because the pins always exist, the live value is **always `True`** (verified: all six counties) — an accident, not a signal. (c) ArcGIS returns **HTTP 200 with an `{"error":…}` body** on service faults; `_validate` then sees zero features → `any_region_advisory=False`, status `ok` (reproduced with an error body and with empty layers). Any gate written as `not any_region_advisory` **passes on an outage or a layer change** — the single scenario the project must never allow. (d) The region-wide flag is not spot/county specific. No unit test covers this adapter.
- **Fix:** Treat these ArcGIS layers as *unverifiable* for closures (see N1). In the adapter: reject bodies containing `"error"`; require `lastEditDate`/`editingInfo` and set `observed_at` to it; return `cannot_confirm` unless a source with per-county + species status and a date exists; default `any_region_advisory=None` (unknown), never `False`, unless a positive-control parse succeeded. Add the three failure tests above.

### P3-2 — MAJOR — Freshness check is skipped when `observed_at` is missing or in the future; empty payloads are `ok`
- `backend/adapters/base.py:118-122`, `backend/adapters/erddap.py:170-179,294-302`, `charm.py:94-101`
- **What's wrong:** `_apply_freshness` returns the result unchanged if `observed_at is None` or the age is ≤ `max_age`; a future timestamp gives a negative age. Verified: payload with `observed_at=None` → `ok`; `observed_at=+2 days` → `ok`. ERDDAP chl/SST and C-HARM return a *successful* payload with `observed_at=None`, value `None` for an empty table (verified: status `ok`, `chla=None`, `stale=True` only inside the payload). Downstream must remember to read the payload's own `stale`, which defeats the base-class guarantee.
- **Scenario:** An empty ERDDAP table (dataset reload) is reported "ok" to health and confidence.
- **Fix:** In the base class: `observed_at is None` ⇒ `degraded` (or `down` for `safety_critical`), future beyond a small skew ⇒ reject; adapters with all-`None` values return `down`/`degraded`, never `ok`.

### P3-3 — MAJOR — C-HARM adapter can never succeed (wrong ERDDAP variable names) and burns its whole deadline
- `backend/adapters/charm.py:63,68,102-104`, `DATA_SOURCES.md` (C-HARM variables), `backend/adapters/registry.py:169`
- **What's wrong:** The adapter queries `PNprob`, `pDA`, `Pseudo_nitzschia_Probability`. Live check: all three return **HTTP 500 "destinationVariableName … wasn't found"**; the real variables are `pseudo_nitzschia`, `particulate_domoic`, `cellular_domoic` (query succeeds, `time` axis ends 2026-11-02). It tries 2 hosts × 2 datasets × 3 vars sequentially (up to 12 requests) inside an 8 s attempt timeout: live run = **down after 8.0 s**. DEVLOG/docs still claim C-HARM is "unpublished" (it is up, stale since 2 Nov; see N5). The mean over a box of probabilities is also not a "maximum"/threshold-ready value.
- **Fix:** Use the documented variable (`pseudo_nitzschia`, optionally the two domoic fields), try one host/dataset per attempt, keep 0–360 longitude, take max or a high percentile over the box, set `observed_at` from the `time` value, and treat `(last)` older than `max_age` as `down`. Add a live-shape fixture test.

### P3-4 — MAJOR — CO-OPS currents adapter fails on the real response shape, drops slack velocities, and ignores the requested day
- `backend/adapters/coops.py:228-233` (shape), `:240` (`row.get("Velocity_Major") or row.get("v")`), `:200` (`"date": "today"`) vs `:192-195` (cache key from `start`)
- **What's wrong:** Live shape is `current_predictions: {units, cp: [...]}`; the adapter looks for `current_predictions`/`predictions` inside the block, finds nothing and raises "empty" → live adapter **down** (verified live; also with the REPORT.md sample). Even with the accepted shape, `Velocity_Major: 0` (every slack point) is falsy, so it falls through to `row.get("v")` → `velocity_kt=None` for exactly the points crabbing "slack closeness" needs (verified). `_fetch_live` always requests `date=today`, but the cache key uses the *requested* day: a request for tomorrow caches today's data under tomorrow's key (verified: params `date=today`, key day 20261121). No unit test covers currents.
- **Fix:** Read `cp`; use `row.get("Velocity_Major")` with `is None` checks; request `begin_date/end_date` from the window in GMT; validate that points cover the window; add a test from the real REPORT sample.

### P3-5 — MAJOR — NDBC: cross-spot cache collision, no fallback chain, and incomplete sentinel handling
- `backend/adapters/ndbc.py:42-44,46-61,85-88,107-112`, `backend/validation.py:261-296`
- **What's wrong:** (1) `cache_key` falls back to buoy `46026` when a spot has no `buoy_ids`; `fetch()` checks the cache **before** `_fetch_live` raises, so a spot with no buoy is served **another station's** observation as `ok` (verified: berkeley-style spot got `station_id=46026` from cache). (2) Only `buoy_ids[0]` is ever tried: with `["46012","46237"]` and 46012 failing, 46237 is never attempted (verified: tried `['46012']`, `down`); the README promises a fallback chain. A first buoy with `MM` wind (live 46237) just yields `wspd=None`. (3) Sentinels are matched as *strings* (`NDBC_MISSING`), so `"99"`, `"99.00"`, `"999.00"` parse as numbers; range limits are the only backstop and the gust cap is 100 m/s: `GST="99.00"` → **gust 99 m/s accepted** (verified). Gust < wind and gust > range of wind (75) are not checked. Good: `MM`, `999`, `999.0`, `9999.0`, negative wind, `WDIR=999`, `WTMP=99/999` are rejected; `WDIR=99` is kept (legit); timestamps are UTC; units kept in m/s (no kt conversion exists yet).
- **Fix:** Cache key must be `None`/raise when `buoy_ids` is empty; iterate `buoy_ids` until one yields wind/wave data fresher than `max_age` and report which buoy was used (`fallback_used`); parse sentinels numerically per column (`99`, `99.0`, `99.00`, `999*`, `9999*`); enforce `gust ≥ wind` and `gust ≤ 75`; add the m/s→kt converter with a test.

### P3-6 — MAJOR — Tide adapter silently substitutes San Francisco for a missing/failed station and never checks window coverage
- `backend/adapters/coops.py:18,72,76-101,147-174`
- **What's wrong:** A spot without `tide_station_id`, or a transient failure at its station, is served from **9414290 (SF)**; only the payload field `fallback_used` records it. Tides differ materially: live same-day lows at Pillar Point 1.08 ft vs SF 1.67 ft (and ~1 h shift), so a minus-tide gate (≤ −0.5 ft MLLW) can flip. `SourceResult.fallback_used` stays `None`, and no consumer exists to refuse it. `_validate` does not check that points cover `[start,end]`; `observed_at` is the *latest prediction time* (future), so `max_age` never applies (verified old/future behaviour). Permanent errors correctly do **not** fall back (good).
- **Fix:** Missing station ⇒ `cannot_confirm` (raise); allow a fallback only to a configured nearby station with a stated max offset, copy it to `SourceResult.fallback_used`, and have gates fail/cannot_confirm on fallback; check coverage and set `observed_at`/age from `fetched_at` for predictions.

### P3-7 — MAJOR — A malformed cached payload makes `fetch()` raise; the branch's own test fails
- `backend/adapters/base.py:96-110,263-270`; failing test `tests/test_adapters_unit.py::test_max_stale_age_returns_down` (**1 failed, 33 passed**)
- **What's wrong:** `_rehydrate` validates `result.data` with `payload_model` without a guard; `_fail_or_stale` (the failure path!) calls it, so a schema-incompatible cached entry (after a deploy that changes a payload model, or a poisoned persisted cache) raises `ValidationError` out of `fetch()`, violating "adapters never crash". The failing test is not a test bug: it stores `{'x': 1}` for `TidePayload` and the call raises. (`phase3-core` hardens this in `aa2f74c`; wip does not.) Also `importlib.import_module(result.data_type)` imports a class named *by the cache content* (`:101-105`) — harmless with the in-memory cache, an arbitrary-import risk the day the cache is persisted.
- **Fix:** Wrap rehydration in try/except → drop the entry and treat as a cache miss; allow-list `data_type` against the adapter's own `payload_model`.

### P3-8 — MAJOR — BeachWatch adapter reads the 50 *oldest* matching rows and reports a wrong "latest" date
- `backend/adapters/beachwatch.py:175-205`
- **What's wrong:** `datastore_search?limit=50&q=<county>` returns rows in storage order, not by date: live page max `SampleDate` = **2025-07-14**, while the dataset's true max is 2026-03-05 (verified both). The adapter therefore reports `latest_sample_date=2025-07-14` and `observed_at` accordingly. It fails closed (good: `cannot_confirm=True`, `down`), but it can **never** report fresh bacteria data even if the county resumes publishing, and the `q=` full-text query is the slow one (36 s in Phase 2). The advisories resource is imported but unused; results are never compared with bacteria standards.
- **Fix:** Use `datastore_search_sql` with `WHERE "County"=… ORDER BY "SampleDate" DESC LIMIT n` (0.4 s in my test), also read the advisories dataset, and keep the current fail-closed defaults.

### P3-9 — MAJOR — EPA UV: dishonest `observed_at`, daily maximum used for any hour
- `backend/adapters/epa_uv.py:188-205`
- **What's wrong:** `observed_at=now`; `uv_index = max(UV_VALUE)` over **all** returned rows (the day's hourly forecast), so at 16:01 PST the adapter reports UV 2.0 although it's nearly dark; `DATE_TIME` ("Nov/19/2026 07 AM", local, no offset) is stored as text, never parsed to UTC hours, so the scorer can't pick the hour of a window. ZIP is chosen from latitude bands only.
- **Fix:** Parse `DATE_TIME` with the region tz into aware UTC, return the per-hour series, and let the scorer pick the window's hours; set `observed_at` from the data or mark as forecast.

### P3-10 — MAJOR — Season/legal module fails open on date rollover and is wired to nothing
- `backend/seasons.py:61-66,143-156,97-109,178,242-253`
- **What's wrong (verified):** (a) The trap restriction is hard-coded to end on 2027-01-01 (`restricted_until`), while CDFW says "until **at least** Jan 1, 2027": on 2027-01-02 traps are `allowed` (fail-open on config expiry). (b) `_as_date(datetime)` uses the datetime's *own* tz: the instant 2026-11-06 19:00 PST gives `season_open=False` as PST-aware but **`True` as UTC-aware** (opener is Nov 7); `date.today()` (`:178,242`) is the server's date (UTC on most hosts), not the region's. (c) `mussel_quarantine_active` returns "lifted" for every date after 2026-10-31, including summer 2027, when the annual May–Oct quarantine applies again. (d) `clamming_season_status` is always `season_open=True` and ignores `Spot.no_take`; the CDPH/domoic status isn't an input. (e) Crab status is not wired to any scorer/gate (none exist). Good: unknown gear ⇒ `cannot_confirm`; SF Bay spots are tagged and gated `fail`; Dungeness SF-Bay prohibition and trap restriction match the quoted regulations.
- **Fix:** After `restricted_until`, return `cannot_confirm` (needs a human re-confirmation date); convert any instant to the region tz (`ZoneInfo(region.timezone)`) before taking `.date()`; make the quarantine rule recurring each year and keep the 2026 lift as an explicit exception; feed `no_take`/closure into clamming.

### P3-11 — MINOR — Blocking synchronous calls are not bounded by the deadline
- `backend/adapters/base.py:143-153,179-182`; verified 1.50 s blocking call → `ok` with a 0.8 s deadline.
- Latent (all adapters use async httpx). **Fix:** document the rule and run any sync parsing in `asyncio.to_thread` under the same deadline; add a lint/test that adapters contain no blocking I/O.

### P3-12 — MINOR — Daylight cross-check uses the UTC date, not the local date
- `backend/adapters/daylight.py:247-251`
- At 16:01 PST (00:01Z) it requested/returned **Nov 20** sun times for local Nov 19 (verified). Optional adapter, small error, but the same off-by-one-day pattern as P3-10(b). **Fix:** derive the date from `ZoneInfo(region.timezone)`; compute sun times offline as primary (as intended).

### P3-13 — MINOR — Interval tide product is unavailable for subordinate stations
- `backend/adapters/coops.py:111-123`, `registry.py:161-165`; live: `ocean_beach_sf` (9414275), `angel_island_ayala` (9414817), `tomales_inverness` (9415228) → `coops_tides_interval` **down**; hilo works for them.
- 3 of 15 spots have no 6-minute curve. **Fix:** derive the curve from hilo by cosine interpolation (and label it), or restrict the interval adapter to harmonic stations; avoid renaming adapters after construction (`registry.py:163-164`).

### P3-14 — MINOR — ERDDAP products use a ±0.05° box mean
- `backend/adapters/erddap.py:67-81,196,313`
- Mean over ~11 km mixes bay/ocean and land-masked pixels (`aquatic_park` chl 4.13 mg m⁻³ vs 1.49 at Pillar Point) and can dilute a bloom; no distance-to-valid-pixel or pixel-count in the payload. **Fix:** nearest valid pixel within a cap (report distance), keep max/percentile for bloom flags, include `n_valid/n_total`.

### P3-15 — MINOR — Branch hygiene and test blind spots
- `tests/test_adapters_unit.py` (11 tests: tides, NDBC row, chl, cache, health): **no tests for currents, CDPH, C-HARM, EPA, BeachWatch, daylight**, which is where the defects are; fixtures don't mirror live shapes (`tests/fixtures/*`). `phase3-wip` and `phase3-core` diverge on `base.py`; `phase3-wip` lacks main's deploy files; `DEVLOG.md` still says C-HARM is unpublished and "prefer ArcGIS".
- **Fix:** Pick one base (core's has redaction/settings/orchestrator), port the other's tests, merge main, add one live-shape fixture test per adapter.

## Checklist (adapters; phase3-wip)
1. **Safety** — Models default-deny (partial); no gate engine; CDPH adapter is the unsafe piece (P3-1); BeachWatch fails closed (P3-8).
2. **Sentinels** — NDBC mostly good, gaps P3-5; CO-OPS range/`MM` filter verified; ERDDAP nulls → `None`; POWER not used (EPA used).
3. **Failure handling** — async deadline/retries/classification/stale caps work; crash on malformed cache (P3-7); ERDDAP mirror/dataset chain exists and loops mirrors on 404/503 (the second host `coastwatch.noaa.gov` redirects, 302, on its root — not verified as a working mirror); **NDBC has no fallback chain** (P3-5); tide fallback is silent (P3-6).
4. **Mocks on live path** — none.
5. **Confidence** — not built.
6. **ExplainerBot / `/ask`** — not yet built; no grounding test.
7. **TZ/datum/units** — GMT/UTC at adapters ✓, MLLW/ft ✓ (live), NDBC m/s kept (no conversion yet), currents knots; date-rollover bugs P3-10/P3-12; EPA hour text unparsed (P3-9).
8. **Concurrency** — each adapter is independent and async; no orchestrator on wip; no single-flight (5 → 5 calls).
9. **Security** — no secrets/`verify=False` in `backend/`; redaction only on core; CORS `*` unchanged.
10. **Depth** — adapters + seasons are real processing; scoring/feature engineering not yet built.

## Summary
- **Top risk:** The CDPH shellfish adapter returns `ok` with `observed_at=now`, and an ArcGIS error body or empty layer is read as "no advisory" — a fail-open path for the clamming safety gate (P3-1), alongside base freshness that ignores missing/future `observed_at` (P3-2).
- **Quick win:** Fix three one-line adapter bugs — C-HARM variable `pseudo_nitzschia` (`charm.py:63`), currents `cp` + `is None` for `Velocity_Major` (`coops.py:228-240`), NDBC cache key for spots without buoys (`ndbc.py:43`) — and guard `_rehydrate` so the failing test passes.
- **Readiness: 4/10** (the REVIEW_1 core fixes mostly landed and every adapter really calls live data, but 3 of 11 adapters are dead/dishonest on live shapes, nothing is wired to the API, and scorers/ExplainerBot/`/ask`/DEMO_MODE do not exist yet).
