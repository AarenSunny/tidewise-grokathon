import { Calendar, Clock, MapPin } from 'lucide-react';
import type { AvailabilityId, AvailabilityWindow, PlannerDayInfo } from '../types';

interface PlannerControlsProps {
  day: PlannerDayInfo;
  availabilityOptions: AvailabilityWindow[];
  selectedAvailabilityId: AvailabilityId;
  onChangeAvailability: (id: AvailabilityId) => void;
}

export function PlannerControls({
  day,
  availabilityOptions,
  selectedAvailabilityId,
  onChangeAvailability,
}: PlannerControlsProps) {
  return (
    <div className="flex flex-col gap-2.5 lg:flex-row lg:flex-wrap lg:items-center">
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:flex lg:items-center">
        {/* Day pill */}
        <div className="flex items-center gap-2.5 rounded-[12px] border border-sand-200 bg-white px-3.5 py-2">
          <Calendar className="h-4 w-4 shrink-0 text-teal-600" aria-hidden="true" />
          <div className="leading-tight">
            <div className="text-[10px] font-semibold tracking-wider text-navy-500 uppercase">
              Day
            </div>
            <div className="text-[13px] font-semibold text-navy-900">
              {day.label}
            </div>
          </div>
        </div>

        {/* Mobile Area card */}
        <div className="flex items-center gap-2.5 rounded-[12px] border border-sand-200 bg-white px-3.5 py-2 md:hidden">
          <MapPin className="h-4 w-4 shrink-0 text-teal-600" aria-hidden="true" />
          <div className="min-w-0 leading-tight">
            <div className="text-[10px] font-semibold tracking-wider text-navy-500 uppercase">
              Area
            </div>
            <div className="truncate text-[13px] font-semibold text-navy-900">
              {day.regionLabel}
            </div>
          </div>
        </div>
      </div>

      {/* Availability switcher */}
      <div className="flex flex-col gap-1.5 rounded-[12px] border border-sand-200 bg-white px-3.5 py-2 sm:flex-row sm:items-center sm:gap-3">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 shrink-0 text-teal-600" aria-hidden="true" />
          <span className="text-[10px] font-semibold tracking-wider text-navy-500 uppercase">
            I&apos;m free
          </span>
        </div>
        <div
          role="radiogroup"
          aria-label="Available hours"
          className="flex flex-wrap items-center gap-1"
        >
          {availabilityOptions.map((option) => {
            const active = option.id === selectedAvailabilityId;
            return (
              <button
                key={option.id}
                type="button"
                role="radio"
                aria-checked={active}
                data-testid={`availability-${option.id}`}
                onClick={() => onChangeAvailability(option.id)}
                className={`rounded-[8px] px-2.5 py-1 text-xs font-medium transition ${
                  active
                    ? 'bg-teal-600 text-white shadow-xs'
                    : 'bg-sand-100 text-navy-700 hover:bg-sand-200/70'
                }`}
              >
                {option.shortLabel}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
