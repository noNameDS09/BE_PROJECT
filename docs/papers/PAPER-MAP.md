# Paper Map — Source of Truth

> Built 2026-09-29 by reading page 1 of every PDF in `ResearchPapers/`.
> Use this table when citing papers in SECTION-xx documents and slides.
> **It supersedes the paper tables in `COMPLETE-ANALYSIS.md` §3 and `SECTION-02-...md` §2.16, which mislabel 8 of the 15 files.**

## 1. What is actually in `ResearchPapers/`

| File | Actual title | Authors | Venue / ID | Pipeline role | Cited in proposal (`BE-Project-2.pdf`)? |
|---|---|---|---|---|---|
| Paper 1 | Taxonomy-Aligned Risk Extraction from 10-K Filings with Autonomous Improvement Using LLMs | Dolphin, Dursun, Blankenship, Adams, Pike (Massive.com) | arXiv 2601.15247 (Jan 2026) | **Extract** — 3-stage: LLM extraction with quotes → embedding map to taxonomy → LLM-as-judge; autonomous taxonomy refinement (F14) | Yes, as Paper 1 |
| Paper 2 | Grounded Event Extraction from SEC 8-K Filings with a Fine-Grained Taxonomy | Dolphin et al. (Massive.com) | arXiv 2607.08346 (Jul 2026) | **Extract** — 119-type, 3-tier event taxonomy; schema-constrained output; fuzzy n-gram quote validation; 2nd-pass 1–5 quality score | Yes, as Paper 2 |
| Paper 3 | Interpretable LLMs for Credit Risk: A Systematic Review and Taxonomy | Golec, AlabdulJalil | arXiv 2506.04290 (2025) | Lit survey — credit-risk / explainability | Yes, as Paper 3 |
| Paper 4 | Unlocking the Black Box: A Five-Dimensional Framework for Evaluating Explainable AI in Credit Risk | Ye, Chen | arXiv 2511.04980 (2025) | Lit survey — XAI evaluation (SHAP/LIME) | Yes, as Paper 4 |
| Paper 5 | Explainable Artificial Intelligence Credit Risk Assessment using Machine Learning | Shreya, Pathak (SRM Univ.) | arXiv 2506.19383 (2025) | Lit survey — XAI credit risk (XGBoost/LightGBM + SHAP) | **No** |
| Paper 6 | Model Risk Management for Generative AI in Financial Institutions | Bhattacharyya, Yu, et al. (Wells Fargo) | — | Governance — SR 11-7 MRM, hallucination/injection testing | Yes, as Paper 6 |
| Paper 7 | Governing Generative AI Across Financial Institutions: A Framework for Generative AI Risk Control | Mao, Lin, Kang, Wang | arXiv 2607.04103 (2026) | Agent architecture — 5 capability patterns incl. tool-using assistants and workflow orchestration | Yes, as Paper 7 |
| Paper 8 | Same Company, Same Signal: The Role of Identity in Earnings Call Transcripts | Yu, Liu, He (Rochester) | arXiv 2412.18029 (2024) | Evaluation caution — "Ticker Identity Trap" | Yes, as Paper 8 |
| Paper 9 | Can AI Read Between the Lines? Benchmarking LLMs on Financial Nuance | Kubica, Gordon, Emura, Saini, Goldenberg (Santa Clara) | arXiv 2505.16090 (2025) | Evaluation — LLM benchmarking on financial text | **No** |
| Paper 10 | FinDPO: Financial Sentiment Analysis for Algorithmic Trading through Preference Optimization of LLMs | Iacovides, Zhou, Mandic (Imperial) | arXiv 2507.18417 (2025) | Sentiment (F6 earnings) | Yes, as Paper 10 |
| Paper 11 | GraphRAG Analysis for Financial Narrative Summarization and A Framework for Optimizing Domain Adaptation | Shukla, Prabhakar, et al. (Oracle) | FinNLP workshop | Retrieval — GraphRAG vs RAG | Yes, as Paper 11 |
| Paper 12 | Familiar signal, new context: The evolution of earnings call sentiment analysis from lexicons to LLMs | Ao, Zhao (S&P Global) | S&P Global white paper (Sep 2025) | Sentiment (F6 earnings) | Yes, as Paper 12 |
| Paper 13 | Generative AI in Financial Institution: A Global Survey of Opportunities, Threats, and Regulation | Saha, Rani, Shukla (IIT Kanpur) | Survey (2025) | Lit survey / governance | Presentation slide 6 only |
| Paper 14 | Enhancing Trading Performance Through Sentiment Analysis with LLMs: Evidence from the S&P 500 | Liu, Lin, Rojas (UCLA) | arXiv 2507.09739 (2025) | Trading — **out of scope**, lit survey only | Presentation slide 6 only |
| Paper 15 | FinAI-BERT: A Transformer-Based Model for Sentence-Level Detection of AI Disclosures in Financial Reports | Zafar (UTM) | — | Sentence-level classification of disclosures | **No** |

