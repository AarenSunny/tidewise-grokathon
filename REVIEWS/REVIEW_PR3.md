# REVIEW_PR3: scorers PR #3 (`cursor/activity-scorers-e323`)

**PR head reviewed: `b66ff12`** (merge of main `1c4831b` into scorer commit `2431e98`).
Main at review time: `f9993b1`. Build branch `phase3-wip` was `2c7da0c`. Its work is already in main via PR #4.
Method: read all scorer, feature and config code, ran the full suite (**93 passed**, after installing `pydantic-settings` and `pytest-asyncio`), and wrote adversarial throwaway tests outside the repo. Each finding below was reproduced.

## VERDICT

- **Merge into main: non-blocking.** The PR is additive. Nothing in `backend/` imports `scorers` or `features` on the live path, the merge is clean, and the tests are green. The merge cannot break the running API.
- **Wiring into /recommend: BLOCKED until PR3-1 through PR3-5 are fixed.** Three of them let unsafe or unconfirmed output through, and one means /recommend cannot work at all.
- **Readiness for /recommend: 4/10.** The gate engine is well built and deny-by-default. The gaps are missing gates, freshness, and the glue code.

## Findings (worst first)

### PR3-1: BLOCKER (/recommend does not work): nothing turns adapter output into a `SpotFeatureGrid`, and the names and units do not line up
- Files: `backend/orchestrator.py:170-190` on main (still returns `windows=[]`, "scoring pipeline not wired"). The PR touches neither the orchestrator nor the API. There is no FeatureEngine in main or in the PR.
- Failure: the frontend calls `/recommend` and gets empty windows. Once someone writes the glue against the PR's models, the mismatches below turn most gates into permanent `cannot_confirm`. That is safe, but nothing is ever recommended.
- Mismatches. Adapter payloads are on main. The scorer expects what is in `models/features.py` and `activities/*.yaml`:

| # | Scorer expects | Build adapters produce | Effect |
|---|---|---|---|
| M1 | gate `sources:` keys `alerts_shellfish`, `satellite_chl`, `sst`, `alerts_bacteria`, `nws_alerts`, `nws_marine`, `offline_lunar` (`activities/*.yaml`, `HourlyFeatures.source_statuses`) | registry names `cdph_shellfish`, `erddap_chl`, `erddap_sst`, `beachwatch_bacteria`, `ndbc_buoy`. **No** `nws_*` adapter is registered. `nws_forecast` is in `DEFAULT_SOURCES` but nothing implements it. | Missing key means "missing", so the gate never confirms. Sailing (`nws_alerts`) and the swimming rip gate (`nws_marine`) can **never** be eligible. Clamming and crabbing cannot pass until the keys are mapped. |
| M2 | `wind_speed_kt`, `wind_gust_kt` | `NdbcObs.wspd_ms`, `gst_ms` (m/s) | If the glue copies the value without ×1.94384, a 21 kt line becomes 10.8 m/s. Wind would be under-read by about 2×, so sailing would pass in 35 kt. Needs a conversion plus a unit test. |
| M3 | `ChlorophyllObservation.chl_mg_m3`, `source_status` | `ChlPayload.chla_mg_m3`, `stale: bool` (adapter default `True`), `SourceResult.status` | Field rename. `stale` has to become a `SourceStatus`. |
| M4 | `TideSample.time`, `height_ft_mllw`, `kind` | `TidePoint.t`, `v_ft_mllw`, `type` | Rename. |
| M5 | `CurrentSample.velocity_kt: float` (required) | `CurrentPoint.velocity_kt: Optional[float]`, `type` in slack/flood/ebb | A `None` sample raises a pydantic error. Build must drop or flag `None` before constructing. |
| M6 | `active_alerts: list[str]` matched against `alert_patterns` | `ShellfishPayload.any_region_advisory`, `region_counties_with_symbol` (county names) | See PR3-6. |
| M7 | `ChlorophyllObservation.pseudo_nitzschia_p` is documented but **no gate uses it** | `CharmPayload.probability`, `available`, `stale` | C-HARM, the only domoic-acid-relevant signal, is unused. |
| M8 | no per-source `observed_at` field on `HourlyFeatures` | `SourceResult.observed_at`, `ChlPayload.observed_at` | Freshness cannot be carried into the scorer. See PR3-2. |
| M9 | resolves region from the `spot_regions` map | `Spot.dungeness_prohibited` and `Spot.county` already exist and are ignored | Two sources of truth. See PR3-4. |
| M10 | `Spot.id` values | **fixed in the final head**: `spot_regions` now uses the real ids (`pillar_point_harbor`, `crissy_field`, ...) | OK. |

