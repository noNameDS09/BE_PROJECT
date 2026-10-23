import type { ArmInfo, CompanyInfo, ModelInfo, OpenRouterModel, Toolset } from "../../api/types";

/** Tool names per toolset, as /api/config reports them (decision D21). */
const GENERIC_TOOLS = ["search_filings", "calculate", "list_companies"];
const HARNESS_TOOLS = [
  "search_filings",
  "get_financial_metric",
  "compare_companies",
  "make_chart",
  "forecast_metric",
  "distress_score",
  "list_events",
  "calculate",
  "list_companies",
];

function toolset(name: Toolset): Pick<ArmInfo, "toolset" | "tools"> {
  return { toolset: name, tools: name === "none" ? [] : name === "generic" ? [...GENERIC_TOOLS] : [...HARNESS_TOOLS] };
}

export const ARMS: ArmInfo[] = [
  { name: "b0", label: "B0 · Closed book", description: "The model alone: no retrieval, no tools. Baseline that shows hallucination.", ...toolset("none") },
  { name: "rag", label: "O1 · Single-shot RAG", description: "Retrieve the top-k passages once, answer in one call.", ...toolset("none") },
  { name: "react", label: "O2 · ReAct", description: "Think → act → observe loop over the generic tools (Yao et al., ICLR 2023).", ...toolset("generic") },
  { name: "plan_execute", label: "O3 · Plan-and-Execute", description: "Plan every tool call up front, then execute (Wang et al., ACL 2023; ReWOO).", ...toolset("generic") },
  { name: "router", label: "O4 · FARE router", description: "Route the question to one specialist agent (FARE, IEEE Access 2026).", ...toolset("generic") },
  { name: "self_refine", label: "O5 · Self-Refine", description: "ReAct plus a critic pass that revises the answer once (Madaan et al., NeurIPS 2023).", ...toolset("generic") },
  { name: "loupe", label: "Loupe", description: "Router + selective planner + financial tool harness + code verifier + abstain. This project.", ...toolset("harness") },
  { name: "loupe-no-router", label: "Loupe minus router", description: "Loupe without the intent router.", ...toolset("harness") },
  { name: "loupe-no-planner", label: "Loupe minus planner", description: "Loupe without the selective planner.", ...toolset("harness") },
  { name: "loupe-no-verifier", label: "Loupe minus code verifier", description: "Loupe without the code verifier.", ...toolset("harness") },
  { name: "loupe-no-critic", label: "Loupe minus critic", description: "Loupe without the critic pass.", ...toolset("harness") },
  { name: "loupe-no-abstain", label: "Loupe minus abstain", description: "Loupe without the abstain policy.", ...toolset("harness") },
  {
    name: "loupe-generic-tools",
    label: "Loupe minus harness (generic tools)",
    description: "Loupe's orchestration with only the baselines' generic tools.",
    ...toolset("generic"),
  },
];

export const MODELS: ModelInfo[] = [
  { alias: "nim-nemotron-super", provider: "nvidia_nim", model: "nvidia_nim/nvidia/nemotron-3-super-120b-a12b", available: true },
  { alias: "groq-llama-70b", provider: "groq", model: "groq/llama-3.3-70b-versatile", available: true },
  { alias: "gemini-flash", provider: "gemini", model: "gemini/gemini-2.5-flash", available: true },
  { alias: "gemini-flash-lite", provider: "gemini", model: "gemini/gemini-2.5-flash-lite", available: true },
  { alias: "or-qwen-72b", provider: "openrouter", model: "openrouter/qwen/qwen-2.5-72b-instruct:free", available: true },
  { alias: "or-llama-70b", provider: "openrouter", model: "openrouter/meta-llama/llama-3.3-70b-instruct:free", available: true },
  { alias: "nim-llama-70b", provider: "nvidia_nim", model: "nvidia_nim/meta/llama-3.3-70b-instruct", available: false },
  { alias: "ollama-qwen-7b", provider: "ollama", model: "ollama_chat/qwen2.5:7b-instruct", available: true },
  { alias: "ollama-llama-8b", provider: "ollama", model: "ollama_chat/llama3.1:8b", available: false },
];

function openrouter(id: string, name: string, context_length: number | null, tools: boolean): OpenRouterModel {
  return { alias: `openrouter/${id}`, id, name, context_length, tools, free: true };
}

/** GET /api/openrouter/models: OpenRouter's free models, tool-calling models first. */
export const OPENROUTER_MODELS: OpenRouterModel[] = [
  openrouter("google/gemma-4-31b-it:free", "Google: Gemma 4 31B (free)", 262144, true),
  openrouter("nvidia/nemotron-3-super-120b-a12b:free", "NVIDIA: Nemotron 3 Super (free)", 262144, true),
  openrouter("qwen/qwen3-235b-a22b:free", "Qwen: Qwen3 235B A22B (free)", 131072, true),
  openrouter("meta-llama/llama-3.3-70b-instruct:free", "Meta: Llama 3.3 70B Instruct (free)", 131072, true),
  openrouter("deepseek/deepseek-r1-0528:free", "DeepSeek: R1 0528 (free)", 163840, false),
  openrouter("cognitivecomputations/dolphin-mistral-24b-venice-edition:free", "Venice: Uncensored (free)", 32768, false),
];

