import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App.jsx";
import SpotsMap from "./SpotsMap.jsx";
import { API_DOWN_MESSAGE } from "./spots.js";

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }) => <div data-testid="map">{children}</div>,
  TileLayer: () => <div data-testid="osm-tiles" />,
  Marker: ({ children, position }) => (
    <div data-testid="marker" data-lat={position?.[0]} data-lon={position?.[1]}>
      {children}
    </div>
  ),
  Popup: ({ children }) => <div>{children}</div>,
  useMap: () => ({
    fitBounds: () => {},
    setView: () => {},
    invalidateSize: () => {},
  }),
}));

const spots = [
  {
    id: "half_moon_bay",
    name: "Half Moon Bay",
    lat: 37.4636,
    lon: -122.4286,
    shoreline_orientation_deg: 270,
    activities: ["clamming", "crabbing", "swimming", "sailing"],
  },
  {
    id: "pacifica",
    name: "Pacifica",
    lat: 37.6138,
    lon: -122.4869,
    shoreline_orientation_deg: 270,
    activities: ["clamming", "swimming"],
  },
  {
    id: "sf_bay",
    name: "San Francisco Bay",
    lat: 37.8076,
    lon: -122.4156,
    shoreline_orientation_deg: 180,
    activities: ["sailing", "crabbing", "swimming"],
  },
];

function jsonResponse(body, ok = true) {
  return {
    ok,
    status: ok ? 200 : 503,
    json: async () => body,
  };
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SpotsMap", () => {
  it("filters markers by activity and shows shoreline and chips", async () => {
    fetch.mockResolvedValue(
      jsonResponse({ region_id: "sf_bay_coast", spots })
    );
    const user = userEvent.setup();
    render(<SpotsMap />);

    const markers = await screen.findAllByTestId("marker");
    expect(markers).toHaveLength(3);
    expect(screen.getByTestId("osm-tiles")).toBeInTheDocument();
    expect(within(markers[0]).getByText("Half Moon Bay")).toBeInTheDocument();
    expect(within(markers[0]).getByText("Clamming")).toBeInTheDocument();
    expect(within(markers[0]).getByText(/Faces W · 270°/)).toBeInTheDocument();
    expect(within(markers[2]).getByText(/Faces S · 180°/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Clamming" }));

    const filtered = screen.getAllByTestId("marker");
    expect(filtered).toHaveLength(2);
    expect(screen.getByText("Half Moon Bay")).toBeInTheDocument();
    expect(screen.getByText("Pacifica")).toBeInTheDocument();
    expect(screen.queryByText("San Francisco Bay")).not.toBeInTheDocument();
    expect(screen.getByText(/2 of 3 spots/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "All" }));
    expect(screen.getAllByTestId("marker")).toHaveLength(3);
    expect(fetch.mock.calls.every((call) => String(call[0]).endsWith("/spots"))).toBe(true);
  });

  it("shows a clear message when the API is down and does not invent spots", async () => {
    fetch.mockRejectedValue(new TypeError("Failed to fetch"));
    const user = userEvent.setup();
    render(<SpotsMap />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(API_DOWN_MESSAGE);
    expect(screen.queryByTestId("marker")).not.toBeInTheDocument();
    expect(screen.queryByText("Half Moon Bay")).not.toBeInTheDocument();
    expect(screen.queryByTestId("map")).not.toBeInTheDocument();

    fetch.mockResolvedValueOnce(jsonResponse({ region_id: "sf_bay_coast", spots }));
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findAllByTestId("marker")).toHaveLength(3);
  });

  it("treats an HTTP error as the API being down", async () => {
    fetch.mockResolvedValue(jsonResponse({ detail: "unavailable" }, false));
    render(<SpotsMap />);
    expect(await screen.findByRole("alert")).toHaveTextContent(API_DOWN_MESSAGE);
    expect(screen.queryByTestId("marker")).not.toBeInTheDocument();
  });

  it("shows an empty state when the API returns no spots", async () => {
    fetch.mockResolvedValue(jsonResponse({ region_id: "sf_bay_coast", spots: [] }));
    render(<SpotsMap />);
    expect(
      await screen.findByText("No coast spots are configured for this region (sf_bay_coast).")
    ).toBeInTheDocument();
    expect(screen.queryByTestId("marker")).not.toBeInTheDocument();
    expect(screen.queryByTestId("map")).not.toBeInTheDocument();
  });

  it("shows a score from the parent hook and still only fetches /spots", async () => {
    fetch.mockResolvedValue(jsonResponse({ region_id: "sf_bay_coast", spots }));
    render(<SpotsMap scoresBySpotId={{ half_moon_bay: 88 }} />);
    expect(await screen.findByText("Recommendation score 88")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Marker colors by recommendation score" })).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(String(fetch.mock.calls[0][0])).toBe("/spots");
  });
});

describe("App map panel", () => {
  it("replaces the Leaflet placeholder with the live map", async () => {
    fetch.mockResolvedValue(jsonResponse({ region_id: "sf_bay_coast", spots }));
    render(<App />);
    expect(screen.queryByText(/Leaflet spots map/i)).not.toBeInTheDocument();
    expect(await screen.findAllByTestId("marker")).toHaveLength(3);
    expect(screen.getByRole("heading", { name: "Map" })).toBeInTheDocument();
  });
});
