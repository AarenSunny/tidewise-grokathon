import { Info, MapPin, Waves } from 'lucide-react';

interface HeaderBarProps {
  regionLabel: string;
  isExampleData: boolean;
  exampleBannerText: string;
}

export function HeaderBar({
  regionLabel,
  isExampleData,
  exampleBannerText,
}: HeaderBarProps) {
  return (
    <header className="border-b border-sand-200 bg-sand-50/95">
      <div className="mx-auto flex max-w-[1360px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center gap-4 sm:gap-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-teal-600 text-white shadow-xs">
              <Waves className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <div className="font-display text-xl leading-tight font-semibold tracking-tight text-navy-900">
                TideWise
              </div>
              <div className="text-[11px] leading-tight font-medium text-navy-500">
                Coastal Planner
              </div>
            </div>
          </div>

          <div className="hidden items-center gap-2 rounded-xl border border-sand-200 bg-white px-3.5 py-1.5 md:flex">
            <MapPin className="h-4 w-4 shrink-0 text-teal-600" aria-hidden="true" />
            <div className="leading-tight">
              <div className="text-[10px] font-semibold tracking-wider text-navy-500 uppercase">
                Area
              </div>
              <div className="text-[13px] font-semibold text-navy-900">
                {regionLabel}
              </div>
            </div>
          </div>
        </div>

        {isExampleData && (
          <div
            className="inline-flex items-center gap-1.5 rounded-full border border-navy-100 bg-navy-100/70 px-3 py-1 text-xs font-medium text-navy-700"
            data-testid="example-data-badge"
          >
            <Info className="h-3.5 w-3.5 shrink-0 text-navy-500" aria-hidden="true" />
            <span>{exampleBannerText}</span>
          </div>
        )}
      </div>
    </header>
  );
}
