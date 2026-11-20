import { CheckCircle2, HelpCircle, OctagonX } from 'lucide-react';
import type { ClosureStatusView } from '../types';

interface StatusBadgeProps {
  status: ClosureStatusView;
  label: string;
  size?: 'sm' | 'md';
}

export function StatusBadge({ status, label, size = 'sm' }: StatusBadgeProps) {
  const padding = size === 'sm' ? 'px-2.5 py-0.5 text-xs' : 'px-3 py-1 text-xs';

  if (status === 'open') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-full border border-teal-600/40 bg-teal-50 font-medium text-teal-800 ${padding}`}
      >
        <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-teal-600" aria-hidden="true" />
        <span>{label}</span>
      </span>
    );
  }

  if (status === 'unverified') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-full border border-dashed border-amber-500 bg-amber-50 font-medium text-amber-900 ${padding}`}
      >
        <HelpCircle className="h-3.5 w-3.5 shrink-0 text-amber-700" aria-hidden="true" />
        <span>{label}</span>
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full bg-red-600 font-medium text-white ${padding}`}
    >
      <OctagonX className="h-3.5 w-3.5 shrink-0 text-white" aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}
