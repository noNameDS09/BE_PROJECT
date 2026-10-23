import { useEffect, useRef, useState } from "react";
import type { ModelInfo } from "../api/types";
import {
  CUSTOM_OPTION,
  NO_TOOLS_HINT,
  classifyModelValue,
  isOpenRouterAlias,
  openRouterId,
  openRouterLabel,
  toOpenRouterAlias,
} from "../lib/modelPicker";
import { useOpenRouterModels } from "../lib/useOpenRouterModels";

/**
 * One model <select>: the models from /api/config, OpenRouter's live free models, and a
 * "Custom OpenRouter model…" option that reveals a text box for any OpenRouter id.
 * A `value` that is in neither list but starts with "openrouter/" is shown as custom.
 */
export function ModelPicker({
  models,
  value,
  onChange,
  label = "Model",
}: {
  models: ModelInfo[];
  value: string;
  onChange: (alias: string) => void;
  label?: string;
}) {
  const { models: live, error, loading } = useOpenRouterModels();
  const kind = classifyModelValue(
    value,
    models.map((m) => m.alias),
    live ? live.map((m) => m.alias) : error ? [] : null,
  );

  const [customMode, setCustomMode] = useState(false);
  const [draft, setDraft] = useState(() => openRouterId(value));
  const emitted = useRef(value);
  const inputRef = useRef<HTMLInputElement>(null);

  // A value set from outside (not typed here) closes the custom box unless it needs it.
  useEffect(() => {
    if (value === emitted.current) return;
    emitted.current = value;
    setCustomMode(false);
    setDraft(openRouterId(value));
  }, [value]);

  const custom = customMode || kind === "custom";

  useEffect(() => {
    if (customMode) inputRef.current?.focus();
  }, [customMode]);

  const emit = (alias: string) => {
    emitted.current = alias;
    onChange(alias);
  };

  const pick = (v: string) => {
    if (v === CUSTOM_OPTION) {
      setDraft(isOpenRouterAlias(value) ? openRouterId(value) : "");
      setCustomMode(true);
      return;
    }
    setCustomMode(false);
    emit(v);
  };

  const type = (text: string) => {
    setDraft(text);
    const alias = toOpenRouterAlias(text);
    if (alias) emit(alias);
  };

  const selectedLive = live?.find((m) => m.alias === value);
  const selectedConfigured = models.find((m) => m.alias === value);
  const title = custom
    ? "Any OpenRouter model id, e.g. qwen/qwen3-235b-a22b:free"
    : selectedLive
      ? selectedLive.tools
        ? selectedLive.id
        : `${selectedLive.id}\n${NO_TOOLS_HINT}`
      : selectedConfigured
        ? `${selectedConfigured.provider} · ${selectedConfigured.model}`
        : value;

  return (
    <span className="model-picker">
      <select className="select" aria-label={label} title={title} value={custom ? CUSTOM_OPTION : value} onChange={(e) => pick(e.target.value)}>
        {kind === "unknown" && <option value={value}>{value} (not configured)</option>}
        <optgroup label="Configured models">
          {models.map((m) => (
            <option key={m.alias} value={m.alias} disabled={!m.available} title={m.model ? `${m.provider} · ${m.model}` : m.provider}>
              {m.alias}
              {m.available ? "" : " (no key)"}
            </option>
          ))}
        </optgroup>
        <optgroup label="OpenRouter · free (live)">
          {kind === "pending" && <option value={value}>{openRouterId(value)}</option>}
          {loading && <option disabled>Loading OpenRouter models…</option>}
          {error && <option disabled title={error.message}>OpenRouter list unavailable</option>}
          {live?.map((m) => (
            <option key={m.alias} value={m.alias} title={m.tools ? m.id : `${m.id}\n${NO_TOOLS_HINT}`}>
              {openRouterLabel(m)}
            </option>
          ))}
        </optgroup>
        <option value={CUSTOM_OPTION}>Custom OpenRouter model…</option>
      </select>
      {custom && (
        <input
          ref={inputRef}
          className="input model-custom"
          type="text"
          placeholder="vendor/model:free"
          aria-label={`${label}: OpenRouter model id`}
          title="An OpenRouter model id; it is sent as openrouter/<id>"
          spellCheck={false}
          autoComplete="off"
          value={draft}
          onChange={(e) => type(e.target.value)}
          aria-invalid={!toOpenRouterAlias(draft)}
        />
      )}
    </span>
  );
}
