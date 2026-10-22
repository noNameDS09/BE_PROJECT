/** Small constructors and deterministic helpers shared by the mock fixtures. */
import type { Answer, Citation, Claim, Evidence, EvidenceKind, TraceStep } from "../api/types";
import { citedIds } from "../lib/citations";

/** FNV-1a hash → [0, 1). Deterministic "randomness" so fixtures are stable across reloads. */
export function hash01(...parts: (string | number)[]): number {
  let h = 0x811c9dc5;
  const s = parts.join("|");
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0) / 0x100000000;
}

export function hashHex(...parts: (string | number)[]): string {
  return Math.floor(hash01(...parts) * 0xffffffff)
    .toString(16)
    .padStart(8, "0");
}

export function cite(p: Partial<Citation> = {}): Citation {
  return {
    doc_id: null,
    chunk_id: null,
    fact_id: null,
    quote: null,
    start_char: null,
    end_char: null,
    url: null,
    verified: null,
    ...p,
  };
}

export function evidence(id: string, kind: EvidenceKind, text: string, citation: Citation, value: number | null = null): Evidence {
  return { id, kind, text, citation, value };
}

/** A chunk citation whose span covers `text`, starting at `start`. */
export function chunkCite(docId: string, start: number, text: string, url: string): Citation {
  return cite({
    doc_id: docId,
    chunk_id: `${docId}:${start}`,
    start_char: start,
    end_char: start + text.length,
    url,
  });
}

/** The supporting line the verifier quotes: a passage's first sentence, or a fact's record. */
function supportingQuote(e: Evidence): string | null {
  if (e.citation.quote) return e.citation.quote;
  if (e.kind === "calc") return null;
  const first = e.kind === "chunk" ? (e.text.split(/(?<=[.;])\s+/)[0] ?? e.text) : e.text;
  return first.slice(0, 300);
}

/**
 * Builds a claim; its citations are the cited ledger items, stamped per citation with the
 * verifier verdict (`verified` mirrors `supported`, as the backend does) and the supporting quote.
 */
export function claim(text: string, supported: boolean | null, ledger: Evidence[]): Claim {
  const ids = citedIds(text);
  const citations = ids
    .map((id) => ledger.find((e) => e.id === id))
    .filter((e): e is Evidence => Boolean(e))
    .map((e) => ({ ...e.citation, quote: supportingQuote(e), verified: supported }));
  return { text, citations, supported };
}

export function emptyAnswer(): Answer {
  return { text: "", claims: [], charts: [], abstained: false, trace: [], evidence: [], removed_claims: [] };
}

/** Joins claim texts (and optional extra sentences) into the answer text. */
export function joinText(claims: Claim[], tail?: string): string {
  return [...claims.map((c) => c.text), ...(tail ? [tail] : [])].join(" ");
}

// ---------------------------------------------------------------- model profiles and traces

interface ModelProfile {
  speed: number; // latency multiplier
  inPrice: number; // USD per 1M input tokens (0 = free tier)
  outPrice: number;
}

export const MODEL_PROFILE: Record<string, ModelProfile> = {
  "nim-nemotron-super": { speed: 0.9, inPrice: 0, outPrice: 0 },
  "groq-llama-70b": { speed: 0.45, inPrice: 0, outPrice: 0 },
  "gemini-flash": { speed: 1.0, inPrice: 0.3, outPrice: 2.5 },
  "gemini-flash-lite": { speed: 0.7, inPrice: 0.1, outPrice: 0.4 },
  "or-qwen-72b": { speed: 1.7, inPrice: 0, outPrice: 0 },
  "or-llama-70b": { speed: 1.5, inPrice: 0, outPrice: 0 },
  "nim-llama-70b": { speed: 1.1, inPrice: 0, outPrice: 0 },
  "ollama-qwen-7b": { speed: 2.6, inPrice: 0, outPrice: 0 },
  "ollama-llama-8b": { speed: 2.4, inPrice: 0, outPrice: 0 },
};

export function profile(model: string): ModelProfile {
  return MODEL_PROFILE[model] ?? { speed: 1, inPrice: 0, outPrice: 0 };
}

