/**
 * The mock "orchestrator": turns (question | item, arm, model) into a RunResult.
 *
 * Three hand-written scenarios cover the cases the Bench must show:
 *   amd   – B0 hallucinates a number (unsupported) next to a fully supported Loupe answer + chart
 *   shak  – a false-premise question where Loupe abstains and ReAct falls for the premise
 *   unh   – an 8-K event question with a deliberately unchecked claim
 * Numeric dataset items get a generated answer from their gold value; anything else gets an
 * honest "no fixture" abstention.
 */
import type { Answer, Chart, Claim, EvalItem, Evidence, RunResult, TraceStep } from "../api/types";
import {
  armTrace,
  chunkCite,
  cite,
  claim,
  emptyAnswer,
  evidence,
  hash01,
  hashHex,
  joinText,
  toolStep,
  totals,
} from "./builders";
import { CIK, SHORT_NAME } from "./fixtures/config";
import { AMD_10K, SHAK_8K, UNH_10K, UNH_8K } from "./fixtures/documents";
import { ITEM_BY_ID, VALUE_TABLE } from "./fixtures/items";

type Arm = "b0" | "rag" | "react" | "plan_execute" | "router" | "self_refine" | "loupe";

interface ArmAnswer {
  answer: Answer;
  correct: number | null;
}

interface Scenario {
  id: string;
  itemId: string;
  question: string;
  match: RegExp;
  tools: TraceStep[];
  /** Answer for an arm, or undefined to fall back to the grounded answer. */
  answers: Partial<Record<Arm, ArmAnswer>>;
  grounded: ArmAnswer;
}

function answer(text: string, claims: Claim[], ledger: Evidence[], extra: Partial<Answer> = {}): Answer {
  return { text, claims, evidence: ledger, charts: [], abstained: false, trace: [], ...extra };
}

function barChart(title: string, xs: string[], ys: number[], evidenceIds: string[], yTitle: string): Chart {
  return {
    title,
    evidence_ids: evidenceIds,
    figure: {
      data: [
        {
          type: "bar",
          x: xs,
          y: ys,
          text: ys.map((y) => `$${y.toFixed(1)}B`),
          textposition: "outside",
          marker: { color: "#6366f1" },
          hovertemplate: "%{x}: $%{y:.2f}B<extra></extra>",
        },
      ],
      layout: {
        yaxis: { title: { text: yTitle }, rangemode: "tozero" },
        xaxis: { type: "category" },
        margin: { t: 24, r: 16, b: 40, l: 56 },
        height: 260,
      },
    },
  };
}

// ---------------------------------------------------------------- AMD revenue

