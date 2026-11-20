import type { SpotWindowViewModel } from '../types';

interface SchematicMapProps {
  spots: SpotWindowViewModel[];
  selectedSpotId: string | null;
  onSelectSpot: (spot: SpotWindowViewModel) => void;
}

export function SchematicMap({
  spots,
  selectedSpotId,
  onSelectSpot,
}: SchematicMapProps) {
  return (
    <div className="rounded-[16px] border border-sand-200 bg-white p-4 shadow-[var(--shadow-card)]">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-navy-900">Where they are</h3>
        <span className="text-[11px] font-medium text-navy-500">
          Orientation only
        </span>
      </div>

      <div className="relative mt-3 h-40 w-full overflow-hidden rounded-[12px] border border-sand-200 bg-teal-50/75">
        {/* Stylized schematic coastline & SF Bay */}
        <svg
          viewBox="0 0 300 160"
          className="h-full w-full"
          role="img"
          aria-label="Schematic orientation map of Half Moon Bay, Pacifica, and SF Bay"
        >
          {/* Ocean */}
          <rect x="0" y="0" width="300" height="160" fill="#E3F0EF" />
          {/* Peninsula + East Bay landmass */}
          <path
            d="M 155 0 L 185 0 L 195 28 L 210 35 L 222 10 L 300 0 L 300 160 L 135 160 L 132 132 L 128 112 L 138 90 L 146 66 L 152 38 Z"
            fill="#EDE3D1"
            stroke="#D6C9AE"
            strokeWidth="1.5"
          />
          {/* San Francisco Bay inlet */}
          <path
            d="M 192 22 C 202 35, 222 45, 245 55 C 258 64, 258 95, 238 118 C 218 134, 200 120, 198 92 C 194 64, 186 42, 192 22 Z"
            fill="#DCECEA"
            stroke="#C3DCD9"
            strokeWidth="1.2"
          />
          {/* Subtle coast labels */}
          <text
            x="32"
            y="34"
            fill="#5A6B80"
            fontSize="9"
            fontFamily="IBM Plex Sans, sans-serif"
            fontWeight="500"
          >
            Pacific Ocean
          </text>
          <text
            x="206"
            y="78"
            fill="#5A6B80"
            fontSize="8.5"
            fontFamily="IBM Plex Sans, sans-serif"
            fontWeight="500"
          >
            SF Bay
          </text>
        </svg>

        {/* Interactive spot pins */}
        {spots.map((spot) => {
          const isSelected = spot.spotId === selectedSpotId;
          const pinBg =
            spot.closureStatus === 'unverified'
              ? 'bg-amber-500 text-white'
              : spot.isTopPick
                ? 'bg-teal-600 text-white'
                : 'bg-teal-800 text-white';

          return (
            <button
              key={spot.spotId}
              type="button"
              onClick={() => onSelectSpot(spot)}
              title={`${spot.rank ? `#${spot.rank} ` : ''}${spot.spotName}`}
              style={{
                left: `${spot.mapPosition.x}%`,
                top: `${spot.mapPosition.y}%`,
              }}
              className={`absolute flex h-6 w-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full text-[11px] font-bold shadow-sm transition hover:scale-110 focus-visible:ring-2 focus-visible:ring-navy-900 focus-visible:outline-none ${pinBg} ${
                isSelected ? 'ring-2 ring-navy-900 ring-offset-2' : ''
              }`}
            >
              {spot.rank ?? '•'}
            </button>
          );
        })}

        <div className="pointer-events-none absolute bottom-2 left-2.5 rounded bg-sand-50/90 px-2 py-0.5 text-[10px] font-medium text-navy-500">
          Schematic — not to scale
        </div>
      </div>
    </div>
  );
}
