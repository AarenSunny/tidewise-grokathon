# TideWise Frontend

Coastal planner UI built with React, TypeScript, Vite, and Tailwind CSS v4.

Currently runs in **Example data** preview mode using `src/preview/exampleData.ts` shaped identically to the FastAPI `RecommendResponse` schema.

## Quick start

```bash
npm install
npm run dev
```

Open `http://localhost:5173`.

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

- `VITE_API_URL` or `VITE_API_BASE_URL` — Optional backend origin (defaults to `""`, using Vite's `/recommend`, `/spots`, `/health`, `/query` proxy to `http://localhost:8000`).

## Swapping in the FastAPI backend

1. Presentational components under `src/components/` receive only typed view-model props from `src/types.ts` — none of them import `src/preview/exampleData.ts`.
2. `src/types.ts` mirrors `backend/models/*.py` (`RecommendResponse`, `SpotRecommendation`, `ScoredWindow`, `GateResult`, `FactorBreakdown`, `AdapterHealth`, `Spot`, `QueryResponse`).
3. `src/lib/api.ts` exposes `fetchRecommend`, `fetchSpots`, `fetchHealth`, and `postQuery`.
4. `src/lib/toViewModel.ts` converts a `RecommendResponse` + spot metadata + the user's selected `AvailabilityWindow` into the `PlannerViewModel` rendered by `src/App.tsx`:
   - In `src/App.tsx`, replace `EXAMPLE_RECOMMEND_RESPONSE` with the result from `fetchRecommend({ activity: 'clamming' })` (and `fetchSpots()` for display metadata) and pass it directly into `toPlannerViewModel(...)`.
   - `toPlannerViewModel` clips windows to the user's selected availability and sunset, enforces the `no_biotoxin_closure` safety gate (`cannot_confirm = true` is treated as `unverified` and never outranks verified `open` spots; `passed = false, cannot_confirm = false` moves to `notRankedSpots`), and computes the `#1` vs `#2` duration tradeoff summary.
