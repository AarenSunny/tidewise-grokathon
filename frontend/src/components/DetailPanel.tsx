import { useEffect } from 'react';
import type {
  AvailabilityWindow,
  PlannerDayInfo,
  SpotWindowViewModel,
} from '../types';
import { SpotDetailContent } from './SpotDetailContent';

interface DetailPanelProps {
  spot: SpotWindowViewModel | null;
  totalRanked: number;
  day: PlannerDayInfo;
  availability: AvailabilityWindow;
  exampleBannerText: string;
  onClose: () => void;
}

export function DetailPanel({
  spot,
  totalRanked,
  day,
  availability,
  exampleBannerText,
  onClose,
}: DetailPanelProps) {
  useEffect(() => {
    if (!spot) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [spot, onClose]);

  if (!spot) return null;

  return (
    <>
      {/* Desktop side panel */}
      <aside
        data-testid="desktop-detail-panel"
        aria-label={`${spot.spotName} window details`}
        className="hidden rounded-[16px] border border-sand-200 bg-white p-5 shadow-[var(--shadow-card)] lg:block"
      >
        <SpotDetailContent
          spot={spot}
          totalRanked={totalRanked}
          day={day}
          availability={availability}
          exampleBannerText={exampleBannerText}
          onClose={onClose}
        />
      </aside>

      {/* Mobile bottom sheet (< lg) */}
      <div
        className="fixed inset-0 z-50 flex items-end justify-center bg-navy-900/45 backdrop-blur-[1px] lg:hidden"
        role="dialog"
        aria-modal="true"
        aria-label={`${spot.spotName} window details`}
        data-testid="mobile-detail-sheet"
        onClick={(e) => {
          if (e.target === e.currentTarget) {
            onClose();
          }
        }}
      >
        <div className="max-h-[88vh] w-full max-w-lg overflow-y-auto rounded-t-[24px] border-t border-sand-200 bg-white px-5 pt-3 pb-7 shadow-[var(--shadow-sheet)]">
          {/* Drag handle */}
          <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-sand-300" />
          <SpotDetailContent
            spot={spot}
            totalRanked={totalRanked}
            day={day}
            availability={availability}
            exampleBannerText={exampleBannerText}
            onClose={onClose}
          />
        </div>
      </div>
    </>
  );
}
