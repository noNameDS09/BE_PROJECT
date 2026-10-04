# FARE Extraction Sheet

Source: Chakraborty, Pathak, Smriti, Bhargava, Supriya, "FARE: Financial Agentic Reasoning and Evaluation for Earnings Call Transcripts", *IEEE Access* 14:67362–67382, 2026. DOI 10.1109/ACCESS.2026.3689742. Licensed CC BY 4.0.
Page numbers below are the journal's (67362–67382). PDF: `docs/FARE_Financial_Agentic_Reasoning_and_Evaluation_for_Earnings_Call_Transcripts.pdf`.

Status: **S** = specified, **P** = partly specified, **N** = not specified.
"Loupe choice" is filled for every P and N row and each is justified in `03-decisions.md`.

## Data and retrieval

| Element | FARE says | Page | Status | Loupe choice |
|---|---|---|---|---|
| Documents | Earnings-call transcripts (PDF) from company investor-relations sites | 67365 | S | SEC EDGAR 10-K, 10-Q, 8-K (decision D1) |
| Universe | 21 companies (Table 1), 8 most recent quarters each, 168 transcripts | 67365–66 | S | Team's 25 companies, FY2023–FY2025 (D2) |
| Parsing | PyMuPDF; remove page boundaries, headers, footers, irregular spacing; keep speaker labels and Prepared Remarks / Q&A sections | 67365 | P | HTML → text; keep filing Item headings |
| Chunking | Recursive character split, 800 chars, 100 overlap, separators paragraph → line → whitespace | 67365 | S | LangChain `RecursiveCharacterTextSplitter` defaults (library not named in paper) |
| Chunk metadata | `chunk_id`, `company`, `quarter`, `year` | 67366 | S | + `cik`, `form`, `accession`, `section`, `filed_at` |
| Embeddings | SentenceTransformers `all-MiniLM-L6-v2`, 384-d | 67366 | S | Same (v0) |
| Index | FAISS `IndexFlatL2`, exact search | 67366 | S | Same (v0) |
| Top-k | k = 10 | 67367 | S | Same (v0) |
| Metadata filtering | Agents receive "retrieved and filtered chunks"; Tone agent reads only the requested quarter | 67367–68 | P | Pre-filter by company and period before search |
| Batch-wise reading | Agents read chunks in batches because of context limits; batch size held constant | 67367 | P | Batch size N (not given) — choose and record |

## Orchestration and agents

| Element | FARE says | Page | Status | Loupe choice |
|---|---|---|---|---|
| Framework | LangGraph; nodes = agents; shared state carries agent response and user portfolio | 67367 | S | Same |
| Orchestrator | LLM routing prompt maps each query to one task category; ambiguous → dominant intent; one agent per query | 67366 | P (prompt N) | Reconstructed routing prompt |
| Prompt style | Role-based ("Tone Analyst", "Investment Advisor") with Chain-of-Thought | 67367 | P (text N) | Reconstructed prompts, versioned, labelled as reconstructions |
| Decoding | Temperature and other parameters | — | N | Temperature 0 |
| Statement Extraction | Semantic search, answer citing speaker and quotes | 67370 | S | Cite filing section and quotes |
| Tone | Batch-wise per-section tone (confident, optimistic, cautious, mixed, uncertain) | 67367–68 | S | Same, on MD&A and earnings release |
| Tone critic | Critic calls Google Search for analyst tone and asks Tone to revise; one-shot example guides revision | 67368 | P | See ambiguity below |
| Investment | Portfolio (companies, risk profile light/moderate/high, amount, reason, date) → hold / re-evaluate / sell | 67368–69 | S | Replaced by Thesis Check, no recommendation (D4) |
| Tone Shift | Start and end quarter; infer the quarters between; per-quarter tone; tone evolution map | 67369 | S | Same, on consecutive filing periods |
| Simulation | Actual vs hypothetical company from the investment quarter plus 2–4 later quarters; 3-part output (missed opportunity, narrative, guidance) | 67369–70 | S | Replaced by Scenario: parts 1–2 only; returns computed by code (D4) |
| Comparison | Companies + topic + quarter; per-company batch analysis; comparative summary | 67370 | S | Same |
| Single-agent baseline | Described as the contrast case, never run | 67367 | — | Run as B1 |

**Ambiguity:** p. 67368 says the Tone Critic "provides feedback to the Tone Agent, asking it to make changes" and also that it "is used exclusively during the evaluation phase and is not involved in the inference-time response generation". Record the choice in `03-decisions.md`.

## Models and hardware

| Element | FARE says | Page | Status | Loupe choice |
|---|---|---|---|---|
| Backbones | Gemini 2.5 Flash, Gemini 2.5 Flash-Lite, Qwen2.5-7B-Instruct, Llama-3.2-3B-Instruct | 67367 | S | 2–4 hosted models (D3) |
| Hardware | Qwen and Llama on one NVIDIA T4 (Colab); Gemini via API | 67367 | S | Hosted APIs; latency not comparable |
| Held constant | Batch size, top-k and other hyperparameters equal across agents and models | 67367 | S | Same, via pipeline config |

## Evaluation

| Element | FARE says | Page | Status | Loupe choice |
|---|---|---|---|---|
| Judge setup | One LLM evaluator per agent; Google Search retrieves analyst commentary as reference; search used only in evaluation | 67370 | P (judge model and prompts N) | `judge-v1-google` (D5) |
| TAEF (Tone) | NI + OT + NA, each 0–2; TAEF = (NI + OT + NA) / 6 | 67371 | S | Same |
| IRAS (Investment) | 0.35·PC + 0.25·RF + 0.20·CC + 0.20·RFid, each 0–1; bands > 0.7, 0.4–0.7, < 0.4 | 67371 | S | Adapted for Thesis Check |
| TAS (Tone Shift) | Four dimensions (quarter match, trajectory, evidence use, confidence); bands > 0.9 … < 0.5 | 67371–72 | P (aggregation N) | Equal weights, normalised |
| EAS (Simulation) | Performance correctness, risk alignment, CODS (1–5); range 0–1 | 67372 | P (aggregation N) | Adapted for Scenario |
| CAS (Comparison) | (Σ FAᵢ + RA) / (2M + 2), each 0–2 | 67372 | S | Same |
| RAGAS | Context Precision (Eq. 4–5), Faithfulness (Eq. 6), Response Relevancy (Eq. 7, N = 3 generated questions) | 67372–73 | S | RAGAS library, same settings |
| Query counts | Statement Extraction 105, Investment 21, Comparison 200, Tone 105, Tone Shift 63, Simulation 50 (Table 2) | 67374 | S (queries N) | Regenerate with the same sampling rules |
| Latency | Reported per agent; Efficiency = metric score / latency (Eq. 8) | 67378 | P (how measured N) | End-to-end wall time per query |

## Stated limitations and future work (p. 67380)

No expert validation of the judge metrics; limited tools, no MCP; qualitative risk analysis only. Future: human-expert validation, ADK + MCP + more tools, ablations of embedding models and chunking (including dialogue-aware), formal risk quantification.
