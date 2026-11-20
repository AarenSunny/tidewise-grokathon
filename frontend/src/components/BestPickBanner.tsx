import type { PlannerDayInfo, SpotWindowViewModel } from '../types';
import {
  formatDuration,
  formatRange,
  formatTime,
  getPeriod,
  formatTimeNoPeriod,
} from '../lib/time';

interface BestPickBannerProps {
  day: PlannerDayInfo;
  bestPick: SpotWindowViewModel | null;
  onSelectSpot: (spot: SpotWindowViewModel) => void;
}

export function BestPickBanner({
  day,
  bestPick,
  onSelectSpot,
}: BestPickBannerProps) {
  if (!bestPick) {
    return (
      <div className="rounded-[16px] bg-navy-900 px-5 py-4 text-white shadow-sm">
        <div className="text-[11px] font-semibold tracking-wider text-amber-500 uppercase">
          No verified pick for {day.shortLabel}
        </div>
        <div className="mt-1 font-display text-lg font-semibold sm:text-xl">
          No verified open spots overlap your selected hours
        </div>
        <p className="mt-1 text-sm text-navy-100">
          Switch your availability window or review the unverified and closed spots below.
        </p>
      </div>
    );
  }

  const arriveTime = formatTime(bestPick.clippedStartMinutes);
  const startNoPeriod = formatTimeNoPeriod(bestPick.clippedStartMinutes);
  const endNoPeriod = formatTimeNoPeriod(bestPick.clippedEndMinutes);
  const endPeriod = getPeriod(bestPick.clippedEndMinutes);
  const durationStr = formatDuration(bestPick.durationMinutes);
  const compactRange = formatRange(
    bestPick.clippedStartMinutes,
    bestPick.clippedEndMinutes,
  );

  return (
    <button
      type="button"
      onClick={() => onSelectSpot(bestPick)}
      className="w-full rounded-[16px] bg-navy-900 px-5 py-4 text-left text-white shadow-sm transition hover:bg-navy-700 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 focus-visible:outline-none sm:px-6 sm:py-5"
    >
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold tracking-[0.08em] text-teal-300 uppercase">
            Best pick for {day.label.split(',')[0]}
          </div>
          <div className="mt-1 font-display text-xl leading-snug font-semibold text-white sm:text-2xl">
            {bestPick.spotName} — arrive {arriveTime}
          </div>
          <div className="mt-1 text-[13px] text-navy-100 sm:hidden">
            Arrive {arriveTime} · {compactRange} · {durationStr}
          </div>
          <div className="mt-1 hidden text-[13px] text-navy-100 sm:block">
            {bestPick.bestPickTagline}
          </div>
        </div>

        <div className="hidden shrink-0 text-right sm:block">
          <div className="font-tabular text-[30px] leading-none font-semibold tracking-tight text-white">
            {startNoPeriod}–{endNoPeriod}
          </div>
          <div className="font-tabular mt-1.5 text-xs font-medium text-teal-300">
            {endPeriod} · {durationStr}
          </div>
        </div>
      </div>
    </button>
  );
}
