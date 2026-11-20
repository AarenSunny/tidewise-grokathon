# TideWise DEVLOG

Judges: this log records decisions, bugs, live-data surprises, review triage, and how Grok Bot was used. Session exports live under `grok-sessions/`.

---

## Phase 1 — Plan & skeleton (2026-11-19)

### What was built
- Confirmed bot-management architecture (IntentBot → Orchestrator → adapters → FeatureEngine → ActivityScorers → ExplainerBot + HealthMonitor).
- Repo layout: `backend/` (models, adapters, cache, features, scorers, bots, config, api), `frontend/` (Vite+React+Leaflet shell), `scripts/probes/`, `tests/`, `grok-sessions/{research,build,review}/`, `REVIEWS/`.
- Pydantic v2 contracts for intent, spots/region, `SourceResult`, hourly features, scored windows, and API schemas.
- Abstract `SourceAdapter` with timeout, retry/backoff, TTL cache, stale serve, and validation hooks; `MemoryTTLCache`; `HealthMonitor`; FastAPI route stubs including debug fail/reset (DEBUG-gated).
- Region + activity YAML configs (placeholder spots until `DATA_SOURCES.md`).
- `.gitignore`, `.env.example`, `requirements.txt`, `Makefile`, README stub, smoke tests.
- Removed the prior Node static prototype from the live path (it conflicted with the FastAPI stack).

### Key decisions and why
| Decision | Alternatives considered | Why |
| --- | --- | --- |
| `/backend` + `/frontend` layout | README's `apps/` + `packages/` monorepo | Matches hackathon deliverables; less packaging overhead |
| Delete Node prototype (not archive) | Keep under `legacy/` | Avoid two stacks; scorers will be Python |
| Abstract `CacheBackend` now | Memory-only with SQLite later bolted on | Adapters stay store-agnostic |
| Activity/region as YAML | Hardcoded Python dicts | Config-driven region extension; scorers as plugins |
| Safety gate rule: missing ⇒ cannot_confirm | Treat missing as pass / soft penalty | Explicit product + judging requirement |

### Risks tracked
- Feed schema drift vs `DATA_SOURCES.md` (trust live call; note in DEVLOG).
- NDBC sentinels (99/999/MM) leaking into scores.
- Rate limits / User-Agent requirements (NWS).
- ExplainerBot inventing numbers (needs grounded JSON + test in Phase 6).
- Timezone / MLLW edge cases around daylight and minus tides.
- `DATA_SOURCES.md` not in repo yet — Phase 2 blocked on research session.

### Bugs found
- **`GET /spots` returned empty list.** Root cause: `api.py` constructed `RegionConfig()` instead of `load_region()`. Fixed by wiring the YAML loader at module import. Verified: 3 placeholder spots returned.
- Activity YAML write failed until `backend/config/activities/` was created (mkdir miss during scaffold).
- **`grok-sessions/build/` ignored by git:** Root cause: `.gitignore` had a bare `build/` pattern that matched any directory named build. Fixed by removing that pattern (frontend output is `frontend/dist/` only).

### Real-world data issues
- N/A this phase (no live calls).

### Reviewer findings
- N/A (review after Phase 3).

### How Grok Bot helped
- Lead-engineer session: architecture confirmation, tradeoffs, scaffolding, and this DEVLOG.
- Export: see `grok-sessions/build/` after commit.

### Commits
- `cdb01b5` build(phase1): scaffold FastAPI architecture and pydantic models

---

## Phase 2 — Probe (2026-11-19)

### What was built
- Read `DATA_SOURCES.md` (research commit `f50ae9d`).
- Added build-owned live probe runner `scripts/probes/run_all.py` covering CO-OPS, NDBC, NWS, ERDDAP (MUR/chl/C-HARM/anom), CDPH ArcGIS + TLS check, BeachWatch CKAN, FIRMS/EONET, EPA UV + NASA POWER.
- Wrote `scripts/probes/REPORT.md` with response shapes, samples, and discrepancies.
- Did **not** edit `DATA_SOURCES.md` or `scripts/research_probes/` (research-owned). Left frontend map UI alone (other agent).

