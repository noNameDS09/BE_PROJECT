import type { ArmInfo, CompanyInfo, ModelInfo } from "../../api/types";

export const ARMS: ArmInfo[] = [
  { name: "b0", label: "B0 · Closed book", description: "The model alone: no retrieval, no tools. Baseline that shows hallucination." },
  { name: "rag", label: "O1 · Single-shot RAG", description: "Retrieve the top-k passages once, answer in one call." },
  { name: "react", label: "O2 · ReAct", description: "Think → act → observe loop over the shared tool set (Yao et al., ICLR 2023)." },
  { name: "plan_execute", label: "O3 · Plan-and-Execute", description: "Plan every tool call up front, then execute (Wang et al., ACL 2023; ReWOO)." },
  { name: "router", label: "O4 · FARE router", description: "Route the question to one specialist agent (FARE, IEEE Access 2026)." },
  { name: "self_refine", label: "O5 · Self-Refine", description: "ReAct plus a critic pass that revises the answer once (Madaan et al., NeurIPS 2023)." },
  { name: "loupe", label: "Loupe", description: "Router + selective planner + tools + code verifier + abstain. This project." },
];

export const MODELS: ModelInfo[] = [
  { alias: "groq-llama-70b", provider: "groq", available: true },
  { alias: "gemini-flash", provider: "gemini", available: true },
  { alias: "gemini-flash-lite", provider: "gemini", available: true },
  { alias: "or-qwen-72b", provider: "openrouter", available: true },
  { alias: "or-llama-70b", provider: "openrouter", available: true },
  { alias: "nim-llama-70b", provider: "nvidia_nim", available: false },
  { alias: "ollama-qwen-7b", provider: "ollama", available: true },
  { alias: "ollama-llama-8b", provider: "ollama", available: false },
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
