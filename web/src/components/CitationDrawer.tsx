import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { Citation } from "../api/types";
import { formatValue } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { CitationContext, type CitationTarget } from "./citationContext";
import { ErrorBanner, SkeletonLines } from "./Feedback";
import { Icon } from "./Icon";
import { EvidenceKindIcon } from "./EvidenceList";

/** Provides the citation drawer to everything below it (chips call `open`). */
export function CitationProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<CitationTarget | null>(null);
  const open = useCallback((t: CitationTarget) => setCurrent(t), []);
  const close = useCallback(() => setCurrent(null), []);
  const value = useMemo(() => ({ open, close, current }), [open, close, current]);
  return (
    <CitationContext.Provider value={value}>
      {children}
      {current && <CitationDrawer target={current} onClose={close} />}
    </CitationContext.Provider>
  );
}

function VerifiedBadge({ verified }: { verified: boolean | null | undefined }) {
  if (verified === undefined) return null;
  if (verified === true) return <span className="badge good" title="The verifier matched the claim to this evidence">claim supported</span>;
  if (verified === false) return <span className="badge bad" title="The claim does not match this evidence">claim unsupported</span>;
  return <span className="badge" title="Nothing checkable in the claim">unchecked</span>;
}

/** Splits `text` at the highlight so the cited span can be marked. */
function Highlighted({ text, highlight }: { text: string; highlight: [number, number] | null }) {
  const markRef = useRef<HTMLElement>(null);
  useEffect(() => {
    markRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [text, highlight]);
  if (!highlight) return <pre className="passage">{text}</pre>;
  const a = Math.max(0, Math.min(text.length, highlight[0]));
  const b = Math.max(a, Math.min(text.length, highlight[1]));
  return (
    <pre className="passage">
      {text.slice(0, a)}
      <mark ref={markRef}>{text.slice(a, b)}</mark>
      {text.slice(b)}
    </pre>
  );
}

function DocumentPassage({ citation }: { citation: Citation }) {
  const docId = citation.doc_id as string;
  const { data, error, loading, reload } = useAsync(
    () => api.document(docId, { start: citation.start_char, end: citation.end_char, context: 600 }),
    [docId, citation.start_char, citation.end_char],
  );
  if (loading) return <SkeletonLines lines={6} />;
  if (error) return <ErrorBanner title="Could not load the passage" error={error} onRetry={reload} />;
  if (!data) return null;
  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="row small muted">
        <span className="badge accent">{data.company_id}</span>
        <span className="badge">{data.form}</span>
        {data.period_end && <span>period ended {data.period_end}</span>}
      </div>
      <Highlighted text={data.text} highlight={data.highlight} />
      <a className="btn sm" href={data.url} target="_blank" rel="noreferrer" style={{ alignSelf: "flex-start" }}>
        Open filing on SEC.gov <Icon name="external" size={13} />
      </a>
    </div>
  );
}

export function CitationDrawer({ target, onClose }: { target: CitationTarget; onClose: () => void }) {
  const { evidence } = target;
  const citation = evidence?.citation ?? target.citation;
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const canFetch = Boolean(citation?.doc_id) && citation?.start_char !== null && citation?.start_char !== undefined;
  const verified = target.verified !== undefined ? target.verified : (citation?.verified ?? undefined);
  // A fetched chunk shows its text highlighted in context, so it is not repeated above.
  const showText = evidence && !(evidence.kind === "chunk" && canFetch);

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={`Evidence ${target.id}`}>
        <div className="drawer-head">
          {evidence && <EvidenceKindIcon kind={evidence.kind} />}
          <strong className="mono" style={{ fontSize: 13 }}>
            {target.id}
          </strong>
          {evidence && <span className="badge">{evidence.kind}</span>}
          <VerifiedBadge verified={verified} />
          <span className="spacer" />
          <button ref={closeRef} className="btn ghost icon" onClick={onClose} aria-label="Close">
            <Icon name="close" />
          </button>
        </div>
        <div className="drawer-body stack">
          {!evidence && !citation && (
            <ErrorBanner
              title="Not in the evidence ledger"
              error={new Error(`The answer cites ${target.id}, but its evidence list has no item with that id.`)}
            />
          )}
          {evidence && showText && (
            <div>
              <div className="section-label" /* taste-skill-ignore */ style={{ marginTop: 0 }}>
                {evidence.kind === "chunk" ? "Cited passage" : evidence.kind === "fact" ? "XBRL fact / record" : "Calculation"}
              </div>
              <div style={{ overflowWrap: "anywhere" }}>{evidence.text}</div>
              {evidence.value !== null && (
                <div className="small muted" style={{ marginTop: 4 }}>
                  value: <span className="mono">{evidence.value.toLocaleString("en-US")}</span>
                  {Math.abs(evidence.value) >= 1e4 && <> ({formatValue(evidence.value)})</>}
                </div>
              )}
            </div>
          )}
          {citation && (
            <dl className="kv">
              {citation.doc_id && (
                <>
                  <dt>document</dt>
                  <dd className="mono">{citation.doc_id}</dd>
                </>
              )}
              {citation.chunk_id && (
                <>
                  <dt>chunk</dt>
                  <dd className="mono">{citation.chunk_id}</dd>
                </>
              )}
              {citation.fact_id && (
                <>
                  <dt>fact</dt>
                  <dd className="mono">{citation.fact_id}</dd>
                </>
              )}
              {citation.start_char !== null && (
                <>
                  <dt>characters</dt>
                  <dd className="mono">
                    {citation.start_char}–{citation.end_char ?? "?"}
                  </dd>
                </>
              )}
              {citation.quote && (
                <>
                  <dt>quote</dt>
                  <dd>“{citation.quote}”</dd>
                </>
              )}
            </dl>
          )}
          {citation && canFetch && (
            <div>
              <div className="section-label" /* taste-skill-ignore */>In the filing</div>
              <DocumentPassage citation={citation} />
            </div>
          )}
          {citation?.url && !canFetch && (
            <a className="btn sm" href={citation.url} target="_blank" rel="noreferrer" style={{ alignSelf: "flex-start" }}>
              Open source on SEC.gov <Icon name="external" size={13} />
            </a>
          )}
          {evidence?.kind === "calc" && !citation?.url && (
            <p className="small faint" style={{ margin: 0 }}>
              Computed by the calculator tool from other evidence items; it has no source document of its own.
            </p>
          )}
        </div>
      </aside>
    </>
  );
}
