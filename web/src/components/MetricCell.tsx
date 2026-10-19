import type { Metric } from "../api/types";
import { DASH, formatMetric, isRateMetric, lowerIsBetter } from "../lib/format";

/**
 * A bootstrap estimate shown as `mean [lo, hi]` with a tiny interval bar on [0, 1] for rates.
 */
export function MetricCell({ metric, name, best = false }: { metric: Metric | null | undefined; name: string; best?: boolean }) {
  const rate = isRateMetric(name);
  if (!metric || metric.mean === null) return <span className="faint">{DASH}</span>;
  const full = formatMetric(metric, { rate });
  const bracket = full.indexOf(" [");
  const mean = bracket >= 0 ? full.slice(0, bracket) : full;
  const ci = bracket >= 0 ? full.slice(bracket + 1) : "";
  const pct = (v: number | null) => `${Math.max(0, Math.min(1, v ?? 0)) * 100}%`;
  return (
    <span className={`metric${lowerIsBetter(name) ? " lower" : ""}`} title={`${name}: ${full}`}>
      <span className="metric-text num">
        <span className={best ? "best" : undefined}>{mean}</span>
        {ci && <span className="metric-ci">{ci}</span>}
      </span>
      {rate && (
        <span className="metric-bar" aria-hidden="true">
          {metric.lo !== null && metric.hi !== null && (
            <span className="ci" style={{ left: pct(metric.lo), width: `calc(${pct(metric.hi)} - ${pct(metric.lo)})` }} />
          )}
          <span className="mean" style={{ left: `calc(${pct(metric.mean)} - 1px)` }} />
        </span>
      )}
    </span>
  );
}
