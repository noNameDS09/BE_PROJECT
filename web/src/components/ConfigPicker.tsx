import type { ArmInfo, ModelInfo, RunConfigPick } from "../api/types";
import { MAX_COMPARE_CONFIGS } from "../api/types";
import { Icon } from "./Icon";
import { ToolsetBadge } from "./ToolsetBadge";

export function ModelSelect({
  models,
  value,
  onChange,
  label = "Model",
  allowEmpty,
}: {
  models: ModelInfo[];
  value: string;
  onChange: (v: string) => void;
  label?: string;
  allowEmpty?: string;
}) {
  return (
    <select className="select" aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}>
      {allowEmpty !== undefined && <option value="">{allowEmpty}</option>}
      {models.map((m) => (
        <option key={m.alias} value={m.alias} title={m.model ? `${m.provider} · ${m.model}` : m.provider}>
          {m.alias}
          {m.available ? "" : " (no key)"}
        </option>
      ))}
    </select>
  );
}

/** Pick up to four (arm × model) configurations to compare. */
export function ConfigPicker({
  value,
  onChange,
  arms,
  models,
  max = MAX_COMPARE_CONFIGS,
}: {
  value: RunConfigPick[];
  onChange: (next: RunConfigPick[]) => void;
  arms: ArmInfo[];
  models: ModelInfo[];
  max?: number;
}) {
  const set = (i: number, patch: Partial<RunConfigPick>) => onChange(value.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  const remove = (i: number) => onChange(value.filter((_, j) => j !== i));
  const add = () => {
    const used = new Set(value.map((c) => `${c.arm}|${c.model}`));
    const model = value[value.length - 1]?.model ?? models.find((m) => m.available)?.alias ?? models[0]?.alias ?? "";
    const arm = arms.find((a) => !used.has(`${a.name}|${model}`))?.name ?? arms[0]?.name ?? "";
    onChange([...value, { arm, model }]);
  };
  const dupes = new Set<string>();
  const seen = new Set<string>();
  for (const c of value) {
    const k = `${c.arm}|${c.model}`;
    if (seen.has(k)) dupes.add(k);
    seen.add(k);
  }

  return (
    <div className="config-rows">
      {value.map((c, i) => (
        <div className="config-row" key={i}>
          <span className="idx">{i + 1}</span>
          <select className="select" aria-label={`Arm for config ${i + 1}`} value={c.arm} onChange={(e) => set(i, { arm: e.target.value })}>
            {arms.map((a) => (
              <option key={a.name} value={a.name} title={a.description}>
                {a.label}
              </option>
            ))}
          </select>
          <span className="config-toolset">
            <ToolsetBadge arm={c.arm} />
          </span>
          <ModelSelect models={models} value={c.model} onChange={(m) => set(i, { model: m })} label={`Model for config ${i + 1}`} />
          <button className="btn ghost icon" onClick={() => remove(i)} disabled={value.length <= 1} aria-label={`Remove config ${i + 1}`}>
            <Icon name="close" size={14} />
          </button>
        </div>
      ))}
      <div className="row">
        <button className="btn sm" onClick={add} disabled={value.length >= max}>
          <Icon name="plus" size={13} /> Add config
        </button>
        <span className="small faint">
          {value.length}/{max}
        </span>
        {dupes.size > 0 && <span className="small" style={{ color: "var(--warn)" }}>Duplicate configs will run twice.</span>}
      </div>
    </div>
  );
}