function amdScenario(): Scenario {
  const factUrl = "https://www.sec.gov/cgi-bin/viewer?action=view&cik=2488&accession_number=0000002488-25-000012";
  const concept = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax";
  const E1 = evidence("E1", "fact", `${concept} · AMD · FY2024 (period ended 2024-12-28) = 25,785,000,000 USD`, cite({ fact_id: `AMD:${concept}:2024-12-28`, url: factUrl }), 25785e6);
  const E2 = evidence("E2", "fact", `${concept} · AMD · FY2023 (period ended 2023-12-30) = 22,680,000,000 USD`, cite({ fact_id: `AMD:${concept}:2023-12-30`, url: factUrl }), 22680e6);
  const E3 = evidence("E3", "calc", "growth(25,785,000,000, 22,680,000,000) = (25,785 − 22,680) / 22,680 = 0.1369 → 13.7%", cite(), 0.1369);
  const E4 = evidence("E4", "chunk", AMD_10K.revenuePassage, chunkCite(AMD_10K.id, AMD_10K.revenueStart, AMD_10K.revenuePassage, AMD_10K.url));
  const E5 = evidence("E5", "fact", `${concept} · AMD · FY2022 (period ended 2022-12-31) = 23,601,000,000 USD`, cite({ fact_id: `AMD:${concept}:2022-12-31`, url: factUrl }), 23601e6);
  const ledger = [E1, E2, E3, E4, E5];

  const groundedClaims = [
    claim("AMD's net revenue for fiscal 2024 was $25,785 million [E1].", true, ledger),
    claim("That is up 13.7% from $22,680 million in fiscal 2023 [E2][E3].", true, ledger),
    claim("Management attributes the increase mainly to a 94% rise in Data Center segment revenue, with Client revenue up 52% [E4].", true, ledger),
  ];
  const grounded = answer(joinText(groundedClaims), groundedClaims, ledger, {
    charts: [barChart("AMD net revenue, FY2022–FY2024", ["FY2022", "FY2023", "FY2024"], [23.601, 22.68, 25.785], ["E5", "E2", "E1"], "USD billions")],
  });

  const b0Claims = [
    claim("AMD reported total revenue of about $24.1 billion for fiscal 2024.", false, []),
    claim("That was roughly 6% higher than the $22.7 billion it reported in fiscal 2023, helped by strong demand for Ryzen processors.", false, []),
  ];
  const b0 = answer(joinText(b0Claims), b0Claims, []);

  const ragE1 = evidence("E1", "chunk", AMD_10K.revenuePassage, chunkCite(AMD_10K.id, AMD_10K.revenueStart, AMD_10K.revenuePassage, AMD_10K.url));
  const ragClaims = [
    claim("AMD's net revenue for 2024 was $25.8 billion [E1].", true, [ragE1]),
    claim("That was an increase of 14% over 2023 net revenue of $22.7 billion [E1].", true, [ragE1]),
    claim("Growth came mainly from the Data Center and Client segments [E1].", null, [ragE1]),
  ];
  const rag = answer(joinText(ragClaims), ragClaims, [ragE1]);

  const routerLedger = [E1, E2, E4];
  const routerClaims = [
    claim("AMD's net revenue for fiscal 2024 was $25,785 million [E1].", true, routerLedger),
    claim("Compared with $22,680 million in fiscal 2023 [E2], that is growth of 15.2%.", false, routerLedger),
    claim("The increase was driven by Data Center revenue, which rose 94% [E4].", true, routerLedger),
  ];
  const router = answer(joinText(routerClaims), routerClaims, routerLedger);

  return {
    id: "amd",
    itemId: "loupe-gold:amd-rev-growth-FY2024",
    question: "What was AMD's total net revenue in fiscal 2024, and how did it change from fiscal 2023?",
    match: /\bamd\b|advanced micro/i,
    tools: [
      toolStep("get_facts", { company: "AMD", concept: "Revenues", fiscal_years: [2022, 2023, 2024] }, { facts: [E5.text, E2.text, E1.text] }, 42),
      toolStep("calc", { op: "growth", new: 25785e6, old: 22680e6 }, { value: 0.1369 }, 3),
      toolStep("search_filings", { query: "net revenue increase drivers 2024", company: "AMD", form: "10-K", k: 8 }, { chunks: [{ chunk_id: E4.citation.chunk_id, score: 0.83 }] }, 168),
      toolStep("make_chart", { kind: "bar", evidence_ids: ["E5", "E2", "E1"] }, { ok: true }, 6),
    ],
    answers: {
      b0: { answer: b0, correct: 0 },
      rag: { answer: rag, correct: 1 },
      router: { answer: router, correct: 0.5 },
    },
    grounded: { answer: grounded, correct: 1 },
  };
}

// ---------------------------------------------------------------- Shake Shack false premise

function shakScenario(): Scenario {
  const eventsUrl = `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${CIK.SHAK}&type=8-K&dateb=&owner=include&count=40`;
  const E1 = evidence(
    "E1",
    "calc",
    "Event table · SHAK · 8-K items filed 2023-01-01 → 2025-12-31: Item 1.03 (Bankruptcy) = 0 · Item 2.06 (Material impairments) = 1 · Item 4.02 (Non-reliance) = 2",
    cite({ url: eventsUrl }),
    0,
  );
  const E2 = evidence("E2", "chunk", SHAK_8K.impairmentPassage, chunkCite(SHAK_8K.id, SHAK_8K.impairmentStart, SHAK_8K.impairmentPassage, SHAK_8K.url));
  const ledger = [E1, E2];

  const loupeClaims = [
    claim("I can't answer this as asked: Shake Shack filed no Chapter 11 petition in FY2023–25, and no 8-K Item 1.03 (Bankruptcy) appears for the company [E1].", true, ledger),
    claim("What its filings do report is an Item 2.06 impairment for underperforming Shacks it intends to close [E2].", true, ledger),
  ];
  const loupe = answer(joinText(loupeClaims, "If you meant that impairment, ask about it and I will pull the figures."), loupeClaims, ledger, { abstained: true });

  const b0Claims = [
    claim("Shake Shack recorded a $48.6 million impairment charge after filing for Chapter 11 in March 2024.", false, []),
    claim("The charge mainly related to closing 34 underperforming locations as part of its restructuring plan.", false, []),
  ];
  const b0 = answer(joinText(b0Claims), b0Claims, []);

  const reactLedger = [E2];
  const reactClaims = [
    claim("After its Chapter 11 filing, Shake Shack recognized impairment charges for underperforming Shacks it planned to close [E2].", false, reactLedger),
    claim("The filings I retrieved do not state the dollar amount of the write-down.", null, reactLedger),
  ];
  const react = answer(joinText(reactClaims), reactClaims, reactLedger);

  const ragE1 = evidence("E1", "chunk", E2.text, E2.citation);
  const ragClaims = [
    claim("The retrieved filings describe an impairment for underperforming Shacks the company intends to close [E1].", true, [ragE1]),
    claim("None of them mention a Chapter 11 filing, so there is no write-down tied to one.", null, [ragE1]),
  ];
  const rag = answer(joinText(ragClaims), ragClaims, [ragE1]);

  return {
    id: "shak",
    itemId: "loupe-gold:trick-SHAK-ch11",
    question: "How much did Shake Shack write down after its Chapter 11 filing in 2024?",
    match: /shake ?shack|\bshak\b|chapter 11/i,
    tools: [
      toolStep("list_events", { company: "SHAK", items: ["1.03", "2.06", "4.02"], start: "2023-01-01", end: "2025-12-31" }, { counts: { "1.03": 0, "2.06": 1, "4.02": 2 } }, 31),
      toolStep("search_filings", { query: "Chapter 11 impairment write-down", company: "SHAK", k: 8 }, { chunks: [{ chunk_id: E2.citation.chunk_id, score: 0.71 }] }, 152),
    ],
    answers: {
      b0: { answer: b0, correct: 0 },
      rag: { answer: rag, correct: 1 },
      react: { answer: react, correct: 0 },
    },
    grounded: { answer: loupe, correct: 1 },
  };
}

