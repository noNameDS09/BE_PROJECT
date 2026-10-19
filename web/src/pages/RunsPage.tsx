import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { Answer, ResultRow } from "../api/types";
import { AnswerView } from "../components/AnswerView";
import { EmptyState, ErrorBanner, SkeletonTable } from "../components/Feedback";
import { FilterBar, FilterSelect } from "../components/Filters";
import { Icon } from "../components/Icon";
import { CorrectBadge } from "../components/RunCard";
import { armColor } from "../lib/arms";
import { DASH, formatCost, formatDate, formatLatency, formatPct, formatTokens, prettyJson, truncate } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { armLabel, useConfig } from "../lib/useConfig";

/** A full Answer stored in ResultRow.meta.answer (optional UI extension), else null. */
export function storedAnswer(row: ResultRow): Answer | null {
  const a = row.meta?.answer;
  if (!a || typeof a !== "object") return null;
  const o = a as Partial<Answer>;
  if (typeof o.text !== "string") return null;
  return {
    text: o.text,
    claims: Array.isArray(o.claims) ? o.claims : [],
    charts: Array.isArray(o.charts) ? o.charts : [],
    abstained: Boolean(o.abstained),
    trace: Array.isArray(o.trace) ? o.trace : [],
    evidence: Array.isArray(o.evidence) ? o.evidence : [],
  };
}

function RunDetail({ row, onClose }: { row: ResultRow; onClose: () => void }) {
  const { config } = useConfig();
  const full = storedAnswer(row);
  const answer: Answer = full ?? { text: row.answer, claims: [], charts: [], abstained: row.abstained, trace: [], evidence: [] };
  const { meta, ...rest } = row;
  const { answer: _omit, ...metaRest } = (meta ?? {}) as Record<string, unknown>;
  void _omit;
  return (
    <section className="card detail">
      <div className="card-head">
        <div className="run-title">
          <span className="arm-swatch" style={{ background: armColor(row.arm) }} />
          <strong>{armLabel(config, row.arm)}</strong>
          <span className="tag">{row.model}</span>
          <CorrectBadge correct={row.correct} />
          {row.abstained && <span className="badge warn">abstained</span>}
        </div>
        <button className="btn ghost sm icon" onClick={onClose} aria-label="Close run">
          <Icon name="close" size={14} />
        </button>
      </div>
      <div className="card-pad stack">
        <div className="small muted mono" style={{ overflowWrap: "anywhere" }}>
          {row.item_id} · {row.run_id} · {formatDate(row.created_at)}
        </div>
        {row.error ? (
          <ErrorBanner title="This run failed" error={new Error(row.error)} />
        ) : (
          <>
            {!full && (
              <div className="small faint">Only the answer text was stored for this run (no claims, evidence or trace).</div>
            )}
            <AnswerView answer={answer} />
          </>
        )}
        <details className="collapsible">
          <summary>
            <Icon name="chevron" size={12} className="chev" /> Result row
          </summary>
          <pre className="json">{prettyJson({ ...rest, answer: truncate(rest.answer, 200), meta: metaRest })}</pre>
        </details>
      </div>
    </section>
  );
}

