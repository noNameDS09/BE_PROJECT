import type { ArmInfo } from "../api/types";
import { TOOLSET_LABEL } from "../lib/arms";
import { useConfig } from "../lib/useConfig";

/** The tooltip for an arm's toolset: its label and the tools it may call. */
export function toolsetTitle(info: Pick<ArmInfo, "toolset" | "tools">): string {
  const label = TOOLSET_LABEL[info.toolset] ?? info.toolset;
  return info.tools.length ? `${label}: ${info.tools.join(", ")}` : `${label}: this arm calls no tools`;
}

/**
 * A small badge saying which tools an arm may call (Loupe harness, generic tools, no tools).
 * Renders nothing when /config has not loaded or does not describe the arm.
 */
export function ToolsetBadge({ arm }: { arm: string }) {
  const { config } = useConfig();
  const info = config?.arms.find((a) => a.name === arm);
  if (!info?.toolset) return null;
  return (
    <span className={`badge toolset${info.toolset === "harness" ? " accent" : ""}`} title={toolsetTitle({ toolset: info.toolset, tools: info.tools ?? [] })}>
      {TOOLSET_LABEL[info.toolset] ?? info.toolset}
    </span>
  );
}
