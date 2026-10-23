import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { ChatMessage, RunResult } from "../api/types";
import { AnswerView } from "../components/AnswerView";
import { DemoGrid } from "../components/DemoQuestions";
import { ErrorBanner, SkeletonLines, Spinner } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { ModelPicker } from "../components/ModelPicker";
import { ToolsetBadge } from "../components/ToolsetBadge";
import { formatCost, formatLatency, formatTokens } from "../lib/format";
import { NO_TOOLS_HINT, isOpenRouterAlias, lacksToolCalling } from "../lib/modelPicker";
import { armLabel, useConfig } from "../lib/useConfig";
import { useOpenRouterModels } from "../lib/useOpenRouterModels";

type Turn =
  | { role: "user"; content: string }
  | { role: "assistant"; result: RunResult }
  | { role: "error"; error: unknown; retry: ChatMessage[] };

/** The history sent to /api/chat: user text plus each assistant answer's text. */
export function toMessages(turns: Turn[]): ChatMessage[] {
  const out: ChatMessage[] = [];
  for (const t of turns) {
    if (t.role === "user") out.push({ role: "user", content: t.content });
    else if (t.role === "assistant") out.push({ role: "assistant", content: t.result.answer.text });
  }
  return out;
}

export function ChatPage() {
  const { config } = useConfig();
  const { models: live } = useOpenRouterModels();
  const [arm, setArm] = useState("loupe");
  const [model, setModel] = useState("nim-nemotron-ultra");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (config && !config.arms.some((a) => a.name === arm)) setArm(config.arms[0]?.name ?? arm);
  }, [config, arm]);

  // OpenRouter aliases are accepted even when /api/config does not list them.
  useEffect(() => {
    if (config && !isOpenRouterAlias(model) && !config.models.some((m) => m.alias === model)) {
      setModel(config.models.find((m) => m.available)?.alias ?? config.models[0]?.alias ?? model);
    }
  }, [config, model]);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [turns, busy]);

  async function send(messages: ChatMessage[], base: Turn[]) {
    setBusy(true);
    try {
      const result = await api.chat({ messages, model, arm });
      setTurns([...base, { role: "assistant", result }]);
    } catch (error) {
      setTurns([...base, { role: "error", error, retry: messages }]);
    } finally {
      setBusy(false);
    }
  }

  function submit(text = draft) {
    const content = text.trim();
    if (!content || busy) return;
    const base: Turn[] = [...turns.filter((t) => t.role !== "error"), { role: "user", content }];
    setTurns(base);
    setDraft("");
    void send(toMessages(base), base);
  }

  function retry(i: number) {
    const t = turns[i];
    if (!t || t.role !== "error") return;
    const base = turns.slice(0, i);
    setTurns(base);
    void send(t.retry, base);
  }

  const isAblation = (name: string) => name.startsWith("loupe-");
  const mainArms = config?.arms.filter((a) => !isAblation(a.name)) ?? [];
  const ablations = config?.arms.filter((a) => isAblation(a.name)) ?? [];
  const selectedArm = config?.arms.find((a) => a.name === arm);
  const noTools = selectedArm !== undefined && selectedArm.toolset !== "none" && lacksToolCalling(model, live);

  return (
    <div className="chat">
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 12, alignItems: "center" }}>
        <div>
          <h1 style={{ fontSize: "var(--fs-section)", fontWeight: 600 }}>Chat</h1>
          <p className="small muted" style={{ margin: "2px 0 0" }}>Cited answers from {armLabel(config, arm)}</p>
        </div>
        <div className="row" style={{ gap: 8 }}>
          {config && (
            <>
              <select className="select" aria-label="Method" value={arm} onChange={(e) => setArm(e.target.value)} title={selectedArm?.description}>
                {mainArms.map((a) => (
                  <option key={a.name} value={a.name} title={a.description}>
                    {a.label}
                  </option>
                ))}
                {ablations.length > 0 && (
                  <optgroup label="Ablations">
                    {ablations.map((a) => (
                      <option key={a.name} value={a.name} title={a.description}>
                        {a.label}
                      </option>
                    ))}
                  </optgroup>
                )}
              </select>
              <ToolsetBadge arm={arm} />
              <ModelPicker models={config.models} value={model} onChange={setModel} />
            </>
          )}
          <button className="btn sm ghost" onClick={() => setTurns([])} disabled={!turns.length || busy}>
            New chat
          </button>
        </div>
      </div>
      {noTools && (
        <p className="small" style={{ color: "var(--warn)", margin: "-4px 0 8px" }} title={NO_TOOLS_HINT}>
          This model has no tool calling, which {armLabel(config, arm)} needs. Pick another model, or B0 / RAG.
        </p>
      )}

      <div className="chat-log" ref={logRef} aria-live="polite">
        {turns.length === 0 && (
          <div className="chat-empty">
            <Icon name="chat" size={32} />
            <h3>Ask about any of the 25 companies</h3>
            <p>Revenue, growth, risk events from 8-Ks, comparisons. Every claim links to its source. Or pick a demo to send it now.</p>
            <DemoGrid onPick={(d) => submit(d.question)} disabled={busy} />
          </div>
        )}
        {turns.map((t, i) => {
          if (t.role === "user")
            return (
              <div key={i} className="msg user">
                <div className="bubble">{t.content}</div>
              </div>
            );
          if (t.role === "error")
            return (
              <div key={i} className="msg assistant">
                <ErrorBanner title="The assistant could not answer" error={t.error} onRetry={() => retry(i)} />
              </div>
            );
          const r = t.result;
          return (
            <div key={i} className="msg assistant">
              <div className="bubble">
                {r.error ? <ErrorBanner title="Model call failed" error={new Error(r.error)} /> : <AnswerView answer={r.answer} />}
              </div>
              <div className="msg-meta num">
                {r.arm} · {r.model} · {formatTokens(r.tokens)} tokens · {formatLatency(r.latency_ms)} · {formatCost(r.cost_usd)}
              </div>
            </div>
          );
        })}
        {busy && (
          <div className="msg assistant">
            <div className="bubble" style={{ paddingBottom: 12 }}>
              <SkeletonLines lines={3} />
            </div>
          </div>
        )}
      </div>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <textarea
          className="textarea"
          rows={1}
          placeholder="Ask a question…  (Enter to send, Shift+Enter for a new line)"
          aria-label="Message"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <button className="btn primary" type="submit" disabled={busy || !draft.trim()} style={{ height: 44 }}>
          {busy ? <Spinner /> : <Icon name="send" size={14} />} Send
        </button>
      </form>
    </div>
  );
}
