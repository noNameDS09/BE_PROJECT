import type { Toolset } from "../api/types";

/** Display order and fallback labels for orchestration arms (the API's /config wins when loaded). */
export const ARM_ORDER = [
  "b0",
  "rag",
  "react",
  "plan_execute",
  "router",
  "self_refine",
  "loupe",
  "loupe-generic-tools",
  "loupe-no-router",
  "loupe-no-planner",
  "loupe-no-verifier",
  "loupe-no-critic",
  "loupe-no-abstain",
] as const;

export const ARM_SHORT: Record<string, string> = {
  b0: "B0",
  rag: "RAG",
  react: "ReAct",
  plan_execute: "Plan-Exec",
  router: "FARE router",
  self_refine: "Self-Refine",
  loupe: "Loupe",
  "loupe-generic-tools": "Loupe − harness",
  "loupe-no-router": "Loupe − router",
  "loupe-no-planner": "Loupe − planner",
  "loupe-no-verifier": "Loupe − verifier",
  "loupe-no-critic": "Loupe − critic",
  "loupe-no-abstain": "Loupe − abstain",
};

export function armShort(arm: string): string {
  return ARM_SHORT[arm] ?? arm;
}

/** Loupe itself or one of its ablations ("loupe-no-router", "loupe-generic-tools", …). */
export function isLoupeArm(arm: string): boolean {
  return arm === "loupe" || arm.startsWith("loupe-");
}

/** Short labels for ArmInfo.toolset. */
export const TOOLSET_LABEL: Record<Toolset, string> = {
  harness: "Loupe harness",
  generic: "generic tools",
  none: "no tools",
};

/** How the comparison is set up (decision D21); shown wherever results are compared. */
export const METHODS_NOTE =
  "Baselines run as published with generic tools (filing search, calculator). Loupe adds our financial tool harness. " +
  "The 'Loupe minus harness' ablation isolates the harness's effect.";

export function armRank(arm: string): number {
  const i = (ARM_ORDER as readonly string[]).indexOf(arm);
  return i < 0 ? ARM_ORDER.length : i;
}

/**
 * Chart colours per arm. Ordered from neutral (baselines) to the accent (Loupe), so the
 * eye lands on our arm; values are tuned to read on both light and dark backgrounds.
 */
export const ARM_COLORS: Record<string, string> = {
  b0: "#9ca3af",
  rag: "#5b9bd5",
  react: "#2f70bb",
  plan_execute: "#1b6c80",
  router: "#a86f0c",
  self_refine: "#c4242a",
  loupe: "#1b6c80",
};

export function armColor(arm: string): string {
  return ARM_COLORS[arm] ?? "#94a3b8";
}
