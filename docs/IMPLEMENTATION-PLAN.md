# Loupe Implementation Plan — Phase R: FARE architecture on SEC EDGAR

Status: plan v2 (29 Sep 2026). Supersedes plan v1. No pipeline code written yet.
Scope of this phase: rebuild the FARE multi-agent architecture from the paper, run it on SEC EDGAR filings, evaluate every stage, and expose it through a benchmarking playground.
India work (taxonomy, event extraction, pledge/RPT compute, NSE, personas) moves to Phase I — see the end of this file.

Companion docs: `docs/Loupe-Replication-HLD.html` (design), `docs/fare/01-extraction-sheet.md` (what the paper specifies), `docs/fare/02-claims.md` (what we test).

---

## 1. Locked decisions

| # | Decision | Consequence |
|---|---|---|
| D1 | **Data = SEC EDGAR filings by CIK only.** FARE's 168 transcripts are not reconstructed. | Replication is an architecture transfer. We test whether FARE's *conclusions* hold on filings, not its numbers. |
| D2 | **Universe = the team's 25 companies**, listed in `configs/universe.yaml` (CIK, ticker, name, sector). | List still to be committed (see §8). Fixed for the whole phase. |
| D3 | **Hosted LLM APIs only**, switched through one gateway. | Latency is reported as our own measurement, not comparable with FARE's T4 numbers. |
| D4 | **Six agents, none advisory.** Investment → **Thesis Check**, Simulation → **Scenario** (see §3). | Their FARE metrics (IRAS, EAS) are adapted; documented in `docs/fare/03-decisions.md`. |
| D5 | **Judges are versioned.** `judge-v1-google` follows FARE (Google Search grounding). Later versions add frozen references and objective checks. | System versions are only compared under the same judge version. Judge versions are compared by agreement with human grades. |
| D6 | **Every stage is pluggable.** Each stage has an interface and a registry of named variants; a pipeline is one choice per stage. | Powers ablations and the playground. |
| D7 | **Tracer first.** One thin end-to-end path works before any stage gets a second variant. | See M1. |
| D8 | **Frontend = React from the start** (Vite + TypeScript), talking to a FastAPI backend. | The pipeline is an API; the UI never imports pipeline code. |

---

## 2. What FARE is (from the paper)

- An **Orchestrator** reads the query and routes it to **exactly one** of six agents (single-intent routing, LLM prompt).
- Six agents: Statement Extraction, Tone, Investment, Comparison, Tone Shift, Simulation. Tone has a **critic loop** that checks its answer against Google Search and revises it.
- Retrieval: recursive character split **800 / 100**, **all-MiniLM-L6-v2** (384-d), **FAISS IndexFlatL2**, **top-k = 10**, metadata `chunk_id, company, quarter, year`, batch-wise reading of chunks.
- Role-based **Chain-of-Thought** prompts (not published).
- Evaluation: one **LLM-as-judge** per agent with Google Search references — TAEF (Tone), IRAS (Investment), CAS (Comparison), TAS (Tone Shift), EAS + CODS (Simulation) — plus **RAGAS** Context Precision, Faithfulness and Response Relevancy for Statement Extraction. 544 queries (paper Table 2).
- Four backbones compared on score and latency. Details and page references: `docs/fare/01-extraction-sheet.md`.

---

## 3. The six agents on SEC filings

| Agent | FARE task | Loupe task on EDGAR | Main filings used | Metric |
|---|---|---|---|---|
| Statement Extraction | Factual answer with speaker and quotes | Factual answer with quotes and filing section | 10-K, 10-Q, 8-K | RAGAS CP, F, RR + citation precision |
| Tone | Tone of one quarter's call, critic loop | Tone of one period's MD&A and earnings release, critic loop | 10-K Item 7, 10-Q Item 2, 8-K Item 2.02 EX-99.1 | TAEF |
| Tone Shift | Tone across a range of quarters | Tone across consecutive periods | same as Tone | TAS |
| Comparison | Companies on one topic in one quarter | Same, on filings | 10-K / 10-Q sections | CAS |
| **Thesis Check** (was Investment) | hold / re-evaluate / sell | Does the filing evidence support, weaken or leave open the user's stated reason for holding? Quotes required. No recommendation. | 10-K, 10-Q, 8-K | IRAS adapted (drop recommendation correctness and risk-profile fit) |
| **Scenario** (was Simulation) | Missed opportunity + narrative + guidance | Actual vs hypothetical holding: returns computed by code from prices, narrative from filings. Guidance section dropped. | filings + daily prices | EAS + CODS adapted |

