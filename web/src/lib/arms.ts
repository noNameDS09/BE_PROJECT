/** Display order and fallback labels for orchestration arms (the API's /config wins when loaded). */
export const ARM_ORDER = ["b0", "rag", "react", "plan_execute", "router", "self_refine", "loupe"] as const;

export const ARM_SHORT: Record<string, string> = {
  b0: "B0",
  rag: "RAG",
  react: "ReAct",
  plan_execute: "Plan-Exec",
  router: "FARE router",
  self_refine: "Self-Refine",
  loupe: "Loupe",
};

export function armShort(arm: string): string {
  return ARM_SHORT[arm] ?? arm;
}

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
