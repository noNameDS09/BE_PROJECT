import { Fragment, useMemo } from "react";
import type { Answer, Claim, Evidence } from "../api/types";
import { claimStatus, claimSummary, parseCitations, segmentAnswer } from "../lib/citations";
import { formatLatency, formatTokens } from "../lib/format";
import { useCitation } from "./citationContext";
import { Collapsible } from "./Collapsible";
import { EvidenceList } from "./EvidenceList";
import { Icon } from "./Icon";
import { PlotlyChart } from "./PlotlyChart";
import { TraceTimeline } from "./TraceTimeline";

/** Text with [E#] markers rendered as clickable chips. */
export function CitedText({ text, ledger, claim }: { text: string; ledger: Map<string, Evidence>; claim?: Claim }) {
  const { open, current } = useCitation();
  const tokens = useMemo(() => parseCitations(text), [text]);
  return (
    <>
      {tokens.map((t, i) => {
        if (t.type === "text") return <Fragment key={i}>{t.value}</Fragment>;
        const ev = ledger.get(t.id);
        const fallback = !ev ? claim?.citations[0] : undefined;
        const active = current?.id === t.id && current.evidence === ev;
        // The claim's own citation of this item carries the verifier's verdict.
        const own = ev
          ? claim?.citations.find(
              (c) =>
                (c.chunk_id !== null && c.chunk_id === ev.citation.chunk_id) ||
                (c.fact_id !== null && c.fact_id === ev.citation.fact_id),
            )
          : undefined;
        const verified = claim ? (own?.verified ?? claim.supported) : undefined;
        return (
          <button
            key={i}
            type="button"
            className={`chip${ev || fallback ? "" : " missing"}${active ? " active" : ""}`}
            title={ev ? `${t.id} · ${ev.kind}: ${ev.text.slice(0, 120)}` : `${t.id} is not in the evidence ledger`}
            onClick={() => open({ id: t.id, evidence: ev, citation: fallback, verified })}
          >
            {t.id}
          </button>
        );
      })}
    </>
  );
}

const STATUS_TITLE = {
  supported: "Supported: numbers and quotes match the cited evidence",
  unsupported: "Unsupported: does not match the cited evidence",
  unchecked: "Nothing checkable in this sentence",
} as const;

function ClaimSpan({ claim, ledger }: { claim: Claim; ledger: Map<string, Evidence> }) {
  const status = claimStatus(claim);
  return (
    <span className={`claim ${status}`} title={STATUS_TITLE[status]}>
      <CitedText text={claim.text} ledger={ledger} claim={claim} />
    </span>
  );
}

export function ClaimLegend({ claims }: { claims: Claim[] }) {
  const s = claimSummary(claims);
  return (
    <div className="legend" aria-label="Claim verdicts">
      <span>
        <i className="supported" />
        {s.supported} supported
      </span>
      <span>
        <i className="unsupported" />
        {s.unsupported} unsupported
      </span>
      <span>
        <i className="unchecked" />
        {s.unchecked} unchecked
      </span>
    </div>
  );
}

/**
 * The shared answer renderer (Compare, Runs, Chat): answer text with claims highlighted by
 * verdict and [E#] chips, charts, the evidence ledger and the trace.
 */
export function AnswerView({
  answer,
  traceOpen = false,
  evidenceOpen = false,
}: {
  answer: Answer;
  traceOpen?: boolean;
  evidenceOpen?: boolean;
}) {
  const ledger = useMemo(() => new Map(answer.evidence.map((e) => [e.id, e])), [answer.evidence]);
  const segments = useMemo(() => segmentAnswer(answer.text, answer.claims), [answer.text, answer.claims]);
  const traceTokens = answer.trace.reduce((s, t) => s + t.tokens_in + t.tokens_out, 0);
  const traceMs = answer.trace.reduce((s, t) => s + t.latency_ms, 0);

  return (
    <div className="stack" style={{ gap: 10 }}>
      {answer.abstained && (
        <div className="abstain-note">
          <Icon name="info" size={14} /> Abstained: the system declined to give a definitive answer.
        </div>
      )}

      {segments ? (
        <div className="answer-text">
          {segments.map((seg, i) => {
            const c = seg.claim === null ? undefined : answer.claims[seg.claim];
            return c ? <ClaimSpan key={i} claim={c} ledger={ledger} /> : <CitedText key={i} text={seg.text} ledger={ledger} />;
          })}
          {!answer.text && <span className="faint">(empty answer)</span>}
        </div>
      ) : (
        <div className="answer-text">
          <ol className="claim-list">
            {answer.claims.map((c, i) => (
              <li key={i}>
                <ClaimSpan claim={c} ledger={ledger} />
              </li>
            ))}
          </ol>
        </div>
      )}

      {answer.claims.length > 0 && <ClaimLegend claims={answer.claims} />}

      {answer.charts.map((chart, i) => (
        <div className="chart-box" key={i}>
          <div className="chart-title">
            <span>{chart.title}</span>
            <span className="small faint">
              from{" "}
              {chart.evidence_ids.map((id) => (
                <CitedText key={id} text={`[${id}]`} ledger={ledger} />
              ))}
            </span>
          </div>
          <PlotlyChart figure={chart.figure} />
        </div>
      ))}

      <div>
        <Collapsible title="Evidence" meta={answer.evidence.length} defaultOpen={evidenceOpen}>
          <EvidenceList evidence={answer.evidence} />
        </Collapsible>
        <Collapsible
          title="Trace"
          meta={`${answer.trace.length} steps · ${formatTokens(traceTokens)} tok · ${formatLatency(traceMs)}`}
          defaultOpen={traceOpen}
        >
          <TraceTimeline trace={answer.trace} />
        </Collapsible>
      </div>
    </div>
  );
}
