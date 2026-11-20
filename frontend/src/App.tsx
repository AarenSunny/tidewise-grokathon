import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronUp, MapPin } from 'lucide-react';
import { ActivitySelector } from './components/ActivitySelector';
import { ApiStatus } from './components/ApiStatus';
import { BestPickBanner } from './components/BestPickBanner';
import { DetailPanel } from './components/DetailPanel';
import { GuidanceRail } from './components/GuidanceRail';
import { HeaderBar } from './components/HeaderBar';
import { LiveSourcesPanel } from './components/LiveSourcesPanel';
import { LiveWindowsByDay } from './components/LiveWindowsByDay';
import { PlannerControls } from './components/PlannerControls';
import { ScoreWindowCard } from './components/ScoreWindowCard';
import { SchematicMap } from './components/SchematicMap';
import { TimelineChart } from './components/TimelineChart';
import {
  CRABBING_GEAR,
  CRABBING_GEAR_OPTIONS,
  PLANNER_ACTIVITIES,
  type CrabbingGear,
  hasLiveWindows,
  recommendParamsForActivity,
} from './lib/crabbing';
import { loadPlannerData, type LoadedPlannerData } from './lib/loadPlannerData';
import { isTruthyEnvFlag } from './lib/sourceHealth';
import { toPlannerViewModel } from './lib/toViewModel';
import {
  DEFAULT_AVAILABILITY_ID,
  EXAMPLE_AVAILABILITY_OPTIONS,
  EXAMPLE_DAY,
  EXAMPLE_SPOT_META,
  getPreviewScenario,
} from './preview/exampleData';
import type { Activity, AvailabilityId, SpotWindowViewModel } from './types';

const forcePreview = isTruthyEnvFlag(import.meta.env.VITE_FORCE_PREVIEW);

