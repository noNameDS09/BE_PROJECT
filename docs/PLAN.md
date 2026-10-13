# Loupe: Research and Build Plan (v2)

## Context

Loupe is a cited financial-risk copilot. It extracts risk events from company filings and answers questions in chat with text, charts, comparisons and forecasts. Every claim cites its source, and every number is computed by code.

The project title promises **agent orchestration**, so the central research claim is that our orchestration beats both plain LLMs and published orchestration methods. Accuracy, hallucination rate and cost are measured stage by stage on public benchmarks and on AI-built, citation-verified golden datasets.

**Order:**
1. US: about 25 companies, built fast, tested on free-tier models.
2. India: swap in data for 10–20 companies.

**Where:** `Loupe/` repo only (github.com/noNameDS09/BE_PROJECT). The old skeleton and plans can be deleted. There are no calendar dates; each phase ends with a "done when".

## Decisions taken (from Q&A, 13 Oct 2026)

| Topic | Decision |
|---|---|
| Outcome | Event extraction plus chat on top of the events table; charts, comparisons, predictions |
| Prediction | All three: metric trend projections, distress score, and a price-forecast experiment (never buy/sell advice) |
| Universe | 25 US companies, about 15 overlapping FinanceBench, the rest chosen for notable risk events; later 10–20 Indian companies |
| Time window | FY2023–25 for our corpus and gold sets, plus the specific older filings that benchmark questions need |
| Datasets | Use as many public datasets as possible; add our own domain-precise sets for what they don't cover |
| Gold data creation | Built by AI (strongest model, with search tools), every item cited and checked by code, cross-checked by a second model, ~5% audited by humans |
| Orchestration comparison | Core 4 (single-shot RAG, ReAct, Plan-and-Execute/ReWOO, FARE-style router) plus Critic/Self-Refine, against **our design, fixed before any experiments** |
| UI | React + FastAPI. A Bench UI for the team and the guide/examiners, plus a chat view |
| LLMs | Free tiers: Gemini, OpenRouter, Groq, NVIDIA NIM, local Ollama; budget being requested |
| Transcripts (US) | Skipped. Earnings releases (8-K EX-99.1) and MD&A are used instead |

## Research questions

| # | Question | How it's answered |
|---|---|---|
| RQ1 | How badly do plain LLMs answer company-specific financial questions (wrong numbers, invented events, no refusal)? | B0 (no retrieval) on all sets |
| RQ2 | **Does our orchestration beat published ones** at the same model, retrieval, tools and token budget? | O1–O5 vs Ours |
| RQ3 | Which component of our orchestration matters most? | Ablate router, planner, tools, verifier and critic one at a time |
| RQ4 | Which retrieval and data stages matter? | Chunking, embeddings, hybrid search, reranker, top-k |
| RQ5 | Do results hold across models (small local vs 70B-class vs Gemini)? | Model sweep on the core subset |
| RQ6 | How good is event extraction, and is the second-pass quality score calibrated? | Event P/R/F1, precision by score bin |
| RQ7 | Do forecasts beat naive baselines? | Backtests |
| RQ8 | Does the pipeline transfer to Indian disclosures? | Same harness on India data |

## Orchestration arms (one LLM, retriever, toolset and token cap shared by all)

| Arm | Method | Source |
|---|---|---|
| B0 | Model alone, no retrieval | Hallucination baseline |
| O1 | Single-shot RAG: retrieve top-k, answer | Standard RAG |
| O2 | ReAct: think → tool → observe loop | Yao et al., ICLR 2023 |
| O3 | Plan-and-Execute / ReWOO: plan every tool call up front, then execute and solve | Wang et al., ACL 2023; Xu et al. 2023 |
| O4 | Router → one specialist agent (single intent) | FARE, IEEE Access 2026 (our base paper) |
| O5 | O2 plus a Self-Refine critic (generate → critique → revise) | Madaan et al. 2023; Fatemi & Hu, ICAIF 2024 |
| **Ours** | Design fixed in advance (below) | — |

**Code-as-action is a second dimension crossed with every arm.** Tools on means numbers come from code; tools off means the LLM does the arithmetic. Program-of-Thought shows about +20 points on FinQA, so this is likely the largest single effect.

**Our orchestration (fixed before experiments, "Loupe-Orch v1"):**
1. **Intent router.** Classifies the question as lookup, calc, compare, event, trend/forecast, chart or open analysis. Unlike FARE, one question can have several intents.
2. **Planner.** Writes a ReWOO-style typed plan only for multi-step questions; simple ones skip straight to execution.
3. **Executors.** Deterministic tools and retrieval filtered by company and period.
4. **Composer.** Writes the answer, linking each claim to its evidence ids.
5. **Verifier.** Code checks every quote and number against the source. An LLM critic flags unsupported claims, with at most one revision.
6. **Abstain.** If evidence is insufficient, the answer says so instead of guessing.

