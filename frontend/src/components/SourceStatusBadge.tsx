import type { SourceBadgeKind } from '../types';

interface SourceStatusBadgeProps {
  badge: SourceBadgeKind;
  label: string;
  size?: 'sm' | 'md';
}

const BADGE_CLASS: Record<SourceBadgeKind, string> = {
  ok: 'border-teal-600/40 bg-teal-50 text-teal-800',
  stale: 'border-amber-500/70 bg-amber-50 text-amber-900',
  degraded: 'border-amber-500/70 bg-amber-50 text-amber-900',
  unavailable: 'border-red-600/40 bg-red-50 text-red-800',
  unknown: 'border-navy-300 bg-navy-100 text-navy-700',
};

export function SourceStatusBadge({
  badge,
  label,
  size = 'sm',
}: SourceStatusBadgeProps) {
  const padding = size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs';
  return (
    <span
      data-testid={`source-badge-${badge}`}
      className={`inline-flex items-center rounded-full border font-medium ${BADGE_CLASS[badge]} ${padding}`}
    >
      {label}
    </span>
  );
}
