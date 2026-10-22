import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { LeaderboardRow, ModelInfo, PlotlyFigure } from "../api/types";
import { EmptyState, ErrorBanner, SkeletonTable } from "../components/Feedback";
import { FilterBar, FilterSelect } from "../components/Filters";
import { MetricCell } from "../components/MetricCell";
import { PlotlyChart } from "../components/PlotlyChart";
import { ToolsetBadge } from "../components/ToolsetBadge";
import { METHODS_NOTE, armColor } from "../lib/arms";
import { formatLatency, formatPp, formatTokens } from "../lib/format";
import { summarizeModels, type ModelDatasetSummary } from "../lib/modelSummary";
import { useAsync } from "../lib/useAsync";
import { armLabel, useConfig } from "../lib/useConfig";
import { runsLink } from "./LeaderboardPage";

/** Grouped bars (Loupe accuracy, hallucination) per model on one dataset, with CI error bars. */
export function modelsFigure(rows: LeaderboardRow[]): PlotlyFigure {
  const sorted = [...rows].sort((a, b) => a.model.localeCompare(b.model));
  const x = sorted.map((r) => r.model);
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
      hovertemplate: `%{x}<br>Loupe ${name.toLowerCase()}: %{y:.1f}%<extra></extra>`,
    };
  };
  return {
    data: [trace("accuracy", "Accuracy", "#1b6c80"), trace("hallucination_rate", "Hallucination rate", "#c4242a")],
    layout: {
      barmode: "group",
      bargap: 0.3,
      height: 300,
      yaxis: { title: { text: "%" }, range: [0, 100] },
      xaxis: { type: "category", automargin: true },
      margin: { t: 16, r: 16, b: 60, l: 48 },
      legend: { orientation: "h", y: 1.12, x: 0 },
    },
  };
}

function Delta({ value, lowerIsBetter = false }: { value: number | null; lowerIsBetter?: boolean }) {
  const good = value !== null && (lowerIsBetter ? value < 0 : value > 0);
  const bad = value !== null && (lowerIsBetter ? value > 0 : value < 0);
  return <span style={{ color: good ? "var(--good)" : bad ? "var(--bad)" : undefined }}>{formatPp(value)}</span>;
}

