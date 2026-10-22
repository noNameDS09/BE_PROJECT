/**
 * Synthetic benchmark results with the expected shape of the real ones (bootstrap CIs, a
 * B0 → Loupe waterfall, per-run rows). The numbers are made up for the UI; they are not results.
 */
import type { LeaderboardQuery, LeaderboardRow, Metric, ResultRow, RunsQuery, StageStep, StagesQuery } from "../../api/types";
import { hash01, hashHex } from "../builders";
import { buildRun } from "../scenarios";
import { ITEMS } from "./items";

const ARM_BASE: Record<string, { acc: number; hall: number; abst: number; tokens: number; latency: number }> = {
  b0: { acc: 0.19, hall: 0.58, abst: 0.02, tokens: 520, latency: 1100 },
  rag: { acc: 0.52, hall: 0.22, abst: 0.06, tokens: 3300, latency: 2900 },
  react: { acc: 0.61, hall: 0.16, abst: 0.05, tokens: 7900, latency: 7400 },
  plan_execute: { acc: 0.63, hall: 0.15, abst: 0.05, tokens: 6800, latency: 6100 },
  router: { acc: 0.6, hall: 0.17, abst: 0.04, tokens: 4200, latency: 4300 },
  self_refine: { acc: 0.66, hall: 0.12, abst: 0.07, tokens: 11800, latency: 11200 },
  loupe: { acc: 0.74, hall: 0.05, abst: 0.11, tokens: 6100, latency: 6600 },
  // Loupe's orchestration with the baselines' generic tools: isolates the harness's effect.
  "loupe-generic-tools": { acc: 0.66, hall: 0.08, abst: 0.12, tokens: 8400, latency: 8100 },
};

const MODEL_SHIFT: Record<string, { acc: number; hall: number; speed: number; price: number }> = {
  "nim-nemotron-super": { acc: 0, hall: 0, speed: 0.9, price: 0 },
  "gemini-flash": { acc: 0.04, hall: -0.02, speed: 1.0, price: 0.0000009 },
  "ollama-qwen-7b": { acc: -0.17, hall: 0.12, speed: 2.6, price: 0 },
};

const DATASET_SHIFT: Record<string, { acc: number; hall: number; n: number }> = {
  "loupe-gold": { acc: 0, hall: 0, n: 240 },
  financebench: { acc: -0.06, hall: 0.03, n: 118 },
  failsafeqa: { acc: -0.02, hall: 0.05, n: 220 },
};

export const LEADERBOARD_MODELS = Object.keys(MODEL_SHIFT);
export const LEADERBOARD_DATASETS = Object.keys(DATASET_SHIFT);

const clamp = (x: number) => Math.min(0.995, Math.max(0.005, x));

/** Normal-approximation 95% interval, asymmetric near the bounds like a bootstrap would be. */
function estimate(p: number, n: number): Metric {
  const half = 1.96 * Math.sqrt((p * (1 - p)) / n);
  const r = (x: number) => Number(x.toFixed(4));
  return { mean: r(p), lo: r(Math.max(0, p - half)), hi: r(Math.min(1, p + half)) };
}

function splitN(n: number, split: string | undefined): number {
  if (split === "dev") return Math.round(n * 0.3);
  if (split === "test") return Math.round(n * 0.7);
  return n;
}

export function leaderboardRows(q: LeaderboardQuery = {}): LeaderboardRow[] {
  const rows: LeaderboardRow[] = [];
  const datasets = q.dataset ? [q.dataset] : LEADERBOARD_DATASETS;
  for (const dataset of datasets) {
    const ds = DATASET_SHIFT[dataset];
    if (!ds) continue;
    for (const [model, ms] of Object.entries(MODEL_SHIFT)) {
      if (q.model && q.model !== model) continue;
      for (const [arm, base] of Object.entries(ARM_BASE)) {
        if (q.arm && q.arm !== arm) continue;
        const seed = `${dataset}|${model}|${arm}|${q.split ?? ""}`;
        const noise = (k: string) => (hash01(seed, k) - 0.5) * 0.04;
        // Loupe's verifier blunts a weak model's hallucinations more than other arms do.
        const hallShift = arm.startsWith("loupe") ? ms.hall * 0.3 : ms.hall;
        const acc = clamp(base.acc + ms.acc + ds.acc + noise("acc"));
        const hall = clamp(base.hall + hallShift + ds.hall + noise("hall"));
        const abst = clamp(base.abst + (model.startsWith("ollama") && arm.startsWith("loupe") ? 0.08 : 0) + noise("abst") / 2);
        const n = splitN(ds.n, q.split);
        rows.push({
          arm,
          model,
          dataset,
          n,
          metrics: {
            accuracy: estimate(acc, n),
            hallucination_rate: estimate(hall, n),
            supported_rate: arm === "b0" ? estimate(clamp(1 - hall - 0.12), n) : estimate(clamp(1 - hall - 0.03), n),
            abstain_rate: estimate(abst, n),
          },
          tokens: Math.round(base.tokens * (0.92 + 0.16 * hash01(seed, "tok"))),
          latency_ms: Math.round(base.latency * ms.speed * (0.9 + 0.2 * hash01(seed, "lat"))),
          cost_usd: Number((base.tokens * ms.price).toFixed(5)),
        });
      }
    }
  }
  return rows;
}