export function modelStep(
  stage: string,
  model: string,
  seed: string,
  tokensIn: number,
  tokensOut: number,
  baseMs: number,
  input: unknown,
  output: unknown,
): TraceStep {
  const p = profile(model);
  const jitter = 0.85 + 0.3 * hash01(seed, stage, tokensIn);
  const tin = Math.round(tokensIn * (0.9 + 0.2 * hash01(seed, "in", stage)));
  const tout = Math.round(tokensOut * (0.85 + 0.3 * hash01(seed, "out", stage)));
  return {
    stage,
    name: model,
    input,
    output,
    model,
    tokens_in: tin,
    tokens_out: tout,
    latency_ms: Math.round(baseMs * p.speed * jitter),
    cost_usd: Number(((tin * p.inPrice + tout * p.outPrice) / 1e6).toFixed(6)),
  };
}

export function toolStep(name: string, input: unknown, output: unknown, latencyMs: number): TraceStep {
  return { stage: "tool", name, input, output, model: null, tokens_in: 0, tokens_out: 0, latency_ms: latencyMs, cost_usd: 0 };
}

/**
 * The trace shape each orchestration produces, given the tool calls a grounded answer needs.
 * Mirrors the arms described in README "Orchestrations we compare".
 */
export function armTrace(arm: string, model: string, seed: string, question: string, tools: TraceStep[], answer: Answer): TraceStep[] {
  const evidenceIds = answer.evidence.map((e) => e.id);
  const compose = (stage = "answer", extraIn = 0) =>
    modelStep(stage, model, seed, 2200 + extraIn + 260 * tools.length, 180 + 30 * answer.claims.length, 1500, { question, evidence_ids: evidenceIds }, answer.text);
  const thought = (i: number, t: TraceStep) =>
    modelStep("step", model, `${seed}:${i}`, 900 + 450 * i, 70, 700, { question, scratchpad_steps: i }, `Thought: I need ${t.name} with ${JSON.stringify(t.input)}.`);

  switch (arm) {
    case "b0":
      return [modelStep("answer", model, seed, 320, 140, 1100, { question, tools: "none", retrieval: "none" }, answer.text)];
    case "rag": {
      const search = tools.find((t) => t.name === "search_filings") ?? toolStep("search_filings", { query: question, k: 8 }, { chunks: [] }, 140);
      return [search, compose("answer", 1200)];
    }
    case "react":
      return [...tools.flatMap((t, i) => [thought(i, t), t]), compose()];
    case "plan_execute":
      return [
        modelStep("plan", model, seed, 1100, 160, 900, { question }, { steps: tools.map((t) => ({ tool: t.name, args: t.input })) }),
        ...tools,
        compose(),
      ];
    case "router":
      return [
        modelStep("route", model, seed, 640, 60, 520, { question }, { agent: tools.some((t) => t.name === "list_events") ? "events_agent" : "numbers_agent" }),
        ...tools.flatMap((t, i) => [thought(i, t), t]),
        compose(),
      ];
    case "self_refine":
      return [
        ...tools.flatMap((t, i) => [thought(i, t), t]),
        compose(),
        modelStep("critique", model, seed, 2600, 150, 1300, { draft: answer.text }, { issues: [], verdict: "keep" }),
        compose("answer", 400),
      ];
    case "loupe":
    default: {
      const route = modelStep("route", model, seed, 700, 90, 540, { question }, {
        intents: tools.map((t) => t.name),
        path: tools.length > 2 ? "multi-step" : "simple",
      });
      const plan =
        tools.length > 2
          ? [modelStep("plan", model, seed, 1000, 150, 820, { question }, { steps: tools.map((t) => ({ tool: t.name, args: t.input })) })]
          : [];
      const verify: TraceStep = {
        stage: "verify",
        name: "code_verifier",
        input: { claims: answer.claims.length, evidence: evidenceIds },
        output: {
          supported: answer.claims.filter((c) => c.supported === true).length,
          unsupported: answer.claims.filter((c) => c.supported === false).length,
          unchecked: answer.claims.filter((c) => c.supported === null).length,
          action: answer.abstained ? "abstain" : "accept",
        },
        model: null,
        tokens_in: 0,
        tokens_out: 0,
        latency_ms: 35,
        cost_usd: 0,
      };
      return [route, ...plan, ...tools, compose("compose"), verify];
    }
  }
}

export function totals(trace: TraceStep[]): { tokens: number; latency_ms: number; cost_usd: number } {
  return {
    tokens: trace.reduce((s, t) => s + t.tokens_in + t.tokens_out, 0),
    latency_ms: trace.reduce((s, t) => s + t.latency_ms, 0),
    cost_usd: Number(trace.reduce((s, t) => s + t.cost_usd, 0).toFixed(6)),
  };
}

export function sleep(ms: number): Promise<void> {
  return ms > 0 ? new Promise((r) => setTimeout(r, ms)) : Promise.resolve();
}
