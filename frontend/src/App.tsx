import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronUp, MapPin } from 'lucide-react';
import { ActivitySelector } from './components/ActivitySelector';
import { BestPickBanner } from './components/BestPickBanner';
import { DetailPanel } from './components/DetailPanel';
import { GuidanceRail } from './components/GuidanceRail';
import { ApiStatus } from './components/ApiStatus';
import { HeaderBar } from './components/HeaderBar';
import { PlannerControls } from './components/PlannerControls';
import { SchematicMap } from './components/SchematicMap';
import { TimelineChart } from './components/TimelineChart';
import { fetchRecommend } from './lib/api';
import { toPlannerViewModel } from './lib/toViewModel';
import {
  DEFAULT_AVAILABILITY_ID,
  EXAMPLE_ACTIVITIES,
  EXAMPLE_AVAILABILITY_OPTIONS,
  EXAMPLE_DATA_BANNER_TEXT,
  EXAMPLE_DAY,
  EXAMPLE_RECOMMEND_RESPONSE,
  EXAMPLE_SPOT_META,
} from './preview/exampleData';
import type {
  Activity,
  AvailabilityId,
  PlannerDayInfo,
  RecommendResponse,
  SpotDisplayMeta,
  SpotWindowViewModel,
} from './types';

type LoadPhase = 'loading' | 'live' | 'example';

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError';
}

