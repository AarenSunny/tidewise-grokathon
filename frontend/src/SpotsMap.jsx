import { useEffect, useMemo, useState } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  ACTIVITIES,
  API_DOWN_MESSAGE,
  filterSpots,
  formatActivity,
  fetchSpots,
  isMappableSpot,
  markerColorForScore,
  regionBounds,
  shorelineFacing,
} from "./spots.js";

/**
 * Optional `scoresBySpotId` colors markers when recommendation scores exist.
 * Pass the result of scoresFromRecommendations() once GET /recommend is live.
 * This component does not call /recommend.
 */
export default function SpotsMap({ scoresBySpotId = null }) {
  const [reloadKey, setReloadKey] = useState(0);
  const [activity, setActivity] = useState("all");
  const [state, setState] = useState({
    status: "loading",
    regionId: "",
    spots: [],
    bbox: null,
    message: "",
  });

  useEffect(() => {
    const controller = new AbortController();
    setState((prev) => ({ ...prev, status: "loading", message: "" }));
    fetchSpots(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        const mappable = data.spots.filter(isMappableSpot);
        if (data.spots.length > 0 && mappable.length === 0) {
          setState({
            status: "error",
            regionId: data.regionId,
            spots: [],
            bbox: null,
            message: "The API returned spots, but none have coordinates to map.",
          });
          return;
        }
        setState({
          status: mappable.length ? "ready" : "empty",
          regionId: data.regionId,
          spots: mappable,
          bbox: data.bbox,
          message: "",
        });
      })
      .catch((err) => {
        if (err?.name === "AbortError" || controller.signal.aborted) return;
        setState({
          status: "error",
          regionId: "",
          spots: [],
          bbox: null,
          message: err?.message || API_DOWN_MESSAGE,
        });
      });
    return () => controller.abort();
  }, [reloadKey]);

  const visible = useMemo(
    () => filterSpots(state.spots, activity),
    [state.spots, activity]
  );
  const bounds = useMemo(
    () => regionBounds(state.spots, state.bbox),
    [state.spots, state.bbox]
  );
  const scored = useMemo(() => finiteScores(scoresBySpotId), [scoresBySpotId]);

  return (
    <div className="spots-map">
      {state.status === "loading" && (
        <p className="muted" role="status">
          Loading coast spots…
        </p>
      )}

      {state.status === "error" && (
        <div className="map-message" role="alert">
          <p>{state.message}</p>
          <button type="button" onClick={() => setReloadKey((key) => key + 1)}>
            Try again
          </button>
        </div>
      )}

      {state.status === "empty" && (
        <p className="map-message" role="status">
          No coast spots are configured for this region
          {state.regionId ? ` (${state.regionId})` : ""}.
        </p>
      )}

      {state.status === "ready" && (
        <>
          <div className="activity-filter" role="group" aria-label="Filter spots by activity">
            <button
              type="button"
              aria-pressed={activity === "all"}
              onClick={() => setActivity("all")}
            >
              All
            </button>
            {ACTIVITIES.map((name) => (
              <button
                key={name}
                type="button"
                aria-pressed={activity === name}
                onClick={() => setActivity(name)}
              >
                {formatActivity(name)}
              </button>
            ))}
          </div>

          {visible.length === 0 && (
            <p className="muted" role="status">
              No spots include {formatActivity(activity)}.
            </p>
          )}

          {bounds && (
            <MapContainer
              center={boundsCenter(bounds)}
              zoom={9}
              scrollWheelZoom={false}
              className="map-canvas"
              aria-label="Bay Area coast spots"
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <FitBounds bounds={bounds} />
              {visible.map((spot) => {
                const score = scored.get(spot.id);
                return (
                  <Marker
                    key={spot.id || `${spot.lat},${spot.lon}`}
                    position={[Number(spot.lat), Number(spot.lon)]}
                    icon={pinIcon(markerColorForScore(score))}
                    title={spot.name}
                    alt={spot.name}
                  >
                    <Popup minWidth={180} maxWidth={240}>
                      <SpotPopup spot={spot} score={score} />
                    </Popup>
                  </Marker>
                );
              })}
            </MapContainer>
          )}

          <p className="muted spots-summary">
            {state.regionId ? `${state.regionId} · ` : ""}
            {visible.length === state.spots.length
              ? `${state.spots.length} ${state.spots.length === 1 ? "spot" : "spots"}`
              : `${visible.length} of ${state.spots.length} spots`}
          </p>

          {scored.size > 0 && <ScoreLegend />}
        </>
      )}
    </div>
  );
}

function SpotPopup({ spot, score }) {
  const activities = Array.isArray(spot.activities) ? spot.activities : [];
  const facing = shorelineFacing(spot.shoreline_orientation_deg);
  return (
    <div className="spot-popup">
      <p className="spot-name">{spot.name}</p>
      {activities.length > 0 ? (
        <div className="chips">
          {activities.map((activity) => (
            <span key={activity} className="chip">
              {formatActivity(activity)}
            </span>
          ))}
        </div>
      ) : (
        <p className="muted">No activities listed</p>
      )}
      {facing ? (
        <p className="shoreline">
          <svg
            className="shore-arrow"
            viewBox="0 0 12 12"
            width="14"
            height="14"
            aria-hidden="true"
            style={{ transform: `rotate(${facing.rotation}deg)` }}
          >
            <path
              d="M6 1.2v9.2M6 1.2 3.1 4.1M6 1.2l2.9 2.9"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Faces {facing.cardinal} · {facing.label}°
        </p>
      ) : (
        <p className="shoreline">Shoreline orientation unknown</p>
      )}
      {Number.isFinite(score) && (
        <p className="spot-score">Recommendation score {Math.round(score)}</p>
      )}
    </div>
  );
}

function ScoreLegend() {
  const steps = [
    ["80–100", 90],
    ["60–79", 70],
    ["40–59", 50],
    ["20–39", 30],
    ["0–19", 10],
  ];
  return (
    <ul className="score-legend" aria-label="Marker colors by recommendation score">
      {steps.map(([label, sample]) => (
        <li key={label}>
          <i style={{ background: markerColorForScore(sample) }} />
          {label}
        </li>
      ))}
    </ul>
  );
}

function FitBounds({ bounds }) {
  const map = useMap();
  const boundsKey = bounds.flat().join(",");
  useEffect(() => {
    const apply = () => {
      map.invalidateSize();
      const [[south, west], [north, east]] = bounds;
      if (south === north && west === east) {
        map.setView([south, west], 12);
        return;
      }
      map.fitBounds(bounds, { padding: [28, 28], maxZoom: 11 });
    };
    apply();
    window.addEventListener("resize", apply);
    return () => window.removeEventListener("resize", apply);
  }, [map, bounds, boundsKey]);
  return null;
}

function boundsCenter(bounds) {
  return [(bounds[0][0] + bounds[1][0]) / 2, (bounds[0][1] + bounds[1][1]) / 2];
}

function finiteScores(scoresBySpotId) {
  const scored = new Map();
  if (!scoresBySpotId || typeof scoresBySpotId !== "object") return scored;
  for (const [id, value] of Object.entries(scoresBySpotId)) {
    if (value == null || value === "") continue;
    const score = Number(value);
    if (Number.isFinite(score)) scored.set(id, score);
  }
  return scored;
}

const pinCache = new Map();

function pinIcon(color) {
  const cached = pinCache.get(color);
  if (cached) return cached;
  const icon = L.divIcon({
    className: "spot-marker",
    html: `<span class="spot-pin" style="background:${color}"></span>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -14],
  });
  pinCache.set(color, icon);
  return icon;
}
