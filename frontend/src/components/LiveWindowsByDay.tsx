import { useMemo, useState } from 'react';
import type { RecommendResponse, Spot } from '../types';
import {
  groupWindowsByDay,
  type GateView,
  type LiveWindowRow,
} from '../lib/crabbing';

interface LiveWindowsByDayProps {
  response: RecommendResponse;
  spots: Spot[];
  activityLabel?: string;
}

function GateBadge({ gate }: { gate: GateView }) {
  const cls =
    gate.state === 'pass'
      ? 'border-teal-600/40 bg-teal-50 text-teal-800'
      : gate.state === 'cant-confirm'
        ? 'border-sky-200 bg-sky-50 text-sky-900'
        : 'border-red-600/40 bg-red-50 text-red-800';
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${cls}`}
    >
      {gate.label}
    </span>
  );
}

function WindowDetail({ row, onClose }: { row: LiveWindowRow; onClose: () => void }) {
  return (
    <aside
      data-testid="live-window-detail"
      aria-label={`${row.spotName} window details`}
      className="rounded-[16px] border border-sand-200 bg-white p-5 shadow-[var(--shadow-card)]"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-[11px] font-semibold tracking-[0.08em] text-navy-500 uppercase">
            Selected window
          </div>
          <h3 className="mt-1 font-display text-xl font-semibold text-navy-900">
            {row.spotName}
          </h3>
          <div className="font-tabular mt-1 text-sm text-navy-700">
            {row.dateLabel} · {row.rangeLabel}
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close window details"
          className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-sand-100 text-navy-700 hover:bg-sand-200"
        >
          ×
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-3 text-sm">
        <div>
          <span className="text-[11px] font-semibold tracking-wider text-navy-500 uppercase">
            Score
          </span>
          <div className="font-tabular font-semibold text-navy-900">
            {Math.round(row.score)}
          </div>
        </div>
        <div>
          <span className="text-[11px] font-semibold tracking-wider text-navy-500 uppercase">
            Confidence
          </span>
          <div className="font-tabular font-semibold text-navy-900">
            {row.confidence.toFixed(2)}
          </div>
        </div>
      </div>

      {row.hasCantConfirm && (
        <div
          role="status"
          data-testid="cant-confirm-alert"
          className="mt-4 rounded-[12px] border-[1.5px] border-sky-200 bg-sky-50 p-3.5"
        >
          <div className="text-[13px] font-semibold text-sky-900">
            Check before you go
          </div>
          <p className="mt-1 text-xs leading-relaxed text-sky-900/80">
            Some live safety feeds are temporarily unavailable, so check the
            official advisory before heading out.
          </p>
        </div>
      )}

      {row.summary && (
        <p className="mt-3 text-[13px] leading-relaxed text-navy-800">{row.summary}</p>
      )}

      <div className="mt-4 border-t border-sand-200 pt-3">
        <div className="text-[11px] font-semibold tracking-wider text-navy-500 uppercase">
          Gates
        </div>
        <ul className="mt-2 space-y-2.5">
          {row.gates.map((gate) => (
            <li key={gate.name} data-testid={`gate-${gate.name}`}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[13px] font-semibold text-navy-900">
                  {gate.name}
                </span>
                <GateBadge gate={gate} />
              </div>
              <p className="mt-0.5 text-xs leading-relaxed text-navy-700">
                {gate.reason}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

export function LiveWindowsByDay({
  response,
  spots,
  activityLabel = 'Crabbing',
}: LiveWindowsByDayProps) {
  const groups = useMemo(
    () => groupWindowsByDay(response, spots),
    [response, spots],
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = groups
    .flatMap((group) => group.windows)
    .find((row) => row.id === selectedId) ?? null;

  if (groups.length === 0) {
    return (
      <div className="rounded-[16px] border border-sand-200 bg-white px-5 py-8 text-sm text-navy-700 shadow-[var(--shadow-card)]">
        No {activityLabel.toLowerCase()} windows in this range.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:items-start">
      <div className="space-y-4 lg:col-span-8">
        {groups.map((group) => (
          <section
            key={group.dateKey}
            className="rounded-[16px] border border-sand-200 bg-white p-4 shadow-[var(--shadow-card)] sm:p-5"
          >
            <h3 className="text-[15px] font-semibold text-navy-900">
              {group.dateLabel}
            </h3>
            <ul className="mt-3 divide-y divide-sand-100">
              {group.windows.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    data-testid={`live-window-${row.spotId}`}
                    onClick={() => setSelectedId(row.id)}
                    className={`flex w-full flex-col gap-1 px-1 py-3 text-left transition hover:bg-sand-50 focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:outline-none sm:flex-row sm:items-center sm:justify-between ${
                      selectedId === row.id ? 'bg-sand-50' : ''
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="text-[14px] font-semibold text-navy-900">
                        {row.spotName}
                      </div>
                      <div className="font-tabular text-sm text-navy-800">
                        {row.rangeLabel}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {row.hasCantConfirm && (
                        <span className="inline-flex items-center rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-900">
                          Check before you go
                        </span>
                      )}
                      <span className="font-tabular text-xs text-navy-500">
                        Score {Math.round(row.score)}
                      </span>
                      <span className="font-tabular text-xs text-navy-500">
                        Conf {row.confidence.toFixed(2)}
                      </span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
      <div className="lg:col-span-4">
        {selected ? (
          <WindowDetail row={selected} onClose={() => setSelectedId(null)} />
        ) : (
          <div className="rounded-[14px] border border-teal-100 bg-teal-50/90 px-4 py-3 text-[13px] leading-snug text-teal-800">
            Select a window to see every gate, including pass, fail, and
            can&apos;t-confirm states.
          </div>
        )}
      </div>
    </div>
  );
}
