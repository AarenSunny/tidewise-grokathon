import type { AdapterHealth } from '../types';
import {
  buildSourceBadges,
  isHiddenOptionalSource,
  OPTIONAL_HIDDEN_NOTE,
} from '../lib/sourceHealth';
import { formatIsoToPacificTimeWithZone } from '../lib/time';
import { SourceStatusBadge } from './SourceStatusBadge';

interface LiveSourcesPanelProps {
  health: AdapterHealth[];
  sourcesAreLive: boolean;
  freshnessAsOf: Date;
}

export function LiveSourcesPanel({
  health,
  sourcesAreLive,
  freshnessAsOf,
}: LiveSourcesPanelProps) {
  const badges = buildSourceBadges(health, freshnessAsOf);
  const optionalHidden = health.some((adapter) =>
    isHiddenOptionalSource(adapter, freshnessAsOf),
  );
  const title = sourcesAreLive ? 'Live data sources' : 'Data sources (example data)';

  return (
    <section
      data-testid="live-sources-panel"
      aria-label={title}
      className="rounded-[16px] border border-sand-200 bg-white p-5 shadow-[var(--shadow-card)]"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-[15px] font-semibold text-navy-900">{title}</h3>
        {!sourcesAreLive && (
          <span className="text-[11px] font-medium tracking-wide text-navy-500 uppercase">
            Example data
          </span>
        )}
      </div>

      {badges.length === 0 ? (
        <p className="mt-3 text-[13px] text-navy-500">No source health reported.</p>
      ) : (
        <ul className="mt-3 divide-y divide-sand-100">
          {badges.map((source) => (
            <li
              key={source.sourceName}
              data-testid={`source-row-${source.sourceName}`}
              className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 py-2 first:pt-0 last:pb-0"
            >
              <div className="min-w-0 text-[13px] font-medium text-navy-900">
                {source.displayName}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <SourceStatusBadge
                  badge={source.badge}
                  label={source.badgeLabel}
                />
                <span className="font-tabular text-[11px] text-navy-500">
                  {formatIsoToPacificTimeWithZone(source.lastSuccessAt)}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
      {optionalHidden && (
        <p className="mt-3 text-[12px] text-navy-500">{OPTIONAL_HIDDEN_NOTE}</p>
      )}
    </section>
  );
}