export function App() {
  const [availabilityId, setAvailabilityId] = useState<AvailabilityId>(
    DEFAULT_AVAILABILITY_ID,
  );
  const [selectedSpotId, setSelectedSpotId] = useState<string | null>(null);
  const [showMobileMap, setShowMobileMap] = useState(false);
  const [activity, setActivity] = useState<Activity>(
    forcePreview ? 'clamming' : 'crabbing',
  );
  const [crabbingGear, setCrabbingGear] =
    useState<CrabbingGear>(CRABBING_GEAR);
  const [loaded, setLoaded] = useState<LoadedPlannerData | null>(null);
  const [loadState, setLoadState] = useState<'loading' | 'ready'>('loading');
  const [page, setPage] = useState<'planner' | 'score'>('planner');

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    const recParams = recommendParamsForActivity(activity, crabbingGear);
    setLoadState('loading');

    void (async () => {
      try {
        const result = await loadPlannerData({
          activity: recParams.activity,
          gear: recParams.gear,
          start: recParams.start,
          end: recParams.end,
          durationHours: recParams.durationHours,
          forcePreview,
          scenario: getPreviewScenario(),
          signal: controller.signal,
        });
        if (!cancelled) {
          setLoaded(result);
          setLoadState('ready');
        }
      } catch {
        // Request was aborted on unmount; ignore.
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [activity, crabbingGear]);

  const selectedAvailability = useMemo(
    () =>
      EXAMPLE_AVAILABILITY_OPTIONS.find((opt) => opt.id === availabilityId) ??
      EXAMPLE_AVAILABILITY_OPTIONS[0],
    [availabilityId],
  );

  const viewModel = useMemo(() => {
    if (!loaded) return null;
    return toPlannerViewModel({
      response: loaded.response,
      spotMeta: EXAMPLE_SPOT_META,
      day: EXAMPLE_DAY,
      availability: selectedAvailability,
      isExampleData: loaded.isExampleData,
      exampleBannerText: loaded.exampleBannerText,
      dataMode: loaded.dataMode,
      freshnessAsOf: loaded.freshnessAsOf,
      spots: loaded.spots,
      scoringPending: loaded.scoringPending,
      backendNote: loaded.backendNote,
      liveSpots: loaded.liveSpots,
    });
  }, [loaded, selectedAvailability]);

  const selectedSpot: SpotWindowViewModel | null = useMemo(() => {
    if (!selectedSpotId || !viewModel) return null;
    return (
      viewModel.rankedSpots.find((s) => s.spotId === selectedSpotId) ??
      viewModel.notRankedSpots.find((s) => s.spotId === selectedSpotId) ??
      null
    );
  }, [selectedSpotId, viewModel]);

  const handleSelectSpot = (spot: SpotWindowViewModel) => {
    setSelectedSpotId(spot.spotId);
  };

  const bannerTestId =
    loaded?.dataMode === 'fallback'
      ? 'live-data-unavailable-banner'
      : loaded?.scoringPending
        ? 'scoring-pending-banner'
        : 'data-mode-banner';

  const bannerTone =
    loaded?.dataMode === 'fallback'
      ? 'border-amber-500/40 bg-amber-50 text-amber-900'
      : loaded?.scoringPending
        ? 'border-teal-100 bg-teal-50 text-teal-800'
        : 'border-navy-100 bg-navy-100/60 text-navy-800';

  return (
    <div className="min-h-screen bg-sand-50 text-navy-900">
      <HeaderBar
        regionLabel={viewModel?.day.regionLabel ?? EXAMPLE_DAY.regionLabel}
        isExampleData={viewModel?.isExampleData ?? true}
        exampleBannerText={
          viewModel?.exampleBannerText || 'Example data'
        }
      />

      {page === 'planner' && loaded && loaded.exampleBannerText && (
        <div
          role="status"
          data-testid={bannerTestId}
          className={`border-b ${bannerTone}`}
        >
          <div className="mx-auto max-w-[1360px] px-4 py-2 text-sm font-medium sm:px-6 lg:px-8">
            {loaded.exampleBannerText}
          </div>
        </div>
      )}

      <main className="mx-auto max-w-[1360px] px-4 pt-5 pb-12 sm:px-6 lg:px-8 lg:pt-7">
        <div
          role="tablist"
          aria-label="TideWise views"
          className="inline-flex gap-1 rounded-[12px] border border-sand-200 bg-white p-1"
        >
          <button
            type="button"
            role="tab"
            aria-selected={page === 'planner'}
            onClick={() => setPage('planner')}
            className={`rounded-[9px] px-3.5 py-1.5 text-sm font-medium ${
              page === 'planner'
                ? 'bg-navy-900 text-white shadow-xs'
                : 'text-navy-700 hover:bg-sand-100'
            }`}
          >
            Planner
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={page === 'score'}
            onClick={() => setPage('score')}
            className={`rounded-[9px] px-3.5 py-1.5 text-sm font-medium ${
              page === 'score'
                ? 'bg-navy-900 text-white shadow-xs'
                : 'text-navy-700 hover:bg-sand-100'
            }`}
          >
            Quick score
          </button>
        </div>

        {page === 'score' ? (
          <ScoreWindowCard />
        ) : loadState === 'loading' || !viewModel || !loaded ? (
          <div
            data-testid="planner-loading"
            className="mt-5 rounded-[16px] border border-sand-200 bg-white px-5 py-10 text-center shadow-[var(--shadow-card)]"
          >
            <div className="text-[11px] font-semibold tracking-[0.09em] text-teal-700 uppercase">
              TideWise
            </div>
            <p className="mt-2 text-sm text-navy-700">
              Checking live conditions…
            </p>
          </div>
        ) : (
          <>
            {/* Hero heading */}
            <div>
              <div className="text-[11px] font-semibold tracking-[0.09em] text-teal-700 uppercase">
                Planner · {viewModel.availability.overlineSuffix}
              </div>
              <h1 className="mt-1.5 font-display text-[28px] leading-[1.15] font-semibold tracking-tight text-navy-900 sm:text-[36px]">
                Where and when should you go {activity}?
              </h1>
            </div>

            {loaded.scoringPending && (
              <div
                data-testid="scoring-pending-panel"
                className="mt-5 rounded-[14px] border border-teal-100 bg-teal-50/90 px-4 py-3 text-[13px] leading-relaxed text-teal-800"
              >
                {loaded.liveSpots.length > 0 && (
                  <p className="font-medium">
                    Live spots:{' '}
                    {loaded.liveSpots.map((spot) => spot.name).join(', ')}
                  </p>
                )}
                {loaded.backendNote && (
                  <p className="mt-1.5" data-testid="backend-note">
                    {loaded.backendNote}
                  </p>
                )}
              </div>
            )}

            {/* Controls row */}
            <div className="mt-5 flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-center">
              <ActivitySelector
                activities={PLANNER_ACTIVITIES}
                selectedActivity={activity}
                onSelectActivity={setActivity}
              />
              {activity === 'crabbing' && (
                <label className="flex items-center gap-2 rounded-[12px] border border-sand-200 bg-white px-3 py-2 text-[13px] font-medium text-navy-700">
                  <span>Gear</span>
                  <select
                    aria-label="Crabbing gear"
                    value={crabbingGear}
                    onChange={(event) =>
                      setCrabbingGear(event.target.value as CrabbingGear)
                    }
                    className="rounded-[8px] border border-sand-200 bg-sand-50 px-2 py-1 text-navy-900 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                  >
                    {CRABBING_GEAR_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {!(
                loaded.dataMode === 'live' &&
                hasLiveWindows(loaded.liveResponse ?? loaded.response)
              ) && (
              <PlannerControls
                day={viewModel.day}
                availabilityOptions={EXAMPLE_AVAILABILITY_OPTIONS}
                selectedAvailabilityId={availabilityId}
                onChangeAvailability={setAvailabilityId}
              />
              )}
            </div>

            {loaded.dataMode === 'live' &&
            hasLiveWindows(loaded.liveResponse ?? loaded.response) ? (
              <div className="mt-6">
                {loaded.backendNote && (
                  <p
                    data-testid="backend-note"
                    className="mb-4 text-[13px] leading-relaxed text-navy-700"
                  >
                    {loaded.backendNote}
                  </p>
                )}
                <LiveWindowsByDay
                  response={loaded.liveResponse ?? loaded.response}
                  spots={loaded.spots}
                  activityLabel={activity.charAt(0).toUpperCase() + activity.slice(1)}
                />
                <div className="mt-6">
                  <LiveSourcesPanel
                    health={loaded.panelHealth}
                    sourcesAreLive={loaded.sourcesAreLive}
                    freshnessAsOf={loaded.freshnessAsOf}
                  />
                </div>
              </div>
            ) : activity !== 'clamming' && loaded.dataMode !== 'preview' ? (
              <div className="mt-6 rounded-[16px] border border-sand-200 bg-white px-5 py-8 text-sm text-navy-700 shadow-[var(--shadow-card)]">
                Live {activity} windows are unavailable right now. Switch to Clamming to
                review the example planner, or retry after the backend is
                reachable.
              </div>
            ) : (
            /* Main 2-column clamming grid on desktop */
            <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-12 lg:items-start">
              {/* Left 8 columns: Best pick + shared timeline comparison */}
              <div className="space-y-4 lg:col-span-8">
                <BestPickBanner
                  day={viewModel.day}
                  bestPick={viewModel.bestPick}
                  onSelectSpot={handleSelectSpot}
                />

                <TimelineChart
                  day={viewModel.day}
                  availability={viewModel.availability}
                  rankedSpots={viewModel.rankedSpots}
                  notRankedSpots={viewModel.notRankedSpots}
                  tradeoff={viewModel.tradeoff}
                  selectedSpotId={selectedSpot?.spotId ?? null}
                  onSelectSpot={handleSelectSpot}
                />

                {/* Mobile collapsible map trigger (keeps maps secondary) */}
                <div className="lg:hidden">
                  <button
                    type="button"
                    onClick={() => setShowMobileMap((prev) => !prev)}
                    aria-expanded={showMobileMap}
                    className="flex w-full items-center justify-center gap-2 rounded-[14px] border border-sand-200 bg-white px-4 py-3 text-sm font-medium text-navy-900 shadow-xs transition hover:bg-sand-50"
                  >
                    <MapPin className="h-4 w-4 text-teal-600" aria-hidden="true" />
                    <span>View spots on map</span>
                    {showMobileMap ? (
                      <ChevronUp className="h-4 w-4 text-navy-500" aria-hidden="true" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-navy-500" aria-hidden="true" />
                    )}
                  </button>

                  {showMobileMap && (
                    <div className="mt-3">
                      <SchematicMap
                        spots={viewModel.rankedSpots}
                        selectedSpotId={selectedSpot?.spotId ?? null}
                        onSelectSpot={handleSelectSpot}
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Right 4 columns: Detail panel when selected, or Guidance rail */}
              <div className="space-y-4 lg:col-span-4">
                {selectedSpot ? (
                  <DetailPanel
                    spot={selectedSpot}
                    totalRanked={viewModel.rankedSpots.length}
                    day={viewModel.day}
                    availability={viewModel.availability}
                    exampleBannerText={viewModel.exampleBannerText}
                    onClose={() => setSelectedSpotId(null)}
                  />
                ) : (
                  <div className="hidden lg:block">
                    <GuidanceRail
                      freshness={viewModel.freshness}
                      rankedSpots={viewModel.rankedSpots}
                      selectedSpotId={null}
                      onSelectSpot={handleSelectSpot}
                      isLiveChart={!viewModel.isExampleData}
                    />
                  </div>
                )}

                <LiveSourcesPanel
                  health={loaded.panelHealth}
                  sourcesAreLive={loaded.sourcesAreLive}
                  freshnessAsOf={loaded.freshnessAsOf}
                />
              </div>
            </div>
            )}
          </>
        )}

        <footer className="mt-8 border-t border-sand-200 pt-4 text-xs leading-relaxed text-navy-500">
          Planning aid only. Verify local closures, licenses, weather alerts, and official guidance before entering the water. Missing safety data never counts as safe.
          <ApiStatus />
        </footer>
      </main>
    </div>
  );
}

export default App;
