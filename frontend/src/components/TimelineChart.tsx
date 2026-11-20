import { ArrowLeftRight, Sunset } from 'lucide-react';
import type {
  AvailabilityWindow,
  PlannerDayInfo,
  SpotWindowViewModel,
  TradeoffSummary,
} from '../types';
import {
  formatDuration,
  formatHourTick,
  formatRange,
  minutesToAxisPercent,
} from '../lib/time';
import { StatusBadge } from './StatusBadge';

interface TimelineChartProps {
  day: PlannerDayInfo;
  availability: AvailabilityWindow;
  rankedSpots: SpotWindowViewModel[];
  notRankedSpots: SpotWindowViewModel[];
  tradeoff: TradeoffSummary | null;
  selectedSpotId: string | null;
  onSelectSpot: (spot: SpotWindowViewModel) => void;
}

function buildHourTicks(startMinutes: number, endMinutes: number): number[] {
  const startHour = Math.floor(startMinutes / 60);
  const endHour = Math.ceil(endMinutes / 60);
  const hours: number[] = [];
  for (let h = startHour; h <= endHour; h += 1) {
    hours.push(h);
  }
  return hours;
}

export function TimelineChart({
  day,
  availability,
  rankedSpots,
  notRankedSpots,
  tradeoff,
  selectedSpotId,
  onSelectSpot,
}: TimelineChartProps) {
  const { axisStartMinutes, axisEndMinutes, sunsetMinutes, sunsetTime } = day;
  const hourTicks = buildHourTicks(axisStartMinutes, axisEndMinutes);

  const availStartPct = minutesToAxisPercent(
    availability.startMinutes,
    axisStartMinutes,
    axisEndMinutes,
  );
  const availEndPct = minutesToAxisPercent(
    availability.endMinutes,
    axisStartMinutes,
    axisEndMinutes,
  );
  const sunsetPct = minutesToAxisPercent(
    sunsetMinutes,
    axisStartMinutes,
    axisEndMinutes,
  );

  const maxTradeoffDuration = Math.max(
    tradeoff?.spot1DurationMinutes ?? 1,
    tradeoff?.spot2DurationMinutes ?? 1,
  );

  return (
    <section
      aria-label="Spot comparison timeline"
      className="rounded-[16px] border border-sand-200 bg-white p-4 shadow-[var(--shadow-card)] sm:p-6"
    >
      {/* Card Header + Desktop Legend */}
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-start">
        <div>
          <h2 className="text-[17px] font-semibold tracking-tight text-navy-900 sm:text-lg">
            <span className="md:hidden">
              {rankedSpots.length} spots on the same clock
            </span>
            <span className="hidden md:inline">
              Recommended windows · same clock
            </span>
          </h2>
          <p className="mt-0.5 text-[13px] text-navy-500">
            <span className="md:hidden">Tap a spot to see why it ranked there</span>
            <span className="hidden md:inline">
              Tap a window to see why it ranked there
            </span>
          </p>
        </div>

        {/* Desktop legend */}
        <div className="hidden flex-wrap items-center gap-3.5 text-xs text-navy-700 md:flex">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3 w-5 rounded-[4px] bg-teal-600" aria-hidden="true" />
            Top pick
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="h-3 w-5 rounded-[4px] border border-teal-600 bg-teal-50"
              aria-hidden="true"
            />
            Other option
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="h-3 w-5 rounded-[4px] border border-dashed border-amber-500 bg-amber-50"
              aria-hidden="true"
            />
            Can&apos;t verify
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className="h-3 w-4 rounded-[3px] border border-sand-300/70 bg-sand-200/70"
              aria-hidden="true"
            />
            Outside your hours
          </span>
        </div>
      </div>

      {/* =================================================================== */}
      {/* DESKTOP TIMELINE (md and up)                                        */}
      {/* =================================================================== */}
      <div className="mt-5 hidden md:block">
        {/* Availability pill + hour axis ticks */}
        <div className="grid grid-cols-[215px_1fr] items-end gap-4">
          <div />
          <div>
            {/* Free window banner aligned to axis */}
            <div className="relative mb-2 h-6">
              <div
                style={{
                  left: `${availStartPct}%`,
                  width: `${Math.max(0, availEndPct - availStartPct)}%`,
                }}
                className="absolute inset-y-0 flex items-center justify-center rounded-full bg-teal-50 px-2 text-xs font-medium text-teal-800"
              >
                <span className="truncate">{availability.axisCaption}</span>
              </div>
            </div>

            {/* Hour tick labels */}
            <div className="relative h-5 text-[11px] font-medium text-navy-500">
              {hourTicks.map((hour, idx) => {
                const pct = minutesToAxisPercent(
                  hour * 60,
                  axisStartMinutes,
                  axisEndMinutes,
                );
                const translateClass =
                  idx === 0
                    ? 'translate-x-0'
                    : idx === hourTicks.length - 1
                      ? '-translate-x-full'
                      : '-translate-x-1/2';
                const inAvailability =
                  hour * 60 >= availability.startMinutes &&
                  hour * 60 <= availability.endMinutes;
                return (
                  <span
                    key={hour}
                    style={{ left: `${pct}%` }}
                    className={`font-tabular absolute top-0 whitespace-nowrap ${translateClass} ${
                      inAvailability ? 'font-semibold text-navy-700' : 'text-navy-300'
                    }`}
                  >
                    {formatHourTick(hour, false)}
                  </span>
                );
              })}
            </div>
          </div>
        </div>

        {/* Continuous shared plot grid + spot rows */}
        <div className="relative mt-1">
          {/* Background plot overlay spanning the right column across ALL rows */}
          <div className="pointer-events-none absolute inset-0 grid grid-cols-[215px_1fr] gap-4">
            <div />
            <div className="relative overflow-hidden rounded-[10px] border border-sand-200/90 bg-sand-50/45">
              {/* Shaded outside availability (left) */}
              {availStartPct > 0 && (
                <div
                  style={{ left: '0%', width: `${availStartPct}%` }}
                  className="absolute inset-y-0 bg-sand-200/70"
                />
              )}
              {/* Shaded outside availability (right) */}
              {availEndPct < 100 && (
                <div
                  style={{
                    left: `${availEndPct}%`,
                    width: `${100 - availEndPct}%`,
                  }}
                  className="absolute inset-y-0 bg-sand-200/70"
                />
              )}
              {/* Vertical hour gridlines */}
              {hourTicks.slice(1, -1).map((hour) => {
                const pct = minutesToAxisPercent(
                  hour * 60,
                  axisStartMinutes,
                  axisEndMinutes,
                );
                return (
                  <div
                    key={hour}
                    style={{ left: `${pct}%` }}
                    className="absolute inset-y-0 w-px bg-sand-200/90"
                  />
                );
              })}
              {/* Sunset vertical line */}
              <div
                style={{ left: `${sunsetPct}%` }}
                className="absolute inset-y-0 z-10 w-[1.5px] bg-navy-700/80"
              />
            </div>
          </div>

          {/* Spot rows */}
          <div className="relative z-10 divide-y divide-sand-200/70">
            {rankedSpots.map((spot) => {
              const startPct = minutesToAxisPercent(
                spot.clippedStartMinutes,
                axisStartMinutes,
                axisEndMinutes,
              );
              const endPct = minutesToAxisPercent(
                spot.clippedEndMinutes,
                axisStartMinutes,
                axisEndMinutes,
              );
              const widthPct = Math.max(2, endPct - startPct);
              const isSelected = spot.spotId === selectedSpotId;
              const isNarrow = widthPct < 14;
              const isCompactBar = widthPct < 22;

              const showTradeoffGhost =
                spot.isTopPick &&
                tradeoff?.hasTradeoff &&
                tradeoff.comparisonSpanStartMinutes !== null &&
                tradeoff.comparisonSpanEndMinutes !== null;

              const ghostStartPct = showTradeoffGhost
                ? minutesToAxisPercent(
                    tradeoff.comparisonSpanStartMinutes!,
                    axisStartMinutes,
                    axisEndMinutes,
                  )
                : 0;
              const ghostEndPct = showTradeoffGhost
                ? minutesToAxisPercent(
                    tradeoff.comparisonSpanEndMinutes!,
                    axisStartMinutes,
                    axisEndMinutes,
                  )
                : 0;

              const barStyle =
                spot.closureStatus === 'unverified'
                  ? 'border-[1.5px] border-dashed border-amber-500 bg-amber-50 text-amber-900 hover:bg-amber-100/70'
                  : spot.isTopPick
                    ? 'bg-teal-600 text-white hover:bg-teal-700 shadow-xs'
                    : 'border-[1.5px] border-teal-600 bg-teal-50 text-navy-900 hover:bg-teal-100/80';

              return (
                <div
                  key={spot.spotId}
                  className="grid grid-cols-[215px_1fr] items-center gap-4"
                >
                  {/* Left label cell */}
                  <button
                    type="button"
                    onClick={() => onSelectSpot(spot)}
                    className="flex flex-col items-start justify-center rounded-l-[8px] py-3.5 pr-2 text-left transition hover:bg-sand-50/80 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
                  >
                    <div className="flex items-center gap-2">
                      <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-navy-900 text-[11px] font-bold text-white">
                        {spot.rank}
                      </span>
                      <span className="text-[14px] font-semibold text-navy-900">
                        {spot.spotName}
                      </span>
                    </div>
                    <div className="mt-0.5 pl-7 text-xs text-navy-500">
                      {spot.area}
                    </div>
                    <div className="mt-2 pl-7">
                      <StatusBadge
                        status={spot.closureStatus}
                        label={spot.closureLabel}
                      />
                    </div>
                  </button>

                  {/* Right timeline track cell */}
                  <div className="relative flex min-h-[92px] items-center">
                    {/* Dashed comparison ghost span on #1 when shorter than #2 */}
                    {showTradeoffGhost && ghostEndPct > ghostStartPct && (
                      <div
                        style={{
                          left: `${ghostStartPct}%`,
                          width: `${ghostEndPct - ghostStartPct}%`,
                        }}
                        className="pointer-events-none absolute z-10 flex h-12 items-center justify-center rounded-l-[10px] border border-r-0 border-dashed border-navy-300 bg-white/80 px-1.5 text-[11px] font-medium text-navy-700"
                      >
                        <span className="inline-flex items-center gap-1 whitespace-nowrap">
                          <ArrowLeftRight
                            className="h-3 w-3 shrink-0 text-navy-500"
                            aria-hidden="true"
                          />
                          <span>{formatDuration(tradeoff!.shorterByMinutes)} shorter</span>
                        </span>
                      </div>
                    )}

                    {/* Clickable window bar */}
                    <button
                      type="button"
                      data-testid={`spot-bar-${spot.spotId}`}
                      aria-label={`${spot.spotName}, ${formatRange(
                        spot.clippedStartMinutes,
                        spot.clippedEndMinutes,
                      )}, ${formatDuration(spot.durationMinutes)}, ${spot.closureLabel}`}
                      aria-pressed={isSelected}
                      onClick={() => onSelectSpot(spot)}
                      style={{
                        left: `${startPct}%`,
                        width: `${widthPct}%`,
                      }}
                      className={`absolute z-20 flex h-12 flex-col justify-center rounded-[10px] text-left transition focus-visible:ring-2 focus-visible:ring-navy-900 focus-visible:ring-offset-2 focus-visible:outline-none ${
                        isCompactBar ? 'px-2' : 'px-3'
                      } ${barStyle} ${
                        isSelected
                          ? 'ring-2 ring-navy-900 ring-offset-2 ring-offset-white'
                          : ''
                      }`}
                    >
                      {!isNarrow ? (
                        <>
                          <div
                            className={`font-tabular leading-tight font-semibold whitespace-nowrap ${
                              isCompactBar ? 'text-[11.5px]' : 'text-[13px]'
                            }`}
                          >
                            {formatRange(
                              spot.clippedStartMinutes,
                              spot.clippedEndMinutes,
                            )}
                          </div>
                          <div
                            className={`font-tabular mt-0.5 truncate text-[11px] leading-tight ${
                              spot.isTopPick
                                ? 'text-teal-50'
                                : spot.closureStatus === 'unverified'
                                  ? 'text-amber-700'
                                  : 'text-navy-500'
                            }`}
                          >
                            {formatDuration(spot.durationMinutes)}
                          </div>
                        </>
                      ) : (
                        <div className="font-tabular truncate text-[11px] font-semibold">
                          {formatDuration(spot.durationMinutes)}
                        </div>
                      )}
                    </button>

                    {/* If bar is very narrow, show full range right beside it */}
                    {isNarrow && (
                      <span
                        style={{ left: `calc(${endPct}% + 8px)` }}
                        className="font-tabular pointer-events-none absolute z-20 text-xs font-medium whitespace-nowrap text-navy-700"
                      >
                        {formatRange(
                          spot.clippedStartMinutes,
                          spot.clippedEndMinutes,
                        )}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Sunset & Outside-hours axis footer */}
        <div className="mt-2 grid grid-cols-[215px_1fr] gap-4">
          <div />
          <div className="relative h-6 text-[11px] font-medium text-navy-500">
            <div
              style={{ left: `${sunsetPct}%` }}
              className="absolute top-0 flex -translate-x-1/2 items-center gap-1 whitespace-nowrap text-navy-700"
            >
              <Sunset className="h-3.5 w-3.5 text-navy-700" aria-hidden="true" />
              <span className="font-tabular">Sunset {sunsetTime}</span>
            </div>
            {availEndPct < 100 && (
              <div
                style={{ left: `${(availEndPct + 100) / 2}%` }}
                className="absolute top-0 -translate-x-1/2 whitespace-nowrap text-navy-500"
              >
                Outside your hours
              </div>
            )}
          </div>
        </div>
      </div>

      {/* =================================================================== */}
      {/* MOBILE TIMELINE (< md) — stacked full-width tracks, zero horiz scroll */}
      {/* =================================================================== */}
      <div className="mt-4 md:hidden">
        {/* Shared clock header */}
        <div className="mb-3">
          <div className="relative mb-1.5 h-6">
            <div
              style={{
                left: `${availStartPct}%`,
                width: `${Math.max(0, availEndPct - availStartPct)}%`,
              }}
              className="absolute inset-y-0 flex items-center justify-center rounded-full bg-teal-50 px-2 text-[11px] font-medium whitespace-nowrap text-teal-800"
            >
              <span>Free · {availability.shortLabel}</span>
            </div>
          </div>
          <div className="relative h-4 text-[11px] font-medium">
            {hourTicks.map((hour, idx) => {
              const pct = minutesToAxisPercent(
                hour * 60,
                axisStartMinutes,
                axisEndMinutes,
              );
              const translateClass =
                idx === 0
                  ? 'translate-x-0'
                  : idx === hourTicks.length - 1
                    ? '-translate-x-full'
                    : '-translate-x-1/2';
              const inAvailability =
                hour * 60 >= availability.startMinutes &&
                hour * 60 <= availability.endMinutes;
              return (
                <span
                  key={hour}
                  style={{ left: `${pct}%` }}
                  className={`font-tabular absolute top-0 ${translateClass} ${
                    inAvailability ? 'font-semibold text-navy-900' : 'text-navy-300'
                  }`}
                >
                  {formatHourTick(hour, true)}
                </span>
              );
            })}
          </div>
        </div>

        {/* Mobile Spot Rows */}
        <div className="divide-y divide-sand-200 border-t border-sand-200">
          {rankedSpots.map((spot) => {
            const startPct = minutesToAxisPercent(
              spot.clippedStartMinutes,
              axisStartMinutes,
              axisEndMinutes,
            );
            const endPct = minutesToAxisPercent(
              spot.clippedEndMinutes,
              axisStartMinutes,
              axisEndMinutes,
            );
            const widthPct = Math.max(3, endPct - startPct);
            const isSelected = spot.spotId === selectedSpotId;

            const showTradeoffGhost =
              spot.isTopPick &&
              tradeoff?.hasTradeoff &&
              tradeoff.comparisonSpanStartMinutes !== null &&
              tradeoff.comparisonSpanEndMinutes !== null;

            const ghostStartPct = showTradeoffGhost
              ? minutesToAxisPercent(
                  tradeoff.comparisonSpanStartMinutes!,
                  axisStartMinutes,
                  axisEndMinutes,
                )
              : 0;
            const ghostEndPct = showTradeoffGhost
              ? minutesToAxisPercent(
                  tradeoff.comparisonSpanEndMinutes!,
                  axisStartMinutes,
                  axisEndMinutes,
                )
              : 0;

            return (
              <button
                key={spot.spotId}
                type="button"
                data-testid={`mobile-spot-card-${spot.spotId}`}
                onClick={() => onSelectSpot(spot)}
                className={`block w-full py-4 text-left transition focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none ${
                  isSelected ? 'bg-sand-50/70' : ''
                }`}
              >
                <div className="flex items-start gap-2.5">
                  <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-navy-900 text-[11px] font-bold text-white">
                    {spot.rank}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="text-[15px] font-semibold text-navy-900">
                      {spot.spotName}
                    </div>
                    <div className="text-xs text-navy-500">{spot.area}</div>
                  </div>
                </div>

                <div className="mt-2">
                  <StatusBadge
                    status={spot.closureStatus}
                    label={spot.closureLabel}
                  />
                </div>

                <div className="mt-2.5 flex items-baseline justify-between gap-2">
                  <span className="font-tabular text-xl font-semibold tracking-tight text-navy-900">
                    {formatRange(
                      spot.clippedStartMinutes,
                      spot.clippedEndMinutes,
                    )}
                  </span>
                  <span className="font-tabular text-xs font-medium text-navy-500">
                    {formatDuration(spot.durationMinutes)} window
                  </span>
                </div>

                {/* Shared clock mini track */}
                <div className="relative mt-2 h-7 w-full overflow-hidden rounded-[8px] border border-sand-200/80 bg-sand-50">
                  {availStartPct > 0 && (
                    <div
                      style={{ left: '0%', width: `${availStartPct}%` }}
                      className="absolute inset-y-0 bg-sand-200/75"
                    />
                  )}
                  {availEndPct < 100 && (
                    <div
                      style={{
                        left: `${availEndPct}%`,
                        width: `${100 - availEndPct}%`,
                      }}
                      className="absolute inset-y-0 bg-sand-200/75"
                    />
                  )}
                  {hourTicks.slice(1, -1).map((hour) => {
                    const pct = minutesToAxisPercent(
                      hour * 60,
                      axisStartMinutes,
                      axisEndMinutes,
                    );
                    return (
                      <div
                        key={hour}
                        style={{ left: `${pct}%` }}
                        className="absolute inset-y-0 w-px bg-sand-200/80"
                      />
                    );
                  })}

                  {/* Dashed ghost span */}
                  {showTradeoffGhost && ghostEndPct > ghostStartPct && (
                    <div
                      style={{
                        left: `${ghostStartPct}%`,
                        width: `${ghostEndPct - ghostStartPct}%`,
                      }}
                      className="absolute inset-y-1 rounded-[5px] border border-dashed border-navy-300 bg-white/75"
                    />
                  )}

                  {/* Spot window fill */}
                  <div
                    style={{ left: `${startPct}%`, width: `${widthPct}%` }}
                    className={`absolute inset-y-0.5 rounded-[6px] ${
                      spot.closureStatus === 'unverified'
                        ? 'border-[1.5px] border-dashed border-amber-500 bg-amber-50'
                        : spot.isTopPick
                          ? 'bg-teal-600'
                          : 'border-[1.5px] border-teal-600 bg-teal-50'
                    }`}
                  />

                  {/* Sunset line */}
                  <div
                    style={{ left: `${sunsetPct}%` }}
                    className="absolute inset-y-0 z-10 w-[1.5px] bg-navy-700/80"
                  />
                </div>

                {spot.isTopPick && tradeoff?.hasTradeoff && (
                  <div className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-sand-100 px-2.5 py-1 text-[11px] font-medium text-navy-700">
                    <ArrowLeftRight className="h-3 w-3 shrink-0 text-navy-500" aria-hidden="true" />
                    <span>
                      {formatDuration(tradeoff.shorterByMinutes)} shorter than #2 — but lower tide
                    </span>
                  </div>
                )}
              </button>
            );
          })}
        </div>

        {/* Mobile timeline legend */}
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-sand-200 pt-3 text-[11px] text-navy-500">
          <span className="inline-flex items-center gap-1 font-medium text-navy-700">
            <Sunset className="h-3.5 w-3.5 text-navy-700" aria-hidden="true" />
            <span className="font-tabular">Sunset {sunsetTime}</span>
          </span>
          <span className="inline-flex items-center gap-1">
            <span
              className="h-3 w-3 rounded-[2px] border border-sand-300 bg-sand-200/80"
              aria-hidden="true"
            />
            Outside your hours
          </span>
          {tradeoff?.hasTradeoff && (
            <span className="inline-flex items-center gap-1">
              <span
                className="h-3 w-3 rounded-[2px] border border-dashed border-navy-300 bg-white"
                aria-hidden="true"
              />
              Time #1 gives up vs #2
            </span>
          )}
        </div>
      </div>

      {/* =================================================================== */}
      {/* TRADEOFF SUMMARY CALLOUT                                            */}
      {/* =================================================================== */}
      {tradeoff && (
        <div
          data-testid="tradeoff-callout"
          className="mt-4 rounded-[12px] border border-sand-200 bg-sand-100/85 p-4"
        >
          <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 hidden h-8 w-8 shrink-0 items-center justify-center rounded-full bg-navy-900 text-white sm:flex">
                <ArrowLeftRight className="h-4 w-4" aria-hidden="true" />
              </div>
              <div>
                <div className="text-[13px] font-semibold text-navy-900">
                  {tradeoff.headline}
                </div>
                <p className="mt-1 text-[13px] leading-relaxed text-navy-700">
                  {tradeoff.body}
                </p>
              </div>
            </div>

            {/* Proportional duration comparison bars */}
            <div className="hidden shrink-0 space-y-1.5 lg:block lg:w-52">
              <div className="flex items-center gap-2 text-xs">
                <span className="font-tabular w-5 font-medium text-navy-500">
                  {tradeoff.spot1Label}
                </span>
                <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-sand-200/80">
                  <div
                    style={{
                      width: `${Math.round(
                        (tradeoff.spot1DurationMinutes / maxTradeoffDuration) * 100,
                      )}%`,
                    }}
                    className="h-full rounded-full bg-teal-600"
                  />
                </div>
                <span className="font-tabular w-12 text-right font-semibold text-navy-900">
                  {formatDuration(tradeoff.spot1DurationMinutes)}
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <span className="font-tabular w-5 font-medium text-navy-500">
                  {tradeoff.spot2Label}
                </span>
                <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-sand-200/80">
                  <div
                    style={{
                      width: `${Math.round(
                        (tradeoff.spot2DurationMinutes / maxTradeoffDuration) * 100,
                      )}%`,
                    }}
                    className="h-full rounded-full border border-teal-600 bg-teal-100"
                  />
                </div>
                <span className="font-tabular w-12 text-right font-semibold text-navy-900">
                  {formatDuration(tradeoff.spot2DurationMinutes)}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* NOT RANKED FOOTER (Closed / Out-of-hours spots)                     */}
      {/* =================================================================== */}
      {notRankedSpots.length > 0 && (
        <div className="mt-4 space-y-2 border-t border-sand-200/80 pt-3.5">
          {notRankedSpots.map((spot) => (
            <button
              key={spot.spotId}
              type="button"
              data-testid={`not-ranked-${spot.spotId}`}
              onClick={() => onSelectSpot(spot)}
              className="flex w-full flex-wrap items-center gap-x-2.5 gap-y-1.5 rounded-[8px] px-1 py-1 text-left text-xs transition hover:bg-sand-50 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
            >
              <span className="font-medium text-navy-500">Not ranked:</span>
              <span className="font-semibold text-navy-900">
                {spot.spotName} · {spot.area}
              </span>
              <StatusBadge
                status={spot.closureStatus}
                label={spot.closureLabel}
              />
              <span className="text-navy-500">{spot.notRankedReason}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
