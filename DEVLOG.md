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

### Real-world data issues
- N/A this phase (no live calls).

### Reviewer findings
- N/A (review after Phase 3).

### How Grok Bot helped
- Lead-engineer session: architecture confirmation, tradeoffs, scaffolding, and this DEVLOG.
- Export: see `grok-sessions/build/` after commit.

### Commits
- `cdb01b5` build(phase1): scaffold FastAPI architecture and pydantic models