Scenario needs a price-data source (open item §8). Returns and drawdowns are computed deterministically, never by the LLM.

---

## 4. Stages and variants (the registry)

`v0` is the FARE baseline and is built first. Later variants are added one at a time.

| Stage | v0 (FARE) | Planned variants |
|---|---|---|
| Source | EDGAR submissions API, 10-K / 10-Q / 8-K | + XBRL company facts |
| Parse | HTML → clean text | section-aware (10-K/10-Q Items), table-preserving |
| Chunk | recursive, 800 / 100 | section-aware, semantic, 1500 / 200 |
| Embed | all-MiniLM-L6-v2 | bge-small, e5, one hosted embedding API |
| Retrieve | FAISS flat L2, top-10, metadata filter | BM25, hybrid (RRF), + reranker, top-k sweep |
| Route | LLM single-intent | keyword rules, embedding classifier |
| Agents | reconstructed FARE prompts | improved prompts, + tools (XBRL lookup, calculator) |
| Generator | 2–4 hosted models | any model via the gateway |
| Judge | `judge-v1-google` | `v2-frozen-refs`, `v3-objective` (XBRL / price facts), human-calibrated |

Rules:
- A pipeline config names one variant per stage and is stored with a hash; every result row carries that hash.
- Benchmarks change **one stage at a time** from v0, plus a few chosen combinations. No full grid (cost).
- The playground can run any combination live on a single query.

---

## 5. Evaluation

| Set | Contents | Used for |
|---|---|---|
| Q-FARE | Queries per agent following FARE's Table 2 sampling rules, regenerated for our 25 companies and filings | Per-agent FARE metrics, claims test |
| Q-FIN | FinanceBench open sample (check licence) | Statement Extraction, retrieval recall |
| Q-XBRL | Questions generated from XBRL facts, exact answers | Numeric accuracy, tools ablation |
| H-100 | 100 items graded by two team members | Judge-vs-human agreement (κ) |

Baselines: **B0** LLM only · **B1** single-agent RAG (FARE describes but never runs this) · **B2** FARE rebuild · **B3** + tools · **B4** + citation checks.
Reporting: dev/test split frozen and tagged; temperature 0; 95% bootstrap CIs; cost and latency on every row.

---

## 6. Milestones (tracer first)

### M0 — Foundation · week of 5 Oct
- Repo hygiene: fix `pyproject.toml` (add `[build-system]`; remove `sec-api` (paid) and `xbrl`; move pytest/ruff to a dev group; move ruff `select` under `[tool.ruff.lint]`; add `langchain-text-splitters`, `ragas`, `fastapi`, `uvicorn`, `google-genai`, `httpx`); pin Python 3.12 (`.python-version`); `.gitignore` for `data/raw`, caches, `.env`.
- `configs/universe.yaml` with the 25 companies and CIKs.
- Data contracts (Pydantic): `Document`, `Chunk`, `Query`, `RoutedQuery`, `AgentOutput`, `Trace`, `EvalRecord`, `PipelineConfig`.
- Registry interface: `register(stage, name)`, `build(pipeline_config)`.
- FARE docs: finish `01-extraction-sheet.md`, `02-claims.md`, start `03-decisions.md`.
- **Gate:** contracts and registry reviewed by all four; universe committed.

### M1 — Tracer · weeks 2–3 (12–23 Oct)
One path, all v0: EDGAR fetch (25 companies, FY2023–FY2025) → parse → chunk 800/100 → MiniLM → FAISS → LLM router → **Statement Extraction only** → RAGAS → result row in DuckDB.
- FastAPI: `POST /runs` (config + query → trace), `GET /runs/{id}`, `GET /variants`.
- React: one page that sends a query and renders the trace stage by stage.
- **Gate:** one query runs end to end from the UI; one benchmark row exists for Q-FIN dev.

