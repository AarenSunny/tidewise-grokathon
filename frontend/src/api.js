/** Shared API origin. Empty VITE_API_BASE uses the Vite dev proxy. */

export function apiUrl(path) {
  const configured = import.meta.env?.VITE_API_BASE;
  const base = typeof configured === "string" ? configured.trim().replace(/\/+$/, "") : "";
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${base}${suffix}`;
}

export async function fetchJson(path, { signal, method = "GET", body } = {}) {
  const response = await fetch(apiUrl(path), {
    method,
    signal,
    headers: {
      Accept: "application/json",
      ...(body == null ? {} : { "Content-Type": "application/json" }),
    },
    body: body == null ? undefined : JSON.stringify(body),
  });
  let payload = null;
  if (typeof response.json === "function") {
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
  }
  return { ok: response.ok, status: response.status, payload };
}
