import type {
  ActivityOption,
  AvailabilityId,
  AvailabilityWindow,
  PlannerDayInfo,
  RecommendResponse,
  Spot,
  SpotDisplayMeta,
} from '../types';

export const EXAMPLE_DATA_BANNER_TEXT =
  'Example data — illustrative sample, not live conditions';

export const EXAMPLE_ACTIVITIES: ActivityOption[] = [
  { id: 'clamming', label: 'Clamming', enabled: true },
  { id: 'crabbing', label: 'Crabbing', enabled: false, comingSoonLabel: 'Soon' },
  { id: 'swimming', label: 'Swimming', enabled: false, comingSoonLabel: 'Soon' },
  { id: 'sailing', label: 'Sailing', enabled: false, comingSoonLabel: 'Soon' },
];

export const EXAMPLE_DAY: PlannerDayInfo = {
  dateIso: '2026-11-21',
  label: 'Saturday, Nov 21',
  shortLabel: 'Sat, Nov 21',
  regionLabel: 'Half Moon Bay · Pacifica · SF Bay',
  axisStartMinutes: 11 * 60, // 11:00 AM
  axisEndMinutes: 19 * 60, // 7:00 PM
  sunsetTime: '4:52 PM',
  sunsetMinutes: 16 * 60 + 52, // 4:52 PM
};

export const EXAMPLE_AVAILABILITY_OPTIONS: AvailabilityWindow[] = [
  {
    id: 'afternoon',
    label: 'Afternoon (12–6 PM)',
    shortLabel: '12–6 PM',
    axisCaption: "You're free · 12:00 – 6:00 PM",
    overlineSuffix: 'SATURDAY AFTERNOON',
    startMinutes: 12 * 60,
    endMinutes: 18 * 60,
  },
  {
    id: 'after3pm',
    label: 'After 3 PM (3–6 PM)',
    shortLabel: 'After 3 PM',
    axisCaption: "You're free · 3:00 – 6:00 PM",
    overlineSuffix: 'SATURDAY AFTER 3 PM',
    startMinutes: 15 * 60,
    endMinutes: 18 * 60,
  },
  {
    id: 'midday',
    label: 'Early (11 AM–3 PM)',
    shortLabel: '11 AM–3 PM',
    axisCaption: "You're free · 11:00 AM – 3:00 PM",
    overlineSuffix: 'SATURDAY MIDDAY',
    startMinutes: 11 * 60,
    endMinutes: 15 * 60,
  },
];

export const DEFAULT_AVAILABILITY_ID: AvailabilityId = 'afternoon';

/**
 * Spot catalog aligned with backend/config/region.yaml spot IDs
 * (`half_moon_bay`, `pacifica`, `sf_bay`) plus a closed Half Moon Bay jetty spot.
 */
export const EXAMPLE_SPOTS: Spot[] = [
  {
    id: 'half_moon_bay',
    name: 'Pillar Point Harbor',
    lat: 37.498,
    lon: -122.487,
    shoreline_orientation_deg: 270,
    activities: ['clamming', 'crabbing', 'swimming', 'sailing'],
    tide_station_id: '9414131',
    buoy_ids: ['46012'],
    nws_grid: 'MTR/81,96',
    notes: 'Half Moon Bay — outer harbor mudflats',
  },
  {
    id: 'sf_bay',
    name: 'Crown Beach',
    lat: 37.762,
    lon: -122.277,
    shoreline_orientation_deg: 180,
    activities: ['clamming', 'sailing', 'crabbing', 'swimming'],
    tide_station_id: '9414750',
    buoy_ids: [],
    nws_grid: 'MTR/89,105',
    notes: 'Alameda · SF Bay — wide sandy flat',
  },
  {
    id: 'pacifica',
    name: 'Rockaway Beach',
    lat: 37.609,
    lon: -122.498,
    shoreline_orientation_deg: 270,
    activities: ['clamming', 'swimming'],
    tide_station_id: '9414290',
    buoy_ids: ['46026'],
    nws_grid: 'MTR/82,100',
    notes: 'Pacifica — exposed ocean cove',
  },
  {
    id: 'princeton_jetty',
    name: 'Princeton Jetty',
    lat: 37.495,
    lon: -122.483,
    shoreline_orientation_deg: 265,
    activities: ['clamming'],
    tide_station_id: '9414131',
    buoy_ids: ['46012'],
    nws_grid: 'MTR/81,96',
    notes: 'Half Moon Bay — illustrative confirmed closure example',
  },
];

