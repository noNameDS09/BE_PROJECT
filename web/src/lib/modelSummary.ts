import type { LeaderboardRow } from "../api/types";
import { isLoupeArm } from "./arms";

/** Loupe's row on one (model, dataset) slice next to the strongest published baseline. */
export interface ModelDatasetSummary {
  model: string;
  dataset: string;
  loupe: LeaderboardRow | null;
  /** The non-Loupe arm with the highest mean accuracy on the same model and dataset. */
  baseline: LeaderboardRow | null;
  /** Loupe minus best baseline, as fractions; null when either side is missing. */
  deltaAccuracy: number | null;
  deltaHallucination: number | null;
}

export interface ModelSummary {
  model: string;
  datasets: ModelDatasetSummary[];
}

function mean(row: LeaderboardRow | null, metric: string): number | null {
  const v = row?.metrics[metric]?.mean;
  return typeof v === "number" ? v : null;
}

function diff(a: number | null, b: number | null): number | null {
  return a === null || b === null ? null : a - b;
}

/**
 * Groups leaderboard rows by model, then dataset. Baselines are the arms that are neither Loupe
 * nor one of its ablations. Models and datasets are sorted by name.
 */
export function summarizeModels(rows: LeaderboardRow[], dataset = ""): ModelSummary[] {
  const byModel = new Map<string, Map<string, LeaderboardRow[]>>();
  for (const r of rows) {
    if (dataset && r.dataset !== dataset) continue;
    const ds = byModel.get(r.model) ?? new Map<string, LeaderboardRow[]>();
    byModel.set(r.model, ds);
    ds.set(r.dataset, [...(ds.get(r.dataset) ?? []), r]);
  }
  return [...byModel.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([model, ds]) => ({
      model,
      datasets: [...ds.entries()]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([name, slice]) => {
          const loupe = slice.find((r) => r.arm === "loupe") ?? null;
          let baseline: LeaderboardRow | null = null;
          for (const r of slice) {
            if (isLoupeArm(r.arm)) continue;
            const acc = mean(r, "accuracy");
            if (acc !== null && (baseline === null || acc > (mean(baseline, "accuracy") ?? -1))) baseline = r;
          }
          return {
            model,
            dataset: name,
            loupe,
            baseline,
            deltaAccuracy: diff(mean(loupe, "accuracy"), mean(baseline, "accuracy")),
            deltaHallucination: diff(mean(loupe, "hallucination_rate"), mean(baseline, "hallucination_rate")),
          };
        }),
    }));
}
