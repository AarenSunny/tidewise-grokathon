// Base URL for the TideWise API.
// Production (Vercel): set VITE_API_URL to the deployed backend, e.g. https://tidewise-api.onrender.com
// Local dev: leave unset; Vite's dev proxy forwards /health, /spots, /query, /recommend to :8000.
export const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");

export const apiUrl = (path) => `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