const STAGE_DEFS: { label: string; arm: string; acc: number; hall: number; kind: "step" | "ablation" }[] = [
  { label: "B0 closed book", arm: "b0", acc: 0.19, hall: 0.58, kind: "step" },
  { label: "+ Retrieval (single-shot RAG)", arm: "rag", acc: 0.52, hall: 0.22, kind: "step" },
  { label: "+ Tool loop (ReAct)", arm: "react", acc: 0.61, hall: 0.16, kind: "step" },
  { label: "+ Router & selective planner", arm: "loupe_no_verify", acc: 0.67, hall: 0.13, kind: "step" },
  { label: "+ Code verifier", arm: "loupe_no_abstain", acc: 0.72, hall: 0.07, kind: "step" },
  { label: "+ Abstain policy = Loupe", arm: "loupe", acc: 0.74, hall: 0.05, kind: "step" },
  { label: "Loupe minus router", arm: "loupe-no-router", acc: 0.7, hall: 0.06, kind: "ablation" },
  { label: "Loupe minus planner", arm: "loupe-no-planner", acc: 0.69, hall: 0.06, kind: "ablation" },
  { label: "Loupe minus code verifier", arm: "loupe-no-verifier", acc: 0.68, hall: 0.12, kind: "ablation" },
  { label: "Loupe minus harness (generic tools)", arm: "loupe-generic-tools", acc: 0.66, hall: 0.08, kind: "ablation" },
];

export function stageSteps(q: StagesQuery = {}): StageStep[] {
  const ds = DATASET_SHIFT[q.dataset ?? "loupe-gold"] ?? DATASET_SHIFT["loupe-gold"]!;
  const ms = MODEL_SHIFT[q.model ?? "nim-nemotron-super"] ?? MODEL_SHIFT["nim-nemotron-super"]!;
  return STAGE_DEFS.map((s) => {
    const seed = `${q.dataset}|${q.model}|${s.arm}`;
    const acc = clamp(s.acc + ds.acc + ms.acc + (hash01(seed, "a") - 0.5) * 0.02);
    const hall = clamp(s.hall + ds.hall + ms.hall * (s.arm.startsWith("loupe") ? 0.4 : 1) + (hash01(seed, "h") - 0.5) * 0.02);
    return { label: s.label, arm: s.arm, kind: s.kind, accuracy: estimate(acc, ds.n), hallucination_rate: estimate(hall, ds.n) };
  });
}

// ---------------------------------------------------------------- runs (drill-down)

const RUN_MODELS = LEADERBOARD_MODELS;
const RUN_ARMS = Object.keys(ARM_BASE);

let RUN_ROWS: ResultRow[] | null = null;

function buildRunRows(): ResultRow[] {
  const items = ITEMS.filter((i) => i.answer !== null && i.kind !== "retrieval").slice(0, 26);
  const base = Date.parse("2026-10-17T09:00:00Z");
  const rows: ResultRow[] = [];
  let k = 0;
  for (const item of items) {
    for (const model of RUN_MODELS) {
      for (const arm of RUN_ARMS) {
        k += 1;
        const run = buildRun({ question: null, itemId: item.item_id, arm, model, salt: "stored" });
        const timeout = model === "ollama-qwen-7b" && arm === "self_refine" && hash01(item.item_id, "timeout") < 0.2;
        const claims = run.answer.claims;
        const checkable = claims.filter((c) => c.supported !== null);
        const supported = checkable.filter((c) => c.supported === true).length;
        rows.push({
          run_id: run.run_id,
          item_id: item.item_id,
          dataset: item.dataset,
          arm,
          model,
          config_hash: hashHex(arm, model, "cfg").slice(0, 12).padEnd(12, "0"),
          answer: timeout ? "" : run.answer.text,
          correct: timeout ? null : (run.gold?.correct ?? null),
          supported_rate: timeout || checkable.length === 0 ? null : Number((supported / checkable.length).toFixed(3)),
          hallucinated: timeout || checkable.length === 0 ? null : supported < checkable.length,
          abstained: !timeout && run.answer.abstained,
          retrieval_recall: arm === "b0" || timeout ? null : Number((0.55 + 0.45 * hash01(run.run_id, "recall")).toFixed(2)),
          tokens: timeout ? 0 : run.tokens,
          latency_ms: timeout ? 120000 : run.latency_ms,
          cost_usd: timeout ? 0 : run.cost_usd,
          error: timeout ? "Timeout: no response from ollama_chat/qwen2.5:7b-instruct after 120 s" : null,
          created_at: new Date(base + k * 47_000).toISOString(),
          meta: timeout ? { attempt: 2 } : { answer: run.answer, tools_enabled: arm !== "b0" },
        });
      }
    }
  }
  return rows;
}

export function allRunRows(): ResultRow[] {
  if (!RUN_ROWS) RUN_ROWS = buildRunRows();
  return RUN_ROWS;
}

export function runRows(q: RunsQuery = {}): ResultRow[] {
  const limit = q.limit ?? 50;
  return allRunRows()
    .filter((r) => !q.dataset || r.dataset === q.dataset)
    .filter((r) => !q.arm || r.arm === q.arm)
    .filter((r) => !q.model || r.model === q.model)
    .filter((r) => {
      if (q.correct === "true") return r.correct !== null && r.correct >= 0.5;
      if (q.correct === "false") return r.correct !== null && r.correct < 0.5;
      return true;
    })
    .slice(0, limit);
}