**Hypotheses** (recorded before any run):
- H1: Ours beats every arm on numeric accuracy and hallucination rate at no more than O3's cost.
- H2: The verifier gives the largest drop in hallucination.
- H3: Tools give the largest numeric gain.
- H4: The router cuts cost compared with ReAct.

Debate, FinCon and TradingAgents are cited, not rebuilt: they are trading-oriented and expensive.

## Data needed

**US (FY2023–25, 25 companies):**
- EDGAR submissions API (filing index), 10-K, 10-Q and 8-K with exhibits (EX-99.1 earnings releases)
- XBRL company facts (exact numbers)
- 8-K item codes (free event labels)
- SEC ticker↔CIK file
- Free daily prices
- The FinanceBench source PDFs for its questions on our companies

All free. Requests need a User-Agent with an email and at most 10 requests/s.

**India (later, 10–20 companies):**
- ISIN master; NSE announcements (JSON + PDF) with category labels
- XBRL results and shareholding/pledges; insider-trading data
- Annual reports and earnings-call transcripts (PDF, filed with the exchange)
- Rating actions (via announcements); bhavcopy prices

Cleaning: identity table keyed by ISIN → structured sources first → PDF triage (text / tables / OCR) → one common format → lakh/crore normalisation → deduplication by hash.

## Datasets

The harness has two modes:
- **Corpus mode:** questions about our 25-company index.
- **Bring-your-own-docs mode:** each question ships with its own documents, which are indexed on the fly. This is needed for DocFinQA, FinDER and FailSafeQA.

### Public datasets adopted (verified 13 Oct)

| Dataset | Open size | Tests | Mode | Licence | Fit / caveat |
|---|---|---|---|---|---|
| FinanceBench | 150 | Retrieval + QA on real 10-K/10-Q/8-K, page evidence | Corpus (+ its PDFs) | CC-BY-NC | Best fit; mostly FY2015–22 filings |
| FinDER | 5,703 | Retrieval against gold passages, analyst-style queries | Bring-own | CC-BY-NC | Best pure retrieval test |
| DocFinQA | 922 test | Long-filing numeric QA (avg 123k words) | Bring-own | MIT | Old years (≤2019); seeded subsample |
| ConvFinQA | dev set | Multi-turn numeric chat | Bring-own | MIT | Tests chat follow-ups |
| FinQA / TAT-QA | test sets | Calculator and code-as-action module | Bring-own | MIT / CC BY | Retrieval is trivial; numeric reasoning only |
| Finance Agent Benchmark | 50 (v1) + 27 (v2) public | Agent tool use on EDGAR | Own harness | CC-BY-4.0 | Small; results are indicative only |
| FailSafeQA | 220 | Hallucination and refusal under bad or missing context | Bring-own | MIT | Ready-made robustness test |
| SECQUE | 565 | Analyst-style comparison, ratio and risk questions | Bring-own | MIT (eval only) | Sample |
| 8-K item codes | All our 8-Ks | Event type labels | Corpus | Public | Labels only, no quotes |
| India: IndFin-Bench, IndiaFinBench | 100, 406 | Indian filings QA; SEBI/RBI regulation QA | Bring-own | CC-BY-NC, CC-BY | Small or vendor-made pilots only |

**Gaps that no public dataset covers:** FY2023–25 questions on our companies, verified event quotes, comparisons, charts, false-premise questions, plan/tool-route labels, forecasting, and anything Indian. These become Loupe-Gold.

### Loupe-Gold (AI-built, cited, verified)

| Set | Target size | Built from |
|---|---|---|
| Gold-Num | ~300 | XBRL facts, answers set by code (no LLM) |
| Gold-Calc | ~150 | XBRL multi-period growth, margins and ratios; answers by code |
| Gold-Event | ~250 8-Ks | Item code label + extracted fields + verbatim quote |
| Gold-Compare | ~60 | Multi-company questions; numbers from XBRL, narrative from cited sections |
| Gold-Chart | ~40 | Chart requests; expected data series from XBRL |
| Gold-Trick | ~120 | False premises, invented events, future periods, wrong company; expected answer is a refusal or correction |
| Gold-Plan | ~200 | Questions with the expected intents and tool sequence (scores the router and planner) |
| Gold-Multiturn | ~40 conversations | Follow-ups with coreference |
| Gold-Forecast | backtest | Held-out last 4 quarters of metrics; held-out price window |

