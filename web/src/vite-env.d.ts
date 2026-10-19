/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the backend API. Defaults to "/api" (proxied to :8000 by the dev server). */
  readonly VITE_API_BASE?: string;
  /** "1" serves every call from the fixtures in src/mocks/ instead of the backend. */
  readonly VITE_MOCK?: string;
  /** Artificial latency for mock calls, in ms (default 350). */
  readonly VITE_MOCK_DELAY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "plotly.js-dist-min" {
  const Plotly: object;
  export default Plotly;
}
