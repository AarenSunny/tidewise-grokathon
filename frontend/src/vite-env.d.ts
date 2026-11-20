/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Optional backend origin. Empty/unset uses the Vite dev proxy (same-origin). */
  readonly VITE_API_BASE_URL?: string;
  /** Alternate backend origin used by the Render/Vercel helper. */
  readonly VITE_API_URL?: string;
  /**
   * Truthy values (`1`, `true`, `yes`, `on`) skip the network and always
   * render labeled example data in preview mode.
   */
  readonly VITE_FORCE_PREVIEW?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
