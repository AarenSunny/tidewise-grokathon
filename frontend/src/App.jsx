/**
 * App shell. The map reads GET /spots.
 * When GET /recommend exists, pass scoresFromRecommendations(...)
 * as scoresBySpotId on SpotsMap. Do not call /recommend yet.
 */
import SpotsMap from "./SpotsMap.jsx";

export default function App() {
  return (
    <div className="app">
      <header>
        <h1>TideWise</h1>
        <p>Best times and places for Bay Area water recreation.</p>
      </header>
      <main className="layout">
        <section className="chat panel">
          <h2>Ask</h2>
          <p className="muted">Chat → IntentBot (Phase 6–7)</p>
        </section>
        <section className="results panel">
          <h2>Ranked windows</h2>
          <p className="muted">Scorer output (Phase 5–7)</p>
        </section>
        <section className="map panel">
          <h2>Map</h2>
          <SpotsMap />
        </section>
        <section className="health panel">
          <h2>Data health</h2>
          <p className="muted">GET /health (Phase 3+)</p>
        </section>
      </main>
    </div>
  );
}
