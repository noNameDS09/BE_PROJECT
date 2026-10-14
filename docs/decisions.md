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
| D11 | 2026-10-14 | EDGAR access uses `edgartools` 5.62, as named in the PLAN.md stack. Version 5 has three behaviours the adapters must work around (D12–D14). | Team stack decision; it is a large but maintained wrapper |
| D12 | 2026-10-14 | Section offsets are section-local, and a citation quote is resolved against the **stored section text**, never against a character range of the whole filing. | edgartools normalises whitespace differently between `document.text()` and `section.text()`, so a section is not a byte-exact slice of the body. Verified on AMD's FY2024 10-K: section text matches the body only after whitespace collapsing, and every reported `start_offset` is 0. Resolving quotes against section-local text is exact; resolving them against whole-document offsets would silently fail. |
| D13 | 2026-10-14 | XBRL facts are reduced to 8 canonical concepts (`Revenue`, `GrossProfit`, `OperatingIncome`, `NetIncome`, `Assets`, `Liabilities`, `StockholdersEquity`, `Cash`), with revenue accepting four tag spellings, and filtered to the FY2023–25 corpus window. | A 10-K carries ~800 us-gaap tags and filers disagree on the revenue tag (AMD has none tagged `Revenues`). Facts outside the window were being returned (2009–2010 rows for AMD), which would let a benchmark answer be drawn from outside D4. |
| D14 | 2026-10-14 | Prices are optional in P1. The Stooq adapter is pluggable and raises `PriceUnavailable`; ingest records the failure and continues. | Both free daily-price sources are unreachable from the dev network (Stooq serves a JavaScript proof-of-work page, Yahoo returns HTTP 429). Losing filing text to a blocked price site would be the wrong trade, since P1's "done when" is cited chunks, not prices. P5's forecast work needs a working provider. |
| D15 | 2026-10-14 | Retrieval is BM25-only in P1, with a dense stage implemented but off by default, and a company filter applied to the **scoring** step rather than by truncating results. | sentence-transformers pulls torch, which P1 does not need; RQ4 enables dense retrieval as an ablation. Filtering after ranking would let another company's chunks consume the top-k slots, so every arm would see a smaller candidate pool than the one the comparison is meant to hold equal. |
| D16 | 2026-10-14 | 8-K risk-event ranking orders items 1.03 ≈ 4.02 > 2.04 > 4.01 > 1.01 > 5.02 ≈ 2.01, then by breadth, then recency. | The universe's second half needs an explicit, reproducible rule (PLAN.md D3). This ordering is a judgement, so it is written down rather than buried in code; changing it changes the universe. |
