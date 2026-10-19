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
| D11 | 2026-10-13 | US universe frozen at 25 companies (`configs/companies_us.yaml`): 15 FinanceBench companies with the most open questions (118/150), plus 10 risk-event companies (revenue ≥ $1B, FY2023–25 8-K items 1.03/1.05/2.04/2.06/4.01/4.02, chosen to cover every item type and different sectors). 8 dev / 17 test, stratified by sector, seed 20261013. | Benchmark comparability plus real risk events for extraction and trick questions |
| D12 | 2026-10-13 | Corpus window = period of report 2023-01-01..2025-12-31 (10-K/10-Q) and filing date in the same range (8-K, with EX-99.1). Amendments excluded. XBRL facts kept from 2015 onward for trend backtests. | Fixed, reproducible corpus; enough history for forecasting |
| D13 | 2026-10-13 | The SEC contact email lives only in each person's local `.env` (`SEC_USER_AGENT`) and is never committed. | SEC requires a contact; keep personal addresses out of the repo |
| D14 | 2026-10-19 | Search index = section-aware chunks (1,200 chars, 150 overlap; never crossing a section), local embeddings (bge-small-en-v1.5 via fastembed/ONNX, with a short "company · form · period · item" header), exact dense search (NumPy) + BM25 (bm25s), fused with RRF (k=60); filters applied before ranking. Replaces LanceDB in the plan. | At ~124k chunks exact search takes milliseconds, avoids approximate-search recall loss and keeps retrieval reproducible; no GPU or API needed. Chunk size, overlap, embedder and header are ablation variables (RQ4). |
| D15 | 2026-10-19 | Fiscal-year labels for XBRL facts come from each company's own 10-K calendar (majority label offset across its 10-Ks); quarters are numbered by position in the fiscal year; Q4 = FY − 9-month YTD when not reported. | Companies label fiscal years differently (Ulta vs Best Buy) and SEC's `fy` field is wrong in some Kroger filings. |
| D16 | 2026-10-19 | Answers cite evidence ids ([E#]); a code verifier marks each sentence supported only if its numbers match cited evidence (allowing the rounding written) and its quotes appear in cited passages. | Hallucination and citation precision are measured by code, not only by an LLM judge. |
| D17 | 2026-10-19 | The full passage index is embedded once on an NVIDIA GPU (PyTorch, same bge-small-en-v1.5 weights) from the chunks built locally; queries stay on local ONNX. `loupe index check` must show cosine >= 0.99 between GPU and ONNX vectors on a seeded sample before the index is used. ONNX now uses every CPU core (3x faster than its default). | On an M1 CPU the 123,889-chunk embedding takes ~5-6 h (5.4 chunks/s); a GPU does it in minutes. Chunking stays local so chunk ids and offsets used by citations don't change. |
