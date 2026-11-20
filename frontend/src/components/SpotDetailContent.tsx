import { HelpCircle, OctagonX, X } from 'lucide-react';
import type {
  AvailabilityWindow,
  PlannerDayInfo,
  SpotWindowViewModel,
} from '../types';
import {
  formatDuration,
  formatRangeSpaced,
  formatSignedHeight,
  formatTime,
} from '../lib/time';
import { SourceStatusBadge } from './SourceStatusBadge';
import { StatusBadge } from './StatusBadge';

interface SpotDetailContentProps {
  spot: SpotWindowViewModel;
  totalRanked: number;
  day: PlannerDayInfo;
  availability: AvailabilityWindow;
  exampleBannerText: string;
  onClose: () => void;
}

export function SpotDetailContent({
  spot,
  totalRanked,
  day,
  availability,
  exampleBannerText,
  onClose,
}: SpotDetailContentProps) {
  const arriveByDisplay =
    spot.closureStatus === 'closed'
      ? '—'
      : formatTime(spot.clippedStartMinutes);

  const closureCardValue =
    spot.closureStatus === 'open'
      ? 'Open'
      : spot.closureStatus === 'unverified'
        ? 'Unknown'
        : 'Closed';

  const closureCardColor =
    spot.closureStatus === 'open'
      ? 'text-teal-700'
      : spot.closureStatus === 'unverified'
        ? 'text-amber-700'
        : 'text-red-600';

  return (
    <div className="flex flex-col">
      {/* Header row */}
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold tracking-[0.08em] text-navy-500 uppercase">
          Selected window · Clamming
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close spot details"
          data-testid="close-detail-button"
          className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-sand-100 text-navy-700 transition hover:bg-sand-200 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      {/* Spot identity */}
      <h3 className="mt-3 font-display text-2xl leading-tight font-semibold text-navy-900">
        {spot.spotName}
      </h3>
      <div className="mt-0.5 text-[13px] text-navy-500">{spot.area}</div>

      {/* Prominent window time */}
      <div className="font-tabular mt-4 text-[28px] leading-none font-semibold tracking-tight text-navy-900 sm:text-[30px]">
        {formatRangeSpaced(spot.clippedStartMinutes, spot.clippedEndMinutes)}
      </div>
      <div className="font-tabular mt-1.5 text-xs text-navy-500">
        {formatDuration(spot.durationMinutes)} window · {day.shortLabel}
      </div>

      {/* Rank pill + Closure status pill side by side */}
      <div className="mt-3.5 flex flex-wrap items-center gap-2">
        {spot.closureStatus === 'closed' ? (
          <span className="inline-flex items-center rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-semibold text-red-800">
            Not recommended
          </span>
        ) : spot.isTopPick ? (
          <span className="inline-flex items-center rounded-full bg-teal-600 px-2.5 py-0.5 text-xs font-semibold text-white">
            Recommended · #{spot.rank} of {totalRanked}
          </span>
        ) : spot.closureStatus === 'unverified' ? (
          <span className="inline-flex items-center rounded-full bg-navy-100 px-2.5 py-0.5 text-xs font-semibold text-navy-700">
            Ranked #{spot.rank} of {totalRanked} · hold off
          </span>
        ) : (
          <span className="inline-flex items-center rounded-full bg-teal-50 px-2.5 py-0.5 text-xs font-semibold text-teal-800">
            Ranked #{spot.rank} of {totalRanked}
          </span>
        )}

        <StatusBadge status={spot.closureStatus} label={spot.closureLabel} />
      </div>

      {/* Plain-English explanation */}
      <p className="mt-3.5 text-[14px] leading-relaxed text-navy-900">
        {spot.reasonSummary}
      </p>

      {/* Distinct alert banner for Unverified or Closed */}
      {spot.closureStatus === 'unverified' && spot.closureAlertTitle && (
        <div
          role="status"
          data-testid="unverified-closure-alert"
          className="mt-4 rounded-[12px] border-[1.5px] border-dashed border-amber-500 bg-amber-50 p-3.5"
        >
          <div className="flex items-center gap-2 text-[13px] font-semibold text-amber-900">
            <HelpCircle className="h-4 w-4 shrink-0 text-amber-700" aria-hidden="true" />
            <span>{spot.closureAlertTitle}</span>
          </div>
          <p className="mt-1.5 text-xs leading-relaxed text-amber-900/90">
            {spot.closureAlertMessage}
          </p>
        </div>
      )}

      {spot.closureStatus === 'closed' && spot.closureAlertTitle && (
        <div
          role="alert"
          data-testid="closed-closure-alert"
          className="mt-4 rounded-[12px] bg-red-600 p-3.5 text-white"
        >
          <div className="flex items-center gap-2 text-[13px] font-semibold">
            <OctagonX className="h-4 w-4 shrink-0 text-white" aria-hidden="true" />
            <span>{spot.closureAlertTitle}</span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-red-50">
            {spot.closureAlertMessage}
          </p>
        </div>
      )}

      {/* 2x2 Metric Grid */}
      <div className="mt-4 grid grid-cols-2 gap-2.5">
        <div className="rounded-[12px] border border-sand-200 bg-sand-50/75 p-3">
          <div className="text-[10px] font-semibold tracking-wider text-navy-500 uppercase">
            Low tide
          </div>
          <div className="font-tabular mt-1 text-lg font-semibold text-navy-900">
            {spot.lowTideTime}
          </div>
          <div className="font-tabular mt-0.5 text-[11px] text-navy-500">
            {formatSignedHeight(spot.lowTideHeightFt)} ({spot.lowTideDatum})
          </div>
        </div>

        <div className="rounded-[12px] border border-sand-200 bg-sand-50/75 p-3">
          <div className="text-[10px] font-semibold tracking-wider text-navy-500 uppercase">
            Daylight overlap
          </div>
          <div className="font-tabular mt-1 text-lg font-semibold text-navy-900">
            {formatDuration(spot.durationMinutes)}
          </div>
          <div className="mt-0.5 text-[11px] text-navy-500">
            All in daylight · sunset {spot.sunsetTime}
          </div>
        </div>

        <div className="rounded-[12px] border border-sand-200 bg-sand-50/75 p-3">
          <div className="text-[10px] font-semibold tracking-wider text-navy-500 uppercase">
            Shellfish closure
          </div>
          <div
            className={`mt-1 font-display text-lg font-semibold ${closureCardColor}`}
          >
            {closureCardValue}
          </div>
          <div className="mt-0.5 text-[11px] text-navy-500">
            {spot.closureDetail}
          </div>
        </div>

        <div className="rounded-[12px] border border-sand-200 bg-sand-50/75 p-3">
          <div className="text-[10px] font-semibold tracking-wider text-navy-500 uppercase">
            Arrive by
          </div>
          <div className="font-tabular mt-1 text-lg font-semibold text-navy-900">
            {arriveByDisplay}
          </div>
          <div className="mt-0.5 text-[11px] text-navy-500">
            Inside your {availability.shortLabel}
          </div>
        </div>
      </div>

      {/* Sources & Last update */}
      <div className="mt-5 border-t border-sand-200 pt-4">
        <div className="text-[10px] font-semibold tracking-wider text-navy-500 uppercase">
          Sources &amp; last update
        </div>
        <ul className="mt-2 space-y-1.5 text-xs leading-relaxed">
          {spot.sources.map((src) => (
            <li
              key={src.label}
              className={src.isWarning ? 'font-medium text-amber-700' : 'text-navy-700'}
            >
              <span className="font-semibold">{src.label}</span> · {src.detail}
              {src.badge && src.badgeLabel && src.badge !== 'ok' && (
                <span className="ml-2 inline-block align-middle">
                  <SourceStatusBadge badge={src.badge} label={src.badgeLabel} />
                </span>
              )}
            </li>
          ))}
        </ul>
        {spot.sourceIssues.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {spot.sourceIssues
              .filter((issue, index, all) =>
                all.findIndex((item) => item.badgeLabel === issue.badgeLabel) === index,
              )
              .map((issue) => (
                <SourceStatusBadge
                  key={issue.badgeLabel}
                  badge={issue.badge}
                  label={issue.badgeLabel}
                />
              ))}
          </div>
        )}
        {exampleBannerText ? (
          <div className="mt-3 text-[11px] italic text-navy-500">
            {exampleBannerText}
          </div>
        ) : null}
      </div>
    </div>
  );
}
