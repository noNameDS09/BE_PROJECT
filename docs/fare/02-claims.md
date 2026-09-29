# FARE Claims Register

Every result FARE reports, as a hypothesis we test on SEC filings. Numbers are copied from the paper's Tables 3–8 (pp. 67374–67375).
Verdicts are filled at milestone M2 and updated at M3: **holds**, **partly**, **does not hold**, or **not testable** (with reason).

## Reported numbers (targets for reference, not for matching)

| Agent (metric) | Gemini 2.5 Flash | Gemini 2.5 Flash-Lite | Qwen2.5-7B-Instruct | Llama-3.2-3B-Instruct |
|---|---|---|---|---|
| Statement Extraction CP / F / RR | 0.52 / 0.96 / 0.71 | 0.52 / **0.99** / 0.73 | 0.48 / 0.82 / **0.84** | 0.47 / 0.83 / 0.82 |
| Statement Extraction latency (s) | 21.74 | **9.11** | 52.25 | 27.66 |
| Investment IRAS / latency | 0.53 / 182.55 | 0.61 / **60.99** | **0.63** / 609.15 | 0.39 / 380.43 |
| Comparison CAS / latency | 0.65 / 166.67 | 0.64 / **14.30** | 0.71 / 698.67 | **0.77** / 485.75 |
| Tone NI / OT / NA / TAEF | 1.93 / 2.00 / 1.99 / 0.99 | 1.98 / 1.99 / 1.99 / 0.99 | 2.00 / 2.00 / 2.00 / **1.00** | 1.89 / 1.67 / 1.83 / 0.90 |
| Tone latency (s) | 148.02 | **18.15** | 495.49 | 365.70 |
| Tone Shift TAS / latency | 0.55 / 110.63 | 0.67 / **30.92** | **0.87** / 191.21 | 0.75 / 126.53 |
| Simulation CODS / EAS / latency | 3.74 / 0.68 / 107.17 | 3.28 / 0.64 / **53.68** | **4.08** / **0.76** / 189.37 | 2.60 / 0.70 / 101.65 |

## Claims

| Id | Claim | Evidence in paper | How we test it | Verdict |
|---|---|---|---|---|
| C1 | Qwen2.5-7B-Instruct gives the strongest reasoning across most agents | Best IRAS, TAEF, TAS, CODS/EAS, RR; not CAS or Faithfulness | Rank models per agent on Q-FARE with CIs, same judge version | — |
| C2 | Gemini 2.5 Flash-Lite has the lowest latency on every agent | Tables 3–8 | Rank latency under our hosting; not comparable in absolute terms | — |
| C3 | Flash-Lite has the best efficiency (score ÷ latency) on every metric | Fig. 18 | Recompute Eq. 8 per agent | — |
| C4 | Gemini models are the most faithful to retrieved context | F 0.96 / 0.99 vs 0.82 / 0.83 | RAGAS Faithfulness on Q-FARE and Q-FIN | — |
| C5 | Context precision sits near 0.5 for every model at top-10 because relevant information is spread across chunks | CP 0.47–0.52 | CP with v0, then top-k sweep and reranker variants | — |
| C6 | Llama-3.2-3B is the weakest overall, yet best at comparison | IRAS 0.39, TAEF 0.90; CAS 0.77 | Only if a 3B-class model is in our model set | — |
| C7 | Tone refinement is near the ceiling for all models | TAEF 0.90–1.00 | TAEF on filings; check for ceiling effect with human grades (H-100) | — |
| C8 | Splitting tasks across specialised agents reasons better than a single-agent RAG system | Asserted (p. 67367), **not measured** | B2 vs B1 on the same queries, paired test | — |

C8 is the claim FARE does not test itself. Measuring it is one of our contributions.
