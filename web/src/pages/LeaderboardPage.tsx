import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { LeaderboardRow, PlotlyFigure } from "../api/types";
import { EmptyState, ErrorBanner, SkeletonTable } from "../components/Feedback";
import { FilterBar, FilterSelect, SortHeader } from "../components/Filters";
import { MetricCell } from "../components/MetricCell";
import { PlotlyChart } from "../components/PlotlyChart";
import { armColor, armRank } from "../lib/arms";
import { formatCost, formatLatency, formatTokens, lowerIsBetter } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { armLabel, useConfig } from "../lib/useConfig";

const METRICS = [
  { key: "accuracy", label: "Accuracy" },
  { key: "hallucination_rate", label: "Hallucination" },
  { key: "supported_rate", label: "Supported" },
  { key: "abstain_rate", label: "Abstain" },
] as const;

type SortKey = "arm" | "model" | "dataset" | "n" | "tokens" | "latency_ms" | "cost_usd" | (typeof METRICS)[number]["key"];

function sortValue(row: LeaderboardRow, key: SortKey): number | string {
  switch (key) {
    case "arm":
      return armRank(row.arm);
    case "model":
    case "dataset":
      return row[key];
    case "n":
    case "tokens":
    case "latency_ms":
    case "cost_usd":
      return row[key];
    default:
      return row.metrics[key]?.mean ?? -1;
  }
}

/** Grouped bars (accuracy, hallucination) per arm with CI error bars. */
export function leaderboardFigure(rows: LeaderboardRow[], label: (arm: string) => string): PlotlyFigure {
  const sorted = [...rows].sort((a, b) => armRank(a.arm) - armRank(b.arm));
  const x = sorted.map((r) => label(r.arm));
  const trace = (key: "accuracy" | "hallucination_rate", name: string, color: string) => {
    const m = sorted.map((r) => r.metrics[key]);
    return {
      type: "bar",
      name,
      x,
      y: m.map((v) => (v?.mean ?? 0) * 100),
      marker: { color },
      error_y: {
        type: "data",
        symmetric: false,
        array: m.map((v) => ((v?.hi ?? v?.mean ?? 0) - (v?.mean ?? 0)) * 100),
        arrayminus: m.map((v) => ((v?.mean ?? 0) - (v?.lo ?? v?.mean ?? 0)) * 100),
        thickness: 1.2,
        width: 4,
      },
      hovertemplate: `%{x}<br>${name}: %{y:.1f}%<extra></extra>`,
    };
  };
  return {
    data: [trace("accuracy", "Accuracy", "#6366f1"), trace("hallucination_rate", "Hallucination rate", "#ef4444")],
    layout: {
      barmode: "group",
      bargap: 0.25,
      height: 300,
      yaxis: { title: { text: "%" }, range: [0, 100], ticksuffix: "" },
      margin: { t: 16, r: 16, b: 60, l: 48 },
      legend: { orientation: "h", y: 1.12, x: 0 },
    },
  };
}

