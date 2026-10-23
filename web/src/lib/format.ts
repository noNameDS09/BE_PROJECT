import type { Metric } from "../api/types";

/** Metrics whose values are fractions in [0, 1] and are shown as percentages. */
const RATE_METRICS = new Set([
  "accuracy",
  "hallucination_rate",
  "supported_rate",
  "abstain_rate",
  "retrieval_recall",
  "correct",
]);

export function isRateMetric(name: string): boolean {
  return RATE_METRICS.has(name) || name.endsWith("_rate");
}

/** Metrics where lower is better (for colouring and sort direction hints). */
export function lowerIsBetter(name: string): boolean {
  return name === "hallucination_rate";
}

export const DASH = "—"; /* taste-skill-ignore */

/** 0.6234 → "62.3%". */
export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH;
  return `${(value * 100).toFixed(digits)}%`;
}

/** A difference of two rates in percentage points: 0.051 → "+5.1 pp". */
export function formatPp(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH;
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)} pp`;
}

/** Formats a bootstrap estimate as `mean [lo, hi]`, e.g. "62.3% [55.1, 69.0]". */
export function formatMetric(metric: Metric | null | undefined, opts: { rate?: boolean; digits?: number } = {}): string {
  const rate = opts.rate ?? true;
  const digits = opts.digits ?? 1;
  if (!metric || metric.mean === null || metric.mean === undefined) return DASH;
  const scale = rate ? 100 : 1;
  const fmt = (v: number) => (v * scale).toFixed(digits);
  const mean = rate ? `${fmt(metric.mean)}%` : fmt(metric.mean);
  if (metric.lo === null || metric.hi === null || metric.lo === undefined || metric.hi === undefined) return mean;
  return `${mean} [${fmt(metric.lo)}, ${fmt(metric.hi)}]`;
}

/** 4210 → "4,210"; 1_250_000 → "1.25M". */
export function formatTokens(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return DASH;
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  return Math.round(n).toLocaleString("en-US");
}

/** 640 → "640 ms"; 6230 → "6.23 s"; 95_000 → "1m 35s". */
export function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return DASH;
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(2)} s`;
  const m = Math.floor(ms / 60_000);
  const s = Math.round((ms % 60_000) / 1000);
  return `${m}m ${s}s`;
}

/** 0 → "$0"; 0.00042 → "$0.00042"; 1.5 → "$1.50". */
export function formatCost(usd: number | null | undefined): string {
  if (usd === null || usd === undefined || Number.isNaN(usd)) return DASH;
  if (usd === 0) return "$0";
  if (Math.abs(usd) < 0.01) return `$${usd.toPrecision(2)}`;
  return `$${usd.toFixed(2)}`;
}

/** Large values in base units (e.g. USD) → "$25.79B". */
export function formatValue(value: number | null | undefined, unit?: string | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH;
  const abs = Math.abs(value);
  const usd = !unit || unit.toUpperCase() === "USD";
  const prefix = usd ? "$" : "";
  const suffix = usd ? "" : unit ? ` ${unit}` : "";
  if (unit === "%" || unit === "percent") return `${value.toFixed(2)}%`;
  if (abs >= 1e9) return `${prefix}${(value / 1e9).toFixed(2)}B${suffix}`;
  if (abs >= 1e6) return `${prefix}${(value / 1e6).toFixed(2)}M${suffix}`;
  if (abs >= 1e4) return `${prefix}${Math.round(value).toLocaleString("en-US")}${suffix}`;
  return `${prefix}${Number(value.toPrecision(6))}${suffix}`;
}

export type Correctness = "correct" | "partial" | "incorrect" | "ungraded";

/** Maps ResultRow.correct / Gold.correct (1/0, or judge score 0..1) to a badge state. */
export function correctness(correct: number | null | undefined): Correctness {
  if (correct === null || correct === undefined) return "ungraded";
  if (correct >= 0.999) return "correct";
  if (correct <= 0.001) return "incorrect";
  return correct >= 0.5 ? "partial" : "incorrect";
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().slice(0, 16).replace("T", " ");
}

/** Pretty JSON for trace inputs/outputs; strings are shown as-is. */
export function prettyJson(value: unknown): string {
  if (value === undefined) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function truncate(s: string, max: number): string {
  return s.length <= max ? s : `${s.slice(0, max - 1).trimEnd()}…`;
}
