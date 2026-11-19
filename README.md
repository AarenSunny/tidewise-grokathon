# Tidewise

Tidewise recommends **where and when to do water recreation** using live public Earth-observation and environmental data. It supports clamming, crabbing, swimming, fishing, boating, kite sports, parasailing, and sailing.

The core product is not a chart on top of one API. It converts multiple feeds into an activity-specific recommendation, explains the factors behind that recommendation, exposes data freshness and uncertainty, and degrades safely when a source is incomplete or unavailable.

> **Safety:** This project is a planning aid, not an emergency, navigation, legal, health, or regulatory authority. Users must verify local closures, licenses, weather alerts, marine conditions, and official guidance before entering the water.

## Product flow

1. The user chooses an activity, location or search area, and time window.
2. The service resolves nearby observation/forecast stations and retrieves current public data.
3. Source adapters normalize units, timestamps, coordinates, quality flags, and freshness.
4. A scoring engine evaluates hard safety gates and activity-specific preferences.
5. The API returns ranked place/time windows with factor-level explanations, provenance, freshness, and confidence.
6. The client presents recommendations and clearly labels unavailable or stale inputs.

## Intended architecture

```text
Public APIs
  -> source adapters
  -> validation + unit/time normalization
  -> short-lived cache + last-known-good records
  -> geospatial/time-window join
  -> safety gates + activity scoring
  -> recommendation API
  -> map/list UI with explanations and source timestamps
```

Suggested repository boundaries once implementation begins:

```text
apps/web/              user interface
apps/api/              recommendation API
packages/adapters/     one adapter per public data provider
packages/scoring/      activity rules, gates, confidence, explanations
packages/contracts/    shared schemas and API types
tests/                 fixtures, adapter contracts, scoring and degradation tests
```

## Live public data

The initial U.S. data plan uses official public sources:

| Source | Intended signals | Role in recommendations |
| --- | --- | --- |
| [NOAA CO-OPS Data API](https://api.tidesandcurrents.noaa.gov/api/dev) | Tide predictions, observed water level, currents, water temperature, wind and other station products | Tide-dependent access, current-sensitive boating/sailing, and coastal timing |
| [National Weather Service API](https://www.weather.gov/documentation/services-web-api) | Hourly forecasts, observations, watches, warnings and advisories | Weather, wind, precipitation, visibility proxies, and hard hazard gates |
| [USGS Water Data APIs](https://api.waterdata.usgs.gov/) | Recent continuous measurements, streamflow, gage height, temperature, monitoring locations and selected water-quality observations | Inland-water conditions, flow and level context, and station metadata |
| [EPA BEACON / jurisdiction beach programs](https://www.epa.gov/beaches/find-information-about-particular-us-beach) | Submitted beach advisories, closures and monitoring context | Swimming and contact-water health gate, with jurisdiction links for verification |

Coverage and reporting latency vary by station and jurisdiction. Each response should retain source URL, station identifier, observed/forecast time, retrieval time, units, quality flags, and license/attribution where applicable.

## Scoring and safety gates

Each candidate place/time window receives an activity-specific score. Thresholds are configuration and must be backed by cited domain guidance before production use.

```text
eligible = no applicable hard gate is triggered

score = weighted mean of available normalized factors
confidence = coverage x freshness x source quality x spatial relevance
```

Example factors include tide stage, current speed, wind speed/gusts, air and water temperature, precipitation, streamflow or gage height, daylight, water-quality status, and distance from the relevant station. The response should include each factor's value, timestamp, contribution, and source so users can understand why a window ranked well or poorly.

Hard gates take precedence over a high numeric score. Examples include an official closure or warning, a severe-weather alert that intersects the location/time, data outside its allowed staleness window for a safety-critical factor, or conditions beyond a configured activity limit. The UI should never silently convert unknown safety data into “safe.”

## Missing, stale, bad, or unavailable data

- Validate every upstream payload against a source-specific schema and reject impossible or malformed values.
- Apply per-signal freshness limits; label stale observations and do not treat them as current.
- Retry transient failures with bounded exponential backoff and jitter, then use a time-limited last-known-good record when allowed.
- Open a circuit breaker for a repeatedly failing feed so one provider cannot stall the request.
- Reweight only non-critical missing preference factors. Never reweight around a required safety gate.
- Return `limited` or `unavailable` with reasons when evidence is insufficient; do not manufacture a recommendation.
- Surface partial coverage, source errors, timestamps, and confidence in the response and UI.
- Cache by provider, station or grid, product, and time bucket; respect upstream terms and rate limits.

## Local development

The current prototype is dependency-free and requires Python 3 only to serve the static files:

```bash
git clone https://github.com/AarenSunny/tidewise-grokathon.git
cd tidewise-grokathon
python3 -m http.server 8000
```

Open `http://localhost:8000`. The current UI is an interactive product shell; its recommendation cards are explicitly labeled previews. The provider-neutral scoring engine is real and can be verified with Node.js 20+:

```bash
node --test test/recommendation.test.mjs
```

No API keys are required for the skeleton. Never commit `.env` or credentials.

## Robustness and test plan

- Contract tests for every public API adapter using representative responses plus null, malformed, delayed, and error cases.
- Deterministic scoring tests at thresholds and around time-zone/daylight transitions.
- Geospatial tests for station selection, coastal boundaries, distance limits, and alert polygons.
- End-to-end test using live current data, while keeping recorded fixtures for repeatable CI.
- Visible provenance and freshness checks in API and UI acceptance tests.
- Failure drills for timeouts, rate limits, partial responses, provider downtime, and stale cache entries.

## Hackathon deliverables

The Track 03 submission requires:

- A **public GitHub repository** containing this README and a **Grok Bot session export with personal information removed**.
- A **public video link**, no longer than two minutes. A rough demo is acceptable.
- A deployment is ideal but not required. If local-only, this README must contain exact run instructions.
- A **presentation or slideshow at a public link**.

Judging emphasizes real/current public data, meaningful processing and logic, robustness to bad or unavailable feeds, a clear benefit to people on the ground, and evidence of how Grok Bot was used to plan, build, and debug.

See [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md) for the final 4:45 PM handoff.

## Current status

Implemented: responsive interactive UI, all eight activity choices, geolocation input, provider-neutral normalization/scoring, safety overrides, freshness/confidence handling, and five passing tests. Next: connect live adapters, replace preview cards with scored time/location windows, deploy, and add the redacted Grok session export, video, and slides.

