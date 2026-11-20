import type { SpotSourceIssue } from '../types';
import { SourceStatusBadge } from './SourceStatusBadge';

interface SourceIssueBadgesProps {
  issues: SpotSourceIssue[];
  className?: string;
}

export function SourceIssueBadges({
  issues,
  className = 'mt-1.5 flex flex-wrap gap-1 pl-7',
}: SourceIssueBadgesProps) {
  if (issues.length === 0) return null;
  const seen = new Set<string>();
  const unique = issues.filter((issue) => {
    if (seen.has(issue.badgeLabel)) return false;
    seen.add(issue.badgeLabel);
    return true;
  });
  return (
    <span className={className}>
      {unique.map((issue) => (
        <SourceStatusBadge
          key={issue.badgeLabel}
          badge={issue.badge}
          label={issue.badgeLabel}
        />
      ))}
    </span>
  );
}