// ---------------------------------------------------------------- UnitedHealth cyber incident (8-K 1.05)

function unhScenario(): Scenario {
  const E1 = evidence("E1", "chunk", UNH_8K.incidentPassage, chunkCite(UNH_8K.id, UNH_8K.incidentStart, UNH_8K.incidentPassage, UNH_8K.url));
  const E2 = evidence(
    "E2",
    "fact",
    "Event · UNH · 8-K Item 1.05 Material Cybersecurity Incidents · filed 2024-02-22 · quote matched (score 0.98) · quality 5/5",
    cite({ fact_id: "event:UNH:2024-02-22:1.05", doc_id: UNH_8K.id, url: UNH_8K.url }),
  );
  const E3 = evidence("E3", "chunk", UNH_10K.costPassage, chunkCite(UNH_10K.id, UNH_10K.costStart, UNH_10K.costPassage, UNH_10K.url));
  const ledger = [E1, E2, E3];

  const claims = [
    claim("UnitedHealth reported the incident in an 8-K under Item 1.05, Material Cybersecurity Incidents [E2].", true, ledger),
    claim("It said that on February 21, 2024 a suspected nation-state associated threat actor gained access to some of Change Healthcare's IT systems, and that it isolated the impacted systems on detection [E1].", true, ledger),
    claim("Its 2024 annual report describes business disruption impacts and direct response costs from the attack [E3].", true, ledger),
    claim("The cited filings do not give one total 2024 cost figure, so I am not stating one.", null, ledger),
  ];
  const loupe = answer(joinText(claims), claims, ledger);

  const b0Claims = [
    claim("UnitedHealth disclosed in March 2024 that hackers had stolen data on 45 million members.", false, []),
    claim("The company recorded a $1.6 billion charge for the attack in the first quarter of 2024.", false, []),
  ];
  const b0 = answer(joinText(b0Claims), b0Claims, []);

  const ragLedger = [evidence("E1", "chunk", E1.text, E1.citation)];
  const ragClaims = [
    claim("On February 21, 2024, UnitedHealth identified that a suspected nation-state associated actor had accessed some Change Healthcare systems [E1].", true, ragLedger),
    claim("The company isolated the impacted systems and expected the disruption to be resolved within days.", false, ragLedger),
  ];
  const rag = answer(joinText(ragClaims), ragClaims, ragLedger);

  return {
    id: "unh",
    itemId: "loupe-gold:event-UNH-1.05",
    question: "What did UnitedHealth disclose about the Change Healthcare cyberattack, and when did it happen?",
    match: /unitedhealth|\bunh\b|change healthcare|cyber/i,
    tools: [
      toolStep("list_events", { company: "UNH", items: ["1.05"], start: "2023-01-01", end: "2025-12-31" }, { events: [E2.citation.fact_id] }, 28),
      toolStep("search_filings", { query: "Change Healthcare cyberattack disclosure", company: "UNH", k: 8 }, { chunks: [{ chunk_id: E1.citation.chunk_id, score: 0.88 }, { chunk_id: E3.citation.chunk_id, score: 0.64 }] }, 171),
    ],
    answers: {
      b0: { answer: b0, correct: 0 },
      rag: { answer: rag, correct: 0.75 },
    },
    grounded: { answer: loupe, correct: 1 },
  };
}

