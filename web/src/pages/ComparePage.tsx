import { useEffect, useState, type CSSProperties } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { CompareRequest, ConfigResponse, EvalItem, RunConfigPick, RunResult } from "../api/types";
import { ConfigPicker } from "../components/ConfigPicker";
import { DemoGrid } from "../components/DemoQuestions";
import { EmptyState, ErrorBanner, InfoBanner, Skeleton, SkeletonLines, Spinner } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { RunCard } from "../components/RunCard";
import { ToolsetBadge } from "../components/ToolsetBadge";
import { armColor } from "../lib/arms";
import { DEMO_ARMS, datasetOf, findDemo, type DemoQuestion } from "../lib/examples";
import { truncate } from "../lib/format";
import { isOpenRouterAlias } from "../lib/modelPicker";
import { useAsync, useDebounced } from "../lib/useAsync";
import { armLabel, useConfig } from "../lib/useConfig";

type Mode = "question" | "item";

const DEFAULT_CONFIGS: RunConfigPick[] = [
  { arm: "b0", model: "nim-nemotron-ultra" },
  { arm: "loupe", model: "nim-nemotron-ultra" },
];

/** Model for demo runs when no config row has one yet. */
const DEMO_FALLBACK_MODEL = "nim-nemotron-ultra";

/** Keeps the default configs valid against what /config actually offers (OpenRouter aliases are always accepted). */
function sanitize(configs: RunConfigPick[], config: ConfigResponse): RunConfigPick[] {
  const arms = new Set(config.arms.map((a) => a.name));
  const models = new Set(config.models.map((m) => m.alias));
  const fallbackModel = config.models.find((m) => m.available)?.alias ?? config.models[0]?.alias ?? "";
  return configs.map((c) => ({
    arm: arms.has(c.arm) ? c.arm : (config.arms[0]?.name ?? c.arm),
    model: models.has(c.model) || isOpenRouterAlias(c.model) ? c.model : fallbackModel,
  }));
}

function ItemPicker({
  config,
  dataset,
  onDataset,
  selected,
  onSelect,
}: {
  config: ConfigResponse;
  dataset: string;
  onDataset: (d: string) => void;
  selected: EvalItem | null;
  onSelect: (item: EvalItem) => void;
}) {
  const [q, setQ] = useState("");
  const query = useDebounced(q, 250);
  const { data, error, loading, reload } = useAsync(() => api.datasetItems(dataset, { q: query, limit: 50 }), [dataset, query], Boolean(dataset));

  return (
    <div className="item-picker">
      <div className="row" style={{ flexWrap: "nowrap" }}>
        <select className="select" aria-label="Dataset" value={dataset} onChange={(e) => onDataset(e.target.value)} style={{ flex: "0 0 auto", maxWidth: "45%" }}>
          {config.datasets.map((d) => (
            <option key={d.name} value={d.name}>
              {d.name} ({d.items})
            </option>
          ))}
        </select>
        <input
          className="input"
          type="search"
          placeholder="Search questions, ids or tickers…"
          aria-label="Search items"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ flex: 1 }}
        />
      </div>
      {error ? (
        <ErrorBanner title="Could not load items" error={error} onRetry={reload} />
      ) : (
        <div className="item-list" aria-busy={loading}>
          {loading && !data ? (
            <div style={{ padding: 10 }}>
              <SkeletonLines lines={5} />
            </div>
          ) : data && data.items.length === 0 ? (
            <EmptyState icon="search" title="No matching items">
              Try another search or dataset.
            </EmptyState>
          ) : (
            data?.items.map((item) => (
              <button
                key={item.item_id}
                className={`item-row${selected?.item_id === item.item_id ? " on" : ""}`}
                onClick={() => onSelect(item)}
              >
                <div className="q">{item.question}</div>
                <div className="meta">
                  <span className="mono">{item.item_id}</span>
                  <span>{item.kind}</span>
                  {item.companies.length > 0 && <span>{item.companies.join(", ")}</span>}
                  {item.split && <span>{item.split}</span>}
                </div>
              </button>
            ))
          )}
        </div>
      )}
      {data && data.total > data.items.length && (
        <div className="small faint">
          Showing {data.items.length} of {data.total}; refine the search to narrow down.
        </div>
      )}
    </div>
  );
}