**Creation protocol** (written into each set's dataset card):
1. The generator is the strongest available model with EDGAR and web search. It **is never one of the evaluated models**, which avoids self-preference.
2. Every item stores: source URL, accession, form, section, verbatim quote, character offsets, and the answer's derivation.
3. Code checks that each quote is in the filing, each number matches XBRL within a stated tolerance, and periods and units are consistent. Failures are dropped.
4. A model from a different family re-answers each item from its evidence. Disagreements are dropped or flagged.
5. A random 5% sample is audited by the team (about 1–2 hours) and the error rate is reported with a confidence interval.
6. Sets are versioned in `data/gold/` and split dev/test by company (8 dev / 17 test). Test items are used only in final runs.

## Experiment design (sized for free tiers)

- **Core subset:** about 300 seeded questions drawn across all sets. Runs the full matrix: B0 + O1–O5 + Ours, tools on/off, on 2 models.
- **Full sets:** Ours vs the two best arms on 1–2 models.
- **Model sweep:** Ours and B0 on the core subset, on 4 models (small local, 70B-class, Gemini Flash-class, Qwen-class).
- **Ablations:** one component or stage at a time from Ours, on the core subset, 1 model.
- **Controls:**
  - temperature 0
  - the same top-k and token cap for every arm
  - every call cached
  - config hash on every result row
  - cost, latency, tokens and step count per row
- **Statistics:** company-cluster bootstrap 95% CIs, paired tests between arms, Holm correction. Anything added after the hypotheses are recorded is labelled exploratory.
- **LLM judge:** used only where exact checking is impossible. A different family from the generator. Its agreement with the human audit is reported.

## System architecture

```
Source adapters (us/, india/) → Common format (Document, Section, Chunk, Fact, Event, Citation)
  → Stores: DuckDB (facts, events, results) + LanceDB (chunks: vector + BM25)
  → Tools: search, facts, calc (code), compare, chart, timeline, trend, distress, price-forecast
  → Orchestrators (B0, O1–O5, Ours; all share one interface)
  → Answer {text, claims→evidence, charts, trace}
  → Eval runner (datasets × arms × models)
  → FastAPI → React app (Bench + Chat)
```

**Stack:**
- Python 3.12 with uv
- edgartools for EDGAR filings, sections and XBRL
- LiteLLM gateway (5 providers, cache, throttling, cost log)
- LangGraph for orchestrators
- sentence-transformers (bge-small, local) and LanceDB
- DuckDB
- statsmodels for forecasts
- Plotly specs for charts
- FastAPI
- React + Vite + TypeScript frontend
- India later: PyMuPDF, Docling, OCR

**Bench UI (React):**
1. **Compare.**
   - Pick any question (from any dataset, or typed) and up to 4 configs (model × orchestration × retrieval).
   - See the answers side by side, with:
     - clickable citations that open the source text
     - a tool/step timeline
     - tokens, cost and latency
     - the gold answer and a correctness badge
   - Runs live, or loads cached results.
2. **Leaderboard.** Scores with CIs, filterable by dataset, stage, model, arm and tools on/off.
3. **Stage view.** A waterfall from B0 to Ours, the ablation table and per-stage metrics.
4. **Dataset explorer.** Browse every gold item with its provenance, verification status and audit result.
5. **Chat.** The product view: cited answers, charts, comparisons, forecasts.

## Repo restructure

**Delete:**
- `src/loupe/{agent,compute,extract,retrieve}/` (their `__init__` files import modules that don't exist)
- `app/`, `eval/`
- old `docs/*` plans and HTML pages (keep the FARE PDF in `docs/papers/`)
- `data/raw/companyfacts/`

**Rewrite:** `pyproject.toml`, `README.md`, `.gitignore`.

```
Loupe/
├── src/loupe/
│   ├── core/          # schemas, settings, registry
│   ├── llm/           # gateway, cache, rate limits, cost log, models.yaml loader
│   ├── sources/us/    # edgar, xbrl, prices       (sources/india/ later)
│   ├── ingest/  index/
│   ├── tools/         # search, facts, calc, compare, chart, timeline, trend, distress, price
│   ├── extract/       # 8-K event extraction, quote validator, 2nd-pass scorer
│   ├── orchestrators/ # b0, rag, react, plan_execute, router, self_refine, loupe
│   ├── datasets/      # loaders for public sets + Loupe-Gold builders and verifiers
│   ├── eval/          # runner, metrics, judge, stats
│   └── api/           # FastAPI
├── web/               # React + Vite + TS (Bench + Chat)
├── configs/           # companies_us.yaml, models.yaml, arms/*.yaml
├── data/              # raw/ processed/ git-ignored; gold/ versioned with dataset cards
├── docs/              # hypotheses.md (pre-registration), decisions.md, research-log.md, significance/
└── tests/
```

## Phases

### P0 · Setup and pre-registration
- Restructure the repo; set up uv, ruff, pytest and pre-commit; add `.env.example`.
- LLM gateway for all 5 providers. `loupe models check` reports for each model: reachable, tool-calling support, JSON mode, rate limit.
- Choose the 25 companies. Starting candidates: about 15 FinanceBench companies still filing (e.g. 3M, Adobe, AMD, Amazon, AmEx, Best Buy, Boeing, Coca-Cola, CVS, J&J, JPMorgan, Lockheed, MGM, Microsoft, Nike, PepsiCo, Pfizer, Verizon, Walmart). The remaining ~10 are found by scanning FY2023–25 8-Ks for items 4.01, 4.02, 2.04, 1.03 and 5.02.
- Write `docs/hypotheses.md`: the Loupe-Orch v1 design, H1–H4, metrics and analysis plan. Commit and tag it.
- **Done when:** the models report and the company list are committed and the hypotheses are tagged in git.

### P1 · US data layer
- EDGAR adapter, XBRL Facts, prices, FinanceBench PDFs for our companies.
- Sections → chunks → index. Coverage report.
- **Done when:** coverage is at least 95% and `loupe search` returns cited chunks for every company.

### P2 · Thin end-to-end and Bench skeleton
- Tools: search, facts, calc. Orchestrators: B0, O1, Ours (minimal version).
- FastAPI `POST /runs`, `GET /runs/{id}`, `GET /configs`. React Compare view with 2 configs side by side.
- **Done when:** a question runs on B0 vs Ours across 2 models in the Bench, showing the trace and citations.

### P3 · All arms, full toolset, event extraction
- O2–O5 on the shared interface. Tools: compare, chart, timeline, trend, distress, price-forecast.
- 8-K event extraction with the quote validator and second-pass scorer. Chat view with charts.
- **Done when:** every arm answers the same 10 questions, and each tool passes unit tests against hand-checked values.

### P4 · Datasets (can start in parallel with P1)
- Loaders for every public set in both modes. Seeded subsamples.
- Loupe-Gold builders run with the creation protocol. Dataset cards. 5% audit.
- Dataset explorer view.
- **Done when:** every set loads in the runner, Loupe-Gold has passed verification, and the audit error rate is reported.

### P5 · Experiments
- Core matrix, full sets, model sweep, ablations, forecast backtests.
- Leaderboard and Stage views.
- A gallery of real B0 hallucinations with the correct cited answers.
- **Done when:** every pre-registered hypothesis has a result with CIs in the Bench, and `research-log.md` covers every run.

### P6 · India swap
- India adapters plus the 5-company data test (scanned-PDF share, parse failure rate).
- India tools: pledge %, related-party ratios. India Loupe-Gold built with the same protocol, plus IndFin-Bench as a pilot.
- **Done when:** the same matrix runs on India data and appears in the Bench.

### Parallel track · Significance
`docs/significance/` covers:
- the industry problem (analyst time, scattered disclosures, LLM hallucination risk)
- user personas
- the competitor comparison
- what we solve and how

It is updated with real numbers from P5 and feeds the report, slides and demo.

## Workstreams

| Stream | Owns |
|---|---|
| A · Data | sources, ingest, index, coverage; India adapters |
| B · Orchestration & tools | gateway, all arms, Loupe-Orch, tools, event extraction, prediction |
| C · Evaluation | dataset loaders, Loupe-Gold pipeline (with Claude), runner, metrics, stats, audit |
| D · Bench & story | FastAPI, React Bench + Chat, charts, significance docs, demo |

## Risks

| Risk | Mitigation |
|---|---|
| Free-tier limits make the matrix too big | Core subset plus tiered design; cache; Ollama for dev; full runs only for the best arms |
| AI-built gold data contains errors | Code verification, cross-model check, 5% human audit with reported error rate, generator never evaluated |
| Our arm gets more tuning than the others | Same token cap and the same number of dev tuning rounds for every arm; hypotheses tagged before runs |
| Benchmark years differ from our window | Bring-own-docs mode; results reported per dataset |
| Non-commercial licences | Research use only; noted in dataset cards |
| Weak tool calling on small models | Checked in P0; JSON-mode fallback |
| Indian PDFs worse than expected | Data test first; narrow document types |

## Verification

- `uv run pytest` passes (schemas, adapters, tools, quote validator, metrics).
- `loupe models check`, `loupe ingest --companies dev` (coverage ≥95%), `loupe search ...`
- `loupe run --arm loupe --model <m> "What was AMD's FY2024 gross margin and why did it change?"` returns a cited answer whose numbers match XBRL.
- `loupe eval --set core --arms b0,o1,o2,o3,o4,o5,loupe --models <a>,<b>` writes rows to DuckDB.
- The Bench Compare view shows 4 configs side by side with traces. The Leaderboard shows CIs. The Dataset explorer shows provenance and audit status for each gold item.
