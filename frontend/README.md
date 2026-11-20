# TideWise Frontend

Coastal planner UI built with React, TypeScript, Vite, and Tailwind CSS v4.

On load the app calls `/recommend` and `/health` (and `/spots` best-effort) through `src/lib/api.ts`. If either required endpoint errors, times out (4s), returns 501/non-2xx, or fails to parse, it falls back to labeled example data from `src/preview/exampleData.ts` and shows the banner **Live data unavailable — showing example data**.

When live data arrives but every recommendation has an empty `windows` array (current phase3-core scoring is not wired), the app shows **Scoring pending: live sources connected, rankings shown use example data**, keeps the example chart, and displays the backend `note` plus a **Live data sources** panel from `/health`.

## Quick start

```bash
npm install
npm run dev
```

Open `http://localhost:5173`.

Demo the stale-source robustness proof with `http://localhost:5173/?scenario=stale` (uses the example-data variant in `src/preview/exampleData.ts`).

## Scripts

- `npm run dev` — Start Vite dev server on port `5173` (proxies `/query`, `/recommend`, `/health`, `/spots`, `/debug` to `http://localhost:8000`)
- `npm run build` — Run TypeScript project build (`tsc -b`) and Vite production bundle
- `npm run typecheck` — Run `tsc --noEmit`
- `npm run lint` — Run ESLint across `src/`
- `npm run preview` — Preview the production build locally

## Environment variables

Copy `.env.example` to `.env` if you want to override the same-origin Vite proxy:

```bash
cp .env.example .env
```

- `VITE_API_BASE_URL` — Optional backend origin. Takes precedence over `VITE_API_URL`. Defaults to `""`, using Vite's `/recommend`, `/spots`, `/health`, `/query` proxy to `http://localhost:8000`.
- `VITE_API_URL` — Alternate backend origin used by the Render/Vercel helper. Used when `VITE_API_BASE_URL` is unset.
- `VITE_FORCE_PREVIEW` — Truthy values (`1`, `true`, `yes`, `on`) skip the network and always show labeled example data in preview mode (`Preview mode — showing example data`).

## Swapping in the FastAPI backend

1. Presentational components under `src/components/` receive only typed view-model props from `src/types.ts` — none of them import `src/preview/exampleData.ts`.
2. `src/types.ts` mirrors `backend/models/*.py` (`RecommendResponse`, `SpotRecommendation`, `ScoredWindow`, `GateResult`, `FactorBreakdown`, `AdapterHealth`, `Spot`, `QueryResponse`), including phase3-core fields (`note`, `distances_km`, `distance_km`, `gates_all_passed`, `SourceStatus` including `unknown`, and optional spot fields).
3. `src/lib/api.ts` exposes `fetchRecommend`, `fetchSpots`, `fetchHealth`, and `postQuery`. `fetchRecommend` sends timezone-aware `start`/`end` query params with an `America/Los_Angeles` numeric offset (the backend 422s on naive timestamps). Optional `lat`, `lon`, and `limit` are supported.
4. `src/lib/toViewModel.ts` converts a `RecommendResponse` + spot metadata + the user's selected `AvailabilityWindow` into the `PlannerViewModel` rendered by `src/App.tsx`:
   - Health source names `noaa_tides` and `daylight_table` are mapped to `coops_tides` and `daylight_sunrise_api` (`cdph_shellfish` already matches).
   - Stale, down, or unknown safety sources are never treated as verified-safe (cannot-confirm).
   - Windows are clipped to the user's selected availability and sunset, and `#1` vs `#2` duration tradeoffs are computed only among verified-safe spots.
5. The footer includes `ApiStatus`, which probes `/health` and `/spots` through the same API client.
