import { Compass, Fish, Sailboat, Shell, Waves } from 'lucide-react';
import type { Activity, ActivityOption } from '../types';

interface ActivitySelectorProps {
  activities: ActivityOption[];
  selectedActivity: Activity;
  onSelectActivity?: (id: Activity) => void;
}

function ActivityIcon({ id, active }: { id: Activity; active: boolean }) {
  const cls = `h-4 w-4 shrink-0 ${active ? 'text-teal-300' : 'text-navy-500'}`;
  switch (id) {
    case 'clamming':
      return <Shell className={cls} aria-hidden="true" />;
    case 'crabbing':
      return <Fish className={cls} aria-hidden="true" />;
    case 'swimming':
      return <Waves className={cls} aria-hidden="true" />;
    case 'sailing':
      return <Sailboat className={cls} aria-hidden="true" />;
    default:
      return <Compass className={cls} aria-hidden="true" />;
  }
}

export function ActivitySelector({
  activities,
  selectedActivity,
  onSelectActivity,
}: ActivitySelectorProps) {
  return (
    <div
      role="tablist"
      aria-label="Coastal activity"
      className="grid grid-cols-4 gap-1 rounded-[12px] border border-sand-200 bg-white p-1 sm:inline-flex sm:items-center sm:gap-1"
    >
      {activities.map((act) => {
        const isSelected = act.id === selectedActivity;
        return (
          <button
            key={act.id}
            type="button"
            role="tab"
            aria-selected={isSelected}
            disabled={!act.enabled}
            title={act.enabled ? act.label : `${act.label} — coming soon`}
            onClick={() => act.enabled && onSelectActivity?.(act.id)}
            className={`group relative flex flex-col items-center justify-center gap-1 rounded-[9px] px-2 py-2 text-xs font-medium transition sm:flex-row sm:gap-1.5 sm:px-3.5 sm:py-1.5 sm:text-[13px] ${
              isSelected
                ? 'bg-navy-900 text-white shadow-xs'
                : act.enabled
                  ? 'text-navy-700 hover:bg-sand-100'
                  : 'cursor-not-allowed text-navy-500/75 opacity-75'
            }`}
          >
            <ActivityIcon id={act.id} active={isSelected} />
            <span>{act.label}</span>
            {!act.enabled && act.comingSoonLabel && (
              <span className="hidden rounded bg-sand-100 px-1.5 py-0.5 text-[10px] leading-none font-medium text-navy-500 lg:inline">
                {act.comingSoonLabel}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
