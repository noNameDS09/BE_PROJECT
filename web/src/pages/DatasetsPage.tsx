import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { KINDS, type EvalItem, type Kind, type Split } from "../api/types";
import { EmptyState, ErrorBanner, SkeletonLines, SkeletonTable } from "../components/Feedback";
import { FilterBar, FilterSelect } from "../components/Filters";
import { Icon } from "../components/Icon";
import { DASH, formatValue, prettyJson, truncate } from "../lib/format";
import { useAsync, useDebounced } from "../lib/useAsync";
import { useConfig } from "../lib/useConfig";

const PAGE = 25;

function List({ values }: { values: string[] }) {
  if (!values.length) return <span className="faint">{DASH}</span>;
  return (
    <span className="row" style={{ gap: 4 }}>
      {values.map((v, i) => (
        <span key={i} className="tag">
          {v}
        </span>
      ))}
    </span>
  );
}

function ItemDetail({ item, onClose }: { item: EvalItem; onClose: () => void }) {
  const navigate = useNavigate();
  return (
    <section className="card detail">
      <div className="card-head">
        <h2 className="mono" style={{ fontSize: 12, overflowWrap: "anywhere" }}>
          {item.item_id}
        </h2>
        <div className="row" style={{ flexWrap: "nowrap" }}>
          <button className="btn primary sm" onClick={() => navigate(`/?item=${encodeURIComponent(item.item_id)}`)}>
            Run in Compare <Icon name="arrowRight" size={13} />
          </button>
          <button className="btn ghost sm icon" onClick={onClose} aria-label="Close item">
            <Icon name="close" size={14} />
          </button>
        </div>
      </div>
      <div className="card-pad">
        <p style={{ marginTop: 0, fontSize: 14 }}>{item.question}</p>
        <dl className="kv">
          <dt>dataset</dt>
          <dd>{item.dataset}</dd>
          <dt>kind</dt>
          <dd>
            <span className="badge">{item.kind}</span>
          </dd>
          <dt>answer</dt>
          <dd>{item.answer ?? <span className="faint">{DASH}</span>}</dd>
          <dt>answer_value</dt>
          <dd className="mono">
            {item.answer_value === null ? DASH : `${item.answer_value} ${item.answer_unit ?? ""}`}
            {item.answer_value !== null && Math.abs(item.answer_value) >= 1e4 && (
              <span className="faint"> ({formatValue(item.answer_value, item.answer_unit)})</span>
            )}
          </dd>
          <dt>tolerance</dt>
          <dd className="mono">{item.tolerance}</dd>
          <dt>mode</dt>
          <dd>{item.mode}</dd>
          <dt>companies</dt>
          <dd>
            <List values={item.companies} />
          </dd>
          <dt>fiscal_year</dt>
          <dd>{item.fiscal_year ?? DASH}</dd>
          <dt>split</dt>
          <dd>{item.split ?? DASH}</dd>
          <dt>category</dt>
          <dd>{item.category ?? DASH}</dd>
          <dt>turns</dt>
          <dd>{item.turns.length ? <ol style={{ margin: 0, paddingLeft: 18 }}>{item.turns.map((t, i) => <li key={i}>{t}</li>)}</ol> : DASH}</dd>
          <dt>expected_tools</dt>
          <dd>
            <List values={item.expected_tools} />
          </dd>
          <dt>expected_intents</dt>
          <dd>
            <List values={item.expected_intents} />
          </dd>
        </dl>

        {item.context && (
          <>
            <div className="section-label" /* taste-skill-ignore */>Context</div>
            <pre className="passage" style={{ maxHeight: 200, overflow: "auto" }}>
              {item.context}
            </pre>
          </>
        )}

        <div className="section-label" /* taste-skill-ignore */>Gold evidence ({item.evidence.length})</div>
        {item.evidence.length === 0 ? (
          <div className="small faint">None.</div>
        ) : (
          <ul className="evidence-list">
            {item.evidence.map((e, i) => (
              <li key={i} className="evidence-item" style={{ cursor: "default", gridTemplateColumns: "1fr" }}>
                <div>
                  <div className="evidence-meta">
                    {e.doc_id && <span className="mono">{e.doc_id}</span>}
                    {e.item && <span>Item {e.item}</span>}
                    {e.page !== null && <span>page {e.page}</span>}
                    {e.accession && <span className="mono">{e.accession}</span>}
                  </div>
                  <div className="small" style={{ color: "var(--text-muted)" }}>
                    {e.text ?? <span className="faint">(no passage text)</span>}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}

        <div className="section-label" /* taste-skill-ignore */>Documents ({item.documents.length})</div>
        {item.documents.length === 0 ? (
          <div className="small faint">None (corpus mode uses the shared index).</div>
        ) : (
          <table className="data small">
            <tbody>
              {item.documents.map((d) => (
                <tr key={d.doc_id}>
                  <td className="mono">{d.doc_id}</td>
                  <td>{d.title || DASH}</td>
                  <td className="mono faint">{d.path ?? (d.text ? `${d.text.length} chars inline` : DASH)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="section-label" /* taste-skill-ignore */>Meta</div>
        <pre className="json">{prettyJson(item.meta)}</pre>
      </div>
    </section>
  );
}

export function DatasetsPage() {
  const { config, error: configError, retry } = useConfig();
  const [params, setParams] = useSearchParams();
  const ds = params.get("ds") ?? "";
  const split = (params.get("split") ?? "") as Split | "";
  const kind = (params.get("kind") ?? "") as Kind | "";
  const page = Math.max(0, Number(params.get("page") ?? 0) || 0);
  const [q, setQ] = useState(params.get("q") ?? "");
  const query = useDebounced(q, 250);
  const [selected, setSelected] = useState<EvalItem | null>(null);

  const update = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    setParams(next, { replace: true });
  };

  useEffect(() => {
    if ((params.get("q") ?? "") !== query) update({ q: query || null, page: null });
  }, [query]);

  useEffect(() => {
    if (!ds && config?.datasets[0]) update({ ds: config.datasets[0].name });
  }, [config, ds]);

  const { data, error, loading, reload } = useAsync(
    () => api.datasetItems(ds, { offset: page * PAGE, limit: PAGE, split, kind, q: query }),
    [ds, page, split, kind, query],
    Boolean(ds),
  );

  const info = config?.datasets.find((d) => d.name === ds);
  const total = data?.total ?? 0;
  const from = total === 0 ? 0 : page * PAGE + 1;
  const to = Math.min(total, (page + 1) * PAGE);

  if (configError) return <ErrorBanner title="Could not load /api/config" error={configError} onRetry={retry} />;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Datasets</h1>
          <p>Every evaluation item in one format (EvalItem): public benchmarks and Loupe-Gold.</p>
        </div>
      </div>

      {!config ? (
        <SkeletonLines lines={2} />
      ) : config.datasets.length === 0 ? (
        <EmptyState icon="database" title="No datasets loaded">
          Run <code>uv run loupe datasets download</code> and restart the API.
        </EmptyState>
      ) : (
        <div className="dataset-cards">
          {config.datasets.map((d) => (
            <button
              key={d.name}
              className={`dataset-card${d.name === ds ? " on" : ""}`}
              onClick={() => {
                setSelected(null);
                setQ("");
                setParams({ ds: d.name }, { replace: true });
              }}
            >
              <div className="row" style={{ justifyContent: "space-between" }}>
                <strong>{d.name}</strong>
                <span className="count">{d.items.toLocaleString("en-US")}</span>
              </div>
              <div className="row" style={{ gap: 4, marginTop: 6 }}>
                {d.kinds.map((k) => (
                  <span key={k} className="tag">
                    {k}
                  </span>
                ))}
              </div>
            </button>
          ))}
        </div>
      )}

      {ds && (
        <>
          <FilterBar>
            <label className="field" style={{ flex: "1 1 240px" }}>
              <span>Search</span>
              <input className="input" type="search" placeholder="Question, id or ticker" value={q} onChange={(e) => setQ(e.target.value)} />
            </label>
            <FilterSelect label="Split" value={split} onChange={(v) => update({ split: v || null, page: null })} options={[{ value: "dev", label: "dev" }, { value: "test", label: "test" }]} />
            <FilterSelect
              label="Kind"
              value={kind}
              onChange={(v) => update({ kind: v || null, page: null })}
              options={(info?.kinds.length ? info.kinds : KINDS).map((k) => ({ value: k, label: k }))}
            />
          </FilterBar>

          <div className={selected ? "split" : undefined}>
            <section className="card" style={{ minWidth: 0 }}>
              {error ? (
                <div className="card-pad">
                  <ErrorBanner title="Could not load items" error={error} onRetry={reload} />
                </div>
              ) : loading && !data ? (
                <SkeletonTable rows={10} cols={5} />
              ) : !data || data.items.length === 0 ? (
                <EmptyState icon="search" title="No items match these filters" />
              ) : (
                <>
                  <div className="table-wrap" style={{ opacity: loading ? 0.6 : 1 }}>
                    <table className="data">
                      <thead>
                        <tr>
                          <th>Question</th>
                          <th>Kind</th>
                          <th>Answer</th>
                          <th>Companies</th>
                          <th className="opt">Split</th>
                          <th className="opt">Category</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.items.map((item) => (
                          <tr
                            key={item.item_id}
                            className={`clickable${selected?.item_id === item.item_id ? " selected" : ""}`}
                            onClick={() => setSelected(item)}
                          >
                            <td style={{ minWidth: 260 }}>
                              <div>{truncate(item.question, 140)}</div>
                              <div className="small faint mono">{item.item_id}</div>
                            </td>
                            <td>
                              <span className="badge">{item.kind}</span>
                            </td>
                            <td className="small" style={{ minWidth: 140, maxWidth: 260 }}>
                              {item.answer ? truncate(item.answer, 90) : <span className="faint">{DASH}</span>}
                            </td>
                            <td className="nowrap">{item.companies.join(", ") || <span className="faint">{DASH}</span>}</td>
                            <td className="opt">{item.split ?? <span className="faint">{DASH}</span>}</td>
                            <td className="small nowrap opt">{item.category ?? <span className="faint">{DASH}</span>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="pager">
                    <span className="num">
                      {from}–{to} of {total}
                    </span>
                    <button className="btn sm" disabled={page === 0} onClick={() => update({ page: page - 1 ? String(page - 1) : null })}>
                      Previous
                    </button>
                    <button className="btn sm" disabled={to >= total} onClick={() => update({ page: String(page + 1) })}>
                      Next
                    </button>
                  </div>
                </>
              )}
            </section>
            {selected && <ItemDetail item={selected} onClose={() => setSelected(null)} />}
          </div>
        </>
      )}
    </div>
  );
}
