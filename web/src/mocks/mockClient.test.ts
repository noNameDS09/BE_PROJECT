import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import { DEMO_QUESTIONS, EXAMPLE_QUESTIONS } from "../lib/examples";
import { parseCitations } from "../lib/citations";
import { createMockClient } from ".";
import { findScenario } from "./scenarios";

const api = createMockClient({ delayMs: 0 });

const TICKERS = "PEP AMCR JNJ MMM AMD BBY BA AXP MGM PFE ULTA ADBE JPM VZ CVS ADM UNH DBD SHAK SAH ECHO KR RIG CMP BFH".split(" ");

describe("mock config", () => {
  it("lists the 25 companies, the seven arms plus Loupe ablations, and datasets", async () => {
    const c = await api.config();
    expect(c.companies.map((x) => x.id).sort()).toEqual([...TICKERS].sort());
    expect(c.arms.slice(0, 7).map((a) => a.name)).toEqual(["b0", "rag", "react", "plan_execute", "router", "self_refine", "loupe"]);
    expect(c.arms.slice(7).every((a) => a.name.startsWith("loupe-"))).toBe(true);
    expect(c.datasets.length).toBeGreaterThanOrEqual(3);
    for (const d of c.datasets) expect(d.items).toBeGreaterThan(0);
    for (const m of c.models) expect(m.model).toContain("/");
  });

  it("gives baselines generic tools and Loupe the financial harness", async () => {
    const c = await api.config();
    const arm = (name: string) => c.arms.find((a) => a.name === name)!;
    expect(arm("b0").toolset).toBe("none");
    expect(arm("b0").tools).toEqual([]);
    expect(arm("react").toolset).toBe("generic");
    expect(arm("react").tools).not.toContain("get_financial_metric");
    expect(arm("loupe").toolset).toBe("harness");
    expect(arm("loupe").tools).toContain("get_financial_metric");
    expect(arm("loupe-generic-tools").toolset).toBe("generic");
  });
});

describe("mock compare", () => {
  it("returns B0 with a hallucinated (unsupported) claim and Loupe fully supported with a chart", async () => {
    const { results } = await api.compare({
      question: null,
      item_id: "loupe-gold:amd-rev-growth-FY2024",
      configs: [
        { arm: "b0", model: "groq-llama-70b" },
        { arm: "loupe", model: "groq-llama-70b" },
      ],
    });
    const [b0, loupe] = results;
    expect(b0?.answer.claims.some((c) => c.supported === false)).toBe(true);
    expect(b0?.gold?.correct).toBe(0);
    expect(loupe?.answer.claims.length).toBeGreaterThan(0);
    expect(loupe?.answer.claims.every((c) => c.supported === true)).toBe(true);
    expect(loupe?.answer.charts.length).toBe(1);
    expect(loupe?.gold?.correct).toBe(1);
    // Loupe's verifier removed a sentence; other arms never report removed claims.
    expect(loupe?.answer.removed_claims?.length).toBeGreaterThan(0);
    expect(b0?.answer.removed_claims ?? []).toEqual([]);
    // Fact citations carry a verdict and point at SEC's inline XBRL viewer.
    const fact = loupe!.answer.claims[0]!.citations[0]!;
    expect(fact.verified).toBe(true);
    expect(fact.url).toContain("/ix?doc=");
    const passage = loupe!.answer.claims.flatMap((c) => c.citations).find((c) => c.chunk_id !== null);
    expect(passage?.quote).toBeTruthy();
    // tokens / latency are the sums over the trace
    const t = loupe!.answer.trace.reduce((s, x) => s + x.tokens_in + x.tokens_out, 0);
    expect(loupe?.tokens).toBe(t);
  });

  it("every [E#] in Loupe answers resolves to an evidence item", async () => {
    for (const q of EXAMPLE_QUESTIONS) {
      const { results } = await api.compare({ question: q, item_id: null, configs: [{ arm: "loupe", model: "gemini-flash" }] });
      const a = results[0]!.answer;
      const ids = new Set(a.evidence.map((e) => e.id));
      for (const tok of parseCitations(a.text)) if (tok.type === "cite") expect(ids.has(tok.id)).toBe(true);
    }
  });

  it("abstains on the false-premise question", async () => {
    const falsePremise = DEMO_QUESTIONS.find((d) => d.id === "false-premise")!.question;
    const { results } = await api.compare({ question: falsePremise, item_id: null, configs: [{ arm: "loupe", model: "groq-llama-70b" }] });
    expect(results[0]?.answer.abstained).toBe(true);
    expect(results[0]?.gold).toBeNull(); // free-text question: no gold
  });

  it("returns an error result for a failing model while other columns succeed", async () => {
    const { results } = await api.compare({
      question: EXAMPLE_QUESTIONS[0]!,
      item_id: null,
      configs: [
        { arm: "loupe", model: "nim-llama-70b" },
        { arm: "loupe", model: "groq-llama-70b" },
      ],
    });
    expect(results[0]?.error).toMatch(/NVIDIA_NIM_API_KEY/);
    expect(results[0]?.answer.text).toBe("");
    expect(results[1]?.error).toBeNull();
  });

  it("rejects more than four configs and missing questions", async () => {
    const five = Array.from({ length: 5 }, () => ({ arm: "b0", model: "groq-llama-70b" }));
    await expect(api.compare({ question: "x", item_id: null, configs: five })).rejects.toBeInstanceOf(ApiError);
    await expect(api.compare({ question: "  ", item_id: null, configs: [five[0]!] })).rejects.toMatchObject({ status: 422 });
  });

  it("generates answers for numeric dataset items", () => {
    expect(findScenario(null, "loupe-gold:num-JPM-NetIncomeLoss-FY2024")).not.toBeNull();
  });
});