/** The 25-company US universe (configs/companies_us.yaml). */
export const COMPANIES: CompanyInfo[] = [
  { id: "PEP", name: "PEPSICO INC", sector: "Consumer Staples", group: "financebench", split: "test" },
  { id: "AMCR", name: "Amcor plc", sector: "Materials", group: "financebench", split: "test" },
  { id: "JNJ", name: "JOHNSON & JOHNSON", sector: "Health Care", group: "financebench", split: "test" },
  { id: "MMM", name: "3M CO", sector: "Industrials", group: "financebench", split: "dev" },
  { id: "AMD", name: "ADVANCED MICRO DEVICES INC", sector: "Information Technology", group: "financebench", split: "dev" },
  { id: "BBY", name: "BEST BUY CO INC", sector: "Consumer Discretionary", group: "financebench", split: "test" },
  { id: "BA", name: "BOEING CO", sector: "Industrials", group: "financebench", split: "test" },
  { id: "AXP", name: "AMERICAN EXPRESS CO", sector: "Financials", group: "financebench", split: "test" },
  { id: "MGM", name: "MGM Resorts International", sector: "Consumer Discretionary", group: "financebench", split: "test" },
  { id: "PFE", name: "PFIZER INC", sector: "Health Care", group: "financebench", split: "test" },
  { id: "ULTA", name: "Ulta Beauty, Inc.", sector: "Consumer Discretionary", group: "financebench", split: "dev" },
  { id: "ADBE", name: "ADOBE INC.", sector: "Information Technology", group: "financebench", split: "test" },
  { id: "JPM", name: "JPMORGAN CHASE & CO", sector: "Financials", group: "financebench", split: "test" },
  { id: "VZ", name: "VERIZON COMMUNICATIONS INC", sector: "Communication Services", group: "financebench", split: "dev" },
  { id: "CVS", name: "CVS HEALTH Corp", sector: "Health Care", group: "financebench", split: "dev" },
  { id: "ADM", name: "Archer-Daniels-Midland Co", sector: "Consumer Staples", group: "event", split: "test" },
  { id: "UNH", name: "UNITEDHEALTH GROUP INC", sector: "Health Care", group: "event", split: "test" },
  { id: "DBD", name: "DIEBOLD NIXDORF, Inc", sector: "Information Technology", group: "event", split: "test" },
  { id: "SHAK", name: "Shake Shack Inc.", sector: "Consumer Discretionary", group: "event", split: "test" },
  { id: "SAH", name: "SONIC AUTOMOTIVE INC", sector: "Consumer Discretionary", group: "event", split: "test" },
  { id: "ECHO", name: "EchoStar CORP", sector: "Communication Services", group: "event", split: "test" },
  { id: "KR", name: "KROGER CO", sector: "Consumer Staples", group: "event", split: "dev" },
  { id: "RIG", name: "Transocean Ltd.", sector: "Energy", group: "event", split: "test" },
  { id: "CMP", name: "COMPASS MINERALS INTERNATIONAL INC", sector: "Materials", group: "event", split: "dev" },
  { id: "BFH", name: "BREAD FINANCIAL HOLDINGS, INC.", sector: "Financials", group: "event", split: "dev" },
];

export const COMPANY_BY_ID: Record<string, CompanyInfo> = Object.fromEntries(COMPANIES.map((c) => [c.id, c]));

/** Display names used in generated answers. */
export const SHORT_NAME: Record<string, string> = {
  PEP: "PepsiCo",
  AMCR: "Amcor",
  JNJ: "Johnson & Johnson",
  MMM: "3M",
  AMD: "AMD",
  BBY: "Best Buy",
  BA: "Boeing",
  AXP: "American Express",
  MGM: "MGM Resorts",
  PFE: "Pfizer",
  ULTA: "Ulta Beauty",
  ADBE: "Adobe",
  JPM: "JPMorgan Chase",
  VZ: "Verizon",
  CVS: "CVS Health",
  ADM: "ADM",
  UNH: "UnitedHealth",
  DBD: "Diebold Nixdorf",
  SHAK: "Shake Shack",
  SAH: "Sonic Automotive",
  ECHO: "EchoStar",
  KR: "Kroger",
  RIG: "Transocean",
  CMP: "Compass Minerals",
  BFH: "Bread Financial",
};

export const CIK: Record<string, string> = {
  AMD: "2488",
  UNH: "731766",
  SHAK: "1620533",
  PEP: "77476",
  JNJ: "200406",
  ADBE: "796343",
  JPM: "19617",
  BBY: "764478",
  ULTA: "1403568",
  VZ: "732712",
  PFE: "78003",
  KR: "56873",
  CVS: "64803",
  BA: "12927",
  AXP: "4962",
  MGM: "789570",
};