## 2. Wrong labels to fix in existing docs

| Doc says | Truth |
|---|---|
| Paper 4 = Lombardo, bankruptcy prediction (IEEE Access 2024) | Paper 4 = Ye & Chen, XAI 5-D framework. Lombardo is **not in the folder**. |
| Paper 5 = FinDPO | FinDPO is **Paper 10**. Paper 5 = Shreya & Pathak XAI credit risk. |
| Paper 6 = Ticker Identity Trap | Ticker Trap is **Paper 8**. Paper 6 = Wells Fargo MRM. |
| Paper 8 = LLM earnings sentiment (Ao/Zhao) | Ao/Zhao is **Paper 12**. |
| Paper 9 = GraphRAG (Shukla) | GraphRAG is **Paper 11**. Paper 9 = Kubica et al. benchmark. |
| Paper 10 = Model Risk Management | MRM is **Paper 6**. Paper 10 = FinDPO. |
| Paper 11 = FinNLP proceedings, cross-cutting | Paper 11 is specifically the Shukla GraphRAG paper. |
| Paper 13 = Lombardo format reconstruction | Paper 13 = IIT Kanpur GenAI survey. Lombardo format-reconstruction is **not in the folder**. |
| `ARCHITECTURE-*.html`: "OCR … Lombardo method (Paper 4 / Papers 4/13)" | Neither Paper 4 nor 13 is Lombardo. Cite Lombardo et al. 2024 by name once the PDF is added. |
| "LLM-as-judge increases precision 12% → 96%" (proposal p. 6, architecture pages) | Paper 2 reports precision **by quality-score bin**: 12% at score 1, 96% at score 5. Score 5 keeps only 34% of tags; score ≥ 4 keeps 55% at 93%. The finding is that a *separate second pass* makes the score calibrated. |

Affected files: `COMPLETE-ANALYSIS.md` §3, `SECTION-02-FULL-DESCRIPTION-BASE-PAPER.md` §2.16 (and FARE sections), `ARCHITECTURE-ENGINES.html`, `ARCHITECTURE-LIGHT.html`.

## 3. Cited but missing from the folder (download these)

| Paper | Why it matters | Status |
|---|---|---|
| **FARE** — Chakraborty et al., *IEEE Access* 14:67362–67382, 2026, DOI 10.1109/ACCESS.2026.3689742 | **Primary base paper.** SECTION-02 describes its data, architecture and orchestration as "inferred". | Missing |
| RAMAS — Du, Zhao, Mao, Xing, Cambria, *IEEE Intelligent Systems* 40(2), 2025 | Multi-agent consensus → verification layer | Missing |
| Lombardo et al., NLP + DL for Bankruptcy Prediction, *IEEE Access* 12, 2024 | Distress early-warning (F11) | Missing |
| Lombardo et al., LM Fine-Tuning for Automatic Format Reconstruction of 10-K, *IEEE Access* 2024 | Messy-PDF ingestion | Missing |
| Sleipnir — Qian et al., *IEEE Access* 2026 | Multi-agent orchestration reference | Missing |
| Ferrag et al., From LLM Reasoning to Autonomous AI Agents, *IEEE Access* 2026 | Agent taxonomy survey | Missing |
| "Model-agnostic XAI Methods in Finance: A Systematic Review" (2025) | Presentation slide 5, row 3 | Missing |
| "AI Agents in Finance and Fintech: A Scientific Review" (2025) | Presentation slide 6, row 4 | Missing |

## 4. What the presentation already says about FARE

Slide 5 of `BE-Project-presentation-2.pdf` has concrete FARE details that SECTION-02 lacks. Confirm each against the paper before reusing:

- **Tools:** LangGraph, FAISS, PyMuPDF, SentenceTransformers
- **Method:** multi-agent framework, 6 specialised agents, orchestrated with LangGraph, RAG grounding
- **Findings:** Qwen2.5-7B-Instruct strongest reasoning; Gemini 2.5 Flash-Lite most efficient
- **Future scope:** human-in-the-loop validation, MCP integration, formal risk quantification
- **Limitations:** limited context windows, reliance on LLM-as-a-judge without human validation, no formal risk framework

FARE's own stated gaps (no formal risk framework, no human validation) are exactly what our taxonomy + deterministic compute + gold-set evaluation address. That makes a stronger novelty argument than the inferred table in SECTION-02 §2.14.