export function RunsPage() {
  const { config } = useConfig();
  const [params, setParams] = useSearchParams();
  const filters = {
    dataset: params.get("dataset") ?? "",
    arm: params.get("arm") ?? "",
    model: params.get("model") ?? "",
    correct: (params.get("correct") ?? "") as "" | "true" | "false",
    limit: Number(params.get("limit") ?? 100) || 100,
  };
  const setFilter = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    setParams(next, { replace: true });
  };
  const { data, error, loading, reload } = useAsync(
    () => api.runs(filters),
    [filters.dataset, filters.arm, filters.model, filters.correct, filters.limit],
  );
  const [selected, setSelected] = useState<ResultRow | null>(null);
  const rows = data?.rows ?? [];

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Runs</h1>
          <p>Every stored (item, arm, model) run. Filter to drill down, e.g. B0 with correct = false shows its hallucinations.</p>
        </div>
      </div>
      <FilterBar>
        <FilterSelect label="Dataset" value={filters.dataset} onChange={(v) => setFilter("dataset", v)} options={(config?.datasets ?? []).map((d) => ({ value: d.name, label: d.name }))} />
        <FilterSelect label="Arm" value={filters.arm} onChange={(v) => setFilter("arm", v)} options={(config?.arms ?? []).map((a) => ({ value: a.name, label: a.label }))} />
        <FilterSelect label="Model" value={filters.model} onChange={(v) => setFilter("model", v)} options={(config?.models ?? []).map((m) => ({ value: m.alias, label: m.alias }))} />
        <FilterSelect
          label="Correct"
          value={filters.correct}
          onChange={(v) => setFilter("correct", v)}
          allLabel="Any"
          options={[
            { value: "true", label: "Correct" },
            { value: "false", label: "Incorrect" },
          ]}
        />
        <FilterSelect
          label="Limit"
          value={String(filters.limit)}
          onChange={(v) => setFilter("limit", v === "100" ? "" : v)}
          allLabel={null}
          options={["50", "100", "200", "500"].map((v) => ({ value: v, label: v }))}
        />
      </FilterBar>

      {error ? (
        <ErrorBanner title="Could not load runs" error={error} onRetry={reload} />
      ) : (
        <div className={selected ? "split" : undefined}>
          <section className="card" style={{ minWidth: 0 }}>
            {loading && !data ? (
              <SkeletonTable rows={10} cols={7} />
            ) : rows.length === 0 ? (
              <EmptyState icon="list" title="No runs match these filters">
                Runs appear here once the eval runner has stored results.
              </EmptyState>
            ) : (
              <div className="table-wrap" style={{ opacity: loading ? 0.6 : 1 }}>
                <table className="data">
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>Arm</th>
                      <th>Model</th>
                      <th>Correct</th>
                      <th className="r opt">Supported</th>
                      <th>Flags</th>
                      <th className="r opt">Tokens</th>
                      <th className="r opt">Latency</th>
                      <th className="r opt">Cost</th>
                      <th className="opt">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.run_id} className={`clickable${selected?.run_id === r.run_id ? " selected" : ""}`} onClick={() => setSelected(r)}>
                        <td style={{ minWidth: 220 }}>
                          <div className="mono small">{r.item_id}</div>
                          <div className="small faint">{r.error ? <span style={{ color: "var(--bad)" }}>{truncate(r.error, 80)}</span> : truncate(r.answer, 80)}</div>
                        </td>
                        <td className="nowrap">
                          <span className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
                            <span className="arm-swatch" style={{ background: armColor(r.arm) }} />
                            {armLabel(config, r.arm)}
                          </span>
                        </td>
                        <td className="mono small nowrap">{r.model}</td>
                        <td>
                          <CorrectBadge correct={r.correct} />
                        </td>
                        <td className="r num opt">{r.supported_rate === null ? DASH : formatPct(r.supported_rate, 0)}</td>
                        <td className="nowrap">
                          <span className="row" style={{ gap: 4, flexWrap: "nowrap" }}>
                            {r.hallucinated && <span className="badge bad">hallucinated</span>}
                            {r.abstained && <span className="badge warn">abstained</span>}
                            {r.error && <span className="badge bad">error</span>}
                          </span>
                        </td>
                        <td className="r num opt">{formatTokens(r.tokens)}</td>
                        <td className="r num nowrap opt">{formatLatency(r.latency_ms)}</td>
                        <td className="r num opt">{formatCost(r.cost_usd)}</td>
                        <td className="small faint nowrap num opt">{formatDate(r.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {rows.length > 0 && (
              <div className="pager">
                <span>
                  {rows.length} rows{rows.length === filters.limit ? " (limit reached; raise the limit or filter)" : ""}
                </span>
              </div>
            )}
          </section>
          {selected && <RunDetail row={selected} onClose={() => setSelected(null)} />}
        </div>
      )}
    </div>
  );
}
