import { useState } from "react";
import type { TraceStep } from "../api/types";
import { formatCost, formatLatency, formatTokens, prettyJson } from "../lib/format";
import { Icon } from "./Icon";

function Step({ step }: { step: TraceStep }) {
  const [open, setOpen] = useState(false);
  const tokens = step.tokens_in + step.tokens_out;
  return (
    <li className={`trace-step ${step.stage}`}>
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className="trace-stage">{step.stage}</span>
        <span className="trace-name" title={step.name}>
          {step.name}
        </span>
        <span className="trace-stats num">
          {tokens > 0 && (
            <span title={`${step.tokens_in} in / ${step.tokens_out} out`}>{formatTokens(tokens)} tok</span>
          )}
          <span>{formatLatency(step.latency_ms)}</span>
          {step.cost_usd > 0 && <span>{formatCost(step.cost_usd)}</span>}
          <Icon name="chevron" size={12} className="chev" />
        </span>
      </button>
      {open && (
        <div className="trace-io">
          <div>
            <div className="io-label">input</div>
            <pre>{prettyJson(step.input) || "—"}</pre>
          </div>
          <div>
            <div className="io-label">output</div>
            <pre>{prettyJson(step.output) || "—"}</pre>
          </div>
          {step.model && <div className="small faint">model: {step.model}</div>}
        </div>
      )}
    </li>
  );
}

/** One row per model or tool call, in order; click a row for its input/output JSON. */
export function TraceTimeline({ trace }: { trace: TraceStep[] }) {
  if (!trace.length) return <div className="small faint">No trace recorded.</div>;
  return (
    <ol className="trace">
      {trace.map((s, i) => (
        <Step key={i} step={s} />
      ))}
    </ol>
  );
}