export function LeaderboardPage() {
  const { config } = useConfig();
  const [params, setParams] = useSearchParams();
  const filters = {
    dataset: params.get("dataset") ?? "",
    split: (params.get("split") ?? "") as "" | "dev" | "test",
    model: params.get("model") ?? "",
    arm: params.get("arm") ?? "",
  };
  const setFilter = (k: keyof typeof filters, v: string) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    setParams(next, { replace: true });
  };

  const { data, error, loading, reload } = useAsync(
    () => api.leaderboard(filters),
    [filters.dataset, filters.split, filters.model, filters.arm],
  );
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({ key: "accuracy", dir: "desc" });
  const onSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: key === "hallucination_rate" || key === "arm" || key === "model" || key === "dataset" ? "asc" : "desc" }));

  const rows = useMemo(() => {
    const r = [...(data?.rows ?? [])];
    r.sort((a, b) => {
      const va = sortValue(a, sort.key);
      const vb = sortValue(b, sort.key);
      const c = typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb));
      return sort.dir === "asc" ? c : -c;
    });
    return r;
  }, [data, sort]);

  // The chart shows one (model, dataset) slice; default to the filters or the first row.
  const [chartModel, setChartModel] = useState("");
  const [chartDataset, setChartDataset] = useState("");
  const models = [...new Set((data?.rows ?? []).map((r) => r.model))];
  const datasets = [...new Set((data?.rows ?? []).map((r) => r.dataset))];
  const cm = filters.model || (models.includes(chartModel) ? chartModel : models[0]) || "";
  const cd = filters.dataset || (datasets.includes(chartDataset) ? chartDataset : datasets[0]) || "";
  const chartRows = useMemo(() => (data?.rows ?? []).filter((r) => r.model === cm && r.dataset === cd), [data, cm, cd]);
  const figure = useMemo(() => leaderboardFigure(chartRows, (a) => armLabel(config, a)), [chartRows, config]);

  // Best value per metric among visible rows (bold).
  const best = useMemo(() => {
    const out: Record<string, number> = {};
    for (const m of METRICS) {
      const vals = rows.map((r) => r.metrics[m.key]?.mean).filter((v): v is number => typeof v === "number");
      if (vals.length) out[m.key] = lowerIsBetter(m.key) ? Math.min(...vals) : Math.max(...vals);
    }
    return out;
  }, [rows]);

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Leaderboard</h1>
          <p>Scores per arm and model with 95% cluster-bootstrap intervals, shown as mean [lo, hi].</p>
        </div>
      </div>

      <FilterBar>
        <FilterSelect label="Dataset" value={filters.dataset} onChange={(v) => setFilter("dataset", v)} options={(config?.datasets ?? []).map((d) => ({ value: d.name, label: d.name }))} />
        <FilterSelect label="Split" value={filters.split} onChange={(v) => setFilter("split", v)} options={[{ value: "dev", label: "dev" }, { value: "test", label: "test" }]} />
        <FilterSelect label="Model" value={filters.model} onChange={(v) => setFilter("model", v)} options={(config?.models ?? []).map((m) => ({ value: m.alias, label: m.alias }))} />
        <FilterSelect label="Arm" value={filters.arm} onChange={(v) => setFilter("arm", v)} options={(config?.arms ?? []).map((a) => ({ value: a.name, label: a.label }))} />
      </FilterBar>

      {error && <ErrorBanner title="Could not load the leaderboard" error={error} onRetry={reload} />}

      {!error && (
        <div className="stack">
          <section className="card">
            <div className="card-head">
              <h2>Accuracy and hallucination by arm</h2>
              <div className="row small">
                {!filters.model && models.length > 1 && (
                  <select className="select" aria-label="Chart model" value={cm} onChange={(e) => setChartModel(e.target.value)} style={{ height: 28 }}>
                    {models.map((m) => (
                      <option key={m}>{m}</option>
                    ))}
                  </select>
                )}
                {!filters.dataset && datasets.length > 1 && (
                  <select className="select" aria-label="Chart dataset" value={cd} onChange={(e) => setChartDataset(e.target.value)} style={{ height: 28 }}>
                    {datasets.map((d) => (
                      <option key={d}>{d}</option>
                    ))}
                  </select>
                )}
                {(filters.model || models.length <= 1) && (filters.dataset || datasets.length <= 1) && (
                  <span className="faint">
                    {cm} · {cd}
                  </span>
                )}
              </div>
            </div>
            <div className="card-pad">
              {loading && !data ? (
                <SkeletonTable rows={4} cols={1} />
              ) : chartRows.length ? (
                <PlotlyChart figure={figure} />
              ) : (
                <EmptyState icon="stages" title="No rows for this slice" />
              )}
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <h2>All rows</h2>
              <span className="small faint">{rows.length} rows · click a header to sort</span>
            </div>
            {loading && !data ? (
              <SkeletonTable rows={8} cols={7} />
            ) : rows.length === 0 ? (
              <EmptyState title="No results for these filters">Results appear here once the eval runner has written them.</EmptyState>
            ) : (
              <div className="table-wrap" style={{ opacity: loading ? 0.6 : 1 }}>
                <table className="data">
                  <thead>
                    <tr>
                      <SortHeader label="Arm" k="arm" sort={sort} onSort={onSort} />
                      <SortHeader label="Model" k="model" sort={sort} onSort={onSort} />
                      <SortHeader label="Dataset" k="dataset" sort={sort} onSort={onSort} />
                      <SortHeader label="n" k="n" sort={sort} onSort={onSort} right />
                      {METRICS.map((m) => (
                        <SortHeader key={m.key} label={m.label} k={m.key} sort={sort} onSort={onSort} />
                      ))}
                      <SortHeader label="Tokens" k="tokens" sort={sort} onSort={onSort} right />
                      <SortHeader label="Latency" k="latency_ms" sort={sort} onSort={onSort} right />
                      <SortHeader label="Cost" k="cost_usd" sort={sort} onSort={onSort} right />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={`${r.arm}|${r.model}|${r.dataset}`}>
                        <td className="nowrap">
                          <span className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
                            <span className="arm-swatch" style={{ background: armColor(r.arm) }} />
                            {armLabel(config, r.arm)}
                          </span>
                        </td>
                        <td className="mono nowrap">{r.model}</td>
                        <td className="nowrap">{r.dataset}</td>
                        <td className="r num">{r.n}</td>
                        {METRICS.map((m) => (
                          <td key={m.key}>
                            <MetricCell metric={r.metrics[m.key]} name={m.key} best={r.metrics[m.key]?.mean === best[m.key]} />
                          </td>
                        ))}
                        <td className="r num">{formatTokens(r.tokens)}</td>
                        <td className="r num nowrap">{formatLatency(r.latency_ms)}</td>
                        <td className="r num">{formatCost(r.cost_usd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
