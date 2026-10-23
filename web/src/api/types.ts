/**
 * TypeScript mirror of the backend contract. Field names are snake_case, exactly as they
 * appear on the wire.
 *
 *   docs/api.md                 – endpoint shapes (RunResult, Evidence, Chart, …)
 *   src/loupe/core/schemas.py   – Citation, Claim, TraceStep, Answer
 *   src/loupe/eval/schema.py    – EvalDoc, GoldEvidence, EvalItem, ResultRow
 *
 * Pydantic fields with a default are still always serialised, so they are required here;
 * `X | None` becomes `X | null`. Fields marked "UI extension" are optional additions the
 * frontend understands but the backend does not have to send (see web/README.md).
 */

// ---------------------------------------------------------------- core/schemas.py

export interface Citation {
  doc_id: string | null;
  chunk_id: string | null;
  fact_id: string | null;
  /** For passage citations: the exact supporting line from the filing. */
  quote: string | null;
  start_char: number | null;
  end_char: number | null;
  /**
   * Fact citations usually point to SEC's inline XBRL viewer ("https://www.sec.gov/ix?doc=/Archives/…");
   * otherwise this is the filing (folder) URL.
   */
  url: string | null;
  /**
   * Set per citation by the verifier, never by the model: true = the claim's numbers/quotes match
   * this evidence, false = they don't, null = nothing checkable.
   */
  verified: boolean | null;
}

export interface Claim {
  /** One sentence of the answer, including its [E#] markers. */
  text: string;
  citations: Citation[];
  /** true = numbers/quotes match cited evidence; false = they don't; null = nothing checkable. */
  supported: boolean | null;
}

/** Known stages; the backend may send others, so the type stays open. */
export type TraceStage =
  | "route"
  | "plan"
  | "step"
  | "tool"
  | "answer"
  | "compose"
  | "verify"
  | "critique"
  | (string & {});

export interface TraceStep {
  stage: TraceStage;
  name: string;
  input: unknown;
  output: unknown;
  model: string | null;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  cost_usd: number;
}

export type EvidenceKind = "chunk" | "fact" | "calc";

/** One ledger item an answer can cite (Answer.evidence entries). */
export interface Evidence {
  id: string; // "E1"
  kind: EvidenceKind;
  text: string;
  citation: Citation;
  value: number | null;
}

/** A Plotly figure spec built only from verified numbers (Answer.charts entries). */
export interface PlotlyFigure {
  data: Record<string, unknown>[];
  layout?: Record<string, unknown>;
}

export interface Chart {
  title: string;
  figure: PlotlyFigure;
  evidence_ids: string[];
}

export interface Answer {
  text: string;
  claims: Claim[];
  charts: Chart[];
  abstained: boolean;
  trace: TraceStep[];
  evidence: Evidence[];
  /**
   * Sentences Loupe's code verifier removed because their numbers or quotes did not match the
   * cited evidence. Empty for other arms; absent on answers stored before the field existed.
   */
  removed_claims?: string[];
}

// ---------------------------------------------------------------- docs/api.md: runs

export interface Gold {
  answer: string;
  /** 1/0 for numeric and refusal items, judge score 0..1 for text; null = not graded yet. */
  correct: number | null;
}

export interface RunResult {
  run_id: string;
  arm: string;
  model: string;
  question: string;
  /** null when the run failed before producing an answer (see `error`). */
  answer: Answer | null;
  tokens: number;
  latency_ms: number;
  cost_usd: number;
  gold: Gold | null;
  /** Set when the model call failed; `answer` is then empty. */
  error: string | null;
}

export interface RunConfigPick {
  arm: string;
  model: string;
}

export interface RunRequest {
  question: string;
  arm: string;
  model: string;
  item_id: string | null;
}

export interface CompareRequest {
  question: string | null;
  item_id: string | null;
  /** At most MAX_COMPARE_CONFIGS entries. */
  configs: RunConfigPick[];
}

export const MAX_COMPARE_CONFIGS = 4;