### Key decisions
| Decision | Alternatives | Why |
| --- | --- | --- |
| New Python runner in `scripts/probes/` | Re-run research bash only | Need structured shapes for Phase 3 adapters; keep research scripts untouched |
| Commit REPORT.md, gitignore `out/` | Commit raw dumps | Keep repo small; shapes matter more than full payloads |

### Bugs found
- Report writer `ValueError` on f-string `{r.latency_ms:.0f if ...}` — invalid format spec. Fixed with conditional expression outside format spec.
- Initial ERDDAP failures looked like bad quoting; **root cause was not quoting** — dataset/info URLs 404'd and then ERDDAP went 503.

### Real-world data issues
- **CoastWatch ERDDAP outage/partial failure** same day DATA_SOURCES verified it: first chl/C-HARM 404 while MUR 200; then global 503. Documented in REPORT timeline. Trust live call; note discrepancy vs DATA_SOURCES.
- **NDBC 46239** HTTP 200 but data stamped **2026-10-25** (~25 days stale) — confirms research warning; adapters must check row time.
- **NDBC `MM` sentinels** present on active buoys (DPD etc.).
- **CO-OPS** no `water_temperature` at 9414290 — confirmed error JSON.
- **NASA POWER** `ALLSKY_SFC_UV_INDEX` all `-999` — use EPA UV.
- **CDPH** HTML TLS verify failed in this runtime; ArcGIS FeatureServer OK. Prefer ArcGIS.
- **CDPH county symbols false discrepancy:** probe matched `San Francisco` but ArcGIS returns `San Francisco County`. Root cause: overly strict string match. Fixed in probe.
- Today's SF lows only **+1.0 / +1.7 ft MLLW** — no minus tide; clamming gates will correctly fail on tide today.

### Reviewer findings
- N/A

### How Grok Bot helped
- Phase 2 plan/tradeoffs, live debugging of ERDDAP 404→503, probe runner + REPORT.
- Export: `grok-sessions/build/` (this session).

### Commits
- `0d08bf3` / `0528875` build(phase2) probes + session export

---

## Phase 3 — Adapters WIP (2026-11-19)

Work branched to `phase3-wip` mid-phase so cloud agents can split remaining work.

### What was built (WIP)
- Review1 model fixes: `GateResult` forbids `passed=True`+`cannot_confirm=True`; `ScoredWindow.eligible` default `False`; tz-aware validators on SourceResult/intent/scoring.
- `SourceResult.observed_at` + base adapter freshness (`max_age` / `max_stale_age`), stable cache keys, typed cache rehydrate, overall deadline, retry classification, HealthMonitor wiring.
- `MemoryTTLCache` size cap + max stale age.
- Adapters: CO-OPS tides/currents, ERDDAP chl+SST (mirror/dataset fallback), C-HARM (optional/down-safe), CDPH ArcGIS, NDBC, EPA UV, BeachWatch (stale⇒cannot_confirm), optional daylight sunrise API.
- `backend/seasons.py` + `config/seasons.yaml` from **DATA_SOURCES.md @ ed08814** (zone-based gear; SF Bay Dungeness hard-fail; trap restricted until 2027-01-01; hoop/snare/hand allowed with snare/loop caveat).
- `region.yaml` filled from Part B spots + station IDs; `GET /recommend` lat/lon nearby selection.
- Unit tests + fixtures (see pytest status on branch).

