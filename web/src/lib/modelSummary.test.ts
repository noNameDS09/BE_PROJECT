import { describe, expect, it } from "vitest";
import type { LeaderboardRow } from "../api/types";
import { summarizeModels } from "./modelSummary";

const row = (arm: string, model: string, dataset: string, acc: number | null, hall: number | null): LeaderboardRow => ({
  arm,
  model,
  dataset,
  n: 10,
  metrics: { accuracy: { mean: acc, lo: null, hi: null }, hallucination_rate: { mean: hall, lo: null, hi: null } },
  tokens: 0,
  latency_ms: 0,
  cost_usd: 0,
});

describe("summarizeModels", () => {
  const rows = [
    row("b0", "m1", "gold", 0.2, 0.6),
    row("react", "m1", "gold", 0.6, 0.15),
    row("self_refine", "m1", "gold", 0.65, 0.12),
    row("loupe-generic-tools", "m1", "gold", 0.9, 0.01), // an ablation, never the baseline
    row("loupe", "m1", "gold", 0.75, 0.05),
    row("react", "m1", "fb", 0.5, 0.2),
    row("loupe", "m2", "gold", 0.7, 0.06),
  ];

  it("pairs Loupe with the best non-Loupe arm by accuracy", () => {
    const [m1] = summarizeModels(rows);
    const gold = m1!.datasets.find((d) => d.dataset === "gold")!;
    expect(gold.loupe?.arm).toBe("loupe");
    expect(gold.baseline?.arm).toBe("self_refine");
    expect(gold.deltaAccuracy).toBeCloseTo(0.1);
    expect(gold.deltaHallucination).toBeCloseTo(-0.07);
  });

  it("leaves deltas null when a side is missing", () => {
    const [m1, m2] = summarizeModels(rows);
    const fb = m1!.datasets.find((d) => d.dataset === "fb")!;
    expect(fb.loupe).toBeNull();
    expect(fb.deltaAccuracy).toBeNull();
    expect(m2!.datasets[0]!.baseline).toBeNull();
  });

  it("filters by dataset", () => {
    const out = summarizeModels(rows, "fb");
    expect(out.map((m) => m.model)).toEqual(["m1"]);
    expect(out[0]!.datasets.map((d) => d.dataset)).toEqual(["fb"]);
  });
});
