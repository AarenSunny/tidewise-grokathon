import { useMemo, useState } from 'react';
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
import type { AvailabilityId, SpotWindowViewModel } from './types';

export function App() {
  const [availabilityId, setAvailabilityId] = useState<AvailabilityId>(
    DEFAULT_AVAILABILITY_ID,
  );
  const [selectedSpotId, setSelectedSpotId] = useState<string | null>(null);
  const [showMobileMap, setShowMobileMap] = useState(false);

  const selectedAvailability = useMemo(
    () =>
      EXAMPLE_AVAILABILITY_OPTIONS.find((opt) => opt.id === availabilityId) ??
      EXAMPLE_AVAILABILITY_OPTIONS[0],
    [availabilityId],
  );

  const viewModel = useMemo(
    () =>
      toPlannerViewModel({
        response: EXAMPLE_RECOMMEND_RESPONSE,
        spotMeta: EXAMPLE_SPOT_META,
        day: EXAMPLE_DAY,
        availability: selectedAvailability,
        isExampleData: true,
        exampleBannerText: EXAMPLE_DATA_BANNER_TEXT,
      }),
    [selectedAvailability],
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

  return (
    <div className="min-h-screen bg-sand-50 text-navy-900">
      <HeaderBar
        regionLabel={viewModel.day.regionLabel}
        isExampleData={viewModel.isExampleData}
        exampleBannerText={viewModel.exampleBannerText}
      />

      <main className="mx-auto max-w-[1360px] px-4 pt-5 pb-12 sm:px-6 lg:px-8 lg:pt-7">
        {/* Hero heading */}
        <div>
          <div className="text-[11px] font-semibold tracking-[0.09em] text-teal-700 uppercase">
            Planner · {viewModel.availability.overlineSuffix}
          </div>
          <h1 className="mt-1.5 font-display text-[28px] leading-[1.15] font-semibold tracking-tight text-navy-900 sm:text-[36px]">
            Where and when should you go clamming?
          </h1>
        </div>

        {/* Controls row */}
        <div className="mt-5 flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-center">
          <ActivitySelector
            activities={EXAMPLE_ACTIVITIES}
            selectedActivity={viewModel.activity}
          />
          <PlannerControls
            day={viewModel.day}
            availabilityOptions={EXAMPLE_AVAILABILITY_OPTIONS}
            selectedAvailabilityId={availabilityId}
            onChangeAvailability={setAvailabilityId}
          />
        </div>

        {/* Main 2-column grid on desktop */}
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
          <div className="lg:col-span-4">
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
                />
              </div>
            )}
          </div>
        </div>
        <footer className="mt-8 border-t border-sand-200 pt-4 text-xs leading-relaxed text-navy-500">
          Planning aid only. Verify local closures, licenses, weather alerts, and official guidance before entering the water. Missing safety data never counts as safe.
          <ApiStatus />
        </footer>
      </main>
    </div>
  );
}

export default App;