export const EXAMPLE_SPOT_META: Record<string, SpotDisplayMeta> = {
  half_moon_bay: {
    area: 'Half Moon Bay',
    mapPosition: { x: 46, y: 74 },
  },
  sf_bay: {
    area: 'Alameda · SF Bay',
    mapPosition: { x: 82, y: 40 },
  },
  pacifica: {
    area: 'Pacifica',
    mapPosition: { x: 52, y: 46 },
  },
  princeton_jetty: {
    area: 'Half Moon Bay',
    mapPosition: { x: 42, y: 70 },
  },
};

/**
 * Sample payload mirroring the FastAPI `GET /recommend` contract (`RecommendResponse`).
 */
export const EXAMPLE_RECOMMEND_RESPONSE: RecommendResponse = {
  activity: 'clamming',
  spot_ids: ['half_moon_bay', 'sf_bay', 'pacifica', 'princeton_jetty'],
  start: '2026-11-21T12:00:00-08:00',
  end: '2026-11-21T18:00:00-08:00',
  recommendations: [
    {
      spot_id: 'half_moon_bay',
      spot_name: 'Pillar Point Harbor',
      best_score: 91,
      windows: [
        {
          spot_id: 'half_moon_bay',
          start: '2026-11-21T14:50:00-08:00',
          end: '2026-11-21T16:50:00-08:00',
          score: 91,
          eligible: true,
          confidence: {
            value: 0.94,
            notes: ['NOAA tide & CDPH closure data fresh'],
          },
          gates: [
            {
              name: 'no_biotoxin_closure',
              passed: true,
              cannot_confirm: false,
              reason: 'No active shellfish quarantine reported for Half Moon Bay.',
              evidence: 'CDPH shellfish advisory (sample)',
            },
            {
              name: 'daylight_window',
              passed: true,
              cannot_confirm: false,
              reason: 'Entire clamming window finishes before 4:52 PM sunset.',
              evidence: 'Sunset 4:52 PM',
            },
          ],
          factors: [
            {
              name: 'low_tide_height_ft',
              value: -0.6,
              weight: 0.55,
              contribution: 51,
              note: '−0.6 ft MLLW at 3:48 PM',
            },
            {
              name: 'low_tide_time_min',
              value: 15 * 60 + 48, // 3:48 PM
              weight: 0.0,
              contribution: 0,
              note: 'Peak low tide at 3:48 PM',
            },
            {
              name: 'daylight_overlap_min',
              value: 120,
              weight: 0.25,
              contribution: 22,
              note: '2h 00m in full daylight',
            },
          ],
          summary:
            'Lowest tide of the day (−0.6 ft at 3:48 PM) with verified open shellfish status.',
        },
      ],
    },
    {
      spot_id: 'sf_bay',
      spot_name: 'Crown Beach',
      best_score: 82,
      windows: [
        {
          spot_id: 'sf_bay',
          start: '2026-11-21T13:20:00-08:00',
          end: '2026-11-21T16:50:00-08:00',
          score: 82,
          eligible: true,
          confidence: {
            value: 0.92,
            notes: ['NOAA tide & CDPH closure data fresh'],
          },
          gates: [
            {
              name: 'no_biotoxin_closure',
              passed: true,
              cannot_confirm: false,
              reason: 'No active shellfish quarantine reported for Alameda shoreline.',
              evidence: 'CDPH shellfish advisory (sample)',
            },
            {
              name: 'daylight_window',
              passed: true,
              cannot_confirm: false,
              reason: 'Entire clamming window finishes before 4:52 PM sunset.',
              evidence: 'Sunset 4:52 PM',
            },
          ],
          factors: [
            {
              name: 'low_tide_height_ft',
              value: 0.4,
              weight: 0.55,
              contribution: 38,
              note: '+0.4 ft MLLW at 2:35 PM',
            },
            {
              name: 'low_tide_time_min',
              value: 14 * 60 + 35, // 2:35 PM
              weight: 0.0,
              contribution: 0,
              note: 'Peak low tide at 2:35 PM',
            },
            {
              name: 'daylight_overlap_min',
              value: 210,
              weight: 0.25,
              contribution: 25,
              note: '3h 30m in full daylight',
            },
          ],
          summary:
            'Longer 3h 30m window, though tide only drops to +0.4 ft.',
        },
      ],
    },
    {
      spot_id: 'pacifica',
      spot_name: 'Rockaway Beach',
      best_score: 0,
      windows: [
        {
          spot_id: 'pacifica',
          start: '2026-11-21T15:00:00-08:00',
          end: '2026-11-21T16:30:00-08:00',
          score: 74,
          eligible: false,
          confidence: {
            value: 0.42,
            notes: ['CDPH shellfish closure feed unreachable since 6:10 AM'],
          },
          gates: [
            {
              name: 'no_biotoxin_closure',
              passed: false,
              cannot_confirm: true,
              reason:
                "We couldn't reach the state shellfish closure feed since 6:10 AM, so we can't confirm this beach is open. Check the official advisory before you dig.",
              evidence: 'CDPH shellfish advisory feed unreachable',
            },
            {
              name: 'daylight_window',
              passed: true,
              cannot_confirm: false,
              reason: 'Finishes before 4:52 PM sunset.',
              evidence: 'Sunset 4:52 PM',
            },
          ],
          factors: [
            {
              name: 'low_tide_height_ft',
              value: -0.5,
              weight: 0.55,
              contribution: 47,
              note: '−0.5 ft MLLW at 3:41 PM',
            },
            {
              name: 'low_tide_time_min',
              value: 15 * 60 + 41, // 3:41 PM
              weight: 0.0,
              contribution: 0,
              note: 'Peak low tide at 3:41 PM',
            },
            {
              name: 'daylight_overlap_min',
              value: 90,
              weight: 0.25,
              contribution: 18,
              note: '1h 30m in full daylight',
            },
          ],
          summary:
            'Good −0.5 ft tide at 3:41 PM, but shellfish closure status cannot be verified.',
        },
      ],
    },
    {
      spot_id: 'princeton_jetty',
      spot_name: 'Princeton Jetty',
      best_score: 0,
      windows: [
        {
          spot_id: 'princeton_jetty',
          start: '2026-11-21T14:45:00-08:00',
          end: '2026-11-21T16:45:00-08:00',
          score: 0,
          eligible: false,
          confidence: {
            value: 0.95,
            notes: ['Confirmed CDPH shellfish quarantine active'],
          },
          gates: [
            {
              name: 'no_biotoxin_closure',
              passed: false,
              cannot_confirm: false,
              reason:
                'A confirmed state quarantine is in effect for this beach. Do not harvest clams here today.',
              evidence: 'CDPH shellfish advisory (sample)',
            },
            {
              name: 'daylight_window',
              passed: true,
              cannot_confirm: false,
              reason: 'Inside daylight hours.',
              evidence: 'Sunset 4:52 PM',
            },
          ],
          factors: [
            {
              name: 'low_tide_height_ft',
              value: -0.5,
              weight: 0.55,
              contribution: 0,
              note: '−0.5 ft MLLW at 3:46 PM',
            },
            {
              name: 'low_tide_time_min',
              value: 15 * 60 + 46, // 3:46 PM
              weight: 0.0,
              contribution: 0,
              note: 'Peak low tide at 3:46 PM',
            },
          ],
          summary: 'Confirmed shellfish quarantine — excluded from ranking.',
        },
      ],
    },
  ],
  health: [
    {
      source_name: 'noaa_tides',
      status: 'ok',
      last_success_at: '2026-11-21T14:05:00-08:00',
      last_error_at: null,
      last_error: null,
      last_latency_ms: 142,
      consecutive_failures: 0,
      forced_down: false,
    },
    {
      source_name: 'cdph_shellfish',
      status: 'degraded',
      last_success_at: '2026-11-21T06:10:00-08:00',
      last_error_at: '2026-11-21T13:40:00-08:00',
      last_error: 'Timeout reaching Rockaway Beach advisory feed',
      last_latency_ms: 5002,
      consecutive_failures: 4,
      forced_down: false,
    },
    {
      source_name: 'daylight_table',
      status: 'ok',
      last_success_at: '2026-11-21T06:00:00-08:00',
      last_error_at: null,
      last_error: null,
      last_latency_ms: 8,
      consecutive_failures: 0,
      forced_down: false,
    },
  ],
};
