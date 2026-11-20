import { Info } from 'lucide-react';
import type { DataFreshnessSummary, SpotWindowViewModel } from '../types';
import { SchematicMap } from './SchematicMap';

interface GuidanceRailProps {
  freshness: DataFreshnessSummary;
  rankedSpots: SpotWindowViewModel[];
  selectedSpotId: string | null;
  onSelectSpot: (spot: SpotWindowViewModel) => void;
}

const RANKING_RULES = [
  'Lower low tide exposes more clam bed',
  'Window must be in daylight',
  'Window must fit your free hours',
  'Closure status must be verified as open',
];

export function GuidanceRail({
  freshness,
  rankedSpots,
  selectedSpotId,
  onSelectSpot,
}: GuidanceRailProps) {
  return (
    <aside className="space-y-4">
      {/* Selection guidance banner */}
      <div className="flex items-start gap-2.5 rounded-[14px] border border-teal-100 bg-teal-50/90 px-4 py-3 text-[13px] leading-snug text-teal-800">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-teal-600" aria-hidden="true" />
        <span>
          Select any window on the chart to see its details, closure status and
          sources.
        </span>
      </div>

      {/* How we rank clamming windows */}
      <div className="rounded-[16px] border border-sand-200 bg-white p-5 shadow-[var(--shadow-card)]">
        <h3 className="text-[15px] font-semibold text-navy-900">
          How we rank clamming windows
        </h3>
        <ol className="mt-3.5 space-y-2.5">
          {RANKING_RULES.map((rule, index) => (
            <li
              key={rule}
              className="flex items-center gap-2.5 text-[13px] text-navy-700"
            >
              <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sand-100 text-[11px] font-semibold text-navy-700">
                {index + 1}
              </span>
              <span>{rule}</span>
            </li>
          ))}
        </ol>

        <div className="mt-4 border-t border-sand-200/80 pt-3 text-[11px] leading-relaxed text-navy-500">
          Data freshness (sample): tides updated {freshness.tidesUpdatedAt} ·
          closures checked {freshness.closuresCheckedAt}
          {freshness.warningNote ? ` · ${freshness.warningNote}` : ''}
        </div>
      </div>

      {/* Orientation map (secondary) */}
      <SchematicMap
        spots={rankedSpots}
        selectedSpotId={selectedSpotId}
        onSelectSpot={onSelectSpot}
      />
    </aside>
  );
}
