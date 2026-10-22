# Experiments (shared results)

Results from runs on Ayush's machine, committed so the whole team can see them.
The raw stores (`data/processed/results.duckdb`, `data/logs/`) are git-ignored, so this folder is the shared copy.

| File | What it is |
|---|---|
| `results-ayush-2026-10-22.zip` | Every successful result row with its full stored answer (claims, citations, trace). Import it to see the runs in the Bench UI. |
| `pilot2-gold-num/results.csv` | Pilot 2: gold_num dev, 24 questions × 4 methods, scored by the **old** verifier |
| `pilot3-gold-num/results.csv` | Pilot 3: the same questions re-run after the verifier fixes in PR #12 |
| `llm-usage-by-model.csv` | Every LLM call made so far, grouped by model: calls, tokens, median latency |

Model availability tests (NVIDIA NIM, Ollama Cloud, Mistral, Groq, OpenRouter) are in [`docs/models.md`](../docs/models.md).

## See these runs in the Bench UI
```bash
uv run loupe eval import experiments/results-ayush-2026-10-22.zip
uv run loupe serve          # API; then: cd web && npm run dev → Leaderboard
```
Imports are keyed by `run_id`, so importing twice is safe.

## Pilot results: gold_num dev split
24 single-number questions from XBRL across the 8 dev companies. Model: `nim-nemotron-super`.

| Method | Pilot 2 accuracy | Pilot 2 hallucination | Pilot 3 accuracy | Pilot 3 hallucination | Tokens / question (P3) |
|---|---|---|---|---|---|
| B0: plain LLM, no retrieval | 0.00 | 1.00 | 0.00 | 1.00 | 1,018 |
| Single-shot RAG | 0.58 | 0.58 | 0.58 | 0.33 | 3,969 |
| ReAct | 1.00 | 0.13 | 1.00 | 0.04 | 9,651 |
| **Loupe-Orch v1** | 0.88 | 0.00 | **1.00** (22 of 24 ran) | **0.00** | 8,318 |

What this shows:
- **A plain LLM never gets these right.** B0 answered 0/24 correctly and every answer made an unsupported numeric claim. This is the hallucination baseline.
- **Single-shot RAG fails mostly at retrieval.** In 7 of its 10 misses the right number was never in the retrieved passages.
- **Loupe's three pilot 2 misses were checker bugs, not model errors.** "3M" was read as 3 million, a minus sign was stripped, and the "30" in "June 30" was checked as a value. Fixing them (PR #12) also lowered the measured hallucination of RAG and ReAct. The bugs inflated it for every method.
- **Loupe matches ReAct on accuracy** with no hallucinated claims and about 14% fewer tokens.

Caveats:
- This is a pilot: 24 items, 1 model, dev split only.
- Loupe's 2 missing items failed because the NVIDIA API stopped serving `nemotron-3-super` (see below), not because of a wrong answer. They need re-running before any number is quoted.

## What failed
- **2026-10-20, 19:24 IST:** NVIDIA NIM started returning `404 Function not found for account` for `nim-nemotron-super`. As a result, pilot 3's gold_calc and gold_trick runs (170 rows) failed and are not included here. Re-run them once the model responds again, or switch `--model` (e.g. `oc-gemma4-31b`).
- **Mistral Medium/Small:** rate-limited on the free tier. Only `ministral-14b` (the judge) works.
- **OpenRouter Gemma 4:** provider at capacity. `or-nemotron-super` works but is limited to 50 requests/day.
- **Groq:** works, but the free tier caps input at 7–8K tokens/min, so it's for short calls only.

## Next runs (anyone can pick these up; see docs/TEAM-TASKS.md)
1. Re-run gold_calc and gold_trick dev with a working model, all 4 methods.
2. Same three sets with `oc-gemma4-31b` and `nim-gpt-oss-20b`, to check the results hold across models (RQ5).
3. Give the other methods their own dev-tuning round (fairness rule in `docs/hypotheses.md`).

When you run something, export it and add it here:
`uv run loupe eval export experiments/results-<name>-<date>.zip`
