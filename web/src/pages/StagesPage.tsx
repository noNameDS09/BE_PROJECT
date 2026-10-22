import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { PlotlyFigure, StageStep } from "../api/types";
import { EmptyState, ErrorBanner, SkeletonTable } from "../components/Feedback";
import { FilterBar, FilterSelect } from "../components/Filters";
import { MetricCell } from "../components/MetricCell";
import { PlotlyChart } from "../components/PlotlyChart";
import { DASH } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { useConfig } from "../lib/useConfig";

const pp = (v: number | null) => (v === null ? DASH : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)} pp`);

/** Splits steps into the ordered waterfall and the ablation rows. */
export function splitStages(steps: StageStep[]): { waterfall: StageStep[]; ablations: StageStep[] } {
  return {
    waterfall: steps.filter((s) => (s.kind ?? "step") === "step"),
    ablations: steps.filter((s) => s.kind === "ablation"),
  };
}

/** Accuracy waterfall (B0 → Loupe) with the hallucination rate as a line on a second axis. */
export function stagesFigure(waterfall: StageStep[]): PlotlyFigure {
  const acc = waterfall.map((s) => (s.accuracy.mean ?? 0) * 100);
  const deltas = acc.map((v, i) => (i === 0 ? v : v - (acc[i - 1] ?? 0)));
  const labels = waterfall.map((s) => s.label);
  const total = acc[acc.length - 1] ?? 0;
  return {
    data: [
      {
        type: "waterfall",
        name: "Accuracy",
        x: [...labels, "Loupe total"],
        y: [...deltas, 0],
        measure: [...waterfall.map((_, i) => (i === 0 ? "absolute" : "relative")), "total"],
        text: [...deltas.map((d, i) => (i === 0 ? `${d.toFixed(1)}%` : `${d >= 0 ? "+" : ""}${d.toFixed(1)}`)), `${total.toFixed(1)}%`],
        textposition: "outside",
        connector: { line: { color: "rgba(140,140,150,0.5)", width: 1, dash: "dot" } },
        increasing: { marker: { color: "#1e7b4f" } },
        decreasing: { marker: { color: "#c4242a" } },
        totals: { marker: { color: "#1b6c80" } },
        hovertemplate: "%{x}<br>%{text}<extra></extra>",
      },
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Hallucination rate",
        x: labels,
        y: waterfall.map((s) => (s.hallucination_rate.mean ?? 0) * 100),
        yaxis: "y2",
        line: { color: "#a86f0c", width: 2 },
        marker: { size: 6 },
        hovertemplate: "%{x}<br>hallucination %{y:.1f}%<extra></extra>",
      },
    ],
    layout: {
      height: 360,
      showlegend: true,
      legend: { orientation: "h", y: 1.12, x: 0 },
      margin: { t: 24, r: 56, b: 96, l: 52 },
      xaxis: { type: "category", tickangle: -20, automargin: true },
      yaxis: { title: { text: "Accuracy (%)" }, range: [0, 100] },
      yaxis2: { title: { text: "Hallucination (%)" }, overlaying: "y", side: "right", range: [0, 100], showgrid: false },
    },
  };
}

export function StagesPage() {
  const { config } = useConfig();
  const [params, setParams] = useSearchParams();
  const dataset = params.get("dataset") ?? "";
  const model = params.get("model") ?? "";
  const setFilter = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    setParams(next, { replace: true });
  };
  const { data, error, loading, reload } = useAsync(() => api.stages({ dataset, model }), [dataset, model]);
  const { waterfall, ablations } = useMemo(() => splitStages(data?.steps ?? []), [data]);
  const figure = useMemo(() => stagesFigure(waterfall), [waterfall]);
  const loupe = waterfall[waterfall.length - 1];

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Stages</h1>
          <p>What each stage adds on the way from the closed-book baseline to Loupe, plus ablations of the final system.</p>
        </div>
      </div>
      <FilterBar>
        <FilterSelect label="Dataset" value={dataset} onChange={(v) => setFilter("dataset", v)} allLabel="Default" options={(config?.datasets ?? []).map((d) => ({ value: d.name, label: d.name }))} />
        <FilterSelect label="Model" value={model} onChange={(v) => setFilter("model", v)} allLabel="Default" options={(config?.models ?? []).map((m) => ({ value: m.alias, label: m.alias }))} />
      </FilterBar>

      {error ? (
        <ErrorBanner title="Could not load stage results" error={error} onRetry={reload} />
      ) : loading && !data ? (
        <div className="card">
          <SkeletonTable rows={8} cols={5} />
        </div>
      ) : !data || data.steps.length === 0 ? (
        <div className="card">
          <EmptyState icon="stages" title="No stage results yet" />
        </div>
      ) : (
        <div className="stack" style={{ opacity: loading ? 0.6 : 1 }}>
          <section className="card">
            <div className="card-head">
              <h2>Accuracy waterfall</h2>
              <span className="small faint">bars: accuracy change per stage · line: hallucination rate</span>
            </div>
            <div className="card-pad">{waterfall.length > 0 ? <PlotlyChart figure={figure} /> : <EmptyState title="No waterfall steps" />}</div>
          </section>
          <section className="card">
            <div className="card-head">
              <h2>Steps</h2>
            </div>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Step</th>
                    <th>Arm</th>
                    <th>Accuracy</th>
                    <th className="r">Δ accuracy</th>
                    <th>Hallucination</th>
                    <th className="r">Δ hallucination</th>
                  </tr>
                </thead>
                <tbody>
                  {waterfall.map((s, i) => {
                    const prev = waterfall[i - 1];
                    const dAcc = prev && s.accuracy.mean !== null && prev.accuracy.mean !== null ? s.accuracy.mean - prev.accuracy.mean : null;
                    const dHal =
                      prev && s.hallucination_rate.mean !== null && prev.hallucination_rate.mean !== null
                        ? s.hallucination_rate.mean - prev.hallucination_rate.mean
                        : null;
                    return (
                      <tr key={s.arm + s.label}>
                        <td>{s.label}</td>
                        <td className="mono small">{s.arm}</td>
                        <td>
                          <MetricCell metric={s.accuracy} name="accuracy" />
                        </td>
                        <td className="r num" style={{ color: dAcc === null ? undefined : dAcc >= 0 ? "var(--good)" : "var(--bad)" }}>
                          {pp(dAcc)}
                        </td>
                        <td>
                          <MetricCell metric={s.hallucination_rate} name="hallucination_rate" />
                        </td>
                        <td className="r num" style={{ color: dHal === null ? undefined : dHal <= 0 ? "var(--good)" : "var(--bad)" }}>
                          {pp(dHal)}
                        </td>
                      </tr>
                    );
                  })}
                  {ablations.length > 0 && (
                    <tr className="group-sep">
                      <td colSpan={6}>Ablations (Δ vs. Loupe)</td>
                    </tr>
                  )}
                  {ablations.map((s) => {
                    const dAcc = loupe && s.accuracy.mean !== null && loupe.accuracy.mean !== null ? s.accuracy.mean - loupe.accuracy.mean : null;
                    const dHal =
                      loupe && s.hallucination_rate.mean !== null && loupe.hallucination_rate.mean !== null
                        ? s.hallucination_rate.mean - loupe.hallucination_rate.mean
                        : null;
                    return (
                      <tr key={s.arm + s.label}>
                        <td>{s.label}</td>
                        <td className="mono small">{s.arm}</td>
                        <td>
                          <MetricCell metric={s.accuracy} name="accuracy" />
                        </td>
                        <td className="r num" style={{ color: dAcc === null ? undefined : dAcc >= 0 ? "var(--good)" : "var(--bad)" }}>
                          {pp(dAcc)}
                        </td>
                        <td>
                          <MetricCell metric={s.hallucination_rate} name="hallucination_rate" />
                        </td>
                        <td className="r num" style={{ color: dHal === null ? undefined : dHal <= 0 ? "var(--good)" : "var(--bad)" }}>
                          {pp(dHal)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