function dayFromResponse(response: RecommendResponse): PlannerDayInfo {
  const start = response.start ? new Date(response.start) : new Date();
  const zone = 'America/Los_Angeles';
  const label = new Intl.DateTimeFormat('en-US', {
    timeZone: zone,
    weekday: 'long',
    month: 'short',
    day: 'numeric',
  }).format(start);
  const shortLabel = new Intl.DateTimeFormat('en-US', {
    timeZone: zone,
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  }).format(start);
  const dateIso = new Intl.DateTimeFormat('en-CA', {
    timeZone: zone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(start);
  return {
    dateIso,
    label,
    shortLabel,
    regionLabel: EXAMPLE_DAY.regionLabel,
    axisStartMinutes: 6 * 60,
    axisEndMinutes: 21 * 60,
    sunsetTime: '5:00 PM',
    sunsetMinutes: 17 * 60,
  };
}

function spotMetaFor(response: RecommendResponse): Record<string, SpotDisplayMeta> {
  const meta: Record<string, SpotDisplayMeta> = { ...EXAMPLE_SPOT_META };
  response.recommendations.forEach((rec, index) => {
    if (meta[rec.spot_id]) return;
    meta[rec.spot_id] = {
      area: 'Bay Area coast',
      mapPosition: { x: 18 + (index % 5) * 16, y: 28 + (index % 4) * 16 },
    };
  });
  return meta;
}

export function App() {
  const [activity, setActivity] = useState<Activity>('clamming');
  const [availabilityId, setAvailabilityId] = useState<AvailabilityId>(
    DEFAULT_AVAILABILITY_ID,
  );
  const [selectedSpotId, setSelectedSpotId] = useState<string | null>(null);
  const [showMobileMap, setShowMobileMap] = useState(false);
  const [phase, setPhase] = useState<LoadPhase>('loading');
  const [liveResponse, setLiveResponse] = useState<RecommendResponse | null>(null);

  const activities = useMemo(
    () =>
      EXAMPLE_ACTIVITIES.map((item) => ({
        ...item,
        enabled: true,
        comingSoonLabel: undefined,
      })),
    [],
  );

  useEffect(() => {
    const controller = new AbortController();
    setPhase('loading');
    setLiveResponse(null);
    setSelectedSpotId(null);
    fetchRecommend({ activity, signal: controller.signal })
      .then((response) => {
        const hasWindows = response.recommendations.some((rec) => rec.windows.length > 0);
        if (!hasWindows) {
          setPhase('example');
          return;
        }
        setLiveResponse(response);
        setPhase('live');
      })
      .catch((error: unknown) => {
        if (isAbortError(error)) return;
        setPhase('example');
      });
    return () => controller.abort();
  }, [activity]);

  const selectedAvailability = useMemo(
    () =>
      EXAMPLE_AVAILABILITY_OPTIONS.find((opt) => opt.id === availabilityId) ??
      EXAMPLE_AVAILABILITY_OPTIONS[0],
    [availabilityId],
  );

  const usingExample = phase === 'example';
  const response = usingExample || liveResponse == null ? EXAMPLE_RECOMMEND_RESPONSE : liveResponse;

  const viewModel = useMemo(
    () =>
      toPlannerViewModel({
        response,
        spotMeta: usingExample ? EXAMPLE_SPOT_META : spotMetaFor(response),
        day: usingExample ? EXAMPLE_DAY : dayFromResponse(response),
        availability: selectedAvailability,
        isExampleData: usingExample,
        exampleBannerText: EXAMPLE_DATA_BANNER_TEXT,
      }),
    [response, selectedAvailability, usingExample],
  );

  const selectedSpot: SpotWindowViewModel | null = useMemo(() => {
    if (!selectedSpotId) return null;
    return (
      viewModel.rankedSpots.find((s) => s.spotId === selectedSpotId) ??
      viewModel.notRankedSpots.find((s) => s.spotId === selectedSpotId) ??
      null
    );
  }, [selectedSpotId, viewModel.rankedSpots, viewModel.notRankedSpots]);

  const handleSelectSpot = (spot: SpotWindowViewModel) => {
    setSelectedSpotId(spot.spotId);
  };

  const headingActivity =
    activities.find((item) => item.id === (phase === 'live' ? activity : viewModel.activity))
      ?.label.toLowerCase() ?? activity;

  return (
    <div className="min-h-screen bg-sand-50 text-navy-900">
      <HeaderBar
        regionLabel={viewModel.day.regionLabel}
        isExampleData={usingExample}
        exampleBannerText={viewModel.exampleBannerText}
      />

      <main className="mx-auto max-w-[1360px] px-4 pt-5 pb-12 sm:px-6 lg:px-8 lg:pt-7">
        <div>
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold tracking-[0.09em] text-teal-700 uppercase">
            <span>Planner · {viewModel.availability.overlineSuffix}</span>
            {phase === 'live' && (
              <span
                className="rounded-full border border-teal-600/30 bg-teal-600/10 px-2 py-0.5 text-[10px] tracking-normal text-teal-700 normal-case"
                data-testid="live-data-label"
              >
                Live data
              </span>
            )}
          </div>
          <h1 className="mt-1.5 font-display text-[28px] leading-[1.15] font-semibold tracking-tight text-navy-900 sm:text-[36px]">
            Where and when should you go {headingActivity}?
          </h1>
        </div>

        <div className="mt-5 flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-center">
          <ActivitySelector
            activities={activities}
            selectedActivity={activity}
            onSelectActivity={setActivity}
          />
          <PlannerControls
            day={viewModel.day}
            availabilityOptions={EXAMPLE_AVAILABILITY_OPTIONS}
            selectedAvailabilityId={availabilityId}
            onChangeAvailability={setAvailabilityId}
          />
        </div>

        {phase === 'loading' ? (
          <p className="mt-6 text-sm text-navy-500">Loading live recommendations…</p>
        ) : (
          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-12 lg:items-start">
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

            <div className="lg:col-span-4">
              {selectedSpot ? (
                <DetailPanel
                  spot={selectedSpot}
                  totalRanked={viewModel.rankedSpots.length}
                  day={viewModel.day}
                  availability={viewModel.availability}
                  exampleBannerText={usingExample ? viewModel.exampleBannerText : ''}
                  onClose={() => setSelectedSpotId(null)}
                />
              ) : (
                <div className="hidden lg:block">
                  <GuidanceRail
                    freshness={viewModel.freshness}
                    rankedSpots={viewModel.rankedSpots}
                    selectedSpotId={null}
                    onSelectSpot={handleSelectSpot}
                  />
                </div>
              )}
            </div>
          </div>
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