describe("mock OpenRouter models and chat", () => {
  it("lists free OpenRouter models, tool-calling ones first, including one without tools", async () => {
    const { models, fetched_at } = await api.openrouterModels();
    expect(fetched_at).toBeGreaterThan(0);
    expect(models.length).toBeGreaterThanOrEqual(3);
    for (const m of models) {
      expect(m.alias).toBe(`openrouter/${m.id}`);
      expect(m.free).toBe(true);
    }
    expect(models.some((m) => !m.tools)).toBe(true);
    const firstNoTools = models.findIndex((m) => !m.tools);
    expect(models.slice(firstNoTools).every((m) => !m.tools)).toBe(true);
  });

  it("answers chat with the requested arm (Loupe by default) and accepts custom OpenRouter aliases", async () => {
    const messages = [{ role: "user" as const, content: EXAMPLE_QUESTIONS[0]! }];
    expect((await api.chat({ messages, model: "gemini-flash" })).arm).toBe("loupe");
    const r = await api.chat({ messages, model: "openrouter/qwen/qwen3-235b-a22b:free", arm: "react" });
    expect(r.arm).toBe("react");
    expect(r.model).toBe("openrouter/qwen/qwen3-235b-a22b:free");
    expect(r.error).toBeNull();
    await expect(api.chat({ messages, model: "gemini-flash", arm: "nope" })).rejects.toMatchObject({ status: 422 });
  });
});

describe("mock datasets", () => {
  it("paginates and filters items", async () => {
    const all = await api.datasetItems("loupe-gold", { limit: 10 });
    expect(all.items).toHaveLength(10);
    expect(all.total).toBeGreaterThan(10);
    const page2 = await api.datasetItems("loupe-gold", { offset: 10, limit: 10 });
    expect(page2.items[0]?.item_id).not.toBe(all.items[0]?.item_id);
    const refusals = await api.datasetItems("loupe-gold", { kind: "refusal" });
    expect(refusals.items.every((i) => i.kind === "refusal")).toBe(true);
    const amd = await api.datasetItems("loupe-gold", { q: "AMD" });
    expect(amd.items.every((i) => i.companies.includes("AMD") || /amd/i.test(i.question + i.item_id))).toBe(true);
  });

  it("404s for unknown datasets", async () => {
    await expect(api.datasetItems("nope")).rejects.toMatchObject({ status: 404 });
  });
});

describe("mock results and documents", () => {
  it("leaderboard rows carry bounded intervals", async () => {
    const { rows } = await api.leaderboard({ dataset: "loupe-gold", model: "nim-nemotron-super" });
    expect(rows).toHaveLength(8);
    for (const r of rows) {
      const m = r.metrics.accuracy!;
      expect(m.lo!).toBeLessThanOrEqual(m.mean!);
      expect(m.hi!).toBeGreaterThanOrEqual(m.mean!);
    }
  });

  it("runs filter on correctness", async () => {
    const { rows } = await api.runs({ arm: "b0", correct: "false", limit: 500 });
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.every((r) => r.arm === "b0" && r.correct !== null && r.correct < 0.5)).toBe(true);
  });

  it("documents return the cited span highlighted within the window", async () => {
    const { results } = await api.compare({ question: EXAMPLE_QUESTIONS[0]!, item_id: null, configs: [{ arm: "loupe", model: "groq-llama-70b" }] });
    const chunk = results[0]!.answer.evidence.find((e) => e.kind === "chunk")!;
    const doc = await api.document(chunk.citation.doc_id!, { start: chunk.citation.start_char, end: chunk.citation.end_char });
    const [a, b] = doc.highlight!;
    expect(doc.text.slice(a, b)).toBe(chunk.text);
  });
});