### M2 — Six agents and judge v1 · weeks 4–6 (26 Oct – 13 Nov)
- Remaining five agents, Tone critic loop, Thesis Check and Scenario (non-advisory).
- `judge-v1-google` for TAEF, TAS, CAS, adapted IRAS, adapted EAS/CODS.
- Q-FARE query sets; baselines B0 and B1.
- Human grading of H-100 starts.
- **Gate:** first claims table (`02-claims.md`): each claim holds / partly / does not hold, 2–4 models.

### M3 — Variants and playground · weeks 7–9 (16 Nov – 4 Dec)
- Stage variants from §4, one-factor-at-a-time runs.
- `judge-v2-frozen-refs`; κ for v1 and v2 against H-100.
- React playground: **Benchmark view** (filter by stage, variant, model, judge version) and **Live run view** (pick a variant per stage, run, inspect each stage's output, time and cost).
- **Gate — Semester VII review:** claims table, ablation tables with CIs, playground demo.

### M4 — Extensions · from December
- B3 (tools) and B4 (citation checks), `judge-v3-objective`.
- Write the replication chapter. Then start Phase I.

---

## 7. Workstreams (one per person)

| Stream | Owns | First deliverable |
|---|---|---|
| A · Data & retrieval | sources, parse, chunk, embed, retrieve + their variants | M1 index for 25 companies |
| B · Agents | orchestrator, six agents, prompts, tools, LangGraph graph | M1 router + Statement Extraction |
| C · Evaluation | query sets, judges, RAGAS, baselines, stats, H-100 grading | M1 RAGAS row |
| D · Platform | FastAPI, React playground, results store, tracing, gateway | M1 query-to-trace UI |

---

## 8. Open items

1. Commit the **25-company list** with CIKs (`configs/universe.yaml`).
2. **Price data** source for Scenario and adapted metrics.
3. **Models**: which 2–4 hosted models; check Gemini 2.5 Flash / Flash-Lite are still served; monthly budget.
4. **Adapted metric definitions** for Thesis Check and Scenario (in `03-decisions.md`).
5. **Tone critic ambiguity**: the paper describes the critic as an inference-time feedback loop and also as evaluation-only (p. 67368). Choose and record.

---

## 9. Proposed code layout

```
Loupe/
├── src/loupe/
│   ├── contracts/        # Pydantic data contracts
│   ├── registry.py       # stage registries, pipeline builder
│   ├── sources/          # EDGAR (Phase I: NSE)
│   ├── parse/  chunk/  embed/  retrieve/
│   ├── llm/              # gateway: provider switch, cache, cost log
│   ├── agents/           # orchestrator + six agents (LangGraph)
│   ├── tools/            # XBRL lookup, calculator, price returns
│   ├── eval/             # query sets, judges, RAGAS, stats
│   ├── store/            # DuckDB results, JSONL traces
│   └── api/              # FastAPI
├── web/                  # React + Vite + TypeScript playground
├── configs/              # universe.yaml, pipelines/, judges/, prompts/fare/
├── data/                 # raw/ and processed/ git-ignored; eval/ versioned
├── docs/                 # plan, HLD, fare/01–05
└── tests/
```
The existing `extract/` and `compute/` packages stay empty until Phase I. `retrieve/` becomes part of the stage packages above.

---

## Phase I (after Phase R) — moved from plan v1

- Verify the LODR taxonomy (`data/taxonomy/india_disclosure_taxonomy.v0.yaml`, 9 flagged items).
- Event extraction with quotes and second-pass scoring (Papers 1 & 2).
- Compute tools: pledge %, RPT ratios, results ratios, distress score, rumour price window; lakh/crore units.
- `NseSource` (NSE announcements API works; BSE blocks automated access).
- Personas, cited chat, and the Indian product features (Compass §5).
