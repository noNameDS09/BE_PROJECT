import type {
  ChatRequest,
  CompareRequest,
  CompareResponse,
  ConfigResponse,
  DocumentQuery,
  DocumentResponse,
  EvalItem,
  HealthResponse,
  ItemsQuery,
  ItemsResponse,
  LeaderboardQuery,
  LeaderboardResponse,
  RunRequest,
  RunResult,
  RunsQuery,
  RunsResponse,
  StagesQuery,
  StagesResponse,
} from "./types";

/** Every backend call the UI makes. Implemented over HTTP and by the mock in src/mocks/. */
export interface ApiClient {
  health(): Promise<HealthResponse>;
  config(): Promise<ConfigResponse>;
  run(body: RunRequest): Promise<RunResult>;
  compare(body: CompareRequest): Promise<CompareResponse>;
  datasetItems(name: string, query?: ItemsQuery): Promise<ItemsResponse>;
  datasetItem(name: string, itemId: string): Promise<EvalItem>;
  leaderboard(query?: LeaderboardQuery): Promise<LeaderboardResponse>;
  stages(query?: StagesQuery): Promise<StagesResponse>;
  runs(query?: RunsQuery): Promise<RunsResponse>;
  document(docId: string, query?: DocumentQuery): Promise<DocumentResponse>;
  chat(body: ChatRequest): Promise<RunResult>;
}

/** An HTTP failure, carrying the `detail` from the `{ "detail": … }` error body. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(status ? `${status}: ${detail}` : detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

type QueryValue = string | number | boolean | null | undefined;

/** Builds `?a=1&b=x`, skipping empty values. Exported for tests. */
export function buildQuery(params: Record<string, QueryValue> | object = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params) as [string, QueryValue][]) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

function detailToString(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{ loc, msg, type }]
    return detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : JSON.stringify(d)))
      .join("; ");
  }
  return JSON.stringify(detail);
}

export function createHttpClient(base: string, fetchImpl: typeof fetch = fetch): ApiClient {
  const root = base.replace(/\/+$/, "");

  async function request<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
    let res: Response;
    try {
      res = await fetchImpl(`${root}${path}`, {
        method,
        headers: body === undefined ? { Accept: "application/json" } : { "Content-Type": "application/json", Accept: "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch (err) {
      throw new ApiError(0, `Could not reach the API at ${root} (${err instanceof Error ? err.message : String(err)})`);
    }
    if (!res.ok) {
      let detail = res.statusText || "Request failed";
      try {
        const data = (await res.json()) as { detail?: unknown };
        if (data && data.detail !== undefined) detail = detailToString(data.detail);
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(res.status, detail);
    }
    return (await res.json()) as T;
  }

  const enc = encodeURIComponent;

  return {
    health: () => request("GET", "/health"),
    config: () => request("GET", "/config"),
    run: (body) => request("POST", "/runs", body),
    compare: (body) => request("POST", "/compare", body),
    datasetItems: (name, query) => request("GET", `/datasets/${enc(name)}/items${buildQuery(query)}`),
    datasetItem: (name, itemId) => request("GET", `/datasets/${enc(name)}/items/${enc(itemId)}`),
    leaderboard: (query) => request("GET", `/results/leaderboard${buildQuery(query)}`),
    stages: (query) => request("GET", `/results/stages${buildQuery(query)}`),
    runs: (query) => request("GET", `/results/runs${buildQuery(query)}`),
    document: (docId, query) => request("GET", `/documents/${enc(docId)}${buildQuery(query)}`),
    chat: (body) => request("POST", "/chat", body),
  };
}

export const MOCK_MODE = import.meta.env.VITE_MOCK === "1";
export const API_BASE = import.meta.env.VITE_API_BASE || "/api";

/** Defers every call to a client that is loaded asynchronously (keeps fixtures out of the main bundle). */
function deferred(load: Promise<ApiClient>): ApiClient {
  return {
    health: () => load.then((c) => c.health()),
    config: () => load.then((c) => c.config()),
    run: (b) => load.then((c) => c.run(b)),
    compare: (b) => load.then((c) => c.compare(b)),
    datasetItems: (n, q) => load.then((c) => c.datasetItems(n, q)),
    datasetItem: (n, id) => load.then((c) => c.datasetItem(n, id)),
    leaderboard: (q) => load.then((c) => c.leaderboard(q)),
    stages: (q) => load.then((c) => c.stages(q)),
    runs: (q) => load.then((c) => c.runs(q)),
    document: (id, q) => load.then((c) => c.document(id, q)),
    chat: (b) => load.then((c) => c.chat(b)),
  };
}

export const api: ApiClient = MOCK_MODE
  ? deferred(
      import("../mocks").then((m) =>
        m.createMockClient({ delayMs: Number(import.meta.env.VITE_MOCK_DELAY ?? 350) }),
      ),
    )
  : createHttpClient(API_BASE);
