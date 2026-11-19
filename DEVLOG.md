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
- (filled after commit)