Matches that are fine: `GateResult` (`passed` and `cannot_confirm` cannot both be true, identical on main), `ScoredWindow` (adds `label`; main's `gates_all_passed` coexists with `eligible`), `SourceStatus.unknown` (handled in `_worst`, `predicates.py:~546`), tz-aware datetimes, and ft MLLW tide. Fix: add a small `features/engine.py` with a per-adapter mapping table and unit tests per field, or rename the YAML keys to the registry names.

### PR3-2: BLOCKER: freshness is only a status flag. Frozen or old data passes every gate with confidence 1.0
- Files: `features/bloom.py:39` (only `source_status` is checked, `observed_at` is never compared with `as_of`), `scorers/predicates.py:512` (`source_problem` reads only `SourceStatus`). `min_confidence_to_recommend: 0.60` appears in all four YAMLs and is **never read** by any `.py`.
- Reproduced: a chlorophyll composite from 2026-11-02, scored on 2026-11-21 with `status=ok`, gives `no_bloom` **passed**, `eligible=True`, confidence **1.0**. This is REVIEW_2 N4/N10 and REVIEW_1 #2, still open at the scorer layer.
- Fix: add `max_age_hours` per source in the YAML (chl about 5 days, SST 3 days, shellfish and bacteria 6 h, buoy 3 h). `source_problem` and `bloom_status` compare `observed_at` with `as_of` and return `stale`, which becomes `cannot_confirm`. Enforce `min_confidence_to_recommend` in `_eligible`.

### PR3-3: BLOCKER (unsafe output): swimming has no surf gate, and sailing has no gust gate
- Files: `activities/swimming.yaml:42-71` (gates are bacteria, rip alert, bloom, daylight, cold shock only), `predicates.py:400` (sailing tests sustained wind only), `activities/sailing.yaml:12-13`.
- Reproduced:
  - Swimming with `wave_height_m=4.0`, 18 °C, and no alerts gives `eligible=True` with a score of 17.9. A hard 4 m (13 ft) surf, or an NWS beach-hazards statement that never arrives as a string, is "OK to swim".
  - Sailing with 14 kt sustained and **45 kt gusts** gives `eligible=True` and score 70. The gust spread of 31 kt is only scored down.
- Fix: add hard gates. For swimming, a significant wave height or surf cutoff (for example above about 6 ft, or per NWS surf zone) with a `cannot_confirm` when the buoy is missing. For sailing, `wind_gust_kt >= 34` fails (gale), with a lower gust cutoff for small craft. Cite NWS thresholds in the YAML.

### PR3-4: BLOCKER: the Dungeness "SF Bay ban" can be bypassed by the caller, because `grid.bloom_region` overrides the spot map
- Files: `features/bloom.py:93-97` (`resolve_region`: `if grid.bloom_region: return grid.bloom_region`), used by `predicates.py:281` (`dungeness_water_decision`).
- Reproduced: spot `crissy_field` with `grid.bloom_region="outer_coast"` gives `dungeness_water` **passed** and `eligible=True`. With only the spot id it correctly **fails**. The ban therefore depends on whichever code builds the grid setting an optional field correctly. A single mapping slip legalizes Dungeness in the Bay (14 CCR §29.85(b)(1), REVIEW_2 N3).
- Fix: make `spot_regions` and `Spot.dungeness_prohibited` authoritative. The gate fails if either says bay. If `grid.bloom_region` disagrees with the map, return `cannot_confirm` or fail. Never let a caller-supplied value clear a prohibition. Add a test.

### PR3-5: MAJOR (safety, depends on the glue): "no alert" is "inactive" whenever the source status is ok, and matching is on free text
- Files: `predicates.py:470` (`alert_state` returns `inactive` if no string matches), `alerts_match` substring patterns in `activities/*.yaml`.
- Reproduced: `active_alerts=["San Mateo County"]` with status ok gives `no_biotoxin_closure` **passed**. Adapter M6 produces county names and booleans, not words like "biotoxin". If the glue forwards `region_counties_with_symbol` as strings, a real CDPH advisory passes. REVIEW_2 N1/N2 are worse still: a live shellfish source may not exist, and BeachWatch ended in March 2026.
- Fix: the gate input must be a typed tri-state (`active`, `inactive`, `unknown`) set by the adapter mapping. `inactive` requires a positive "checked and clear" signal with a fresh `observed_at`, not an empty list. Until N1/N2 have a source, hard-wire shellfish and bacteria to `cannot_confirm` (maybe via config `confirmed: false`, as the season block already does).

### PR3-6: MAJOR: factor `observed_at` and `age_minutes` are the forecast grid hour, not the source observation time
- Files: `scorers/base.py:373-405` (`_timing` uses `hour.hour`, and `_age` uses `ctx.as_of or ctx.start`).
- Reproduced: with no `as_of`, every factor shows `age_minutes: 0.0`, which reads as perfectly fresh. With `as_of` one day earlier it shows **-1440**. The chlorophyll factor is the only one that uses a real `observed_at`. This breaks the "honest observed_at" requirement and what ExplainerBot will cite.
- Fix: carry per-source `observed_at` into the grid (see M8) and report that. Return `None` for age when it is unknown. Clamp negative values.

### PR3-7: MAJOR: hours before the window start are dropped, and a gate can pass while ignoring the first partial hour
- Files: `scorers/base.py:131-139` (`start_utc <= moment < end_utc` keeps hours by their start instant).
- Reproduced: grid hour 12:00 at +2.0 ft and hours 13:00 and 14:00 at -1.2 ft. For window 12:30-15:00, `minus_tide` **passes**, because the 12:00 hour is excluded. For 12:30-13:00 there are no hours, so it gives `cannot_confirm`. Windows from `tides.py` start at crossing times such as 6:10 and rarely sit on the hour.
- Fix: select hours overlapping `[start, end)`, meaning `floor_hour(start) <= hour < end`. Evaluate the gate on the interpolated 6-minute series for tide, or require both neighbours.

### PR3-8: MAJOR: bloom thresholds are loosely justified, and chlorophyll is treated as a safety signal for domoic acid
- Files: `config/region.yaml` (`bloom_regions`), `features/bloom.py:20-91`.
- Units are right: linear mg/m³, NaN, negative, -999 and >500 are rejected (verified), 5.0 is a pass, 5.01 fails, and null pixels give `cannot_confirm`. Concerns:
  1. The outer-coast 5 mg/m³ cut (Nezlin 2012) is a Southern California remote-sensing bloom marker, not a Pseudo-nitzschia or domoic-acid threshold. Central Coast upwelling in summer often exceeds 5 and is harmless. Low chlorophyll does not mean no toxin. A "bloom clear" pass can imply safety that does not exist.
  2. SF Bay: 13 mg/m³ is Sutula's protective level for eutrophication, not a recreational-safety line. Satellite chlorophyll in turbid Bay water (case-2) is poorly retrieved, and the at-risk band (25-40) only sets `at_risk`.
  3. C-HARM probability (M7) is unused.
- Fix: relabel the gate so it does not claim safety ("elevated chlorophyll, informational"). Make C-HARM probability the gating signal, with a threshold cited and `cannot_confirm` when it is down (REVIEW_2 N10). Do not let the bloom gate substitute for CDPH.

### PR3-9: MAJOR (rules): Dungeness and trap rules are conservative but incomplete
- Files: `activities/crabbing.yaml:gear`, `region.yaml:crab_zones`, `predicates.py:209-278`.
- Verified correct: `trap` fails in Zone 3 before 2027-01-01 and is `cannot_confirm` after. `hoop_net`, `snare`, `loop_trap` and `hand` pass with the §29.80(e) caveat carried in the reason. `Trap` and `TRAP` give `cannot_confirm` (case-sensitive, so deny). The bay fails Dungeness. Pre-season and post-season both fail (2026-11-07 to 2027-06-30).
- Gaps:
  - Only Zone 3 is configured. Trap outside Zone 3 is `cannot_confirm`, which is safe, but the "Zones 1-5" ban is not modelled. `seasons.yaml` on main has zones 3 and 4. Two sources of truth.
  - No species. A Dungeness rule gates everything called "crabbing". Rock crab and red rock crab in the Bay are legal, so every Bay spot is permanently blocked for them.
  - The hoop-net 2-hour rule is a note only.
  - `gear` must be passed by the caller. If the frontend omits it, crabbing is always `cannot_confirm`, so the API needs a `gear` parameter.
- Fix: read `seasons.yaml` and `Spot.dungeness_prohibited` instead of duplicating them. Add a `species` field (dungeness or rock). Normalise gear (lowercase, underscores) with a known-alias list.

### PR3-10: MAJOR: ineligible windows still carry a plausible score and a confidence that does not drop for age
- Files: `scorers/base.py:544-552`, `windows.py:107`.
- Reproduced: a cold-shock-blocked swim window (`eligible=False`) shows score **43.5**. Confidence only drops for gate `cannot_confirm` or status problems, not for age. A consumer reading `best_score` or the ranking can show a "43" next to a blocked window.
- Fix: score is 0 or `None` when ineligible, or set a separate `display_score`. Document that `eligible` is the only recommendation signal.

### PR3-11: MINOR: validation ranges
- `predicates.py:numeric_sentinel`: a tide of -15 ft or +25 ft is accepted (the check is `abs >= 30`). Real SF range is about -3 to +8 ft. Sea temperature of 0 to 2 °C is accepted. Currents above 20 kt are rejected, but a 12 kt SF current is accepted. Tighten per region.
- Wind `>=150` and `99/999` sentinels are rejected. A negative wind is rejected. This is OK.

### PR3-12: MINOR: legal-light margin is applied to swimming and sailing
- `daylight_margin_minutes: 30` (14 CCR §29.20 covers clamming) is reused for swimming and sailing, with the CCR citation. Solar times verified plausible (HMB 2026-11-21 sunrise 06:55, sunset 16:55 PST).
- Fix: keep the margin for take activities. Swimming and sailing should use sunrise to sunset or civil twilight.

### PR3-13: MINOR: a config with a gate removed is accepted
- `rules.py:validate_activity_config` only requires one gate. A YAML with only `daylight` gives `eligible=True` on a +5 ft tide with no source statuses. Add a required-gate list per activity, so deleting a bloom gate fails at load.

### PR3-14: MINOR: `windows.py` invented `_slack_from_tide_turns` and hour-based slack fallback
- `windows.py:~190-260` treats a +/-45 minute window around any high or low tide as crab "slack" when currents are missing. Tide turns are not current slack in the Bay, and the label still reads "slack water". Mark the window `cannot_confirm`, or label it "estimated from tide turns".

## Checks that passed
- Gates are deny-by-default: unknown status gives `cannot_confirm`, and a missing hour, naive datetime or unknown rule field fails closed.
- `GateResult` forbids passed together with `cannot_confirm`.
- Sentinels for NDBC (99, 999, MM-style strings), NaN, inf, negative wind and chlorophyll -999 are rejected.
- No mock or fixture is imported from `backend/` (the fixtures live in `tests/conftest.py`).
- DST: a 5-hour window across 2026-11-01 scores normally. Solar and moon are computed offline.
- A naive `start` raises `NaiveDateTimeError`, a `ValueError`. The API must map it to a 422, or the user sees a 500.

## Summary
- **Top risk:** PR3-1, because /recommend still cannot return windows. After that come PR3-2/3/4, where gates can pass on 17-day-old chlorophyll, 4 m surf, 45 kt gusts, or a Bay Dungeness window if `bloom_region` is set wrongly.
- **Quick win:** make `resolve_region` and the Dungeness gate fail on `Spot.dungeness_prohibited` or a region mismatch (PR3-4). Add `max_age_hours` plus an `observed_at` check in `source_problem` (PR3-2). Rename the source keys in the YAML to the registry names (M1).
- **Readiness: 4/10.** The merge is safe. Wiring is blocked until PR3-1 to PR3-5 are fixed.
