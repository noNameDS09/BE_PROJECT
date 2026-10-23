import type { OpenRouterModel } from "../api/types";

/** Any alias with this prefix is accepted by the backend, even if /api/config does not list it. */
export const OPENROUTER_PREFIX = "openrouter/";

/** The <select> value of the "Custom OpenRouter model…" option (never a real alias). */
export const CUSTOM_OPTION = "__custom_openrouter__";

export const NO_TOOLS_HINT =
  "This model does not support tool calling. Agent methods (ReAct, Plan-and-Execute, FARE router, Self-Refine, Loupe) need it; B0 and RAG work without it.";

export function isOpenRouterAlias(alias: string): boolean {
  return alias.startsWith(OPENROUTER_PREFIX);
}

/**
 * A typed OpenRouter id → model alias: "qwen/qwen3-235b-a22b:free" → "openrouter/qwen/qwen3-235b-a22b:free".
 * A pasted "openrouter/" prefix is stripped first, but only when what follows is still a
 * "vendor/model" id: OpenRouter's own router is literally "openrouter/free". Blank input gives "".
 */
export function toOpenRouterAlias(input: string): string {
  let id = input.trim();
  if (id.toLowerCase().startsWith(OPENROUTER_PREFIX) && id.slice(OPENROUTER_PREFIX.length).includes("/")) {
    id = id.slice(OPENROUTER_PREFIX.length).trim();
  }
  return id ? OPENROUTER_PREFIX + id : "";
}

/** The OpenRouter id inside an alias ("" for non-OpenRouter aliases). */
export function openRouterId(alias: string): string {
  return isOpenRouterAlias(alias) ? alias.slice(OPENROUTER_PREFIX.length) : "";
}

/** 262144 → "262k"; 1048576 → "1M"; null → "". */
export function formatContext(tokens: number | null | undefined): string {
  if (!tokens || tokens <= 0) return "";
  if (tokens >= 1_000_000) return `${Number((tokens / 1_000_000).toFixed(1))}M`;
  return `${Math.max(1, Math.round(tokens / 1000))}k`;
}

/** "Google: Gemma 4 31B (free)" → "Gemma 4 31B" (the whole group is free; the id is in the tooltip). */
export function shortModelName(name: string): string {
  const short = name
    .replace(/\s*\(free\)\s*$/i, "")
    .replace(/^[^:]{1,40}:\s+/, "")
    .replace(/\s+/g, " ")
    .trim();
  return short || name.trim();
}

/** Option label for a live OpenRouter model, e.g. "Gemma 4 31B · 262k" or "R1 · 164k · no tools". */
export function openRouterLabel(m: Pick<OpenRouterModel, "name" | "context_length" | "tools">): string {
  const ctx = formatContext(m.context_length);
  return `${shortModelName(m.name)}${ctx ? ` · ${ctx}` : ""}${m.tools ? "" : " · no tools"}`;
}

/**
 * Where the picker shows `value`:
 *   configured – one of /api/config's models
 *   openrouter – one of the live OpenRouter models
 *   pending    – an OpenRouter alias while the live list is still loading
 *   custom     – an OpenRouter alias in neither list (typed by the user)
 *   unknown    – anything else (e.g. a stale alias); shown as-is
 * `openrouter` is null while the live list is loading.
 */
export type ModelValueKind = "configured" | "openrouter" | "pending" | "custom" | "unknown";

export function classifyModelValue(value: string, configured: readonly string[], openrouter: readonly string[] | null): ModelValueKind {
  if (configured.includes(value)) return "configured";
  if (!isOpenRouterAlias(value)) return "unknown";
  if (openrouter === null) return "pending";
  return openrouter.includes(value) ? "openrouter" : "custom";
}

/** True when `alias` is a live OpenRouter model known not to support tool calling. */
export function lacksToolCalling(alias: string, openrouter: readonly OpenRouterModel[] | undefined): boolean {
  return openrouter?.find((m) => m.alias === alias)?.tools === false;
}