export const SCENARIOS: Scenario[] = [amdScenario(), shakScenario(), unhScenario()];

export const SUGGESTED_QUESTIONS = SCENARIOS.map((s) => s.question);

// ---------------------------------------------------------------- generated numeric answers

function numericScenario(item: EvalItem): Scenario | null {
  const ticker = item.companies[0];
  if (item.kind !== "numeric" || !ticker || item.answer_value === null || !item.fiscal_year) return null;
  const row = VALUE_TABLE.find(([t]) => t === ticker);
  if (!row) return null;
  const [, label, concept, values] = row;
  const name = SHORT_NAME[ticker] ?? ticker;
  const fy = item.fiscal_year;
  const v = values[fy];
  if (v === undefined) return null;
  const url = `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${CIK[ticker] ?? ticker}&type=10-K`;
  const fact = (id: string, year: number, value: number) =>
    evidence(id, "fact", `${concept} · ${ticker} · FY${year} = ${(value * 1e6).toLocaleString("en-US")} USD`, cite({ fact_id: `${ticker}:${concept}:FY${year}`, url }), value * 1e6);
  const money = (m: number) => `$${Math.round(m).toLocaleString("en-US")} million`;
  const seed = item.item_id;

  const isGrowth = item.answer_unit === "%";
  const prevYear = fy - 1;
  const prev = values[prevYear];

  let ledger: Evidence[];
  let claims: Claim[];
  let tools: TraceStep[];
  let charts: Chart[] = [];
  if (isGrowth && prev !== undefined) {
    const g = ((v - prev) / prev) * 100;
    const E1 = fact("E1", prevYear, prev);
    const E2 = fact("E2", fy, v);
    const E3 = evidence("E3", "calc", `growth(${v}, ${prev}) = ${(g / 100).toFixed(4)} → ${g.toFixed(1)}%`, cite(), g / 100);
    ledger = [E1, E2, E3];
    claims = [
      claim(`${name}'s ${label} went from ${money(prev)} in fiscal ${prevYear} [E1] to ${money(v)} in fiscal ${fy} [E2].`, true, ledger),
      claim(`That is a change of ${g >= 0 ? "+" : ""}${g.toFixed(1)}% [E3].`, true, ledger),
    ];
    tools = [
      toolStep("get_facts", { company: ticker, concept, fiscal_years: [prevYear, fy] }, { facts: [E1.text, E2.text] }, 40),
      toolStep("calc", { op: "growth", new: v * 1e6, old: prev * 1e6 }, { value: g / 100 }, 3),
    ];
    charts = [barChart(`${name} ${label}, FY${prevYear}–FY${fy}`, [`FY${prevYear}`, `FY${fy}`], [prev / 1000, v / 1000], ["E1", "E2"], "USD billions")];
  } else {
    const E1 = fact("E1", fy, v);
    ledger = [E1];
    claims = [claim(`${name}'s ${label} for fiscal ${fy} was ${money(v)} [E1].`, true, ledger)];
    tools = [toolStep("get_facts", { company: ticker, concept, fiscal_years: [fy] }, { facts: [E1.text] }, 38)];
  }
  const grounded = answer(joinText(claims), claims, ledger, { charts });

  // B0 is right from memory a quarter of the time; otherwise it is off by 4–15%.
  const r = hash01(seed, "b0");
  const off = r < 0.25 ? 0 : (r < 0.6 ? -1 : 1) * (0.04 + 0.11 * hash01(seed, "b0-off"));
  const b0Val = v * (1 + off);
  const b0Text = isGrowth && prev !== undefined
    ? `${name}'s ${label} grew by roughly ${(((b0Val - prev) / prev) * 100).toFixed(0)}% in fiscal ${fy}.`
    : `${name} reported ${label} of approximately $${(b0Val / 1000).toFixed(1)} billion in fiscal ${fy}.`;
  const b0Claims = [claim(b0Text, off === 0 ? true : false, [])];
  const b0 = answer(b0Text, b0Claims, []);

  return {
    id: `num:${item.item_id}`,
    itemId: item.item_id,
    question: item.question,
    match: /$^/,
    tools,
    answers: { b0: { answer: b0, correct: off === 0 ? 1 : 0 } },
    grounded: { answer: grounded, correct: 1 },
  };
}