### Reviewer findings triage (REVIEW_1.md)
| Finding | Decision | Reason |
| --- | --- | --- |
| #1 models (GateResult / eligible default) | **fix** | Done in models (not features.py / ActivityConfig — deferred to scorers agent) |
| #1 YAML ActivityConfig / HourlyFeatures gates | **defer** | scorers/features cloud agent owns |
| #2 observed_at freshness | **fix** | SourceResult + base `_apply_freshness` |
| #3 stable cache keys | **fix** | station/product/day keys; quantized hour default |
| #4 max_stale_age + cache eviction | **fix** | MemoryTTLCache max_entries + get_stale age |
| #5 cache type round-trip | **fix** | data_type + rehydrate via payload_model |
| #6 timeouts / overall deadline | **fix** | httpx timeouts + asyncio.wait_for overall |
| #7 retry classification | **fix** (partial) | PermanentFetchError fail-fast; transient retry + jitter |
| #8 validation layer | **fix** (partial) | `backend/validation.py` + per-adapter validate; features.py constraints deferred |
| #9 HealthMonitor wiring | **fix** | registry + debug fail/reset on known sources |
| #10 tz / CO-OPS gmt | **fix** (partial) | aware validators; CO-OPS `time_zone=gmt` |
| #11 activity gate YAML gaps | **defer** | scorers agent; Spot.no_take + dungeness_prohibited added |
| #12 region placeholders | **fix** | region.yaml rewritten from DATA_SOURCES Part B |

### Season / gear source
Encoded **only** from `DATA_SOURCES.md` @ **ed08814** (not from chat notes). Zone 3 lat bounds; trap restriction; hoop nets / snares / hand allowed with §29.80(e) caveat on loop traps/snares; SF Bay/San Pablo Dungeness = gate **fail**.

### Real-world data notes
- CoastWatch ERDDAP 404/503 earlier today → adapters try pfeg + coastwatch.noaa.gov + alternate datasets; never invent chl/SST/C-HARM.
- C-HARM unpublished afternoon → optional adapter returns down/cannot_confirm.
- BeachWatch bacteria months-stale → `cannot_confirm` for swim gates.
- EPA UV only (not POWER UV_INDEX).

### How Grok Bot helped
- Phase 3 plan, review triage, adapter scaffold, season gear encoding from research commit, WIP branch handoff.

---

## Phase 3 — Core track (`phase3-core`, 2026-11-19)

Branched from rebased `phase3-wip` onto `origin/main`. Cloud agents A/B own concrete adapters; this track owns shared interfaces, orchestrator, API wiring, and review fixes.

### Root cause: `test_max_stale_age_returns_down`
**Test bug + brittle rehydrate path.** The test seeded a *fresh* TTL cache entry (`timedelta(hours=1)`) with `data={"x": 1}` (not a `TidePayload`). `fetch()` hit the cache_hit path and `payload_model.model_validate` raised `ValidationError` before `get_stale`/`max_stale_age` ran.  
**Fix:** (1) `_rehydrate` returns `None` on validation failure (treat as miss); (2) `get_stale` uses `age >= max_stale_age` so `0` never serves stale; (3) test expires TTL (`timedelta(0)`), uses a Fake adapter + valid payload shape.

### Interface changes during split (additive only)
| Change | Compat |
| --- | --- |
| `SourceResult.observed_at`, `data_type` | additive fields |
| `SourceAdapter.max_age`, `max_stale_age`, `safety_critical`, `payload_model`, `overall_deadline_s` | additive class attrs |
| `TransientFetchError.retry_after_s` | additive kw-only; positional message unchanged |
| `_rehydrate` → `Optional[SourceResult]` | internal; callers updated in base only |
| `MemoryTTLCache` deep-copy on get/set; `get_stale` uses `>=` | behavior tightened; signature unchanged |
| `HealthMonitor` initial `unknown`; `register` / `is_forced_down` / redact on failure | additive |
| `Spot.no_take`, `dungeness_prohibited`, id/lat/lon validators | additive |
| `RecommendResponse.note`, `distances_km` | additive |
| `QueryRequest.text` max_length=2000 | tighter validation |
| `SourceStatus.unknown` | additive enum member |
| `Orchestrator` real implementation (was NotImplementedError stub) | new public API |
| `backend/redact.py`, `backend/settings.py` | new modules |

