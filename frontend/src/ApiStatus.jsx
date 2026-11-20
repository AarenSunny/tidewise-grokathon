import { useEffect, useState } from "react";
import { API_BASE, apiUrl } from "./api.js";

// Minimal production check: proves the deployed frontend can reach the backend.
export default function ApiStatus() {
  const [state, setState] = useState({ status: "checking" });

  useEffect(() => {
    Promise.all([fetch(apiUrl("/health")), fetch(apiUrl("/spots"))])
      .then(async ([h, s]) => {
        if (!h.ok || !s.ok) throw new Error(`HTTP ${h.status} / ${s.status}`);
        const health = await h.json();
        const spots = await s.json();
        setState({ status: "ok", health: health.status, spots: spots.spots.map((x) => x.name) });
      })
      .catch((err) => setState({ status: "error", error: String(err) }));
  }, []);

  return (
    <p className="muted" data-testid="api-status">
      Backend ({API_BASE || "local proxy"}):{" "}
      {state.status === "checking" && "checking…"}
      {state.status === "ok" && `connected, health ${state.health}, ${state.spots.length} spots (${state.spots.join(", ")})`}
      {state.status === "error" && `unreachable (${state.error})`}
    </p>
  );
}
