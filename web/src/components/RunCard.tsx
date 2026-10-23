import type { RunResult } from "../api/types";
import { armColor } from "../lib/arms";
import { claimSummary } from "../lib/citations";
import { correctness, formatCost, formatLatency, formatTokens } from "../lib/format";
import { armLabel, useConfig } from "../lib/useConfig";
import { AnswerView } from "./AnswerView";
import { Icon } from "./Icon";
import { ToolsetBadge } from "./ToolsetBadge";

export function CorrectBadge({ correct }: { correct: number | null | undefined }) {
  const c = correctness(correct);
  const score = correct !== null && correct !== undefined && correct > 0 && correct < 1 ? ` ${correct.toFixed(2)}` : "";
  if (c === "correct") return <span className="badge good">correct</span>;
  if (c === "partial") return <span className="badge warn">partial{score}</span>;
  if (c === "incorrect") return <span className="badge bad">incorrect{score}</span>;
  return <span className="badge">ungraded</span>;
}

/** One column of a comparison: header strip (cost, verdicts, gold) and the answer. */
export function RunCard({ result }: { result: RunResult }) {
  const { config } = useConfig();
  const answer = result.answer; // null when the run failed (result.error explains why)
  const s = claimSummary(answer?.claims ?? []);
  return (
    <article className="card run-col" aria-label={`${result.arm} · ${result.model}`}>
      <header className="run-col-head">
        <div className="run-title">
          <span className="arm-swatch" style={{ background: armColor(result.arm) }} />
          <strong>{armLabel(config, result.arm)}</strong>
          <ToolsetBadge arm={result.arm} />
          <span className="tag">{result.model}</span>
          <span className="spacer" />
          {answer?.abstained && <span className="badge warn">abstained</span>}
          {result.error && <span className="badge bad">error</span>}
        </div>
        <div className="stats-strip num">
          <span>
            <b>{formatTokens(result.tokens)}</b> tokens
          </span>
          <span>
            <b>{formatLatency(result.latency_ms)}</b>
          </span>
          <span>
            <b>{formatCost(result.cost_usd)}</b>
          </span>
          {s.supported + s.unsupported + s.unchecked > 0 && (
            <span title="supported / unsupported / unchecked claims">
              claims <b style={{ color: "var(--good)" }}>{s.supported}</b>/<b style={{ color: "var(--bad)" }}>{s.unsupported}</b>/
              <b className="faint">{s.unchecked}</b>
            </span>
          )}
        </div>
      </header>
      {result.gold && (
        <div className="gold-strip">
          <span className="label">Gold</span>
          <span className="gold-text" title={result.gold.answer}>
            {result.gold.answer}
          </span>
          <CorrectBadge correct={result.gold.correct} />
        </div>
      )}
      {result.error || !answer ? (
        <div className="banner error-card" role="alert">
          <Icon name="alert" />
          <div className="banner-body">
            <strong>This configuration failed</strong>
            <div className="small muted mono">{result.error ?? "No answer was returned."}</div>
          </div>
        </div>
      ) : (
        <div className="run-body">
          <AnswerView answer={answer} />
        </div>
      )}
      <div className="small faint mono" style={{ padding: "0 14px 10px" }}>
        {result.run_id}
      </div>
    </article>
  );
}