function ModelCard({ model, info, datasets }: { model: string; info: ModelInfo | undefined; datasets: ModelDatasetSummary[] }) {
  const { config } = useConfig();
  const navigate = useNavigate();
  return (
    <section className="card">
      <div className="card-head">
        <div className="run-title">
          <h2>{model}</h2>
          {info && <span className="badge">{info.provider}</span>}
          {info?.model && <span className="tag">{info.model}</span>}
        </div>
        {info && !info.available && <span className="badge warn">no API key</span>}
      </div>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Dataset</th>
              <th className="r">n</th>
              <th>Loupe accuracy</th>
              <th>Hallucination</th>
              <th>Abstain</th>
              <th className="r">Tokens</th>
              <th className="r">Latency</th>
              <th>Best baseline (by accuracy)</th>
              <th className="r">Δ accuracy</th>
              <th className="r">Δ hallucination</th>
            </tr>
          </thead>
          <tbody>
            {datasets.map((d) => {
              const l = d.loupe;
              const b = d.baseline;
              return (
                <tr
                  key={d.dataset}
                  className={l ? "clickable" : undefined}
                  tabIndex={l ? 0 : undefined}
                  title={l ? "Open Loupe's runs on this dataset" : undefined}
                  onClick={l ? () => navigate(runsLink(l)) : undefined}
                  onKeyDown={
                    l
                      ? (e) => {
                          if (e.key === "Enter") navigate(runsLink(l));
                        }
                      : undefined
                  }
                >
                  <td className="nowrap">{d.dataset}</td>
                  {l ? (
                    <>
                      <td className="r num">{l.n}</td>
                      <td>
                        <MetricCell metric={l.metrics.accuracy} name="accuracy" />
                      </td>
                      <td>
                        <MetricCell metric={l.metrics.hallucination_rate} name="hallucination_rate" />
                      </td>
                      <td>
                        <MetricCell metric={l.metrics.abstain_rate} name="abstain_rate" />
                      </td>
                      <td className="r num">{formatTokens(l.tokens)}</td>
                      <td className="r num nowrap">{formatLatency(l.latency_ms)}</td>
                    </>
                  ) : (
                    <td colSpan={6} className="small faint">
                      No Loupe runs on this dataset yet.
                    </td>
                  )}
                  <td>
                    {b ? (
                      <div className="stack" style={{ gap: 2 }}>
                        <span className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
                          <span className="arm-swatch" style={{ background: armColor(b.arm) }} />
                          <span className="nowrap">{armLabel(config, b.arm)}</span>
                          <ToolsetBadge arm={b.arm} />
                        </span>
                        <MetricCell metric={b.metrics.accuracy} name="accuracy" />
                      </div>
                    ) : (
                      <span className="small faint">no baseline runs</span>
                    )}
                  </td>
                  <td className="r num nowrap">
                    <Delta value={d.deltaAccuracy} />
                  </td>
                  <td className="r num nowrap">
                    <Delta value={d.deltaHallucination} lowerIsBetter />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function ModelsPage() {
  const { config } = useConfig();
  const [params, setParams] = useSearchParams();
  const dataset = params.get("dataset") ?? "";
  const setDataset = (v: string) => {
    const next = new URLSearchParams(params);
    if (v) next.set("dataset", v);
    else next.delete("dataset");
    setParams(next, { replace: true });
  };

  // All rows, no filters: the dataset filter is applied here.
  const { data, error, loading, reload } = useAsync(() => api.leaderboard(), []);
  const allRows = useMemo(() => data?.rows ?? [], [data]);
  const summaries = useMemo(() => summarizeModels(allRows, dataset), [allRows, dataset]);

  const datasets = useMemo(() => [...new Set(allRows.map((r) => r.dataset))].sort(), [allRows]);
  const [chartDataset, setChartDataset] = useState("");
  const cd = dataset || (datasets.includes(chartDataset) ? chartDataset : datasets[0]) || "";
  const chartRows = useMemo(() => allRows.filter((r) => r.arm === "loupe" && r.dataset === cd), [allRows, cd]);
  const figure = useMemo(() => modelsFigure(chartRows), [chartRows]);

  const withResults = new Set(allRows.map((r) => r.model));
  const without = (config?.models ?? []).filter((m) => !withResults.has(m.alias)).map((m) => m.alias);
  const datasetOptions = [...new Set([...(config?.datasets ?? []).map((d) => d.name), ...datasets])].map((d) => ({ value: d, label: d }));

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Models</h1>
          <p>How each model performs with Loupe, next to the best baseline arm on the same model and dataset.</p>
          <p className="small">{METHODS_NOTE}</p>
        </div>
      </div>

      <FilterBar>
        <FilterSelect label="Dataset" value={dataset} onChange={setDataset} options={datasetOptions} />
      </FilterBar>

      {error ? (
        <ErrorBanner title="Could not load results" error={error} onRetry={reload} />
      ) : loading && !data ? (
        <div className="card">
          <SkeletonTable rows={6} cols={6} />
        </div>
      ) : allRows.length === 0 ? (
        <div className="card">
          <EmptyState icon="cpu" title="No results yet">
            Each model appears here once the eval runner has stored its runs. Run{" "}
            <code>loupe eval run ... --model &lt;alias&gt;</code> for every model you want to compare, using an alias from{" "}
            <code>configs/models.yaml</code>.
          </EmptyState>
        </div>
      ) : summaries.length === 0 ? (
        <div className="card">
          <EmptyState icon="cpu" title={`No results on ${dataset}`}>
            Pick another dataset, or run <code>loupe eval run ... --model &lt;alias&gt;</code> on this one.
          </EmptyState>
        </div>
      ) : (
        <div className="stack" style={{ opacity: loading ? 0.6 : 1 }}>
          <section className="card">
            <div className="card-head">
              <h2>Loupe accuracy and hallucination by model</h2>
              <div className="row small">
                {!dataset && datasets.length > 1 ? (
                  <select className="select" aria-label="Chart dataset" value={cd} onChange={(e) => setChartDataset(e.target.value)} style={{ height: 28 }}>
                    {datasets.map((d) => (
                      <option key={d}>{d}</option>
                    ))}
                  </select>
                ) : (
                  <span className="faint">{cd}</span>
                )}
              </div>
            </div>
            <div className="card-pad">
              {chartRows.length ? <PlotlyChart figure={figure} /> : <EmptyState icon="stages" title="No Loupe runs on this dataset" />}
            </div>
          </section>

          {summaries.map((s) => (
            <ModelCard key={s.model} model={s.model} info={config?.models.find((m) => m.alias === s.model)} datasets={s.datasets} />
          ))}

          {without.length > 0 && (
            <p className="small faint" style={{ margin: 0 }}>
              No results yet for {without.join(", ")}. Run <code>loupe eval run ... --model &lt;alias&gt;</code> to add one.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