### Reviewer findings triage (REVIEW_1)
| # | Decision | Notes |
| --- | --- | --- |
| #1 models | **fix** (partial) | GateResult / eligible default; ActivityConfig/features deferred to scorers |
| #2–#6 | **fix** | observed_at, cache keys, max_stale, rehydrate, deadlines (prior WIP + core) |
| #7 | **fix** | Permanent fail-fast; Retry-After on 429; jitter |
| #8 | **fix** (partial) | `validation.py` helpers; features.py Field constraints deferred |
| #9 | **fix** | HealthMonitor wired via registry |
| #10 | **fix** (partial) | tz-aware models; CO-OPS gmt in A’s adapter |
| #11 | **defer** | scorers agent |
| #12 | **fix** | region.yaml filled earlier; Spot.id validator |
| #13 | **fix** | `redact()` on logs/notes/health |
| #14 | **fix** | single-flight + orchestrator gather/deadline/semaphore |
| #15 | **fix** | DEBUG default false; CORS allowlist from env; settings load |
| #16 | **fix** | core unit tests added |
| #17 | **won't fix** | email in git history needs force-push; owner decision |
| #18 | **defer** | B owns CDPH adapter |
| #19 | **fix** (partial) | monotonic time, note cap, copy-on-read, QueryRequest cap |

### Tests
44 passed (pytest). Ruff not previously configured; added minimal `[tool.ruff]` excluding A/B adapter paths.

### REVIEW_2 triage (core track) — `REVIEWS/REVIEW_2.md`
| # | Decision | What / why |
| --- | --- | --- |
| N1 (CDPH ArcGIS can't represent closures) | **owner: Agent B** | not touched here. We retract "prefer ArcGIS" for the *gate*: probe report now states the layers are static pins and CDPH HTML fails strict TLS, so the closure gate is `cannot_confirm`. |
| N2 (BeachWatch stale) | **owner: Agent B** | not touched here. |
| N3 (crabbing vs CCR / species / gear) | **fix (tests) + verified config** | `region.yaml` already flags `dungeness_prohibited` on every SF/San Pablo Bay spot and none offers `crabbing`; `seasons.yaml` (B) carries the dated trap restriction and gear table. Added `tests/test_crabbing_bay_block.py`: API 400 for crabbing at each bay spot, nearby search from *inside* the Bay never returns them, and `crabbing_season_status` is a hard **fail** (not `cannot_confirm`) for all gear. No hoop-net count is shown anywhere. |
| N4 (frozen feeds marked ok) | **fix** | `scripts/probes/run_all.py` now records the data's own timestamp, compares with per-source budgets (`MAX_AGE_HOURS`, equal to the adapters' `max_age`, enforced by `tests/test_probe_freshness.py`), and prints a **Verdict**: OK / STALE / UNKNOWN_AGE / FAIL / N/A. Live run 16:0x PST: C-HARM 420 h → **STALE**, VIIRS 8-day chl 264 h → **STALE**, NDBC 46239 621 h → **STALE**, MUR SST 39 h → OK. |
| N5 (ERDDAP "outage" wording) | **fix (probe side)** | 404/502/503 are reported as transient/intermittent (flapping observed: MUR anomaly returned 503 again in the same run that returned 200 for MUR SST). `DATA_SOURCES.md` wording is research-owned; flagged, not edited. |
| N6 (insecure TLS helper) | **fix** | `insecure=` and `ssl._create_unverified_context()` deleted from `run_all.py`. CDPH TLS probe is strict-only and now reports **FAIL** (missing intermediate cert) instead of ok-after-insecure-retry. A test greps for `verify=False`, `_create_unverified_context`, `insecure=True`, `CERT_NONE`. |
| N7 latency budgets | **defer** | per-adapter timeouts belong to A/B adapter files; base supports per-class `timeout_s`/`overall_deadline_s`. |
| N8 time module / legal clamming hours | **defer** | features/scorers owner; core already normalizes datetimes to aware UTC. |
| N9 deployment hardening | **partial** | CORS allowlist from env, `DEBUG` default false, `/health` error redaction, `QueryRequest` max_length done; rate limit, pinned deps, CI, persisted cache **deferred**. |
| N10 null satellite pixels | **defer** | adapter-owned (neighbourhood search). |
| N11 emails in metadata | **won't fix** | history rewrite needs force-push; owner decision. Use GitHub noreply going forward. |
| N12 doc drift | **fix** | REVIEW_1 triage table + this table in DEVLOG; REPORT.md labelled as a dated snapshot. |