// ---------------------------------------------------------------- run builder

const NO_FIXTURE =
  "Mock mode has hand-written answers for three questions (AMD revenue, the Shake Shack Chapter 11 trick question, the UnitedHealth cyberattack) and generated answers for numeric dataset items. Pick one of those to see a full answer.";

const MODEL_ERRORS: Record<string, string> = {
  "nim-llama-70b": "AuthenticationError: NVIDIA_NIM_API_KEY is not set (add it to .env; see .env.example)",
  "ollama-llama-8b": "APIConnectionError: could not connect to Ollama at http://localhost:11434 (is `ollama serve` running?)",
};

/** Small local models sometimes mangle a number when nothing checks them. */
function degradeForSmallModel(a: ArmAnswer, arm: string, model: string, seed: string): ArmAnswer {
  if (!model.startsWith("ollama") || arm === "loupe" || arm === "b0") return a;
  if (hash01(seed, arm, model, "slip") > 0.35) return a;
  const idx = a.answer.claims.findIndex((c) => /\$[\d,]+ million|\d+\.\d%/.test(c.text));
  if (idx < 0) return a;
  const claims = a.answer.claims.map((c, i) =>
    i === idx
      ? {
          ...c,
          text: c.text
            .replace(/\$([\d,]+) million/, (_m, n: string) => `$${n} billion`)
            .replace(/(\d+\.\d)%/, (_m, n: string) => `${(Number(n) * 1.8).toFixed(1)}%`),
          supported: false,
          citations: c.citations.map((ct) => ({ ...ct, verified: false })),
        }
      : c,
  );
  return { answer: { ...a.answer, claims, text: joinText(claims) }, correct: 0 };
}

export function findScenario(question: string | null, itemId: string | null): Scenario | null {
  if (itemId) {
    const byItem = SCENARIOS.find((s) => s.itemId === itemId);
    if (byItem) return byItem;
    const item = ITEM_BY_ID[itemId];
    if (item) return numericScenario(item);
    return null;
  }
  if (!question) return null;
  const q = question.trim().toLowerCase();
  const exact = SCENARIOS.find((s) => s.question.toLowerCase() === q);
  if (exact) return exact;
  const numeric = Object.values(ITEM_BY_ID).find((i) => i.question.toLowerCase() === q);
  if (numeric) {
    const s = numericScenario(numeric);
    if (s) return s;
  }
  return SCENARIOS.find((s) => s.match.test(question)) ?? null;
}

export interface MockRunInput {
  question: string | null;
  itemId: string | null;
  arm: string;
  model: string;
  /** Distinguishes repeated runs (run_id only). */
  salt?: string;
}

export function buildRun({ question, itemId, arm, model, salt = "" }: MockRunInput): RunResult {
  const item = itemId ? ITEM_BY_ID[itemId] : undefined;
  const q = question ?? item?.question ?? "";
  const seed = `${itemId ?? q}|${arm}|${model}`;
  const run_id = `r_${hashHex(seed, salt)}${hashHex(salt, seed).slice(0, 4)}`;
  const gold = item?.answer ? { answer: item.answer, correct: null as number | null } : null;

  const modelError = MODEL_ERRORS[model];
  if (modelError) {
    return { run_id, arm, model, question: q, answer: emptyAnswer(), tokens: 0, latency_ms: 0, cost_usd: 0, gold, error: modelError };
  }

  const scenario = findScenario(question, itemId);
  let chosen: ArmAnswer;
  let tools: TraceStep[];
  if (!scenario) {
    chosen = { answer: answer(NO_FIXTURE, [], [], { abstained: true }), correct: null };
    tools = [];
  } else {
    const explicit = scenario.answers[arm as Arm];
    const base = explicit ?? scenario.grounded;
    // Only Loupe draws charts; other arms do not call make_chart.
    const ans: Answer = arm === "loupe" ? base.answer : { ...base.answer, charts: [] };
    chosen = degradeForSmallModel({ answer: ans, correct: base.correct }, arm, model, seed);
    tools = arm === "loupe" ? scenario.tools : scenario.tools.filter((t) => t.name !== "make_chart");
  }

  const trace = armTrace(arm, model, seed, q, tools, chosen.answer);
  const full: Answer = { ...chosen.answer, trace };
  const t = totals(trace);
  return {
    run_id,
    arm,
    model,
    question: q,
    answer: full,
    ...t,
    gold: gold ? { ...gold, correct: chosen.correct } : null,
    error: null,
  };
}
