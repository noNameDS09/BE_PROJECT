# Implementation Plan: FARE Replication + Risk Extraction

Status: Plan only — no code written yet.
Location: All coding in `Loupe/` folder.

---

## Phase 1: Foundation (Design — no code)

### R-1: Confirm Scope & Decisions (blocks all)
- Confirm India pivot with guide (Compass §3, issue #3)
- Confirm FARE PDF download (DOI 10.1109/ACCESS.2026.3689742)
- Confirm LLM budget: Qwen2.5-7B (extraction) + Gemini 2.5 Flash-Lite (judge)
- Confirm frozen dev/test split with version tags

### R-2: Data Contracts (`models/`)
- Shared Pydantic stubs: `Document`, `Chunk`, `Event`, `ComputeResult`, `AgentState`, `Trace`
- Agree interfaces between retrieve / extract / compute / agent

### R-3: Taxonomy Verification
- Verify `data/taxonomy/india_disclosure_taxonomy.v0.yaml` (47 types, 7 dims)
- Confirm 9 flagged items vs current LODR Schedule III
- Document deviations from Paper 2's 119-type taxonomy

---

## Phase 2: Replication Harness (FARE on SEC — Phase R)

### R-4: Stream A — Ingestion (`retrieve/`)
- `EdgarSource`: SEC EDGAR fetcher (CIK, 10-K/10-Q/8-K), polite rate, User-Agent
- `FilingParser`: HTML (EDGAR) + PyMuPDF (PDF transcripts)
- `Chunker`: Section-aware chunking, metadata filter
- `Store`: DuckDB + FAISS persistence
- Deliverable: Parser metrics on 30 filings; evidence-string recovery rate

### R-5: Stream B — Taxonomy & Extraction (`extract/`)
- `Taxonomy.load_taxonomy()` from YAML
- `EventExtractor`: LLM extraction + quote validation (Paper 1)
- `QualityScorer`: 2nd-pass 1–5 scoring (Paper 2 calibration — NOT "12%→96%")
- Deliverable: Gold-set annotation guide; extractor on 50 announcements

### R-6: Stream C — Compute (`compute/`)
- `pledge.py`, `rpt.py`, `results.py`, `distress.py`, `rumour.py`
- `units.py`: `normalize_amount()`, `parse_indian_number()` (lakh/crore, IndAS)
- `xbrl.py`: XBRL fact lookup
- Deliverable: Unit tests; exact-match vs 50 company-quarters

### R-7: Stream D — Agent Graph (`agent/`)
- `graph.py`: LangGraph planner → Retriever → Analysts → Synthesizer → Evaluator
- `tools.py`: `RetrieveTool`, `ComputeTool`, `XBRLTool` (typed, tested)
- `personas.py`: Research + Credit prompts
- `eval.py`: `EvaluationHarness` skeleton (E1–E5, layer metrics)
- Deliverable: B0 (LLM only) + B1 (plain RAG) baselines

### R-8: Replication Gate (Week 9)
- Run B0–B2 across models on E1, E3, E4, E5
- Each FARE claim: holds / partly / does not hold
- Judge-vs-human κ on 100-item subset
- Cost per correct answer logged
- Deliverable: Replication chapter results table

---

## Phase 3: Extension (Risk Framework + India Pivot — Phase I)

### I-1: Extension Mode (`agent/`)
- Enable `XBRLTool` + `ComputeTool` (B3)
- Add citation check + calibrated judge (B4)
- Deliverable: B3/B4 results; numeric error rate comparison

### I-2: India Data Source (`retrieve/nse.py`)
- `NseSource`: NSE announcements fetcher, polite, cached
- Confirm MCA portal access (CAPTCHA/paid) — drop from MVP if blocked
- Deliverable: 1 quarter announcements + 1 XBRL file for 5 companies

### I-3: India Taxonomy Integration (`extract/`)
- Replace SEC taxonomy refs with LODR v0 YAML
- Adapt prompts for Indian disclosure language (Reg 30, Schedule III)
- Deliverable: Extractor runs on Indian filings; quote validation passes

### I-4: Chat & Demo (`app/`)
- Chainlit or Streamlit front end
- Citation rendering, persona selection
- Deliverable: Thin chat calling one real tool by end of phase 1

---

## Blocking Edge Summary

```
R-1 (Scope) → R-2 (Contracts) → R-3 (Taxonomy)
                                      ↓
R-4 (Retrieve) ←────────────── R-5 (Extract) ←── R-6 (Compute)
     ↓                              ↓                  ↓
     └──────────────→ R-7 (Agent Graph) ←───────────┘
                              ↓
                         R-8 (Gate)
                              ↓
                    I-1 (Extension) → I-2 (NSE) → I-3 (Taxonomy) → I-4 (App)
```

---

## Basic Features (MVP — Compass §5)

**Core (must build):** F2 (LODR event extraction), F3 (deterministic compute), F4+F5 (cited chat, 2 personas), F11 (distress score), F9 (rumour tracker)

**Free (falls out):** F8 (screening SQL query), F10 (timeline sort)

**Stretch:** F6 (earnings notes), F14 (autonomous taxonomy loop), F12 (charts/exports)

**Deferred:** F1 full (MCA/news), F7 (DRHP teardown), F13 (portfolio aggregation)

---

## Decisions Needed This Week

1. India pivot confirmed? (If no, Phase R stays on SEC)
2. LLM budget & models? (Qwen2.5-7B + Gemini 2.5 Flash-Lite via API?)
3. Vector index? (FAISS flat CPU OK for replication corpus?)
4. Judge protocol? (Cross-family, fixed rubric, 100-item human subset?)