export function ComparePage() {
  const { config, error: configError, retry } = useConfig();
  const [params, setParams] = useSearchParams();
  const itemParam = params.get("item");

  const [mode, setMode] = useState<Mode>(itemParam ? "item" : "question");
  const [question, setQuestion] = useState("");
  const [dataset, setDataset] = useState(itemParam ? datasetOf(itemParam) : "");
  const [selected, setSelected] = useState<EvalItem | null>(null);
  const [configs, setConfigs] = useState<RunConfigPick[]>(DEFAULT_CONFIGS);
  const [results, setResults] = useState<RunResult[] | null>(null);
  const [ranFor, setRanFor] = useState<string>("");
  const [running, setRunning] = useState<RunConfigPick[] | null>(null);
  const [runningFor, setRunningFor] = useState("");
  const [runError, setRunError] = useState<unknown>(null);

  useEffect(() => {
    if (config) {
      setConfigs((c) => sanitize(c, config));
      setDataset((d) => d || config.datasets[0]?.name || "");
    }
  }, [config]);

  // Preselect an item passed as ?item=<dataset>:<id> (e.g. from the Datasets page).
  useEffect(() => {
    if (!itemParam || selected?.item_id === itemParam) return;
    let live = true;
    setMode("item");
    api
      .datasetItem(datasetOf(itemParam), itemParam)
      .then((item) => {
        if (!live) return;
        setSelected(item);
        setDataset(item.dataset);
      })
      .catch((e: unknown) => live && setRunError(e));
    return () => {
      live = false;
    };
  }, [itemParam, selected?.item_id]);

  const selectItem = (item: EvalItem) => {
    setSelected(item);
    setParams({ item: item.item_id }, { replace: true });
  };

  const switchMode = (m: Mode) => {
    setMode(m);
    if (m === "question" && itemParam) setParams({}, { replace: true });
    if (m === "item" && selected) setParams({ item: selected.item_id }, { replace: true });
  };

  const ready = configs.length > 0 && (mode === "question" ? question.trim().length > 0 : selected !== null);

  /** Runs the current setup, or `demo` (a free question with its own configs) when given. */
  async function run(demo?: { question: string; configs: RunConfigPick[] }) {
    if (running || (!demo && !ready)) return;
    const runConfigs = demo?.configs ?? configs;
    const body: CompareRequest = demo
      ? { question: demo.question, item_id: null, configs: runConfigs }
      : mode === "question"
        ? { question: question.trim(), item_id: null, configs }
        : { question: null, item_id: (selected as EvalItem).item_id, configs };
    const askedFor = body.question ?? (selected as EvalItem).question;
    setRunning(runConfigs);
    setRunningFor(askedFor);
    setRunError(null);
    try {
      const res = await api.compare(body);
      setResults(res.results);
      setRanFor(askedFor);
    } catch (e) {
      setRunError(e);
    } finally {
      setRunning(null);
    }
  }

  /** Fills the question, sets B0 / ReAct / Loupe on the first row's model, and runs at once. */
  function runDemo(demo: DemoQuestion) {
    if (running) return;
    const model = configs[0]?.model || DEMO_FALLBACK_MODEL;
    const picks = DEMO_ARMS.map((arm) => ({ arm, model }));
    const next = config ? sanitize(picks, config) : picks;
    switchMode("question");
    setQuestion(demo.question);
    setConfigs(next);
    void run({ question: demo.question, configs: next });
  }

  if (configError) return <ErrorBanner title="Could not load /api/config" error={configError} onRetry={retry} />;

  const cols = running?.length ?? results?.length ?? 2;
  const activeDemo = mode === "question" ? findDemo(question) : undefined;
  const shownDemo = findDemo(running ? runningFor : results ? ranFor : "");

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Compare</h1>
          <p>Run one question through up to four arm × model configurations and read the answers side by side.</p>
        </div>
      </div>

      <div className="compare-setup">
        <section className="card">
          <div className="card-head">
            <h2>Question</h2>
            <div className="segmented" role="tablist" aria-label="Question source">
              <button role="tab" aria-selected={mode === "question"} className={mode === "question" ? "on" : ""} onClick={() => switchMode("question")}>
                Type a question
              </button>
              <button role="tab" aria-selected={mode === "item"} className={mode === "item" ? "on" : ""} onClick={() => switchMode("item")}>
                Dataset item
              </button>
            </div>
          </div>
          <div className="card-pad">
            {mode === "question" ? (
              <>
                <textarea
                  className="textarea"
                  style={{ width: "100%" }}
                  rows={3}
                  placeholder="Ask about any of the 25 companies, e.g. revenue, growth, risk events…"
                  aria-label="Question"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                      e.preventDefault();
                      void run();
                    }
                  }}
                />
              </>
            ) : config ? (
              <div className="stack" style={{ gap: 10 }}>
                <ItemPicker config={config} dataset={dataset} onDataset={setDataset} selected={selected} onSelect={selectItem} />
                {selected && (
                  <div className="selected-item">
                    <div className="row small faint" style={{ marginBottom: 4 }}>
                      <span className="mono">{selected.item_id}</span>
                      <span className="badge">{selected.kind}</span>
                      {selected.split && <span className="badge">{selected.split}</span>}
                    </div>
                    <div>{selected.question}</div>
                    {selected.turns.length > 0 && (
                      <div className="small muted" style={{ marginTop: 4 }}>
                        Earlier turns: {selected.turns.join(" → ")}
                      </div>
                    )}
                    {selected.answer && (
                      <div className="small muted" style={{ marginTop: 4 }}>
                        <strong>Gold:</strong> {selected.answer}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <SkeletonLines lines={5} />
            )}
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h2>Configurations</h2>
            <button className="btn primary" onClick={() => void run()} disabled={!ready || Boolean(running)} title="Run (⌘/Ctrl + Enter)">
              {running ? <Spinner /> : <Icon name="play" size={13} />} {running ? "Running…" : "Run"}
            </button>
          </div>
          <div className="card-pad">
            {config ? (
              <ConfigPicker value={configs} onChange={setConfigs} arms={config.arms} models={config.models} />
            ) : (
              <SkeletonLines lines={3} />
            )}
          </div>
        </section>
      </div>

      <section className="card demo-panel">
        <div className="card-head">
          <h2>Demo questions</h2>
          <span className="small faint">Click one to run it on B0, ReAct and Loupe with the first row's model. Hover for what to look for.</span>
        </div>
        <div className="card-pad">
          <DemoGrid onPick={runDemo} activeId={activeDemo?.id} disabled={Boolean(running)} />
        </div>
      </section>

      {Boolean(runError) && (
        <div style={{ marginBottom: 14 }}>
          <ErrorBanner title="Comparison failed" error={runError} onRetry={ready ? () => void run() : undefined} />
        </div>
      )}

      {shownDemo && (running || results) && (
        <div style={{ marginBottom: 12 }}>
          <InfoBanner>
            <strong>{shownDemo.title}: what to look for.</strong> {shownDemo.lookFor}
          </InfoBanner>
        </div>
      )}

      {running ? (
        <div className="compare-grid" style={{ "--cols": cols } as CSSProperties}>
          {running.map((c, i) => (
            <div className="card run-col" key={i} aria-busy="true">
              <div className="run-col-head">
                <div className="run-title">
                  <span className="arm-swatch" style={{ background: armColor(c.arm) }} />
                  <strong>{armLabel(config, c.arm)}</strong>
                  <ToolsetBadge arm={c.arm} />
                  <span className="tag">{c.model}</span>
                </div>
                <div className="stats-strip">
                  <Skeleton width={180} height={10} />
                </div>
              </div>
              <div className="run-body stack">
                <SkeletonLines lines={4} />
                <Skeleton height={120} />
              </div>
            </div>
          ))}
        </div>
      ) : results ? (
        <>
          <div className="row" style={{ marginBottom: 10, alignItems: "baseline" }}>
            <h2>Results</h2>
            <span className="muted small" style={{ minWidth: 0 }}>
              {truncate(ranFor, 140)}
            </span>
          </div>
          {results[0]?.gold && (
            <div className="small" style={{ marginBottom: 10 }}>
              <span className="badge accent">Gold</span> <span className="muted">{results[0].gold.answer}</span>
            </div>
          )}
          <div className="compare-grid" style={{ "--cols": cols } as CSSProperties}>
            {results.map((r) => (
              <RunCard key={r.run_id} result={r} />
            ))}
          </div>
        </>
      ) : (
        <div className="card">
          <EmptyState icon="compare" title="Nothing compared yet">
            Type a question or pick a dataset item, choose the configurations, then press Run. Each claim is highlighted green when the
            verifier found it supported by the cited evidence and red when it did not.
          </EmptyState>
        </div>
      )}
    </div>
  );
}
