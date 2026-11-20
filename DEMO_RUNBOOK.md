# TideWise — Live Demo Runbook (2 minutes)

_Last verified: Thu Nov 19 2026, 4:35 PM PT (headless Chromium, desktop 1440×900 and mobile 390×844)._

## Deployment URLs and SHAs

| Piece | URL | Deployed commit | Verified |
|---|---|---|---|
| Frontend (Vercel, production) | https://tidewise-asunny.vercel.app | `e61b258` (PR #22, = `main` HEAD at 4:36 PM PT) | Vercel deployment `dpl_2Dd3wjXEzSD3z9Q77rcp9xJnwuNW`, ready 4:33 PM PT |
| Backend (Render, free plan) | https://tidewise-api.onrender.com | `121f3f9` | Render deploy `dep-dbvp7kh42hec73ag99a0`, live 4:27 PM PT |

The backend code is identical from `04cef6a` (PR #15) through `e61b258`. Later commits changed only the frontend and docs, so Render may not redeploy, and that is fine. API docs: https://tidewise-api.onrender.com/docs

## T-minus 3 minutes: warm up Render (required)

Render's free plan puts the backend to sleep after about 15 minutes of no traffic. The first request after that can take 30–60 s. The frontend waits **45 s** for `/recommend` and `/health` (PR #22). If the backend is still asleep after that, the page shows the amber **"Live data unavailable — showing example data"** banner. That banner is honest, but it is not the demo you want.

1. Open https://tidewise-api.onrender.com/health 2–3 minutes before you present. Wait for JSON (`"status":"degraded"` is expected).
2. Open the best API URL below once, to warm the adapter caches.
3. Open https://tidewise-asunny.vercel.app and confirm the footer reads `Backend (https://tidewise-api.onrender.com): connected, health degraded, 15 spots`.
4. Keep both tabs open, and reload the frontend once right before you start.

## Best live request

```
https://tidewise-api.onrender.com/recommend?activity=crabbing&spot=pillar_point_harbor&gear=hoop_net
```

- The default range is now to now+48 h. Leaving out explicit start and end keeps the URL valid at any time. It takes about 5–9 s warm.
- To match the frontend's 72 h range, add `&start=<now ISO>&end=<now+72h ISO>`, for example `...&start=2026-11-20T01:00:00Z&end=2026-11-23T01:00:00Z`.
- Snapshot at 4:35 PM PT, default range:
  - **Top window:** Sat Nov 21, 3:29–4:35 PM PT (2026-11-21T23:29Z–2026-11-22T00:35Z), score **96.4**, confidence **0.20**, `eligible: false`, `best_score: null`.
  - **Other windows:** Sat 8:44–9:43 AM PT (96.0) and Fri 8:15–9:23 AM PT (94.6).
  - **Over 72 h:** the top window was Sun Nov 22, 9:15–10:10 AM PT, score 97.4.
- **Factors:**
  - slack water, good (`coops_currents`, station SFB1201)
  - current 0.29 kt, good (`coops_currents`)
  - moon phase 0.41, fair (`offline_lunar`, computed; not a live feed)
- **Gates:**
  - Pass: `season_open` (2026-11-07 to 2027-06-30); `gear_allowed` (hoop net, citing 14 CCR §29.80(b)(2)); `dungeness_water` (Pillar Point is not a prohibited water).
  - **Can't confirm:** `no_domoic_advisory` (CDPH shellfish status unknown) and `no_bloom` (satellite chlorophyll is stale; its last observation is 2026-11-08).
- **Every displayed number has a source.** Each factor carries `source` and `observed_at`, each gate carries `evidence: cited:[...]`, and the response-level `health[]` lists per-adapter status.
- **No window is eligible today, for any activity.** This is the safety design working, not a bug: a gate that can't be confirmed is never treated as a pass.

## Click-by-click demo sequence (about 2 min)

1. **0:00** Open https://tidewise-asunny.vercel.app, already warm. The **Planner** tab is the default and **Crabbing** is pre-selected. Point out that the page loads live data, with no example banner.
2. **0:15** Read the heading "Where and when should you go crabbing?" and the backend note: _"a gate that cannot be confirmed … is not a pass."_
3. **0:25** Scroll to **Saturday** and click the **Pillar Point Harbor / Princeton** window that scores about 96. The detail panel opens on the right; on mobile it opens below.
4. **0:35** Walk through the gates: three green **Pass** (season, hoop-net gear rule with the regulation cited, Dungeness water). Then two **Check advisory**: CDPH domoic acid status unknown, chlorophyll stale.
5. **0:55** Scroll to **Live data sources**. Show NOAA tides OK, NOAA currents, SST, NWS alerts, EPA UV, daylight, and CDPH shellfish **Unavailable**, chlorophyll **Source stale**.
6. **1:10** Click the **Clamming** tab and wait about 9 s. Show the Pillar Point minus-tide window: Sun Nov 22, about 1:33 PM, tide −0.63 ft MLLW, about 82–86. It is also "Check before you go" for the same CDPH and chlorophyll reasons.
7. **1:30** Optional: open the raw API URL above in the second tab to show `factors[].source`, `gates[].evidence` and `eligible: false`.
8. **1:45** Close: "TideWise would rather say *check before you go* than invent a green light."

**Do not open the "Quick score" tab during judging.** It calls `/score`, which returns fixed heuristic scores (for example swimming 62/100, or clamming 74/100 for a night-time window). No safety gates are applied there, and the card is labeled "Unscreened timing estimate". It contradicts the Planner. Swimming and Sailing in the Planner are live but show every window as "Check before you go", and sailing scores 0, because there is no NWS marine/alerts mapping and no forward wind/wave data. Skip both.

## 90-second narration

> "Planning a day on the coast means juggling tide tables, current predictions, fishing regulations, and health advisories. TideWise pulls them into one answer: where and when to go, and whether it's safe to.
>
> This is live. The backend just queried NOAA tide and current predictions, satellite sea-surface temperature and chlorophyll, NWS alerts, EPA UV, sunrise/sunset, and California's shellfish and beach-bacteria feeds.
>
> For crabbing at Pillar Point with a hoop net, the best window is Saturday around 3:30 PM. That's slack water from NOAA's current predictions, and it scores 96 out of 100. Open it, and every gate shows its evidence: season open, hoop nets allowed under the cited CDFW rule, and Pillar Point isn't a prohibited Dungeness water.
>
> But look at these two. California's shellfish biotoxin feed isn't returning a dated status right now, and the satellite chlorophyll is eleven days old. Most apps would quietly treat missing data as 'all clear'. TideWise refuses. A safety gate we can't confirm is never a pass. So instead of a green light, you get 'Check before you go', and the exact reason why.
>
> Here's our live source panel. You can see which feeds are healthy and which are down at this moment. Switch to clamming: there's a minus tide Sunday afternoon, −0.6 feet, which is great for clams. Same honesty: biotoxin status can't be confirmed.
>
> Every number on screen is traceable to a named public source and timestamp. When the data's there, TideWise gives you a ranked window. When it isn't, it tells you, and that's a feature, not a bug."

## Honest fallback plan (if a feed fails during judging)

| Symptom | What to do and say |
|---|---|
| Amber banner **"Live data unavailable — showing example data"** | The backend was asleep or slow (more than 45 s). Say: "That's the cold-start fallback, and it's labeled as example data." Open `/health` in the other tab, wait for JSON, then reload. Never narrate example numbers as live. |
| A source turns **Unavailable** or **stale** that was OK in rehearsal | Point at it in the Live data sources panel and show that the related gate switched to "Check advisory". That shows the safety design working. |
| NOAA CO-OPS fails, so no crabbing or clamming windows appear | Say so plainly. Show the raw `/recommend` JSON with `health[]` and the gate reasons. Do not switch to Quick score or to preview mode. |
| Whole backend down (`/health` not answering after 60 s) | Show screenshots from rehearsal, clearly introduced as "captured at <time> PT", plus the code that sets gate behavior (`backend/grid_builder.py`, `backend/source_aliases.py`). Say it's a recording. |
| CDPH or chlorophyll come back and a window turns **eligible** | Great. Show it, read its cited evidence, and note that `best_score` is now set. |

Health status is a per-adapter global snapshot: it reflects the most recent fetch for any spot. A source may therefore flip between OK and Unavailable from one request to the next. For example, NOAA currents shows "Unavailable" right after a fetch for a spot with no current station. If a judge asks, that's the reason.

## Known current blockers for an "eligible" window (do not bypass)

- **Crabbing and clamming:** `cdph_shellfish` is down (`observed_at_missing_not_fresh`), so `no_domoic_advisory` and `no_biotoxin_closure` can't be confirmed. `erddap_chl` is stale (last observation 2026-11-08, plus ERDDAP 429s), so `no_bloom` can't be confirmed.
- **Swimming:** `beachwatch_bacteria` data is about 13 years old, and `grid_builder` never treats bacteria as a confirmed clear. `nws_marine` has no adapter mapped (`source_aliases.py`). NDBC wave height is attached only to the observation hour, so future windows have none.
- **Sailing:** `nws_alerts` maps to `None` in `source_aliases.py`, although the adapter is healthy. NDBC wind, gust and wave are observation-hour only, so all four sailing gates can't be confirmed and the score is 0.
