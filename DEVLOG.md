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
