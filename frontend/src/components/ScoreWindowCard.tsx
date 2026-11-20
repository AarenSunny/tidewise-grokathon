import { useEffect, useState } from 'react';
import { fetchScore } from '../lib/api';
import type { Activity, ScoreWindowResponse } from '../types';

const ACTIVITIES: Activity[] = ['crabbing', 'clamming', 'swimming', 'sailing'];

function formatWhen(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString('en-US', {
    timeZone: 'America/Los_Angeles',
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function ScoreWindowCard() {
  const [activity, setActivity] = useState<Activity>('swimming');
  const [location, setLocation] = useState('Half Moon Bay');
  const [submitted, setSubmitted] = useState({
    activity: 'swimming' as Activity,
    location: 'Half Moon Bay',
  });
  const [windowRec, setWindowRec] = useState<ScoreWindowResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetchScore({
      activity: submitted.activity,
      location: submitted.location,
      signal: controller.signal,
    })
      .then((body) => {
        setWindowRec(body);
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setWindowRec(null);
        setError(err instanceof Error ? err.message : 'Could not load a window');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [submitted]);

  return (
    <section className="mt-5 rounded-[16px] border border-sand-200 bg-white px-5 py-4 shadow-xs">
      <div className="text-[11px] font-semibold tracking-[0.08em] text-teal-700 uppercase">
        Unscreened timing estimate — safety gates not applied
      </div>
      <h2 className="mt-1 font-display text-lg font-semibold text-navy-900">
        Timing window
      </h2>
      <p className="mt-1 text-sm leading-relaxed text-navy-700">
        Use the Planner for safety-gated recommendations.
      </p>
      <form
        className="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          setSubmitted({ activity, location: location.trim() || 'Half Moon Bay' });
        }}
      >
        <label className="text-[11px] font-semibold tracking-wider text-navy-500 uppercase">
          Activity
          <select
            value={activity}
            onChange={(event) => setActivity(event.target.value as Activity)}
            className="mt-1 block rounded-[8px] border border-sand-200 bg-white px-2.5 py-1.5 text-sm font-medium text-navy-900 normal-case"
          >
            {ACTIVITIES.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-[11px] font-semibold tracking-wider text-navy-500 uppercase">
          Location
          <input
            value={location}
            onChange={(event) => setLocation(event.target.value)}
            className="mt-1 block rounded-[8px] border border-sand-200 px-2.5 py-1.5 text-sm font-medium text-navy-900 normal-case"
          />
        </label>
        <button
          type="submit"
          className="rounded-[8px] bg-teal-600 px-3 py-1.5 text-sm font-medium text-white"
        >
          Score
        </button>
      </form>

      {loading && (
        <p className="mt-3 text-sm text-navy-500">Checking live tides and daylight…</p>
      )}
      {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      {windowRec && (
        <dl className="mt-3 grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-[10px] font-semibold tracking-wider text-navy-500 uppercase">
              Activity
            </dt>
            <dd className="text-sm font-semibold text-navy-900">{windowRec.activity}</dd>
          </div>
          <div>
            <dt className="text-[10px] font-semibold tracking-wider text-navy-500 uppercase">
              Location
            </dt>
            <dd className="text-sm font-semibold text-navy-900">{windowRec.location}</dd>
          </div>
          <div>
            <dt className="text-[10px] font-semibold tracking-wider text-navy-500 uppercase">
              Time window
            </dt>
            <dd className="text-sm font-semibold text-navy-900">
              {formatWhen(windowRec.start)} – {formatWhen(windowRec.end)} PT
            </dd>
          </div>
          <div>
            <dt className="text-[10px] font-semibold tracking-wider text-navy-500 uppercase">
              Score
            </dt>
            <dd className="text-sm font-semibold text-navy-900">
              {Math.round(windowRec.score)} / 100
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-[10px] font-semibold tracking-wider text-navy-500 uppercase">
              Reason
            </dt>
            <dd className="text-sm leading-relaxed text-navy-700">{windowRec.reason}</dd>
          </div>
        </dl>
      )}
    </section>
  );
}
