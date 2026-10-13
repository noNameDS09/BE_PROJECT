# Decisions log

One row per decision that affects scope or results. Rows are never edited.
A change is a new dated row that names the row it replaces.

| Id | Date | Decision | Reason |
|---|---|---|---|
| D1 | 2026-10-13 | Restart from the problem statement. Previous FARE-replication plans and the code skeleton are removed (they remain in git history on `initialize`). | The team re-scoped to a product-plus-research plan: `docs/PLAN.md` |
| D2 | 2026-10-13 | Outcome: risk-event extraction plus cited chat on top of it, with charts, comparisons and predictions. | Problem statement |
| D3 | 2026-10-13 | US first: 25 companies, about 15 overlapping FinanceBench, the rest chosen for notable 8-K risk events. Then India: 10–20 companies. | Public-benchmark comparability, plus interesting events |
| D4 | 2026-10-13 | Corpus window FY2023–FY2025, plus the specific older filings that public benchmark questions need. | Gold sets mostly post-date model training; benchmarks still answerable |
| D5 | 2026-10-13 | Prediction means: metric trend projections, distress score, and a price-forecast experiment against naive baselines. Never buy/sell advice. | Team choice; credibility |
| D6 | 2026-10-13 | Public datasets first. Loupe-Gold is built by AI with citations, code verification, a cross-model check and a 5% human audit. | Team choice; labelling capacity |
| D7 | 2026-10-13 | Arms: B0, single-shot RAG, ReAct, Plan-and-Execute/ReWOO, FARE-style router, ReAct + Self-Refine, vs Loupe-Orch v1, which is fixed before experiments. | The title promises orchestration; it must be validated |
| D8 | 2026-10-13 | UI: React + FastAPI; a Bench for the team and examiners plus a Chat view. | Team choice |
| D9 | 2026-10-13 | LLMs: free tiers only for now (Gemini, OpenRouter, Groq, NVIDIA NIM, Ollama), behind one cached, throttled gateway. | No budget yet |
| D10 | 2026-10-13 | US earnings-call transcripts skipped; earnings releases (8-K EX-99.1) and MD&A used instead. | No free official source |
