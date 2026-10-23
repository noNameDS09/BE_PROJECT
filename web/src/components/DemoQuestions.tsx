import { DEMO_QUESTIONS, type DemoQuestion } from "../lib/examples";

/** The ten demo questions as a compact grid of cards; `lookFor` is each card's tooltip. */
export function DemoGrid({
  onPick,
  activeId,
  disabled,
}: {
  onPick: (demo: DemoQuestion) => void;
  activeId?: string;
  disabled?: boolean;
}) {
  return (
    <div className="demo-grid">
      {DEMO_QUESTIONS.map((d) => (
        <button
          key={d.id}
          type="button"
          className={`demo-card${d.id === activeId ? " on" : ""}`}
          onClick={() => onPick(d)}
          disabled={disabled}
          title={`Look for: ${d.lookFor}`}
          aria-pressed={activeId === undefined ? undefined : d.id === activeId}
        >
          <span className="demo-title">{d.title}</span>
          <span className="demo-q">{d.question}</span>
          <span className="demo-shows">{d.shows}</span>
        </button>
      ))}
    </div>
  );
}