### Phase 3 core hardening (REVIEW_3) — interface changes during split
Additive/strictening changes to frozen interfaces, all covered by `tests/test_hardening_review3.py`:
| Interface | Change | Why |
| --- | --- | --- |
| `SourceAdapter._apply_freshness` (P3-2) | `observed_at is None` with a payload now means **not fresh** (status `stale`, `down` if `safety_critical`, note `observed_at_missing_not_fresh`). `observed_at` more than `max_future_skew` (default 5 min; class attr or `ADAPTER_MAX_FUTURE_SKEW_S`) in the future is **invalid** (status `down`, note `observed_at_in_future_invalid`). | Previously both cases skipped the check and returned `ok`. |
| `SourceAdapter.allows_future_observed_at` (new, default `False`) | Forecast/prediction feeds opt in; `AdapterRegistry` sets it for `coops_tides`, `coops_tides_interval`, `coops_currents`, `daylight_sunrise_api` (their `observed_at` is the newest *predicted* point). | Keeps the strict rule for every observation feed without editing A/B adapter files. |
| `SourceAdapter.validate_timeout_s` (new, 5 s) (REVIEW_1 #6) | `_validate` runs in `asyncio.wait_for(asyncio.to_thread(...))`; timeout is a `PermanentFetchError` -> `down`/stale-cache path. | A hung or slow sync parse can no longer block the event loop or the request. The worker thread cannot be killed; it is abandoned. Config YAML loads are startup-only/`lru_cache`d, not in the request path. |
| `ScoredWindow` (REVIEW_1 #1) | New validator: `eligible=True` is rejected unless `gates` is non-empty and every gate has `passed=True` and `cannot_confirm=False`. | Closes the last default-deny hole in the model. |

### phase3-e2e: live path wired to the real scorers
- `/recommend` and `/query` now run adapters -> `backend/grid_builder.py` -> `backend/scorers` (`ranked_windows`) -> `ScoredWindow`s with cited factors. Responses carry `scorer: "activity_scorers"` (or `"unavailable"` if the scorers cannot be imported: empty windows, never fake scores).
- `backend/source_aliases.py` is the single map from scorer/config keys to registry names (`alerts_shellfish->cdph_shellfish`, `satellite_chl->erddap_chl`, `sst->erddap_sst`, `alerts_bacteria->beachwatch_bacteria`). `nws_*` map to nothing: sailing and the rip gate stay cannot_confirm.
- PR3-1: NDBC m/s converted to knots (x1.94384) at the grid boundary (tested). PR3-2: per-source `max_age` is enforced against `observed_at` when the grid is built; stale values become None/cannot_confirm (tested with 19-day-old chlorophyll).
- Shellfish: the scorer only ever sees `any_region_advisory=false` (explicit False from a fresh, confirmed CDPH result) or `any_region_advisory=true`. None, empty list, county strings, truthy/falsy non-bools, stale/missing/unconfirmed all give no token -> cannot_confirm (tested through the orchestrator). Bacteria is never a confirmed clear (records are not parsed): swimming stays cannot_confirm. Demo clamming/crabbing only; no sailing.
- SF Bay / San Pablo Bay Dungeness is also enforced in the orchestrator from Spot/region config (defense in depth, tested); it is ineligible through the API.
- Deferred (not done before freeze): DEMO_MODE snapshot, /ask, /alerts, satellite overlay, factor pass-through extras, NWS alerts mapping into the grid, bacteria parsing, forecast wind/waves (a single buoy observation is attached only to the hour it was observed).
