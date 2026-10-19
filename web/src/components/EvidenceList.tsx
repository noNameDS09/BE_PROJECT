import type { Evidence, EvidenceKind } from "../api/types";
import { useCitation } from "./citationContext";
import { Icon, type IconName } from "./Icon";

const KIND_ICON: Record<EvidenceKind, IconName> = { chunk: "doc", fact: "hash", calc: "calc" };
const KIND_LABEL: Record<EvidenceKind, string> = { chunk: "Filing passage", fact: "XBRL fact", calc: "Calculation" };

export function EvidenceKindIcon({ kind }: { kind: EvidenceKind }) {
  return (
    <span className={`kind ${kind}`} title={KIND_LABEL[kind] ?? kind} style={{ display: "inline-grid", placeItems: "center" }}>
      <Icon name={KIND_ICON[kind] ?? "doc"} size={14} />
    </span>
  );
}

/** The run's evidence ledger. Clicking an item opens it in the citation drawer. */
export function EvidenceList({ evidence }: { evidence: Evidence[] }) {
  const { open } = useCitation();
  if (!evidence.length) return <div className="small faint">No evidence: this run did not retrieve or compute anything.</div>;
  return (
    <ul className="evidence-list">
      {evidence.map((e) => (
        <li
          key={e.id}
          className="evidence-item"
          role="button"
          tabIndex={0}
          onClick={() => open({ id: e.id, evidence: e })}
          onKeyDown={(ev) => {
            if (ev.key === "Enter" || ev.key === " ") {
              ev.preventDefault();
              open({ id: e.id, evidence: e });
            }
          }}
        >
          <EvidenceKindIcon kind={e.kind} />
          <div style={{ minWidth: 0 }}>
            <div className="evidence-meta">
              <strong className="mono" style={{ color: "var(--text)" }}>
                {e.id}
              </strong>
              <span>{KIND_LABEL[e.kind] ?? e.kind}</span>
              {e.citation.doc_id && <span className="mono">{e.citation.doc_id}</span>}
              {e.citation.url && (
                <a href={e.citation.url} target="_blank" rel="noreferrer" onClick={(ev) => ev.stopPropagation()} title="Open on SEC.gov">
                  SEC <Icon name="external" size={11} />
                </a>
              )}
            </div>
            <div className="evidence-text">{e.text}</div>
          </div>
        </li>
      ))}
    </ul>
  );
}