export interface CompareResponse {
  results: RunResult[];
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface ChatRequest {
  messages: ChatMessage[];
  model: string;
  /** Orchestration arm that answers; the backend defaults to "loupe". */
  arm?: string;
}

// ---------------------------------------------------------------- docs/api.md: config

export interface HealthResponse {
  ok: boolean;
  index: string;
  models_with_keys: number;
}

/**
 * Which tools an arm may call (decision D21): "harness" = Loupe's financial tool harness,
 * "generic" = what a standard agent framework ships, "none" = no tools.
 */
export type Toolset = "harness" | "generic" | "none";

export interface ArmInfo {
  name: string;
  label: string;
  description: string;
  toolset: Toolset;
  /** Tool names this arm may call. */
  tools: string[];
}

export interface ModelInfo {
  alias: string;
  provider: string;
  /** The provider's model id, e.g. "nvidia_nim/nvidia/nemotron-3-super-120b-a12b". */
  model: string;
  available: boolean;
}

/** One of OpenRouter's current free models (GET /api/openrouter/models). */
export interface OpenRouterModel {
  /** "openrouter/<id>"; usable anywhere a model alias is accepted. */
  alias: string;
  /** OpenRouter's model id, e.g. "google/gemma-4-31b-it:free". */
  id: string;
  name: string;
  context_length: number | null;
  /** Supports tool calling (needed by every arm except B0 and RAG). */
  tools: boolean;
  free: boolean;
}

export interface OpenRouterModelsResponse {
  /** Tool-calling models first. */
  models: OpenRouterModel[];
  /** Unix seconds when the backend fetched the list from OpenRouter. */
  fetched_at: number;
}

export interface DatasetInfo {
  name: string;
  items: number;
  kinds: Kind[];
}

export interface CompanyInfo {
  id: string;
  name: string;
  sector: string;
  group: string;
  split: Split | null;
}

export interface ConfigResponse {
  arms: ArmInfo[];
  models: ModelInfo[];
  datasets: DatasetInfo[];
  companies: CompanyInfo[];
}

// ---------------------------------------------------------------- eval/schema.py

export type Kind = "numeric" | "text" | "refusal" | "event" | "plan" | "retrieval";
export const KINDS: Kind[] = ["numeric", "text", "refusal", "event", "plan", "retrieval"];

export type Split = "dev" | "test";
export type ItemMode = "corpus" | "docs" | "context";

export interface EvalDoc {
  doc_id: string;
  title: string;
  text: string | null;
  path: string | null;
}

export interface GoldEvidence {
  doc_id: string | null;
  page: number | null;
  text: string | null;
  accession: string | null;
  item: string | null;
}

export interface EvalItem {
  item_id: string; // "<dataset>:<native id>"
  dataset: string;
  question: string;
  kind: Kind;
  answer: string | null;
  answer_value: number | null;
  answer_unit: string | null;
  tolerance: number;
  mode: ItemMode;
  context: string | null;
  documents: EvalDoc[];
  evidence: GoldEvidence[];
  companies: string[];
  fiscal_year: number | null;
  turns: string[];
  expected_tools: string[];
  expected_intents: string[];
  split: Split | null;
  category: string | null;
  meta: Record<string, unknown>;
}

export interface ResultRow {
  run_id: string;
  item_id: string;
  dataset: string;
  arm: string;
  model: string;
  config_hash: string;
  answer: string;
  correct: number | null;
  supported_rate: number | null;
  hallucinated: boolean | null;
  abstained: boolean;
  retrieval_recall: number | null;
  tokens: number;
  latency_ms: number;
  cost_usd: number;
  error: string | null;
  /** ISO 8601 datetime. */
  created_at: string;
  /** UI extension: if `meta.answer` holds a full Answer, Runs renders claims/evidence/trace. */
  meta: Record<string, unknown>;
}

export interface ItemsQuery {
  offset?: number;
  limit?: number;
  split?: Split | "";
  kind?: Kind | "";
  q?: string;
}

export interface ItemsResponse {
  total: number;
  items: EvalItem[];
}

// ---------------------------------------------------------------- docs/api.md: results

/** A bootstrap estimate. Rates are fractions in [0, 1]; null when not computable. */
export interface Metric {
  mean: number | null;
  lo: number | null;
  hi: number | null;
}

export type LeaderboardMetricName =
  | "accuracy"
  | "hallucination_rate"
  | "supported_rate"
  | "abstain_rate";

export interface LeaderboardRow {
  arm: string;
  model: string;
  dataset: string;
  n: number;
  /** Keyed by LeaderboardMetricName; extra metrics are allowed and shown if present. */
  metrics: Partial<Record<string, Metric>>;
  /** Mean per run. */
  tokens: number;
  /** Mean per run. */
  latency_ms: number;
  /** Mean per run. */
  cost_usd: number;
}

export interface LeaderboardQuery {
  dataset?: string;
  split?: Split | "";
  model?: string;
  arm?: string;
}

export interface LeaderboardResponse {
  rows: LeaderboardRow[];
}

export interface StageStep {
  label: string;
  arm: string;
  accuracy: Metric;
  hallucination_rate: Metric;
  /**
   * UI extension: "step" rows form the B0 → Loupe waterfall (in order); "ablation" rows are
   * shown only in the table. Absent = "step".
   */
  kind?: "step" | "ablation";
}

export interface StagesQuery {
  dataset?: string;
  model?: string;
}

export interface StagesResponse {
  steps: StageStep[];
}

export interface RunsQuery {
  dataset?: string;
  arm?: string;
  model?: string;
  correct?: "true" | "false" | "";
  limit?: number;
}

export interface RunsResponse {
  rows: ResultRow[];
}

// ---------------------------------------------------------------- docs/api.md: documents

export interface DocumentQuery {
  start?: number | null;
  end?: number | null;
  context?: number;
}

export interface DocumentResponse {
  doc_id: string;
  company_id: string;
  form: string;
  period_end: string | null;
  url: string;
  /** The requested window of the document (cited span ± `context` chars). */
  text: string;
  /** [start, end] of the cited span, as offsets into `text` (not into the full document). */
  highlight: [number, number] | null;
}

/** Error body for HTTP 4xx/5xx. */
export interface ApiErrorBody {
  detail: string | unknown;
}
