# TideWise

**One answer, in seconds, to "Is now a good and safe time to go clamming, crabbing, swimming, or sailing in the San Francisco Bay?"**

Built at the Berkeley x Stanford Grok Bot Hackathon (SpaceXSI SF office) for Track 3: *Make space data useful*.

- **Live app:** https://tidewise-asunny.vercel.app (mirror: https://tidewise-two.vercel.app)
- **API:** https://tidewise-api.onrender.com (`/health`, `/spots`, `/recommend`, `/query`). It runs on Render's free tier, so the first request can take about 50 seconds while it wakes up.
- **Slides:** https://docs.google.com/presentation/d/1dUlozPYD897xqW1JyfsQNxPoVqmrxNKCozvRVlQtWTc/edit

## The problem

Planning a day on the Bay means checking a lot of separate sites: tide tables, buoy readings, marine weather alerts, satellite water temperature, shellfish toxin notices, and beach bacteria postings. Most people don't know all of these exist. The ones that matter most for safety, like a toxin closure or a bacteria warning, are the easiest to miss.

## What TideWise does

TideWise pulls live NASA, NOAA, and Earth-observation data into one place. It checks safety first, then rates conditions for four activities at researched Bay Area spots.

| | Before TideWise | With TideWise |
|---|---|---|
| Where you look | 6 to 10 separate agency sites | One app |
| Time | 20 minutes or more, if you know where to look | Seconds |
| Safety notices | Easy to miss | Checked first, and they override the score |
| Missing data | You might not notice | Shown with its date and marked as old |

## How it works

1. **Data layer.** 10 live public data feeds, documented and checked live in [`DATA_SOURCES.md`](DATA_SOURCES.md). They include NOAA CO-OPS Tides & Currents (tide predictions and water levels), NOAA NDBC buoys (waves, wind, water temperature), NOAA CoastWatch ERDDAP (satellite sea surface temperature and chlorophyll), NASA POWER (weather context), the National Weather Service alerts API, and the USNO moon and sun data API. `DATA_SOURCES.md` lists 16 researched spots, and the deployed API's `/spots` returns 15.
2. **Hard safety checks run before any score:**
   - Shellfish biotoxin closures (FDA action levels: PSP 80 µg/100 g, domoic acid 20 ppm) for clamming and crabbing.
   - Beach bacteria limits (EPA Beach Action Values for Enterococcus) for swimming.
   - NWS marine alerts (Small Craft Advisory, Gale, Rip Current, Beach Hazards).
   - A safety failure always overrides the score.
3. **Honest about missing data.**
   - The app shows UNKNOWN only when a live safety feed the activity needs actually fails.
   - Sources with no API (for example, state shellfish advisories) use a dated snapshot with a "check advisory, last verified <date>" note.
   - Each activity checks only the feeds it needs. Sailing doesn't check shellfish toxins, for example.
   - Each feed has a cached fallback, marked stale with its timestamp.
4. **Robustness.** It rejects bad buoy readings, such as NDBC placeholder values and physically impossible numbers. It can also simulate a dead feed to show the fallback working.

## Built today vs. next

**Built today**
- FastAPI backend (`backend/`) and a Vite/React frontend (`frontend/`), both deployed.
- Live connections to the data feeds, with per-feed health tracking (`/health`).
- The `/spots` catalog of Bay Area spots.
- Safety-check rules and thresholds, with sources cited in `DATA_SOURCES.md`.
- Data validation, stale-cache fallback, and dead-feed simulation.
- Tests, plus live API check scripts in `scripts/research_probes/`.

**Next (not working yet)**
- **Scored time windows.** As of 4:19 PM PT, `/recommend?activity=clamming&spot=pillar_point_harbor` connects to the feeds but returns `windows: []` and `best_score: null`. The next step is finishing the scoring step that turns live data into ranked "best time to go" windows.
- **Plain-English questions** through `/query`, such as "Can I take my kids crabbing this weekend?" The bots that would read the question and explain the answer (IntentBot and ExplainerBot) are planned but not built.
- A satellite map layer, "notify me when conditions are good" alerts, and spots beyond the Bay Area.

## How we built it: Grok Bot and Cursor

A team of Grok Bot assistants did most of the research, data work, verification, and repo updates, each in its own role:

| Bot | What it did |
|---|---|
| **Grok Bot** | Picked the APIs and designed the data layer |
| **Specific** | Researched each activity: conditions that matter, cited thresholds, scoring logic, safety and regulatory flags, and data feeds |
| **Henry Reader** | Checked every API in `DATA_SOURCES.md` live and pushed the research to the repo |
| **API changer presentation** (with Grok Bot) | Edited the slide deck |
| **extra task** | Audited the repo and coordinated the final submission |
| **Cursor cloud agent** | Made the commits to this repo |

**Grok Bot features we used**
- **Multiple bots handing work to each other.** Bots passed research, rule changes, and deadlines back and forth with no copy-pasting by people.
- **A shared computer.** All the bots work on one computer, so briefs and files were shared through it.
- **Skills and memory.** Reusable instructions, and project context remembered between sessions.
- **Connectors** for Google Slides (the deck) and GitHub (the repo).
- **A Cursor cloud agent** for committing code.
- **Approvals.** Risky actions, like pushing to the repo, needed a human's okay.

**Cursor** was used to write and refactor the backend and frontend. Cursor cloud agents committed changes to `main`.

## Run it locally

```bash
make install    # Python venv + backend deps + frontend npm install
make dev        # API on http://localhost:8000
make frontend   # Vite frontend on http://localhost:5173 (separate terminal)
make test       # pytest
```

## Disclaimer

TideWise is a planning aid, not an official safety source. Always check current agency advisories (CDPH, CDFW, NWS, local beach programs) before harvesting shellfish, swimming, or going out on the water.
